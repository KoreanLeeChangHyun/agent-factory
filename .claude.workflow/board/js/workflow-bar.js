/**
 * @module workflow-bar
 *
 * WorkflowRenderer (banner parser + state machine) and phaseTimeline (DOM renderer).
 *
 * Parses Bash tool_use_result text for workflow banner patterns emitted by
 * flow-claude, flow-init, flow-step, flow-phase, and flow-finish scripts.
 * phaseTimeline renders the timeline bar DOM below .terminal-session-bar.
 *
 * Depends on: common.js (Board namespace)
 * Registers:  Board.WorkflowRenderer, Board.phaseTimeline
 */
"use strict";

(function () {

  // ── ANSI strip utility ──

  var ANSI_STRIP_RE = /\x1b\[[0-9;]*m/g;
  function stripAnsi(text) {
    return (text || "").replace(ANSI_STRIP_RE, "");
  }

  // ── WorkflowRenderer namespace ──

  var WorkflowRenderer = (function () {

    // ── Pattern constants ──

    var P = {
      workflowBoxTop:    /╔[═]+╗/,
      workflowStartCmd:  /(?:║\s+▶\s+(\S+)|\[WORKFLOW\]\s+(\S+))/,
      workflowEnd:       /(?:║\s+\[OK\]\s+(\S+)\s+·\s+(.+?)(?:\s+\((\w+)\))?$|\[OK\]\s+(\S+)\s+·\s+(.+?)(?:\s+\((\w+)\))?$)/,
      endBorder:         /^[═]{10,}$/,
      init:              /(?:║\s+INIT:\s+(.+)$|\[INIT\]\s+(.+)$)/,
      initWorkDir:       /(?:║\s+(\.claude\.workflow\/workflow\/[^\s]+)$|^(\.claude\.workflow\/workflow\/[^\s]+)$)/,
      stepStart:         /(?:║\s+\[●[^\]]*\]\s+(PLAN|WORK|REPORT|DONE)|\[STEP\]\s+(PLAN|WORK|REPORT|DONE)(?:\s+-\s+[^0-9]|$))/,
      stepEnd:           /(?:║\s+\[●[^\]]*\]\s+(PLAN|WORK|REPORT|DONE)\s+-\s+(.+)$|\[STEP\]\s+(PLAN|WORK|REPORT|DONE)\s+-\s+(\d{4}.+)$)/,
      artifactLine:      /(?:║\s+(\.claude\.workflow\/workflow\/[^\s]+)$|^(\.claude\.workflow\/workflow\/[^\s]+)$)/,
      stepOk:            /(?:║\s+\[OK\]\s+(\S+)$|\[OK\]\s+(\S+)$)/,
      stepAsk:           /(?:║\s+\[ASK\]\s+(\S+)$|\[ASK\]\s+(\S+)$)/,
      phase:             /(?:║\s+STATE:\s+Phase\s+(\d+)\s+(sequential|parallel)|\[PHASE\]\s+(\d+)\s+(sequential|parallel))/,
      phaseAgents:       /(?:║\s+>>\s+([^\[]+?)(?:\s+\[([^\]]+)\])?$|^>>\s+([^\[]+?)(?:\s+\[([^\]]+)\])?$)/,
      finishDone:        /(?:║\s+DONE:\s+워크플로우\s+(완료|실패)|\[DONE\]\s+워크플로우\s+(완료|실패))/,
      finishKey:         /(?:║\s+(\d{8}-\d{6})$|^(\d{8}-\d{6})$)/,
      stateChange:       /\[STATE\]\s+단계\s+변경/,
      stateTransition:   /^>>\s+(\w+)\s*->\s*(\w+)$/,
      taskStatus:        /AGENT_(DISPATCH|RETURN):\s+taskId=(\w+)(?:\s+status=(\w+))?/,
      fail:              /^FAIL$/
    };

    // ── Step Panel constants ──

    var STEP_COLORS = {
      unknown: "#858585",
      init:    "#858585",
      plan:    "#569cd6",
      work:    "#D97757",
      report:  "#c586c0",
      done:    "#4ec9b0",
      failed:  "#f48771"
    };

    var STEP_STATUS_LABELS = {
      active: "\uC9C4\uD589 \uC911",
      done:   "\uC644\uB8CC"
    };

    // ── Default state ──

    var DEFAULT_STATE = {
      command:      "",
      workId:       "",
      title:        "",
      workDir:      "",
      currentStep:  "init",
      currentPhase: -1,
      phases:       [],
      artifacts:    [],
      artifactPaths: {},
      status:       "running",
      error:        undefined,
      stepTimestamps: {
        init:   { start: null, end: null },
        plan:   { start: null, end: null },
        work:   { start: null, end: null },
        report: { start: null, end: null },
        done:   { start: null, end: null }
      },
      agentStatuses: {}
    };

    // ── Internal mutable state ──

    var _state = {};

    /** @type {HTMLElement|null} Current active step panel DOM element */
    var _activeStepPanel = null;

    /** @type {Object<string, HTMLElement>} Map of step name -> panel DOM */
    var _stepPanels = {};

    var _pendingInit = false;
    var _pendingInitTitle = "";
    var _pendingStepEnd = false;
    var _pendingStepEndName = "";
    var _pendingStepEndTs = "";
    var _pendingPhase = false;
    var _pendingPhaseN = -1;
    var _pendingPhaseMode = "";
    var _inBox = false;
    var _boxHasCmd = false;
    var _pendingFinish = false;
    var _pendingFinishResult = "";
    var _pendingStateChange = false;

    function _reset(command) {
      // Re-entry guard: once a workflow is running (command set & past init),
      // stray [WORKFLOW] tokens in subtool stdout (e.g. flow-update echoes)
      // must NOT tear down the panel FSM. Only allow a full reset when no
      // workflow is active or we are still in init.
      if (_state && _state.command && _state.currentStep && _state.currentStep !== "init") {
        return;
      }

      // Preserve any INIT panel already created by _insertToCurrentPanel
      // fallback before the [WORKFLOW] banner parsed. Otherwise a premature
      // INIT panel (holding workflow-start assistant text) becomes orphaned
      // and a second INIT panel is spawned for subsequent tool events.
      var preservedPanels = _stepPanels;
      var preserveInit = !!(preservedPanels && preservedPanels.init);

      _state = {
        command:      command || "",
        workId:       "",
        title:        "",
        workDir:      "",
        currentStep:  "init",
        currentPhase: -1,
        phases:       [],
        artifacts:    [],
        artifactPaths: {},
        status:       "running",
        error:        undefined,
        stepTimestamps: {
          init:   { start: null, end: null },
          plan:   { start: null, end: null },
          work:   { start: null, end: null },
          report: { start: null, end: null },
          done:   { start: null, end: null }
        },
        agentStatuses: {}
      };

      if (preserveInit) {
        _stepPanels = { init: preservedPanels.init };
        _activeStepPanel = preservedPanels.init;
      } else {
        _stepPanels = {};
        _activeStepPanel = null;
      }
      _clearParserFlags();
    }

    function _clearParserFlags() {
      _pendingInit = false;
      _pendingInitTitle = "";
      _pendingStepEnd = false;
      _pendingStepEndName = "";
      _pendingStepEndTs = "";
      _pendingPhase = false;
      _pendingPhaseN = -1;
      _pendingPhaseMode = "";
      _inBox = false;
      _boxHasCmd = false;
      _pendingFinish = false;
      _pendingFinishResult = "";
      _pendingStateChange = false;
    }

    function _setInit(title, workDir) {
      _state.title = title;
      _state.workDir = workDir;
      _state.currentStep = "init";
    }

    function _setStep(stepName) {
      var prevStep = _state.currentStep;
      var newStep = stepName.toLowerCase();

      // Record timestamps for step transitions
      var now = Date.now();
      if (_state.stepTimestamps) {
        // End previous step if not yet ended
        if (prevStep && prevStep !== newStep && _state.stepTimestamps[prevStep]) {
          if (!_state.stepTimestamps[prevStep].end) {
            _state.stepTimestamps[prevStep].end = now;
          }
        }
        // Start new step if not yet started
        if (_state.stepTimestamps[newStep] && !_state.stepTimestamps[newStep].start) {
          _state.stepTimestamps[newStep].start = now;
        }
      }

      _state.currentStep = newStep;

      // Mark previous step panel as done
      if (prevStep && prevStep !== _state.currentStep && _stepPanels[prevStep]) {
        var prevPanel = _stepPanels[prevStep];
        prevPanel.setAttribute("data-status", "done");
        var prevStatusEl = prevPanel.querySelector(".wf-step-panel-status");
        if (prevStatusEl) {
          prevStatusEl.setAttribute("data-status", "done");
          prevStatusEl.textContent = STEP_STATUS_LABELS.done;
        }
        var prevIcon = prevPanel.querySelector(".wf-step-panel-icon");
        if (prevIcon) prevIcon.textContent = "\u2713";
      }

      // Create or activate panel for new step
      _activeStepPanel = _getOrCreateStepPanel(_state.currentStep);
    }

    function _setPhase(n, mode, agents, taskIds) {
      _state.phases.push({
        n:       n,
        agents:  agents  || [],
        taskIds: taskIds || [],
        mode:    mode
      });
      _state.currentPhase = n;

      // Initialize agent statuses as running
      var agentList = agents || [];
      for (var i = 0; i < agentList.length; i++) {
        _state.agentStatuses[agentList[i]] = "running";
      }
    }

    // ── Step Panel DOM management ──

    function _getOrCreateStepPanel(stepName) {
      if (_stepPanels[stepName]) return _stepPanels[stepName];

      var outputDiv = document.getElementById("terminal-output");
      if (!outputDiv) return null;

      var panel = document.createElement("div");
      panel.className = "wf-step-panel";
      panel.setAttribute("data-step", stepName);
      panel.setAttribute("data-status", "active");

      var color = STEP_COLORS[stepName] || STEP_COLORS.unknown;

      var header = document.createElement("div");
      header.className = "wf-step-panel-header";
      header.style.borderLeftColor = color;

      var icon = document.createElement("span");
      icon.className = "wf-step-panel-icon";
      icon.textContent = "\u25CF";
      icon.style.color = color;
      header.appendChild(icon);

      var name = document.createElement("span");
      name.className = "wf-step-panel-name";
      name.textContent = stepName.toUpperCase();
      header.appendChild(name);

      var status = document.createElement("span");
      status.className = "wf-step-panel-status";
      status.setAttribute("data-status", "active");
      status.textContent = STEP_STATUS_LABELS.active;
      header.appendChild(status);

      panel.appendChild(header);

      var body = document.createElement("div");
      body.className = "wf-step-panel-body";
      panel.appendChild(body);

      // Append to output with scroll
      var follow = Board._term && Board._term.isNearBottom ? Board._term.isNearBottom(outputDiv) : true;
      outputDiv.appendChild(panel);
      if (Board._term && Board._term.scrollToBottomIfFollowing) {
        Board._term.scrollToBottomIfFollowing(outputDiv, follow);
      }

      _stepPanels[stepName] = panel;
      return panel;
    }

    function _insertToCurrentPanel(html) {
      var panel = _activeStepPanel;
      if (!panel) {
        // Fallback: create panel for current step if needed
        panel = _getOrCreateStepPanel(_state.currentStep || "init");
        _activeStepPanel = panel;
      }
      if (!panel) return null;

      var body = panel.querySelector(".wf-step-panel-body");
      if (!body) return null;

      var outputDiv = document.getElementById("terminal-output");
      var follow = Board._term && Board._term.isNearBottom ? Board._term.isNearBottom(outputDiv) : true;

      // MAX_OUTPUT_NODES guard for panel body
      while (body.childNodes.length >= 500) {
        body.removeChild(body.firstChild);
      }

      var container = document.createElement("div");
      container.innerHTML = html;
      body.appendChild(container);

      if (outputDiv && Board._term && Board._term.scrollToBottomIfFollowing) {
        Board._term.scrollToBottomIfFollowing(outputDiv, follow);
      }

      return container;
    }

    function _appendDomToCurrentPanel(domEl) {
      var panel = _activeStepPanel;
      if (!panel) {
        panel = _getOrCreateStepPanel(_state.currentStep || "init");
        _activeStepPanel = panel;
      }
      if (!panel) return;

      var body = panel.querySelector(".wf-step-panel-body");
      if (!body) return;

      var outputDiv = document.getElementById("terminal-output");
      var follow = Board._term && Board._term.isNearBottom ? Board._term.isNearBottom(outputDiv) : true;

      while (body.childNodes.length >= 500) {
        body.removeChild(body.firstChild);
      }

      body.appendChild(domEl);

      if (outputDiv && Board._term && Board._term.scrollToBottomIfFollowing) {
        Board._term.scrollToBottomIfFollowing(outputDiv, follow);
      }
    }

    function _addArtifact(path) {
      if (!path) return;
      if (_state.artifactPaths[path]) return;
      _state.artifactPaths[path] = true;
      var label = path.split("/").pop();
      var type = "other";
      if (/plan\.md$/.test(path))   type = "plan";
      else if (/report\.md$/.test(path)) type = "report";
      else if (/work\//.test(path)) type = "work";
      _state.artifacts.push({
        type:  type,
        path:  path,
        at:    new Date().toISOString(),
        label: label
      });
    }

    function _setWorkflowEnd(workId, title) {
      if (workId) _state.workId = workId;
      if (title)  _state.title  = title;
    }

    function _complete() {
      var now = Date.now();

      // End current step timestamp
      var prev = _state.currentStep;
      if (prev && _state.stepTimestamps && _state.stepTimestamps[prev]) {
        if (!_state.stepTimestamps[prev].end) {
          _state.stepTimestamps[prev].end = now;
        }
      }

      // Mark done step timestamp
      if (_state.stepTimestamps && _state.stepTimestamps.done) {
        _state.stepTimestamps.done.start = now;
        _state.stepTimestamps.done.end = now;
      }

      // Mark all agents as completed
      var keys = Object.keys(_state.agentStatuses);
      for (var i = 0; i < keys.length; i++) {
        _state.agentStatuses[keys[i]] = "completed";
      }

      _state.status      = "done";
      _state.currentStep = "done";
    }

    function _fail(msg) {
      var now = Date.now();

      // End current step timestamp
      var prev = _state.currentStep;
      if (prev && _state.stepTimestamps && _state.stepTimestamps[prev]) {
        if (!_state.stepTimestamps[prev].end) {
          _state.stepTimestamps[prev].end = now;
        }
      }

      // Mark all agents as completed on failure
      var keys = Object.keys(_state.agentStatuses);
      for (var i = 0; i < keys.length; i++) {
        _state.agentStatuses[keys[i]] = "completed";
      }

      _state.status      = "failed";
      _state.currentStep = "failed";
      _state.error       = msg || "FAIL";
    }

    // ── OR-pattern capture helper ──
    // For patterns like /(?:old_group1|new_group2)/, returns first defined capture.
    function _pick(m /* match array */) {
      for (var i = 1; i < m.length; i++) {
        if (m[i] !== undefined) return m[i];
      }
      return "";
    }

    // Returns array of first N defined captures from OR-pattern match.
    function _pickN(m, n) {
      var result = [];
      for (var i = 1; i < m.length && result.length < n; i++) {
        if (m[i] !== undefined) result.push(m[i]);
      }
      return result;
    }

    // ── Per-line pattern matching ──

    function _parseLine(line) {
      var m;
      var vals;

      // ── [STATE] 단계 변경 (2-line sequence, line 1) ──
      if (P.stateChange.test(line)) {
        _pendingStateChange = true;
        return true;
      }

      // ── >> FROM -> TO (2-line sequence, line 2) ──
      if (_pendingStateChange && (m = P.stateTransition.exec(line))) {
        _pendingStateChange = false;
        var toStep = m[2];
        _setStep(toStep);
        return true;
      }

      // ── AGENT_DISPATCH / AGENT_RETURN ──
      if ((m = P.taskStatus.exec(line))) {
        var action = m[1];
        var taskId = m[2];
        var taskSt = m[3] || "";
        if (action === "DISPATCH") {
          _state.agentStatuses[taskId] = "running";
        } else if (action === "RETURN") {
          _state.agentStatuses[taskId] = "completed";
        }
        return true;
      }

      if (P.workflowBoxTop.test(line)) {
        _inBox    = true;
        _boxHasCmd = false;
        return true;
      }

      if (P.endBorder.test(line)) {
        _pendingStepEnd = false;
        return true;
      }

      if (_inBox && (m = P.workflowStartCmd.exec(line))) {
        _boxHasCmd = true;
        _inBox     = false;
        _reset(_pick(m));
        return true;
      }

      // [WORKFLOW] without box — new format
      if (!_inBox && (m = P.workflowStartCmd.exec(line))) {
        _reset(_pick(m));
        return true;
      }

      if (_inBox && !_boxHasCmd && (m = P.stepStart.exec(line))) {
        _inBox = false;
        _setStep(_pick(m));
        return true;
      }

      if (/╚[═]+╝/.test(line)) {
        _inBox     = false;
        _boxHasCmd = false;
        return true;
      }

      if ((m = P.workflowEnd.exec(line))) {
        vals = _pickN(m, 3);
        _setWorkflowEnd(vals[0], (vals[1] || "").trim());
        return true;
      }

      if ((m = P.init.exec(line))) {
        _pendingInit      = true;
        _pendingInitTitle = _pick(m).trim();
        _pendingStepEnd = false;
        _pendingPhase   = false;
        return true;
      }

      if (_pendingInit && (m = P.initWorkDir.exec(line))) {
        _setInit(_pendingInitTitle, _pick(m).trim());
        _pendingInit      = false;
        _pendingInitTitle = "";
        return true;
      }

      // stepEnd must be checked before stepStart (stepEnd is more specific)
      if ((m = P.stepEnd.exec(line))) {
        vals = _pickN(m, 2);
        _pendingStepEnd     = true;
        _pendingStepEndName = vals[0];
        _pendingStepEndTs   = (vals[1] || "").trim();
        _setStep(vals[0]);
        return true;
      }

      // [STEP] without box — new format (stepStart only, not stepEnd)
      if (!_inBox && (m = P.stepStart.exec(line))) {
        _setStep(_pick(m));
        return true;
      }

      if ((m = P.artifactLine.exec(line))) {
        _addArtifact(_pick(m).trim());
        return true;
      }

      if (_pendingStepEnd && (P.stepOk.test(line) || P.stepAsk.test(line))) {
        _pendingStepEnd = false;
        return true;
      }

      if ((m = P.phase.exec(line))) {
        vals = _pickN(m, 2);
        _pendingPhase    = true;
        _pendingPhaseN   = parseInt(vals[0], 10);
        _pendingPhaseMode = vals[1];
        return true;
      }

      if (_pendingPhase && (m = P.phaseAgents.exec(line))) {
        vals = _pickN(m, 2);
        var agentsRaw = (vals[0] || "").trim();
        var taskIdsRaw = vals[1] ? vals[1].trim() : "";
        var agents  = agentsRaw  ? agentsRaw.split(/[\s,]+/).filter(Boolean) : [];
        var taskIds = taskIdsRaw ? taskIdsRaw.split(/[\s,]+/).filter(Boolean) : [];
        _setPhase(_pendingPhaseN, _pendingPhaseMode, agents, taskIds);
        _pendingPhase     = false;
        _pendingPhaseN    = -1;
        _pendingPhaseMode = "";
        return true;
      }

      if ((m = P.finishDone.exec(line))) {
        _pendingFinish       = true;
        _pendingFinishResult = _pick(m);
        return true;
      }

      if (_pendingFinish && (m = P.finishKey.exec(line))) {
        _pendingFinish = false;
        var registryKey = _pick(m);
        if (_pendingFinishResult === "완료") {
          _complete();
        } else {
          _fail("워크플로우 실패 (" + registryKey + ")");
        }
        _pendingFinishResult = "";
        return true;
      }

      if (P.fail.test(line)) {
        _fail("FAIL");
        return true;
      }

      return false;
    }

    // ── Public API ──

    return {
      get state() { return _state; },
      patterns: P,

      tap: function (text) {
        var stripped = stripAnsi(text);
        var lines    = stripped.split("\n");
        var consumed = false;

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim();
          if (line && _parseLine(line)) {
            consumed = true;
          }
        }

        return consumed;
      },

      reset: function () {
        _reset();
      },

      /**
       * Get or create a step panel DOM for the given step name.
       * @param {string} stepName
       * @returns {HTMLElement|null}
       */
      getOrCreateStepPanel: function (stepName) {
        return _getOrCreateStepPanel(stepName);
      },

      /**
       * Insert HTML content into the current active step panel's body.
       * @param {string} html
       * @returns {HTMLElement|null} the container element or null
       */
      insertToCurrentPanel: function (html) {
        return _insertToCurrentPanel(html);
      },

      /**
       * Append a DOM element into the current active step panel's body.
       * @param {HTMLElement} domEl
       */
      appendDomToCurrentPanel: function (domEl) {
        _appendDomToCurrentPanel(domEl);
      },

      /**
       * Returns the current active step panel DOM element.
       * @returns {HTMLElement|null}
       */
      getActiveStepPanel: function () {
        return _activeStepPanel;
      }
    };
  })();

  // ── phaseTimeline DOM Renderer ──

  var phaseTimeline = (function () {

    // ── Timer state (module-scoped within phaseTimeline IIFE) ──
    var _timerId = null;

    /**
     * Format milliseconds into a human-readable duration string.
     * < 60s  => "Xs"
     * >= 60s => "Xm Ys"
     * >= 60m => "Xh Ym"
     */
    function _formatDuration(ms) {
      if (ms < 0) ms = 0;
      var totalSec = Math.floor(ms / 1000);
      if (totalSec < 60) {
        return totalSec + "s";
      }
      var totalMin = Math.floor(totalSec / 60);
      var sec = totalSec % 60;
      if (totalMin < 60) {
        return totalMin + "m " + sec + "s";
      }
      var hours = Math.floor(totalMin / 60);
      var min = totalMin % 60;
      return hours + "h " + min + "m";
    }

    /**
     * Update all active step time badges in the timeline bar via DOM query.
     * Reads data-start attribute and computes elapsed time from Date.now().
     */
    function _tickActiveTimers() {
      var bar = document.getElementById("wf-timeline-bar");
      if (!bar) return;

      var activeBadges = bar.querySelectorAll(".wf-step-time.active");
      var now = Date.now();
      for (var i = 0; i < activeBadges.length; i++) {
        var badge = activeBadges[i];
        var startStr = badge.getAttribute("data-start");
        if (startStr) {
          var elapsed = now - parseInt(startStr, 10);
          badge.textContent = _formatDuration(elapsed);
        }
      }
    }

    /**
     * Start the 1-second interval timer for updating active step time badges.
     * Clears any existing timer first to prevent duplicates.
     */
    function _startTimer() {
      _stopTimer();
      _timerId = setInterval(_tickActiveTimers, 1000);
    }

    /**
     * Stop the interval timer if running.
     */
    function _stopTimer() {
      if (_timerId !== null) {
        clearInterval(_timerId);
        _timerId = null;
      }
    }

    function _getOrCreateBar() {
      var existing = document.getElementById("wf-timeline-bar");
      if (existing) return existing;

      var sessionBar = document.querySelector(".terminal-session-bar");
      if (!sessionBar) return null;

      var bar = document.createElement("div");
      bar.className = "wf-timeline-bar";
      bar.id = "wf-timeline-bar";

      var parent = sessionBar.parentNode;
      if (parent) {
        parent.insertBefore(bar, sessionBar.nextSibling);
      }
      return bar;
    }

    function _esc(s) {
      return String(s || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function _buildStepsRowHtml(st) {
      var labels = { init: "INIT", plan: "PLAN", work: "WORK", report: "REPORT", done: "DONE", failed: "FAIL" };
      var current = st.currentStep || "init";

      var orderedSteps = ["init", "plan", "work", "report", "done"];
      if (current === "failed") {
        orderedSteps.push("failed");
      }

      var stepOrder = {};
      orderedSteps.forEach(function (s, i) { stepOrder[s] = i; });
      var currentIdx = stepOrder[current];

      var timestamps = st.stepTimestamps || {};

      var html = '<div class="wf-steps-row">';
      orderedSteps.forEach(function (step, idx) {
        var cls = "wf-timeline-step";
        var stepState; // "active" | "done" | "pending"
        if (step === current) {
          cls += " active";
          stepState = "active";
        } else if (currentIdx !== undefined && idx < currentIdx) {
          cls += " done";
          stepState = "done";
        } else {
          cls += " pending";
          stepState = "pending";
        }

        html += '<div class="' + cls + '" data-step="' + _esc(step) + '">';
        html += _esc(labels[step] || step.toUpperCase());

        if (step === "work" && st.currentPhase >= 0) {
          html += '<span class="wf-phase-badge">Phase ' + _esc(String(st.currentPhase)) + '</span>';
        }

        // Elapsed time badge
        var ts = timestamps[step];
        if (ts && ts.start) {
          if (stepState === "done" && ts.end) {
            // Completed step — fixed duration
            var elapsed = ts.end - ts.start;
            html += '<span class="wf-step-time done">' + _formatDuration(elapsed) + '</span>';
          } else if (stepState === "active") {
            // Active step — real-time updated via timer
            var elapsedNow = Date.now() - ts.start;
            html += '<span class="wf-step-time active" data-start="' + ts.start + '">'
              + _formatDuration(elapsedNow) + '</span>';
          }
        }

        html += '</div>';

        if (idx < orderedSteps.length - 1) {
          html += '<div class="wf-timeline-sep">&rarr;</div>';
        }
      });
      html += '</div>';
      return html;
    }

    function _buildMetaRowHtml(st) {
      if (!st.command && !st.title) return "";
      var html = '<div class="wf-meta-row">';
      if (st.command) {
        html += '<span class="wf-meta-command">' + _esc(st.command) + '</span>';
        html += '<span class="wf-meta-sep">&middot;</span>';
      }
      if (st.title) {
        html += '<span class="wf-meta-title">' + _esc(st.title) + '</span>';
      }
      if (st.workId) {
        html += '<span class="wf-meta-id">#' + _esc(st.workId) + '</span>';
      }
      html += '</div>';
      return html;
    }

    function _buildArtifactsRowHtml(artifacts) {
      if (!artifacts || artifacts.length === 0) return "";
      var seen = {};
      var html = '<div class="wf-artifacts-row">';
      artifacts.forEach(function (a) {
        if (seen[a.path]) return;
        seen[a.path] = true;
        html += '<a class="wf-timeline-artifact" data-path="' + _esc(a.path) + '"'
          + ' href="#" title="' + _esc(a.label) + ' 열기">'
          + _esc(a.label) + '</a>';
      });
      html += '</div>';
      return html;
    }

    /**
     * Build the agent status row HTML for WORK step.
     * Shows agent badges (running/completed) with phase info.
     * Only renders when WORK step is active and phase data exists.
     */
    function _buildAgentStatusHtml(st) {
      // Only show during or after WORK step with phase data
      if (!st.phases || st.phases.length === 0) return "";

      var current = st.currentStep || "init";
      var stepOrder = { init: 0, plan: 1, work: 2, report: 3, done: 4 };
      var currentIdx = stepOrder[current];

      // Show agent row when WORK is active or already completed (idx >= 2)
      if (currentIdx === undefined || currentIdx < 2) return "";

      var agentStatuses = st.agentStatuses || {};
      var agentKeys = Object.keys(agentStatuses);
      if (agentKeys.length === 0) return "";

      // Get the latest (current or last) phase info
      var latestPhase = st.phases[st.phases.length - 1];
      var phaseLabel = "Phase " + latestPhase.n;
      if (latestPhase.mode) {
        phaseLabel += " (" + _esc(latestPhase.mode) + ")";
      }

      var html = '<div class="wf-agent-row">';
      html += '<span class="wf-agent-row-label">' + phaseLabel + '</span>';

      agentKeys.forEach(function (agentId) {
        var status = agentStatuses[agentId] || "running";
        var badgeCls = "wf-agent-badge " + _esc(status);
        var icon = status === "completed" ? "\u2713 " : "\u25CF ";
        html += '<span class="' + badgeCls + '">' + icon + _esc(agentId) + '</span>';
      });

      html += '</div>';
      return html;
    }

    // ── Public API ──

    return {

      renderTimelineBar: function () {
        // Guard: requires isWorkflowMode and outputDiv from terminal.js core
        // These are checked via Board.state
        var outputDiv = document.getElementById("terminal-output");
        if (!outputDiv) return;

        var bar = _getOrCreateBar();
        if (!bar) return;

        var st = WorkflowRenderer.state;

        var html = "";
        html += _buildMetaRowHtml(st);
        html += _buildStepsRowHtml(st);
        html += _buildAgentStatusHtml(st);
        html += _buildArtifactsRowHtml(st.artifacts);

        bar.innerHTML = html;

        var links = bar.querySelectorAll(".wf-timeline-artifact[data-path]");
        for (var i = 0; i < links.length; i++) {
          (function (link) {
            link.addEventListener("click", function (e) {
              e.preventDefault();
              var path = link.getAttribute("data-path");
              if (path) {
                phaseTimeline.openArtifact(path);
              }
            });
          })(links[i]);
        }

        // Timer management: start if there's an active step, stop if done/failed
        if (st.status === "done" || st.status === "failed") {
          _stopTimer();
        } else if (bar.querySelector(".wf-step-time.active")) {
          _startTimer();
        }
      },

      renderArtifactLinks: function () {
        var outputDiv = document.getElementById("terminal-output");
        if (!outputDiv) return;

        var bar = document.getElementById("wf-timeline-bar");
        if (!bar) {
          phaseTimeline.renderTimelineBar();
          return;
        }

        var st = WorkflowRenderer.state;

        var existingRow = bar.querySelector(".wf-artifacts-row");
        var newHtml = _buildArtifactsRowHtml(st.artifacts);

        if (newHtml) {
          if (existingRow) {
            existingRow.outerHTML = newHtml;
          } else {
            bar.insertAdjacentHTML("beforeend", newHtml);
          }
          var links = bar.querySelectorAll(".wf-timeline-artifact[data-path]");
          for (var i = 0; i < links.length; i++) {
            (function (link) {
              link.addEventListener("click", function (e) {
                e.preventDefault();
                var path = link.getAttribute("data-path");
                if (path) phaseTimeline.openArtifact(path);
              });
            })(links[i]);
          }
        } else if (existingRow) {
          existingRow.parentNode.removeChild(existingRow);
        }
      },

      renderStatusBadge: function (status, msg) {
        var outputDiv = document.getElementById("terminal-output");
        if (!outputDiv) return;

        var follow = Board._term && Board._term.isNearBottom ? Board._term.isNearBottom(outputDiv) : true;

        var existing = outputDiv.querySelector(".wf-status-badge");
        if (existing) existing.parentNode.removeChild(existing);

        var st = WorkflowRenderer.state;
        var isOk = (status === "ok");

        var badge = document.createElement("div");
        badge.className = "wf-status-badge";
        badge.setAttribute("data-status", isOk ? "ok" : "fail");

        var iconChar = isOk ? "&#10003;" : "&#10005;";
        var labelText = isOk ? "워크플로우 완료" : "워크플로우 실패";
        var subText = msg || (isOk
          ? ("#" + (st.workId || "") + " · " + (st.title || ""))
          : (st.error || "FAIL"));

        badge.innerHTML =
          '<span class="wf-badge-icon">' + iconChar + '</span>' +
          '<span class="wf-badge-text">' + _esc(labelText) + '</span>' +
          '<span class="wf-badge-sub">' + _esc(subText) + '</span>';

        outputDiv.appendChild(badge);
        if (Board._term && Board._term.scrollToBottomIfFollowing) {
          Board._term.scrollToBottomIfFollowing(outputDiv, follow);
        }
      },

      render: function () {
        phaseTimeline.renderTimelineBar();

        var st = WorkflowRenderer.state;
        if (st.status === "done") {
          phaseTimeline.renderStatusBadge("ok");
        } else if (st.status === "failed") {
          phaseTimeline.renderStatusBadge("fail", st.error);
        }
      },

      openArtifact: function (path) {
        var url = "/api/workflow/artifact?path=" + encodeURIComponent(path);
        window.open(url, "_blank");
      },

      insertPlaceholder: function () {
        _getOrCreateBar();
      },

      /**
       * Stop the real-time timer. Called externally when workflow ends.
       */
      stopTimer: function () {
        _stopTimer();
      },

      /**
       * Format duration in ms to human-readable string.
       * Exposed for reuse by other modules (e.g., tool card timing).
       */
      formatDuration: _formatDuration

    };
  })();

  // ── Register on Board namespace ──
  Board.WorkflowRenderer = WorkflowRenderer;
  Board.phaseTimeline = phaseTimeline;
})();
