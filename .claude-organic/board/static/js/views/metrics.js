/**
 * @module metrics
 *
 * Metrics 탭 — 워크플로우 metrics.jsonl 집계 시각화 (T-400 / W06).
 *
 * 4 위젯:
 *   1) 단계별 duration line chart (registryKey x축, INIT/PLAN/WORK/REPORT/DONE y축 ms)
 *   2) 토큰 사용량 stacked bar (input/output/cache_creation/cache_read 4종)
 *   3) FAILED 비율 bar (단계별 outcome=fail 비율)
 *   4) Top 회귀 패턴 list (kind 별 빈도 + signal_summary)
 *
 * 데이터 소스:
 *   GET /api/metrics/aggregate?last=20  → 최근 N개 run summary list
 *   GET /api/metrics/regression?last=20 → 회귀 패턴 빈도 + 예시
 *
 * Depends on: common.js (Board.state, Board.util.esc, Board.util.formatTokens),
 *             vendor/chart-4.5.0.min.js (Chart.js)
 *
 * 진입점:
 *   Board.render.renderMetrics()  — switchTab 에서 호출
 */
"use strict";

(function () {
  var esc = Board.util.esc;

  // ── Constants ──
  var DEFAULT_LAST = 20;             // 한 번 fetch 할 최근 run 개수
  var STEP_ORDER = ["INIT", "PLAN", "WORK", "REPORT", "DONE"];
  // 테라코타 강조색 (테마 컬러). border-left 한쪽 색상 X — 차트 stroke/legend 위주 사용.
  var ACCENT = "#D97757";
  // 단계별 duration 라인 색상 (의미 구분용 — 테라코타는 강조 1축에만 사용)
  var STEP_COLORS = {
    INIT:   "#4ec9b0",  // 청록
    PLAN:   "#dcdcaa",  // 노랑
    WORK:   ACCENT,     // 테라코타 (가장 핵심 단계)
    REPORT: "#c586c0",  // 보라
    DONE:   "#858585",  // 회색
  };
  // 토큰 카테고리 색상 (stacked bar segment)
  var TOKEN_COLORS = {
    input:          "#569cd6",
    output:         "#4ec9b0",
    cache_creation: "#dcdcaa",
    cache_read:     "#858585",
  };
  // 회귀 kind 5종 표시 순서
  var REGRESSION_KINDS = [
    "worker_false_success",
    "hook_deny",
    "empty_bash_card",
    "stage_header_leak",
    "other",
  ];

  // ── State (모듈 내부) ──
  // 탭 한 번 진입에서 fetch → 캐싱 → 재진입 시 재사용. 새로고침 버튼으로만 재fetch.
  var state = {
    fetched: false,
    fetching: false,
    last: DEFAULT_LAST,
    runs: [],          // aggregate_recent 결과 (최근순; 차트는 chrono 로 reverse)
    regression: null,  // regression_counts 결과
    error: null,
  };

  // Chart.js 인스턴스 트래킹 (canvas 재생성 시 destroy 필요)
  Board.state.metricsChartInstances = Board.state.metricsChartInstances || {};

  // ── Chart Management ──
  function destroyChart(canvasId) {
    if (Board.state.metricsChartInstances[canvasId]) {
      Board.state.metricsChartInstances[canvasId].destroy();
      delete Board.state.metricsChartInstances[canvasId];
    }
  }

  function createChart(canvasId, config) {
    if (typeof Chart === "undefined") return null;
    var canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    destroyChart(canvasId);
    var instance = new Chart(canvas.getContext("2d"), config);
    Board.state.metricsChartInstances[canvasId] = instance;
    return instance;
  }

  // ── Data Fetching ──
  function fetchAll(last) {
    state.fetching = true;
    state.error = null;
    state.last = last;
    var aggUrl = "/api/metrics/aggregate?last=" + encodeURIComponent(last);
    var regUrl = "/api/metrics/regression?last=" + encodeURIComponent(last);
    return Promise.all([
      fetch(aggUrl, { cache: "no-store" }).then(function (res) {
        if (!res.ok) throw new Error("aggregate HTTP " + res.status);
        return res.json();
      }),
      fetch(regUrl, { cache: "no-store" }).then(function (res) {
        if (!res.ok) throw new Error("regression HTTP " + res.status);
        return res.json();
      }),
    ]).then(function (results) {
      state.runs = (results[0] && results[0].runs) || [];
      state.regression = results[1] || null;
      state.fetched = true;
      state.fetching = false;
    }).catch(function (err) {
      state.error = String(err && err.message || err);
      state.fetching = false;
    });
  }

  // ── Empty State ──
  function emptyCard(title, msg) {
    return ''
      + '<section class="metrics-card metrics-card--empty">'
      +   '<header class="metrics-card-head"><h3>' + esc(title) + '</h3></header>'
      +   '<div class="metrics-card-body">'
      +     '<div class="metrics-empty">' + esc(msg) + '</div>'
      +   '</div>'
      + '</section>';
  }

  // ── Header / Toolbar ──
  function renderHeader() {
    var optsHtml = [5, 10, 20, 50].map(function (n) {
      var sel = (n === state.last) ? ' selected' : '';
      return '<option value="' + n + '"' + sel + '>최근 ' + n + '개</option>';
    }).join('');
    return ''
      + '<div class="metrics-toolbar">'
      +   '<div class="metrics-toolbar-title">'
      +     '<h2>Workflow Metrics</h2>'
      +     '<p class="metrics-subtitle">최근 워크플로우 실행 측정 지표 — 단계별 duration / 토큰 / FAILED / 회귀 패턴</p>'
      +   '</div>'
      +   '<div class="metrics-toolbar-controls">'
      +     '<label class="metrics-select-label">집계 범위 '
      +       '<select id="metrics-last-select">' + optsHtml + '</select>'
      +     '</label>'
      +     '<button type="button" class="metrics-refresh" id="metrics-refresh-btn" title="다시 집계">새로고침</button>'
      +   '</div>'
      + '</div>';
  }

  // ── Widget 1: Step Duration Line Chart ──
  function renderStepDurationCard() {
    return ''
      + '<section class="metrics-card metrics-card--chart">'
      +   '<header class="metrics-card-head">'
      +     '<h3>단계별 평균 duration</h3>'
      +     '<span class="metrics-card-hint">최근 ' + state.runs.length + '개 워크플로우 (registryKey 기준 chronological)</span>'
      +   '</header>'
      +   '<div class="metrics-card-body metrics-chart-wrap">'
      +     '<canvas id="metrics-chart-duration"></canvas>'
      +   '</div>'
      + '</section>';
  }

  function drawStepDurationChart() {
    if (!state.runs.length) return;
    // chrono (오래된 → 최근). aggregate_recent 는 최근순 (0번째가 가장 최근).
    var chrono = state.runs.slice().reverse();
    var labels = chrono.map(function (r) { return r.registry_key || ""; });

    // 단계별 데이터셋: 각 단계의 avg_ms 시계열 (단계가 비면 null)
    var datasets = STEP_ORDER.map(function (step) {
      var values = chrono.map(function (r) {
        var sd = (r.step_durations || {})[step];
        return sd && typeof sd.avg_ms === "number" ? Math.round(sd.avg_ms) : null;
      });
      var color = STEP_COLORS[step] || ACCENT;
      return {
        label: step,
        data: values,
        borderColor: color,
        backgroundColor: color,
        borderWidth: step === "WORK" ? 3 : 2,  // WORK 강조
        pointRadius: 3,
        pointBackgroundColor: color,
        tension: 0.25,
        spanGaps: true,
      };
    });

    createChart("metrics-chart-duration", {
      type: "line",
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#cccccc", boxWidth: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                if (ctx.parsed.y === null) return ctx.dataset.label + ": —";
                return ctx.dataset.label + ": " + ctx.parsed.y + " ms";
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { color: "#858585", font: { size: 10 }, maxRotation: 45 },
            grid: { color: "#2d2d2d" },
          },
          y: {
            beginAtZero: true,
            ticks: {
              color: "#858585",
              font: { size: 10 },
              callback: function (v) { return v + " ms"; },
            },
            grid: { color: "#2d2d2d" },
          },
        },
      },
    });
  }

  // ── Widget 2: Token Stacked Bar ──
  function renderTokenStackCard() {
    return ''
      + '<section class="metrics-card metrics-card--chart">'
      +   '<header class="metrics-card-head">'
      +     '<h3>토큰 사용량 (stacked)</h3>'
      +     '<span class="metrics-card-hint">input / output / cache_creation / cache_read 4종 누적</span>'
      +   '</header>'
      +   '<div class="metrics-card-body metrics-chart-wrap">'
      +     '<canvas id="metrics-chart-tokens"></canvas>'
      +   '</div>'
      + '</section>';
  }

  function drawTokenStackChart() {
    if (!state.runs.length) return;
    var chrono = state.runs.slice().reverse();
    var labels = chrono.map(function (r) { return r.registry_key || ""; });
    var categories = ["input", "output", "cache_creation", "cache_read"];
    var datasets = categories.map(function (cat) {
      return {
        label: cat,
        data: chrono.map(function (r) {
          return Number((r.tokens || {})[cat] || 0);
        }),
        backgroundColor: TOKEN_COLORS[cat],
        borderColor: TOKEN_COLORS[cat],
        borderWidth: 1,
      };
    });

    createChart("metrics-chart-tokens", {
      type: "bar",
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#cccccc", boxWidth: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ctx.dataset.label + ": " + Board.util.formatTokens(ctx.parsed.y);
              },
            },
          },
        },
        scales: {
          x: {
            stacked: true,
            ticks: { color: "#858585", font: { size: 10 }, maxRotation: 45 },
            grid: { color: "#2d2d2d" },
          },
          y: {
            stacked: true,
            beginAtZero: true,
            ticks: {
              color: "#858585",
              font: { size: 10 },
              callback: function (v) { return Board.util.formatTokens(v); },
            },
            grid: { color: "#2d2d2d" },
          },
        },
      },
    });
  }

  // ── Widget 3: FAIL Ratio Bar ──
  // 단계별 outcome=fail 비율 = sum(fail) / sum(count) — 최근 N개 run 누적.
  function renderFailRatioCard() {
    return ''
      + '<section class="metrics-card metrics-card--chart">'
      +   '<header class="metrics-card-head">'
      +     '<h3>FAILED 비율 (단계별)</h3>'
      +     '<span class="metrics-card-hint">fail / count, 최근 ' + state.runs.length + '개 워크플로우 누적</span>'
      +   '</header>'
      +   '<div class="metrics-card-body metrics-chart-wrap">'
      +     '<canvas id="metrics-chart-failratio"></canvas>'
      +   '</div>'
      + '</section>';
  }

  function drawFailRatioChart() {
    if (!state.runs.length) return;
    // 단계별 fail/count 누적
    var totals = {};
    STEP_ORDER.forEach(function (s) { totals[s] = { fail: 0, count: 0 }; });
    state.runs.forEach(function (r) {
      var sd = r.step_durations || {};
      Object.keys(sd).forEach(function (step) {
        if (!totals[step]) totals[step] = { fail: 0, count: 0 };
        totals[step].fail += Number(sd[step].fail || 0);
        totals[step].count += Number(sd[step].count || 0);
      });
    });
    // 표시 순서: STEP_ORDER + 그 외(있다면)
    var allSteps = STEP_ORDER.slice();
    Object.keys(totals).forEach(function (s) {
      if (allSteps.indexOf(s) === -1) allSteps.push(s);
    });
    var labels = allSteps;
    var ratios = allSteps.map(function (s) {
      var t = totals[s];
      if (!t || !t.count) return 0;
      return Math.round((t.fail / t.count) * 1000) / 10;  // 소수 첫째자리 % (0~100)
    });
    var bgColors = labels.map(function (s) {
      // 비율 0 → 청록, 양수 → 주홍 (#f48771 — 워크플로우 실패 색 컨벤션)
      var t = totals[s];
      var hasFail = t && t.fail > 0;
      return hasFail ? "rgba(244,135,113,0.6)" : "rgba(78,201,176,0.4)";
    });
    var borderColors = labels.map(function (s) {
      var t = totals[s];
      return (t && t.fail > 0) ? "#f48771" : "#4ec9b0";
    });

    createChart("metrics-chart-failratio", {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "Fail %",
          data: ratios,
          backgroundColor: bgColors,
          borderColor: borderColors,
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                var step = ctx.label;
                var t = totals[step] || { fail: 0, count: 0 };
                return step + ": " + ctx.parsed.y + "% (" + t.fail + "/" + t.count + ")";
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { color: "#cccccc", font: { size: 11 } },
            grid: { color: "#2d2d2d" },
          },
          y: {
            beginAtZero: true,
            max: 100,
            ticks: {
              color: "#858585",
              font: { size: 10 },
              callback: function (v) { return v + "%"; },
            },
            grid: { color: "#2d2d2d" },
          },
        },
      },
    });
  }

  // ── Widget 4: Top Regression Patterns ──
  function renderRegressionCard() {
    var reg = state.regression;
    if (!reg || !reg.counts) {
      return emptyCard("Top 회귀 패턴", "회귀 데이터가 없습니다");
    }
    var counts = reg.counts || {};
    var examples = reg.examples || {};

    // kind 정렬: count 내림차순. 0인 항목도 표시 (5종 카탈로그 일관성).
    var sorted = REGRESSION_KINDS.slice().sort(function (a, b) {
      return (counts[b] || 0) - (counts[a] || 0);
    });

    var rowsHtml = sorted.map(function (kind) {
      var n = counts[kind] || 0;
      var exList = examples[kind] || [];
      var sample = exList.length > 0 ? exList[0] : "";
      var hasFail = n > 0;
      return ''
        + '<li class="metrics-regression-row' + (hasFail ? ' has-count' : '') + '">'
        +   '<span class="metrics-regression-kind">' + esc(kind) + '</span>'
        +   '<span class="metrics-regression-count">' + n + '</span>'
        +   '<span class="metrics-regression-example">' + (sample ? esc(sample) : '<em class="metrics-muted">(예시 없음)</em>') + '</span>'
        + '</li>';
    }).join('');

    var scanned = (reg.scanned_keys || []).length;
    return ''
      + '<section class="metrics-card metrics-card--list">'
      +   '<header class="metrics-card-head">'
      +     '<h3>Top 회귀 패턴</h3>'
      +     '<span class="metrics-card-hint">스캔된 워크플로우: ' + scanned + '개</span>'
      +   '</header>'
      +   '<div class="metrics-card-body">'
      +     '<ul class="metrics-regression-list">'
      +       '<li class="metrics-regression-row metrics-regression-head">'
      +         '<span class="metrics-regression-kind">kind</span>'
      +         '<span class="metrics-regression-count">count</span>'
      +         '<span class="metrics-regression-example">signal_summary 예시</span>'
      +       '</li>'
      +       rowsHtml
      +     '</ul>'
      +   '</div>'
      + '</section>';
  }

  // ── Loading / Error ──
  function renderStatusBlock(content) {
    return '<div class="metrics-status">' + content + '</div>';
  }

  // ── Main Render ──
  function renderMetrics() {
    var el = document.getElementById("view-metrics");
    if (!el) return;

    // 첫 진입 또는 fetch 진행 중
    if (!state.fetched && !state.fetching) {
      el.innerHTML = renderHeader() + renderStatusBlock("Loading metrics...");
      bindToolbar();
      fetchAll(state.last).then(function () { renderMetrics(); });
      return;
    }
    if (state.fetching) {
      el.innerHTML = renderHeader() + renderStatusBlock("Loading metrics...");
      bindToolbar();
      return;
    }
    if (state.error) {
      el.innerHTML = renderHeader()
        + renderStatusBlock(
          '<div class="metrics-error">'
          + '<strong>집계 실패</strong><br>' + esc(state.error)
          + '</div>'
        );
      bindToolbar();
      return;
    }

    // Chart.js 다크 테마 디폴트 (idempotent)
    if (typeof Chart !== "undefined") {
      Chart.defaults.color = "#cccccc";
      Chart.defaults.borderColor = "#2d2d2d";
    }

    // 데이터 0건 (metrics.jsonl 가 아직 없는 환경) — graceful 빈 상태
    var hasRuns = state.runs && state.runs.length > 0;
    var hasRegression = state.regression
      && state.regression.counts
      && Object.keys(state.regression.counts).length > 0;

    var html = renderHeader();

    if (!hasRuns && !hasRegression) {
      html += '<div class="metrics-empty-grid">'
        + emptyCard("단계별 평균 duration", "metrics.jsonl 이 아직 기록되지 않았습니다")
        + emptyCard("토큰 사용량 (stacked)", "metrics.jsonl 이 아직 기록되지 않았습니다")
        + emptyCard("FAILED 비율 (단계별)", "metrics.jsonl 이 아직 기록되지 않았습니다")
        + emptyCard("Top 회귀 패턴", "회귀 데이터가 없습니다")
        + '</div>';
      el.innerHTML = html;
      bindToolbar();
      return;
    }

    html += '<div class="metrics-grid">';
    html += hasRuns ? renderStepDurationCard() : emptyCard("단계별 평균 duration", "데이터 없음");
    html += hasRuns ? renderTokenStackCard() : emptyCard("토큰 사용량 (stacked)", "데이터 없음");
    html += hasRuns ? renderFailRatioCard() : emptyCard("FAILED 비율 (단계별)", "데이터 없음");
    html += renderRegressionCard();
    html += '</div>';
    el.innerHTML = html;

    bindToolbar();

    // 차트 렌더는 DOM 삽입 후에 호출 (canvas 가 존재해야 함)
    if (hasRuns) {
      drawStepDurationChart();
      drawTokenStackChart();
      drawFailRatioChart();
    }
  }

  // ── Toolbar Binding ──
  function bindToolbar() {
    var sel = document.getElementById("metrics-last-select");
    if (sel) {
      sel.value = String(state.last);
      sel.addEventListener("change", function () {
        var n = parseInt(sel.value, 10);
        if (!Number.isFinite(n) || n <= 0) return;
        state.fetched = false;
        state.last = n;
        renderMetrics();
      });
    }
    var btn = document.getElementById("metrics-refresh-btn");
    if (btn) {
      btn.addEventListener("click", function () {
        state.fetched = false;
        renderMetrics();
      });
    }
  }

  // ── Public API ──
  Board.render.renderMetrics = renderMetrics;
})();
