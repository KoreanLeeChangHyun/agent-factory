/**
 * @module terminal/session-switcher
 * Split from terminal.js. Functions attach to Board._term (M) namespace.
 */
"use strict";

(function () {
  var esc = Board.util.esc;
  var M = (Board._term = Board._term || {});

  // ── Session Switcher Engine ──

  var MAX_SAVED_NODES = 5000;

  /**
   * 현재 활성 세션의 상태를 _sessionMap에 저장한다.
   *
   * T-383 Phase 1 (VUL-5 / S5): 엔트리 누락 시 early return 하면 outputNodes
   * 스냅샷이 유실되어 탭 왕복 시 메인 DOM 이 복원되지 않는 회귀가 발생한다.
   * terminal.js 초기화 블록에서 _activeSessionId 엔트리가 사전 생성되는 것이
   * 1차 방어선이며, 본 함수는 이중화된 방어선으로서 엔트리가 없으면
   * _createSessionEntry 로 즉석 생성 후 계속 진행한다 (defensive layering).
   */
  M._saveCurrentSession = function() {
    var entry = M._sessionMap[M._activeSessionId];
    if (!entry) {
      entry = M._createSessionEntry(M._activeSessionId);
      M._sessionMap[M._activeSessionId] = entry;
    }

    // M.outputDiv 자식 노드 스냅샷 (최대 MAX_SAVED_NODES개)
    if (M.outputDiv) {
      entry.outputNodes = [];
      var children = M.outputDiv.childNodes;
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
    entry.cost = M.sessionCost;
    entry.tokens = { input: M.sessionTokens.input, output: M.sessionTokens.output };
    entry.model = M.sessionModel;
    entry.status = Board.state.termStatus;
    entry.inputQueue = M.inputQueue.slice();
  };

  /**
   * 대상 세션의 상태를 활성 변수로 복원한다.
   * @param {string} targetId
   */
  M._restoreSession = function(targetId) {
    var entry = M._sessionMap[targetId];
    if (!entry) return;

    // 세션 모드 변수 업데이트
    if (targetId === "main") {
      M.workflowSessionId = null;
      M.isWorkflowMode = false;
    } else {
      M.workflowSessionId = targetId;
      M.isWorkflowMode = true;
    }

    // 입력 카드 표시/숨김 즉각 반영 (M.updateControlBar 호출 전 동기 처리)
    var inputCardEl = document.querySelector(".terminal-input-card");
    if (inputCardEl) {
      if (M.isWorkflowMode) {
        inputCardEl.classList.add("wf-input-hidden");
      } else {
        inputCardEl.classList.remove("wf-input-hidden");
      }
    }

    // 상태 변수 복원
    M.sessionCost = entry.cost;
    M.sessionTokens = { input: entry.tokens.input, output: entry.tokens.output };
    M.sessionModel = entry.model;
    Board.state.termStatus = entry.status;
    Board.state.termSessionId = targetId === "main" ? null : targetId;

    // M.inputQueue 교체 (참조를 유지하면서 내용만 교체)
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

    // M.outputDiv 복원
    if (M.outputDiv) {
      M.outputDiv.innerHTML = "";
      if (entry.outputNodes && entry.outputNodes.length > 0) {
        for (var ni = 0; ni < entry.outputNodes.length; ni++) {
          M.outputDiv.appendChild(entry.outputNodes[ni].cloneNode(true));
        }
        // 스크롤을 맨 아래로
        M.outputDiv.scrollTop = M.outputDiv.scrollHeight;
      } else {
        // 빈 세션: 초기 메시지 출력
        if (targetId === "main") {
          M.appendSystemMessage("Claude Code Terminal");
          M.appendSystemMessage('Press "Start" to begin a session.');
        } else {
          // 워크플로우 모드: "Workflow Session: ..." 메시지는 탭 바 활성 탭으로 대체
          M.appendSystemMessage("Connecting to live stream...");
        }
      }
    }
  };

  /**
   * 세션을 전환한다.
   * (a) 현재 세션 상태 저장 → (b) 대상 세션 복원 → (c) SSE 재연결 → (d) 상태바 갱신
   *
   * @param {string} targetSessionId - 전환할 세션 ID ("main" 또는 "wf-T-NNN-...")
   * @returns {Promise<void>}
   */
  M.switchSession = function(targetSessionId) {
    if (!targetSessionId) return Promise.resolve();
    if (targetSessionId === M._activeSessionId) return Promise.resolve();

    // 대상 세션이 맵에 없으면 생성
    if (!M._sessionMap[targetSessionId]) {
      M._sessionMap[targetSessionId] = M._createSessionEntry(targetSessionId);
    }

    // 1. 현재 세션 저장
    M._saveCurrentSession();

    // 2. 활성 세션 ID 변경
    var prevId = M._activeSessionId;
    M._activeSessionId = targetSessionId;

    // 3. SSE 선행 차단 (T-383 Phase 2 / VUL-1 / S4)
    // _restoreSession 이전에 disconnectSSE 를 호출하여, 복원 도중 들어오는
    // prev-session SSE 이벤트가 outputDiv 재구성 중인 DOM 에 들러붙는
    // race window 를 원천 차단한다.
    // adoptLastEventIdForSession / resetLastEventId 는 disconnectSSE 와
    // 논리적으로 묶여 있으므로(세션별 last-event-id 를 먼저 복원한 뒤
    // 연결을 끊어 from-id 재접속 의미 보존) 번들로 함께 이동시킨다.
    if (Board.session) {
      if (Board.session.adoptLastEventIdForSession) {
        Board.session.adoptLastEventIdForSession(targetSessionId);
      } else if (Board.session.resetLastEventId) {
        Board.session.resetLastEventId();
      }
      Board.session.disconnectSSE();
    }

    // 4. 대상 세션 상태 복원 (M.outputDiv, 변수)
    M._restoreSession(targetSessionId);

    // 5. SSE 재연결: 복원 완료 후 새 세션 DOM 을 대상으로 연결
    if (Board.session) {
      Board.session.connectSSEReady()
        .then(function () { Board.session.fetchStatus(); })
        .catch(function () {});
    }

    // 6. phase timeline 표시/숨김
    var timelineBar = document.getElementById("wf-timeline-bar");
    if (timelineBar) {
      timelineBar.style.display = targetSessionId === "main" ? "none" : "";
    }

    // 7. UI 갱신
    M.updateControlBar();

    // 탭 바가 있으면 활성 탭 업데이트 (W01에서 구현하는 UI 훅)
    if (Board.sessionSwitcher && Board.sessionSwitcher._onSwitch) {
      Board.sessionSwitcher._onSwitch(targetSessionId, prevId);
    }

    return Promise.resolve();
  };

})();
