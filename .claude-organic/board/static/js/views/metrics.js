/**
 * @module metrics
 *
 * @deprecated T-461 Phase 2 — 모든 차트 헬퍼와 state 가 dashboard.js 의 Workflow
 * Metrics 섹션으로 이전되었습니다. 이 파일은 Phase 3 에서 _deprecated/ 로
 * 이동되며, 현재는 호환성 fallback 만 유지합니다.
 *
 * 동작:
 *   Board.render.renderMetrics() 가 호출되면 즉시 Dashboard 탭으로 forward 한다.
 *   common.js 의 switchTab(target="metrics") 분기가 이 함수를 호출하므로
 *   Metrics 탭 진입 시 사용자는 자동으로 Dashboard 를 보게 된다.
 *   ?tab=metrics URL 진입 케이스는 Phase 3 의 sse.js / common.js 4점 처리에서
 *   처리된다.
 *
 * 본래 파일 (Phase 2 이전): 4 위젯 (단계별 duration / 토큰 stacked / FAILED 비율
 * / Top 회귀 패턴 list) 과 모듈 클로저 state (`{fetched, fetching, last, runs,
 * regression, error}`), bindToolbar(), Chart.defaults 다크 테마 설정 — 모두
 * dashboard.js 의 Workflow Metrics 섹션 + Board.state.metricsState 네임스페이스
 * 로 1:1 이전 완료.
 */
"use strict";

(function () {
  /**
   * @deprecated Phase 2 fallback — Metrics 탭 진입 시 Dashboard 로 redirect.
   *             Phase 3 에서 본 함수와 파일 자체가 _deprecated/ 로 이동된다.
   */
  function renderMetrics() {
    if (Board.util && typeof Board.util.switchTab === "function") {
      Board.util.switchTab("dashboard");
      return;
    }
    // util.switchTab 미가용 시 (이론상 발생 X) — 빈 안내만 표시
    var el = document.getElementById("view-metrics");
    if (el) {
      el.innerHTML = '<div class="empty" style="margin-top:48px">'
        + 'Workflow Metrics 는 Dashboard 탭으로 통합되었습니다.</div>';
    }
  }

  Board.render.renderMetrics = renderMetrics;
})();
