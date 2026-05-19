/**
 * @module dashboard
 *
 * Board SPA dashboard tab module.
 *
 * Handles dashboard data fetching from .dashboard/ markdown files,
 * KPI stats computation, Chart.js chart rendering (usage, command pie,
 * warn/error, skill frequency), and data table rendering with tabs.
 *
 * Phase 2 (T-461): Workflow Metrics 섹션을 통합한다 — metrics.js 의 4개 차트 헬퍼
 * (renderStepDurationCard / renderTokensStackedCard / renderFailRatioCard /
 * renderRegressionList) 와 모듈 클로저 state 를 이전한다.
 *   - state 는 Board.state.metricsState 네임스페이스로 승격 (W01 의 dashMetrics*
 *     4개 키를 통합 정리).
 *   - chart 인스턴스는 Board.state.metricsState.chartInstances 로 격리 (대시보드
 *     본체의 dashChartInstances 와 분리).
 *   - collapse 토글 + localStorage('wf_metrics_collapsed') 영속화.
 *   - lazy create: collapsed 상태에서는 차트를 그리지 않고, expand 시점에 비로소
 *     렌더 (Chart.js canvas 크기 0 초기화 위험 회피).
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

// ── Workflow Metrics Constants (테라코타 강조 1축) ──
const METRICS_DEFAULT_LAST = 20;
const METRICS_STEP_ORDER = ["INIT", "PLAN", "WORK", "VALIDATE", "REPORT", "DONE"];
const METRICS_ACCENT = "#D97757";
const METRICS_STEP_COLORS = {
  INIT:   "#4ec9b0",  // 청록
  PLAN:   "#dcdcaa",  // 노랑
  WORK:   METRICS_ACCENT,  // 테라코타 (가장 핵심 단계)
  VALIDATE: "#9cdcfe",  // 하늘 (work 직후 검증)
  REPORT: "#c586c0",  // 보라
  DONE:   "#858585",  // 회색
};
const METRICS_TOKEN_COLORS = {
  input:          "#569cd6",
  output:         "#4ec9b0",
  cache_creation: "#dcdcaa",
  cache_read:     "#858585",
};
const METRICS_REGRESSION_KINDS = [
  "worker_false_success",
  "hook_deny",
  "empty_bash_card",
  "stage_header_leak",
  "other",
];
const METRICS_COLLAPSE_LS_KEY = "wf_metrics_collapsed";

// ── T-462 Phase 4-A: 6-tier Pace Color 수식 ──
// claude-usage-tracker (Swift/SwiftUI) §5.4 의 projected-usage tier 함수를 advisory-only
// 시각 표시용 헬퍼로 이식. 자동 강제 / 자동 전이 / 임계값 차단 0건 — 단순 분류 함수.
// elapsedFraction < 0.03 (3% noise floor) → null 반환 (호출자가 표시 생략 결정).
// 매핑 CSS 변수: --pace-comfortable / --pace-on-track / --pace-warming / --pace-pressing
//             / --pace-critical / --pace-runaway  (dashboard.css :root 정의)
const PACE_TIER_THRESHOLDS = [
  { max: 0.5, name: "comfortable", cssVar: "--pace-comfortable" },
  { max: 0.8, name: "on-track",    cssVar: "--pace-on-track" },
  { max: 1.0, name: "warming",     cssVar: "--pace-warming" },
  { max: 1.5, name: "pressing",    cssVar: "--pace-pressing" },
  { max: 2.0, name: "critical",    cssVar: "--pace-critical" },
];
const PACE_TIER_RUNAWAY = { name: "runaway", cssVar: "--pace-runaway" };

/**
 * Computes the 6-tier pace tier for advisory-only color display.
 * @param {number} usedPercentage - tokens used as % of budget (0–100+)
 * @param {number} elapsedFraction - fraction of session window elapsed (0.0–1.0)
 * @returns {{name: string, cssVar: string, projected: number}|null}
 *   - null when elapsedFraction < 0.03 (noise floor — projection unreliable).
 *   - Otherwise the matching tier + raw projected value for tooltip rendering.
 */
function computePaceTier(usedPercentage, elapsedFraction) {
  if (typeof usedPercentage !== "number" || typeof elapsedFraction !== "number") return null;
  if (!isFinite(usedPercentage) || !isFinite(elapsedFraction)) return null;
  if (elapsedFraction < 0.03) return null;
  const projected = (usedPercentage / 100.0) / elapsedFraction;
  for (let i = 0; i < PACE_TIER_THRESHOLDS.length; i++) {
    if (projected < PACE_TIER_THRESHOLDS[i].max) {
      return {
        name: PACE_TIER_THRESHOLDS[i].name,
        cssVar: PACE_TIER_THRESHOLDS[i].cssVar,
        projected: projected,
      };
    }
  }
  return { name: PACE_TIER_RUNAWAY.name, cssVar: PACE_TIER_RUNAWAY.cssVar, projected: projected };
}

// ── Workflow Metrics State (Board.state.metricsState 네임스페이스) ──
// 모듈 클로저 대신 Board.state 로 승격하여 다른 모듈에서도 검사 가능.
// W01 의 dashMetrics{Fetched,Data,Last,Error,ChartInstances} 5개 키를 흡수한다.
(function initMetricsState() {
  const ms = Board.state.metricsState || {};
  ms.fetched = !!ms.fetched;
  ms.fetching = !!ms.fetching;
  ms.last = (typeof ms.last === "number" && ms.last > 0) ? ms.last : METRICS_DEFAULT_LAST;
  ms.data = ms.data || { runs: [], regression: null, launchLatency: null };
  ms.error = ms.error || null;
  ms.chartInstances = ms.chartInstances || {};
  // collapsed 초기값: localStorage 가 명시적으로 '0' 이 아니면 collapsed=true (default true)
  let stored = null;
  try { stored = localStorage.getItem(METRICS_COLLAPSE_LS_KEY); } catch (e) {}
  ms.collapsed = stored !== "0";
  Board.state.metricsState = ms;
})();

// ── T-462 Phase 4-B: SVG progress bar + time marker overlay ──
// usage-tracker §4-B 의 진행 바 + 현재 시각 marker overlay 컴포넌트를 SVG 로 직접
// 이식. 외부 아이콘 라이브러리 / 폰트 0건. 자동 동작 0건 — render 함수는 명시 호출만.

const SVG_NS = "http://www.w3.org/2000/svg";

/**
 * Builds an inline SVG progress bar with an optional time-marker overlay.
 * Caller passes a container DOM element which is replaced with the SVG.
 * @param {HTMLElement} container - DOM element to render into (innerHTML replaced)
 * @param {number} percent - 0~100 progress percentage
 * @param {string|null} tier - pace tier name from computePaceTier (e.g. "warming")
 *   or null/undefined to use the default accent color. When provided, fill is set to
 *   `var(--pace-<tier>)` so CSS variable wins.
 */
function renderProgressBar(container, percent, tier) {
  if (!container) return;
  const pct = Math.max(0, Math.min(100, Number(percent) || 0));
  const fillColor = tier ? "var(--pace-" + tier + ")" : "var(--pace-on-track)";
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 100 8");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", "8");
  svg.setAttribute("role", "progressbar");
  svg.setAttribute("aria-valuemin", "0");
  svg.setAttribute("aria-valuemax", "100");
  svg.setAttribute("aria-valuenow", String(Math.round(pct)));
  svg.classList.add("pace-progress-bar");
  if (tier) svg.classList.add("pace-progress-bar--" + tier);

  // Background track
  const track = document.createElementNS(SVG_NS, "rect");
  track.setAttribute("x", "0");
  track.setAttribute("y", "0");
  track.setAttribute("width", "100");
  track.setAttribute("height", "8");
  track.setAttribute("rx", "2");
  track.setAttribute("ry", "2");
  track.setAttribute("fill", "#2d2d2d");
  svg.appendChild(track);

  // Filled portion
  const fill = document.createElementNS(SVG_NS, "rect");
  fill.setAttribute("x", "0");
  fill.setAttribute("y", "0");
  fill.setAttribute("width", String(pct));
  fill.setAttribute("height", "8");
  fill.setAttribute("rx", "2");
  fill.setAttribute("ry", "2");
  fill.setAttribute("fill", fillColor);
  svg.appendChild(fill);

  // Replace container content with the new SVG
  container.innerHTML = "";
  container.appendChild(svg);
  return svg;
}

/**
 * Overlays a current-time marker (1px vertical line) on a previously-rendered
 * progress bar SVG. Position is `fraction` (0.0~1.0) along the bar.
 * Idempotent — replaces any existing marker (.pace-time-marker) in the SVG.
 * @param {HTMLElement} container - the same container used by renderProgressBar
 * @param {number} fraction - 0.0~1.0 elapsed-time fraction
 */
function renderTimeMarker(container, fraction) {
  if (!container) return;
  const svg = container.querySelector("svg.pace-progress-bar");
  if (!svg) return;
  const frac = Math.max(0, Math.min(1, Number(fraction) || 0));
  const x = frac * 100;

  // Remove old marker (idempotent)
  const old = svg.querySelector(".pace-time-marker");
  if (old) old.parentNode.removeChild(old);

  const marker = document.createElementNS(SVG_NS, "line");
  marker.classList.add("pace-time-marker");
  marker.setAttribute("x1", String(x));
  marker.setAttribute("x2", String(x));
  marker.setAttribute("y1", "-1");
  marker.setAttribute("y2", "9");
  marker.setAttribute("stroke", "#e0e0e0");
  marker.setAttribute("stroke-width", "0.6");
  marker.setAttribute("stroke-linecap", "round");
  svg.appendChild(marker);
  return marker;
}

// ── T-462 Phase 4-C: status banner (error / stale / ok) ──
// usage-tracker §4-C 의 상태 배너 (네트워크 끊김 / SSE stale / 정상) 컨셉 이식.
// SSE 재연결 로직은 core/sse.js 에 이미 있으므로 본 함수는 *표시 전용*. advisory only.

/**
 * Renders a status banner inside the given container. Idempotent —
 * existing `.status-banner` is replaced.
 * @param {HTMLElement} container - host element (innerHTML 대신 prepend / replace 사용)
 * @param {string} state - one of "error" | "stale" | "ok"
 * @param {string} message - human-readable status message
 */
function renderStatusBanner(container, state, message) {
  if (!container) return;
  const validStates = ["error", "stale", "ok"];
  const s = validStates.indexOf(state) >= 0 ? state : "ok";
  // Remove previous banner (idempotent — caller may call repeatedly on SSE events)
  const old = container.querySelector(":scope > .status-banner");
  if (old) old.parentNode.removeChild(old);

  const banner = document.createElement("div");
  banner.classList.add("status-banner");
  banner.classList.add("status-banner--" + s);
  banner.setAttribute("role", s === "error" ? "alert" : "status");

  const dot = document.createElement("span");
  dot.classList.add("status-banner__dot");
  banner.appendChild(dot);

  const text = document.createElement("span");
  text.classList.add("status-banner__text");
  text.textContent = String(message || "");
  banner.appendChild(text);

  // Prepend so banner is at top of container
  if (container.firstChild) container.insertBefore(banner, container.firstChild);
  else container.appendChild(banner);
  return banner;
}

// ── T-462 Phase 4-D: accordion expand/collapse rows (P8) ──
// usage-tracker 의 expandable row 컴포넌트를 dashboard 표시용으로 이식. 표시 토글만 —
// 자동 펼침 / 자동 접힘 / 자동 행 추가 0건. 호출자가 click handler 로 명시 호출.

/**
 * Toggles the open state of an accordion row.
 * Idempotent — adds `is-open` class when closed, removes when open.
 * Updates aria-expanded on the row's header (button[role=button]) if present.
 * @param {HTMLElement} rowElement - element carrying `.accordion__row` (or descendant button)
 */
function toggleAccordion(rowElement) {
  if (!rowElement) return;
  // Accept either the row container or a child header — climb to the row.
  let row = rowElement;
  if (!row.classList.contains("accordion__row")) {
    row = rowElement.closest(".accordion__row");
  }
  if (!row) return;
  const isOpen = row.classList.toggle("is-open");
  const header = row.querySelector(".accordion__header");
  if (header) header.setAttribute("aria-expanded", isOpen ? "true" : "false");
  const detail = row.querySelector(".accordion__detail");
  if (detail) {
    if (isOpen) detail.removeAttribute("hidden");
    else detail.setAttribute("hidden", "");
  }
  return isOpen;
}

// ── T-462 Phase 4-E: CombinedUsageChart 시간 윈도우 + 네비게이션 ──
// usage-tracker §4-E 의 시간 윈도우 (5h / 24h / 7d / 30d) + prev/current/next 네비게이션을
// chart-usage (Chart.js bar+line composite) 에 advisory-only 표시로 이식.
// 서버 변경 0건 — 기존 usage rows 를 클라이언트 측에서 timestamp 분기로 필터링.
// 자동 polling / 자동 윈도우 변경 / 자동 차단 0건.

const USAGE_CHART_WINDOWS = ["5h", "24h", "7d", "30d"];
const USAGE_CHART_WINDOW_MS = {
  "5h":  5 * 60 * 60 * 1000,
  "24h": 24 * 60 * 60 * 1000,
  "7d":  7 * 24 * 60 * 60 * 1000,
  "30d": 30 * 24 * 60 * 60 * 1000,
};

// Per-window state — 호출자가 window 와 anchor (시점 슬라이딩) 를 외부에서 변경.
// anchor=Date.now() 가 default — navigateUsageChart('prev') 시 anchor 가 window 만큼 후퇴.
(function initUsageChartState() {
  const s = Board.state.usageChartState || {};
  if (USAGE_CHART_WINDOWS.indexOf(s.window) < 0) s.window = "24h";
  if (typeof s.anchorMs !== "number" || !isFinite(s.anchorMs)) s.anchorMs = Date.now();
  Board.state.usageChartState = s;
})();

/**
 * Parses a usage row's first cell (registry_key like "20260519-053240") to epoch ms.
 * Tolerant — returns NaN on malformed input.
 * @param {string} key - registry_key style YYYYMMDD-HHMMSS
 * @returns {number} epoch ms or NaN
 */
function _parseRegistryKeyMs(key) {
  if (typeof key !== "string") return NaN;
  const m = /^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/.exec(key.trim());
  if (!m) return NaN;
  // Local-time interpretation (board runs in user's TZ).
  const d = new Date(
    parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10),
    parseInt(m[4], 10), parseInt(m[5], 10), parseInt(m[6], 10)
  );
  return d.getTime();
}

/**
 * Filters usage rows to those falling within [anchor - windowMs, anchor].
 * @param {Array<Array<string>>} rows - usage table rows (chronological recent-first)
 * @param {string} windowStr - "5h" | "24h" | "7d" | "30d"
 * @param {number} anchorMs - epoch-ms anchor (rightmost edge of window)
 * @returns {Array<Array<string>>} filtered rows in original order
 */
function filterUsageRowsByWindow(rows, windowStr, anchorMs) {
  const windowMs = USAGE_CHART_WINDOW_MS[windowStr];
  if (!windowMs || !Array.isArray(rows)) return rows || [];
  const minMs = anchorMs - windowMs;
  return rows.filter(function (cells) {
    const t = _parseRegistryKeyMs(cells[0] || "");
    if (!isFinite(t)) return false;
    return t >= minMs && t <= anchorMs;
  });
}

/**
 * Changes the active usage chart window and re-renders the chart with filtered rows.
 * advisory-only — caller dispatches; no automatic switching.
 * @param {string} windowStr - one of USAGE_CHART_WINDOWS
 */
function setUsageChartWindow(windowStr) {
  if (USAGE_CHART_WINDOWS.indexOf(windowStr) < 0) return;
  const s = Board.state.usageChartState;
  s.window = windowStr;
  // Reset anchor to "now" on window change — typical UX is "show latest in this scale".
  s.anchorMs = Date.now();
  _rerenderUsageChartForWindow();
}

/**
 * Moves the usage-chart anchor by one window-stride in the requested direction.
 * @param {string} direction - one of "prev" | "current" | "next"
 */
function navigateUsageChart(direction) {
  const s = Board.state.usageChartState;
  const windowMs = USAGE_CHART_WINDOW_MS[s.window] || USAGE_CHART_WINDOW_MS["24h"];
  if (direction === "prev") {
    s.anchorMs = s.anchorMs - windowMs;
  } else if (direction === "next") {
    s.anchorMs = Math.min(Date.now(), s.anchorMs + windowMs);
  } else if (direction === "current") {
    s.anchorMs = Date.now();
  } else {
    return;
  }
  _rerenderUsageChartForWindow();
}

/**
 * Re-renders chart-usage with the currently configured window + anchor.
 * Uses cached dashData.usage rows (no network roundtrip).
 */
function _rerenderUsageChartForWindow() {
  const data = Board.state.dashData || {};
  const allRows = dashParseMdTableRows(data.usage || "");
  const s = Board.state.usageChartState;
  const filtered = filterUsageRowsByWindow(allRows, s.window, s.anchorMs);
  renderUsageChart(filtered);
}

// ── T-462 Phase 4-F: Empty State 컴포넌트 표준화 (C6) ──
// usage-tracker §4-F 의 empty-state 패턴 (icon + title + description) 을 표준화.
// SVG icon 직접 생성 — 외부 라이브러리 0건. 자동 retry / auto-dismiss 0건.

/**
 * Default inline SVG used when caller does not provide a custom icon.
 * Lucide-style "inbox" — viewBox 24x24, stroke=currentColor, stroke-width=2.
 */
function _defaultEmptyStateIcon() {
  return ''
    + '<svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor"'
    + ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"></polyline>'
    + '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"></path>'
    + '</svg>';
}

/**
 * Renders a standardized empty state inside the container. Replaces existing content.
 * @param {HTMLElement} container - host element (innerHTML replaced)
 * @param {Object} [opts]
 * @param {string} [opts.icon] - inline SVG markup; defaults to the lucide-inbox icon
 * @param {string} [opts.title] - heading text
 * @param {string} [opts.description] - body text
 */
function renderEmptyState(container, opts) {
  if (!container) return;
  const o = opts || {};
  const iconSvg = (typeof o.icon === "string" && o.icon.trim()) ? o.icon : _defaultEmptyStateIcon();
  const title = String(o.title || "No data");
  const description = String(o.description || "");

  const wrap = document.createElement("div");
  wrap.className = "empty-state";

  const iconEl = document.createElement("div");
  iconEl.className = "empty-state__icon";
  iconEl.innerHTML = iconSvg;  // SVG markup is generated by caller or by _defaultEmptyStateIcon
  wrap.appendChild(iconEl);

  const titleEl = document.createElement("div");
  titleEl.className = "empty-state__title";
  titleEl.textContent = title;
  wrap.appendChild(titleEl);

  if (description) {
    const descEl = document.createElement("div");
    descEl.className = "empty-state__description";
    descEl.textContent = description;
    wrap.appendChild(descEl);
  }

  container.innerHTML = "";
  container.appendChild(wrap);
  return wrap;
}

// ── Fetch Functions ──

/**
 * Fetches metrics data from aggregate, regression, and launch_latency API endpoints.
 * @param {number} last - number of recent runs to aggregate
 * @returns {Promise<{runs: Array, regression: Object|null, launchLatency: Object|null}>}
 */
function fetchMetrics(last) {
  const aggUrl = "/api/metrics/aggregate?last=" + encodeURIComponent(last);
  const regUrl = "/api/metrics/regression?last=" + encodeURIComponent(last);
  const launchUrl = "/api/metrics/launch_latency?last=" + encodeURIComponent(last);
  return Promise.all([
    fetch(aggUrl, { cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error("aggregate HTTP " + res.status);
      return res.json();
    }),
    fetch(regUrl, { cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error("regression HTTP " + res.status);
      return res.json();
    }),
    fetch(launchUrl, { cache: "no-store" }).then(function (res) {
      if (!res.ok) return null;  // graceful — endpoint may 500 if T-475 not deployed
      return res.json();
    }).catch(function () { return null; }),
  ]).then(function (results) {
    const runs = (results[0] && results[0].runs) || [];
    const regression = results[1] || null;
    const launchLatency = (results[2] && results[2].ok && results[2].data) ? results[2].data : null;
    return { runs: runs, regression: regression, launchLatency: launchLatency };
  });
}

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

// ── Chart Management (Dashboard 본체 차트 — chart-usage / chart-command / chart-warn-error / chart-skills) ──

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

// ── Metrics Chart Management (Workflow Metrics 섹션 전용 — metricsState.chartInstances) ──
// 본체 차트(dashChartInstances) 와 인스턴스를 분리하여 collapse / range 변경 시
// metrics 차트만 destroy 할 수 있게 격리한다.

/** Destroys a metrics Chart instance by canvas ID. */
function destroyMetricsChart(canvasId) {
  const insts = Board.state.metricsState.chartInstances;
  if (insts[canvasId]) {
    insts[canvasId].destroy();
    delete insts[canvasId];
  }
}

/** Creates a metrics Chart.js instance tracked under metricsState.chartInstances. */
function createMetricsChart(canvasId, config) {
  if (typeof Chart === "undefined") return null;
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;
  destroyMetricsChart(canvasId);
  const instance = new Chart(canvas.getContext("2d"), config);
  Board.state.metricsState.chartInstances[canvasId] = instance;
  return instance;
}

/** Destroys all metrics chart instances (used on collapse / range change / refresh). */
function destroyAllMetricsCharts() {
  const insts = Board.state.metricsState.chartInstances;
  Object.keys(insts).forEach(function (id) {
    try { insts[id].destroy(); } catch (e) {}
  });
  Board.state.metricsState.chartInstances = {};
}

// ── Individual Chart Renderers (Dashboard 본체) ──

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

// ── Workflow Metrics — Section / Toolbar / 4 Charts ──

/** Returns an SVG chevron icon used for the Workflow Metrics collapse toggle. */
function metricsCollapseIcon(collapsed) {
  // chevron 우(접힘) / 하(펼침). Lucide 스타일, currentColor.
  if (collapsed) {
    return ''
      + '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"'
      + ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
      + '<polyline points="9 18 15 12 9 6"></polyline></svg>';
  }
  return ''
    + '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"'
    + ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<polyline points="6 9 12 15 18 9"></polyline></svg>';
}

/**
 * Returns HTML for the Workflow Metrics section (header + toolbar + 4 chart slots).
 * @returns {string} HTML
 */
function renderMetricsSection() {
  const ms = Board.state.metricsState;
  const collapsed = !!ms.collapsed;
  const lastVal = ms.last;

  let h = '<section class="dash-section dash-metrics-section' + (collapsed ? ' is-collapsed' : '') + '">';
  // Header (clickable, toggles collapse)
  h += '<h3 class="dash-section-title dash-metrics-header" id="dash-metrics-header"'
    + ' role="button" tabindex="0" aria-expanded="' + (collapsed ? 'false' : 'true') + '"'
    + ' aria-controls="dash-metrics-body">';
  h += '<span class="dash-metrics-toggle-icon" id="dash-metrics-toggle-icon">'
    + metricsCollapseIcon(collapsed) + '</span>';
  h += '<span class="dash-metrics-title-text">Workflow Metrics</span>';
  h += '</h3>';

  // Body wrapper (max-height transition)
  h += '<div class="dash-metrics-body" id="dash-metrics-body"' + (collapsed ? ' hidden' : '') + '>';

  // Toolbar
  h += '<div class="dash-metrics-toolbar">';
  h += '<label class="dash-metrics-select-label" for="dash-metrics-last-select">Range '
    + '<select id="dash-metrics-last-select" class="dash-metrics-select">';
  [5, 10, 20, 50].forEach(function (n) {
    h += '<option value="' + n + '"' + (n === lastVal ? ' selected' : '') + '>Last ' + n + '</option>';
  });
  h += '</select></label>';
  h += '<button type="button" class="dash-metrics-refresh" id="dash-metrics-refresh-btn">Refresh</button>';
  h += '</div>';

  // Status
  if (ms.error) {
    h += '<div class="dash-metrics-error">'
      + '<strong>Metrics load failed</strong><br>' + dashEsc(ms.error) + '</div>';
  } else if (ms.fetching || !ms.fetched) {
    h += '<div class="dash-metrics-loading">Loading metrics...</div>';
  }

  // 2x2 chart grid (canvases are always present in DOM when expanded; charts created lazily)
  h += '<div class="dash-metrics-grid">';
  h += '<div class="dash-metrics-card"><div class="dash-metrics-card-head">'
    + '<h4>Step Duration</h4>'
    + '<span class="dash-metrics-hint">avg ms / step (chronological)</span>'
    + '</div><div class="dash-metrics-chart-wrap">'
    + '<canvas id="dash-metrics-duration"></canvas></div></div>';
  h += '<div class="dash-metrics-card"><div class="dash-metrics-card-head">'
    + '<h4>Token Usage (stacked)</h4>'
    + '<span class="dash-metrics-hint">input / output / cache_creation / cache_read</span>'
    + '</div><div class="dash-metrics-chart-wrap">'
    + '<canvas id="dash-metrics-tokens"></canvas></div></div>';
  h += '<div class="dash-metrics-card"><div class="dash-metrics-card-head">'
    + '<h4>Fail Ratio (per step)</h4>'
    + '<span class="dash-metrics-hint">fail / count (cumulative)</span>'
    + '</div><div class="dash-metrics-chart-wrap">'
    + '<canvas id="dash-metrics-failratio"></canvas></div></div>';
  h += '<div class="dash-metrics-card dash-metrics-card--list">'
    + '<div class="dash-metrics-card-head">'
    + '<h4>Top Regression Patterns</h4>'
    + '<span class="dash-metrics-hint" id="dash-metrics-regression-scanned"></span>'
    + '</div><div class="dash-metrics-list-wrap" id="dash-metrics-regression-list"></div></div>';
  h += '</div>';  // grid

  // Launch Latency chart — full-width row below the 2x2 grid
  h += '<div class="dash-metrics-grid dash-metrics-grid--single">';
  h += '<div class="dash-metrics-card"><div class="dash-metrics-card-head">'
    + '<h4>Launch Latency (spawn_duration_ms)</h4>'
    + '<span class="dash-metrics-hint">p50 / p95 / p99 per run (ms) — activated after T-475 deployment</span>'
    + '</div>'
    + '<div id="dash-metrics-launchlatency-placeholder" class="dash-metrics-pending">'
    + 'T-475 배포 후 LAUNCH_* 이벤트가 누적되면 차트가 활성화됩니다.'
    + '</div>'
    + '<div class="dash-metrics-chart-wrap">'
    + '<canvas id="dash-metrics-launchlatency"></canvas>'
    + '</div></div>';
  h += '</div>';  // launch latency grid row

  h += '</div>';  // body
  h += '</section>';
  return h;
}

/**
 * Renders step duration line chart into #dash-metrics-duration canvas.
 * @param {Array} runs - aggregate_recent run list
 */
function renderStepDurationCard(runs) {
  if (!runs || !runs.length) return;
  const chrono = runs.slice().reverse();
  const labels = chrono.map(function (r) { return r.registry_key || ""; });
  const datasets = METRICS_STEP_ORDER.map(function (step) {
    const color = METRICS_STEP_COLORS[step] || METRICS_ACCENT;
    return {
      label: step,
      data: chrono.map(function (r) {
        const sd = (r.step_durations || {})[step];
        return sd && typeof sd.avg_ms === "number" ? Math.round(sd.avg_ms) : null;
      }),
      borderColor: color,
      backgroundColor: color,
      borderWidth: step === "WORK" ? 3 : 2,  // WORK 강조
      pointRadius: 3,
      pointBackgroundColor: color,
      tension: 0.25,
      spanGaps: true,
    };
  });
  createMetricsChart("dash-metrics-duration", {
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
function renderTokensStackedCard(runs) {
  if (!runs || !runs.length) return;
  const chrono = runs.slice().reverse();
  const labels = chrono.map(function (r) { return r.registry_key || ""; });
  const categories = ["input", "output", "cache_creation", "cache_read"];
  const datasets = categories.map(function (cat) {
    return {
      label: cat,
      data: chrono.map(function (r) { return Number((r.tokens || {})[cat] || 0); }),
      backgroundColor: METRICS_TOKEN_COLORS[cat],
      borderColor: METRICS_TOKEN_COLORS[cat],
      borderWidth: 1,
    };
  });
  createMetricsChart("dash-metrics-tokens", {
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
function renderFailRatioCard(runs) {
  if (!runs || !runs.length) return;
  const totals = {};
  METRICS_STEP_ORDER.forEach(function (s) { totals[s] = { fail: 0, count: 0 }; });
  runs.forEach(function (r) {
    const sd = r.step_durations || {};
    Object.keys(sd).forEach(function (step) {
      if (!totals[step]) totals[step] = { fail: 0, count: 0 };
      totals[step].fail += Number(sd[step].fail || 0);
      totals[step].count += Number(sd[step].count || 0);
    });
  });
  // 표시 순서: METRICS_STEP_ORDER + 그 외(있다면)
  const allSteps = METRICS_STEP_ORDER.slice();
  Object.keys(totals).forEach(function (s) {
    if (allSteps.indexOf(s) === -1) allSteps.push(s);
  });
  const ratios = allSteps.map(function (s) {
    const t = totals[s];
    if (!t || !t.count) return 0;
    return Math.round((t.fail / t.count) * 1000) / 10;  // 소수 첫째자리 % (0~100)
  });
  // 비율 0 → 청록, 양수 → 주홍 (#f48771 — 워크플로우 실패 색 컨벤션)
  const bgColors = allSteps.map(function (s) {
    return (totals[s] && totals[s].fail > 0) ? "rgba(244,135,113,0.6)" : "rgba(78,201,176,0.4)";
  });
  const borderColors = allSteps.map(function (s) {
    return (totals[s] && totals[s].fail > 0) ? "#f48771" : "#4ec9b0";
  });
  createMetricsChart("dash-metrics-failratio", {
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
              const step = ctx.label;
              const t = totals[step] || { fail: 0, count: 0 };
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
 * Renders top regression patterns list into #dash-metrics-regression-list.
 * @param {Object|null} regression - regression API response
 */
function renderRegressionList(regression) {
  const wrap = document.getElementById("dash-metrics-regression-list");
  const scannedEl = document.getElementById("dash-metrics-regression-scanned");
  if (!wrap) return;
  if (!regression || !regression.counts) {
    wrap.innerHTML = '<div class="dash-metrics-empty">No regression data</div>';
    if (scannedEl) scannedEl.textContent = "";
    return;
  }
  const counts = regression.counts || {};
  const examples = regression.examples || {};
  const sorted = METRICS_REGRESSION_KINDS.slice().sort(function (a, b) {
    return (counts[b] || 0) - (counts[a] || 0);
  });
  const scanned = (regression.scanned_keys || []).length;
  if (scannedEl) scannedEl.textContent = "scanned: " + scanned;

  const rowsHtml = sorted.map(function (kind) {
    const n = counts[kind] || 0;
    const exList = examples[kind] || [];
    const sample = exList.length > 0 ? dashEsc(exList[0]) : '<em class="dash-metrics-muted">(none)</em>';
    return ''
      + '<li class="dash-metrics-regression-row' + (n > 0 ? ' has-count' : '') + '">'
      +   '<span class="dash-metrics-regression-kind">' + dashEsc(kind) + '</span>'
      +   '<span class="dash-metrics-regression-count">' + n + '</span>'
      +   '<span class="dash-metrics-regression-example">' + sample + '</span>'
      + '</li>';
  }).join('');
  wrap.innerHTML = ''
    + '<ul class="dash-metrics-regression-list">'
    +   '<li class="dash-metrics-regression-row dash-metrics-regression-head">'
    +     '<span class="dash-metrics-regression-kind">kind</span>'
    +     '<span class="dash-metrics-regression-count">count</span>'
    +     '<span class="dash-metrics-regression-example">signal_summary example</span>'
    +   '</li>'
    +   rowsHtml
    + '</ul>';
}

/**
 * Renders launch latency line chart (p50/p95/p99) into #dash-metrics-launchlatency canvas.
 * When no LAUNCH_* events are present (T-475 not yet deployed), the placeholder message
 * remains visible and the chart renders with empty data (no error thrown).
 * @param {Object|null} launchLatency - launch_latency API response data field, or null
 */
function renderLaunchLatencyCard(launchLatency) {
  const placeholder = document.getElementById("dash-metrics-launchlatency-placeholder");
  const dist = (launchLatency && launchLatency.distribution) || {};
  const perRun = (launchLatency && launchLatency.per_run) || [];
  const hasData = launchLatency && typeof dist.count === "number" && dist.count > 0;

  // Show/hide placeholder depending on whether data is available
  if (placeholder) {
    placeholder.style.display = hasData ? "none" : "";
  }

  // Build per-run series for p50/p95/p99.
  // Each perRun entry: { registry_key, events, avg_duration_ms }.
  // When no per-run breakdown, fall back to global distribution scalars as a single point.
  var labels, p50data, p95data, p99data;

  if (hasData && perRun.length > 0) {
    // Use per-run list (oldest first — reverse so chronological left-to-right)
    const chrono = perRun.slice().reverse();
    labels = chrono.map(function (r) { return r.registry_key || ""; });
    // per_run entries only carry avg_duration_ms (scalar); p-value breakdown is global.
    // Render global p50/p95/p99 as horizontal reference lines by repeating the scalar.
    const p50 = (typeof dist.p50 === "number") ? dist.p50 : null;
    const p95 = (typeof dist.p95 === "number") ? dist.p95 : null;
    const p99 = (typeof dist.p99 === "number") ? dist.p99 : null;
    p50data = labels.map(function () { return p50; });
    p95data = labels.map(function () { return p95; });
    p99data = labels.map(function () { return p99; });
    // Overlay per-run average as a 4th dataset
    const avgData = chrono.map(function (r) {
      return (typeof r.avg_duration_ms === "number") ? Math.round(r.avg_duration_ms) : null;
    });
    // Create chart with per-run avg line + global p50/p95/p99 reference lines
    createMetricsChart("dash-metrics-launchlatency", {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "avg (per run)",
            data: avgData,
            borderColor: METRICS_ACCENT,
            backgroundColor: METRICS_ACCENT,
            borderWidth: 2,
            pointRadius: 4,
            pointBackgroundColor: METRICS_ACCENT,
            tension: 0.2,
            spanGaps: true,
          },
          {
            label: "p50 (global)",
            data: p50data,
            borderColor: "#4ec9b0",
            backgroundColor: "transparent",
            borderWidth: 1,
            borderDash: [4, 3],
            pointRadius: 0,
            tension: 0,
            spanGaps: true,
          },
          {
            label: "p95 (global)",
            data: p95data,
            borderColor: "#dcdcaa",
            backgroundColor: "transparent",
            borderWidth: 1,
            borderDash: [4, 3],
            pointRadius: 0,
            tension: 0,
            spanGaps: true,
          },
          {
            label: "p99 (global)",
            data: p99data,
            borderColor: "#f48771",
            backgroundColor: "transparent",
            borderWidth: 1,
            borderDash: [4, 3],
            pointRadius: 0,
            tension: 0,
            spanGaps: true,
          },
        ],
      },
      options: _launchLatencyChartOptions(),
    });
    return;
  }

  // No data case: render empty chart (avoids Chart.js error on missing canvas) with null points.
  // Placeholder message is shown above the canvas.
  labels = [];
  createMetricsChart("dash-metrics-launchlatency", {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        { label: "avg (per run)", data: [], borderColor: METRICS_ACCENT, backgroundColor: METRICS_ACCENT, borderWidth: 2, pointRadius: 3, tension: 0.2 },
        { label: "p50", data: [], borderColor: "#4ec9b0", backgroundColor: "transparent", borderWidth: 1, borderDash: [4, 3], pointRadius: 0, tension: 0 },
        { label: "p95", data: [], borderColor: "#dcdcaa", backgroundColor: "transparent", borderWidth: 1, borderDash: [4, 3], pointRadius: 0, tension: 0 },
        { label: "p99", data: [], borderColor: "#f48771", backgroundColor: "transparent", borderWidth: 1, borderDash: [4, 3], pointRadius: 0, tension: 0 },
      ],
    },
    options: _launchLatencyChartOptions(),
  });
}

/** Returns shared Chart.js options for the launch latency chart. */
function _launchLatencyChartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: "#cccccc", boxWidth: 12, font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: function (ctx) {
            if (ctx.parsed.y === null || ctx.parsed.y === undefined) return ctx.dataset.label + ": —";
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
  };
}

/**
 * Triggers a metrics fetch (idempotent — sets fetching flag, calls renderDashboard on resolve).
 */
function triggerMetricsFetch() {
  const ms = Board.state.metricsState;
  if (ms.fetching) return;
  ms.fetching = true;
  ms.error = null;
  fetchMetrics(ms.last).then(function (data) {
    ms.fetched = true;
    ms.fetching = false;
    // data = { runs, regression, launchLatency }
    ms.data = data;
    ms.error = null;
    renderDashboard();
  }).catch(function (err) {
    ms.fetched = true;
    ms.fetching = false;
    ms.error = String((err && err.message) || err);
    renderDashboard();
  });
}

/**
 * Renders all 5 metrics widgets (only when expanded — lazy create).
 * Caller must ensure DOM canvases exist (i.e. body is not collapsed).
 */
function renderAllMetricsWidgets() {
  const ms = Board.state.metricsState;
  if (!ms.fetched || ms.error) return;
  const data = ms.data || {};
  const runs = data.runs || [];
  const regression = data.regression || null;
  const launchLatency = data.launchLatency || null;
  renderStepDurationCard(runs);
  renderTokensStackedCard(runs);
  renderFailRatioCard(runs);
  renderRegressionList(regression);
  renderLaunchLatencyCard(launchLatency);
}

/**
 * Toggles the Workflow Metrics collapse state and persists to localStorage.
 * On expand: lazy-creates charts (canvas size 0 issue avoided since DOM is now sized).
 * On collapse: destroys charts to free memory and prevent ghost ticks.
 */
function toggleMetricsCollapse() {
  const ms = Board.state.metricsState;
  ms.collapsed = !ms.collapsed;
  try { localStorage.setItem(METRICS_COLLAPSE_LS_KEY, ms.collapsed ? "1" : "0"); } catch (e) {}

  // Update DOM in-place (avoid full renderDashboard re-entry)
  const section = document.querySelector(".dash-metrics-section");
  const body = document.getElementById("dash-metrics-body");
  const header = document.getElementById("dash-metrics-header");
  const icon = document.getElementById("dash-metrics-toggle-icon");
  if (!section || !body || !header) return;

  if (ms.collapsed) {
    section.classList.add("is-collapsed");
    body.setAttribute("hidden", "");
    header.setAttribute("aria-expanded", "false");
    if (icon) icon.innerHTML = metricsCollapseIcon(true);
    destroyAllMetricsCharts();
  } else {
    section.classList.remove("is-collapsed");
    body.removeAttribute("hidden");
    header.setAttribute("aria-expanded", "true");
    if (icon) icon.innerHTML = metricsCollapseIcon(false);
    // Lazy-create charts on expand. If data not yet fetched, kick off fetch.
    if (!ms.fetched && !ms.fetching) {
      triggerMetricsFetch();
    } else if (ms.fetched && !ms.error) {
      // requestAnimationFrame ensures the canvas has its computed layout size
      // before Chart.js measures it (avoids 0x0 canvas → fixed default 400px).
      window.requestAnimationFrame(renderAllMetricsWidgets);
    }
  }
}

/**
 * Binds metrics toolbar handlers (range select, refresh button, collapse header).
 * Called once after innerHTML replacement of #view-dashboard.
 */
function bindMetricsToolbar() {
  // Collapse toggle (clickable header — works for click + Enter/Space keyboard)
  const header = document.getElementById("dash-metrics-header");
  if (header) {
    header.addEventListener("click", toggleMetricsCollapse);
    header.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        toggleMetricsCollapse();
      }
    });
  }
  // Range select
  const sel = document.getElementById("dash-metrics-last-select");
  if (sel) {
    sel.addEventListener("change", function () {
      const n = parseInt(sel.value, 10);
      if (!Number.isFinite(n) || n <= 0) return;
      const ms = Board.state.metricsState;
      ms.last = n;
      ms.fetched = false;
      ms.data = { runs: [], regression: null, launchLatency: null };
      destroyAllMetricsCharts();
      triggerMetricsFetch();
    });
  }
  // Refresh button
  const btn = document.getElementById("dash-metrics-refresh-btn");
  if (btn) {
    btn.addEventListener("click", function () {
      const ms = Board.state.metricsState;
      ms.fetched = false;
      ms.data = { runs: [], regression: null, launchLatency: null };
      destroyAllMetricsCharts();
      triggerMetricsFetch();
    });
  }
}

// ── Main Render ──

/**
 * Main Dashboard render entry point.
 * Fetches data (first time) then renders KPI cards, chart sections,
 * data tables, and the Workflow Metrics section in a single scrollable layout.
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

  // Set Chart.js dark theme defaults (single source of truth — metrics.js no longer sets these)
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

  // Workflow Metrics section (collapsible, lazy chart create on expand)
  h += renderMetricsSection();

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

  // Render Dashboard 본체 차트 after DOM is populated
  renderUsageChart(usageRows);
  renderCommandPieChart(usageRows);
  renderWarnErrorChart(logsRows);
  renderSkillFreqChart(skillsRows);

  // Bind metrics toolbar (always — controls live in DOM whether expanded or collapsed)
  bindMetricsToolbar();

  // Render Workflow Metrics widgets only when expanded (lazy create avoids canvas-size-0 issue)
  const ms = Board.state.metricsState;
  if (!ms.collapsed) {
    if (!ms.fetched && !ms.fetching) {
      triggerMetricsFetch();
    } else if (ms.fetched && !ms.error) {
      // requestAnimationFrame: defer until layout pass completes
      window.requestAnimationFrame(renderAllMetricsWidgets);
    }
  }
}

// ── Register on Board namespace ──

Board.fetch.fetchAllDashboardFiles = fetchAllDashboardFiles;
Board.fetch.fetchMetrics = fetchMetrics;
Board.render.renderDashboard = renderDashboard;

// T-462 Phase 4-A — pace tier helper exposed for other modules + ad-hoc usage.
Board.computePaceTier = computePaceTier;

// T-462 Phase 4-B — SVG progress bar + time marker (advisory display).
Board.render.renderProgressBar = renderProgressBar;
Board.render.renderTimeMarker = renderTimeMarker;

// T-462 Phase 4-C — status banner (advisory display, SSE reconnect 로직은 core/sse.js 재사용).
Board.render.renderStatusBanner = renderStatusBanner;

// T-462 Phase 4-D — accordion expand/collapse toggle (명시 호출만, 자동 펼침 0).
Board.toggleAccordion = toggleAccordion;

// T-462 Phase 4-E — CombinedUsageChart 시간 윈도우 + 네비게이션 (advisory).
Board.setUsageChartWindow = setUsageChartWindow;
Board.navigateUsageChart = navigateUsageChart;
Board.filterUsageRowsByWindow = filterUsageRowsByWindow;

// T-462 Phase 4-F — Empty State 컴포넌트 (advisory display 표준화).
Board.render.renderEmptyState = renderEmptyState;
