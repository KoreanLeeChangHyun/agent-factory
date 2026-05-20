/**
 * @module workflow-tab-storage
 *
 * T-516 — 워크플로우 탭 라이프사이클 단일 출처 (localStorage).
 *
 * 클라이언트 측 단일 진실 공급원: `localStorage['terminal.workflow.tabs']`
 * (배열 of 워크플로우 ID 문자열).
 *
 * 3 액션 단순 구조 (plan §결정):
 *   - store : 워크플로우 시작 시 add(id) — launch SSE OR submit 응답 OR 조건
 *   - render: 페이지 로드 시 get() → addTab + GET /api/v2/sessions/<id> 합성
 *   - remove: 닫기 클릭 시 remove(id) — DOM 제거와 페어
 *
 * 메인 탭 ('main') 보호: id === 'main' 입력은 no-op.
 * localStorage 손상 / quota / private mode: try/catch + silent fail + [] 반환.
 *
 * Depends on: common.js (Board namespace)
 * Registers:  Board.workflowTabStorage, window.WorkflowTabStorage
 */
"use strict";

(function () {

  /** @const {string} localStorage key — 본 모듈의 단일 출처 슬롯. */
  var STORAGE_KEY = "terminal.workflow.tabs";

  /** @const {string} 메인 탭 ID — 본 헬퍼는 메인 탭을 추적하지 않는다. */
  var MAIN_TAB_ID = "main";

  /**
   * 저장된 워크플로우 탭 ID 목록을 반환한다.
   *
   * 파싱 실패 / 손상 / quota / private mode 등 모든 오류는 silent fail
   * 후 빈 배열 반환 — 호출자는 항상 Array 를 받음을 보장.
   *
   * @returns {Array<string>}
   */
  function get() {
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed.filter(function (v) { return typeof v === "string" && v.length > 0; });
    } catch (_err) {
      return [];
    }
  }

  /**
   * 워크플로우 ID 를 저장 슬롯에 추가한다 (중복 dedupe).
   *
   * 메인 탭 ID ('main') 는 본 헬퍼 추적 대상 아님 — no-op.
   * 빈 문자열 / null / undefined / 비-문자열 입력도 no-op.
   *
   * @param {string} id - 워크플로우 ID (예: "wf-T-516-20260519-173839")
   */
  function add(id) {
    if (typeof id !== "string" || id.length === 0) return;
    if (id === MAIN_TAB_ID) return;
    try {
      var arr = get();
      if (arr.indexOf(id) !== -1) return;
      arr.push(id);
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(arr));
    } catch (_err) {
      // quota / disabled — silent fail
    }
  }

  /**
   * 워크플로우 ID 를 저장 슬롯에서 제거한다.
   *
   * 슬롯에 없는 ID 입력도 안전 (no-op).
   *
   * @param {string} id - 워크플로우 ID
   */
  function remove(id) {
    if (typeof id !== "string" || id.length === 0) return;
    try {
      var arr = get();
      var filtered = arr.filter(function (v) { return v !== id; });
      if (filtered.length === arr.length) return;
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
    } catch (_err) {
      // silent fail
    }
  }

  /**
   * 저장 슬롯 전체를 삭제한다 (follow-up 'Close All Stopped' 대비).
   *
   * 본 cycle 미사용 — API 표면만 신설.
   */
  function clear() {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch (_err) {
      // silent fail
    }
  }

  var api = {
    get: get,
    add: add,
    remove: remove,
    clear: clear,
    _STORAGE_KEY: STORAGE_KEY,
    _MAIN_TAB_ID: MAIN_TAB_ID,
  };

  // ── Register on Board namespace + window (terminal.html standalone 호환) ──
  if (typeof window !== "undefined") {
    if (typeof window.Board !== "undefined") {
      window.Board.workflowTabStorage = api;
    }
    window.WorkflowTabStorage = api;
  }
})();
