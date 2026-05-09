/**
 * @module dashboard
 *
 * Board SPA dashboard tab module.
 *
 * Handles dashboard data fetching from .dashboard/ markdown files,
 * KPI stats computation, Chart.js chart rendering (usage, command pie,
 * warn/error, skill frequency), and data table rendering with tabs.
 *
 * Depends on: common.js (Board.state, Board.util, Board.render)
 */
"use strict";

// ── Destructure shared utilities ──
const {
  esc: dashEsc,
  parseToken: dashParseToken,
  parseMdTableRows: dashParseMdTableRows,
  parseMdTableHeader: dashParseMdTableHeader,
  formatTokens: dashFormatTokens,
} = Board.util;

// ── Constants ──
const DASH_FILES = ["usage", "logs", "skills"];

// ── Metrics State Initialization (dashboard.js owns dashMetrics* state keys) ──
// These keys are initialized here so they are available before renderDashboard() runs.
Board.state.dashMetricsFetched = Board.state.dashMetricsFetched || false;
Board.state.dashMetricsData = Board.state.dashMetricsData || { runs: [], regression: null };
Board.state.dashMetricsLast = Board.state.dashMetricsLast || 20;
Board.state.dashMetricsError = Board.state.dashMetricsError || null;
Board.state.dashMetricsChartInstances = Board.state.dashMetricsChartInstances || {};

// ── Fetch Functions ──

/**
 * Fetches metrics data from aggregate and regression API endpoints.
 * @param {number} last - number of recent runs to aggregate
 * @returns {Promise<{runs: Array, regression: Object|null}>}
 */
function fetchMetrics(last) {
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
    var runs = (results[0] && results[0].runs) || [];
    var regression = results[1] || null;
    return { runs: runs, regression: regression };
  });
}

/**
 * Fetches a single dashboard markdown file.
 * @param {string} name - file name without extension (usage|logs|skills)
 * @returns {Promise<string>} file content or empty string on error
 */
/**
 * Fetches all dashboard files via /api/dashboard (single request).
 * @returns {Promise<Object>} the dashData object
 */
function fetchAllDashboardFiles() {
  return fetch("/api/dashboard", { cache: "no-store" }).then(function (res) {
    if (!res.ok) return Board.state.dashData;
    return res.json();
  }).then(function (data) {
    DASH_FILES.forEach(function (name) { Board.state.dashData[name] = data[name] || ""; });
    Board.state.dashFetched = true;
    return Board.state.dashData;
  }).catch(function () { return Board.state.dashData; });
}

// ── KPI Stats ──

/**
 * Computes KPI stats from raw dashboard text data.
 * @param {Object} data - { usage, logs, skills }
 * @returns {Object} stats with totalWorkflows, totalTokens, warnErrors, topSkill
 */
function computeKpiStats(data) {
  // usage.md: count rows, sum last column (total tokens)
  const usageRows = dashParseMdTableRows(data.usage || "");
  const totalWorkflows = usageRows.length;
  let totalTokens = 0;
  usageRows.forEach(function (cells) {
    const last = cells[cells.length - 1] || "-";
    totalTokens += dashParseToken(last);
  });

  // logs.md: count non-zero WARN (col 4) and ERROR (col 5)
  const logsRows = dashParseMdTableRows(data.logs || "");
  let warnErrors = 0;
  logsRows.forEach(function (cells) {
    const warn = parseInt(cells[4] || "0", 10) || 0;
    const error = parseInt(cells[5] || "0", 10) || 0;
    warnErrors += warn + error;
  });

  // skills.md: count skill occurrences, find top skill
  const skillsRows = dashParseMdTableRows(data.skills || "");
  const skillCount = {};
  skillsRows.forEach(function (cells) {
    const skillList = cells[5] || "";
    const parts = skillList.split(/<br\s*\/?>/i);
    parts.forEach(function (part) {
      const skills = part.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
      skills.forEach(function (s) {
        skillCount[s] = (skillCount[s] || 0) + 1;
      });
    });
  });
  let topSkill = "-";
  let topCount = 0;
  Object.keys(skillCount).forEach(function (s) {
    if (skillCount[s] > topCount) { topCount = skillCount[s]; topSkill = s; }
  });

  return {
    totalWorkflows: totalWorkflows,
    totalTokens: totalTokens,
    warnErrors: warnErrors,
    topSkill: topSkill,
  };
}

// ── Card / Table Rendering ──

/**
 * Renders the 4 KPI Summary Cards with left accent borders.
 * @param {Object} stats - KPI stats from computeKpiStats
 * @returns {string} HTML
 */
function renderDashCards(stats) {
  const cards = [
    { label: "Total Workflows", value: String(stats.totalWorkflows), sub: "all time", accent: "#569cd6" },
    { label: "Total Tokens", value: dashFormatTokens(stats.totalTokens), sub: "cumulative", accent: "#4ec9b0" },
    { label: "Warn / Error", value: String(stats.warnErrors), sub: "across all runs", accent: "#dcdcaa" },
    { label: "Top Skill", value: stats.topSkill, sub: "most used", accent: "#c586c0" },
  ];
  let h = '<div class="dash-cards">';
  cards.forEach(function (card) {
    h += '<div class="dash-card" style="border-left-color:' + card.accent + '">';
    h += '<div class="dash-card-label">' + dashEsc(card.label) + "</div>";
    h += '<div class="dash-card-value">' + dashEsc(card.value) + "</div>";
    h += '<div class="dash-card-sub">' + dashEsc(card.sub) + "</div>";
    h += "</div>";
  });
  h += "</div>";
  return h;
}

/**
 * Renders a markdown table from header and rows arrays to HTML table.
 * @param {Array<string>} headers
 * @param {Array<Array<string>>} rows
 * @returns {string} HTML
 */
function renderMdTable(headers, rows) {
  if (!rows || rows.length === 0) return '<div class="empty">No data</div>';
  let h = '<div class="md-body"><table>';
  h += "<thead><tr>";
  headers.forEach(function (hdr) { h += "<th>" + dashEsc(hdr) + "</th>"; });
  h += "</tr></thead>";
  h += "<tbody>";
  rows.forEach(function (cells) {
    h += "<tr>";
    cells.forEach(function (cell) {
      // Render markdown links inside cell: [text](url)
      let rendered = cell.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, text, url) {
        return '<a href="' + dashEsc(url) + '" target="_blank" rel="noopener">' + dashEsc(text) + "</a>";
      });
      // Render <br> as line break
      rendered = rendered.replace(/<br\s*\/?>/gi, "<br>");
      h += "<td>" + rendered + "</td>";
    });
    h += "</tr>";
  });
  h += "</tbody></table></div>";
  return h;
}

// ── Chart Management ──

/**
 * Destroys an existing Chart instance by canvas ID, if any.
 * @param {string} canvasId - the id attribute of the canvas element
 */
function destroyChart(canvasId) {
  if (Board.state.dashChartInstances[canvasId]) {
    Board.state.dashChartInstances[canvasId].destroy();
    delete Board.state.dashChartInstances[canvasId];
  }
}

/**
 * Creates a Chart.js instance and tracks it for later cleanup.
 * @param {string} canvasId - the id attribute of the canvas element
 * @param {Object} config - Chart.js configuration object
 * @returns {Object|null} Chart instance or null if canvas not found
 */
function createChart(canvasId, config) {
  if (typeof Chart === "undefined") return null;
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;
  destroyChart(canvasId);
  const instance = new Chart(canvas.getContext("2d"), config);
  Board.state.dashChartInstances[canvasId] = instance;
  return instance;
}

// ── Individual Chart Renderers ──

/**
 * Renders token usage bar+line composite chart.
 * @param {Array<Array<string>>} rows - parsed usage table rows
 */
function renderUsageChart(rows) {
  if (!rows.length) return;
  const chronoRows = rows.slice().reverse();
  const labels = chronoRows.map(function (c) { return c[0] || ""; });
  const values = chronoRows.map(function (c) { return dashParseToken(c[c.length - 1] || "0"); });

  createChart("chart-usage", {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Tokens",
          data: values,
          backgroundColor: "rgba(86,156,214,0.6)",
          borderColor: "#569cd6",
          borderWidth: 1,
          order: 2,
        },
        {
          label: "Trend",
          data: values,
          type: "line",
          borderColor: "#4ec9b0",
          backgroundColor: "transparent",
          borderWidth: 2,
          pointRadius: 2,
          pointBackgroundColor: "#4ec9b0",
          tension: 0.3,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#cccccc", boxWidth: 12, font: { size: 11 } } },
      },
      scales: {
        x: {
          ticks: { color: "#858585", font: { size: 10 }, maxRotation: 45 },
          grid: { color: "#2d2d2d" },
        },
        y: {
          ticks: { color: "#858585", font: { size: 10 } },
          grid: { color: "#2d2d2d" },
        },
      },
    },
  });
}

/**
 * Renders command type pie chart from usage rows.
 * @param {Array<Array<string>>} rows - parsed usage table rows
 */
function renderCommandPieChart(rows) {
  if (!rows.length) return;
  const cmdCount = {};
  rows.forEach(function (cells) {
    const cmd = (cells[3] || "other").trim().toLowerCase();
    cmdCount[cmd] = (cmdCount[cmd] || 0) + 1;
  });

  const colorMap = {
    implement: "#569cd6",
    review: "#c586c0",
    research: "#dcdcaa",
  };

  const labels = Object.keys(cmdCount);
  const values = labels.map(function (k) { return cmdCount[k]; });
  const colors = labels.map(function (k) { return colorMap[k] || "#858585"; });

  createChart("chart-command", {
    type: "pie",
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: "#1e1e1e",
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "right",
          labels: { color: "#cccccc", padding: 12, font: { size: 11 } },
        },
      },
    },
  });
}

/**
 * Renders WARN/ERROR time series line chart from logs rows.
 * @param {Array<Array<string>>} rows - parsed logs table rows
 */
function renderWarnErrorChart(rows) {
  if (!rows.length) return;
  const chronoRows = rows.slice().reverse();
  const labels = chronoRows.map(function (c) { return c[0] || ""; });
  const warns = chronoRows.map(function (c) { return parseInt(c[4] || "0", 10) || 0; });
  const errors = chronoRows.map(function (c) { return parseInt(c[5] || "0", 10) || 0; });

  createChart("chart-warn-error", {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "WARN",
          data: warns,
          borderColor: "#dcdcaa",
          backgroundColor: "rgba(220,220,170,0.1)",
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: "#dcdcaa",
          fill: true,
          tension: 0.2,
        },
        {
          label: "ERROR",
          data: errors,
          borderColor: "#f44747",
          backgroundColor: "rgba(244,71,71,0.1)",
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: "#f44747",
          fill: true,
          tension: 0.2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#cccccc", boxWidth: 12, font: { size: 11 } } },
      },
      scales: {
        x: {
          ticks: { color: "#858585", font: { size: 10 }, maxRotation: 45 },
          grid: { color: "#2d2d2d" },
        },
        y: {
          beginAtZero: true,
          ticks: { color: "#858585", font: { size: 10 } },
          grid: { color: "#2d2d2d" },
        },
      },
    },
  });
}

/**
 * Renders skill frequency horizontal bar chart from skills rows.
 * Shows top 10 most used skills.
 * @param {Array<Array<string>>} rows - parsed skills table rows
 */
function renderSkillFreqChart(rows) {
  if (!rows.length) return;
  const skillCount = {};
  rows.forEach(function (cells) {
    const skillList = cells[5] || "";
    const parts = skillList.split(/<br\s*\/?>/i);
    parts.forEach(function (part) {
      const skills = part.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
      skills.forEach(function (s) {
        skillCount[s] = (skillCount[s] || 0) + 1;
      });
    });
  });

  // Sort by count descending, take top 10
  const sorted = Object.keys(skillCount).sort(function (a, b) {
    return skillCount[b] - skillCount[a];
  }).slice(0, 10);

  const labels = sorted;
  const values = sorted.map(function (k) { return skillCount[k]; });

  createChart("chart-skills", {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        label: "Frequency",
        data: values,
        backgroundColor: "rgba(197,134,192,0.6)",
        borderColor: "#c586c0",
        borderWidth: 1,
      }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          beginAtZero: true,
          ticks: { color: "#858585", font: { size: 10 } },
          grid: { color: "#2d2d2d" },
        },
        y: {
          ticks: { color: "#cccccc", font: { size: 10 } },
          grid: { display: false },
        },
      },
    },
  });
}

// ── Main Render ──

/**
 * Main Dashboard render entry point.
 * Fetches data (first time) then renders KPI cards, chart sections,
 * and data tables in a single scrollable page layout.
 */
function renderDashboard() {
  const el = document.getElementById("view-dashboard");
  if (!el) return;

  // Show loading state before data arrives
  if (!Board.state.dashFetched) {
    el.innerHTML = '<div class="empty" style="margin-top:48px">Loading...</div>';
    fetchAllDashboardFiles().then(function () { renderDashboard(); });
    return;
  }

  // Trigger metrics data load on first render (after dashFetched)
  if (!Board.state.dashMetricsFetched) {
    fetchMetrics(Board.state.dashMetricsLast).then(function (data) {
      Board.state.dashMetricsFetched = true;
      Board.state.dashMetricsData = data;
      Board.state.dashMetricsError = null;
      renderDashboard();
    }).catch(function (err) {
      Board.state.dashMetricsFetched = true;
      Board.state.dashMetricsError = String(err && err.message || err);
      renderDashboard();
    });
  }

  // Set Chart.js dark theme defaults
  if (typeof Chart !== "undefined") {
    Chart.defaults.color = "#cccccc";
    Chart.defaults.borderColor = "#2d2d2d";
  }

  const stats = computeKpiStats(Board.state.dashData);
  let h = renderDashCards(stats);

  // Parse all data
  const usageHeaders = dashParseMdTableHeader(Board.state.dashData.usage || "");
  const usageRows = dashParseMdTableRows(Board.state.dashData.usage || "");
  const logsHeaders = dashParseMdTableHeader(Board.state.dashData.logs || "");
  const logsRows = dashParseMdTableRows(Board.state.dashData.logs || "");
  const skillsHeaders = dashParseMdTableHeader(Board.state.dashData.skills || "");
  const skillsRows = dashParseMdTableRows(Board.state.dashData.skills || "");
  // Normalize skills column: replace commas with <br> so each skill is on its own line
  skillsRows.forEach(function (cells) {
    if (cells[5]) {
      cells[5] = cells[5].split(/,\s*|<br\s*\/?>/i).filter(Boolean).join("<br>");
    }
  });

  // Charts section
  h += '<div class="dash-section">';
  h += '<h3 class="dash-section-title">Charts</h3>';
  h += '<div class="dash-chart-row">';
  h += '<div class="dash-chart-container"><canvas id="chart-usage" height="260"></canvas></div>';
  h += '<div class="dash-chart-container"><canvas id="chart-command" height="260"></canvas></div>';
  h += "</div>";
  h += '<div class="dash-chart-row">';
  h += '<div class="dash-chart-container"><canvas id="chart-warn-error" height="260"></canvas></div>';
  h += '<div class="dash-chart-container"><canvas id="chart-skills" height="260"></canvas></div>';
  h += "</div>";
  h += "</div>";

  // Tables section (tabbed)
  h += '<div class="dash-section">';
  h += '<h3 class="dash-section-title">Data</h3>';
  h += '<div class="dash-table-tabs">';
  h += '<button class="dash-table-tab active" data-table="usage">Usage</button>';
  h += '<button class="dash-table-tab" data-table="logs">Logs</button>';
  h += '<button class="dash-table-tab" data-table="skills">Skills</button>';
  h += "</div>";
  h += '<div class="dash-table-panel active" data-table="usage">' + renderMdTable(usageHeaders, usageRows) + "</div>";
  h += '<div class="dash-table-panel" data-table="logs">' + renderMdTable(logsHeaders, logsRows) + "</div>";
  h += '<div class="dash-table-panel" data-table="skills">' + renderMdTable(skillsHeaders, skillsRows) + "</div>";
  h += "</div>";

  // Workflow Metrics section (Phase 1: placeholder, Phase 2: full render)
  h += '<section class="dash-section dash-metrics-section">';
  h += '<h3 class="dash-section-title">Workflow Metrics</h3>';
  // Toolbar
  h += '<div class="dash-metrics-toolbar">';
  var lastVal = Board.state.dashMetricsLast;
  h += '<label class="dash-metrics-select-label">Range: ';
  h += '<select id="dash-metrics-last-select">';
  [5, 10, 20, 50].forEach(function (n) {
    h += '<option value="' + n + '"' + (n === lastVal ? ' selected' : '') + '>Last ' + n + '</option>';
  });
  h += '</select></label>';
  h += '<button type="button" id="dash-metrics-refresh-btn">Refresh</button>';
  h += '</div>';
  // Status / error
  if (Board.state.dashMetricsError) {
    h += '<div class="dash-metrics-error">Metrics load failed: ' + dashEsc(Board.state.dashMetricsError) + '</div>';
  } else if (!Board.state.dashMetricsFetched) {
    h += '<div class="dash-metrics-loading">Loading metrics...</div>';
  }
  // 4 chart canvases (2x2 grid)
  h += '<div class="dash-metrics-grid">';
  h += '<div class="dash-metrics-chart-wrap"><canvas id="dash-metrics-duration"></canvas></div>';
  h += '<div class="dash-metrics-chart-wrap"><canvas id="dash-metrics-tokens"></canvas></div>';
  h += '<div class="dash-metrics-chart-wrap"><canvas id="dash-metrics-failratio"></canvas></div>';
  h += '<div class="dash-metrics-chart-wrap" id="dash-metrics-regression-list"></div>';
  h += '</div>';
  h += '</section>';

  el.innerHTML = h;

  // Wire up table tab switching
  el.querySelectorAll(".dash-table-tab").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const target = btn.getAttribute("data-table");
      el.querySelectorAll(".dash-table-tab").forEach(function (b) { b.classList.remove("active"); });
      el.querySelectorAll(".dash-table-panel").forEach(function (p) { p.classList.remove("active"); });
      btn.classList.add("active");
      el.querySelector('.dash-table-panel[data-table="' + target + '"]').classList.add("active");
    });
  });

  // Render charts after DOM is populated
  renderUsageChart(usageRows);
  renderCommandPieChart(usageRows);
  renderWarnErrorChart(logsRows);
  renderSkillFreqChart(skillsRows);

  // Render metrics widgets (if data is available)
  if (Board.state.dashMetricsFetched && !Board.state.dashMetricsError) {
    var mData = Board.state.dashMetricsData;
    var runs = (mData && mData.runs) || [];
    var regression = (mData && mData.regression) || null;
    renderDashMetricsDuration(runs);
    renderDashMetricsTokens(runs);
    renderDashMetricsFailRatio(runs);
    renderDashMetricsRegression(regression);
  }

  // Bind metrics toolbar
  bindDashMetricsToolbar();
}

// ── Metrics Widget Helpers (Phase 1: minimal inline — Phase 2: replaced by merged metrics.js helpers) ──

// Constants (mirrors metrics.js — Phase 2 will deduplicate)
var DASH_METRICS_STEP_ORDER = ["INIT", "PLAN", "WORK", "REPORT", "DONE"];
var DASH_METRICS_ACCENT = "#D97757";
var DASH_METRICS_STEP_COLORS = {
  INIT:   "#4ec9b0",
  PLAN:   "#dcdcaa",
  WORK:   DASH_METRICS_ACCENT,
  REPORT: "#c586c0",
  DONE:   "#858585",
};
var DASH_METRICS_TOKEN_COLORS = {
  input:          "#569cd6",
  output:         "#4ec9b0",
  cache_creation: "#dcdcaa",
  cache_read:     "#858585",
};
var DASH_METRICS_REGRESSION_KINDS = [
  "worker_false_success",
  "hook_deny",
  "empty_bash_card",
  "stage_header_leak",
  "other",
];

/**
 * Renders step duration line chart into #dash-metrics-duration canvas.
 * @param {Array} runs - aggregate_recent run list
 */
function renderDashMetricsDuration(runs) {
  if (!runs || !runs.length) return;
  var chrono = runs.slice().reverse();
  var labels = chrono.map(function (r) { return r.registry_key || ""; });
  var datasets = DASH_METRICS_STEP_ORDER.map(function (step) {
    var color = DASH_METRICS_STEP_COLORS[step] || DASH_METRICS_ACCENT;
    return {
      label: step,
      data: chrono.map(function (r) {
        var sd = (r.step_durations || {})[step];
        return sd && typeof sd.avg_ms === "number" ? Math.round(sd.avg_ms) : null;
      }),
      borderColor: color,
      backgroundColor: color,
      borderWidth: step === "WORK" ? 3 : 2,
      pointRadius: 3,
      pointBackgroundColor: color,
      tension: 0.25,
      spanGaps: true,
    };
  });
  createChart("dash-metrics-duration", {
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
        x: { ticks: { color: "#858585", font: { size: 10 }, maxRotation: 45 }, grid: { color: "#2d2d2d" } },
        y: {
          beginAtZero: true,
          ticks: { color: "#858585", font: { size: 10 }, callback: function (v) { return v + " ms"; } },
          grid: { color: "#2d2d2d" },
        },
      },
    },
  });
}

/**
 * Renders token usage stacked bar chart into #dash-metrics-tokens canvas.
 * @param {Array} runs - aggregate_recent run list
 */
function renderDashMetricsTokens(runs) {
  if (!runs || !runs.length) return;
  var chrono = runs.slice().reverse();
  var labels = chrono.map(function (r) { return r.registry_key || ""; });
  var categories = ["input", "output", "cache_creation", "cache_read"];
  var datasets = categories.map(function (cat) {
    return {
      label: cat,
      data: chrono.map(function (r) { return Number((r.tokens || {})[cat] || 0); }),
      backgroundColor: DASH_METRICS_TOKEN_COLORS[cat],
      borderColor: DASH_METRICS_TOKEN_COLORS[cat],
      borderWidth: 1,
    };
  });
  createChart("dash-metrics-tokens", {
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
        x: { stacked: true, ticks: { color: "#858585", font: { size: 10 }, maxRotation: 45 }, grid: { color: "#2d2d2d" } },
        y: {
          stacked: true,
          beginAtZero: true,
          ticks: { color: "#858585", font: { size: 10 }, callback: function (v) { return Board.util.formatTokens(v); } },
          grid: { color: "#2d2d2d" },
        },
      },
    },
  });
}

/**
 * Renders fail ratio bar chart into #dash-metrics-failratio canvas.
 * @param {Array} runs - aggregate_recent run list
 */
function renderDashMetricsFailRatio(runs) {
  if (!runs || !runs.length) return;
  var totals = {};
  DASH_METRICS_STEP_ORDER.forEach(function (s) { totals[s] = { fail: 0, count: 0 }; });
  runs.forEach(function (r) {
    var sd = r.step_durations || {};
    Object.keys(sd).forEach(function (step) {
      if (!totals[step]) totals[step] = { fail: 0, count: 0 };
      totals[step].fail += Number(sd[step].fail || 0);
      totals[step].count += Number(sd[step].count || 0);
    });
  });
  var allSteps = DASH_METRICS_STEP_ORDER.slice();
  Object.keys(totals).forEach(function (s) {
    if (allSteps.indexOf(s) === -1) allSteps.push(s);
  });
  var ratios = allSteps.map(function (s) {
    var t = totals[s];
    if (!t || !t.count) return 0;
    return Math.round((t.fail / t.count) * 1000) / 10;
  });
  var bgColors = allSteps.map(function (s) {
    return (totals[s] && totals[s].fail > 0) ? "rgba(244,135,113,0.6)" : "rgba(78,201,176,0.4)";
  });
  var borderColors = allSteps.map(function (s) {
    return (totals[s] && totals[s].fail > 0) ? "#f48771" : "#4ec9b0";
  });
  createChart("dash-metrics-failratio", {
    type: "bar",
    data: {
      labels: allSteps,
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
        x: { ticks: { color: "#cccccc", font: { size: 11 } }, grid: { color: "#2d2d2d" } },
        y: {
          beginAtZero: true,
          max: 100,
          ticks: { color: "#858585", font: { size: 10 }, callback: function (v) { return v + "%"; } },
          grid: { color: "#2d2d2d" },
        },
      },
    },
  });
}

/**
 * Renders top regression patterns list into #dash-metrics-regression-wrap.
 * @param {Object|null} regression - regression API response
 */
function renderDashMetricsRegression(regression) {
  var wrap = document.getElementById("dash-metrics-regression-list");
  if (!wrap) return;
  if (!regression || !regression.counts) {
    wrap.innerHTML = '<div class="dash-metrics-empty">No regression data</div>';
    return;
  }
  var counts = regression.counts || {};
  var examples = regression.examples || {};
  var sorted = DASH_METRICS_REGRESSION_KINDS.slice().sort(function (a, b) {
    return (counts[b] || 0) - (counts[a] || 0);
  });
  var scanned = (regression.scanned_keys || []).length;
  var rowsHtml = sorted.map(function (kind) {
    var n = counts[kind] || 0;
    var exList = examples[kind] || [];
    var sample = exList.length > 0 ? dashEsc(exList[0]) : '<em>(none)</em>';
    return '<li class="dash-metrics-regression-row' + (n > 0 ? ' has-count' : '') + '">'
      + '<span class="dash-metrics-regression-kind">' + dashEsc(kind) + '</span>'
      + '<span class="dash-metrics-regression-count">' + n + '</span>'
      + '<span class="dash-metrics-regression-example">' + sample + '</span>'
      + '</li>';
  }).join('');
  wrap.innerHTML = '<div class="dash-metrics-regression-header">Top Regression Patterns <span class="dash-metrics-scanned">(scanned: ' + scanned + ')</span></div>'
    + '<ul class="dash-metrics-regression-list">'
    + '<li class="dash-metrics-regression-row dash-metrics-regression-head">'
    + '<span class="dash-metrics-regression-kind">kind</span>'
    + '<span class="dash-metrics-regression-count">count</span>'
    + '<span class="dash-metrics-regression-example">example</span>'
    + '</li>'
    + rowsHtml
    + '</ul>';
}

/**
 * Binds dashboard metrics toolbar (range select + refresh button).
 */
function bindDashMetricsToolbar() {
  var sel = document.getElementById("dash-metrics-last-select");
  if (sel) {
    sel.addEventListener("change", function () {
      var n = parseInt(sel.value, 10);
      if (!Number.isFinite(n) || n <= 0) return;
      Board.state.dashMetricsLast = n;
      Board.state.dashMetricsFetched = false;
      Board.state.dashMetricsData = { runs: [], regression: null };
      renderDashboard();
    });
  }
  var btn = document.getElementById("dash-metrics-refresh-btn");
  if (btn) {
    btn.addEventListener("click", function () {
      Board.state.dashMetricsFetched = false;
      Board.state.dashMetricsData = { runs: [], regression: null };
      renderDashboard();
    });
  }
}

// ── Register on Board namespace ──

Board.fetch.fetchAllDashboardFiles = fetchAllDashboardFiles;
Board.fetch.fetchMetrics = fetchMetrics;
Board.render.renderDashboard = renderDashboard;
