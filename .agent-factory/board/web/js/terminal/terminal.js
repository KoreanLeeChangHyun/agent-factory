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
  // WR-513 P3 — V1 Main Terminal Workflow Mode Waster (Crystal Point #1 + #5).
  // The old URL `?session=wf-...` entry point terminal — the main terminal is only active in the main mode.
  // Production-line workflow enters production-line-workflow.js.
  M.workflowSessionId = null;

  M.isWorkflowMode = false;

  // Old V1 workflow mode URL query entry is closed — this variable is null fixed
  // line ~1134 'if(M. initialQuerySession)' branch is dead.
  M._initialQuerySession = null;

  // D5 #5: URL session pre-valid status. check=complete, inFlight=fetch progress
  M._initialSessionChecked = false;

  M._initialSessionInFlight = false;

  // User messages that are exposed after rendering fails
  M._initialFallbackMessage = null;

  // ── Session Switcher State ──
  // Map to save the status of session. key = sessionId ("main" or "wf-WR-NNN-...")
  M._sessionMap = {};

  // Current Activity Session ID
  M._activeSessionId = M.isWorkflowMode ? M.workflowSessionId : "main";

  /**
   * Create session entries Helper.
   * @param {string} sessionId
   * @returns {object}
   */
  M._createSessionEntry = function(sessionId) {
    return {
      id: sessionId,
      isWorkflow: sessionId !== "main",
      outputNodes: [],   // M.outputDiv Self-catering node snapshot (Array<Node>)
      cost: 0,
      tokens: { input: 0, output: 0 },
      model: "--",
      status: sessionId === "main" ? "stopped" : "running",
      inputQueue: []
    };
  };

  // WR-383 Phase 1 (VUL-5/S5): Pre-generate the initial active session entries.
  // In the past,  sessionMap={} only reset and switch to the first tab  saveCurrentSession
  // !entry mad to early return and outputNodes of main session is not saved
  // "Agent Factory Console" initial message O/O output when the bug has occurred.
  // In the URL query session path, if external generates the same ID entry first
  // Perform idempotent checks to prevent collisions.
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

  M.terminalProvider = "claude";

  M.terminalCapabilities = {
    resume: true,
    attachments: true,
    permission_prompts: true,
    interrupt: true,
    slash_commands: true,
    multiple_inputs: true
  };

  M.hasCapability = function(name) {
    return !!(M.terminalCapabilities && M.terminalCapabilities[name]);
  };

  /**
   * Type C. Each item is pending entry object (1:1 turn model — no nextTurn field).
   * @type {Array<{id: string, text: string, ts: number, status: string}>}
   */
  M.inputQueue = [];

  /**
   * Whether it’s an IME combination (compositionstart/end listener is managed).
   * @type {boolean}
   */
  M._isComposing = false;

  /**
   * Send the user message text directly.
   * Automatically restores the ESC intermittent input window and enables users to retransmission after modification.
   * sendInput / commitQueue will store it immediately before send, and stopSession will be clear after restore.
   * @type {string}
   */
  M._lastSentText = "";

  /** @type {Array<{data: string, media_type: string, name: string}>} */
  M.attachedImages = [];

  /** @type {Array<{file: File, name: string, size: number, type: string}>} */
  M.attachedFiles = [];

  /**
   * Conveyor card → workRequest domain with main terminal DnD.
   * Automatic rain after sending the same as image/file attachment (M.clearWorkRequests).
   * Each item is fetched report.html text at the time of dragstart.
   * @type {Array<{number: string, title: string, command: string, prompt: any, result: any, report: string|null, addedAt: number}>}
   */
  M.attachedWorkRequests = [];

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
  // The workflow mode starts with idle as the server side channel is already running.
  // The main mode is before Start, so stop.
  // Single, ESC INTERFAT re-called case (localStorage ESC restore text)
  // The server side process is likely to live with automatic resume, so as to 'starting'
  // Launches the STOPPED flash. fetchStatus response is corrected by idle/busy.
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
    label.textContent = "Server rebuild...";
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
    // inAutoResume Can be stopped/starting in Windows — input window flash.
    var inputtable = Board.util.TERM_STATUS_INPUTTABLE.has(status)
        || !!Board.state._inAutoResume;
    var isStopped = status === "stopped";
    var isBusy = status === "busy";
    var supportsResume = M.hasCapability("resume");
    var supportsAttachments = M.hasCapability("attachments");
    if (toggleBtn) {
      // Toggle button only displays the main tab active.
      if (!isMainActive) {
        toggleBtn.style.display = "none";
      } else if (status === "archived" || status === "missing") {
        // Start/Kill in archived/missing
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
          ? "Memory Update (Current Session Content to Memory — Clear Before)"
          : "Memory Load (MMEMORY.md Re-Case request to current session)";
      }
    }
    var sessionsBtn = document.getElementById("terminal-sessions-btn");
    if (sessionsBtn) {
      sessionsBtn.disabled = !supportsResume;
      sessionsBtn.title = supportsResume ? "Main sessions" : "Session resume is not supported by this provider";
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
      // .last-session-id restored UUID remains hidden at stop status.
      // The past session is explicitly resumed in Sessions dropdown.
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
          // return result after interruption — deactivate button and block re-click
          // We use cookies to ensure that we give you the best experience on our website. return
          // onResult turns the flag and call updateControlBar.
          sendBtn.classList.add("is-stop");
          sendBtn.disabled = true;
          sendBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>';
          sendBtn.onclick = null;
        } else if (isBusy) {
          // busy: Claude response during → interrupt button
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
        hintEl.textContent = "Auto Run Only";
      } else if (isBusy) {
        // busy: Cue Count exposure (includes current processing messages)
        var queueLen = M.inputQueue.length;
        if (queueLen > 0) {
          hintEl.textContent = "ESC Stop \\u00B7 Cue" + queueLen + "(in processing \\u00B7)";
        } else {
          hintEl.textContent = "ESC";
        }
      } else if (status === "starting") {
        hintEl.textContent = "Starting session...";
      } else if (status === "archived") {
        hintEl.textContent = "Read-only (archived)";
      } else if (status === "missing") {
        hintEl.textContent = "Session not found";
      } else {
        // idle (Q = 0): Normal input hint
        hintEl.textContent = "Shift+Enter";
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

    if (slModel) {
      var providerLabel = M.terminalProvider
        ? M.terminalProvider.charAt(0).toUpperCase() + M.terminalProvider.slice(1)
        : "";
      slModel.textContent = providerLabel
        ? providerLabel + (M.sessionModel && M.sessionModel !== "--" ? " " + M.sessionModel : "")
        : M.sessionModel;
    }

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
      barFill.style.backgroundColor = pct < 60 ? "#D97757" : pct < 85 ? "#d29922" : "#f85149";
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

    // D5 #5: URL Session Preliminary Verification — Reissue after fallback in the main
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
              "[Error] URL Session '" + failedId + "You can't find it, switched to the main session.";
          }
        })
        .catch(function () { /* network error: */ })
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
    h += '<button class="terminal-btn terminal-btn-memory" id="terminal-memory-btn" title="MEMORY.md re-order request at current session)">Memory</button>';
    h += '<span class="terminal-controls-divider"></span>';
    h += '<button class="terminal-btn terminal-btn-sessions" id="terminal-sessions-btn" title="Main sessions">';
    h += '<span id="terminal-sessions-label">Sessions</span>';
    h += '<span class="terminal-sessions-count" id="terminal-sessions-count" style="display:none"></span>';
    h += '</button>';
    h += '<div class="terminal-sessions-dropdown" id="terminal-sessions-dropdown"></div>';
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
      + 'placeholder..." rows="1"'
      + ' autocomplete="off" spellcheck="false"'
      + (Board.util.TERM_STATUS_INPUTTABLE.has(Board.state.termStatus) ? "" : " disabled")
      + '></textarea>';
    h += '<div class="terminal-input-bottom">';
    h += '<div class="terminal-input-bottom-left">';
    h += '<button class="terminal-attach-btn" id="terminal-attach-btn" title="Withimage"'
      + (Board.util.TERM_STATUS_INPUTTABLE.has(Board.state.termStatus) && M.hasCapability("attachments") ? "" : " disabled")
      + '><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg></button>';
    h += '<input type="file" id="terminal-attach-input" accept="image/png,image/jpeg,image/gif,image/webp" style="display:none" multiple>';
    h += '</div>';
    h += '<div class="terminal-input-bottom-right">';
    h += '<span class="terminal-input-hint">Shift+Enter</span>';
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

    // [ESC Renewal] If the ESC direct message stored in localStorage is in the input window
    // Automatic filling (user can edit/transmit). sendInput/commitQueue send to the point of send
    // Because localStorage is clear, there is no permanent residency.
    // If you have an existing text in the input window, please keep the browser form automatically restored.
    // blank one can stand out prepend.
    if (!M.isWorkflowMode) {
      try {
        var savedText = localStorage.getItem("board.term.lastSentText");
        if (savedText) {
          var inputElRestore = document.getElementById("terminal-input");
          if (inputElRestore) {
            inputElRestore.value = inputElRestore.value
              ? savedText + " " + inputElRestore.value
              : savedText;
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
              if (Board.WfWorkRequestRenderer && Board.WfWorkRequestRenderer.detect(M.textBuffer)) {
                Board.WfWorkRequestRenderer.render(M.textBuffer);
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

    // Bind WfWorkRequestRenderer context
    if (Board.WfWorkRequestRenderer) {
      Board.WfWorkRequestRenderer.setContext({
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
      // Main Session Limited: Restore or empty status after status is confirmed.
      // session id can be restored in .last-session-id
      // About Us When the session is live (= stop not), it will be automatically restored.
      // Keep an empty screen before Start, and the past session explicitly expressly in dropdown
      // resume
      if (!M.isWorkflowMode && statusPromise && typeof statusPromise.then === "function") {
        statusPromise.then(function () {
          var sid = Board.state.termSessionId;
          var status = Board.state.termStatus;
          if (Board.debugLog) Board.debugLog('terminal.init.statusReady', {
            sid: sid || null, status: status,
            willLoadHistory: !!(sid && status && status !== "stopped"),
          });
          if (sid && status && status !== "stopped") {
            M.loadHistory(sid);
          } else {
            M.showEmptyState();
          }
        });
      }
    }

    // D5 #5: URL Session Pre-verification Failure Notifications (When the M.outputDiv pre-verification is completed after the renderer)
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
        // archived/missing: The button itself cannot be hidden clicks (reflective use)
      });
    }

    if (inputEl) {
      // The flag during the IME combination — managed by the compositionstart/end event
      inputEl.addEventListener("compositionstart", function () {
        M._isComposing = true;
      });
      inputEl.addEventListener("compositionend", function () {
        M._isComposing = false;
      });

      inputEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          // If IME combination does not intercept Enter.
          // About Us isComposing: Standard (Chrome/Firefox/Edge)
          // M. isComposing: e.isComposing in some browsers such as Safari is false due to case contrast
          if (e.isComposing || M._isComposing) return;

          e.preventDefault();
          if (M.isWorkflowMode) return;

          // Unified all quarters to sendInput.
          // idle inside sendInput: Instant echo + send, busy: enqueueInput (text+image)
          // Ѵ . The image will be queue to the same path.
          M.sendInput();
          return;
        }
        if (e.key !== "Escape") e.stopPropagation();
      });
      inputEl.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 120) + "px";
      });
      // Paste the clipboard image (Ctrl+V) + Paste the path text
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
        // text/plain
        // The path that starts with "/" wrapped with a small quote is blocked to the slash command.
        var text = e.clipboardData.getData("text/plain");
        if (text && M.isFilePath(text)) {
          e.preventDefault();
          M.insertTextAtCursor(inputEl, "'" + text + "'");
        }
        // The general text not the path is entrusted to the default paste operation
      });
    }

    // drag/drop event handler — registered with .terminal-input-card element
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
          label.textContent = "Set the file here";
          overlay.appendChild(label);
          inputCard.appendChild(overlay);
        }
      });

      inputCard.addEventListener("dragover", function (e) {
        e.preventDefault();
        if (!M.hasCapability("attachments")) return;
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
        if (!M.hasCapability("attachments")) {
          M.appendErrorMessage("Current provider does not support attachments");
          return;
        }

        // (0) Split card drop — application/x-board-work-request MIME priority processing
        // dragstart conveyor.js is set and registered in the attached domain by parsing the workRequest JSON.
        // report  report  report  report  report  report  report
        var workRequestJson = "";
        try {
          workRequestJson = dt.getData("application/x-board-work-request");
        } catch (_e) {
          workRequestJson = "";
        }
        if (workRequestJson) {
          var workRequestPayload = null;
          try {
            workRequestPayload = JSON.parse(workRequestJson);
          } catch (_parseErr) {
            workRequestPayload = null;
          }
          if (workRequestPayload && typeof workRequestPayload === "object") {
            // workdir extraction: result.workdir first (conveyor.js dragstart payload norm)
            var workdir = "";
            if (workRequestPayload.result && typeof workRequestPayload.result === "object" && typeof workRequestPayload.result.workdir === "string") {
              workdir = workRequestPayload.result.workdir;
            }

            // workdir regularization: absolute path → literally, relative path → "/" prefix
            // (Board server is same-origin, so use the origin-based path)
            var reportUrl = "";
            if (workdir) {
              var normalized = workdir;
              if (normalized.charAt(0) !== "/") {
                normalized = "/" + normalized;
              }
              if (normalized.charAt(normalized.length - 1) !== "/") {
                normalized = normalized + "/";
              }
              reportUrl = normalized + "report.html";
            }

            // fetch synchronous — failed/null all graceful (M.attachWorkRequest call is only once)
            // 1st: reportUrl (active path) → 404 o'clock .history/ fallback → null when both failed
            if (reportUrl) {
              var historyReportUrl = reportUrl.replace(
                /(\/runs\/)(?!\.history\/)([0-9]{8}-[0-9]{6}\/)/,
                "$1.history/$2"
              );
              fetch(reportUrl, { cache: "no-store" })
                .then(function (res) {
                  if (res && res.ok) return res.text();
                  // 1st 404 (or failure) and fallback URL only try 2nd
                  if (res && res.status === 404 && historyReportUrl !== reportUrl) {
                    return fetch(historyReportUrl, { cache: "no-store" })
                      .then(function (res2) {
                        if (!res2 || !res2.ok) return null;
                        return res2.text();
                      })
                      .catch(function () { return null; });
                  }
                  return null;
                })
                .catch(function () {
                  return null;
                })
                .then(function (reportText) {
                  if (typeof M.attachWorkRequest === "function") {
                    M.attachWorkRequest(workRequestPayload, reportText || null);
                  }
                });
            } else if (typeof M.attachWorkRequest === "function") {
              M.attachWorkRequest(workRequestPayload, null);
            }
            return;
          }
        }

        // 0b) Memory card drop — application/x-board-memory MIME processing
        // dragstart when memory-core.js is set {name, category} JSON parsing.
        // The text is not included in the attachment (user intention = path only, assign read),
        // fetchMemoryFile + parseMemoryFrontmatter
        var memoryJson = "";
        try {
          memoryJson = dt.getData("application/x-board-memory");
        } catch (_memErr) {
          memoryJson = "";
        }
        if (memoryJson) {
          var memPayload = null;
          try {
            memPayload = JSON.parse(memoryJson);
          } catch (_memParseErr) {
            memPayload = null;
          }
          if (memPayload && memPayload.name && typeof M.attachMemory === "function") {
            M.attachMemory(memPayload);
            return;
          }
        }

        // (a) File drop — Images: Added to attachedImages + Thumbnails / Images: File card + File name insertion
        if (dt.files && dt.files.length > 0) {
          var names = [];
          for (var fi = 0; fi < dt.files.length; fi++) {
            var droppedFile = dt.files[fi];
            names.push(droppedFile.name);
            if (ALLOWED_MIME.indexOf(droppedFile.type) !== -1) {
              // Image file: Reuse existing M.attachImage() path (Thumbnail Rendering)
              M.attachImage(droppedFile);
            } else {
              // Non-Image: rendering file card after registering with an attachedFiles
              M.attachedFiles.push({ file: droppedFile, name: droppedFile.name, size: droppedFile.size, type: droppedFile.type });
              M.renderFilePreview();
              M.insertTextAtCursor(targetInput, droppedFile.name + (fi < dt.files.length - 1 ? "\n" : ""));
            }
          }
          return;
        }

        // (b) text/plain This path pattern inserts the path to textarea
        // The path that starts with "/" wrapped with a small quote is blocked to the slash command.
        var dropText = dt.getData("text/plain");
        if (dropText && M.isFilePath(dropText)) {
          M.insertTextAtCursor(targetInput, "'" + dropText + "'");
          return;
        }
        // (c) both or ignored (Sinario C, Chromium CF HDROP bug)
      });
    }

    // Attachment button and hidden file input event
    var attachBtn = document.getElementById("terminal-attach-btn");
    var attachInput = document.getElementById("terminal-attach-input");
    if (attachBtn && attachInput) {
      attachBtn.addEventListener("click", function () {
        if (!M.hasCapability("attachments")) {
          M.appendErrorMessage("Current provider does not support attachments");
          return;
        }
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

    // Memory shortcut: quarterly based on session status
    //  - message 0 (first/resume right after): memory request (id: memory.load)
    //  - Message 1+ (Intermediate): Current Session Content Memory (id: memory.persist)
    // .agent-factory/board/config/quick-prompts.json
    // When fetch fails, use the default pollen text — keeping the operation even when offline or missing files.
    var FALLBACK_MEMORY_LOAD = "Memory Load";
    var FALLBACK_MEMORY_PERSIST = "Please refresh the core contents of this session (crystal, learning, yishu, rule) to memory. categorized as appropriate type(user/feedback/project/reference), and reinforce when it is overlapsed with existing notes.";
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
            var closedSid = closeTab.dataset.session;
            var wasActive = closeTab.classList.contains("active");
            closeTab.parentNode.removeChild(closeTab);
            // WR-516 — localStorage Remove ID from single source. Close = DOM + simultaneously.
            // Resurrection Resurrection 0 (lasting user’s explicitly close)
            if (closedSid && Board.workflowTabStorage && Board.workflowTabStorage.remove) {
              Board.workflowTabStorage.remove(closedSid);
            }
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

    // onSwitch Hook: M.switchSession() Updated tab bar active status when calling
    Board.sessionSwitcher._onSwitch = function (newSessionId, _prevId) {
      if (Board.sessionSwitcher.setActiveTab) {
        Board.sessionSwitcher.setActiveTab(newSessionId);
      }
    };

    // URL ?session= Initial session tab processing based on query parameters
    if (M._initialQuerySession) {
      // Add an initial session to the tab bar (workflow tab)
      if (Board.sessionSwitcher.addTab) {
        var initLabel = M._initialQuerySession.replace(/^wf-/, "").replace(/-\d+$/, "");
        Board.sessionSwitcher.addTab(M._initialQuerySession, initLabel, "running");
      }
      // Enable Tabs (Inclusion Sessions Display With Active Tabs)
      if (Board.sessionSwitcher.setActiveTab) {
        Board.sessionSwitcher.setActiveTab(M._initialQuerySession);
      }
      // Remove the URL to terminal.html
      try {
        history.replaceState(null, "", "terminal.html");
      } catch (e) {}
    }

    // WR-516 — restore workflow tabs from localStorage single source.
    // The main tab blocks the Helper add + bypass the main flow (M. initialQuerySession also duplicate skip).
    // The ID without server registry is displayed as 'stopped' (great) — only removed by close button.
    if (Board.workflowTabStorage && Board.workflowTabStorage.get) {
      var storedIds = Board.workflowTabStorage.get();
      storedIds.forEach(function (sid) {
        if (!sid || sid === "main") return;
        if (sid === M._initialQuerySession) return; // Added already in the above branch
        if (Board.sessionSwitcher.addTab) {
          var label = sid.replace(/^wf-/, "").replace(/-\d+$/, "");
          Board.sessionSwitcher.addTab(sid, label, "stopped");
        }
        // synchronous status synthesis — /api/v2/sessions/<id> response status to dot update.
        // No response missing / network failure / 404 = 'stopped' gray (user express decision).
        if (Board.productionLineWorkflow && Board.productionLineWorkflow.fetchSession) {
          Board.productionLineWorkflow.fetchSession(sid).then(function (meta) {
            if (!meta) return; // 404 / null
            var st = (meta.status === "running" || meta.status === "idle")
              ? "running" : "stopped";
            if (Board.sessionSwitcher.setTabStatus) {
              Board.sessionSwitcher.setTabStatus(sid, st);
            }
          }).catch(function () { /* Network failure → Maintenance */ });
        }
      });
    }

    Board.workflowSessions.refresh(M.workflowSessionId, M.isWorkflowMode);
    setInterval(function () {
      Board.workflowSessions.refresh(M.workflowSessionId, M.isWorkflowMode);
    }, 5000);

    // Fetch branch on load — SSE git branch event (core/sse.js) is responsible for follow-up updates.
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

  // Board.sessionSwitcher Public API ──
  // M.renderTerminal() registers at the IIFE level to be available before calling.
  // The UI tab method (addTab, removeTab, etc.) is added within the M.renderTerminal().
  Board.sessionSwitcher = Board.sessionSwitcher || {};

  /**
   * Session Conversion Public API.
   * @param {string} sessionId - "main" or "wf-WR-NNN-..."
   * @returns {Promise<void>}
   */
  Board.sessionSwitcher.switchSession = function (sessionId) {
    return M.switchSession(sessionId);
  };

  /**
   * returns the current active session ID.
   * @returns {string}
   */
  Board.sessionSwitcher.getCurrentSession = function () {
    return M._activeSessionId;
  };

  /**
   * Returns the registered session list.
   * @returns {Array<{id: string, isWorkflow: boolean, status: string, model: string}>}
   */
  Board.sessionSwitcher.getSessionList = function () {
    return Object.keys(M._sessionMap).map(function (id) {
      var e = M._sessionMap[id];
      return { id: e.id, isWorkflow: e.isWorkflow, status: e.status, model: e.model };
    });
  };

  /**
   * Register a new session. If you have already existed, it is ignored.
   * @param {string} sessionId
   * @param {object} [opts] - initial state override (status, model, etc.)
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
   * Remove session from the list. If the current active session is switched to main, remove it.
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
   * W01 Tab-Bar UI Switching Hook. Override from W01 to use tab activation.
   * @param {string} newSessionId
   * @param {string} prevSessionId
   */
  Board.sessionSwitcher._onSwitch = Board.sessionSwitcher._onSwitch || function (_newId, _prevId) {};
})();
