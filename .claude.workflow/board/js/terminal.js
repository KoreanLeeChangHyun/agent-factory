/**
 * @module terminal (core)
 *
 * Board SPA terminal tab module — core orchestrator.
 *
 * Provides Markdown renderer, constants, state variables, output div management,
 * smart scroll, tool box renderer, thinking spinner, input management, UI update,
 * main render, and Board namespace registration.
 *
 * External modules are accessed via Board namespace:
 *   Board.ToolResultRenderer.dispatch()
 *   Board.WorkflowRenderer.tap()
 *   Board.phaseTimeline.render()
 *   Board.slashCommands.handle()
 *   Board.workflowSessions.refresh()
 *   Board.session.*
 *
 * Depends on: common.js, renderers.js, workflow-bar.js, slash-commands.js,
 *             workflow-sessions.js, session.js
 * Optional:   marked.js (CDN, fallback to plain text if unavailable)
 */
"use strict";

(function () {
  var esc = Board.util.esc;

  // ── Markdown Renderer (marked.js wrapper with fallback) ──

  var _termMermaidCounter = 0;
  var _markedConfigured = false;

  function initMarked() {
    if (typeof marked === "undefined") return;
    if (_markedConfigured) return;
    _markedConfigured = true;

    marked.use({
      breaks: true,
      gfm: true,
      renderer: {
        code: function (token) {
          var text = token.text;
          var lang = token.lang;
          if (lang === "mermaid") {
            var mid = "term-mermaid-" + (++_termMermaidCounter);
            return '<div class="mermaid-block" data-mermaid-id="' + mid + '">' + esc(text) + '</div>';
          }
          var langLabel = lang ? esc(lang) : "code";
          var highlighted = "";
          if (typeof hljs !== "undefined" && lang && hljs.getLanguage(lang)) {
            try {
              highlighted = hljs.highlight(text, { language: lang }).value;
            } catch (e) {
              highlighted = "";
            }
          }
          if (!highlighted) {
            highlighted = token.escaped ? text : esc(text);
          }
          return '<pre class="term-code-block"><span class="term-code-lang">' + langLabel + '</span><code class="lang-' + esc(lang || "") + '">' + highlighted + '</code></pre>';
        },

        codespan: function (token) {
          return '<code class="term-inline-code">' + token.text + '</code>';
        },

        heading: function (token) {
          var depth = token.depth;
          return '<h' + depth + ' class="term-heading">' + token.text + '</h' + depth + '>';
        },

        table: function (token) {
          var header = "";
          for (var i = 0; i < token.header.length; i++) {
            header += '<th>' + token.header[i].text + '</th>';
          }
          var body = "";
          for (var r = 0; r < token.rows.length; r++) {
            var row = token.rows[r];
            var cells = "";
            for (var c = 0; c < row.length; c++) {
              cells += '<td>' + row[c].text + '</td>';
            }
            body += '<tr>' + cells + '</tr>';
          }
          return '<table class="term-table"><thead><tr>' + header + '</tr></thead><tbody>' + body + '</tbody></table>';
        },

        list: function (token) {
          var tag = token.ordered ? "ol" : "ul";
          var body = "";
          for (var i = 0; i < token.items.length; i++) {
            var itemContent = this.parser.parseInline(token.items[i].tokens);
            body += '<li>' + itemContent + '</li>';
          }
          return '<' + tag + ' class="term-list">' + body + '</' + tag + '>';
        },

        paragraph: function (token) {
          return '<p class="term-para">' + token.text + '</p>';
        },

        link: function (token) {
          var t = token.title ? ' title="' + esc(token.title) + '"' : '';
          return '<a href="' + esc(token.href) + '"' + t + ' target="_blank" rel="noopener">' + token.text + '</a>';
        }
      }
    });
  }

  function renderMarkdownToHtml(text) {
    if (typeof marked !== "undefined" && marked.parse) {
      if (!_markedConfigured) initMarked();
      try {
        var html = marked.parse(text);
        // Mermaid blocks need post-insert init (DOM not ready until caller appends)
        if (Board.render && Board.render.initMermaid) {
          setTimeout(Board.render.initMermaid, 0);
        }
        return html;
      } catch (e) {
        // marked.js parse failure -- fallback
      }
    }
    return '<pre class="term-fallback">' + esc(text) + '</pre>';
  }

  // ── Constants ──
  var MAX_OUTPUT_NODES = 10000;

  // ── Session dispatcher ──
  var workflowSessionId = (function () {
    try {
      var p = new URLSearchParams(window.location.search);
      var s = p.get("session");
      if (s && s !== "main" && s.indexOf("wf-") === 0) return s;
    } catch (e) {}
    return null;
  })();
  var isWorkflowMode = workflowSessionId !== null;

  // URL 쿼리 파라미터에서 읽은 초기 세션 ID (renderTerminal 후 탭 전환에 사용)
  var _initialQuerySession = workflowSessionId;

  // ── Session Switcher State ──
  // 세션별 상태를 저장하는 맵. key = sessionId ("main" 또는 "wf-T-NNN-...")
  var _sessionMap = {};
  // 현재 활성 세션 ID
  var _activeSessionId = isWorkflowMode ? workflowSessionId : "main";

  /**
   * 세션 항목 생성 헬퍼.
   * @param {string} sessionId
   * @returns {object}
   */
  function _createSessionEntry(sessionId) {
    return {
      id: sessionId,
      isWorkflow: sessionId !== "main",
      outputNodes: [],   // outputDiv 자식 노드 스냅샷 (Array<Node>)
      cost: 0,
      tokens: { input: 0, output: 0 },
      model: "--",
      status: sessionId === "main" ? "stopped" : "running",
      inputQueue: []
    };
  }

  // 초기 세션 등록 (main + 현재 워크플로우 세션이 있으면 그것도)
  _sessionMap["main"] = _createSessionEntry("main");
  if (isWorkflowMode && workflowSessionId) {
    _sessionMap[workflowSessionId] = _createSessionEntry(workflowSessionId);
  }

  function endpoints() {
    if (isWorkflowMode) {
      var sid = encodeURIComponent(workflowSessionId);
      return {
        events: "/terminal/workflow/events?session_id=" + sid,
        input: "/terminal/workflow/input",
        kill: "/terminal/workflow/kill",
        status: "/terminal/workflow/status?session_id=" + sid,
        inputBody: function (extra) {
          var b = { session_id: workflowSessionId };
          for (var k in extra) if (extra.hasOwnProperty(k)) b[k] = extra[k];
          return b;
        },
      };
    }
    return {
      events: "/terminal/events",
      input: "/terminal/input",
      kill: "/terminal/kill",
      status: "/terminal/status",
      inputBody: function (extra) { return extra; },
    };
  }

  // ── State ──
  Board.state.termConnected = false;
  Board.state.termSessionId = isWorkflowMode ? workflowSessionId : null;
  Board.state.termStatus = isWorkflowMode ? "running" : "stopped";
  Board.state.termLastSessionId = null;

  /** @type {HTMLElement|null} */
  var outputDiv = null;
  /** @type {HTMLElement|null} */
  var currentToolBox = null;
  /** @type {Object<string, HTMLElement>} toolUseId -> box element */
  var toolBoxMap = {};
  /** @type {boolean} */
  var termInitialized = false;
  /** @type {boolean} */
  var inputLocked = false;
  /** @type {Array<string>} */
  var inputQueue = [];
  /** @type {Array<{data: string, media_type: string, name: string}>} */
  var attachedImages = [];
  /** @type {Array<{file: File, name: string, size: number, type: string}>} */
  var attachedFiles = [];
  /** @type {boolean} */
  var receivedChunks = false;
  /** @type {string} */
  var textBuffer = "";
  /** @type {string} */
  var toolInputBuffer = "";
  /** @type {string|null} */
  var currentToolName = null;
  /** @type {number} */
  var sessionCost = 0;
  /** @type {object} */
  var sessionTokens = { input: 0, output: 0 };
  /** @type {string} */
  var sessionModel = '--';
  /** @type {number} */
  var contextWindow = 1000000;

  // ── Output Div Management ──

  function initOutputDiv() {
    outputDiv = document.getElementById("terminal-output");
    if (!outputDiv) return;

    outputDiv.innerHTML = "";
    if (isWorkflowMode) {
      // 워크플로우 모드: "Workflow Session: ..." 시스템 메시지는 탭 바 활성 탭으로 대체.
      // 스트림 연결 중 메시지만 표시한다.
      appendSystemMessage("Connecting to live stream...");
    } else {
      appendSystemMessage("Claude Code Terminal");
      appendSystemMessage('Press "Start" to begin a session.');
    }

    initMarked();

    // Wire up renderMarkdownToHtml for renderers.js
    if (Board.ToolResultRenderer && Board.ToolResultRenderer.setMarkdownRenderer) {
      Board.ToolResultRenderer.setMarkdownRenderer(renderMarkdownToHtml);
    }
  }

  // ── Smart Auto-Scroll ──
  var SCROLL_NEAR_BOTTOM_THRESHOLD = 100;

  function isNearBottom(el) {
    if (!el) return true;
    return (el.scrollHeight - el.scrollTop - el.clientHeight) <= SCROLL_NEAR_BOTTOM_THRESHOLD;
  }

  function scrollToBottomIfFollowing(el, wasNearBottom) {
    if (el && wasNearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }

  // Expose scroll helpers for workflow-bar.js
  Board._term = Board._term || {};
  Board._term.isNearBottom = isNearBottom;
  Board._term.scrollToBottomIfFollowing = scrollToBottomIfFollowing;

  function appendToOutput(el) {
    if (!outputDiv) return;

    var follow = isNearBottom(outputDiv);

    while (outputDiv.childNodes.length >= MAX_OUTPUT_NODES) {
      outputDiv.removeChild(outputDiv.firstChild);
    }

    outputDiv.appendChild(el);
    scrollToBottomIfFollowing(outputDiv, follow);
  }

  function appendHtmlBlock(html, className) {
    var div = document.createElement("div");
    if (className) div.className = className;
    div.innerHTML = html;
    appendToOutput(div);
  }

  function appendSystemMessage(text) {
    var div = document.createElement("div");
    div.className = "term-system";
    div.textContent = text;
    appendToOutput(div);
  }

  function appendErrorMessage(text) {
    var div = document.createElement("div");
    div.className = "term-error";
    div.textContent = text;
    appendToOutput(div);
  }

  // ── UI Helpers ──

  function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatRelativeTime(isoString) {
    if (!isoString) return "";
    var dt;
    try {
      dt = new Date(isoString);
    } catch (_e) {
      return String(isoString);
    }
    var ts = dt.getTime();
    if (isNaN(ts)) return String(isoString);

    var diffSec = Math.floor((Date.now() - ts) / 1000);
    if (diffSec < 0) diffSec = 0;
    if (diffSec < 60) return "방금 전";
    var diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return diffMin + "분 전";
    var diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return diffHour + "시간 전";
    var diffDay = Math.floor(diffHour / 24);
    if (diffDay < 7) return diffDay + "일 전";
    // 7일 이상은 날짜 표기
    try {
      return dt.toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" });
    } catch (_e2) {
      return String(isoString);
    }
  }

  // ── Tool Box Renderer ──

  function createToolBox(toolName, toolUseId) {
    // 이전 도구 박스가 아직 running이면 done으로 전환
    if (currentToolBox) {
      var prevStatus = currentToolBox.querySelector(".term-tool-status");
      if (prevStatus && prevStatus.classList.contains("running")) {
        prevStatus.className = "term-tool-status done";
        prevStatus.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#3fb950" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
      }
      // 이전 박스의 출력이 비어있으면 DOM에서 선제 제거
      var prevFull = currentToolBox.querySelector(".term-tool-output-full");
      if (prevFull && prevFull.children.length === 0 && !prevFull.textContent.trim()) {
        currentToolBox.remove();
        currentToolBox = null;
      }
    }

    var box = document.createElement("div");
    box.className = "term-tool-box";
    if (toolName) {
      box.setAttribute("data-tool-name", toolName);
    }
    if (toolUseId) {
      box.setAttribute("data-tool-use-id", toolUseId);
      toolBoxMap[toolUseId] = box;
    }

    var header = document.createElement("div");
    header.className = "term-tool-header";

    var toggleSpan = document.createElement("span");
    toggleSpan.className = "term-toggle-icon";
    toggleSpan.innerHTML = '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 2.5L7.5 6 4 9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    header.appendChild(toggleSpan);

    var labelSpan = document.createElement("span");
    labelSpan.className = "term-tool-label";
    labelSpan.textContent = toolName;
    header.appendChild(labelSpan);

    var statusSpan = document.createElement("span");
    statusSpan.className = "term-tool-status running";
    statusSpan.innerHTML = '<span class="term-tool-status-dot"></span>';
    header.appendChild(statusSpan);

    box.appendChild(header);

    var inputDiv = document.createElement("div");
    inputDiv.className = "term-tool-input";
    box.appendChild(inputDiv);

    var outputArea = document.createElement("div");
    outputArea.className = "term-tool-output";

    var previewDiv = document.createElement("div");
    previewDiv.className = "term-tool-output-preview";
    outputArea.appendChild(previewDiv);

    var fullDiv = document.createElement("div");
    fullDiv.className = "term-tool-output-full";
    outputArea.appendChild(fullDiv);

    box.appendChild(outputArea);

    toggleSpan.addEventListener("click", function () {
      var isOpen = box.classList.toggle("open");
      toggleSpan.classList.toggle("rotated", isOpen);
    });

    appendToOutput(box);
    currentToolBox = box;

    return box;
  }

  function removeEmptyToolBox(targetToolUseId) {
    // 특정 toolUseId가 지정된 경우 해당 박스만 정리
    if (targetToolUseId && toolBoxMap[targetToolUseId]) {
      var targetBox = toolBoxMap[targetToolUseId];
      var targetFull = targetBox.querySelector(".term-tool-output-full");
      if (targetFull && targetFull.children.length === 0 && !targetFull.textContent.trim()) {
        if (targetBox.parentNode) {
          targetBox.parentNode.removeChild(targetBox);
        }
        delete toolBoxMap[targetToolUseId];
        if (currentToolBox === targetBox) {
          currentToolBox = null;
        }
      }
    }

    // currentToolBox 정리 (하위 호환)
    if (currentToolBox) {
      var fullDiv = currentToolBox.querySelector(".term-tool-output-full");
      if (fullDiv && fullDiv.children.length === 0 && !fullDiv.textContent.trim()) {
        if (currentToolBox.parentNode) {
          currentToolBox.parentNode.removeChild(currentToolBox);
        }
        currentToolBox = null;
      }
    }

    // toolBoxMap 내 빈 박스 일괄 정리
    var mapKeys = Object.keys(toolBoxMap);
    for (var mi = 0; mi < mapKeys.length; mi++) {
      var mapBox = toolBoxMap[mapKeys[mi]];
      var mapFull = mapBox.querySelector(".term-tool-output-full");
      if (mapFull && mapFull.children.length === 0 && !mapFull.textContent.trim()) {
        if (mapBox.parentNode) {
          mapBox.parentNode.removeChild(mapBox);
        }
        delete toolBoxMap[mapKeys[mi]];
      }
    }

    // DOM 직접 순회: toolBoxMap에 등록되지 않은 잔존 빈 박스도 정리
    if (outputDiv) {
      var domBoxes = outputDiv.querySelectorAll(".term-tool-box");
      for (var di = 0; di < domBoxes.length; di++) {
        var domBox = domBoxes[di];
        var domFull = domBox.querySelector(".term-tool-output-full");
        if (domFull && domFull.children.length === 0 && !domFull.textContent.trim()) {
          var domToolUseId = domBox.getAttribute("data-tool-use-id");
          if (domBox.parentNode) {
            domBox.parentNode.removeChild(domBox);
          }
          if (domToolUseId && toolBoxMap[domToolUseId]) {
            delete toolBoxMap[domToolUseId];
          }
          if (currentToolBox === domBox) {
            currentToolBox = null;
          }
        }
      }
    }

    // 워크플로우 모드 카드도 함께 정리
    removeEmptyWorkflowToolCard();
  }

  function removeEmptyWorkflowToolCard() {
    if (!currentWorkflowToolCard) return;
    var cardBody = currentWorkflowToolCard.querySelector(".wf-tool-card-body");
    if (cardBody && cardBody.children.length === 0 && !cardBody.textContent.trim()) {
      if (currentWorkflowToolCard.parentNode) {
        currentWorkflowToolCard.parentNode.removeChild(currentWorkflowToolCard);
      }
      currentWorkflowToolCard = null;
    }
  }

  function isFlowCommand(commandStr) {
    return /^flow-/.test((commandStr || '').trim());
  }

  function _formatFlowCommand(cmdStr) {
    var raw = (cmdStr || '').replace(/^\$\s*/, '');
    // Split into base command and --args, respecting quoted strings
    var parts = [];
    var base = '';
    var re = /(--\S+)\s+("(?:[^"\\]|\\.)*"|\S+)/g;
    var firstArgIdx = raw.search(/\s--/);
    if (firstArgIdx > 0) {
      base = raw.substring(0, firstArgIdx).trim();
    } else {
      base = raw;
    }
    var m;
    while ((m = re.exec(raw)) !== null) {
      var key = m[1];
      var val = m[2].replace(/^"|"$/g, '');
      parts.push({ key: key, val: val });
    }
    if (!parts.length) {
      return '<span class="flow-cmd-base">' + esc(raw) + '</span>';
    }
    var html = '<span class="flow-cmd-base">' + esc(base) + '</span>';
    for (var i = 0; i < parts.length; i++) {
      var displayVal = parts[i].val.length > 80
        ? parts[i].val.substring(0, 80) + '\u2026'
        : parts[i].val;
      html += '<div class="flow-cmd-arg">'
        + '<span class="flow-cmd-key">' + esc(parts[i].key) + '</span> '
        + '<span class="flow-cmd-val">' + esc(displayVal) + '</span>'
        + '</div>';
    }
    return html;
  }

  function insertToolResult(text, isError, toolName, toolUseId) {
    // toolUseId가 있으면 toolBoxMap에서 대상 박스 조회, 없으면 currentToolBox fallback
    var targetBox = (toolUseId && toolBoxMap[toolUseId]) ? toolBoxMap[toolUseId] : currentToolBox;
    if (!targetBox) return;
    if (!text && !isError) { removeEmptyToolBox(toolUseId); return; }
    var fullDiv = targetBox.querySelector(".term-tool-output-full");
    if (!fullDiv) return;

    var resolvedToolName = toolName;
    if (!resolvedToolName && targetBox.getAttribute) {
      resolvedToolName = targetBox.getAttribute("data-tool-name") || undefined;
    }

    var inputDiv = targetBox.querySelector(".term-tool-input");
    var isFlow = false;
    var flowCommand = "";
    if (toolInputBuffer && inputDiv) {
      var inputSummary = "";
      try {
        var parsedInput = JSON.parse(toolInputBuffer);
        var effectiveToolName = resolvedToolName || currentToolName;
        if (effectiveToolName === "Bash" && parsedInput.command) {
          inputSummary = "$ " + parsedInput.command;
          if (isFlowCommand(parsedInput.command)) {
            isFlow = true;
            flowCommand = parsedInput.command;
          }
        } else if ((effectiveToolName === "Read" || effectiveToolName === "Write" || effectiveToolName === "Edit") && parsedInput.file_path) {
          inputSummary = parsedInput.file_path;
        } else if (effectiveToolName === "Grep" && parsedInput.pattern) {
          inputSummary = parsedInput.pattern + (parsedInput.path ? "  " + parsedInput.path : "");
        } else if (effectiveToolName === "Glob" && parsedInput.pattern) {
          inputSummary = parsedInput.pattern;
        } else {
          var pairs = [];
          var keys = Object.keys(parsedInput);
          for (var ki = 0; ki < keys.length && ki < 3; ki++) {
            var v = parsedInput[keys[ki]];
            if (typeof v === "string") {
              pairs.push(keys[ki] + ": " + (v.length > 40 ? v.slice(0, 40) + "\u2026" : v));
            }
          }
          inputSummary = pairs.join("  ");
        }
      } catch (_e) {
        inputSummary = "";
      }
      if (isFlow && inputSummary) {
        inputDiv.innerHTML = _formatFlowCommand(inputSummary);
      } else {
        inputDiv.textContent = inputSummary;
      }
      toolInputBuffer = "";
    } else if (toolInputBuffer) {
      toolInputBuffer = "";
    }

    if (isFlow) {
      targetBox.setAttribute("data-flow-cmd", "true");
      var labelEl = targetBox.querySelector(".term-tool-label");
      if (labelEl) {
        labelEl.textContent = "Flow";
      }
    }

    var html;
    try {
      html = Board.ToolResultRenderer.dispatch(resolvedToolName, text, { isError: !!isError });
    } catch (e) {
      html = '<pre class="term-plain">' + esc(text || '') + '</pre>';
    }

    var container = document.createElement("div");
    container.className = isError ? "term-tool-error" : "term-tool-result-rendered";
    container.innerHTML = html;
    fullDiv.appendChild(container);

    var effectiveTool = resolvedToolName || currentToolName;
    var toggleIcon = targetBox.querySelector(".term-toggle-icon");
    var isFlowBox = targetBox.getAttribute("data-flow-cmd") === "true";
    if (isFlowBox) {
      targetBox.classList.add("open");
      if (toggleIcon) toggleIcon.classList.add("rotated");
    } else {
      targetBox.classList.remove("open");
      if (toggleIcon) toggleIcon.classList.remove("rotated");
    }

    var statusEl = targetBox.querySelector(".term-tool-status");
    if (statusEl) {
      statusEl.className = isError ? "term-tool-status error" : "term-tool-status done";
      statusEl.innerHTML = isError
        ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#f85149" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
        : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#3fb950" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    }

    if (!isError) {
      var previewDiv = targetBox.querySelector(".term-tool-output-preview");
      if (previewDiv) {
        var lines = (text || "").split("\n");
        var previewLines = lines.slice(0, 4);
        previewDiv.textContent = previewLines.join("\n");
      }
    }

    // 결과 삽입 완료 후 toolBoxMap에서 해당 항목 제거 (메모리 누수 방지)
    if (toolUseId && toolBoxMap[toolUseId]) {
      delete toolBoxMap[toolUseId];
    }
  }

  // ── Workflow Tool Card Renderer ──

  /**
   * Formats elapsed milliseconds into a human-readable duration string.
   * < 1000ms  → "< 1s"
   * 1s–59s    → "X.Xs"  (one decimal place)
   * 60s–59m   → "Xm Ys"
   * ≥ 60min   → "Xh Ym"
   * @param {number} ms - elapsed time in milliseconds
   * @returns {string}
   */
  function formatDuration(ms) {
    if (ms < 1000) return "< 1s";
    var totalSec = ms / 1000;
    if (totalSec < 60) return totalSec.toFixed(1) + "s";
    var totalMin = Math.floor(totalSec / 60);
    var remSec = Math.floor(totalSec % 60);
    if (totalMin < 60) return totalMin + "m " + remSec + "s";
    var hours = Math.floor(totalMin / 60);
    var remMin = totalMin % 60;
    return hours + "h " + remMin + "m";
  }

  /**
   * Creates a compact tool card for workflow step panels.
   * Unlike the full 3-row createToolBox(), this renders:
   *   tool name + input summary (1 line) + collapsible output
   * @param {string} toolName
   * @returns {HTMLElement} the card element
   */
  function createWorkflowToolCard(toolName) {
    var panel = Board.WorkflowRenderer.getActiveStepPanel();
    if (!panel) {
      // Fallback: ensure step panel exists
      Board.WorkflowRenderer.getOrCreateStepPanel(
        Board.WorkflowRenderer.state.currentStep || "init"
      );
    }

    var card = document.createElement("div");
    card.className = "wf-tool-card";
    if (toolName) {
      card.setAttribute("data-tool-name", toolName);
    }

    var cardHeader = document.createElement("div");
    cardHeader.className = "wf-tool-card-header";

    var toggleIcon = document.createElement("span");
    toggleIcon.className = "wf-tool-card-toggle";
    toggleIcon.innerHTML = '<svg width="10" height="10" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 2.5L7.5 6 4 9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    cardHeader.appendChild(toggleIcon);

    var toolLabel = document.createElement("span");
    toolLabel.className = "wf-tool-card-name";
    toolLabel.textContent = toolName || "";
    cardHeader.appendChild(toolLabel);

    var inputSpan = document.createElement("span");
    inputSpan.className = "wf-tool-card-input";
    cardHeader.appendChild(inputSpan);

    var timeSpan = document.createElement("span");
    timeSpan.className = "wf-tool-card-time";
    cardHeader.appendChild(timeSpan);

    card.appendChild(cardHeader);
    card.setAttribute("data-start-time", String(Date.now()));

    var cardBody = document.createElement("div");
    cardBody.className = "wf-tool-card-body";
    card.appendChild(cardBody);

    // Toggle collapse
    toggleIcon.addEventListener("click", function () {
      var isOpen = card.classList.toggle("open");
      toggleIcon.classList.toggle("rotated", isOpen);
    });

    // Append to current step panel
    Board.WorkflowRenderer.appendDomToCurrentPanel(card);

    // Track as current tool card for workflow mode
    currentWorkflowToolCard = card;
    return card;
  }

  /**
   * Insert tool result into current workflow step panel via compact card.
   * Reuses Board.ToolResultRenderer.dispatch() for HTML generation.
   * @param {string} text - raw output text
   * @param {boolean} isError - error flag
   * @param {string} [toolName] - optional tool name override
   */
  function insertWorkflowResult(text, isError, toolName) {
    if (!text && !isError) return;

    var card = currentWorkflowToolCard;
    if (!card) return;

    var cardBody = card.querySelector(".wf-tool-card-body");
    if (!cardBody) return;

    var resolvedToolName = toolName;
    if (!resolvedToolName && card.getAttribute) {
      resolvedToolName = card.getAttribute("data-tool-name") || undefined;
    }

    // Populate input summary on the card header
    var inputSpan = card.querySelector(".wf-tool-card-input");
    var isFlowWf = false;
    var flowCommandWf = "";
    if (toolInputBuffer && inputSpan && !inputSpan.textContent) {
      var inputSummary = "";
      try {
        var parsedInput = JSON.parse(toolInputBuffer);
        var effectiveToolName = resolvedToolName || currentToolName;
        if (effectiveToolName === "Bash" && parsedInput.command) {
          inputSummary = "$ " + parsedInput.command;
          if (isFlowCommand(parsedInput.command)) {
            isFlowWf = true;
            flowCommandWf = parsedInput.command;
          }
        } else if ((effectiveToolName === "Read" || effectiveToolName === "Write" || effectiveToolName === "Edit") && parsedInput.file_path) {
          inputSummary = parsedInput.file_path;
        } else if (effectiveToolName === "Grep" && parsedInput.pattern) {
          inputSummary = parsedInput.pattern + (parsedInput.path ? "  " + parsedInput.path : "");
        } else if (effectiveToolName === "Glob" && parsedInput.pattern) {
          inputSummary = parsedInput.pattern;
        } else {
          var pairs = [];
          var keys = Object.keys(parsedInput);
          for (var ki = 0; ki < keys.length && ki < 3; ki++) {
            var v = parsedInput[keys[ki]];
            if (typeof v === "string") {
              pairs.push(keys[ki] + ": " + (v.length > 40 ? v.slice(0, 40) + "\u2026" : v));
            }
          }
          inputSummary = pairs.join("  ");
        }
      } catch (_e) {
        inputSummary = "";
      }
      inputSpan.textContent = inputSummary;
      toolInputBuffer = "";
    } else if (toolInputBuffer) {
      toolInputBuffer = "";
    }

    if (isFlowWf) {
      card.setAttribute("data-flow-cmd", "true");
      var cardNameEl = card.querySelector(".wf-tool-card-name");
      if (cardNameEl) {
        cardNameEl.textContent = "Flow";
      }
      var cardToggle = card.querySelector(".wf-tool-card-toggle");
      card.classList.add("open");
      if (cardToggle) cardToggle.classList.add("rotated");
    }

    var html;
    try {
      html = Board.ToolResultRenderer.dispatch(resolvedToolName, text, { isError: !!isError });
    } catch (e) {
      html = '<pre class="term-plain">' + esc(text || '') + '</pre>';
    }

    var container = document.createElement("div");
    container.className = isError ? "wf-tool-error" : "wf-tool-result";
    container.innerHTML = html;
    cardBody.appendChild(container);

    // Record elapsed time on the card header
    var startTimeAttr = card.getAttribute("data-start-time");
    if (startTimeAttr) {
      var startTime = parseInt(startTimeAttr, 10);
      if (!isNaN(startTime)) {
        var elapsed = Date.now() - startTime;
        var timeEl = card.querySelector(".wf-tool-card-time");
        if (timeEl) {
          timeEl.textContent = formatDuration(elapsed);
        }
      }
    }
  }

  /** @type {HTMLElement|null} Current workflow tool card in step panel */
  var currentWorkflowToolCard = null;

  // ── Thinking Spinner ──

  var thinkingEl = null;

  function startSpinner() {
    if (thinkingEl) return;
    if (!outputDiv) return;

    thinkingEl = document.createElement("div");
    thinkingEl.className = "term-thinking";
    thinkingEl.id = "term-thinking-active";
    thinkingEl.innerHTML = '<span class="term-thinking-dot"></span> Thinking...';
    // outputDiv 바로 뒤(input-card 바로 앞)에 삽입하여 하단 고정
    outputDiv.parentNode.insertBefore(thinkingEl, outputDiv.nextSibling);
  }

  function stopSpinner() {
    if (thinkingEl && thinkingEl.parentNode) {
      thinkingEl.parentNode.removeChild(thinkingEl);
    }
    thinkingEl = null;
  }

  // ── Input Management ──

  // ── Image Attachment ──

  var ALLOWED_MIME = ["image/png", "image/jpeg", "image/gif", "image/webp"];
  var MAX_IMAGE_SIZE = 20 * 1024 * 1024; // 20MB

  function renderImagePreview() {
    var container = document.getElementById("terminal-image-preview");
    if (!container) return;
    container.innerHTML = "";
    attachedImages.forEach(function (img, idx) {
      var thumb = document.createElement("div");
      thumb.className = "terminal-image-thumb";

      var imgEl = document.createElement("img");
      imgEl.src = "data:" + img.media_type + ";base64," + img.data;
      imgEl.alt = img.name || "image";

      var removeBtn = document.createElement("button");
      removeBtn.className = "terminal-image-remove";
      removeBtn.title = "제거";
      removeBtn.innerHTML = "\u00D7";
      removeBtn.addEventListener("click", function () { removeImage(idx); });

      thumb.appendChild(imgEl);
      thumb.appendChild(removeBtn);
      container.appendChild(thumb);
    });
  }

  function attachImage(file) {
    if (!file) return;
    if (ALLOWED_MIME.indexOf(file.type) === -1) {
      appendErrorMessage("[첨부 오류] 지원하지 않는 형식입니다 (PNG/JPG/GIF/WebP 만 가능)");
      return;
    }
    if (file.size > MAX_IMAGE_SIZE) {
      appendErrorMessage("[첨부 오류] 파일 크기가 20MB를 초과합니다");
      return;
    }
    var reader = new FileReader();
    reader.onload = function (e) {
      var dataUrl = e.target.result;
      // data:image/png;base64,XXXX 에서 base64 부분만 추출
      var base64 = dataUrl.split(",")[1];
      attachedImages.push({ data: base64, media_type: file.type, name: file.name });
      renderImagePreview();
    };
    reader.readAsDataURL(file);
  }

  function removeImage(index) {
    attachedImages.splice(index, 1);
    renderImagePreview();
  }

  function clearImages() {
    attachedImages = [];
    renderImagePreview();
    var fileInput = document.getElementById("terminal-attach-input");
    if (fileInput) fileInput.value = "";
  }

  /**
   * 바이트 수를 사람이 읽기 쉬운 단위(B, KB, MB)로 변환하여 반환한다.
   */
  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  /**
   * 비이미지 파일 프리뷰 카드를 terminal-image-preview 컨테이너에 렌더링한다.
   * 기존 이미지 썸네일(renderImagePreview)과 동일 컨테이너를 공유하여
   * 하나의 프리뷰 스트립으로 관리한다.
   */
  function renderFilePreview() {
    var container = document.getElementById("terminal-image-preview");
    if (!container) return;

    // 기존 파일 카드만 제거하고 이미지 썸네일은 renderImagePreview()가 관리
    var existingCards = container.querySelectorAll(".terminal-file-card");
    existingCards.forEach(function (card) { card.parentNode.removeChild(card); });

    attachedFiles.forEach(function (info, idx) {
      var card = document.createElement("div");
      card.className = "terminal-file-card";
      card.setAttribute("data-file-idx", idx);

      // 확장자 라벨
      var ext = info.name.split(".").pop().toUpperCase().slice(0, 6) || "FILE";
      var extLabel = document.createElement("div");
      extLabel.className = "terminal-file-card-ext";
      extLabel.textContent = ext;

      // 파일명 (ellipsis)
      var nameLabel = document.createElement("div");
      nameLabel.className = "terminal-file-card-name";
      nameLabel.textContent = info.name;
      nameLabel.title = info.name;

      // 파일 크기
      var sizeLabel = document.createElement("div");
      sizeLabel.className = "terminal-file-card-size";
      sizeLabel.textContent = formatFileSize(info.size);

      // 제거 버튼
      var removeBtn = document.createElement("button");
      removeBtn.className = "terminal-image-remove";
      removeBtn.title = "제거";
      removeBtn.innerHTML = "\u00D7";
      removeBtn.addEventListener("click", (function (capturedIdx) {
        return function () { removeFile(capturedIdx); };
      })(idx));

      card.appendChild(extLabel);
      card.appendChild(nameLabel);
      card.appendChild(sizeLabel);
      card.appendChild(removeBtn);
      container.appendChild(card);
    });
  }

  function removeFile(index) {
    var removed = attachedFiles.splice(index, 1);
    // textarea에서 파일명 제거
    var targetInput = document.getElementById("terminal-input");
    if (targetInput && removed.length > 0) {
      var name = removed[0].name;
      var re = new RegExp("(?:^|\\n)" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?=\\n|$)", "g");
      targetInput.value = targetInput.value.replace(re, "").replace(/^\n/, "").replace(/\n\n+/g, "\n");
      var evt = document.createEvent("Event");
      evt.initEvent("input", true, true);
      targetInput.dispatchEvent(evt);
    }
    renderFilePreview();
  }

  function clearFiles() {
    attachedFiles = [];
    renderFilePreview();
  }

  /**
   * 문자열이 파일 경로 패턴인지 판별한다.
   * - Unix 절대 경로: /로 시작, // 제외 (프로토콜 상대 URL)
   * - Windows 절대 경로: C:\ 등 드라이브 문자
   * - 여러 줄 경로: 각 줄이 경로 패턴인 경우
   * - URL(http://, https://) 제외
   */
  function isFilePath(text) {
    if (!text) return false;
    // URL 제외
    if (/^https?:\/\//i.test(text.trim())) return false;
    // 여러 줄인 경우 각 줄을 검사하여 모두 경로 패턴이면 true
    var lines = text.trim().split(/\r?\n/);
    var pathLine = /^\/[^\/\s]+\/|^[A-Za-z]:\\/;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (line && !pathLine.test(line)) return false;
    }
    return pathLine.test(lines[0].trim());
  }

  /**
   * textarea의 현재 커서 위치(selectionStart/End)에 텍스트를 삽입한다.
   */
  function insertTextAtCursor(textarea, text) {
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    var before = textarea.value.substring(0, start);
    var after = textarea.value.substring(end);
    textarea.value = before + text + after;
    var pos = start + text.length;
    textarea.selectionStart = pos;
    textarea.selectionEnd = pos;
    textarea.focus();
    // input 이벤트를 발생시켜 자동 높이 조정 트리거
    var evt = document.createEvent("Event");
    evt.initEvent("input", true, true);
    textarea.dispatchEvent(evt);
  }

  /**
   * .terminal-input-card 내부에 파일명 뱃지를 잠시 표시한다.
   */
  function showFileBadge(card, names) {
    // 기존 뱃지 제거
    var prev = card.querySelector(".terminal-file-badge");
    if (prev) prev.parentNode.removeChild(prev);

    var badge = document.createElement("div");
    badge.className = "terminal-file-badge";
    badge.textContent = names.join(", ");
    card.appendChild(badge);

    setTimeout(function () {
      if (badge.parentNode) badge.parentNode.removeChild(badge);
    }, 3000);
  }

  function setInputLocked(locked) {
    inputLocked = locked;
    var input = document.getElementById("terminal-input");
    var sendBtn = document.getElementById("terminal-send-btn");
    if (input) {
      // running 상태에서도 입력창은 활성 유지 (큐 입력 허용). stopped 상태에서만 disabled.
      var shouldDisable = Board.state.termStatus === "stopped";
      input.disabled = shouldDisable;
      if (!shouldDisable) {
        input.focus();
      }
    }
    if (sendBtn) {
      sendBtn.disabled = Board.state.termStatus === "stopped";
    }
    var attachBtn = document.getElementById("terminal-attach-btn");
    if (attachBtn) {
      attachBtn.disabled = Board.state.termStatus === "stopped";
    }
  }

  function sendInput() {
    if (isWorkflowMode) return;
    var input = document.getElementById("terminal-input");
    if (!input) return;
    var text = input.value.trim();
    var hasImages = attachedImages.length > 0;
    if (!text && !hasImages) return;
    if (Board.state.termStatus === "stopped") return;

    input.value = "";
    input.style.height = "auto";

    // Route slash commands (큐에 넣지 않고 즉시 처리) — 이미지 있으면 슬래시 커맨드 미적용
    // isFilePath() 체크: /home/... 등 파일 경로는 슬래시 커맨드로 라우팅하지 않음
    if (!hasImages && text.charAt(0) === "/" && !isFilePath(text)) {
      Board.slashCommands.handle(text, {
        isWorkflowMode: isWorkflowMode,
        appendSystemMessage: appendSystemMessage,
        appendHtmlBlock: appendHtmlBlock,
        appendErrorMessage: appendErrorMessage,
        clearOutput: clearOutput,
        postJson: Board.session.postJson
      });
      return;
    }

    // running 상태(응답 대기 중)이면 큐에 push하고 즉시 리턴 (이미지는 큐 미지원)
    if (Board.state.termStatus === "running" && !hasImages) {
      inputQueue.push(text);
      var queuedDiv = document.createElement("div");
      queuedDiv.className = "term-message term-user term-user-queued";
      queuedDiv.textContent = text;
      appendToOutput(queuedDiv);
      updateControlBar();
      return;
    }

    var div = document.createElement("div");
    div.className = "term-message term-user";
    if (text) div.textContent = text;
    if (hasImages) {
      var thumbRow = document.createElement("div");
      thumbRow.style.cssText = "display:flex;gap:4px;flex-wrap:wrap;margin-top:4px;";
      attachedImages.forEach(function (img) {
        var t = document.createElement("img");
        t.src = "data:" + img.media_type + ";base64," + img.data;
        t.style.cssText = "width:48px;height:48px;object-fit:cover;border-radius:6px;border:1px solid #3a3a3a;";
        thumbRow.appendChild(t);
      });
      div.appendChild(thumbRow);
    }
    appendToOutput(div);

    // 전송 payload 구성
    var payload = { text: text };
    if (hasImages) {
      payload.images = attachedImages.map(function (img) {
        return { data: img.data, media_type: img.media_type };
      });
    }
    clearImages();
    clearFiles();

    // Mark text as locally sent so the user_input SSE echo is skipped
    if (text && Board.session && Board.session._markSent) {
      Board.session._markSent(text);
    }

    setInputLocked(true);
    startSpinner();
    Board.state.termStatus = "running";
    updateControlBar();

    var ep = endpoints();
    Board.session.postJson(ep.input, ep.inputBody(payload)).catch(function (err) {
      stopSpinner();
      appendErrorMessage("[Error] " + err.message);
      setInputLocked(false);
      Board.state.termStatus = "idle";
      updateControlBar();
    });
  }

  function drainQueue() {
    if (isWorkflowMode) return;
    if (inputQueue.length === 0) return;
    if (Board.state.termStatus !== "idle") return;

    var nextText = inputQueue.shift();
    updateControlBar();

    // Mark as locally sent to suppress the user_input SSE echo
    if (nextText && Board.session && Board.session._markSent) {
      Board.session._markSent(nextText);
    }

    startSpinner();
    Board.state.termStatus = "running";
    updateControlBar();

    var ep = endpoints();
    Board.session.postJson(ep.input, ep.inputBody({ text: nextText })).catch(function (err) {
      stopSpinner();
      appendErrorMessage("[Error] " + err.message);
      setInputLocked(false);
      Board.state.termStatus = "idle";
      updateControlBar();
    });
  }

  function interruptSession() {
    if (isWorkflowMode) return;
    if (Board.state.termStatus !== "running") return;

    Board.session.postJson("/terminal/interrupt").then(function () {
      stopSpinner();
      appendSystemMessage("[Interrupted]");
      if (textBuffer) {
        if (Board.WfTicketRenderer && Board.WfTicketRenderer.detect(textBuffer)) {
          Board.WfTicketRenderer.render(textBuffer);
        } else {
          var html = renderMarkdownToHtml(textBuffer);
          appendHtmlBlock(html, "term-message term-assistant");
        }
      }
      textBuffer = "";
      currentToolBox = null;
      toolBoxMap = {};
      toolInputBuffer = "";
      currentToolName = null;
      // 상태 변경 및 입력 잠금 해제는 result SSE 이벤트 핸들러에 위임한다.
      // SIGINT 후 Claude CLI는 반드시 result 이벤트를 발행하므로 여기서 직접 변경하지 않는다.
      // (직접 변경 시 서버가 아직 running 상태일 때 클라이언트가 idle로 전환되어 409 발생)
    }).catch(function (err) {
      appendErrorMessage("[Error] Failed to interrupt: " + err.message);
    });
  }

  // ── Output Clear ──

  function clearOutput() {
    if (outputDiv) {
      outputDiv.innerHTML = "";
    }
  }

  // ── UI Update ──

  function updateControlBar() {
    var startBtn = document.getElementById("terminal-start-btn");
    var killBtn = document.getElementById("terminal-kill-btn");
    var resumeBtn = document.getElementById("terminal-resume-btn");
    var statusDot = document.getElementById("terminal-status-dot");
    var statusText = document.getElementById("terminal-status-text");
    var isMainActive = _activeSessionId === "main";
    if (startBtn) {
      // Start 버튼은 main 탭(메인 세션) 활성 시에만 표시한다.
      if (!isMainActive) {
        startBtn.style.display = "none";
      } else {
        startBtn.style.display = "";
        startBtn.disabled = Board.state.termStatus !== "stopped";
      }
    }
    if (resumeBtn) {
      // Resume 버튼은 main 탭 활성 + stopped 상태 + termLastSessionId 존재 시에만 표시한다.
      var showResume = isMainActive
        && Board.state.termStatus === "stopped"
        && !!Board.state.termLastSessionId;
      resumeBtn.style.display = showResume ? "" : "none";
    }
    var browseBtn = document.getElementById("terminal-browse-btn");
    if (browseBtn) {
      // Browse 토글 버튼은 main 탭 활성 + stopped 상태일 때만 표시한다.
      var showBrowse = isMainActive && Board.state.termStatus === "stopped";
      browseBtn.style.display = showBrowse ? "" : "none";
    }
    if (killBtn) {
      killBtn.disabled = Board.state.termStatus === "stopped";
    }
    var loginBtn = document.getElementById("terminal-login");
    if (loginBtn) {
      loginBtn.disabled = Board.state.termStatus === "stopped";
    }
    if (statusDot) {
      statusDot.className = "terminal-status-dot terminal-status-" + Board.state.termStatus;
    }
    var statusContainer = document.querySelector(".terminal-status");
    if (statusContainer) {
      statusContainer.setAttribute("data-state", Board.state.termStatus);
    }
    if (statusText) {
      statusText.textContent = Board.state.termStatus;
    }
    var sessionIdEl = document.getElementById("terminal-session-id");
    if (sessionIdEl) {
      sessionIdEl.textContent = Board.state.termSessionId || '';
    }

    var inputCard = document.querySelector(".terminal-input-card");
    if (inputCard) {
      if (isWorkflowMode) {
        inputCard.classList.add("wf-input-hidden");
      } else {
        inputCard.classList.remove("wf-input-hidden");
      }
    }

    var sendBtn = document.getElementById("terminal-send-btn");
    if (sendBtn) {
      if (isWorkflowMode) {
        sendBtn.style.display = "none";
      } else {
        sendBtn.style.display = "";
        var isRunning = Board.state.termStatus === "running";
        if (isRunning) {
          sendBtn.classList.add("is-stop");
          sendBtn.disabled = false;
          sendBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>';
          sendBtn.onclick = function (e) { e.stopPropagation(); interruptSession(); };
        } else {
          sendBtn.classList.remove("is-stop");
          sendBtn.disabled = Board.state.termStatus === "stopped";
          sendBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>';
          sendBtn.onclick = function (e) { e.stopPropagation(); sendInput(); };
        }
      }
    }

    var hintEl = document.querySelector(".terminal-input-hint");
    if (hintEl) {
      if (isWorkflowMode) {
        hintEl.textContent = "자동 실행 전용";
      } else if (Board.state.termStatus === "running") {
        var queueLen = inputQueue.length;
        if (queueLen > 0) {
          hintEl.textContent = "ESC 중지 \u00B7 대기 " + queueLen + "개";
        } else {
          hintEl.textContent = "ESC 중지";
        }
      } else {
        hintEl.textContent = "Enter 전송 \u00B7 Shift+Enter 줄바꿈";
      }
    }

    updateStatusLine();
    setInputLocked(inputLocked);
  }

  function updateStatusLine() {
    var slModel = document.getElementById("terminal-sl-model");
    var slTokens = document.getElementById("terminal-sl-tokens");
    var slCost = document.getElementById("terminal-sl-cost");

    if (slModel) slModel.textContent = sessionModel;

    var slBranch = document.getElementById("terminal-sl-branch");
    if (slBranch) {
      var branchText = slBranch.textContent.replace(/^\ue0a0\s*/, "").trim();
      if (!branchText || branchText === "--") branchText = slBranch.textContent.trim();
      var existingSvg = slBranch.querySelector("svg");
      if (existingSvg) {
        branchText = slBranch.textContent.trim();
        existingSvg.remove();
      }
      if (branchText && branchText !== "--") {
        slBranch.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:3px"><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M6 15V9a6 6 0 0 0 6-6h0a6 6 0 0 0 6 6"/></svg>' + branchText;
      }
    }

    var totalTokens = sessionTokens.input;
    var pct = contextWindow > 0 ? Math.min(totalTokens / contextWindow * 100, 100) : 0;
    var barFill = document.getElementById("terminal-sl-bar-fill");
    var barPct = document.getElementById("terminal-sl-bar-pct");
    if (barFill) {
      barFill.style.width = pct.toFixed(1) + "%";
      barFill.style.backgroundColor = pct < 60 ? "#3fb950" : pct < 85 ? "#d29922" : "#f85149";
    }
    if (barPct) barPct.textContent = pct.toFixed(1) + "%";

    if (slTokens) {
      var fmtTotal = totalTokens >= 1000 ? Math.round(totalTokens / 1000) + "k" : totalTokens;
      var fmtCtx = contextWindow >= 1000000 ? (contextWindow / 1000000) + "M" : Math.round(contextWindow / 1000) + "k";
      slTokens.textContent = "(" + fmtTotal + "/" + fmtCtx + ")";
    }

    if (slCost) slCost.textContent = "$" + sessionCost.toFixed(4);
  }

  // ── Session Switcher Engine ──

  var MAX_SAVED_NODES = 5000;

  /**
   * 현재 활성 세션의 상태를 _sessionMap에 저장한다.
   */
  function _saveCurrentSession() {
    var entry = _sessionMap[_activeSessionId];
    if (!entry) return;

    // outputDiv 자식 노드 스냅샷 (최대 MAX_SAVED_NODES개)
    if (outputDiv) {
      entry.outputNodes = [];
      var children = outputDiv.childNodes;
      var startIdx = 0;
      var truncated = children.length > MAX_SAVED_NODES;
      if (truncated) {
        startIdx = children.length - MAX_SAVED_NODES;
        var omitEl = document.createElement("div");
        omitEl.className = "system-message";
        omitEl.textContent = "(이전 출력 생략)";
        entry.outputNodes.push(omitEl);
      }
      for (var i = startIdx; i < children.length; i++) {
        entry.outputNodes.push(children[i].cloneNode(true));
      }
    }

    // 상태 변수 저장
    entry.cost = sessionCost;
    entry.tokens = { input: sessionTokens.input, output: sessionTokens.output };
    entry.model = sessionModel;
    entry.status = Board.state.termStatus;
    entry.inputQueue = inputQueue.slice();
  }

  /**
   * 대상 세션의 상태를 활성 변수로 복원한다.
   * @param {string} targetId
   */
  function _restoreSession(targetId) {
    var entry = _sessionMap[targetId];
    if (!entry) return;

    // 세션 모드 변수 업데이트
    if (targetId === "main") {
      workflowSessionId = null;
      isWorkflowMode = false;
    } else {
      workflowSessionId = targetId;
      isWorkflowMode = true;
    }

    // 입력 카드 표시/숨김 즉각 반영 (updateControlBar 호출 전 동기 처리)
    var inputCardEl = document.querySelector(".terminal-input-card");
    if (inputCardEl) {
      if (isWorkflowMode) {
        inputCardEl.classList.add("wf-input-hidden");
      } else {
        inputCardEl.classList.remove("wf-input-hidden");
      }
    }

    // 상태 변수 복원
    sessionCost = entry.cost;
    sessionTokens = { input: entry.tokens.input, output: entry.tokens.output };
    sessionModel = entry.model;
    Board.state.termStatus = entry.status;
    Board.state.termSessionId = targetId === "main" ? null : targetId;

    // inputQueue 교체 (참조를 유지하면서 내용만 교체)
    inputQueue.length = 0;
    for (var qi = 0; qi < entry.inputQueue.length; qi++) {
      inputQueue.push(entry.inputQueue[qi]);
    }

    // Reset shared module-scoped state; otherwise new session events
    // route to prior session's DOM references (wf panel + tool buffers).
    if (Board.WorkflowRenderer && Board.WorkflowRenderer.reset) {
      Board.WorkflowRenderer.reset();
    }
    stopSpinner();
    currentToolBox = null;
    toolBoxMap = {};
    currentToolName = null;
    textBuffer = "";
    toolInputBuffer = "";
    receivedChunks = false;
    currentWorkflowToolCard = null;

    // outputDiv 복원
    if (outputDiv) {
      outputDiv.innerHTML = "";
      if (entry.outputNodes && entry.outputNodes.length > 0) {
        for (var ni = 0; ni < entry.outputNodes.length; ni++) {
          outputDiv.appendChild(entry.outputNodes[ni].cloneNode(true));
        }
        // 스크롤을 맨 아래로
        outputDiv.scrollTop = outputDiv.scrollHeight;
      } else {
        // 빈 세션: 초기 메시지 출력
        if (targetId === "main") {
          appendSystemMessage("Claude Code Terminal");
          appendSystemMessage('Press "Start" to begin a session.');
        } else {
          // 워크플로우 모드: "Workflow Session: ..." 메시지는 탭 바 활성 탭으로 대체
          appendSystemMessage("Connecting to live stream...");
        }
      }
    }
  }

  /**
   * 세션을 전환한다.
   * (a) 현재 세션 상태 저장 → (b) 대상 세션 복원 → (c) SSE 재연결 → (d) 상태바 갱신
   *
   * @param {string} targetSessionId - 전환할 세션 ID ("main" 또는 "wf-T-NNN-...")
   * @returns {Promise<void>}
   */
  function switchSession(targetSessionId) {
    if (!targetSessionId) return Promise.resolve();
    if (targetSessionId === _activeSessionId) return Promise.resolve();

    // 대상 세션이 맵에 없으면 생성
    if (!_sessionMap[targetSessionId]) {
      _sessionMap[targetSessionId] = _createSessionEntry(targetSessionId);
    }

    // 1. 현재 세션 저장
    _saveCurrentSession();

    // 2. 활성 세션 ID 변경
    var prevId = _activeSessionId;
    _activeSessionId = targetSessionId;

    // 3. 대상 세션 상태 복원 (outputDiv, 변수)
    _restoreSession(targetSessionId);

    // 4. SSE 재연결: disconnectSSE → connectSSEReady → fetchStatus
    // 세션별 last-event-id 트래커를 복원하여 탭 왕복 시 히스토리 중복 재생을 차단
    if (Board.session) {
      if (Board.session.adoptLastEventIdForSession) {
        Board.session.adoptLastEventIdForSession(targetSessionId);
      } else if (Board.session.resetLastEventId) {
        Board.session.resetLastEventId();
      }
      Board.session.disconnectSSE();
      Board.session.connectSSEReady()
        .then(function () { Board.session.fetchStatus(); })
        .catch(function () {});
    }

    // 5. phase timeline 표시/숨김
    var timelineBar = document.getElementById("wf-timeline-bar");
    if (timelineBar) {
      timelineBar.style.display = targetSessionId === "main" ? "none" : "";
    }

    // 6. UI 갱신
    updateControlBar();

    // 탭 바가 있으면 활성 탭 업데이트 (W01에서 구현하는 UI 훅)
    if (Board.sessionSwitcher && Board.sessionSwitcher._onSwitch) {
      Board.sessionSwitcher._onSwitch(targetSessionId, prevId);
    }

    return Promise.resolve();
  }

  // ── Main Render ──

  function getContainer() {
    var spaEl = document.getElementById("view-terminal");
    if (spaEl) return spaEl;
    var standaloneEl = document.getElementById("terminal-standalone");
    if (standaloneEl) return standaloneEl;
    return null;
  }

  function renderTerminal() {
    var el = getContainer();
    if (!el) return;

    if (termInitialized && document.getElementById("terminal-output")) {
      updateControlBar();
      return;
    }

    var h = "";

    h += '<div class="terminal-container">';

    h += '<div class="terminal-session-bar">';

    h += '<div class="terminal-session-bar-top">';
    h += '<div class="terminal-session-left">';
    h += '<div class="terminal-status" data-state="' + esc(Board.state.termStatus) + '">';
    h += '<span class="terminal-status-dot terminal-status-' + esc(Board.state.termStatus) + '" id="terminal-status-dot"></span>';
    h += '<span class="terminal-status-text" id="terminal-status-text">' + esc(Board.state.termStatus) + '</span>';
    h += '</div>';
    h += '<span class="terminal-session-id" id="terminal-session-id">'
      + esc(Board.state.termSessionId || '')
      + '</span>';
    h += '</div>';
    h += '<div class="terminal-session-controls">';
    h += '<div class="terminal-start-group" id="terminal-start-group">';
    h += '<button class="terminal-btn terminal-btn-start" id="terminal-start-btn">Start</button>';
    h += '<button class="terminal-btn terminal-btn-resume" id="terminal-resume-btn">Resume</button>';
    h += '<button class="terminal-btn terminal-btn-browse" id="terminal-browse-btn" title="Browse sessions" style="display:none">&#x25BE;</button>';
    h += '<div class="terminal-browse-dropdown" id="terminal-browse-dropdown">';
    h += '<button class="terminal-browse-item" id="terminal-browse-new">New Session</button>';
    h += '<button class="terminal-browse-item" id="terminal-browse-resume-last">Resume Last</button>';
    h += '<div class="terminal-browse-divider"></div>';
    h += '<button class="terminal-browse-item" id="terminal-browse-sessions">Browse Sessions...</button>';
    h += '<div class="terminal-browse-session-list" id="terminal-browse-session-list" style="display:none"></div>';
    h += '</div>';
    h += '</div>';
    h += '<button class="terminal-btn terminal-btn-kill" id="terminal-kill-btn">Kill</button>';
    h += '<span class="terminal-controls-divider"></span>';
    h += '<button class="terminal-btn terminal-btn-sessions" id="terminal-sessions-btn" title="Workflow sessions">';
    h += '<span id="terminal-sessions-label">Sessions</span>';
    h += '<span class="terminal-sessions-count" id="terminal-sessions-count" style="display:none"></span>';
    h += '</button>';
    h += '<div class="terminal-sessions-dropdown" id="terminal-sessions-dropdown"></div>';
    h += '<span class="terminal-controls-divider"></span>';
    h += '<button class="terminal-btn terminal-btn-settings" id="terminal-settings-btn" title="Settings">';
    h += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">';
    h += '<circle cx="12" cy="12" r="3"/>';
    h += '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>';
    h += '</svg></button>';
    h += '</div>';
    h += '<div class="terminal-settings-dropdown" id="terminal-settings-dropdown">';
    h += '<button class="terminal-settings-item" id="terminal-restart-server">Restart Server</button>';
    h += '<button class="terminal-settings-item" id="terminal-login">Login</button>';
    h += '<button class="terminal-settings-item" id="terminal-clear-output">Clear Output</button>';
    h += '</div>';
    h += '</div>';

    // Session Tab Bar
    h += '<div class="session-tab-bar" id="session-tab-bar">';
    h += '<div class="session-tab-list" id="session-tab-list">';
    h += '<div class="session-tab active" data-session="main">';
    h += '<span class="session-tab-label">Main</span>';
    h += '</div>';
    h += '</div>';
    h += '<button class="session-tab-add" id="session-tab-add" title="Add workflow session">';
    h += '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>';
    h += '</button>';
    h += '</div>';

    h += '</div>';

    h += '<div class="terminal-output" id="terminal-output"></div>';

    h += '<div class="terminal-input-card">';
    h += '<div class="terminal-image-preview" id="terminal-image-preview"></div>';
    h += '<textarea class="terminal-input" id="terminal-input"'
      + ' placeholder="메시지를 입력하세요..." rows="1"'
      + ' autocomplete="off" spellcheck="false"'
      + (Board.state.termStatus === "stopped" ? " disabled" : "")
      + '></textarea>';
    h += '<div class="terminal-input-bottom">';
    h += '<div class="terminal-input-bottom-left">';
    h += '<button class="terminal-attach-btn" id="terminal-attach-btn" title="이미지 첨부"'
      + (Board.state.termStatus === "stopped" ? " disabled" : "")
      + '><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg></button>';
    h += '<input type="file" id="terminal-attach-input" accept="image/png,image/jpeg,image/gif,image/webp" style="display:none" multiple>';
    h += '</div>';
    h += '<div class="terminal-input-bottom-right">';
    h += '<span class="terminal-input-hint">Enter 전송 \u00B7 Shift+Enter 줄바꿈</span>';
    h += '<button class="terminal-send-btn" id="terminal-send-btn"'
      + (Board.state.termStatus === "stopped" ? " disabled" : "")
      + '><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg></button>';
    h += '</div>';
    h += '</div>';
    h += '</div>';

    h += '<div class="terminal-statusline" id="terminal-statusline">';
    h += '<span class="terminal-sl-model" id="terminal-sl-model">--</span>';
    h += '<span class="terminal-sl-branch" id="terminal-sl-branch">--</span>';
    h += '<span class="terminal-sl-bar" id="terminal-sl-bar"><span class="terminal-sl-bar-track"><span class="terminal-sl-bar-fill" id="terminal-sl-bar-fill" style="width:0%"></span></span><span id="terminal-sl-bar-pct">0%</span></span>';
    h += '<span class="terminal-sl-tokens" id="terminal-sl-tokens">(0/0)</span>';
    h += '<span class="terminal-sl-right">';
    h += '<span class="terminal-sl-mode" id="terminal-sl-mode"></span>';
    h += '<span id="terminal-sl-cost">$0.00</span>';
    h += '<span id="terminal-sl-port">port:' + location.port + '</span>';
    h += '</span>';
    h += '</div>';

    h += '</div>';

    el.innerHTML = h;

    initOutputDiv();

    // Workflow mode: insert timeline bar placeholder
    if (isWorkflowMode) {
      Board.phaseTimeline.insertPlaceholder();
    }

    // Bind session module to core context
    if (Board.session && Board.session._bind) {
      Board.session._bind({
        endpoints: endpoints,
        isWorkflowMode: function () { return isWorkflowMode; },
        getWorkflowSessionId: function () { return workflowSessionId; },
        updateControlBar: updateControlBar,
        updateStatusLine: updateStatusLine,
        appendToOutput: appendToOutput,
        appendSystemMessage: appendSystemMessage,
        appendErrorMessage: appendErrorMessage,
        appendHtmlBlock: appendHtmlBlock,
        createToolBox: createToolBox,
        removeEmptyToolBox: removeEmptyToolBox,
        removeEmptyWorkflowToolCard: removeEmptyWorkflowToolCard,
        insertToolResult: insertToolResult,
        insertWorkflowResult: insertWorkflowResult,
        createWorkflowToolCard: createWorkflowToolCard,
        clearCurrentWorkflowToolCard: function () { currentWorkflowToolCard = null; },
        clearOutput: clearOutput,
        startSpinner: startSpinner,
        stopSpinner: stopSpinner,
        setInputLocked: setInputLocked,
        setReceivedChunks: function (v) { receivedChunks = v; },
        getReceivedChunks: function () { return receivedChunks; },
        appendTextBuffer: function (chunk) { textBuffer += chunk; },
        flushTextBuffer: function () {
          if (textBuffer) {
            if (isWorkflowMode) {
              var wfHtml = renderMarkdownToHtml(textBuffer);
              Board.WorkflowRenderer.insertToCurrentPanel(
                '<div class="wf-assistant-block">' + wfHtml + '</div>'
              );
            } else {
              if (Board.WfTicketRenderer && Board.WfTicketRenderer.detect(textBuffer)) {
                Board.WfTicketRenderer.render(textBuffer);
              } else {
                var html = renderMarkdownToHtml(textBuffer);
                appendHtmlBlock(html, "term-message term-assistant");
              }
            }
          }
          textBuffer = "";
        },
        appendToolInputBuffer: function (chunk) { toolInputBuffer += chunk; },
        resetToolInputBuffer: function () { toolInputBuffer = ""; },
        setCurrentToolName: function (name) { currentToolName = name; },
        clearCurrentToolBox: function () { currentToolBox = null; },
        getToolBoxMap: function () { return toolBoxMap; },
        resetToolBoxMap: function () { toolBoxMap = {}; },
        resetTokens: function () { sessionTokens = { input: 0, output: 0 }; sessionCost = 0; },
        setSessionCost: function (v) { sessionCost = v; },
        addInputTokens: function (n) { sessionTokens.input += n; },
        addOutputTokens: function (n) { sessionTokens.output += n; },
        setInputTokens: function (n) { sessionTokens.input = n; },
        setOutputTokens: function (n) { sessionTokens.output = n; },
        getSessionTokens: function () { return sessionTokens; },
        setSessionModel: function (v) { sessionModel = v; },
        setContextWindow: function (v) { contextWindow = v; },
        drainQueue: drainQueue,
        getInputQueue: function () { return inputQueue; }
      });
    }

    // Bind WfTicketRenderer context
    if (Board.WfTicketRenderer) {
      Board.WfTicketRenderer.setContext({
        appendToOutput: appendToOutput || appendHtmlBlock,
        endpoints: endpoints,
        renderMarkdownToHtml: renderMarkdownToHtml,
        setInputLocked: setInputLocked,
        startSpinner: startSpinner,
        stopSpinner: stopSpinner,
        updateControlBar: updateControlBar,
        appendErrorMessage: appendErrorMessage
      });
    }

    // Connect SSE
    if (Board.session) {
      Board.session.connectSSE();
      Board.session.fetchStatus();
    }

    // Bind event handlers
    var startBtn = document.getElementById("terminal-start-btn");
    var killBtn = document.getElementById("terminal-kill-btn");
    var inputEl = document.getElementById("terminal-input");

    if (startBtn) {
      startBtn.addEventListener("click", function () { Board.session.startSession(); });
    }
    var resumeBtn = document.getElementById("terminal-resume-btn");
    if (resumeBtn) {
      resumeBtn.addEventListener("click", function () {
        Board.session.startSession(Board.state.termLastSessionId);
      });
    }
    if (killBtn) {
      killBtn.addEventListener("click", function () { Board.session.killSession(); });
    }

    // Browse sessions dropdown
    var browseBtn = document.getElementById("terminal-browse-btn");
    var browseDropdown = document.getElementById("terminal-browse-dropdown");
    var browseNewBtn = document.getElementById("terminal-browse-new");
    var browseResumeLastBtn = document.getElementById("terminal-browse-resume-last");
    var browseSessionsBtn = document.getElementById("terminal-browse-sessions");
    var browseSessionList = document.getElementById("terminal-browse-session-list");

    if (browseBtn && browseDropdown) {
      browseBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        browseDropdown.classList.toggle("visible");
        if (browseSessionList) {
          browseSessionList.style.display = "none";
        }
      });
      document.addEventListener("click", function () {
        browseDropdown.classList.remove("visible");
        if (browseSessionList) {
          browseSessionList.style.display = "none";
        }
      });
    }

    if (browseNewBtn) {
      browseNewBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        browseDropdown.classList.remove("visible");
        Board.session.startSession();
      });
    }

    if (browseResumeLastBtn) {
      browseResumeLastBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        browseDropdown.classList.remove("visible");
        if (Board.state.termLastSessionId) {
          Board.session.startSession(Board.state.termLastSessionId);
        }
      });
    }

    if (browseSessionsBtn && browseSessionList) {
      browseSessionsBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        var isVisible = browseSessionList.style.display !== "none";
        if (isVisible) {
          browseSessionList.style.display = "none";
          return;
        }
        browseSessionList.innerHTML = '<div class="terminal-browse-loading">세션 목록을 불러오는 중...</div>';
        browseSessionList.style.display = "block";
        fetch("/terminal/sessions", { cache: "no-store" }).then(function (res) {
          if (!res.ok) throw new Error("HTTP " + res.status);
          return res.json();
        }).then(function (sessions) {
          browseSessionList.innerHTML = "";
          if (!sessions || sessions.length === 0) {
            browseSessionList.innerHTML = '<div class="terminal-browse-empty">최근 세션 없음</div>';
            return;
          }
          sessions.forEach(function (s) {
            var fullId = s.session_id || "";
            var shortId = fullId.substring(0, 8);

            var item = document.createElement("button");
            item.className = "terminal-browse-item terminal-browse-session-item";
            if (s.is_current) item.className += " current";
            item.setAttribute("title", fullId + (s.is_current ? " (현재 세션)" : ""));
            item.setAttribute("data-session-id", fullId);

            var idSpan = document.createElement("span");
            idSpan.className = "terminal-browse-session-id";
            idSpan.textContent = shortId;

            var timeSpan = document.createElement("span");
            timeSpan.className = "terminal-browse-session-time";
            timeSpan.textContent = formatRelativeTime(s.last_active);
            try {
              var dtAbs = new Date(s.last_active);
              if (!isNaN(dtAbs.getTime())) {
                timeSpan.setAttribute("title", dtAbs.toLocaleString("ko-KR"));
              }
            } catch (_eAbs) { /* no-op */ }

            item.appendChild(idSpan);
            if (s.is_current) {
              var currentLabel = document.createElement("span");
              currentLabel.className = "terminal-browse-current-label";
              currentLabel.textContent = "현재";
              item.appendChild(currentLabel);
            }
            item.appendChild(timeSpan);

            item.addEventListener("click", function (ev) {
              ev.stopPropagation();
              browseDropdown.classList.remove("visible");
              browseSessionList.style.display = "none";
              Board.session.startSession(fullId);
            });
            browseSessionList.appendChild(item);
          });
        }).catch(function (err) {
          var msg = err && err.message ? err.message : "알 수 없는 오류";
          browseSessionList.innerHTML = '<div class="terminal-browse-error">세션 목록 로드 실패 (' + escapeHtml(msg) + ')</div>';
        });
      });
    }

    // Settings dropdown
    var settingsBtn = document.getElementById("terminal-settings-btn");
    var settingsDropdown = document.getElementById("terminal-settings-dropdown");
    if (settingsBtn && settingsDropdown) {
      settingsBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        settingsDropdown.classList.toggle("visible");
      });
      document.addEventListener("click", function () {
        settingsDropdown.classList.remove("visible");
      });
    }
    var restartBtn = document.getElementById("terminal-restart-server");
    if (restartBtn) {
      restartBtn.addEventListener("click", function () {
        settingsDropdown.classList.remove("visible");
        Board.session.postJson("/api/restart").then(function () {
          setTimeout(function () { location.reload(); }, 1500);
        }).catch(function () {
          setTimeout(function () { location.reload(); }, 2000);
        });
      });
    }
    var loginBtn = document.getElementById("terminal-login");
    if (loginBtn) {
      loginBtn.addEventListener("click", function () {
        settingsDropdown.classList.remove("visible");
        if (Board.state.termStatus === "stopped") return;
        Board.session.postJson("/terminal/command", { command: "/login" }).catch(function (err) {
          appendErrorMessage("[Error] Login failed: " + err.message);
        });
      });
    }
    var clearBtn = document.getElementById("terminal-clear-output");
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        settingsDropdown.classList.remove("visible");
        clearOutput();
      });
    }
    if (inputEl) {
      inputEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
          e.preventDefault();
          if (!isWorkflowMode) sendInput();
          return;
        }
        if (e.key !== "Escape") e.stopPropagation();
      });
      inputEl.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 120) + "px";
      });
      // 클립보드 이미지 붙여넣기 (Ctrl+V) + 경로 텍스트 붙여넣기
      inputEl.addEventListener("paste", function (e) {
        var items = e.clipboardData && e.clipboardData.items;
        if (!items) return;
        var hasImage = false;
        for (var i = 0; i < items.length; i++) {
          if (items[i].type.indexOf("image/") === 0) {
            hasImage = true;
            var file = items[i].getAsFile();
            if (file) attachImage(file);
          }
        }
        if (hasImage) {
          e.preventDefault();
          return;
        }
        // image/* 가 없으면 text/plain 경로 패턴 확인
        var text = e.clipboardData.getData("text/plain");
        if (text && isFilePath(text)) {
          e.preventDefault();
          insertTextAtCursor(inputEl, text);
        }
        // 경로가 아닌 일반 텍스트는 기본 paste 동작에 위임
      });
    }

    // drag/drop 이벤트 핸들러 — .terminal-input-card 요소에 등록
    var inputCard = el.querySelector(".terminal-input-card");
    if (inputCard) {
      var dragEnterCount = 0;

      inputCard.addEventListener("dragenter", function (e) {
        e.preventDefault();
        dragEnterCount++;
        inputCard.classList.add("drag-over");
        if (!inputCard.querySelector(".terminal-drag-overlay")) {
          var overlay = document.createElement("div");
          overlay.className = "terminal-drag-overlay";
          var label = document.createElement("span");
          label.textContent = "파일을 여기에 놓으세요";
          overlay.appendChild(label);
          inputCard.appendChild(overlay);
        }
      });

      inputCard.addEventListener("dragover", function (e) {
        e.preventDefault();
        inputCard.classList.add("drag-over");
      });

      inputCard.addEventListener("dragleave", function (e) {
        dragEnterCount--;
        if (dragEnterCount <= 0) {
          dragEnterCount = 0;
          inputCard.classList.remove("drag-over");
          var overlay = inputCard.querySelector(".terminal-drag-overlay");
          if (overlay) overlay.parentNode.removeChild(overlay);
        }
      });

      inputCard.addEventListener("drop", function (e) {
        e.preventDefault();
        dragEnterCount = 0;
        inputCard.classList.remove("drag-over");
        var overlay = inputCard.querySelector(".terminal-drag-overlay");
        if (overlay) overlay.parentNode.removeChild(overlay);

        var dt = e.dataTransfer;
        var targetInput = document.getElementById("terminal-input");
        if (!targetInput) return;

        // (a) 파일 드롭 — 이미지: attachedImages에 추가 + 썸네일 / 비이미지: 파일 카드 + 파일명 삽입
        if (dt.files && dt.files.length > 0) {
          var names = [];
          for (var fi = 0; fi < dt.files.length; fi++) {
            var droppedFile = dt.files[fi];
            names.push(droppedFile.name);
            if (ALLOWED_MIME.indexOf(droppedFile.type) !== -1) {
              // 이미지 파일: 기존 attachImage() 경로 재사용 (썸네일 렌더링)
              attachImage(droppedFile);
            } else {
              // 비이미지 파일: attachedFiles에 등록 후 파일 카드 렌더링
              attachedFiles.push({ file: droppedFile, name: droppedFile.name, size: droppedFile.size, type: droppedFile.type });
              renderFilePreview();
              insertTextAtCursor(targetInput, droppedFile.name + (fi < dt.files.length - 1 ? "\n" : ""));
            }
          }
          return;
        }

        // (b) text/plain 이 경로 패턴이면 textarea에 경로 삽입
        var dropText = dt.getData("text/plain");
        if (dropText && isFilePath(dropText)) {
          insertTextAtCursor(targetInput, dropText);
          return;
        }
        // (c) 둘 다 아니면 무시 (시나리오 C, Chromium CF_HDROP 버그)
      });
    }

    // 첨부 버튼 및 hidden file input 이벤트
    var attachBtn = document.getElementById("terminal-attach-btn");
    var attachInput = document.getElementById("terminal-attach-input");
    if (attachBtn && attachInput) {
      attachBtn.addEventListener("click", function () {
        attachInput.click();
      });
      attachInput.addEventListener("change", function () {
        var files = this.files;
        if (!files) return;
        for (var i = 0; i < files.length; i++) {
          attachImage(files[i]);
        }
        this.value = "";
      });
    }

    // Keyboard shortcuts
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !isWorkflowMode && Board.state.termStatus === "running") {
        e.preventDefault();
        interruptSession();
        return;
      }
    });

    termInitialized = true;

    // Workflow sessions dropdown
    var sessionsBtn = document.getElementById("terminal-sessions-btn");
    var sessionsDropdown = document.getElementById("terminal-sessions-dropdown");
    if (sessionsBtn && sessionsDropdown) {
      sessionsBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        sessionsDropdown.classList.toggle("visible");
      });
      document.addEventListener("click", function () {
        sessionsDropdown.classList.remove("visible");
      });
    }
    // Session Tab Bar events
    var sessionTabList = document.getElementById("session-tab-list");
    var sessionTabAdd = document.getElementById("session-tab-add");

    if (sessionTabList) {
      sessionTabList.addEventListener("click", function (e) {
        // Close button
        var closeBtn = e.target.closest(".session-tab-close");
        if (closeBtn) {
          e.stopPropagation();
          var closeTab = closeBtn.closest(".session-tab");
          if (closeTab && closeTab.dataset.session !== "main") {
            var wasActive = closeTab.classList.contains("active");
            closeTab.parentNode.removeChild(closeTab);
            if (wasActive) {
              var mainTab = sessionTabList.querySelector('[data-session="main"]');
              if (mainTab) mainTab.classList.add("active");
              if (Board.sessionSwitcher && Board.sessionSwitcher.switchSession) {
                Board.sessionSwitcher.switchSession("main");
              }
            }
          }
          return;
        }
        // Tab click
        var clickedTab = e.target.closest(".session-tab");
        if (clickedTab) {
          var sessionId = clickedTab.dataset.session;
          sessionTabList.querySelectorAll(".session-tab").forEach(function (t) {
            t.classList.remove("active");
          });
          clickedTab.classList.add("active");
          if (Board.sessionSwitcher && Board.sessionSwitcher.switchSession) {
            Board.sessionSwitcher.switchSession(sessionId);
          }
        }
      });
    }

    if (sessionTabAdd) {
      sessionTabAdd.addEventListener("click", function (e) {
        e.stopPropagation();
        // Reuse sessions dropdown as popover triggered by '+' button
        if (sessionsDropdown) {
          sessionsDropdown.classList.toggle("visible");
        }
      });
    }

    // Expose tab management UI API on Board.sessionSwitcher namespace
    Board.sessionSwitcher = Board.sessionSwitcher || {};
    Board.sessionSwitcher.addTab = function (sessionId, label, status) {
      if (!sessionTabList) return;
      if (sessionTabList.querySelector('[data-session="' + sessionId + '"]')) return;
      var tab = document.createElement("div");
      tab.className = "session-tab";
      tab.dataset.session = sessionId;
      var dotClass = status === "running" ? "session-tab-dot running" : "session-tab-dot stopped";
      tab.innerHTML =
        '<span class="' + dotClass + '"></span>' +
        '<span class="session-tab-label">' + esc(label || sessionId) + '</span>' +
        '<button class="session-tab-close" title="Remove tab">' +
        '<svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>' +
        '</button>';
      sessionTabList.appendChild(tab);
    };
    Board.sessionSwitcher.removeTab = function (sessionId) {
      if (!sessionTabList) return;
      var tab = sessionTabList.querySelector('[data-session="' + sessionId + '"]');
      if (tab) tab.parentNode.removeChild(tab);
    };
    Board.sessionSwitcher.setTabStatus = function (sessionId, status) {
      if (!sessionTabList) return;
      var tab = sessionTabList.querySelector('[data-session="' + sessionId + '"]');
      if (!tab) return;
      var dot = tab.querySelector(".session-tab-dot");
      if (dot) {
        dot.className = status === "running" ? "session-tab-dot running" : "session-tab-dot stopped";
      }
    };
    Board.sessionSwitcher.setActiveTab = function (sessionId) {
      if (!sessionTabList) return;
      sessionTabList.querySelectorAll(".session-tab").forEach(function (t) {
        t.classList.toggle("active", t.dataset.session === sessionId);
      });
    };

    // _onSwitch 훅: switchSession() 호출 시 탭 바 활성 상태 업데이트
    Board.sessionSwitcher._onSwitch = function (newSessionId, _prevId) {
      if (Board.sessionSwitcher.setActiveTab) {
        Board.sessionSwitcher.setActiveTab(newSessionId);
      }
    };

    // URL ?session= 쿼리 파라미터 기반 초기 세션 탭 처리
    if (_initialQuerySession) {
      // 탭 바에 초기 세션 추가 (워크플로우 탭)
      if (Board.sessionSwitcher.addTab) {
        var initLabel = _initialQuerySession.replace(/^wf-/, "").replace(/-\d+$/, "");
        Board.sessionSwitcher.addTab(_initialQuerySession, initLabel, "running");
      }
      // 탭 활성화 (초기 세션이 활성 탭으로 표시)
      if (Board.sessionSwitcher.setActiveTab) {
        Board.sessionSwitcher.setActiveTab(_initialQuerySession);
      }
      // URL을 terminal.html로 정리 (쿼리 파라미터 제거)
      try {
        history.replaceState(null, "", "terminal.html");
      } catch (e) {}
    }

    Board.workflowSessions.refresh(workflowSessionId, isWorkflowMode);
    setInterval(function () {
      Board.workflowSessions.refresh(workflowSessionId, isWorkflowMode);
    }, 5000);

    // Fetch branch on load
    fetch("/api/branch").then(function (r) { return r.json(); }).then(function (d) {
      if (d.branch) {
        var brEl = document.getElementById("terminal-sl-branch");
        if (brEl) brEl.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:3px"><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M6 15V9a6 6 0 0 0 6-6h0a6 6 0 0 0 6 6"/></svg>' + d.branch;
      }
    }).catch(function () {});
  }

  // ── Cleanup ──

  function cleanupTerminal() {
    if (Board.session) Board.session.disconnectSSE();
    outputDiv = null;
    currentToolBox = null;
    toolBoxMap = {};
    thinkingEl = null;
    termInitialized = false;
  }

  // ── Hook into switchTab (SPA mode only) ──
  if (Board.util.switchTab) {
    var originalSwitchTab = Board.util.switchTab;
    Board.util.switchTab = function (target, skipPush) {
      originalSwitchTab(target, skipPush);
      if (target === "terminal" && Board.render.renderTerminal) {
        Board.render.renderTerminal();
      }
    };
  }

  document.querySelectorAll(".tab").forEach(function (t) {
    t.addEventListener("click", function () {
      if (t.dataset.view === "terminal" && Board.render.renderTerminal) {
        Board.render.renderTerminal();
      }
    });
  });

  // ── Register on Board namespace ──
  Board.render.renderTerminal = renderTerminal;
  Board.render.cleanupTerminal = cleanupTerminal;

  // ── Board.sessionSwitcher 공개 API ──
  // renderTerminal() 호출 전에도 사용 가능하도록 IIFE 레벨에서 등록한다.
  // UI 탭 메서드(addTab, removeTab 등)는 renderTerminal() 내에서 추가 등록된다.
  Board.sessionSwitcher = Board.sessionSwitcher || {};

  /**
   * 세션 전환 공개 API.
   * @param {string} sessionId - "main" 또는 "wf-T-NNN-..."
   * @returns {Promise<void>}
   */
  Board.sessionSwitcher.switchSession = function (sessionId) {
    return switchSession(sessionId);
  };

  /**
   * 현재 활성 세션 ID를 반환한다.
   * @returns {string}
   */
  Board.sessionSwitcher.getCurrentSession = function () {
    return _activeSessionId;
  };

  /**
   * 등록된 세션 목록을 반환한다.
   * @returns {Array<{id: string, isWorkflow: boolean, status: string, model: string}>}
   */
  Board.sessionSwitcher.getSessionList = function () {
    return Object.keys(_sessionMap).map(function (id) {
      var e = _sessionMap[id];
      return { id: e.id, isWorkflow: e.isWorkflow, status: e.status, model: e.model };
    });
  };

  /**
   * 새 세션을 등록한다. 이미 존재하면 무시한다.
   * @param {string} sessionId
   * @param {object} [opts] - 초기 상태 오버라이드 (status, model 등)
   */
  Board.sessionSwitcher.addSession = function (sessionId, opts) {
    if (!sessionId) return;
    if (_sessionMap[sessionId]) return;
    var entry = _createSessionEntry(sessionId);
    if (opts) {
      if (opts.status) entry.status = opts.status;
      if (opts.model) entry.model = opts.model;
    }
    _sessionMap[sessionId] = entry;
  };

  /**
   * 세션을 목록에서 제거한다. 현재 활성 세션이면 main으로 전환 후 제거한다.
   * @param {string} sessionId
   */
  Board.sessionSwitcher.removeSession = function (sessionId) {
    if (!sessionId || sessionId === "main") return;
    if (_activeSessionId === sessionId) {
      switchSession("main");
    }
    delete _sessionMap[sessionId];
  };

  /**
   * W01 탭 바 UI 전환 훅. W01에서 오버라이드하여 탭 활성화 처리에 사용한다.
   * @param {string} newSessionId
   * @param {string} prevSessionId
   */
  Board.sessionSwitcher._onSwitch = Board.sessionSwitcher._onSwitch || function (_newId, _prevId) {};
})();
