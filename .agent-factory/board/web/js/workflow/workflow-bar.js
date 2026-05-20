/**
 * @module workflow-bar
 *
 * WorkflowRenderer (banner parser + state machine) and phaseTimeline (DOM renderer).
 *
 * Parses Bash command result text for workflow banner patterns emitted by
 * flow-claude, flow-init, flow-step, flow-phase, and flow-finish scripts.
 * phaseTimeline renders the timeline bar DOM below .terminal-session-bar.
 *
 * T-507 — stdout / step·Phase latency / output viewer is step-overlay.js +
 * session.js is responsible. git git
 * timeline bar (steps row / task row / artifacts row)
 *
 * Depends on: common.js (Board namespace)
 * Registers:  Board.WorkflowRenderer, Board.phaseTimeline
 *
 * Board.phaseTimeline public API:
 *   renderTimelineBar()                — full bar re-render from WorkflowRenderer.state
 *   renderArtifactLinks()              — incremental artifact row update
 *   renderStatusBadge(status, msg)     — completion badge (ok|fail)
 *   renderTaskRow(taskMap)             — task status badge row (session.js _taskStatusMap)
 *   openArtifact(path)                 — open artifact in new tab
 *   insertPlaceholder()                — ensure bar container exists
 *   stopTimer()                        — stop elapsed-time interval
 *   formatDuration(ms)                 — ms → human-readable string
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
      unknown:  "#858585",
      init:     "#858585",
      plan:     "#569cd6",
      work:     "#D97757",
      validate: "#dcdcaa",  /* 12 Rule verification step */
      report:   "#c586c0",
      done:     "#4ec9b0",
      failed:   "#f48771"
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
        init:     { start: null, end: null },
        plan:     { start: null, end: null },
        work:     { start: null, end: null },
        validate: { start: null, end: null }, /* T-495 P2 */
        report:   { start: null, end: null },
        done:     { start: null, end: null }
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
      // T-383 Phase 3: When reset  stepPanels empty map  restoreSession side
      // rebuildStepPanelsFromDom to rebuild maps to current DOM.
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
          init:     { start: null, end: null },
          plan:     { start: null, end: null },
          work:     { start: null, end: null },
          validate: { start: null, end: null },
          report:   { start: null, end: null },
          done:     { start: null, end: null }
        },
        agentStatuses: {}
      };

      _stepPanels = {};
      _activeStepPanel = null;
      _clearParserFlags();
    }

    /**
     * .wf-step-panel  stepPanels map and  activeStepPanel
     * Synchronize the current DOM. by cloneNode
     * It is called after being replaced. Fixed rules: active last → last panel → null.
     *
     * @param {HTMLElement} outputDiv
     */
    function _rebuildStepPanelsFromDom(outputDiv) {
      if (!outputDiv) return;

      var panels = outputDiv.querySelectorAll(".wf-step-panel");
      var newMap = {};
      var lastActive = null;
      var lastAny = null;

      for (var i = 0; i < panels.length; i++) {
        var panel = panels[i];
        var stepName = panel.getAttribute("data-step");
        if (!stepName) continue;

        // If the duplicate data-step exists in this DOM, it is better.
        // (First of the latest DOM in VUL-2 redundancy panel scenario)
        newMap[stepName] = panel;
        lastAny = panel;
        if (panel.getAttribute("data-status") === "active") {
          lastActive = panel;
        }
      }

      _stepPanels = newMap;
      _activeStepPanel = lastActive || lastAny;
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

    /**
     * T-508 — step full + step elapsed ts record.
     *
     * @param {string} stepName
     * @param {{startTsMs?: number}} [opts]
     *   startTsMs: Step enter epoch ms received from backend GET / SSE event.
     *     Date.now() fallback(v1 quarter / end operation)
     *     replay guard: the existing start value is null, or the new value is larger.
     *     If the past ts are incoming than the existing values, it is ignored (smooth elapsed / jump blocked).
     */
    function _setStep(stepName, opts) {
      var prevStep = _state.currentStep;
      var newStep = stepName.toLowerCase();
      var externalTs = opts && typeof opts.startTsMs === "number" ? opts.startTsMs : null;
      var now = externalTs != null ? externalTs : Date.now();

      if (_state.stepTimestamps) {
        // End previous step if not yet ended
        if (prevStep && prevStep !== newStep && _state.stepTimestamps[prevStep]) {
          if (!_state.stepTimestamps[prevStep].end) {
            _state.stepTimestamps[prevStep].end = now;
          }
        }
        // Start new step — external ts replay guard
        var ts = _state.stepTimestamps[newStep];
        if (ts) {
          if (externalTs != null) {
            // External ts: the existing value is null, or the new value is larger
            if (ts.start == null || externalTs > ts.start) {
              ts.start = externalTs;
            }
          } else if (!ts.start) {
            ts.start = now;
          }
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

    // ── T-508 — production-line elapsed ts persist (localStorage fallback) ──
    var PRODUCTION_LINE_STATE_STORAGE_PREFIX = "wf_production_line_state_";

    /**
     * Currently active production-line session id extraction (Board. term.workflowSessionId).
     * null — storage caller skip when failed.
     */
    function _productionLineSessionId() {
      try {
        var sid = Board._term && Board._term.workflowSessionId;
        if (sid && Board.productionLineWorkflow && Board.productionLineWorkflow.isProductionLineSessionId
            && Board.productionLineWorkflow.isProductionLineSessionId(sid)) {
          return sid;
        }
      } catch (_) {}
      return null;
    }

    /**
     * state step/phase ts only extract localStorage to write.
     * production-line session only when active. v1 No quarter impact.
     */
    function _persistProductionLineState() {
      var sid = _productionLineSessionId();
      if (!sid) return;
      try {
        var snap = {
          stepTimestamps: _state.stepTimestamps || null,
          phases: _state.phases ? _state.phases.map(function (p) {
            return { n: p.n, start: p.start || null, end: p.end || null, mode: p.mode || "" };
          }) : [],
          cycleStartTs: _state.cycleStartTs || null,
          currentStep: _state.currentStep || null,
          currentPhase: typeof _state.currentPhase === "number" ? _state.currentPhase : -1
        };
        window.localStorage.setItem(
          PRODUCTION_LINE_STATE_STORAGE_PREFIX + sid,
          JSON.stringify(snap)
        );
      } catch (_) {}
    }

    /**
     * localStorage  state of step/phase ts restored.
     * The backend GET response is used in the first render immediately after the new call.
     * Guard: If the existing  state value is refreshed, the storage value is ignored (unlocked).
     */
    function _restoreProductionLineState() {
      var sid = _productionLineSessionId();
      if (!sid) return false;
      try {
        var raw = window.localStorage.getItem(PRODUCTION_LINE_STATE_STORAGE_PREFIX + sid);
        if (!raw) return false;
        var snap = JSON.parse(raw);
        if (!snap || typeof snap !== "object") return false;

        // stepTimestamps restore — if the existing value is refreshed
        if (snap.stepTimestamps && _state.stepTimestamps) {
          var steps = Object.keys(_state.stepTimestamps);
          for (var i = 0; i < steps.length; i++) {
            var s = steps[i];
            var existing = _state.stepTimestamps[s];
            var stored = snap.stepTimestamps[s];
            if (!stored || !existing) continue;
            if (stored.start && (!existing.start || stored.start < existing.start)) {
              existing.start = stored.start;
            }
            if (stored.end && (!existing.end || stored.end > existing.end)) {
              existing.end = stored.end;
            }
          }
        }

        // phases restoration — only when the existing phases are empty (no race)
        if (Array.isArray(snap.phases) && snap.phases.length > 0
            && (!_state.phases || _state.phases.length === 0)) {
          _state.phases = snap.phases.map(function (p) {
            return {
              n: p.n,
              agents: [],
              taskIds: [],
              mode: p.mode || "sequential",
              start: p.start || null,
              end: p.end || null
            };
          });
          if (typeof snap.currentPhase === "number") {
            _state.currentPhase = snap.currentPhase;
          }
        }

        if (snap.cycleStartTs && !_state.cycleStartTs) {
          _state.cycleStartTs = snap.cycleStartTs;
        }
        return true;
      } catch (_) {
        return false;
      }
    }

    /**
     * T-495 P3 — workflow step/phase/finish payload, extras key
     * (verdict/commit/commit hash/retry/regression)
     *
     * if the driver sends forward-compatible payload, immediately  state.v2Meta
     * In this case, renderTimelineBar's  buildMetaRowHtml is displayed as a badge.
     *
     * #4 (verdict) / #5 (commit) / #6 (retry) meet.
     */
    function _absorbProductionLineExtras(data) {
      if (!data || typeof data !== "object") return;
      if (!_state.v2Meta) _state.v2Meta = {};
      var m = _state.v2Meta;
      // verdict — PASS/WARN/FAIL/SKIP (advisory)
      if (data.verdict) m.verdict = String(data.verdict).toUpperCase();
      if (data.verdict_violations != null) m.verdictViolations = data.verdict_violations;
      // auto_commit hash — driver auto_commit emit
      if (data.commit) m.commit = String(data.commit);
      if (data.commit_hash) m.commit = String(data.commit_hash);
      // retry — rule-based retry counter
      if (data.retry != null) m.retry = data.retry;
      // regression.pattern (5 types) — advisory marker
      if (data.regression) {
        if (!m.regression) m.regression = [];
        m.regression.push(String(data.regression));
      }
    }

    /**
     * T-508 — phase entry + phase elapsed ts record.
     *
     * @param {number} n - phase number
     * @param {string} mode
     * @param {string[]} agents
     * @param {string[]} taskIds
     * @param {{startTsMs?: number}} [opts]
     *   startTsMs: epoch ms in the outside (backend GET / SSE event).
     *     Date.now() fallback same phase n field — conventional  state.phases
     *     push skip (replay redundancy push block) if the end is like n.
     */
    function _setPhase(n, mode, agents, taskIds, opts) {
      var externalTs = opts && typeof opts.startTsMs === "number" ? opts.startTsMs : null;
      var now = externalTs != null ? externalTs : Date.now();

      // <% if (imgObj.width >= imgObj.height) { %>
      if (_state.phases && _state.phases.length > 0) {
        var tail = _state.phases[_state.phases.length - 1];
        if (tail && tail.n === n) {
          _state.currentPhase = n;
          return;
        }
        if (tail && !tail.end) tail.end = now;
      }
      _state.phases.push({
        n:       n,
        agents:  agents  || [],
        taskIds: taskIds || [],
        mode:    mode,
        start:   now,
        end:     null
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
      // T-383 Phase 4 (VUL-4 / S2) invariant:
      //   _stepPanels[stepName] <-> outputDiv.querySelector(
      //     '.wf-step-panel[data-step="' + stepName + '"]'
      //   ) must refer to the same DOM node.
      //   The panel with the same data-step value is up to one in outputDiv.
      //
      // restoreSession This outputDiv to cloneNode
      // rebuildStepPanelsFromDom(outputDiv) has not been called
      // If you have a problem, please do not hesitate to contact us.
      // The same data-step panel is found by rebounding existing panels to maps
      // Double appendChild to block VUL-4 duplicate creation.
      if (_stepPanels[stepName]) return _stepPanels[stepName];

      var outputDiv = document.getElementById("terminal-output");
      if (!outputDiv) return null;

      // DOM fallback: Phase 3  rebuildStepPanelsFromDom Same
      // Maintain consistency using querySelector pattern.
      var existing = outputDiv.querySelector(
        '.wf-step-panel[data-step="' + stepName + '"]'
      );
      if (existing) {
        _stepPanels[stepName] = existing;
        return existing;
      }

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
      else if (/report\.(html|md)$/.test(path)) type = "report";
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

      // ── [STATE] Phase Change (2-line sequence, line 1) ──
      if (P.stateChange.test(line)) {
        _pendingStateChange = true;
        return true;
      }

      // ── >> FROM -> TO (2-line sequence, line 2) ──
      // FSM is responsible for step SSE events. Only the banner is consumed.
      if (_pendingStateChange && (m = P.stateTransition.exec(line))) {
        _pendingStateChange = false;
        return true;
      }

      // ── AGENT_DISPATCH / AGENT_RETURN ──
      if ((m = P.taskStatus.exec(line))) {
        var action = m[1];
        var taskId = m[2];
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

      // [WORKFLOW] command — banner consumption + command capture only (reset removal)
      if (_inBox && (m = P.workflowStartCmd.exec(line))) {
        _boxHasCmd = true;
        _inBox     = false;
        if (!_state.command) _state.command = _pick(m);
        return true;
      }

      if (!_inBox && (m = P.workflowStartCmd.exec(line))) {
        if (!_state.command) _state.command = _pick(m);
        return true;
      }

      // [STEP] in box — Only banner consumption (FSM  setStep removal)
      if (_inBox && !_boxHasCmd && (m = P.stepStart.exec(line))) {
        _inBox = false;
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

      // stepEnd — Only banner consumption (FSM  setStep removal)
      if ((m = P.stepEnd.exec(line))) {
        vals = _pickN(m, 2);
        _pendingStepEnd     = true;
        _pendingStepEndName = vals[0];
        _pendingStepEndTs   = (vals[1] || "").trim();
        return true;
      }

      // [STEP] without box — Only banner consumption (FSM  setStep removal)
      if (!_inBox && (m = P.stepStart.exec(line))) {
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

      // finishKey — Banner consumption only (complete/package is responsible for step 'done' event)
      if (_pendingFinish && (m = P.finishKey.exec(line))) {
        _pendingFinish = false;
        _pendingFinishResult = "";
        return true;
      }

      // FAIL — Banner Only
      if (P.fail.test(line)) {
        return true;
      }

      return false;
    }

    // ── Public API ──

    return {
      get state() { return _state; },
      patterns: P,

      /**
       * T-495 P2 — production-line workflow step event processing.
       * production-line payload shape: { session_id, step ∈ {NONE/INIT/PLAN/WORK/VALIDATE/REPORT/DONE/FAILED}, phase, prev_step }
       *
       * v1 handleStepEvent
       *  - INIT/PLAN/WORK/VALIDATE/REPORT/DONE
       *  - phase WORK internal sub-phase (P1/P2/...)
       *  - Floor lamp warranty
       */
      handleProductionLineStepEvent: function (data) {
        if (!data || !data.step) return;
        var stepUp = String(data.step).toUpperCase();
        var step = stepUp.toLowerCase();

        // T-495 P3 — extras (verdict/commit/retry) when passing  state
        _absorbProductionLineExtras(data);

        // T-508 — backend epoch sec → frontend epoch ms conversion + cycle start cumulative
        var stepOpts;
        if (typeof data.step_ts === "number" && data.step_ts > 0) {
          stepOpts = { startTsMs: Math.round(data.step_ts * 1000) };
        }
        if (typeof data.cycle_start_ts === "number" && data.cycle_start_ts > 0) {
          var cycleMs = Math.round(data.cycle_start_ts * 1000);
          if (!_state.cycleStartTs || cycleMs < _state.cycleStartTs) {
            _state.cycleStartTs = cycleMs;
          }
        }

        // Final step mapping (DONE/FAILED → fsm closing processing)
        if (stepUp === "DONE") {
          _complete();
          _persistProductionLineState();
          return;
        }
        if (stepUp === "FAILED") {
          _fail("Workflow Failure");
          _persistProductionLineState();
          return;
        }

        // 6 step (INIT/PLAN/WORK/VALIDATE/REPORT)
        if (!{ none:1, init:1, plan:1, work:1, validate:1, report:1 }[step]) {
          return;
        }

        // if phase is changed (like step + new phase) is allowed
        var samePhase = (data.phase || "") === (_state.currentPhase >= 0
          ? "P" + _state.currentPhase : "");
        if (step === _state.currentStep && samePhase) {
          // same step + phase external ts update absorbed
          if (stepOpts && _state.stepTimestamps && _state.stepTimestamps[step]) {
            var ts = _state.stepTimestamps[step];
            if (ts.start == null || stepOpts.startTsMs > ts.start) {
              ts.start = stepOpts.startTsMs;
            }
          }
          _persistProductionLineState();
          return;
        }

        _setStep(step, stepOpts);

        // WORK + phase (P1/P2/...)
        if (step === "work" && data.phase) {
          var phaseNum = parseInt(String(data.phase).replace(/^P/i, ""), 10);
          if (!isNaN(phaseNum)) {
            _setPhase(phaseNum, "sequential", [], [], stepOpts);
          }
        }

        _persistProductionLineState();
      },

      /**
       * T-495 P2 — production-line workflow phase event processing.
       * payload: { session_id, phase: "P1"|"P2"..., action: "start"|"end" }
       */
      handleProductionLinePhaseEvent: function (data) {
        if (!data || !data.phase) return;
        _absorbProductionLineExtras(data);  // T-495 P3 — verdict/commit/retry/regression
        var phaseNum = parseInt(String(data.phase).replace(/^P/i, ""), 10);
        if (isNaN(phaseNum)) return;

        // T-508 — backend epoch sec → frontend epoch ms
        var phaseOpts;
        if (typeof data.step_ts === "number" && data.step_ts > 0) {
          phaseOpts = { startTsMs: Math.round(data.step_ts * 1000) };
        }

        if (data.action === "start") {
          _setPhase(phaseNum, "sequential", [], [], phaseOpts);
        } else if (data.action === "end") {
          // phase end — static phase end record (timer stop trigger)
          var endTs = phaseOpts ? phaseOpts.startTsMs : Date.now();
          if (_state.phases && _state.phases.length > 0) {
            var last = _state.phases[_state.phases.length - 1];
            if (last && last.n === phaseNum && !last.end) {
              last.end = endTs;
            }
          }
        }
        _persistProductionLineState();
      },

      /**
       * T-495 P2 — production-line workflow finish event processing.
       * payload: { session_id, outcome: "ok"|"fail", summary }
       */
      handleProductionLineFinishEvent: function (data) {
        if (!data) return;
        _absorbProductionLineExtras(data);  // T-495 P3 — verdict/commit/retry
        if (data.outcome === "ok") {
          _complete();
        } else {
          _fail(data.summary || "Workflow Failure");
        }
      },

      /**
       * process workflow step SSE events to perform FSM ex.
       * The same step name prevents duplicates.
       * @param {object} data - {step, prev_step, trigger, phase?, mode?, result?}
       */
      handleStepEvent: function (data) {
        if (!data || !data.step) return;
        var step = data.step.toLowerCase();

        // done/failed treatment
        if (step === "done") {
          if (data.result === "failure") {
            _fail("Workflow Failure");
          } else {
            _complete();
          }
          return;
        }

        // <# if ( data.meta.album ) { #>{{ data.meta.album }}<# } #>
        if (step === _state.currentStep && data.phase === undefined) return;

        // FSM
        _setStep(step);

        // Phase update with phase information
        if (data.phase !== undefined) {
          _setPhase(data.phase, data.mode || "sequential", [], []);
        }
      },

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
       * Rebuild _stepPanels map and _activeStepPanel from current DOM state.
       * Call this after replacing outputDiv contents (e.g. session restore)
       * so that subsequent step events target live panels rather than
       * detached references.
       * @param {HTMLElement} outputDiv
       */
      rebuildStepPanelsFromDom: function (outputDiv) {
        _rebuildStepPanelsFromDom(outputDiv);
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
      },

      /**
       * T-508 — localStorage stored in production-line ts  state restored.
       * session.js's  startProductionLineWorkflowSession call before fetchSession.
       * @returns {boolean} Restores whether or not successful (key Missing / parse fails false)
       */
      restoreProductionLineState: function () {
        return _restoreProductionLineState();
      },

      /**
       * T-508 — current  state step/phase ts localStorage to write.
       * Can be triggered in external (session.js). Automatic call handleProductionLine*Event.
       */
      persistProductionLineState: function () {
        _persistProductionLineState();
      }
    };
  })();

  // ── phaseTimeline DOM Renderer ──

  var phaseTimeline = (function () {

    // ── Timer state (module-scoped within phaseTimeline IIFE) ──
    var _timerId = null;

    // ── Task row state (module-scoped within phaseTimeline IIFE) ──
    /** @type {HTMLElement|null} Cached .wf-task-row element */
    var _taskRowEl = null;

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

      var activeBadges = bar.querySelectorAll(".wf-step-time.active, .wf-phase-time.active");
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

    /**
     * Ensure .wf-task-row element exists as a child of .wf-timeline-bar.
     * Looks up the bar by id; returns null if bar doesn't exist yet.
     * Caches the element reference in _taskRowEl.
     * @returns {HTMLElement|null}
     */
    function _ensureTaskRowEl() {
      var bar = document.getElementById("wf-timeline-bar");
      if (!bar) {
        _taskRowEl = null;
        return null;
      }
      // Validate cached reference is still inside bar
      if (_taskRowEl && bar.contains(_taskRowEl)) {
        return _taskRowEl;
      }
      // Look for existing .wf-task-row inside bar
      var existing = bar.querySelector(".wf-task-row");
      if (existing) {
        _taskRowEl = existing;
        return _taskRowEl;
      }
      // Create and append
      var row = document.createElement("div");
      row.className = "wf-task-row";
      bar.appendChild(row);
      _taskRowEl = row;
      return _taskRowEl;
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
      var labels = { init: "INIT", plan: "PLAN", work: "WORK", validate: "VALIDATE", report: "REPORT", done: "DONE", failed: "FAIL" };
      var current = st.currentStep || "init";

      // Step 6 + DONE (INIT/PLAN/WORK/VALIDATE/REPORT/DONE)
      var orderedSteps = ["init", "plan", "work", "validate", "report", "done"];
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

      // [Intermediate] button — only displayed during the session (T-904)
      if (st.status === "running") {
        html += '<button class="wf-stop-btn" title="Workflow Force Stop">Underground</button>';
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
          + ' href="#" title="' + _esc(a.label) + 'News'
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
      // Step 6 (INIT/PLAN/WORK/VALIDATE/REPORT/DONE)
      var stepOrder = { init: 0, plan: 1, work: 2, validate: 3, report: 4, done: 5 };
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
        // Invalidate _taskRowEl cache — bar.innerHTML replaced all children.
        // The next renderTaskRow call will re-create and re-append via _ensureTaskRowEl.
        _taskRowEl = null;

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

        // [Medical] Button Handler Binding (T-904)
        var stopBtn = bar.querySelector(".wf-stop-btn");
        if (stopBtn) {
          stopBtn.addEventListener("click", function () {
            if (!confirm("Stop forced workflow. The current operation can be closed. Do you want to visit?")) {
              return;
            }
            // session id and ticket id collection
            var sessionId = (Board._term && Board._term.workflowSessionId) || null;
            var ticketId = null;
            if (sessionId) {
              // "wf-T-NNN-YYYYMMDD-HHMMSS" → "T-NNN"
              var m = sessionId.match(/^wf-(T-\d+)/);
              if (m) ticketId = m[1];
            }
            if (!sessionId && !ticketId) {
              Board.util.showInfoModal("No Session Information", "You cannot find session information. Please refresh the page and try again.", { severity: "warning" });
              return;
            }
            // T-513 P5 — V1 /api/workflow/stop endpoint disposal. Production-line
            // stop endpoint new releases the star follow-up track. This stop button is temporarily closed.
            Board.util.showInfoModal(
              "About Us",
              "Production-line workflow stop function is restored after a star track endpoint fix (T-513 P5 crystal). Use the ESC or subprocess direct termination of the main terminal at the point of view.",
              { severity: "warning" }
            );
          });
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
        var labelText = isOk ? "Skip to content" : "Workflow Failure";
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
       * Render task status badges into the .wf-task-row container below the timeline bar.
       * Called by session.js _flushTaskRender() with the current _taskStatusMap snapshot.
       *
       * @param {Object<string, {description:string, status:string, toolName:string, summary:string, updatedAt:number}>} taskMap
       */
      renderTaskRow: function (taskMap) {
        var rowEl = _ensureTaskRowEl();
        if (!rowEl) return;

        if (!taskMap || Object.keys(taskMap).length === 0) {
          rowEl.innerHTML = "";
          return;
        }

        // Sort by updatedAt descending (most recently updated first), cap at 8
        var entries = Object.entries(taskMap);
        entries.sort(function (a, b) {
          return (b[1].updatedAt || 0) - (a[1].updatedAt || 0);
        });
        if (entries.length > 8) {
          entries = entries.slice(0, 8);
        }

        var html = "";
        entries.forEach(function (pair) {
          var taskId = pair[0];
          var task = pair[1];
          var status = task.status || "running";
          // ellipsis is the last segment
          // About Us "Reading.agent-factory/board/web/js/foo.js" →
          // foo.js hover title is the original summary.
          var rawDesc = task.description || taskId;
          rawDesc = rawDesc.replace(/[\w./-]*\/([\w.-]+)/g, "$1");
          var desc = _esc(rawDesc);
          var tool = _esc(task.toolName || "");
          var summary = _esc(task.summary || "");
          var titleAttr = summary ? ' title="' + summary + '"' : "";

          var badgeHtml = '<span class="wf-task-badge ' + _esc(status) + '"' + titleAttr + '>';

          // Pulse dot only for running state
          if (status === "running") {
            badgeHtml += '<span class="wf-task-pulse-dot">●</span>';
          }

          badgeHtml += '<span class="wf-task-desc">' + desc + '</span>';
          if (tool) {
            badgeHtml += '<span class="wf-task-tool">' + tool + '</span>';
          }
          badgeHtml += '</span>';

          html += badgeHtml;
        });

        rowEl.innerHTML = html;
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
