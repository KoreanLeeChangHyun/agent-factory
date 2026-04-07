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

  function initMarked() {
    if (typeof marked === "undefined") return;

    marked.use({
      breaks: true,
      gfm: true,
      renderer: {
        code: function (token) {
          var text = token.text;
          var lang = token.lang;
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
            body += '<li>' + token.items[i].text + '</li>';
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
      try {
        return marked.parse(text);
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

  /** @type {HTMLElement|null} */
  var outputDiv = null;
  /** @type {HTMLElement|null} */
  var currentToolBox = null;
  /** @type {boolean} */
  var termInitialized = false;
  /** @type {boolean} */
  var inputLocked = false;
  /** @type {Array<string>} */
  var inputQueue = [];
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

  // ── Tool Box Renderer ──

  function createToolBox(toolName) {
    var box = document.createElement("div");
    box.className = "term-tool-box";
    if (toolName) {
      box.setAttribute("data-tool-name", toolName);
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

  function removeEmptyToolBox() {
    if (!currentToolBox) return;
    var fullDiv = currentToolBox.querySelector(".term-tool-output-full");
    if (fullDiv && fullDiv.children.length === 0 && !fullDiv.textContent.trim()) {
      if (currentToolBox.parentNode) {
        currentToolBox.parentNode.removeChild(currentToolBox);
      }
      currentToolBox = null;
    }
  }

  function insertToolResult(text, isError, toolName) {
    if (!currentToolBox) return;
    if (!text && !isError) { removeEmptyToolBox(); return; }
    var fullDiv = currentToolBox.querySelector(".term-tool-output-full");
    if (!fullDiv) return;

    var resolvedToolName = toolName;
    if (!resolvedToolName && currentToolBox.getAttribute) {
      resolvedToolName = currentToolBox.getAttribute("data-tool-name") || undefined;
    }

    var inputDiv = currentToolBox.querySelector(".term-tool-input");
    if (toolInputBuffer && inputDiv) {
      var inputSummary = "";
      try {
        var parsedInput = JSON.parse(toolInputBuffer);
        var effectiveToolName = resolvedToolName || currentToolName;
        if (effectiveToolName === "Bash" && parsedInput.command) {
          inputSummary = "$ " + parsedInput.command;
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
      inputDiv.textContent = inputSummary;
      toolInputBuffer = "";
    } else if (toolInputBuffer) {
      toolInputBuffer = "";
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
    var toggleIcon = currentToolBox.querySelector(".term-toggle-icon");
    currentToolBox.classList.remove("open");
    if (toggleIcon) toggleIcon.classList.remove("rotated");

    var statusEl = currentToolBox.querySelector(".term-tool-status");
    if (statusEl) {
      statusEl.className = isError ? "term-tool-status error" : "term-tool-status done";
      statusEl.innerHTML = isError
        ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#f85149" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
        : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#3fb950" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    }

    if ((effectiveTool === "Bash" || effectiveTool === "Grep" || effectiveTool === "Read") && !isError) {
      var previewDiv = currentToolBox.querySelector(".term-tool-output-preview");
      if (previewDiv) {
        var lines = (text || "").split("\n");
        var previewLines = lines.slice(0, 4);
        previewDiv.textContent = previewLines.join("\n");
      }
    }
  }

  // ── Workflow Tool Card Renderer ──

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

    card.appendChild(cardHeader);

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
    if (toolInputBuffer && inputSpan && !inputSpan.textContent) {
      var inputSummary = "";
      try {
        var parsedInput = JSON.parse(toolInputBuffer);
        var effectiveToolName = resolvedToolName || currentToolName;
        if (effectiveToolName === "Bash" && parsedInput.command) {
          inputSummary = "$ " + parsedInput.command;
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
  }

  function sendInput() {
    var input = document.getElementById("terminal-input");
    if (!input) return;
    var text = input.value.trim();
    if (!text) return;
    if (Board.state.termStatus === "stopped") return;

    input.value = "";
    input.style.height = "auto";

    // Route slash commands (큐에 넣지 않고 즉시 처리)
    if (text.charAt(0) === "/") {
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

    // running 상태(응답 대기 중)이면 큐에 push하고 즉시 리턴
    if (Board.state.termStatus === "running") {
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
    div.textContent = text;
    appendToOutput(div);

    setInputLocked(true);
    startSpinner();
    Board.state.termStatus = "running";
    updateControlBar();

    var ep = endpoints();
    Board.session.postJson(ep.input, ep.inputBody({ text: text })).catch(function (err) {
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
        var html = renderMarkdownToHtml(textBuffer);
        appendHtmlBlock(html, "term-message term-assistant");
      }
      textBuffer = "";
      currentToolBox = null;
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
    var statusDot = document.getElementById("terminal-status-dot");
    var statusText = document.getElementById("terminal-status-text");
    if (startBtn) {
      // Start 버튼은 main 탭(메인 세션) 활성 시에만 표시한다.
      var isMainActive = _activeSessionId === "main";
      if (!isMainActive) {
        startBtn.style.display = "none";
      } else {
        startBtn.style.display = "";
        startBtn.disabled = Board.state.termStatus !== "stopped";
      }
    }
    if (killBtn) {
      killBtn.disabled = Board.state.termStatus === "stopped";
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

    var sendBtn = document.getElementById("terminal-send-btn");
    if (sendBtn && !isWorkflowMode) {
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

    var hintEl = document.querySelector(".terminal-input-hint");
    if (hintEl) {
      if (Board.state.termStatus === "running" && !isWorkflowMode) {
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

  /**
   * 현재 활성 세션의 상태를 _sessionMap에 저장한다.
   */
  function _saveCurrentSession() {
    var entry = _sessionMap[_activeSessionId];
    if (!entry) return;

    // outputDiv 자식 노드 스냅샷
    if (outputDiv) {
      entry.outputNodes = [];
      var children = outputDiv.childNodes;
      for (var i = 0; i < children.length; i++) {
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

    // 4. SSE 재연결: disconnectSSE → connectSSE → fetchStatus
    if (Board.session) {
      Board.session.disconnectSSE();
      Board.session.connectSSE();
      Board.session.fetchStatus();
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
    h += '<button class="terminal-btn terminal-btn-start" id="terminal-start-btn">Start</button>';
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
    h += '<textarea class="terminal-input" id="terminal-input"'
      + ' placeholder="메시지를 입력하세요..." rows="1"'
      + ' autocomplete="off" spellcheck="false"'
      + (Board.state.termStatus === "stopped" ? " disabled" : "")
      + '></textarea>';
    h += '<div class="terminal-input-bottom">';
    h += '<div class="terminal-input-bottom-left"></div>';
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
              var html = renderMarkdownToHtml(textBuffer);
              appendHtmlBlock(html, "term-message term-assistant");
            }
          }
          textBuffer = "";
        },
        appendToolInputBuffer: function (chunk) { toolInputBuffer += chunk; },
        resetToolInputBuffer: function () { toolInputBuffer = ""; },
        setCurrentToolName: function (name) { currentToolName = name; },
        clearCurrentToolBox: function () { currentToolBox = null; },
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
    if (killBtn) {
      killBtn.addEventListener("click", function () { Board.session.killSession(); });
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
          sendInput();
          return;
        }
        e.stopPropagation();
      });
      inputEl.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 120) + "px";
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
        '<span class="session-tab-label">' + (label || sessionId) + '</span>' +
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
