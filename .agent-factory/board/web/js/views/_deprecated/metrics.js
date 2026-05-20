/**
 * @module metrics
 *
 * @deprecated T-461 Phase 2 — Workflow of all chart helpers and state.js
 * Metrics This file is from Phase 3 to  deprecated/ by
 * Moves, and the current keeps only compatibility fallback.
 *
 * Tag:
 *   When Board.render.renderMetrics() is called, it will be forwarded to the Dashboard tab.
 *   common.js's switchTab(target="metrics) branch calls this function
 *   When entering Metrics tab, users will automatically see Dashboard.
 *   ? sse.js / common.js
 *   About Us
 *
 * Original file (Phase 2 earlier): 4 widgets (step duration / token stacked / FAILED rate
 * / Top regression pattern list) and module closure state (`{fetched, fetching, last, runs,
 * regression, error}`), bindToolbar(), Chart.defaults Dark Theme Set — All
 * Workflow Metrics section of dashboard.js + Board.state.metricsState Namespace
 * Complete 1:1 transfer.
 */
"use strict";

(function () {
  /**
   * @deprecated Phase 2 fallback — return to Dashboard when entering Metrics tab.
   *             The function and file itself in Phase 3 is moved to  deprecated/.
   */
  function renderMetrics() {
    if (Board.util && typeof Board.util.switchTab === "function") {
      Board.util.switchTab("dashboard");
      return;
    }
    // util.switchTab Unused (on-the-box X) — empty notice only displayed
    var el = document.getElementById("view-metrics");
    if (el) {
      el.innerHTML = '<div class="empty" style="margin-top:48px">'
        + 'Workflow Metrics is integrated into the Dashboard tab. News /div>';
    }
  }

  Board.render.renderMetrics = renderMetrics;
})();
