/**
 * @module terminal/session-switcher
 * Split from terminal.js. Functions attach to Board._term (M) namespace.
 */
"use strict";

(function () {
  var esc = Board.util.esc;
  var M = (Board._term = Board._term || {});

  // ── Session Switcher Engine ──
  //
  // When switching session, outputDiv self-propelled cloneNode to array reference without cloneNode
  // About Us nodes are alive after detach and they also maintain event listeners.
  // It is free from reproduction cost (O(n×depth) and delegation regression (release).

  M._saveCurrentSession = function() {
    var entry = M._sessionMap[M._activeSessionId];
    if (!entry) {
      entry = M._createSessionEntry(M._activeSessionId);
      M._sessionMap[M._activeSessionId] = entry;
    }

    if (M.outputDiv) {
      entry.outputNodes = [];
      while (M.outputDiv.firstChild) {
        var node = M.outputDiv.firstChild;
        M.outputDiv.removeChild(node);
        entry.outputNodes.push(node);
      }
    }

    entry.cost = M.sessionCost;
    entry.tokens = { input: M.sessionTokens.input, output: M.sessionTokens.output };
    entry.model = M.sessionModel;
    entry.status = Board.state.termStatus;
    entry.inputQueue = M.inputQueue.slice();
  };

  /**
   * Restores the state of the target session with active variables.
   * @param {string} targetId
   */
  M._restoreSession = function(targetId) {
    var entry = M._sessionMap[targetId];
    if (!entry) return;

    // Session mode variable update
    if (targetId === "main") {
      M.workflowSessionId = null;
      M.isWorkflowMode = false;
    } else {
      M.workflowSessionId = targetId;
      M.isWorkflowMode = true;
    }

    // Indication/Remove Immediately Reflecting (Motivation Processing Before Calling M.updateControlBar)
    var inputCardEl = document.querySelector(".terminal-input-card");
    if (inputCardEl) {
      if (M.isWorkflowMode) {
        inputCardEl.classList.add("wf-input-hidden");
      } else {
        inputCardEl.classList.remove("wf-input-hidden");
      }
    }

    // Restores status variables
    M.sessionCost = entry.cost;
    M.sessionTokens = { input: entry.tokens.input, output: entry.tokens.output };
    M.sessionModel = entry.model;
    Board.state.setTermStatus(entry.status);
    Board.state.termSessionId = targetId === "main" ? null : targetId;

    // M.inputQueueue rotation (replacing contents only while maintaining participation)
    M.inputQueue.length = 0;
    for (var qi = 0; qi < entry.inputQueue.length; qi++) {
      M.inputQueue.push(entry.inputQueue[qi]);
    }

    // Reset shared module-scoped state; otherwise new session events
    // route to prior session's DOM references (wf panel + tool buffers).
    if (Board.WorkflowRenderer && Board.WorkflowRenderer.reset) {
      Board.WorkflowRenderer.reset();
    }
    M.stopSpinner();
    M.currentToolBox = null;
    M.toolBoxMap = {};
    M.currentToolName = null;
    M.textBuffer = "";
    M.toolInputBuffer = "";
    M.receivedChunks = false;
    M.currentWorkflowToolCard = null;

    if (M.outputDiv) {
      while (M.outputDiv.firstChild) {
        M.outputDiv.removeChild(M.outputDiv.firstChild);
      }
      if (entry.outputNodes && entry.outputNodes.length > 0) {
        for (var ni = 0; ni < entry.outputNodes.length; ni++) {
          M.outputDiv.appendChild(entry.outputNodes[ni]);
        }
        M.outputDiv.scrollTop = M.outputDiv.scrollHeight;
      }

      // WorkflowRenderer.reset()
      // Reconstructive. routing to the exact panel from the first event to perform before connectSSE.
      if (Board.WorkflowRenderer && Board.WorkflowRenderer.rebuildStepPanelsFromDom) {
        Board.WorkflowRenderer.rebuildStepPanelsFromDom(M.outputDiv);
      }
    }
  };

  /**
   * Convert Sessions.
   * (a) Save current session status → (b) Restore target session → (c) SSE Reconnect → (d) Renew status bar
   *
   * @param {string} targetSessionId - Session ID to switch ("main" or "wf-T-NNN-...")
   * @returns {Promise<void>}
   */
  M.switchSession = function(targetSessionId) {
    if (!targetSessionId) return Promise.resolve();
    if (targetSessionId === M._activeSessionId) return Promise.resolve();

    // If the target session is not mapped
    if (!M._sessionMap[targetSessionId]) {
      M._sessionMap[targetSessionId] = M._createSessionEntry(targetSessionId);
    }

    // 1. FAQ Save Current Sessions
    M._saveCurrentSession();

    // 2. Change Activity Session ID
    var prevId = M._activeSessionId;
    M._activeSessionId = targetSessionId;

    // 3. FAQs (T-383 Phase 2 / VUL-1 / S4)
    // restoreSession calls disconnectSSE prior to restoration
    // prev-session SSE event is loaded into the DOM that outputDiv is reconfigured
    // block race window.
    // AdoptLastEventIdForSession / resetEventLastId with disconnectSSE
    // logically tied (the last-event-id per session first restored
    // Break the connection from-id reconnection means conservation) to move together.
    if (Board.session) {
      if (Board.session.adoptLastEventIdForSession) {
        Board.session.adoptLastEventIdForSession(targetSessionId);
      } else if (Board.session.resetLastEventId) {
        Board.session.resetLastEventId();
      }
      Board.session.disconnectSSE();
    }

    // 4. FAQs Restore Target Session Status (M.outputDiv, variable)
    M._restoreSession(targetSessionId);

    // 5. FAQs SSE Reconnect: Connect to a new session DOM after restoration
    // Workflow Session REST /terminal/workflow/history before SSE subscription
    // Inject the event first (T-391 standard path after removing ringbuckle). Main Session
    // RestoreSession is restored, so there is no need for separate history injection.
    //
    // T-495 P2 — Production-line session is separate entry point (Board.session.startProductionLineSession)
    // to branch. v1 SSE channel (/terminal/workflow/events) and insulating.
    if (Board.session) {
      var isWfTarget = targetSessionId !== "main" &&
        targetSessionId.indexOf("wf-") === 0;
      var isProductionLineTarget = isWfTarget &&
        Board.productionLineWorkflow && Board.productionLineWorkflow.isProductionLineSessionId &&
        Board.productionLineWorkflow.isProductionLineSessionId(targetSessionId);

      if (isProductionLineTarget && Board.session.startProductionLineSession) {
        // Board.productionLineWorkflow.subscribe Single entry point.
        Board.session.startProductionLineSession(targetSessionId);
      } else {
        var historyChain = isWfTarget && Board.session.injectRestHistory
          ? Board.session.injectRestHistory(targetSessionId)
          : Promise.resolve();
        historyChain
          .then(function () { return Board.session.connectSSEReady(); })
          .then(function () { Board.session.fetchStatus(); })
          .catch(function () {});
      }
    }

    // 6. phase timeline display/hidden
    var timelineBar = document.getElementById("wf-timeline-bar");
    if (timelineBar) {
      timelineBar.style.display = targetSessionId === "main" ? "none" : "";
    }

    // 7. OEM UI update
    M.updateControlBar();

    // Updated Active Tabs ( UI Hooks implemented on W01)
    if (Board.sessionSwitcher && Board.sessionSwitcher._onSwitch) {
      Board.sessionSwitcher._onSwitch(targetSessionId, prevId);
    }

    return Promise.resolve();
  };

})();
