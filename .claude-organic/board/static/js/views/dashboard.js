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

// ── Fetch Functions ──

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
}

// ── Register on Board namespace ──

Board.fetch.fetchAllDashboardFiles = fetchAllDashboardFiles;
Board.render.renderDashboard = renderDashboard;
