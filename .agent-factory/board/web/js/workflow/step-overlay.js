/**
 * @module step-overlay
 *
 * Board.stepOverlay — T-505 P3.
 *
 * Step 6 box (INIT / PLAN / WORK / VALIDATE / REPORT / DONE) + WORK box
 * Single true source of Phase sub-panel. workflow
 * FSM status and fold/expand automatic rule by directly subscribed to workflow finish event
 * Notice
 *
 * Price:
 *   - Main module: Step/Phase latometer DOM + fold/expand automatic rule + state machine
 *   - production-line-stdout-bridge: workflow stdout event → this module handleStdout forward
 *   - session.js: main terminal stdout renderer (main cycle in unloaded)
 *
 * Data Model (T-505 P1 §4):
 *   Step = {id, status, startedAt, finishedAt, collapsed, userOverride, phases}
 *   Phase = {id, title, status, startedAt, finishedAt, collapsed, userOverride}
 *
 * fold/expand automatic rule (T-505 P1 §5):
 *   running → expand
 *   done → fold (cascade: all phase done this side step also fold)
 *   failure → expand + outline strong
 *   pending → fold
 *   user click → userOverride = true
 *
 * Visual Canon (board.md §6):
 *   - terracotta #D97757 = running
 *   - cyan #D97757      = success
 *   #f48771
 *   - 1.6s pulse + prefers-reduced-motion guard — step-overlay.css fixation
 *
 * SPEC §0.1:
 *   Copyright © 2019 CRETeria. All Rights Reserved.
 *
 * Depends on: common.js (Board namespace), production-line-workflow.js (subscribe API)
 * Registers:  Board.stepOverlay
 */
"use strict";

(function () {

  // ── VIEW

  /** Step 6box definition — order = up→ bottom display order. */
  var STEP_IDS = ["INIT", "PLAN", "WORK", "VALIDATE", "REPORT", "DONE"];

  /** Valid status value. */
  var STATUS_PENDING = "pending";
  var STATUS_RUNNING = "running";
  var STATUS_DONE = "done";
  var STATUS_FAIL = "fail";

  // ── Internal Status ──

  /** @type {Object<string, {id, status, startedAt, finishedAt, collapsed, userOverride, phases}>} */
  var _stepMap = {};

  /** @type {HTMLElement null} root DOM */
  var _rootEl = null;

  /** @type {{close: function, sessionId: string}|null} */
  var _subscription = null;

  /** @type {string|null} */
  var _activeSessionId = null;

  // ── Early state ──

  function _resetState() {
    _stepMap = {};
    for (var i = 0; i < STEP_IDS.length; i++) {
      _stepMap[STEP_IDS[i]] = {
        id: STEP_IDS[i],
        status: STATUS_PENDING,
        startedAt: null,
        finishedAt: null,
        collapsed: true,
        userOverride: false,
        phases: []
      };
    }
  }

  // ── DOM ──

  function _esc(s) {
    if (Board.util && Board.util.esc) return Board.util.esc(s);
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** SVG inline (board.md §8 — Lucide Style). */
  function _iconOk() {
    return '<svg class="wf-step-icon-ok" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"'
      + ' fill="none" stroke-linecap="round" stroke-linejoin="round">'
      + '<polyline points="20 6 9 17 4 12"></polyline></svg>';
  }
  function _iconFail() {
    return '<svg class="wf-step-icon-fail" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"'
      + ' fill="none" stroke-linecap="round" stroke-linejoin="round">'
      + '<line x1="18" y1="6" x2="6" y2="18"></line>'
      + '<line x1="6" y1="6" x2="18" y2="18"></line></svg>';
  }
  function _iconChevron() {
    return '<svg class="wf-step-toggle" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"'
      + ' fill="none" stroke-linecap="round" stroke-linejoin="round">'
      + '<polyline points="9 18 15 12 9 6"></polyline></svg>';
  }

  /**
   * Root DOM Lazy + 6 Step Box Earlyender.
   * external containers (e.g. terminal.html wf-step-overlay-host)
   * append on the body end itself.
   *
   * @param {HTMLElement} [host] mount container override
   * @returns {HTMLElement}
   */
  function mount(host) {
    if (_rootEl && document.body.contains(_rootEl)) return _rootEl;
    var root = document.createElement("div");
    root.className = "wf-step-overlay";
    root.setAttribute("data-wf-overlay-root", "1");
    _rootEl = root;
    for (var i = 0; i < STEP_IDS.length; i++) {
      root.appendChild(_renderStepBox(STEP_IDS[i]));
    }

    if (host) host.appendChild(root);
    else if (document.body) document.body.appendChild(root);

    return root;
  }

  function _renderStepBox(stepId) {
    var step = _stepMap[stepId];
    var box = document.createElement("div");
    box.className = "wf-step " + step.status;
    if (step.collapsed) box.classList.add("collapsed");
    else box.classList.add("expanded");
    box.setAttribute("data-wf-step", stepId);

    var header = document.createElement("div");
    header.className = "wf-step-header";
    header.innerHTML = ''
      + '<span class="wf-step-id">' + _esc(stepId) + '</span>'
      + '<span class="wf-step-status"></span>'
      + _iconChevron();
    header.addEventListener("click", function () {
      _toggleStep(stepId);
    });
    box.appendChild(header);

    var body = document.createElement("div");
    body.className = "wf-step-body";

    var stdout = document.createElement("div");
    stdout.setAttribute("data-wf-stdout", "1");
    body.appendChild(stdout);

    if (stepId === "WORK") {
      var phaseList = document.createElement("div");
      phaseList.className = "wf-phase-list";
      phaseList.setAttribute("data-wf-phase-list", "1");
      body.appendChild(phaseList);
    }

    box.appendChild(body);
    return box;
  }

  function _stepBox(stepId) {
    if (!_rootEl) return null;
    return _rootEl.querySelector('[data-wf-step="' + stepId + '"]');
  }

  function _phaseBox(phaseId) {
    if (!_rootEl) return null;
    return _rootEl.querySelector('[data-wf-phase="' + phaseId + '"]');
  }

  function _setStepClass(stepId) {
    var step = _stepMap[stepId];
    var box = _stepBox(stepId);
    if (!box) return;
    box.classList.remove(STATUS_PENDING, STATUS_RUNNING, STATUS_DONE, STATUS_FAIL);
    box.classList.add(step.status);
    box.classList.toggle("collapsed", step.collapsed);
    box.classList.toggle("expanded", !step.collapsed);
    var statusEl = box.querySelector(".wf-step-status");
    if (statusEl) statusEl.innerHTML = _statusLabel(step.status);
  }

  function _setPhaseClass(phaseId) {
    var step = _stepMap.WORK;
    var phase = null;
    for (var i = 0; i < step.phases.length; i++) {
      if (step.phases[i].id === phaseId) { phase = step.phases[i]; break; }
    }
    if (!phase) return;
    var box = _phaseBox(phaseId);
    if (!box) return;
    box.classList.remove(STATUS_PENDING, STATUS_RUNNING, STATUS_DONE, STATUS_FAIL);
    box.classList.add(phase.status);
    box.classList.toggle("collapsed", phase.collapsed);
    box.classList.toggle("expanded", !phase.collapsed);
  }

  function _statusLabel(status) {
    if (status === STATUS_DONE) return _iconOk();
    if (status === STATUS_FAIL) return _iconFail();
    if (status === STATUS_RUNNING) return '•••';
    return "";
  }

  // ── fold/expand automatic rule (T-505 P1 §5) ──

  /**
   * Step status Automatic fold/expand applied when changing (userOverride guard).
   * @param {string} stepId
   * @param {string} newStatus
   */
  function _autoFoldStep(stepId, newStatus) {
    var step = _stepMap[stepId];
    if (!step) return;
    step.status = newStatus;
    if (step.userOverride) {
      _setStepClass(stepId);
      return;
    }
    if (newStatus === STATUS_RUNNING || newStatus === STATUS_FAIL) {
      step.collapsed = false;
    } else if (newStatus === STATUS_DONE || newStatus === STATUS_PENDING) {
      step.collapsed = true;
    }
    _setStepClass(stepId);
  }

  function _autoFoldPhase(phaseId, newStatus) {
    var step = _stepMap.WORK;
    var phase = null;
    for (var i = 0; i < step.phases.length; i++) {
      if (step.phases[i].id === phaseId) { phase = step.phases[i]; break; }
    }
    if (!phase) return;
    phase.status = newStatus;
    if (phase.userOverride) {
      _setPhaseClass(phaseId);
      return;
    }
    if (newStatus === STATUS_RUNNING || newStatus === STATUS_FAIL) {
      phase.collapsed = false;
    } else if (newStatus === STATUS_DONE || newStatus === STATUS_PENDING) {
      phase.collapsed = true;
    }
    _setPhaseClass(phaseId);

    // cascade: All phase done side WORK Step also auto fold (protected if thefail)
    var allDone = true;
    var anyFail = false;
    for (var j = 0; j < step.phases.length; j++) {
      if (step.phases[j].status !== STATUS_DONE) allDone = false;
      if (step.phases[j].status === STATUS_FAIL) anyFail = true;
    }
    if (allDone && !anyFail && !step.userOverride) {
      step.collapsed = true;
      _setStepClass("WORK");
    }
  }

  function _toggleStep(stepId) {
    var step = _stepMap[stepId];
    if (!step) return;
    step.userOverride = true;
    step.collapsed = !step.collapsed;
    _setStepClass(stepId);
  }

  function _togglePhase(phaseId) {
    var step = _stepMap.WORK;
    var phase = null;
    for (var i = 0; i < step.phases.length; i++) {
      if (step.phases[i].id === phaseId) { phase = step.phases[i]; break; }
    }
    if (!phase) return;
    phase.userOverride = true;
    phase.collapsed = !phase.collapsed;
    _setPhaseClass(phaseId);
  }

  // ── Phase dynamic creation (plan.json phases array based) ──

  /**
   * sub-panel dynamic renderer in the WORK box with the phases array of plan.json.
   * spawn mode / workers / acceptance criteria does not expose (SPEC §0.1).
   *
   * @param {Array<{id: string, title: string}>} phases
   */
  function setPhases(phases) {
    if (!Array.isArray(phases)) return;
    var step = _stepMap.WORK;
    step.phases = [];
    for (var i = 0; i < phases.length; i++) {
      var p = phases[i];
      if (!p || !p.id) continue;
      step.phases.push({
        id: p.id,
        title: p.title || "",
        status: STATUS_PENDING,
        startedAt: null,
        finishedAt: null,
        collapsed: true,
        userOverride: false
      });
    }
    _renderPhaseList();
  }

  function _renderPhaseList() {
    if (!_rootEl) return;
    var list = _rootEl.querySelector('[data-wf-phase-list]');
    if (!list) return;
    while (list.firstChild) list.removeChild(list.firstChild);
    var phases = _stepMap.WORK.phases;
    for (var i = 0; i < phases.length; i++) {
      list.appendChild(_renderPhaseBox(phases[i]));
    }
  }

  function _renderPhaseBox(phase) {
    var box = document.createElement("div");
    box.className = "wf-phase " + phase.status + (phase.collapsed ? " collapsed" : " expanded");
    box.setAttribute("data-wf-phase", phase.id);

    var header = document.createElement("div");
    header.className = "wf-phase-header";
    header.innerHTML = ''
      + '<span class="wf-phase-id">' + _esc(phase.id) + '</span>'
      + '<span class="wf-phase-title">' + _esc(phase.title) + '</span>';
    header.addEventListener("click", function () {
      _togglePhase(phase.id);
    });
    box.appendChild(header);

    var body = document.createElement("div");
    body.className = "wf-phase-body";
    var stdout = document.createElement("div");
    stdout.setAttribute("data-wf-stdout", "1");
    body.appendChild(stdout);
    box.appendChild(body);
    return box;
  }

  // ── SSE event handler (workflow step / phase / finish) ──

  function _onStep(data) {
    if (!data || !data.step) return;
    var stepId = String(data.step).toUpperCase();
    if (!_stepMap[stepId]) return;
    var prev = data.prev_step ? String(data.prev_step).toUpperCase() : "";
    // Off-Step Auto done (FAILED or)
    if (prev && _stepMap[prev] && _stepMap[prev].status !== STATUS_FAIL) {
      _stepMap[prev].finishedAt = data.ts || null;
      _autoFoldStep(prev, STATUS_DONE);
    }
    if (stepId === "FAILED") {
      // FAILED alias — current Step Verify
      var curr = prev || "DONE";
      if (_stepMap[curr]) {
        _stepMap[curr].finishedAt = data.ts || null;
        _autoFoldStep(curr, STATUS_FAIL);
      }
      return;
    }
    _stepMap[stepId].startedAt = data.ts || null;
    _autoFoldStep(stepId, STATUS_RUNNING);
  }

  function _onPhase(data) {
    if (!data || !data.phase) return;
    var phaseId = String(data.phase);
    var action = data.action || "start";
    if (action === "start") {
      _autoFoldPhase(phaseId, STATUS_RUNNING);
    } else if (action === "end") {
      var outcome = (data.extras && data.extras.outcome) || "ok";
      _autoFoldPhase(phaseId, outcome === "ok" ? STATUS_DONE : STATUS_FAIL);
    }
  }

  function _onFinish(data) {
    var outcome = data && data.outcome === "ok" ? STATUS_DONE : STATUS_FAIL;
    _autoFoldStep("DONE", outcome);
  }

  /**
   * The entry point where the production-line-stdout-bridge calls. payload.raw with SDK NDJSON 1 line.
   * Stdout chunk to the current Step/Phase [data-wf-stdout] container
   * or append the tool use card 1 line.
   *
   * @param {{text?: string, raw?: object}} data
   */
  function handleStdout(data) {
    if (!data) return;
    var target = _currentStdoutContainer();
    if (!target) return;
    var raw = data.raw || null;
    if (raw && raw.type === "tool_use") {
      _appendToolUseCard(target, raw);
      return;
    }
    var text = data.text || "";
    if (raw && raw.type === "assistant" && raw.message && Array.isArray(raw.message.content)) {
      var content = raw.message.content;
      for (var i = 0; i < content.length; i++) {
        var blk = content[i];
        if (!blk || typeof blk !== "object") continue;
        if (blk.type === "text" && blk.text) _appendStdoutLine(target, blk.text);
        else if (blk.type === "tool_use") _appendToolUseCard(target, blk);
      }
      return;
    }
    if (text) _appendStdoutLine(target, text);
  }

  function _currentStdoutContainer() {
    if (!_rootEl) return null;
    var workPhases = _stepMap.WORK.phases;
    for (var i = 0; i < workPhases.length; i++) {
      if (workPhases[i].status === STATUS_RUNNING) {
        var pbox = _phaseBox(workPhases[i].id);
        if (pbox) return pbox.querySelector('[data-wf-stdout]');
      }
    }
    for (var j = 0; j < STEP_IDS.length; j++) {
      if (_stepMap[STEP_IDS[j]].status === STATUS_RUNNING) {
        var sbox = _stepBox(STEP_IDS[j]);
        if (sbox) return sbox.querySelector('.wf-step-body > [data-wf-stdout]');
      }
    }
    return null;
  }

  function _appendStdoutLine(container, text) {
    var line = document.createElement("div");
    line.className = "wf-stdout-line";
    line.textContent = String(text);
    container.appendChild(line);
  }

  function _appendToolUseCard(container, raw) {
    var name = raw.name || "tool";
    var input = raw.input || {};
    var summary = "";
    if (typeof input.command === "string") summary = input.command;
    else if (typeof input.file_path === "string") summary = input.file_path;
    else if (typeof input.pattern === "string") summary = input.pattern;
    else if (typeof input.prompt === "string") summary = input.prompt;
    else summary = JSON.stringify(input).slice(0, 140);
    if (summary.length > 220) summary = summary.slice(0, 217) + "…";
    var card = document.createElement("div");
    card.className = "wf-tool-use";
    card.innerHTML = ''
      + '<span class="wf-tool-name">' + _esc(name) + '</span>'
      + '<span class="wf-tool-summary">' + _esc(summary) + '</span>';
    container.appendChild(card);
  }

  // ── SSE Subscription

  /**
   * step / phase / end event subscription. stdout is a production-line-stdout-bridge with forward.
   *
   * @param {string} sessionId
   * @returns {boolean}
   */
  function subscribe(sessionId) {
    if (!sessionId) return false;
    if (!Board.productionLineWorkflow || typeof Board.productionLineWorkflow.subscribe !== "function") return false;
    if (_subscription && _activeSessionId === sessionId) return true;
    disconnect();
    _activeSessionId = sessionId;
    _subscription = Board.productionLineWorkflow.subscribe(sessionId, {
      onStep: _onStep,
      onPhase: _onPhase,
      onFinish: _onFinish
    });
    return true;
  }

  function disconnect() {
    if (_subscription) {
      try { _subscription.close(); } catch (_) {}
    }
    _subscription = null;
    _activeSessionId = null;
  }

  // ── Reset ──

  _resetState();

  // ── Register on Board namespace ──

  Board.stepOverlay = {
    mount: mount,
    setPhases: setPhases,
    subscribe: subscribe,
    disconnect: disconnect,
    handleStdout: handleStdout,
    // Debug / Test
    _state: function () { return _stepMap; },
    _stepIds: STEP_IDS
  };

})();
