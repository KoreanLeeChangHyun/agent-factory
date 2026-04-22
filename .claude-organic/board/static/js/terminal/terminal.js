/**
 * @module terminal (entry)
 *
 * Board SPA terminal tab module — entry orchestrator.
 * Loaded LAST after output-pipe, tool-box, terminal-input, session-switcher.
 * Initializes shared state on Board._term (M) namespace, provides session
 * dispatch, status line / control bar, and renderTerminal main function.
 */
"use strict";

(function () {
  var esc = Board.util.esc;
  var M = (Board._term = Board._term || {});

  // ── Session dispatcher ──
  M.workflowSessionId = (function () {
    try {
      var p = new URLSearchParams(window.location.search);
      var s = p.get("session");
      if (s && s !== "main" && s.indexOf("wf-") === 0) return s;
    } catch (e) {}
    return null;
  })();

  M.isWorkflowMode = M.workflowSessionId !== null;

  // URL 쿼리 파라미터에서 읽은 초기 세션 ID (M.renderTerminal 후 탭 전환에 사용)
  M._initialQuerySession = M.workflowSessionId;

  // D5 #5: URL 세션 사전 검증 상태. checked=완료, inFlight=fetch 진행 중
  M._initialSessionChecked = false;

  M._initialSessionInFlight = false;

  // 검증 실패 시 렌더 후 노출할 사용자 메시지
  M._initialFallbackMessage = null;

  // ── Session Switcher State ──
  // 세션별 상태를 저장하는 맵. key = sessionId ("main" 또는 "wf-T-NNN-...")
  M._sessionMap = {};

  // 현재 활성 세션 ID
  M._activeSessionId = M.isWorkflowMode ? M.workflowSessionId : "main";

  /**
   * 세션 항목 생성 헬퍼.
   * @param {string} sessionId
   * @returns {object}
   */
  M._createSessionEntry = function(sessionId) {
    return {
      id: sessionId,
      isWorkflow: sessionId !== "main",
      outputNodes: [],   // M.outputDiv 자식 노드 스냅샷 (Array<Node>)
      cost: 0,
      tokens: { input: 0, output: 0 },
      model: "--",
      status: sessionId === "main" ? "stopped" : "running",
      inputQueue: []
    };
  };

  // T-383 Phase 1 (VUL-5 / S5): 초기 활성 세션 엔트리를 사전 생성한다.
  // 과거에는 _sessionMap={} 만 초기화되어 첫 탭 전환 시 _saveCurrentSession 이
  // !entry 가드로 early return 되어 메인 세션의 outputNodes 가 저장되지 않는
  // 버그가 발생했다 (탭 왕복 시 "Claude Code Terminal" 초기 메시지 오출력).
  // URL 쿼리 세션 경로에서 외부가 동일 ID의 엔트리를 먼저 생성하는 경우와의
  // 충돌을 방지하기 위해 idempotent 체크를 수행한다.
  if (!M._sessionMap[M._activeSessionId]) {
    M._sessionMap[M._activeSessionId] = M._createSessionEntry(M._activeSessionId);
  }

  M.endpoints = function() {
    if (M.isWorkflowMode) {
      var sid = encodeURIComponent(M.workflowSessionId);
      return {
        events: "/terminal/workflow/events?session_id=" + sid,
        input: "/terminal/workflow/input",
        kill: "/terminal/workflow/kill",
        status: "/terminal/workflow/status?session_id=" + sid,
        inputBody: function (extra) {
          var b = { session_id: M.workflowSessionId };
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
  };

  /** @type {HTMLElement|null} */
  M.outputDiv = null;

  /** @type {HTMLElement|null} */
  M.currentToolBox = null;

  /** @type {Object<string, HTMLElement>} toolUseId -> box element */
  M.toolBoxMap = {};

  /** @type {boolean} */
  M.termInitialized = false;

  /** @type {boolean} */
  M.inputLocked = false;

  /** @type {Array<string>} */
  M.inputQueue = [];

  /** @type {Array<{data: string, media_type: string, name: string}>} */
  M.attachedImages = [];

  /** @type {Array<{file: File, name: string, size: number, type: string}>} */
  M.attachedFiles = [];

  /** @type {boolean} */
  M.receivedChunks = false;

  /** @type {string} */
  M.textBuffer = "";

  /** @type {string} */
  M.toolInputBuffer = "";

  /** @type {string|null} */
  M.currentToolName = null;

  /** @type {number} */
  M.sessionCost = 0;

  /** @type {object} */
  M.sessionTokens = { input: 0, output: 0 };

  /** @type {string} */
  M.sessionModel = '--';

  /** @type {number} */
  M.contextWindow = 1000000;

  // ── Board.state init ──
  Board.state.termConnected = false;
  Board.state.termSessionId = M.isWorkflowMode ? M.workflowSessionId : null;
  Board.state.termStatus = M.isWorkflowMode ? "running" : "stopped";
  Board.state.termLastSessionId = null;

  // ── Output Clear ──

  M.clearOutput = function() {
    if (M.outputDiv) {
      M.outputDiv.innerHTML = "";
    }
  };

  // ── UI Update ──

  M.updateControlBar = function() {
    var startBtn = document.getElementById("terminal-start-btn");
    var killBtn = document.getElementById("terminal-kill-btn");
    var resumeBtn = document.getElementById("terminal-resume-btn");
    var statusDot = document.getElementById("terminal-status-dot");
    var statusText = document.getElementById("terminal-status-text");
    var isMainActive = M._activeSessionId === "main";
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
      if (M.isWorkflowMode) {
        inputCard.classList.add("wf-input-hidden");
      } else {
        inputCard.classList.remove("wf-input-hidden");
      }
    }

    var sendBtn = document.getElementById("terminal-send-btn");
    if (sendBtn) {
      if (M.isWorkflowMode) {
        sendBtn.style.display = "none";
      } else {
        sendBtn.style.display = "";
        var isRunning = Board.state.termStatus === "running";
        if (isRunning) {
          sendBtn.classList.add("is-stop");
          sendBtn.disabled = false;
          sendBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>';
          sendBtn.onclick = function (e) { e.stopPropagation(); M.interruptSession(); };
        } else {
          sendBtn.classList.remove("is-stop");
          sendBtn.disabled = Board.state.termStatus === "stopped";
          sendBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>';
          sendBtn.onclick = function (e) { e.stopPropagation(); M.sendInput(); };
        }
      }
    }

    var hintEl = document.querySelector(".terminal-input-hint");
    if (hintEl) {
      if (M.isWorkflowMode) {
        hintEl.textContent = "자동 실행 전용";
      } else if (Board.state.termStatus === "running") {
        var queueLen = M.inputQueue.length;
        if (queueLen > 0) {
          hintEl.textContent = "ESC 중지 \u00B7 대기 " + queueLen + "개";
        } else {
          hintEl.textContent = "ESC 중지";
        }
      } else {
        hintEl.textContent = "Enter 전송 \u00B7 Shift+Enter 줄바꿈";
      }
    }

    M.updateStatusLine();
    M.setInputLocked(M.inputLocked);
  };

  M.updateStatusLine = function() {
    var slModel = document.getElementById("terminal-sl-model");
    var slTokens = document.getElementById("terminal-sl-tokens");
    var slCost = document.getElementById("terminal-sl-cost");

    if (slModel) slModel.textContent = M.sessionModel;

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

    var totalTokens = M.sessionTokens.input;
    var pct = M.contextWindow > 0 ? Math.min(totalTokens / M.contextWindow * 100, 100) : 0;
    var barFill = document.getElementById("terminal-sl-bar-fill");
    var barPct = document.getElementById("terminal-sl-bar-pct");
    if (barFill) {
      barFill.style.width = pct.toFixed(1) + "%";
      barFill.style.backgroundColor = pct < 60 ? "#3fb950" : pct < 85 ? "#d29922" : "#f85149";
    }
    if (barPct) barPct.textContent = pct.toFixed(1) + "%";

    if (slTokens) {
      var fmtTotal = totalTokens >= 1000 ? Math.round(totalTokens / 1000) + "k" : totalTokens;
      var fmtCtx = M.contextWindow >= 1000000 ? (M.contextWindow / 1000000) + "M" : Math.round(M.contextWindow / 1000) + "k";
      slTokens.textContent = "(" + fmtTotal + "/" + fmtCtx + ")";
    }

    if (slCost) slCost.textContent = "$" + M.sessionCost.toFixed(4);
  };

  // ── Main Render ──

  M.getContainer = function() {
    var spaEl = document.getElementById("view-terminal");
    if (spaEl) return spaEl;
    var standaloneEl = document.getElementById("terminal-standalone");
    if (standaloneEl) return standaloneEl;
    return null;
  };

  M.renderTerminal = function() {
    var el = M.getContainer();
    if (!el) return;

    // D5 #5: URL 세션 사전 검증 — 잘못된 세션이면 메인으로 fallback 후 재호출
    if (M._initialQuerySession && !M._initialSessionChecked) {
      if (M._initialSessionInFlight) return;
      M._initialSessionInFlight = true;
      var failedId = M._initialQuerySession;
      fetch(
        "/terminal/workflow/status?session_id=" + encodeURIComponent(failedId),
        { cache: "no-store" }
      )
        .then(function (res) {
          if (res.status === 404) {
            M._initialQuerySession = null;
            M.workflowSessionId = null;
            M.isWorkflowMode = false;
            M._activeSessionId = "main";
            delete M._sessionMap[failedId];
            Board.state.termSessionId = null;
            Board.state.termStatus = "stopped";
            try { history.replaceState(null, "", "terminal.html"); } catch (e) {}
            M._initialFallbackMessage =
              "[Error] URL 세션 '" + failedId + "'을 찾을 수 없어 메인 세션으로 전환했습니다.";
          }
        })
        .catch(function () { /* network error: 기본 동작 유지 */ })
        .then(function () {
          M._initialSessionChecked = true;
          M._initialSessionInFlight = false;
          M.renderTerminal();
        });
      return;
    }

    if (M.termInitialized && document.getElementById("terminal-output")) {
      M.updateControlBar();
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

    M.initOutputDiv();

    // Workflow mode: insert timeline bar placeholder
    if (M.isWorkflowMode) {
      Board.phaseTimeline.insertPlaceholder();
    }

    // Bind session module to core context
    if (Board.session && Board.session._bind) {
      Board.session._bind({
        endpoints: M.endpoints,
        isWorkflowMode: function () { return M.isWorkflowMode; },
        getWorkflowSessionId: function () { return M.workflowSessionId; },
        updateControlBar: M.updateControlBar,
        updateStatusLine: M.updateStatusLine,
        appendToOutput: M.appendToOutput,
        appendSystemMessage: M.appendSystemMessage,
        appendErrorMessage: M.appendErrorMessage,
        appendHtmlBlock: M.appendHtmlBlock,
        createToolBox: M.createToolBox,
        removeEmptyToolBox: M.removeEmptyToolBox,
        removeEmptyWorkflowToolCard: M.removeEmptyWorkflowToolCard,
        insertToolResult: M.insertToolResult,
        insertWorkflowResult: M.insertWorkflowResult,
        createWorkflowToolCard: M.createWorkflowToolCard,
        clearCurrentWorkflowToolCard: function () { M.currentWorkflowToolCard = null; },
        clearOutput: M.clearOutput,
        startSpinner: M.startSpinner,
        stopSpinner: M.stopSpinner,
        setInputLocked: M.setInputLocked,
        setReceivedChunks: function (v) { M.receivedChunks = v; },
        getReceivedChunks: function () { return M.receivedChunks; },
        appendTextBuffer: function (chunk) { M.textBuffer += chunk; },
        flushTextBuffer: function () {
          if (M.textBuffer) {
            if (M.isWorkflowMode) {
              var wfHtml = M.renderMarkdownToHtml(M.textBuffer);
              Board.WorkflowRenderer.insertToCurrentPanel(
                '<div class="wf-assistant-block">' + wfHtml + '</div>'
              );
            } else {
              if (Board.WfTicketRenderer && Board.WfTicketRenderer.detect(M.textBuffer)) {
                Board.WfTicketRenderer.render(M.textBuffer);
              } else {
                var html = M.renderMarkdownToHtml(M.textBuffer);
                M.appendHtmlBlock(html, "term-message term-assistant");
              }
            }
          }
          M.textBuffer = "";
        },
        appendToolInputBuffer: function (chunk) { M.toolInputBuffer += chunk; },
        resetToolInputBuffer: function () { M.toolInputBuffer = ""; },
        setCurrentToolName: function (name) { M.currentToolName = name; },
        clearCurrentToolBox: function () { M.currentToolBox = null; },
        getToolBoxMap: function () { return M.toolBoxMap; },
        resetToolBoxMap: function () { M.toolBoxMap = {}; },
        resetTokens: function () { M.sessionTokens = { input: 0, output: 0 }; M.sessionCost = 0; },
        setSessionCost: function (v) { M.sessionCost = v; },
        addInputTokens: function (n) { M.sessionTokens.input += n; },
        addOutputTokens: function (n) { M.sessionTokens.output += n; },
        setInputTokens: function (n) { M.sessionTokens.input = n; },
        setOutputTokens: function (n) { M.sessionTokens.output = n; },
        getSessionTokens: function () { return M.sessionTokens; },
        setSessionModel: function (v) { M.sessionModel = v; },
        setContextWindow: function (v) { M.contextWindow = v; },
        drainQueue: M.drainQueue,
        getInputQueue: function () { return M.inputQueue; }
      });
    }

    // Bind WfTicketRenderer context
    if (Board.WfTicketRenderer) {
      Board.WfTicketRenderer.setContext({
        appendToOutput: M.appendToOutput || M.appendHtmlBlock,
        endpoints: M.endpoints,
        renderMarkdownToHtml: M.renderMarkdownToHtml,
        setInputLocked: M.setInputLocked,
        startSpinner: M.startSpinner,
        stopSpinner: M.stopSpinner,
        updateControlBar: M.updateControlBar,
        appendErrorMessage: M.appendErrorMessage
      });
    }

    // Connect SSE
    if (Board.session) {
      Board.session.connectSSE();
      Board.session.fetchStatus();
    }

    // D5 #5: URL 세션 사전 검증 실패 알림 (렌더 후 M.outputDiv 준비 완료 시점)
    if (M._initialFallbackMessage) {
      M.appendErrorMessage(M._initialFallbackMessage);
      M._initialFallbackMessage = null;
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
            timeSpan.textContent = M.formatRelativeTime(s.last_active);
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
          browseSessionList.innerHTML = '<div class="terminal-browse-error">세션 목록 로드 실패 (' + M.escapeHtml(msg) + ')</div>';
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
          M.appendErrorMessage("[Error] Login failed: " + err.message);
        });
      });
    }
    var clearBtn = document.getElementById("terminal-clear-output");
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        settingsDropdown.classList.remove("visible");
        M.clearOutput();
      });
    }
    if (inputEl) {
      inputEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
          e.preventDefault();
          if (!M.isWorkflowMode) M.sendInput();
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
            if (file) M.attachImage(file);
          }
        }
        if (hasImage) {
          e.preventDefault();
          return;
        }
        // image/* 가 없으면 text/plain 경로 패턴 확인
        var text = e.clipboardData.getData("text/plain");
        if (text && M.isFilePath(text)) {
          e.preventDefault();
          M.insertTextAtCursor(inputEl, text);
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
              // 이미지 파일: 기존 M.attachImage() 경로 재사용 (썸네일 렌더링)
              M.attachImage(droppedFile);
            } else {
              // 비이미지 파일: attachedFiles에 등록 후 파일 카드 렌더링
              M.attachedFiles.push({ file: droppedFile, name: droppedFile.name, size: droppedFile.size, type: droppedFile.type });
              M.renderFilePreview();
              M.insertTextAtCursor(targetInput, droppedFile.name + (fi < dt.files.length - 1 ? "\n" : ""));
            }
          }
          return;
        }

        // (b) text/plain 이 경로 패턴이면 textarea에 경로 삽입
        var dropText = dt.getData("text/plain");
        if (dropText && M.isFilePath(dropText)) {
          M.insertTextAtCursor(targetInput, dropText);
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
          M.attachImage(files[i]);
        }
        this.value = "";
      });
    }

    // Keyboard shortcuts
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !M.isWorkflowMode && Board.state.termStatus === "running") {
        e.preventDefault();
        M.interruptSession();
        return;
      }
    });

    M.termInitialized = true;

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

    // _onSwitch 훅: M.switchSession() 호출 시 탭 바 활성 상태 업데이트
    Board.sessionSwitcher._onSwitch = function (newSessionId, _prevId) {
      if (Board.sessionSwitcher.setActiveTab) {
        Board.sessionSwitcher.setActiveTab(newSessionId);
      }
    };

    // URL ?session= 쿼리 파라미터 기반 초기 세션 탭 처리
    if (M._initialQuerySession) {
      // 탭 바에 초기 세션 추가 (워크플로우 탭)
      if (Board.sessionSwitcher.addTab) {
        var initLabel = M._initialQuerySession.replace(/^wf-/, "").replace(/-\d+$/, "");
        Board.sessionSwitcher.addTab(M._initialQuerySession, initLabel, "running");
      }
      // 탭 활성화 (초기 세션이 활성 탭으로 표시)
      if (Board.sessionSwitcher.setActiveTab) {
        Board.sessionSwitcher.setActiveTab(M._initialQuerySession);
      }
      // URL을 terminal.html로 정리 (쿼리 파라미터 제거)
      try {
        history.replaceState(null, "", "terminal.html");
      } catch (e) {}
    }

    Board.workflowSessions.refresh(M.workflowSessionId, M.isWorkflowMode);
    setInterval(function () {
      Board.workflowSessions.refresh(M.workflowSessionId, M.isWorkflowMode);
    }, 5000);

    // Fetch branch on load
    fetch("/api/branch").then(function (r) { return r.json(); }).then(function (d) {
      if (d.branch) {
        var brEl = document.getElementById("terminal-sl-branch");
        if (brEl) brEl.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:3px"><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M6 15V9a6 6 0 0 0 6-6h0a6 6 0 0 0 6 6"/></svg>' + d.branch;
      }
    }).catch(function () {});
  };

  // ── Cleanup ──

  M.cleanupTerminal = function() {
    if (Board.session) Board.session.disconnectSSE();
    M.outputDiv = null;
    M.currentToolBox = null;
    M.toolBoxMap = {};
    M.thinkingEl = null;
    M.termInitialized = false;
  };


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
  Board.render.renderTerminal = M.renderTerminal;
  Board.render.cleanupTerminal = M.cleanupTerminal;

  // ── Board.sessionSwitcher 공개 API ──
  // M.renderTerminal() 호출 전에도 사용 가능하도록 IIFE 레벨에서 등록한다.
  // UI 탭 메서드(addTab, removeTab 등)는 M.renderTerminal() 내에서 추가 등록된다.
  Board.sessionSwitcher = Board.sessionSwitcher || {};

  /**
   * 세션 전환 공개 API.
   * @param {string} sessionId - "main" 또는 "wf-T-NNN-..."
   * @returns {Promise<void>}
   */
  Board.sessionSwitcher.switchSession = function (sessionId) {
    return M.switchSession(sessionId);
  };

  /**
   * 현재 활성 세션 ID를 반환한다.
   * @returns {string}
   */
  Board.sessionSwitcher.getCurrentSession = function () {
    return M._activeSessionId;
  };

  /**
   * 등록된 세션 목록을 반환한다.
   * @returns {Array<{id: string, isWorkflow: boolean, status: string, model: string}>}
   */
  Board.sessionSwitcher.getSessionList = function () {
    return Object.keys(M._sessionMap).map(function (id) {
      var e = M._sessionMap[id];
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
    if (M._sessionMap[sessionId]) return;
    var entry = M._createSessionEntry(sessionId);
    if (opts) {
      if (opts.status) entry.status = opts.status;
      if (opts.model) entry.model = opts.model;
    }
    M._sessionMap[sessionId] = entry;
  };

  /**
   * 세션을 목록에서 제거한다. 현재 활성 세션이면 main으로 전환 후 제거한다.
   * @param {string} sessionId
   */
  Board.sessionSwitcher.removeSession = function (sessionId) {
    if (!sessionId || sessionId === "main") return;
    if (M._activeSessionId === sessionId) {
      M.switchSession("main");
    }
    delete M._sessionMap[sessionId];
  };

  /**
   * W01 탭 바 UI 전환 훅. W01에서 오버라이드하여 탭 활성화 처리에 사용한다.
   * @param {string} newSessionId
   * @param {string} prevSessionId
   */
  Board.sessionSwitcher._onSwitch = Board.sessionSwitcher._onSwitch || function (_newId, _prevId) {};
})();
