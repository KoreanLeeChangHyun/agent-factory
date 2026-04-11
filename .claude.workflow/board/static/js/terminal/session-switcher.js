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
   */
  M._saveCurrentSession = function() {
    var entry = M._sessionMap[M._activeSessionId];
    if (!entry) return;

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

    // 3. 대상 세션 상태 복원 (M.outputDiv, 변수)
    M._restoreSession(targetSessionId);

    // 4. SSE 재연결: disconnectSSE → connectSSEReady → fetchStatus
    // 세션별 last-event-id 트래커를 복원하여 탭 왕복 시 히스토리 중복 재생을 차단
    if (Board.session) {
      if (Board.session.adoptLastEventIdForSession) {
        Board.session.adoptLastEventIdForSession(targetSessionId);
      } else if (Board.session.resetLastEventId) {
        Board.session.resetLastEventId();
      }
      Board.session.disconnectSSE();
      Board.session.connectSSEReady()
        .then(function () { Board.session.fetchStatus(); })
        .catch(function () {});
    }

    // 5. phase timeline 표시/숨김
    var timelineBar = document.getElementById("wf-timeline-bar");
    if (timelineBar) {
      timelineBar.style.display = targetSessionId === "main" ? "none" : "";
    }

    // 6. UI 갱신
    M.updateControlBar();

    // 탭 바가 있으면 활성 탭 업데이트 (W01에서 구현하는 UI 훅)
    if (Board.sessionSwitcher && Board.sessionSwitcher._onSwitch) {
      Board.sessionSwitcher._onSwitch(targetSessionId, prevId);
    }

    return Promise.resolve();
  };

})();
