/**
 * @module workflow
 *
 * Board SPA workflow tab module.
 *
 * Handles workflow data fetching, table rendering, search/sort/pagination,
 * detail view, column resize, and ticket-workflow linkage functions.
 *
 * Depends on: common.js (Board.state, Board.util, Board.render, Board.fetch)
 */
"use strict";

// ── Destructure shared utilities ──
const {
  esc: wfEsc,
  badge: wfBadge,
  formatTime: wfFormatTime,
  parseDirLinks: wfParseDirLinks,
  lastSegment: wfLastSegment,
  resolveResultPath: wfResolveResultPath,
  projectRoot: wfProjectRoot,
  CMD_COLORS: WF_CMD_COLORS,
  STATUS_COLORS: WF_STATUS_COLORS,
  saveUI: wfSaveUI,
  switchTab: wfSwitchTab,
} = Board.util;

// ── Constants ──

/** Files to show as indicators in workflow table columns. */
const WF_FILES = [
  { key: "query",   file: "user_prompt.txt", label: "query" },
  { key: "plan",    file: "plan.md",         label: "plan" },
  { key: "report",  file: "report.md",       label: "report" },
  { key: "summary", file: "summary.txt",     label: "summary" },
  { key: "usage",   file: "usage.json",      label: "usage" },
  { key: "log",     file: "workflow.log",     label: "log" },
];

const WF_FILE_COLS = ["query", "plan", "work", "report", "summary", "usage", "log"];
const WF_PAGE_SIZE = 50;

// ── Fetch Functions ──

/**
 * Fetches workflow entry list via /api/workflow/entries (single request).
 * Returns sorted hrefs (newest first), no detail fetched yet.
 * @returns {Promise<string[]>}
 */
function fetchWorkflowEntries() {
  return fetch("/api/workflow/entries", { cache: "no-store" }).then(function (res) {
    if (!res.ok) return [];
    return res.json();
  }).catch(function () { return []; });
}

/**
 * Fetches detailed info for a single workflow entry via /api/workflow/detail.
 * @param {string} entryHref - relative path of the entry (e.g. ".claude-organic/runs/20260325-150854/")
 * @returns {Promise<Array>} flat array of workflow item objects
 */
function fetchEntryDetail(entryHref) {
  return fetch("/api/workflow/detail?entry=" + encodeURIComponent(entryHref), { cache: "no-store" }).then(function (res) {
    if (!res.ok) return [];
    return res.json();
  }).catch(function () { return []; });
}

// ── Ticket-Workflow Linkage ──

/**
 * Finds the ticket linked to a given workflow entry by matching workdir or registrykey.
 * @param {Object} w - workflow item
 * @returns {Object|null} matched ticket or null
 */
function findTicketForWorkflow(w) {
  const basePath = w.basePath || "";
  const entry = w.entry || "";
  const wfTicket = (w.ticketNumber || "").trim();
  const tickets = Board.state.TICKETS;
  if (!Array.isArray(tickets) || tickets.length === 0) return null;
  // 1차: 칸반 ticket.result.workdir / registrykey 매칭
  for (let ti = 0; ti < tickets.length; ti++) {
    const ticket = tickets[ti];
    const result = ticket.result;
    if (!result) continue;
    if (result.workdir) {
      let wd = result.workdir;
      if (wd.charAt(wd.length - 1) !== "/") wd += "/";
      const normalized = "../" + wd;
      const normalizedResolved = "../" + wfResolveResultPath(wd);
      if (decodeURIComponent(normalized) === decodeURIComponent(basePath)
          || decodeURIComponent(normalizedResolved) === decodeURIComponent(basePath)) return ticket;
    }
    if (result.registrykey && entry && result.registrykey === entry) {
      return ticket;
    }
  }
  // 2차 fallback: 워크플로우 .context.json 의 ticketNumber 로 칸반 lookup
  if (wfTicket) {
    for (let ti = 0; ti < tickets.length; ti++) {
      const tn = (tickets[ti].number || "").trim();
      if (tn === wfTicket) return tickets[ti];
    }
  }
  return null;
}

/**
 * Returns array of workflows linked from a ticket via its result field.
 * @param {Object} ticket - ticket data object
 * @returns {Array} matched workflow items
 */
function findWorkflowsForTicket(ticket) {
  const found = [];
  const result = ticket.result;
  if (!result) return found;
  const workflows = Board.state.WORKFLOWS;
  for (let wi = 0; wi < workflows.length; wi++) {
    const w = workflows[wi];
    // Match by workdir path
    if (result.workdir) {
      let wd = result.workdir;
      if (wd.charAt(wd.length - 1) !== "/") wd += "/";
      const normalized = "../" + wd;
      const normalizedResolved = "../" + wfResolveResultPath(wd);
      if (decodeURIComponent(normalized) === decodeURIComponent(w.basePath || "")
          || decodeURIComponent(normalizedResolved) === decodeURIComponent(w.basePath || "")) {
        found.push(w);
        continue;
      }
    }
    // Fallback: match by registrykey
    if (result.registrykey && w.entry && result.registrykey === w.entry) {
      found.push(w);
    }
  }
  return found;
}

// ── Search / Sort / Pagination ──

/** Filters workflow list by current search query. */
function filterWorkflows(list) {
  const query = Board.state.wfSearchQuery;
  if (!query) return list;
  const q = query.toLowerCase();
  // 티켓 번호 검색 정규화: "T-446" / "t-446" / "446" 모두 지원하기 위해
  // 입력이 숫자 + 하이픈만으로 구성되면 "T-" prefix 매칭도 허용한다.
  const qDigit = q.replace(/^t-?/, "");
  return list.filter(function (w) {
    if (w.task.toLowerCase().indexOf(q) !== -1) return true;
    if (w.command.toLowerCase().indexOf(q) !== -1) return true;
    if (w.step.toLowerCase().indexOf(q) !== -1) return true;
    if (w.entry.indexOf(q) !== -1) return true;
    // 티켓 번호 매칭: 1차 응답 ticketNumber → 2차 findTicketForWorkflow (workdir/registrykey fallback)
    const tn = (w.ticketNumber || "").toLowerCase();
    if (tn && (tn.indexOf(q) !== -1 || (qDigit && tn.indexOf(qDigit) !== -1))) return true;
    const linked = findTicketForWorkflow(w);
    if (linked) {
      const ln = (linked.number || "").toLowerCase();
      if (ln && (ln.indexOf(q) !== -1 || (qDigit && ln.indexOf(qDigit) !== -1))) return true;
    }
    return false;
  });
}

/** Sorts workflow list by current sort key and direction. */
function sortWorkflows(list) {
  const key = Board.state.wfSortKey;
  const dir = Board.state.wfSortDir === "asc" ? 1 : -1;
  return list.slice().sort(function (a, b) {
    let av, bv;
    if (key === "ticket") {
      const at = findTicketForWorkflow(a);
      const bt = findTicketForWorkflow(b);
      av = at ? at.number : "";
      bv = bt ? bt.number : "";
    } else {
      av = (a[key] || "").toString();
      bv = (b[key] || "").toString();
    }
    return dir * av.localeCompare(bv);
  });
}

/** Loads the next batch of workflow entries and renders them. */
function loadMoreWorkflows() {
  if (Board.state.wfLoading || Board.state.wfLoadedIndex >= Board.state.wfEntryHrefs.length) return;
  Board.state.wfLoading = true;
  const batch = Board.state.wfEntryHrefs.slice(Board.state.wfLoadedIndex, Board.state.wfLoadedIndex + WF_PAGE_SIZE);
  Board.state.wfLoadedIndex += batch.length;
  updateWfStatus();
  Promise.all(batch.map(fetchEntryDetail)).then(function (results) {
    const newItems = [];
    results.forEach(function (items) {
      items.forEach(function (w) { Board.state.WORKFLOWS.push(w); newItems.push(w); });
    });
    Board.state.WORKFLOWS.sort(function (a, b) { return b.updated_at.localeCompare(a.updated_at); });
    Board.state.wfLoading = false;
    if (!Board.state.wfInitialized) {
      Board.state.wfInitialized = true;
      renderWorkflow();
    } else {
      appendWfRows(filterWorkflows(newItems));
      updateWfStatus();
      attachWfSentinel();
    }
  });
}

/** Updates the workflow count display in the search bar. */
function updateWfStatus() {
  const countEl = document.querySelector(".wf-search-count");
  const hasMore = Board.state.wfLoadedIndex < Board.state.wfEntryHrefs.length;
  if (countEl) {
    const filtered = filterWorkflows(Board.state.WORKFLOWS);
    countEl.textContent = filtered.length + (hasMore ? "+" : "") + " / " + Board.state.wfEntryHrefs.length;
  }
}

// ── Table Row Rendering ──

/**
 * Renders a single workflow item as a table row.
 * @param {Object} w - workflow item
 * @returns {string} HTML tr element
 */
function renderWfCard(w) {
  let h = '<tr class="wf-row" data-entry="' + wfEsc(w.entry) + '" data-task="' + wfEsc(w.task) + '" data-cmd="' + wfEsc(w.command) + '">';
  // step cell
  const stepIsDone = (w.step || "").toUpperCase() === "DONE";
  const stepColors = stepIsDone ? WF_STATUS_COLORS.Done : WF_STATUS_COLORS["In Progress"];
  const stepText = wfEsc(w.step || "NONE");
  const stepBadge = '<span class="badge wf-step-badge" style="background:' + stepColors.bg + ";color:" + stepColors.fg + '">' + stepText + "</span>";
  h += '<td class="wf-row-step">' + stepBadge + "</td>";
  // ticket cell: linked ticket badge (룰: 워크플로우는 반드시 티켓에 매핑)
  const linkedTicket = findTicketForWorkflow(w);
  if (linkedTicket) {
    h += '<td class="wf-row-number"><span class="wf-number-badge wf-ticket-badge" data-ticket-num="' + wfEsc(linkedTicket.number) + '">' + wfEsc(linkedTicket.number) + "</span></td>";
  } else {
    h += '<td class="wf-row-number"><span class="wf-number-fallback" title="티켓 매핑 없음 (룰 위반)">(미연결)</span></td>';
  }
  // command cell
  h += '<td class="wf-row-cmd">' + wfBadge(w.command, WF_CMD_COLORS[w.command] || { bg: "rgba(133,133,133,0.25)", fg: "#a0a0a0" }) + "</td>";
  // task cell
  h += '<td class="wf-row-title">' + wfEsc(w.task) + "</td>";
  // file indicator cells
  WF_FILE_COLS.forEach(function (key) {
    const info = w.fileMap && w.fileMap[key];
    if (info && info.exists) {
      const isDir = info.isDir ? ' data-isdir="true"' : "";
      h += '<td class="wf-row-file"><span class="wf-file-indicator active" data-label="' + wfEsc(w.task + " / " + key) + '" data-url="' + wfEsc(info.url) + '"' + isDir + ">&#9679;</span></td>";
    } else {
      h += '<td class="wf-row-file"><span class="wf-file-indicator">&#9675;</span></td>';
    }
  });
  // updated_at cell
  h += '<td class="wf-row-time">' + wfEsc(w.updated_at.substring(0, 16)) + "</td>";
  h += "</tr>";
  return h;
}

/** Appends new workflow rows to the existing table body. */
function appendWfRows(items) {
  const list = document.getElementById("wf-list");
  if (!list) return;
  // Remove sentinel/loading
  const sentinel = document.getElementById("wf-sentinel");
  if (sentinel) sentinel.remove();
  const loading = list.querySelector(".empty");
  if (loading) {
    const emptyRow = loading.closest("tr");
    if (emptyRow) emptyRow.remove(); else loading.remove();
  }
  // Append new rows using table wrapper to avoid <tr> auto-lifting by browser
  const temp = document.createElement("table");
  const tbody = document.createElement("tbody");
  temp.appendChild(tbody);
  let h = "";
  items.forEach(function (w) { h += renderWfCard(w); });
  tbody.innerHTML = h;
  while (tbody.firstChild) {
    list.appendChild(tbody.firstChild);
  }
  bindWfFileLinks(list);
  bindWfRowClicks(list);
}

/** Attaches or refreshes the infinite scroll sentinel at the bottom of the table. */
function attachWfSentinel() {
  const list = document.getElementById("wf-list");
  if (!list) return;
  const hasMore = Board.state.wfLoadedIndex < Board.state.wfEntryHrefs.length;
  // Remove old sentinel
  const old = document.getElementById("wf-sentinel");
  if (old) {
    const oldRow = old.closest("tr") || old;
    oldRow.remove();
  }
  if (Board.state.wfLoading) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.setAttribute("colspan", "12");
    td.className = "empty";
    td.textContent = "Loading...";
    tr.appendChild(td);
    list.appendChild(tr);
  } else if (hasMore) {
    const str = document.createElement("tr");
    const std = document.createElement("td");
    std.setAttribute("colspan", "12");
    std.className = "wf-load-more";
    std.id = "wf-sentinel";
    std.textContent = "Scroll for more";
    str.appendChild(std);
    list.appendChild(str);
    const observer = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) {
        observer.disconnect();
        loadMoreWorkflows();
      }
    });
    observer.observe(std);
  }
}

// ── Event Binding ──

/** Binds click handlers on workflow file indicator links. */
function bindWfFileLinks(container) {
  container.querySelectorAll(".wf-file-indicator.active:not([data-bound])").forEach(function (link) {
    link.setAttribute("data-bound", "1");
    link.addEventListener("click", function (e) {
      e.stopPropagation();
      const isDir = link.dataset.isdir === "true";
      Board.render.openWfFile(link.dataset.label, link.dataset.url, isDir);
    });
  });
}

/** Binds click handlers on workflow table rows and ticket badges. */
function bindWfRowClicks(container) {
  container.querySelectorAll(".wf-row:not([data-row-bound])").forEach(function (row) {
    row.setAttribute("data-row-bound", "1");
    row.addEventListener("click", function (e) {
      if (e.target.closest(".wf-file-indicator.active")) return;
      if (e.target.closest(".wf-ticket-badge")) return;
      const entryKey = row.dataset.entry;
      const taskKey = row.dataset.task;
      const cmdKey = row.dataset.cmd;
      const w = Board.state.WORKFLOWS.find(function (item) {
        return item.entry === entryKey && item.task === taskKey && item.command === cmdKey;
      });
      if (w) openWfDetail(w);
    });
  });
  // Ticket badge clicks: navigate to the linked ticket
  container.querySelectorAll(".wf-ticket-badge:not([data-badge-bound])").forEach(function (badgeEl) {
    badgeEl.setAttribute("data-badge-bound", "1");
    badgeEl.addEventListener("click", function (e) {
      e.stopPropagation();
      const ticketNum = badgeEl.dataset.ticketNum;
      const ticket = Board.state.TICKETS.find(function (t) { return t.number === ticketNum; });
      if (ticket) Board.render.openViewer(ticket);
    });
  });
}

// ── Detail View ──

/**
 * Opens a workflow detail view as a viewer tab.
 * @param {Object} w - workflow item
 */
function openWfDetail(w) {
  const tabId = "wfDetail:" + w.entry + "/" + w.task + "/" + w.command;
  const exists = Board.state.viewerTabs.find(function (t) { return t.number === tabId; });
  if (!exists) {
    Board.state.viewerTabs.push({ number: tabId, ticket: null, wfFile: null, wfDetail: w });
  } else {
    exists.wfDetail = w;
  }
  wfSwitchTab("viewer");
  Board.state.activeViewerTab = tabId;
  Board.render.renderViewer();
  wfSaveUI();
}

/**
 * Renders the detail view HTML for a workflow item.
 * @param {Object} w - workflow item
 * @returns {string} HTML content
 */
function renderWfDetailView(w) {
  let h = '<div class="tv-container wf-detail-container">';

  // Header
  const headerLinkedTicket = findTicketForWorkflow(w);
  h += '<div class="tv-header">';
  h += '<div class="tv-header-top">';
  if (headerLinkedTicket) {
    h += '<span class="tv-number">' + wfEsc(headerLinkedTicket.number) + "</span>";
  } else {
    h += '<span class="tv-number wf-number-fallback">' + wfEsc(w.entry) + "</span>";
  }
  const stepIsDone = (w.step || "").toUpperCase() === "DONE";
  const stepColors = stepIsDone ? WF_STATUS_COLORS.Done : WF_STATUS_COLORS["In Progress"];
  h += '<span class="badge wf-step-badge" style="background:' + stepColors.bg + ";color:" + stepColors.fg + '">' + wfEsc(w.step || "NONE") + "</span>";
  if (w.command) {
    h += wfBadge(w.command, WF_CMD_COLORS[w.command] || { bg: "rgba(133,133,133,0.25)", fg: "#a0a0a0" });
  }
  h += "</div>";
  h += '<h1 class="tv-title">' + wfEsc(w.task) + "</h1>";
  h += '<div class="tv-meta">';
  h += '<span class="tv-time">' + wfEsc(wfFormatTime(w.created_at)) + "</span>";
  h += "</div>";
  h += "</div>";

  // Info section
  h += '<div class="tv-section">';
  h += '<div class="tv-section-title">Info</div>';
  h += '<div class="wf-detail-info">';
  h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Entry</span><span class="wf-detail-info-value">' + wfEsc(w.entry) + "</span></div>";
  h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Command</span><span class="wf-detail-info-value">' + wfEsc(w.command) + "</span></div>";
  h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Step</span><span class="wf-detail-info-value">' + wfEsc(w.step || "NONE") + "</span></div>";
  h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Created</span><span class="wf-detail-info-value">' + wfEsc(wfFormatTime(w.created_at)) + "</span></div>";
  h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Updated</span><span class="wf-detail-info-value">' + wfEsc(wfFormatTime(w.updated_at)) + "</span></div>";
  const infoTicket = findTicketForWorkflow(w);
  if (infoTicket) {
    h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Ticket</span><span class="wf-detail-info-value"><span class="wf-detail-ticket-link" data-ticket-num="' + wfEsc(infoTicket.number) + '">' + wfEsc(infoTicket.number) + "</span></span></div>";
  }
  h += "</div>";
  h += "</div>";

  // Transitions timeline
  if (w.transitions && w.transitions.length > 0) {
    h += '<div class="tv-section">';
    h += '<div class="tv-section-title">Transitions</div>';
    h += '<div class="wf-detail-transitions">';
    h += '<table class="wf-detail-transition-table">';
    h += "<thead><tr><th>From</th><th>To</th><th>Time</th></tr></thead>";
    h += "<tbody>";
    w.transitions.forEach(function (tr) {
      h += "<tr>";
      h += "<td>" + wfEsc(tr.from || "NONE") + "</td>";
      h += "<td>" + wfEsc(tr.to || "") + "</td>";
      h += '<td class="wf-detail-transition-time">' + wfEsc(wfFormatTime(tr.at || "")) + "</td>";
      h += "</tr>";
    });
    h += "</tbody></table>";
    h += "</div>";
    h += "</div>";
  }

  // Artifact links
  if (w.fileMap) {
    h += '<div class="tv-section">';
    h += '<div class="tv-section-title">Artifacts</div>';
    h += '<div class="wf-detail-artifacts">';
    WF_FILE_COLS.forEach(function (key) {
      const info = w.fileMap[key];
      if (info && info.exists) {
        const isDir = info.isDir ? ' data-isdir="true"' : "";
        h += '<span class="wf-detail-artifact-link" data-label="' + wfEsc(w.task + " / " + key) + '" data-url="' + wfEsc(wfProjectRoot() + info.url) + '"' + isDir + ">" + wfEsc(key) + "</span>";
      } else {
        h += '<span class="wf-detail-artifact-absent">' + wfEsc(key) + "</span>";
      }
    });
    h += "</div>";
    h += "</div>";
  }

  // Connected ticket section placeholder
  h += '<div class="wf-detail-ticket-section" data-basepath="' + wfEsc(wfProjectRoot() + (w.basePath || "")) + '"></div>';

  h += "</div>";
  return h;
}

// ── Main Render ──

/** Workflow column definitions (단일 진실 공급원). */
const WF_COLS = [
  { key: "step",       label: "상태" },
  { key: "ticket",     label: "티켓" },
  { key: "command",    label: "명령" },
  { key: "task",       label: "제목" },
  { key: "query",      label: "질의",   nosort: true },
  { key: "plan",       label: "계획",    nosort: true },
  { key: "work",       label: "작업",    nosort: true },
  { key: "report",     label: "보고",  nosort: true },
  { key: "summary",    label: "요약", nosort: true },
  { key: "usage",      label: "사용",   nosort: true },
  { key: "log",        label: "로그",     nosort: true },
  { key: "updated_at", label: "일시" },
];

/**
 * 헤더 sort indicator HTML 만 갱신한다 (dom 교체 없이).
 * sort 상태 변경 시 호출되며 검색바·tbody·스크롤·포커스를 보존한다.
 */
function refreshWfSortIndicators(el) {
  el.querySelectorAll("th[data-sort-key]").forEach(function (th) {
    const key = th.getAttribute("data-sort-key");
    let indicator = th.querySelector(".wf-sort-indicator, .wf-sort-inactive");
    if (!indicator) return;
    if (Board.state.wfSortKey === key) {
      indicator.className = "wf-sort-indicator";
      indicator.innerHTML = Board.state.wfSortDir === "asc"
        ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg>'
        : '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>';
    } else {
      indicator.className = "wf-sort-inactive";
      indicator.innerHTML = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="7 9 12 4 17 9"/><polyline points="7 15 12 20 17 15"/></svg>';
    }
  });
}

/**
 * tbody 만 다시 그린다 (검색바·헤더·스크롤·포커스 보존).
 * 검색 입력, 정렬 변경, SSE ticket 변경, race 보정 모두 본 함수만 호출한다.
 */
function renderWfTbody() {
  const list = document.getElementById("wf-list");
  if (!list) return;
  const filtered = filterWorkflows(Board.state.WORKFLOWS);
  const sortedFiltered = sortWorkflows(filtered);

  let h = "";
  if (sortedFiltered.length > 0) {
    sortedFiltered.forEach(function (w) { h += renderWfCard(w); });
  } else if (!Board.state.wfLoading) {
    h += '<tr><td colspan="12" class="empty" style="margin-top:32px">' + (Board.state.wfSearchQuery ? "No results" : "No workflows") + "</td></tr>";
  }
  list.innerHTML = h;

  bindWfFileLinks(list);
  bindWfRowClicks(list);
  attachWfSentinel();
  updateWfStatus();
}

/** Renders the full workflow tab shell (search, header, empty tbody) — 1회만 호출한다. */
function renderWorkflow() {
  const el = document.getElementById("view-workflow");
  // 이미 shell 이 그려져 있으면 tbody 갱신만 한다 (검색바·스크롤·포커스 보존).
  if (el.querySelector(".wf-search") && el.querySelector("#wf-list")) {
    refreshWfSortIndicators(el);
    renderWfTbody();
    return;
  }
  const filtered = filterWorkflows(Board.state.WORKFLOWS);
  const hasMore = Board.state.wfLoadedIndex < Board.state.wfEntryHrefs.length;

  let h = '<div class="wf-container">';

  // Search bar
  h += '<div class="wf-search-bar">';
  h += '<input class="wf-search" type="text" placeholder="Search workflows..." value="' + wfEsc(Board.state.wfSearchQuery) + '">';
  h += '<span class="wf-search-count">' + filtered.length + (hasMore ? "+" : "") + " / " + Board.state.wfEntryHrefs.length + "</span>";
  h += "</div>";

  // Table header (tbody 는 비워두고 renderWfTbody 로 채운다)
  h += '<div class="wf-table-wrap"><table class="wf-table">';
  h += "<thead><tr>";
  WF_COLS.forEach(function (col) {
    let indicator = "";
    if (!col.nosort) {
      if (Board.state.wfSortKey === col.key) {
        indicator = Board.state.wfSortDir === "asc"
          ? ' <span class="wf-sort-indicator"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg></span>'
          : ' <span class="wf-sort-indicator"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg></span>';
      } else {
        indicator = ' <span class="wf-sort-inactive"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="7 9 12 4 17 9"/><polyline points="7 15 12 20 17 15"/></svg></span>';
      }
    }
    const sortable = col.nosort ? "" : ' class="wf-th-sortable" data-sort-key="' + col.key + '"';
    h += "<th" + sortable + ">" + col.label + indicator + "</th>";
  });
  h += "</tr></thead>";
  h += '<tbody id="wf-list"></tbody></table></div></div>';

  el.innerHTML = h;

  // Search input — 검색 시엔 tbody 만 갱신한다 (검색바 input 자체는 살아있음)
  el.querySelector(".wf-search").addEventListener("input", function (e) {
    Board.state.wfSearchQuery = e.target.value;
    renderWfTbody();
  });

  // Sort header clicks — indicator + tbody 만 갱신
  el.querySelectorAll("th[data-sort-key]").forEach(function (th) {
    th.addEventListener("click", function () {
      const key = th.getAttribute("data-sort-key");
      if (Board.state.wfSortKey === key) {
        Board.state.wfSortDir = Board.state.wfSortDir === "asc" ? "desc" : "asc";
      } else {
        Board.state.wfSortKey = key;
        Board.state.wfSortDir = "desc";
      }
      refreshWfSortIndicators(el);
      renderWfTbody();
    });
  });

  bindWfColResize(el);

  // 첫 tbody 채우기
  renderWfTbody();
}

// ── Column Resize ──

/** Binds column resize handles on workflow table headers. */
function bindWfColResize(container) {
  const table = container.querySelector(".wf-table");
  if (!table) return;
  const ths = table.querySelectorAll("thead th");
  ths.forEach(function (th, idx) {
    if (idx === ths.length - 1) return;
    let handle = th.querySelector(".wf-col-resize-handle");
    if (handle) return;
    handle = document.createElement("div");
    handle.className = "wf-col-resize-handle";
    th.appendChild(handle);

    let startX, startWidth, nextStartWidth, nextTh;

    handle.addEventListener("mousedown", function (e) {
      e.preventDefault();
      e.stopPropagation();
      startX = e.clientX;
      startWidth = th.offsetWidth;
      nextTh = ths[idx + 1];
      nextStartWidth = nextTh ? nextTh.offsetWidth : 0;

      // Fix all column widths before dragging
      ths.forEach(function (t) { t.style.width = t.offsetWidth + "px"; });

      function onMove(ev) {
        const dx = ev.clientX - startX;
        const newWidth = Math.max(30, startWidth + dx);
        th.style.width = newWidth + "px";
        if (nextTh) {
          const newNext = Math.max(30, nextStartWidth - dx);
          nextTh.style.width = newNext + "px";
        }
      }

      function onUp() {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      }

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  });
}

// ── Register on Board namespace ──

// Fetch
Board.fetch.fetchWorkflowEntries = fetchWorkflowEntries;

// Render
Board.render.renderWorkflow = renderWorkflow;
Board.render.renderWfTbody = renderWfTbody;
Board.render.openWfDetail = openWfDetail;
Board.render.renderWfDetailView = renderWfDetailView;
Board.render.findTicketForWorkflow = findTicketForWorkflow;
Board.render.findWorkflowsForTicket = findWorkflowsForTicket;
Board.render.renderWfCard = renderWfCard;
Board.render.bindWfFileLinks = bindWfFileLinks;
Board.render.bindWfRowClicks = bindWfRowClicks;
Board.render.loadMoreWorkflows = loadMoreWorkflows;
Board.render.filterWorkflows = filterWorkflows;

// Expose constants for other modules
Board.util.WF_FILES = WF_FILES;
Board.util.WF_FILE_COLS = WF_FILE_COLS;
