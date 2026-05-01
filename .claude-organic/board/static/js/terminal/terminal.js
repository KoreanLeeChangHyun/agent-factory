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

  /**
   * 입력 큐. 각 항목은 pending entry 객체 (1:1 turn 모델 — nextTurn 필드 없음).
   * @type {Array<{id: string, text: string, ts: number, status: string}>}
   */
  M.inputQueue = [];

  /**
   * IME 조합 중 여부 (compositionstart/end 리스너가 관리).
   * @type {boolean}
   */
  M._isComposing = false;

  /**
   * 직전 send 한 사용자 메시지 텍스트.
   * ESC 인터럽트 시 입력창에 자동 복원하여 사용자가 수정 후 재전송 가능하게 한다.
   * sendInput / commitQueue 가 send 직전에 저장하고, interruptSession 이 복원 후 클리어한다.
   * @type {string}
   */
  M._lastSentText = "";

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
  // 워크플로우 모드는 서버 측 채널이 이미 실행 중이라 idle 로 시작한다.
  // 메인 모드는 Start 전이므로 stopped.
  // 단, ESC 인터럽트 직후 새로고침 케이스(localStorage 에 ESC 복원 텍스트가 남음)는
  // 서버 측 프로세스가 자동 resume 으로 살아있을 가능성이 높으므로 'starting' 으로
  // 시작해 STOPPED 깜박임을 회피한다. fetchStatus 응답으로 idle/busy 로 보정된다.
  var _hasPendingEscRestore = false;
  try { _hasPendingEscRestore = !!localStorage.getItem("board.term.lastSentText"); } catch (e) {}
  Board.state.termStatus = M.isWorkflowMode
    ? "idle"
    : (_hasPendingEscRestore ? "starting" : "stopped");
  Board.state.termLastSessionId = null;

  if (Board.debugLog) Board.debugLog('terminal.init', {
    isWorkflowMode: M.isWorkflowMode, termStatus: Board.state.termStatus,
    href: location.href,
  });

  // ── Output Clear ──

  M.clearOutput = function() {
    if (M.outputDiv) {
      M.outputDiv.innerHTML = "";
    }
  };

  // ── UI Update ──

  M.showRestartOverlay = function() {
    if (document.querySelector(".terminal-restart-overlay")) return;
    var overlay = document.createElement("div");
    overlay.className = "terminal-restart-overlay";
    var spinner = document.createElement("div");
    spinner.className = "terminal-restart-overlay-spinner";
    var label = document.createElement("div");
    label.className = "terminal-restart-overlay-label";
    label.textContent = "서버 재기동 중...";
    overlay.appendChild(spinner);
    overlay.appendChild(label);
    document.body.appendChild(overlay);
  };

  M.updateControlBar = function() {
    var toggleBtn = document.getElementById("terminal-toggle-btn");
    var statusDot = document.getElementById("terminal-status-dot");
    var statusText = document.getElementById("terminal-status-text");
    var isMainActive = M._activeSessionId === "main";
    var status = Board.state.termStatus;
    var killable = Board.util.TERM_STATUS_KILLABLE.has(status);
    var inputtable = Board.util.TERM_STATUS_INPUTTABLE.has(status);
    var isStopped = status === "stopped";
    var isBusy = status === "busy";
    if (toggleBtn) {
      // 토글 버튼은 main 탭 활성 시에만 표시한다.
      if (!isMainActive) {
        toggleBtn.style.display = "none";
      } else if (status === "archived" || status === "missing") {
        // archived/missing 에선 Start/Kill 모두 의미 없음.
        toggleBtn.style.display = "none";
      } else if (killable) {
        toggleBtn.style.display = "";
        toggleBtn.textContent = "Close";
        toggleBtn.classList.add("terminal-btn-kill");
        toggleBtn.classList.remove("terminal-btn-start");
        toggleBtn.disabled = false;
      } else {
        // stopped
        toggleBtn.style.display = "";
        toggleBtn.textContent = "Start";
        toggleBtn.classList.add("terminal-btn-start");
        toggleBtn.classList.remove("terminal-btn-kill");
        toggleBtn.disabled = false;
      }
    }
    var memoryBtn = document.getElementById("terminal-memory-btn");
    if (memoryBtn) {
      if (!isMainActive) {
        memoryBtn.style.display = "none";
      } else {
        memoryBtn.style.display = "";
        memoryBtn.disabled = !inputtable;
        var memHasMsg = !!(M.outputDiv && M.outputDiv.querySelector(".term-message"));
        memoryBtn.title = memHasMsg
          ? "메모리 업데이트 (현재 세션 내용을 메모리에 영속화 — Clear 전)"
          : "메모리 로드 (현재 세션에 MEMORY.md 재인지 요청)";
      }
    }
    var loginBtn = document.getElementById("terminal-login");
    if (loginBtn) {
      loginBtn.disabled = !inputtable;
    }
    if (statusDot) {
      statusDot.className = "terminal-status-dot terminal-status-" + status;
    }
    var statusContainer = document.querySelector(".terminal-status");
    if (statusContainer) {
      statusContainer.setAttribute("data-state", status);
    }
    if (statusText) {
      var labels = Board.util.TERM_STATUS_LABELS || {};
      statusText.textContent = labels[status] || status;
    }
    var sessionIdEl = document.getElementById("terminal-session-id");
    if (sessionIdEl) {
      // stopped 상태에선 .last-session-id 에서 복원된 UUID 가 남아있어도 숨긴다.
      // 과거 세션은 Sessions 드롭다운에서 명시적으로 resume 한다.
      sessionIdEl.textContent = (!isStopped && Board.state.termSessionId) ? Board.state.termSessionId : '';
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
        if (M._interruptInFlight) {
          // interrupt 후 result 대기 중 — 버튼을 잠시 비활성화하여 재클릭 차단
          // 및 사용자에게 처리 중임을 시각적으로 알린다. result 도착 시
          // _onResult 가 플래그를 끄고 updateControlBar 호출.
          sendBtn.classList.add("is-stop");
          sendBtn.disabled = true;
          sendBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>';
          sendBtn.onclick = null;
        } else if (isBusy) {
          // busy: Claude 응답 중 → interrupt 버튼
          sendBtn.classList.add("is-stop");
          sendBtn.disabled = false;
          sendBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>';
          sendBtn.onclick = function (e) { e.stopPropagation(); M.interruptSession(); };
        } else {
          sendBtn.classList.remove("is-stop");
          sendBtn.disabled = !inputtable;
          sendBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>';
          sendBtn.onclick = function (e) { e.stopPropagation(); M.sendInput(); };
        }
      }
    }

    var hintEl = document.querySelector(".terminal-input-hint");
    if (hintEl) {
      if (M.isWorkflowMode) {
        hintEl.textContent = "자동 실행 전용";
      } else if (isBusy) {
        // busy: 큐 카운트 노출 (현재 처리 중인 메시지 포함)
        var queueLen = M.inputQueue.length;
        if (queueLen > 0) {
          hintEl.textContent = "ESC 중지 \u00B7 큐 " + queueLen + "개 (처리 중\u00B7대기)";
        } else {
          hintEl.textContent = "ESC 중지";
        }
      } else if (status === "starting") {
        hintEl.textContent = "Starting session...";
      } else if (status === "archived") {
        hintEl.textContent = "Read-only (archived)";
      } else if (status === "missing") {
        hintEl.textContent = "Session not found";
      } else {
        // idle (큐 = 0): 정상 입력 힌트
        hintEl.textContent = "Shift+Enter 줄바꿈";
      }
    }

    M.updateStatusLine();
    M.setInputLocked(M.inputLocked);
  };

  M.updateStatusLine = function() {
    if (Board.debugLog) Board.debugLog('updateStatusLine', {
      input: M.sessionTokens.input, output: M.sessionTokens.output,
      ctxWindow: M.contextWindow, activeSession: M._activeSessionId,
    });
    var slModel = document.getElementById("terminal-sl-model");
    var slTokens = document.getElementById("terminal-sl-tokens");
    var slCost = document.getElementById("terminal-sl-cost");

    if (slModel) slModel.textContent = M.sessionModel;

    var slBranch = document.getElementById("terminal-sl-branch");
    if (slBranch) {
      var branchText = slBranch.textContent.trim();
      if (branchText && branchText !== "--") {
        Board.util.setBranchStatusBar(branchText);
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
            Board.state.setTermStatus("stopped");
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
    h += '<button class="terminal-btn terminal-btn-start" id="terminal-toggle-btn">Start</button>';
    h += '<span class="terminal-controls-divider"></span>';
    h += '<button class="terminal-btn terminal-btn-memory" id="terminal-memory-btn" title="메모리 로드 (현재 세션에 MEMORY.md 재인지 요청)">Memory</button>';
    h += '<span class="terminal-controls-divider"></span>';
    h += '<button class="terminal-btn terminal-btn-sessions" id="terminal-sessions-btn" title="Main sessions">';
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

    h += '<div class="terminal-input-queue" id="terminal-input-queue" hidden></div>';
    h += '<div class="terminal-input-card">';
    h += '<div class="terminal-image-preview" id="terminal-image-preview"></div>';
    h += '<textarea class="terminal-input" id="terminal-input"'
      + ' placeholder="메시지를 입력하세요..." rows="1"'
      + ' autocomplete="off" spellcheck="false"'
      + (Board.util.TERM_STATUS_INPUTTABLE.has(Board.state.termStatus) ? "" : " disabled")
      + '></textarea>';
    h += '<div class="terminal-input-bottom">';
    h += '<div class="terminal-input-bottom-left">';
    h += '<button class="terminal-attach-btn" id="terminal-attach-btn" title="이미지 첨부"'
      + (Board.util.TERM_STATUS_INPUTTABLE.has(Board.state.termStatus) ? "" : " disabled")
      + '><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg></button>';
    h += '<input type="file" id="terminal-attach-input" accept="image/png,image/jpeg,image/gif,image/webp" style="display:none" multiple>';
    h += '</div>';
    h += '<div class="terminal-input-bottom-right">';
    h += '<span class="terminal-input-hint">Shift+Enter 줄바꿈</span>';
    h += '<button class="terminal-send-btn" id="terminal-send-btn"'
      + (Board.util.TERM_STATUS_INPUTTABLE.has(Board.state.termStatus) ? "" : " disabled")
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

    // [ESC 새로고침 복원] localStorage 에 저장된 ESC 직전 메시지가 있으면 입력창에
    // 자동 채운다 (사용자가 수정/재전송 가능). sendInput/commitQueue 가 send 시점에
    // localStorage 를 클리어하므로 영구 잔류는 없다.
    if (!M.isWorkflowMode) {
      try {
        var savedText = localStorage.getItem("board.term.lastSentText");
        if (savedText) {
          var inputElRestore = document.getElementById("terminal-input");
          if (inputElRestore) {
            inputElRestore.value = savedText;
            inputElRestore.style.height = "auto";
            inputElRestore.style.height = inputElRestore.scrollHeight + "px";
          }
        }
      } catch (e) {}
    }

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
        resetTokens: function () {
          if (Board.debugLog) Board.debugLog('resetTokens', {
            prev: { input: M.sessionTokens.input, output: M.sessionTokens.output },
            stack: new Error().stack.split('\n').slice(1, 5).join(' | '),
          });
          M.sessionTokens = { input: 0, output: 0 };
          M.sessionCost = 0;
        },
        setSessionCost: function (v) { M.sessionCost = v; },
        addInputTokens: function (n) { M.sessionTokens.input += n; },
        addOutputTokens: function (n) { M.sessionTokens.output += n; },
        setInputTokens: function (n) {
          if (Board.debugLog && n !== M.sessionTokens.input) Board.debugLog('setInputTokens', {
            prev: M.sessionTokens.input, next: n,
          });
          M.sessionTokens.input = n;
        },
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
      var statusPromise = Board.session.fetchStatus();
      // 메인 세션 한정: 상태 확정 후 히스토리 복원 또는 빈 상태 표시.
      // session_id 는 .last-session-id 에서 복원될 수 있어 stopped 상태에도
      // 남아 있다. 세션이 실제 살아 있을 때(= stopped 아님)만 자동 복원한다.
      // Start 전 빈 화면을 유지하고, 과거 세션은 드롭다운에서 명시적으로
      // resume 하는 흐름.
      if (!M.isWorkflowMode && statusPromise && typeof statusPromise.then === "function") {
        statusPromise.then(function () {
          var sid = Board.state.termSessionId;
          var status = Board.state.termStatus;
          if (sid && status && status !== "stopped") {
            M.loadHistory(sid);
          } else {
            M.showEmptyState();
          }
        });
      }
    }

    // D5 #5: URL 세션 사전 검증 실패 알림 (렌더 후 M.outputDiv 준비 완료 시점)
    if (M._initialFallbackMessage) {
      M.appendErrorMessage(M._initialFallbackMessage);
      M._initialFallbackMessage = null;
    }

    // Bind event handlers
    var toggleBtn = document.getElementById("terminal-toggle-btn");
    var inputEl = document.getElementById("terminal-input");

    if (toggleBtn) {
      toggleBtn.addEventListener("click", function () {
        var status = Board.state.termStatus;
        if (status === "stopped") {
          Board.session.startSession();
        } else if (Board.util.TERM_STATUS_KILLABLE.has(status)) {
          Board.session.killSession();
        }
        // archived/missing: 버튼 자체가 숨겨져 클릭 도달 안 함 (방어 용도)
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
        M.showRestartOverlay();
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
        if (!Board.util.TERM_STATUS_INPUTTABLE.has(Board.state.termStatus)) return;
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
      // IME 조합 중 플래그 — compositionstart/end 이벤트로 관리
      inputEl.addEventListener("compositionstart", function () {
        M._isComposing = true;
      });
      inputEl.addEventListener("compositionend", function () {
        M._isComposing = false;
      });

      inputEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          // IME 조합 중이면 Enter 를 가로채지 않는다.
          // e.isComposing: 표준 (Chrome/Firefox/Edge)
          // M._isComposing: Safari 등 일부 브라우저에서 e.isComposing 이 false 로 빠지는 케이스 대비
          if (e.isComposing || M._isComposing) return;

          e.preventDefault();
          if (M.isWorkflowMode) return;

          // 모든 분기를 sendInput 으로 통일.
          // sendInput 내부에서 idle: 즉시 echo + send, busy: enqueueInput (텍스트+이미지)
          // 으로 분기한다. 이미지 첨부 시도 동일 경로로 큐잉된다.
          M.sendInput();
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
        // 작은따옴표로 감싸 "/" 로 시작하는 경로가 슬래시 커맨드로 오인되는 것을 차단한다.
        var text = e.clipboardData.getData("text/plain");
        if (text && M.isFilePath(text)) {
          e.preventDefault();
          M.insertTextAtCursor(inputEl, "'" + text + "'");
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
        // 작은따옴표로 감싸 "/" 로 시작하는 경로가 슬래시 커맨드로 오인되는 것을 차단한다.
        var dropText = dt.getData("text/plain");
        if (dropText && M.isFilePath(dropText)) {
          M.insertTextAtCursor(targetInput, "'" + dropText + "'");
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
      if (e.key === "Escape" && !M.isWorkflowMode && Board.state.termStatus === "busy") {
        e.preventDefault();
        M.interruptSession();
        return;
      }
    });

    M.termInitialized = true;

    // Memory shortcut: 세션 상태에 따라 분기
    //  - 메시지 0 (처음/resume 직후): 메모리 인지 요청 (id: memory.load)
    //  - 메시지 1+ (중간): 현재 세션 내용 메모리 영속화 (id: memory.persist)
    // 두 문구는 .claude-organic/board/config/quick-prompts.json 에서 사용자가 편집 가능.
    // fetch 실패 시 기본 폴백 텍스트 사용 — 오프라인이거나 파일 누락 시에도 동작 유지.
    var FALLBACK_MEMORY_LOAD = "메모리 로드하세요";
    var FALLBACK_MEMORY_PERSIST = "이번 세션의 핵심 내용(결정·학습·이슈·규칙)을 메모리에 영속화해주세요. 적절한 type(user/feedback/project/reference)으로 분류하고, 기존 메모와 중복되면 보강.";
    var memoryBtn = document.getElementById("terminal-memory-btn");
    if (memoryBtn) {
      memoryBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        if (M.isWorkflowMode) return;
        if (!Board.util.TERM_STATUS_INPUTTABLE.has(Board.state.termStatus)) return;
        var input = document.getElementById("terminal-input");
        if (!input) return;
        var hasMessages = !!(M.outputDiv && M.outputDiv.querySelector(".term-message"));
        var promptId = hasMessages ? "memory.persist" : "memory.load";
        var fallback = hasMessages ? FALLBACK_MEMORY_PERSIST : FALLBACK_MEMORY_LOAD;
        var lookup = (Board.fetch && Board.fetch.getQuickPromptText)
          ? Board.fetch.getQuickPromptText(promptId, fallback)
          : Promise.resolve(fallback);
        lookup.then(function (text) {
          input.value = text || fallback;
          M.sendInput();
        });
      });
    }

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

    // Fetch branch on load — SSE git_branch 이벤트(core/sse.js)가 후속 갱신을 담당한다.
    fetch("/api/branch").then(function (r) { return r.json(); }).then(function (d) {
      Board.util.setBranchStatusBar(d.branch);
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
