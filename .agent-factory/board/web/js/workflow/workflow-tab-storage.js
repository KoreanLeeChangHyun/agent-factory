/**
 * @module workflow-tab-storage
 *
 * T-516 — Workflow Tab Lifecycle Single Source (localStorage).
 *
 * client side single true source: `localStorage['terminal.workflow.tabs']`
 * (battery of workflow ID string).
 *
 * 3 Action Simulation Structure (plan § Crystal):
 *   - store : add(id) when workflow starts — launch SSE OR submit response OR condition
 *   - render: get() → addTab + GET /api/v2/sessions/<id> synthesis when page load
 *   - remove: remove(id) — remove DOM and pair
 *
 * Main tab ('main') protection: id === 'main' input is no-op.
 * localStorage / quota / private mode: try/catch + silent fail + [] return.
 *
 * Depends on: common.js (Board namespace)
 * Registers:  Board.workflowTabStorage, window.WorkflowTabStorage
 */
"use strict";

(function () {

  /** @const {string} localStorage key — single source slot of this module. */
  var STORAGE_KEY = "terminal.workflow.tabs";

  /** @const {string} Main Tab ID — This Helper does not track the main tab. */
  var MAIN_TAB_ID = "main";

  /**
   * Returns the saved workflow tab ID list.
   *
   * Failure to parse / corruption / quota / private mode, etc.
   * After empty array return — the caller always guarantees Array.
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
   * Add the workflow ID to the slot (recovery dedupe).
   *
   * The main tab ID ('main') is not the target of this heap — no-op.
   * empty strings / null / undefined / non-string input also no-op.
   *
   * @param {string} id - Workflow ID (e.g. "wf-T-516-20260519-173839")
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
   * Remove workflow ID from the storage slot.
   *
   * ID input and safety without slots (no-op).
   *
   * @param {string} id - Workflow ID
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
   * Delete the entire storage slot (follow-up 'Close All Stopped').
   *
   * This cycle unused — only the API surface.
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

  // ── Register on Board namespace + window (terminal.html standalone compatible) ──
  if (typeof window !== "undefined") {
    if (typeof window.Board !== "undefined") {
      window.Board.workflowTabStorage = api;
    }
    window.WorkflowTabStorage = api;
  }
})();
