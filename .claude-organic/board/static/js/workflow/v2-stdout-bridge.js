/**
 * @module v2-stdout-bridge
 *
 * Board.v2StdoutBridge — T-505 P2.
 *
 * V2WorkflowSSEChannel 의 workflow_stdout 이벤트를 EventSource 로 구독하여,
 * step-overlay (P3) 가 보유한 Step/Phase 위계의 stdout 컨테이너로 forward
 * 하는 단일 책임 어댑터 모듈.
 *
 * 본 모듈은 stdout 단일 채널만 다룬다. workflow_step / workflow_phase /
 * workflow_finish 는 step-overlay 가 직접 구독한다.
 *
 * 메인 session.js 는 1줄도 수정하지 않는다 (T-505 §1 결정). 본 bridge 는
 * payload.raw (NDJSON 1 line — type: assistant|tool_use|result|system|
 * rate_limit_event) 를 그대로 step-overlay.handleStdout 에 넘긴다. NDJSON
 * 분기 렌더는 step-overlay 가 자기 컨테이너에 대해 수행한다.
 *
 * Depends on: common.js (Board namespace), v2-workflow.js (subscribe API).
 *             step-overlay.js (handleStdout consumer — 같은 plan 사이클에서 P3 도입).
 * Registers:  Board.v2StdoutBridge
 *
 * Idempotent — 동일 sessionId 로 subscribe() 재호출 시 옛 구독 자동 close.
 *
 * 관련: board.md §1.2 V2WorkflowSSEChannel 의 workflow_stdout 이벤트 계약.
 */
"use strict";

(function () {

  /** @type {{close: function, sessionId: string}|null} 현재 활성 구독 핸들 */
  var _subscription = null;

  /** @type {string|null} */
  var _activeSessionId = null;

  /**
   * v2 driver session 의 workflow_stdout 이벤트를 구독한다.
   *
   * payload = {session_id, text, raw?}
   *   - raw: SDK NDJSON 원본 1줄 (type 키 보유). 가시성 8축의 핵심 데이터.
   *   - text: raw 가 없을 때의 평문 stdout chunk.
   *
   * forward target = Board.stepOverlay.handleStdout(payload). step-overlay 가
   * 현재 진행 중인 Step/Phase 의 [data-wf-stdout] 컨테이너로 렌더.
   *
   * @param {string} sessionId
   * @returns {boolean} true if subscription opened, false otherwise
   */
  function subscribe(sessionId) {
    if (!sessionId) return false;
    if (!Board.v2Workflow || typeof Board.v2Workflow.subscribe !== "function") {
      // v2-workflow.js 미로드 — script 로드 순서 회귀. terminal.html / index.html
      // script 목록 확인 필요.
      return false;
    }

    // 동일 sessionId 재구독은 의미 없음 — 이미 활성이면 그대로 반환
    if (_subscription && _activeSessionId === sessionId) return true;

    // 옛 구독 정리 (다른 sessionId 였거나 close 됐어도 idempotent)
    disconnect();

    _activeSessionId = sessionId;
    _subscription = Board.v2Workflow.subscribe(sessionId, {
      onStdout: function (data) {
        _forwardStdout(data);
      }
      // onOpen/onStep/onPhase/onFinish/onError 는 의도적으로 비움 —
      // 본 bridge 는 stdout 단일 책임. 나머지는 step-overlay 또는
      // session.js 가 별 구독으로 처리.
    });

    return true;
  }

  /**
   * payload 를 step-overlay 의 handleStdout 으로 forward.
   *
   * step-overlay 미로드 시 silent skip — script 로드 race 회피 (workflow_stdout
   * 이벤트가 step-overlay 초기화 직전 도착해도 무해).
   *
   * @param {{session_id?: string, text?: string, raw?: object}} data
   */
  function _forwardStdout(data) {
    if (!data) return;
    if (Board.stepOverlay && typeof Board.stepOverlay.handleStdout === "function") {
      try {
        Board.stepOverlay.handleStdout(data);
      } catch (err) {
        if (Board.debugLog) Board.debugLog("v2StdoutBridge.forward.error", {
          message: err && err.message,
          sessionId: _activeSessionId
        });
      }
    }
  }

  /** 현재 구독 close + 내부 상태 초기화. 이미 닫혀있어도 idempotent. */
  function disconnect() {
    if (_subscription) {
      try { _subscription.close(); } catch (_) {}
    }
    _subscription = null;
    _activeSessionId = null;
  }

  /** @returns {string|null} 현재 구독 중인 sessionId (없으면 null). */
  function activeSessionId() {
    return _activeSessionId;
  }

  /** @returns {boolean} 구독 활성 여부. */
  function isActive() {
    return _subscription !== null;
  }

  // ── Register on Board namespace ──
  Board.v2StdoutBridge = {
    subscribe: subscribe,
    disconnect: disconnect,
    activeSessionId: activeSessionId,
    isActive: isActive
  };

})();
