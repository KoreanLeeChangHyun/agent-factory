/**
 * @module step-overlay
 *
 * Board.stepOverlay — T-505 P3.
 *
 * Step 6박스 (INIT / PLAN / WORK / VALIDATE / REPORT / DONE) + WORK 박스 안
 * Phase sub-패널의 단일 진실 공급원. workflow_step / workflow_phase /
 * workflow_finish 이벤트를 직접 구독하여 FSM 상태와 fold/expand 자동 룰을
 * 관리한다.
 *
 * 책임 분리:
 *   - 본 모듈: Step/Phase 위계 DOM + fold/expand 자동 룰 + 상태 머신
 *   - v2-stdout-bridge: workflow_stdout 이벤트 → 본 모듈 handleStdout 으로 forward
 *   - session.js (무수정): 메인 터미널 stdout 렌더 (본 cycle 에서 미관여)
 *
 * 데이터 모델 (T-505 P1 §4):
 *   Step = {id, status, startedAt, finishedAt, collapsed, userOverride, phases}
 *   Phase = {id, title, status, startedAt, finishedAt, collapsed, userOverride}
 *
 * fold/expand 자동 룰 (T-505 P1 §5):
 *   running → expand
 *   done    → fold (cascade: 모든 phase done 이면 Step 도 fold)
 *   fail    → expand + outline strong (cascade 영향 안 받음)
 *   pending → fold
 *   user click → userOverride=true (자동 룰 무시)
 *
 * 시각 캐논 (board.md §6):
 *   - terracotta #D97757 = running
 *   - cyan #4ec9b0      = success
 *   - 주홍 #f48771      = fail
 *   - 1.6s pulse + prefers-reduced-motion 가드 — step-overlay.css 정합
 *
 * SPEC §0.1 (LLM 자율 영역 비노출):
 *   spawn_mode / workers / acceptance_criteria 필드는 UI 비표시.
 *
 * Depends on: common.js (Board namespace), v2-workflow.js (subscribe API)
 * Registers:  Board.stepOverlay
 */
"use strict";

(function () {

  // ── 상수 ──

  /** Step 6박스 정의 — 순서 = 위→아래 표시 순서. */
  var STEP_IDS = ["INIT", "PLAN", "WORK", "VALIDATE", "REPORT", "DONE"];

  /** 유효 status 값. */
  var STATUS_PENDING = "pending";
  var STATUS_RUNNING = "running";
  var STATUS_DONE = "done";
  var STATUS_FAIL = "fail";

  // ── 내부 상태 ──

  /** @type {Object<string, {id, status, startedAt, finishedAt, collapsed, userOverride, phases}>} */
  var _stepMap = {};

  /** @type {HTMLElement|null} 루트 DOM */
  var _rootEl = null;

  /** @type {{close: function, sessionId: string}|null} */
  var _subscription = null;

  /** @type {string|null} */
  var _activeSessionId = null;

  // ── 초기 state ──

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

  /** SVG inline (board.md §8 — Lucide 스타일). */
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
   * 루트 DOM 게으른 생성 + 6 Step 박스 초기 렌더.
   * 외부 컨테이너 (예: terminal.html 의 wf-step-overlay-host) 가 미존재해도
   * 자체적으로 body 끝에 append.
   *
   * @param {HTMLElement} [host]  마운트 컨테이너 override
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

  // ── fold/expand 자동 룰 (T-505 P1 §5) ──

  /**
   * Step status 변경 시 자동 fold/expand 적용 (userOverride 가드).
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

    // cascade: 모든 phase done 이면 WORK Step 도 자동 fold (fail 있으면 보호)
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

  // ── Phase 동적 생성 (plan.json phases 배열 기반) ──

  /**
   * plan.json 의 phases 배열을 받아 WORK 박스 안에 sub-패널 동적 렌더.
   * spawn_mode / workers / acceptance_criteria 는 노출하지 않는다 (SPEC §0.1).
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

  // ── SSE 이벤트 핸들러 (workflow_step / phase / finish) ──

  function _onStep(data) {
    if (!data || !data.step) return;
    var stepId = String(data.step).toUpperCase();
    if (!_stepMap[stepId]) return;
    var prev = data.prev_step ? String(data.prev_step).toUpperCase() : "";
    // 직전 Step 자동 done (FAILED 가 아니면)
    if (prev && _stepMap[prev] && _stepMap[prev].status !== STATUS_FAIL) {
      _stepMap[prev].finishedAt = data.ts || null;
      _autoFoldStep(prev, STATUS_DONE);
    }
    if (stepId === "FAILED") {
      // FAILED 별칭 — 현재 Step 을 fail 마킹
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
   * v2-stdout-bridge 가 호출하는 진입점. payload.raw 가 SDK NDJSON 1줄.
   * 현재 진행 중인 Step/Phase 의 [data-wf-stdout] 컨테이너에 stdout chunk
   * 또는 tool_use 카드 1줄을 append.
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

  // ── SSE 구독 진입점 ──

  /**
   * step / phase / finish 이벤트 구독. stdout 은 v2-stdout-bridge 가 forward.
   *
   * @param {string} sessionId
   * @returns {boolean}
   */
  function subscribe(sessionId) {
    if (!sessionId) return false;
    if (!Board.v2Workflow || typeof Board.v2Workflow.subscribe !== "function") return false;
    if (_subscription && _activeSessionId === sessionId) return true;
    disconnect();
    _activeSessionId = sessionId;
    _subscription = Board.v2Workflow.subscribe(sessionId, {
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

  // ── 초기화 ──

  _resetState();

  // ── Register on Board namespace ──

  Board.stepOverlay = {
    mount: mount,
    setPhases: setPhases,
    subscribe: subscribe,
    disconnect: disconnect,
    handleStdout: handleStdout,
    // 디버그 / 테스트용
    _state: function () { return _stepMap; },
    _stepIds: STEP_IDS
  };

})();
