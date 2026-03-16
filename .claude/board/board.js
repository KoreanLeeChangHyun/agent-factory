(function () {
  "use strict";

  var TICKETS = [];
  var COLUMNS = [
    { key: "Open", label: "Open", dot: "dot-open" },
    { key: "In Progress", label: "In Progress", dot: "dot-progress" },
    { key: "Review", label: "Review", dot: "dot-review" },
    { key: "Done", label: "Done", dot: "dot-done" },
  ];

  // ── Utilities ──
  function esc(text) {
    var d = document.createElement("div");
    d.textContent = text || "";
    return d.innerHTML;
  }

  function xmlText(el, tag) {
    var c = el && el.querySelector(tag);
    return c ? (c.textContent || "").trim() : "";
  }

  function formatTime(dt) {
    return dt ? dt.substring(0, 16) : "";
  }

  // ── XML Ticket Parsing ──
  function parseSubnumber(el) {
    var prompt = null;
    var promptEl = el.querySelector("prompt");
    if (promptEl) {
      prompt = {};
      for (var i = 0; i < promptEl.children.length; i++) {
        var c = promptEl.children[i];
        var t = (c.textContent || "").trim();
        if (t) prompt[c.tagName] = t;
      }
      if (Object.keys(prompt).length === 0) prompt = null;
    }
    return {
      id: parseInt(el.getAttribute("id") || "0", 10),
      active: el.getAttribute("active") === "true",
      datetime: xmlText(el, "datetime"),
      command: xmlText(el, "command"),
      prompt: prompt,
      result: (function () {
        var resultEl = el.querySelector("result");
        if (!resultEl) return null;
        var obj = {};
        for (var ri = 0; ri < resultEl.children.length; ri++) {
          var rc = resultEl.children[ri];
          var rt = (rc.textContent || "").trim();
          if (rt) obj[rc.tagName.toLowerCase()] = rt;
        }
        return Object.keys(obj).length > 0 ? obj : null;
      })(),
    };
  }

  function parseTicket(text) {
    var doc = new DOMParser().parseFromString(text, "text/xml");
    var root = doc.querySelector("ticket");
    if (!root) return null;

    var meta = root.querySelector("metadata");
    var ticket = { number: "", title: "", datetime: "", status: "Open", current: 0, submit: null, history: [] };

    if (meta) {
      ["number", "title", "datetime", "status"].forEach(function (f) {
        var el = meta.querySelector(f);
        if (el && el.textContent) ticket[f] = el.textContent.trim();
      });
      var cur = meta.querySelector("current");
      if (cur && cur.textContent) ticket.current = parseInt(cur.textContent.trim(), 10);
    }

    var submitEl = root.querySelector("submit");
    if (submitEl) {
      var subs = submitEl.querySelectorAll("subnumber");
      for (var i = 0; i < subs.length; i++) {
        var p = parseSubnumber(subs[i]);
        if (p.active) { ticket.submit = p; break; }
      }
      if (!ticket.submit && subs.length > 0) ticket.submit = parseSubnumber(subs[subs.length - 1]);
    }

    var historyEl = root.querySelector("history");
    if (historyEl) {
      var hs = historyEl.querySelectorAll("subnumber");
      for (var j = 0; j < hs.length; j++) ticket.history.push(parseSubnumber(hs[j]));
    }

    return ticket;
  }

  // ── Fetch Tickets ──

  /** 디렉터리 URL에서 .xml 파일 목록을 가져온다. 404나 네트워크 오류 시 빈 배열 반환. */
  function fetchXmlList(dirUrl) {
    return fetch(dirUrl, { cache: "no-store" }).then(function (res) {
      if (!res.ok) return [];
      return res.text().then(function (html) {
        // 경로 탈출 방지: ../ 포함 항목과 / 시작 항목 제거
        return parseDirLinks(html).files.filter(function (f) { return f.endsWith(".xml") && !f.includes("../") && !f.startsWith("/"); });
      });
    }).catch(function () { return []; });
  }

  /** 디렉터리 리스팅 기반 병렬 fetch로 모든 티켓을 수집한다. */
  function fetchTickets() {
    return Promise.all([
      fetchXmlList("../../.kanban/"),
      fetchXmlList("../../.kanban/done/"),
    ]).then(function (results) {
      var rootFiles = results[0].map(function (f) { return "../../.kanban/" + f; });
      var doneFiles = results[1].map(function (f) { return "../../.kanban/done/" + f; });
      var allFiles = rootFiles.concat(doneFiles);
      return Promise.all(allFiles.map(function (url) {
        return fetch(url, { cache: "no-store" }).then(function (res) {
          if (!res.ok) return null;
          return res.text().then(function (text) { return parseTicket(text); });
        }).catch(function () { return null; });
      }));
    }).then(function (results) {
      return results.filter(function (t) { return t !== null; });
    });
  }

  /**
   * 변경된 파일명 목록만 선택적으로 fetch하여 TICKETS를 업데이트한다.
   * @param {string[]} files - 변경된 파일명 배열 (예: ["T-038.xml"])
   * @returns {Promise<void>}
   */
  function fetchTicketsByFiles(files) {
    return Promise.all(files.map(function (f) {
      return fetch("../../.kanban/" + f, { cache: "no-store" }).then(function (res) {
        if (res.ok) {
          return res.text().then(function (text) {
            return { file: f, ticket: parseTicket(text) };
          });
        }
        // .kanban/ 에 없으면 done/ 에서 시도
        return fetch("../../.kanban/done/" + f, { cache: "no-store" }).then(function (res2) {
          if (res2.ok) {
            return res2.text().then(function (text) {
              return { file: f, ticket: parseTicket(text) };
            });
          }
          // 양쪽 모두 404: 삭제된 파일
          return { file: f, ticket: null };
        });
      }).catch(function () {
        return { file: f, ticket: null };
      });
    })).then(function (results) {
      results.forEach(function (result) {
        var incoming = result.ticket;
        if (incoming === null) {
          // 삭제된 파일: TICKETS에서 파일명으로 해당 티켓 제거
          var baseName = result.file.replace(/\.xml$/, "");
          TICKETS = TICKETS.filter(function (t) { return t.number !== baseName; });
        } else {
          var idx = TICKETS.findIndex(function (t) { return t.number === incoming.number; });
          if (idx !== -1) {
            // 기존 티켓 교체
            TICKETS[idx] = incoming;
          } else {
            // 새 티켓 추가
            TICKETS.push(incoming);
          }
        }
      });
    });
  }

  // ── UI State Persistence ──
  var LS_KEY = "claude-board-ui";
  var KANBAN_SORT_LS_KEY = "claude-board-kanban-sort";

  // ── Kanban Sort State ──
  var kanbanSort = loadKanbanSort();

  function loadKanbanSort() {
    var defaults = {};
    COLUMNS.forEach(function (col) {
      defaults[col.key] = { key: "number", dir: "asc" };
    });
    try {
      var stored = JSON.parse(localStorage.getItem(KANBAN_SORT_LS_KEY));
      if (stored && typeof stored === "object") {
        COLUMNS.forEach(function (col) {
          if (!stored[col.key] || !stored[col.key].key) {
            stored[col.key] = defaults[col.key];
          }
        });
        return stored;
      }
    } catch (e) {}
    return defaults;
  }

  function saveKanbanSort() {
    try { localStorage.setItem(KANBAN_SORT_LS_KEY, JSON.stringify(kanbanSort)); } catch (e) {}
  }

  // ── Kanban Sort Logic ──
  function getModifiedDate(t) {
    // 최신 history/submit의 datetime, 없으면 t.datetime 폴백
    var candidates = [];
    if (t.submit && t.submit.datetime) candidates.push(t.submit.datetime);
    if (t.history && t.history.length > 0) {
      t.history.forEach(function (h) { if (h.datetime) candidates.push(h.datetime); });
    }
    if (candidates.length === 0) return t.datetime || "";
    return candidates.reduce(function (a, b) { return a > b ? a : b; });
  }

  function sortTickets(items, sortKey, sortDir) {
    var dir = sortDir === "desc" ? -1 : 1;
    return items.slice().sort(function (a, b) {
      var av, bv, cmp;
      if (sortKey === "number") {
        av = a.number || "";
        bv = b.number || "";
        cmp = av.localeCompare(bv);
      } else if (sortKey === "created") {
        av = a.datetime || "";
        bv = b.datetime || "";
        cmp = av.localeCompare(bv);
      } else if (sortKey === "modified") {
        av = getModifiedDate(a);
        bv = getModifiedDate(b);
        cmp = av.localeCompare(bv);
      } else if (sortKey === "title") {
        av = a.title || "";
        bv = b.title || "";
        cmp = av.localeCompare(bv, "ko");
      } else {
        cmp = 0;
      }
      return dir * cmp;
    });
  }

  // ── Inline SVG Icons for sort direction ──
  var SVG_ASC = '<svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M5 2L9 8H1L5 2Z"/></svg>';
  var SVG_DESC = '<svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M5 8L1 2H9L5 8Z"/></svg>';

  // ── Sort Options ──
  var SORT_KEYS = [
    { key: "number",   label: "번호" },
    { key: "created",  label: "생성일" },
    { key: "modified", label: "수정일" },
    { key: "title",    label: "제목" },
  ];
  var SORT_DIRS = [
    { dir: "asc",  label: "오름차순" },
    { dir: "desc", label: "내림차순" },
  ];

  function saveUI() {
    var openNums = viewerTabs.map(function (t) { return t.number; });
    var state = { tab: activeTab, viewerTabs: openNums, activeViewerTab: activeViewerTab, tabHistory: tabHistory, forwardHistory: forwardHistory };
    try { localStorage.setItem(LS_KEY, JSON.stringify(state)); } catch (e) {}
  }

  function loadUI() {
    try { return JSON.parse(localStorage.getItem(LS_KEY)) || {}; } catch (e) { return {}; }
  }

  var savedState = loadUI();

  // ── Tab Switching ──
  var tabs = document.querySelectorAll(".tab");
  var views = document.querySelectorAll(".view");
  var activeTab = savedState.tab || "dashboard";
  function migrateTabHistory(history) {
    return history.map(function (entry) {
      if (typeof entry === "string") return { tab: entry, viewerTab: null };
      return entry;
    });
  }

  var tabHistory = migrateTabHistory(savedState.tabHistory || []);
  var forwardHistory = migrateTabHistory(savedState.forwardHistory || []);

  function switchTab(target, skipPush) {
    if (!skipPush && activeTab) {
      tabHistory.push({ tab: activeTab, viewerTab: activeTab === "viewer" ? activeViewerTab : null });
      if (tabHistory.length > 100) tabHistory.shift();
      forwardHistory.length = 0;
    }
    activeTab = target;
    tabs.forEach(function (t) { t.classList.toggle("active", t.dataset.view === target); });
    views.forEach(function (v) { v.classList.toggle("active", v.id === "view-" + target); });
    if (target === "dashboard") renderDashboard();
    saveUI();
  }

  tabs.forEach(function (t) {
    t.addEventListener("click", function () { switchTab(t.dataset.view); });
  });

  // ── Command Badge Colors ──
  var CMD_COLORS = {
    implement: { bg: "rgba(86,156,214,0.3)", fg: "#7bb8e8" },
    review: { bg: "rgba(197,134,192,0.3)", fg: "#d9a0d6" },
    research: { bg: "rgba(220,220,170,0.3)", fg: "#e8e8b0" },
    submit: { bg: "rgba(78,201,176,0.3)", fg: "#6ee0c8" },
    prompt: { bg: "rgba(160,160,160,0.2)", fg: "#a0a0a0" },
  };

  var STATUS_COLORS = {
    Open: { bg: "rgba(78,201,176,0.15)", fg: "#4ec9b0" },
    "In Progress": { bg: "rgba(220,220,170,0.15)", fg: "#dcdcaa" },
    Review: { bg: "rgba(197,134,192,0.15)", fg: "#c586c0" },
    Done: { bg: "rgba(133,133,133,0.15)", fg: "#858585" },
  };

  function badge(text, colors) {
    if (!text || !colors) return "";
    return '<span class="badge" style="background:' + colors.bg + ";color:" + colors.fg + '">' + esc(text) + "</span>";
  }

  // ── Kanban Rendering ──
  function renderKanban() {
    var el = document.getElementById("view-kanban");
    var h = '<div class="kanban-board">';
    COLUMNS.forEach(function (col) {
      var items = TICKETS.filter(function (t) { return t.status === col.key; });
      var colSort = kanbanSort[col.key] || { key: "number", dir: "asc" };
      var sortedItems = sortTickets(items, colSort.key, colSort.dir);
      var sortIcon = colSort.dir === "desc" ? SVG_DESC : SVG_ASC;

      // Build dropdown options HTML (2-tier: key section + divider + dir section)
      var dropHtml = '<div class="col-sort-dropdown" data-col="' + esc(col.key) + '">';
      SORT_KEYS.forEach(function (opt) {
        var isActive = (opt.key === colSort.key) ? " active" : "";
        dropHtml += '<button class="col-sort-option' + isActive + '"'
          + ' data-col="' + esc(col.key) + '"'
          + ' data-sort-key="' + esc(opt.key) + '">'
          + esc(opt.label) + '</button>';
      });
      dropHtml += '<div class="col-sort-divider"></div>';
      SORT_DIRS.forEach(function (opt) {
        var isActive = (opt.dir === colSort.dir) ? " active" : "";
        dropHtml += '<button class="col-sort-option' + isActive + '"'
          + ' data-col="' + esc(col.key) + '"'
          + ' data-sort-dir="' + esc(opt.dir) + '">'
          + esc(opt.label) + '</button>';
      });
      dropHtml += '</div>';

      h += '<div class="column">';
      h += '<div class="col-header">';
      h += '<span class="col-dot ' + col.dot + '"></span>';
      h += esc(col.label);
      h += '<div class="col-sort-wrapper" style="margin-left:auto">';
      h += '<button class="col-sort-btn" data-col="' + esc(col.key) + '" title="정렬">' + sortIcon + '</button>';
      h += dropHtml;
      h += '</div>';
      h += '<span class="col-count">' + items.length + "</span>";
      h += "</div>";
      h += '<div class="cards">';
      if (sortedItems.length === 0) {
        h += '<div class="empty">No items</div>';
      } else {
        sortedItems.forEach(function (t) {
          var done = col.key === "Done" ? " done" : "";
          h += '<div class="card' + done + '" data-num="' + esc(t.number) + '">';
          h += '<div class="card-title">' + esc(t.title || "(No title)") + "</div>";
          h += '<div class="card-meta">';
          h += '<span class="card-meta-left">';
          h += '<span class="card-num">' + esc(t.number) + "</span>";
          if (t.submit && t.submit.command) {
            h += badge(t.submit.command, CMD_COLORS[t.submit.command]);
          }
          h += "</span>";
          h += '<span class="card-date"><span>' + esc((t.datetime || "").substring(0, 10)) + "</span><span>" + esc((t.datetime || "").substring(11, 16)) + "</span></span>";
          h += "</div></div>";
        });
      }
      h += "</div></div>";
    });
    h += "</div>";
    el.innerHTML = h;

    // Bind card clicks
    el.querySelectorAll(".card").forEach(function (card) {
      card.addEventListener("click", function () {
        var num = card.dataset.num;
        var ticket = TICKETS.find(function (t) { return t.number === num; });
        if (ticket) openViewer(ticket);
      });
    });

    // Bind sort button clicks (toggle dropdown)
    el.querySelectorAll(".col-sort-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var colKey = btn.dataset.col;
        var dropdown = btn.parentNode.querySelector(".col-sort-dropdown");
        var isOpen = dropdown.classList.contains("open");
        // Close all dropdowns first
        el.querySelectorAll(".col-sort-dropdown.open").forEach(function (d) {
          d.classList.remove("open");
        });
        if (!isOpen) {
          dropdown.classList.add("open");
        }
      });
    });

    // Bind sort option clicks
    el.querySelectorAll(".col-sort-option").forEach(function (opt) {
      opt.addEventListener("click", function (e) {
        e.stopPropagation();
        var colKey = opt.dataset.col;
        var current = kanbanSort[colKey] || { key: "number", dir: "asc" };
        if (opt.dataset.sortKey && !opt.dataset.sortDir) {
          // Key button: preserve current dir
          kanbanSort[colKey] = { key: opt.dataset.sortKey, dir: current.dir };
        } else if (opt.dataset.sortDir && !opt.dataset.sortKey) {
          // Dir button: preserve current key
          kanbanSort[colKey] = { key: current.key, dir: opt.dataset.sortDir };
        }
        saveKanbanSort();
        renderKanban();
      });
    });

    // Close dropdowns on outside click (attach once per render; cleaned up on next render via innerHTML reset)
    var outsideHandler = function (e) {
      if (!e.target.closest(".col-sort-wrapper")) {
        el.querySelectorAll(".col-sort-dropdown.open").forEach(function (d) {
          d.classList.remove("open");
        });
      }
    };
    document.addEventListener("click", outsideHandler);
    // Store handler reference on element for cleanup on next renderKanban call
    if (el._sortOutsideHandler) {
      document.removeEventListener("click", el._sortOutsideHandler);
    }
    el._sortOutsideHandler = outsideHandler;
  }

  // ── Viewer Tabs ──
  var viewerTabs = [];
  var activeViewerTab = savedState.activeViewerTab || null;

  // ── Code Viewer Store (hybrid rendering + search state) ──
  var codeViewerStore = {}; // { [viewerId]: { pendingRows: [], allLines: [], nextChunk: 0 } }

  function openViewer(ticket) {
    var exists = viewerTabs.find(function (t) { return t.number === ticket.number; });
    if (!exists) {
      viewerTabs.push({ number: ticket.number, ticket: ticket });
    } else {
      exists.ticket = ticket;
    }
    switchTab("viewer");
    activeViewerTab = ticket.number;
    renderViewer();
    saveUI();
  }

  function closeViewerTab(number) {
    viewerTabs = viewerTabs.filter(function (t) { return t.number !== number; });
    if (activeViewerTab === number) {
      activeViewerTab = viewerTabs.length > 0 ? viewerTabs[viewerTabs.length - 1].number : null;
    }
    renderViewer();
    saveUI();
  }

  function renderViewer() {
    var el = document.getElementById("view-viewer");
    var h = "";

    // Tab bar
    h += '<div class="vt-bar">';
    var backDim = tabHistory.length === 0 ? " vt-nav-dim" : "";
    var fwdDim = forwardHistory.length === 0 ? " vt-nav-dim" : "";
    h += '<button class="vt-back-btn' + backDim + '" id="vt-back-btn">&lt;</button>';
    h += '<button class="vt-back-btn' + fwdDim + '" id="vt-fwd-btn">&gt;</button>';
    viewerTabs.forEach(function (t) {
      var ac = t.number === activeViewerTab ? " vt-tab-active" : "";
      h += '<div class="vt-tab' + ac + '" data-num="' + esc(t.number) + '">';
      var tabLabel = t.wfDetail ? (t.wfDetail.number || t.wfDetail.entry) : (t.wfFile ? t.wfFile.label : t.number);
      h += '<span class="vt-tab-label">' + esc(tabLabel) + '</span>';
      h += '<span class="vt-tab-close" data-close="' + esc(t.number) + '">&times;</span>';
      h += '</div>';
    });
    h += '</div>';

    // Content
    h += '<div class="vt-content">';
    var active = viewerTabs.find(function (t) { return t.number === activeViewerTab; });
    if (active && active.wfDetail) {
      h += renderWfDetailView(active.wfDetail);
    } else if (active && active.wfFile) {
      h += renderWfFileView(active.wfFile);
    } else if (active && active.ticket) {
      h += renderTicketHtml(active.ticket);
    } else {
      h += '<div class="empty" style="margin-top:64px">No open tabs</div>';
    }
    h += '</div>';

    el.innerHTML = h;

    // Bind tab clicks
    el.querySelectorAll(".vt-tab").forEach(function (tab) {
      tab.addEventListener("click", function (e) {
        if (e.target.classList.contains("vt-tab-close")) return;
        var prevViewerTab = activeViewerTab;
        if (tab.dataset.num !== prevViewerTab) {
          tabHistory.push({ tab: "viewer", viewerTab: prevViewerTab });
          if (tabHistory.length > 100) tabHistory.shift();
          forwardHistory.length = 0;
        }
        activeViewerTab = tab.dataset.num;
        renderViewer();
        saveUI();
      });
    });
    el.querySelectorAll(".vt-tab-close").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        closeViewerTab(btn.dataset.close);
      });
    });

    // Bind result links
    el.querySelectorAll(".tv-result-link").forEach(function (link) {
      link.addEventListener("click", function () {
        var isDir = link.dataset.isdir === "true";
        openWfFile(link.dataset.label, link.dataset.url, isDir);
      });
    });

    // Bind dir file links
    el.querySelectorAll(".wf-dir-file-link").forEach(function (link) {
      link.addEventListener("click", function () {
        openWfFile(link.dataset.label, link.dataset.url);
      });
    });

    // Bind wfDetail artifact links
    el.querySelectorAll(".wf-detail-artifact-link").forEach(function (link) {
      link.addEventListener("click", function () {
        var isDir = link.dataset.isdir === "true";
        openWfFile(link.dataset.label, link.dataset.url, isDir);
      });
    });

    // Lazy-load connected ticket for wfDetail views
    el.querySelectorAll(".wf-detail-ticket-section[data-basepath]").forEach(function (section) {
      var basePath = section.dataset.basepath;
      if (!basePath || section.dataset.fetched) return;
      section.dataset.fetched = "1";
      fetch(basePath + ".context.json", { cache: "no-store" }).then(function (r) {
        if (!r.ok) return null;
        return r.json();
      }).then(function (ctx) {
        if (!ctx) return;
        var ticketNum = ctx.ticketNumber || "";
        var title = ctx.title || "";
        var workId = ctx.workId || "";
        if (!ticketNum && !title && !workId) return;
        var h = '<div class="tv-section">';
        h += '<div class="tv-section-title">Context</div>';
        h += '<div class="wf-detail-info">';
        if (ticketNum) h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Ticket</span><span class="wf-detail-info-value">' + esc(ticketNum) + '</span></div>';
        if (title) h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Title</span><span class="wf-detail-info-value">' + esc(title) + '</span></div>';
        if (workId) h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Work ID</span><span class="wf-detail-info-value">' + esc(workId) + '</span></div>';
        h += '</div></div>';
        section.innerHTML = h;
      }).catch(function () {});
    });

    // Bind back button
    var backBtn = el.querySelector("#vt-back-btn");
    if (backBtn) {
      backBtn.addEventListener("click", function () {
        while (tabHistory.length > 0) {
          var entry = tabHistory.pop();
          if (entry && entry.tab === "viewer" && entry.viewerTab) {
            var stillOpen = viewerTabs.find(function (t) { return t.number === entry.viewerTab; });
            if (!stillOpen) continue;
            forwardHistory.push({ tab: "viewer", viewerTab: activeViewerTab });
            activeViewerTab = entry.viewerTab;
            renderViewer();
            saveUI();
            return;
          }
          forwardHistory.push({ tab: activeTab, viewerTab: activeTab === "viewer" ? activeViewerTab : null });
          switchTab(entry && entry.tab ? entry.tab : "kanban", true);
          return;
        }
        switchTab("kanban", true);
      });
    }

    // Bind forward button
    var fwdBtn = el.querySelector("#vt-fwd-btn");
    if (fwdBtn) {
      fwdBtn.addEventListener("click", function () {
        while (forwardHistory.length > 0) {
          var entry = forwardHistory.pop();
          if (entry && entry.tab === "viewer" && entry.viewerTab) {
            var stillOpen = viewerTabs.find(function (t) { return t.number === entry.viewerTab; });
            if (!stillOpen) continue;
            tabHistory.push({ tab: "viewer", viewerTab: activeViewerTab });
            if (tabHistory.length > 100) tabHistory.shift();
            activeViewerTab = entry.viewerTab;
            renderViewer();
            saveUI();
            return;
          }
          tabHistory.push({ tab: activeTab, viewerTab: activeTab === "viewer" ? activeViewerTab : null });
          if (tabHistory.length > 100) tabHistory.shift();
          switchTab(entry && entry.tab ? entry.tab : "kanban", true);
          return;
        }
      });
    }

    // Bind wfDetail ticket link clicks (Info section Ticket row)
    el.querySelectorAll(".wf-detail-ticket-link").forEach(function (link) {
      link.addEventListener("click", function () {
        var ticketNum = link.dataset.ticketNum;
        var ticket = TICKETS.find(function (t) { return t.number === ticketNum; });
        if (ticket) openViewer(ticket);
      });
    });

    // Bind ticket viewer workflow links (Connected Workflows section)
    el.querySelectorAll(".tv-result-workflow[data-wf-entry]").forEach(function (link) {
      link.addEventListener("click", function () {
        var entryKey = link.dataset.wfEntry;
        var taskKey = link.dataset.wfTask;
        var cmdKey = link.dataset.wfCmd;
        var w = WORKFLOWS.find(function (item) {
          return item.entry === entryKey && item.task === taskKey && item.command === cmdKey;
        });
        if (w) openWfDetail(w);
      });
    });

    // Bind md-file-link clicks
    el.querySelectorAll(".md-file-link").forEach(function (link) {
      link.addEventListener("click", function () {
        var filePath = link.dataset.filepath;
        if (!filePath) return;
        var url;
        if (link.dataset.url) {
          // Use pre-resolved URL set by renderer.link (W01)
          url = link.dataset.url;
        } else if (filePath.indexOf(".workflow/") === 0 || filePath.indexOf(".claude/") === 0) {
          // Project-root-relative path: prepend "../../" to reach project root from board.html
          url = "../../" + filePath;
        } else {
          // Report-relative path (e.g. "work/..."): resolve against current tab's wfFile.url
          var activeTab = viewerTabs.find(function (t) { return t.number === activeViewerTab; });
          var baseUrl = activeTab && activeTab.wfFile ? activeTab.wfFile.url : "";
          url = urlDir(baseUrl) + filePath;
        }
        openWfFile(filePath, url);
      });
    });

    // Bind copy button clicks
    el.querySelectorAll(".code-copy-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var viewer = btn.closest(".code-viewer");
        if (!viewer) return;
        var lineContents = viewer.querySelectorAll(".code-line-content");
        var text = Array.prototype.map.call(lineContents, function (span) {
          return span.textContent;
        }).join("\n");
        navigator.clipboard.writeText(text).then(function () {
          var original = btn.textContent;
          btn.textContent = "Copied!";
          setTimeout(function () { btn.textContent = original; }, 1500);
        }).catch(function () {
          btn.textContent = "Error";
          setTimeout(function () { btn.textContent = "Copy"; }, 1500);
        });
      });
    });

    // Bind lazy scroll for large files
    el.querySelectorAll(".code-viewer").forEach(function (viewer) {
      var viewerId = viewer.dataset.viewerId;
      if (!viewerId || !codeViewerStore[viewerId]) return;
      var store = codeViewerStore[viewerId];
      if (store.pendingRows.length === 0) return;

      var CHUNK_SIZE = 200;
      var SCROLL_THRESHOLD = 200;

      function appendNextChunk() {
        if (store.pendingRows.length === 0) return;
        var chunk = store.pendingRows.splice(0, CHUNK_SIZE);
        var code = viewer.querySelector("code");
        if (!code) return;
        var chunkHtml = "\n" + chunk.join("\n");
        var lang = store.lang;
        // Apply syntax highlighting to chunk if hljs is available and language is registered
        var highlightedHtml = null;
        if (typeof hljs !== "undefined" && lang && lang !== "plaintext") {
          try {
            var result = hljs.highlight(chunkHtml, { language: lang });
            highlightedHtml = result.value;
          } catch (e) {
            highlightedHtml = null;
          }
        }
        var frag = document.createDocumentFragment();
        var wrapper = document.createElement("span");
        if (highlightedHtml !== null) {
          wrapper.innerHTML = highlightedHtml;
        } else {
          // Fallback: insert as plain HTML (already escaped in rows)
          wrapper.innerHTML = chunkHtml;
        }
        while (wrapper.firstChild) {
          frag.appendChild(wrapper.firstChild);
        }
        code.appendChild(frag);
        if (store.pendingRows.length === 0) {
          viewer.removeEventListener("scroll", onScroll);
        }
      }

      function onScroll() {
        var distFromBottom = viewer.scrollHeight - viewer.scrollTop - viewer.clientHeight;
        if (distFromBottom < SCROLL_THRESHOLD) {
          appendNextChunk();
        }
      }

      viewer.addEventListener("scroll", onScroll);
    });

    // Bind code search (Ctrl+F / Cmd+F)
    el.querySelectorAll(".code-viewer").forEach(function (viewer) {
      var viewerId = viewer.dataset.viewerId;
      if (!viewerId || !codeViewerStore[viewerId]) return;
      var store = codeViewerStore[viewerId];
      var searchBar = viewer.querySelector(".code-search-bar");
      var searchInput = viewer.querySelector(".code-search-input");
      var searchCount = viewer.querySelector(".code-search-count");

      function openSearch() {
        if (!searchBar) return;
        searchBar.style.display = "flex";
        searchInput.focus();
        searchInput.select();
      }

      function closeSearch() {
        if (!searchBar) return;
        searchBar.style.display = "none";
        clearSearchHighlights(viewer);
        store.searchMatches = [];
        store.searchIndex = -1;
        if (searchCount) searchCount.textContent = "";
      }

      function clearSearchHighlights(viewerEl) {
        viewerEl.querySelectorAll(".code-search-match").forEach(function (mark) {
          var parent = mark.parentNode;
          if (!parent) return;
          parent.replaceChild(document.createTextNode(mark.textContent), mark);
          parent.normalize();
        });
        viewerEl.querySelectorAll(".code-line-content.code-search-active").forEach(function (span) {
          span.classList.remove("code-search-active");
        });
      }

      function applySearchHighlights(query) {
        clearSearchHighlights(viewer);
        store.searchMatches = [];
        store.searchIndex = -1;
        if (!query) {
          if (searchCount) searchCount.textContent = "";
          return;
        }
        var lowerQuery = query.toLowerCase();
        var lineContents = viewer.querySelectorAll(".code-line-content");
        lineContents.forEach(function (span) {
          var text = span.textContent;
          if (text.toLowerCase().indexOf(lowerQuery) === -1) return;
          store.searchMatches.push(span);
          // Use TreeWalker to traverse text nodes only, preserving hljs token <span> structure
          var walker = document.createTreeWalker(span, NodeFilter.SHOW_TEXT, null, false);
          var textNodes = [];
          var node;
          while ((node = walker.nextNode())) {
            textNodes.push(node);
          }
          textNodes.forEach(function (textNode) {
            var nodeText = textNode.nodeValue;
            var lowerNodeText = nodeText.toLowerCase();
            var idx = 0;
            var found = lowerNodeText.indexOf(lowerQuery, idx);
            if (found === -1) return;
            // Split text node and wrap matches with <mark>
            var parent = textNode.parentNode;
            var frag = document.createDocumentFragment();
            while (idx < nodeText.length) {
              found = lowerNodeText.indexOf(lowerQuery, idx);
              if (found === -1) {
                frag.appendChild(document.createTextNode(nodeText.substring(idx)));
                break;
              }
              if (found > idx) {
                frag.appendChild(document.createTextNode(nodeText.substring(idx, found)));
              }
              var mark = document.createElement("mark");
              mark.className = "code-search-match";
              mark.appendChild(document.createTextNode(nodeText.substring(found, found + query.length)));
              frag.appendChild(mark);
              idx = found + query.length;
            }
            parent.replaceChild(frag, textNode);
          });
        });
        if (searchCount) {
          searchCount.textContent = store.searchMatches.length > 0
            ? "0/" + store.searchMatches.length
            : "No results";
        }
      }

      function navigateSearch(dir) {
        if (store.searchMatches.length === 0) return;
        // Remove active class from current
        if (store.searchIndex >= 0 && store.searchIndex < store.searchMatches.length) {
          store.searchMatches[store.searchIndex].classList.remove("code-search-active");
        }
        if (dir === "next") {
          store.searchIndex = (store.searchIndex + 1) % store.searchMatches.length;
        } else {
          store.searchIndex = (store.searchIndex - 1 + store.searchMatches.length) % store.searchMatches.length;
        }
        var activeSpan = store.searchMatches[store.searchIndex];
        activeSpan.classList.add("code-search-active");
        if (searchCount) {
          searchCount.textContent = (store.searchIndex + 1) + "/" + store.searchMatches.length;
        }
        activeSpan.scrollIntoView({ block: "center" });
      }

      // Ctrl+F / Cmd+F inside viewer
      viewer.addEventListener("keydown", function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === "f") {
          e.preventDefault();
          openSearch();
        }
        if (e.key === "Escape") {
          closeSearch();
        }
      });

      // Make viewer focusable so keydown fires
      if (!viewer.getAttribute("tabindex")) {
        viewer.setAttribute("tabindex", "0");
      }

      // Global Ctrl+F when viewer is the active code viewer
      viewer.addEventListener("focus", function () {
        viewer._hasFocus = true;
      });
      viewer.addEventListener("blur", function () {
        viewer._hasFocus = false;
      });

      if (searchInput) {
        searchInput.addEventListener("input", function () {
          applySearchHighlights(searchInput.value);
        });
        searchInput.addEventListener("keydown", function (e) {
          if (e.key === "Enter") {
            e.preventDefault();
            navigateSearch(e.shiftKey ? "prev" : "next");
          }
          if (e.key === "Escape") {
            closeSearch();
          }
        });
      }

      // Nav buttons
      viewer.querySelectorAll(".code-search-nav-btn").forEach(function (navBtn) {
        navBtn.addEventListener("click", function () {
          navigateSearch(navBtn.dataset.dir);
        });
      });

      // Close button
      var closeBtn = viewer.querySelector(".code-search-close-btn");
      if (closeBtn) {
        closeBtn.addEventListener("click", function () {
          closeSearch();
        });
      }
    });

    initMermaid();
    initHighlight();
  }

  function renderTicketHtml(ticket) {
    var sc = STATUS_COLORS[ticket.status] || STATUS_COLORS.Open;
    var h = '<div class="tv-container">';

    h += '<div class="tv-header">';
    h += '<div class="tv-header-top">';
    h += '<span class="tv-number">' + esc(ticket.number) + "</span>";
    h += badge(ticket.status, sc);
    h += "</div>";
    h += '<h1 class="tv-title">' + esc(ticket.title || "(No title)") + "</h1>";
    h += '<div class="tv-meta">';
    h += '<span class="tv-time">' + esc(formatTime(ticket.datetime)) + "</span>";
    if (ticket.submit && ticket.submit.command) {
      h += badge(ticket.submit.command, CMD_COLORS[ticket.submit.command]);
    }
    h += "</div></div>";

    if (ticket.submit && ticket.submit.prompt) {
      h += '<div class="tv-section">';
      h += '<div class="tv-section-title">Active Prompt <span class="tv-sub-id">#' + ticket.submit.id + "</span></div>";
      h += renderPromptFields(ticket.submit.prompt);
      h += "</div>";
    }

    if (ticket.submit && ticket.submit.result) {
      h += '<div class="tv-section tv-result-section">';
      h += '<div class="tv-section-title">Result</div>';
      h += renderResultLinks(ticket.submit.result);
      h += "</div>";
    }

    var connectedWfs = findWorkflowsForTicket(ticket);
    if (connectedWfs.length > 0) {
      h += '<div class="tv-section">';
      h += '<div class="tv-section-title">Workflows</div>';
      h += '<div class="tv-result-links">';
      connectedWfs.forEach(function (w) {
        var label = w.number ? w.number + " / " + w.task : w.task;
        h += '<span class="tv-result-link tv-result-workflow" data-wf-entry="' + esc(w.entry) + '" data-wf-task="' + esc(w.task) + '" data-wf-cmd="' + esc(w.command) + '">' + esc(label) + '</span>';
      });
      h += '</div>';
      h += "</div>";
    }

    if (ticket.history.length > 0) {
      h += '<div class="tv-section">';
      h += '<div class="tv-section-title">History</div>';
      h += '<div class="timeline">';
      ticket.history.forEach(function (entry) {
        var ac = entry.active ? " active" : "";
        h += '<div class="tl-entry' + ac + '">';
        h += '<div class="tl-header">';
        h += '<span class="tl-id">#' + entry.id + "</span>";
        if (entry.command) h += badge(entry.command, CMD_COLORS[entry.command]);
        h += '<span class="tl-time">' + esc(formatTime(entry.datetime)) + "</span>";
        h += "</div>";
        if (entry.prompt) h += renderPromptFields(entry.prompt);
        if (entry.result) {
          if (typeof entry.result === "object") {
            h += '<div class="tv-result-section">';
            h += '<div class="tv-field-label">Result</div>';
            h += renderResultLinks(entry.result);
            h += "</div>";
          } else {
            h += '<div class="tv-field"><div class="tv-field-label">Result</div>';
            h += '<div class="tv-field-value">' + esc(entry.result) + "</div></div>";
          }
        }
        h += "</div>";
      });
      h += "</div></div>";
    }

    if (!ticket.submit && ticket.history.length === 0) {
      h += '<div class="empty" style="margin-top:32px">No submit or history data</div>';
    }

    h += "</div>";
    return h;
  }

  function renderPromptFields(prompt) {
    var fields = ["goal", "target", "constraints", "criteria"];
    var h = '<div class="tv-fields">';
    fields.forEach(function (f) {
      if (prompt[f]) {
        h += '<div class="tv-field">';
        h += '<div class="tv-field-label">' + f + "</div>";
        h += '<div class="tv-field-value">' + esc(prompt[f]) + "</div>";
        h += "</div>";
      }
    });
    // render any extra fields not in the standard list
    Object.keys(prompt).forEach(function (k) {
      if (fields.indexOf(k) === -1) {
        h += '<div class="tv-field">';
        h += '<div class="tv-field-label">' + k + "</div>";
        h += '<div class="tv-field-value">' + esc(prompt[k]) + "</div>";
        h += "</div>";
      }
    });
    h += "</div>";
    return h;
  }

  /** Returns the ticket that links to this workflow, or null. */
  function findTicketForWorkflow(w) {
    var basePath = w.basePath || "";
    var entry = w.entry || "";
    for (var ti = 0; ti < TICKETS.length; ti++) {
      var ticket = TICKETS[ti];
      var subnumbers = [];
      if (ticket.submit) subnumbers.push(ticket.submit);
      if (ticket.history) subnumbers = subnumbers.concat(ticket.history);
      for (var si = 0; si < subnumbers.length; si++) {
        var result = subnumbers[si].result;
        if (!result) continue;
        // Match by workdir path (basePath 기반)
        if (result.workdir) {
          var wd = result.workdir;
          if (wd.charAt(wd.length - 1) !== "/") wd += "/";
          var normalized = "../../" + wd;
          if (decodeURIComponent(normalized) === decodeURIComponent(basePath)) return ticket;
        }
        // Fallback: match by registrykey (entry = YYYYMMDD-HHMMSS)
        if (result.registrykey && entry && result.registrykey === entry) {
          return ticket;
        }
      }
    }
    return null;
  }

  /** Returns array of workflows linked from any subnumber of a ticket. */
  function findWorkflowsForTicket(ticket) {
    var found = [];
    var subnumbers = [];
    if (ticket.submit) subnumbers.push(ticket.submit);
    if (ticket.history) subnumbers = subnumbers.concat(ticket.history);
    for (var si = 0; si < subnumbers.length; si++) {
      var result = subnumbers[si].result;
      if (!result) continue;
      for (var wi = 0; wi < WORKFLOWS.length; wi++) {
        var w = WORKFLOWS[wi];
        var alreadyFound = found.indexOf(w) !== -1;
        if (alreadyFound) continue;
        // Match by workdir path (basePath 기반)
        if (result.workdir) {
          var wd = result.workdir;
          if (wd.charAt(wd.length - 1) !== "/") wd += "/";
          var normalized = "../../" + wd;
          if (decodeURIComponent(normalized) === decodeURIComponent(w.basePath || "")) {
            found.push(w);
            continue;
          }
        }
        // Fallback: match by registrykey (entry = YYYYMMDD-HHMMSS)
        if (result.registrykey && w.entry && result.registrykey === w.entry) {
          found.push(w);
        }
      }
    }
    return found;
  }

  /** Renders result object keys as clickable links for Viewer tab. */
  function renderResultLinks(result) {
    // If result contains a workflow number (W-NNN), render as a workflow link
    if (result.workflow) {
      var h = '<div class="tv-result-links">';
      h += '<span class="tv-result-link tv-result-workflow" data-workflow="' + esc(result.workflow) + '">' + esc(result.workflow) + '</span>';
      h += '</div>';
      return h;
    }
    var keys = ["plan", "work", "report"];
    var h = '<div class="tv-result-links">';
    // Render registrykey as plain text identifier (not a clickable link)
    if (result.registrykey) {
      h += '<span class="tv-result-id">' + esc(result.registrykey) + '</span>';
    }
    keys.forEach(function (k) {
      if (!result[k]) return;
      var url = encodeURI("../../" + result[k]);
      var isDir = k === "work";
      h += '<span class="tv-result-link" data-label="' + esc(k) + '" data-url="' + esc(url) + '"' + (isDir ? ' data-isdir="true"' : '') + '>' + esc(k) + '</span>';
    });
    // render any extra keys not in the standard list
    // workdir: shown via Connected Workflows section
    // registrykey: identifier only, not a file path link (rendered above)
    var excludedKeys = ["workdir", "registrykey"];
    Object.keys(result).forEach(function (k) {
      if (keys.indexOf(k) === -1 && excludedKeys.indexOf(k) === -1) {
        var url = encodeURI("../../" + result[k]);
        h += '<span class="tv-result-link" data-label="' + esc(k) + '" data-url="' + esc(url) + '">' + esc(k) + '</span>';
      }
    });
    h += "</div>";
    return h;
  }

  // ── Workflow ──
  var WORKFLOWS = [];


  // Files to show as indicators in workflow table columns
  var WF_FILES = [
    { key: "query",   file: "user_prompt.txt", label: "query" },
    { key: "plan",    file: "plan.md",          label: "plan" },
    { key: "report",  file: "report.md",        label: "report" },
    { key: "summary", file: "summary.txt",      label: "summary" },
    { key: "usage",   file: "usage.json",       label: "usage" },
    { key: "log",     file: "workflow.log",     label: "log" },
  ];

  function parseDirLinks(html) {
    var dirs = [];
    var files = [];
    var re = /href="([^"]+)"/g;
    var m;
    while ((m = re.exec(html)) !== null) {
      var href = m[1];
      if (href === "../") continue;
      if (href.endsWith("/")) dirs.push(href);
      else files.push(href);
    }
    return { dirs: dirs, files: files };
  }

  function lastSegment(href) {
    var parts = href.replace(/\/$/, "").split("/");
    return decodeURIComponent(parts[parts.length - 1]);
  }

  function fetchEntriesFrom(baseHref) {
    return fetch(baseHref, { cache: "no-store" }).then(function (res) {
      if (!res.ok) return [];
      return res.text();
    }).then(function (html) {
      return parseDirLinks(html).dirs.filter(function (h) {
        return /\d{8}-\d{6}\/$/.test(h);
      }).map(function (h) {
        return baseHref + h;
      });
    }).catch(function () { return []; });
  }

  // Fetch entry list only (no detail), sorted newest first
  function fetchWorkflowEntries() {
    return Promise.all([
      fetchEntriesFrom("../../.workflow/"),
      fetchEntriesFrom("../../.workflow/.history/"),
    ]).then(function (results) {
      var all = results[0].concat(results[1]);
      // Sort by entry name (timestamp) descending
      all.sort(function (a, b) { return lastSegment(b).localeCompare(lastSegment(a)); });
      return all;
    });
  }

  // Fetch detail for a single entry href
  function fetchEntryDetail(entryHref) {
    var entry = lastSegment(entryHref);
    return fetch(entryHref, { cache: "no-store" }).then(function (r) { return r.text(); }).then(function (h2) {
      var taskLinks = parseDirLinks(h2).dirs.map(function (h) { return entryHref + h; });
      return Promise.all(taskLinks.map(function (taskHref) {
        var task = lastSegment(taskHref);
        return fetch(taskHref, { cache: "no-store" }).then(function (r) { return r.text(); }).then(function (h3) {
          var cmdLinks = parseDirLinks(h3).dirs.map(function (h) { return taskHref + h; });
          return Promise.all(cmdLinks.map(function (cmdHref) {
            var cmd = lastSegment(cmdHref);
            var basePath = cmdHref;
            return fetch(basePath + "status.json", { cache: "no-store" })
              .then(function (r) { return r.ok ? r.json() : null; })
              .then(function (status) {
                if (!status) return null;
                return fetch(basePath, { cache: "no-store" }).then(function (r) { return r.text(); }).then(function (listing) {
                  var parsed = parseDirLinks(listing);
                  var fileNames = parsed.files.map(function (f) { return lastSegment(f); });
                  var hasWork = parsed.dirs.some(function (d) { return lastSegment(d) === "work"; });
                  var fileMap = {};
                  WF_FILES.forEach(function (wf) {
                    var exists = fileNames.indexOf(wf.file) !== -1;
                    fileMap[wf.key] = { exists: exists, url: exists ? basePath + wf.file : "" };
                  });
                  fileMap.work = { exists: hasWork, url: hasWork ? basePath + "work/" : "", isDir: true };
                  return {
                    entry: entry, task: task, command: cmd, basePath: basePath,
                    step: status.step || "NONE",
                    created_at: status.created_at || "",
                    updated_at: status.updated_at || "",
                    transitions: status.transitions || [],
                    fileMap: fileMap,
                  };
                });
              }).catch(function () { return null; });
          }));
        }).catch(function () { return []; });
      }));
    }).then(function (nested) {
      var flat = [];
      nested.forEach(function (a) { a.forEach(function (b) { if (b) flat.push(b); }); });
      return flat;
    }).catch(function () { return []; });
  }

  // Open workflow file in Viewer tab
  function openWfFile(label, url, isDir) {
    var tabId = "wf:" + url;
    var exists = viewerTabs.find(function (t) { return t.number === tabId; });
    if (!exists) {
      viewerTabs.push({ number: tabId, ticket: null, wfFile: { label: label, url: url, content: null, isDir: isDir || url.endsWith("/") } });
    }
    switchTab("viewer");
    activeViewerTab = tabId;
    renderViewer();
    // Fetch content
    var effectiveIsDir = isDir || url.endsWith("/");
    if (effectiveIsDir) {
      fetch(url, { cache: "no-store" }).then(function (r) { return r.text(); }).then(function (html) {
        var tab = viewerTabs.find(function (t) { return t.number === tabId; });
        if (tab && tab.wfFile) {
          var parsed = parseDirLinks(html);
          tab.wfFile.content = JSON.stringify({ files: parsed.files, baseUrl: url });
          tab.wfFile.isDirListing = true;
          if (activeViewerTab === tabId) renderViewer();
        }
      }).catch(function () {});
    } else {
      fetch(url, { cache: "no-store" }).then(function (r) { return r.text(); }).then(function (text) {
        var tab = viewerTabs.find(function (t) { return t.number === tabId; });
        if (tab && tab.wfFile) {
          tab.wfFile.content = text;
          if (activeViewerTab === tabId) renderViewer();
        }
      });
    }
  }

  function renderDirListing(files, baseUrl) {
    if (!files || files.length === 0) {
      return '<div class="empty" style="margin-top:16px">No files</div>';
    }
    var extClass = {
      ".md": "dir-file-md",
      ".json": "dir-file-json",
      ".txt": "dir-file-text",
      ".log": "dir-file-text",
    };
    var h = '<div class="wf-dir-listing">';
    files.forEach(function (href) {
      var name = decodeURIComponent(href.split("/").pop());
      var dotIdx = name.lastIndexOf(".");
      var ext = dotIdx !== -1 ? name.substring(dotIdx) : "";
      var cls = extClass[ext] || "dir-file-other";
      var fileUrl = href.startsWith("http") || href.startsWith("../../") ? href : baseUrl + href;
      h += '<span class="wf-dir-file-link ' + cls + '" data-label="' + esc(name) + '" data-url="' + esc(fileUrl) + '">' + esc(name) + '</span>';
    });
    h += '</div>';
    return h;
  }

  var wfSearchQuery = "";
  var wfSortKey = "updated_at";  // default sort column
  var wfSortDir = "desc";        // default sort direction
  var wfEntryHrefs = [];   // all entry hrefs (sorted newest first)
  var wfLoadedIndex = 0;   // how many entries have been loaded
  var wfLoading = false;
  var WF_PAGE_SIZE = 50;

  function filterWorkflows(list) {
    if (!wfSearchQuery) return list;
    var q = wfSearchQuery.toLowerCase();
    return list.filter(function (w) {
      return w.task.toLowerCase().indexOf(q) !== -1
        || w.command.toLowerCase().indexOf(q) !== -1
        || w.step.toLowerCase().indexOf(q) !== -1
        || w.entry.indexOf(q) !== -1;
    });
  }

  var wfInitialized = false;

  function loadMoreWorkflows() {
    if (wfLoading || wfLoadedIndex >= wfEntryHrefs.length) return;
    wfLoading = true;
    var batch = wfEntryHrefs.slice(wfLoadedIndex, wfLoadedIndex + WF_PAGE_SIZE);
    wfLoadedIndex += batch.length;
    updateWfStatus();
    Promise.all(batch.map(fetchEntryDetail)).then(function (results) {
      var newItems = [];
      results.forEach(function (items) {
        items.forEach(function (w) { WORKFLOWS.push(w); newItems.push(w); });
      });
      WORKFLOWS.sort(function (a, b) { return b.updated_at.localeCompare(a.updated_at); });
      wfLoading = false;
      if (!wfInitialized) {
        wfInitialized = true;
        renderWorkflow();
      } else {
        appendWfRows(filterWorkflows(newItems));
        updateWfStatus();
        attachWfSentinel();
      }
    });
  }

  function updateWfStatus() {
    var countEl = document.querySelector(".wf-search-count");
    var hasMore = wfLoadedIndex < wfEntryHrefs.length;
    if (countEl) {
      var filtered = filterWorkflows(WORKFLOWS);
      countEl.textContent = filtered.length + (hasMore ? '+' : '') + ' / ' + wfEntryHrefs.length;
    }
  }

  function appendWfRows(items) {
    var list = document.getElementById("wf-list");
    if (!list) return;
    // Remove sentinel/loading
    var sentinel = document.getElementById("wf-sentinel");
    if (sentinel) sentinel.remove();
    var loading = list.querySelector(".empty");
    if (loading) {
      var emptyRow = loading.closest("tr");
      if (emptyRow) emptyRow.remove(); else loading.remove();
    }
    // Append new rows using table wrapper to avoid <tr> auto-lifting by browser
    var temp = document.createElement("table");
    var tbody = document.createElement("tbody");
    temp.appendChild(tbody);
    var h = "";
    items.forEach(function (w) { h += renderWfCard(w); });
    tbody.innerHTML = h;
    while (tbody.firstChild) {
      list.appendChild(tbody.firstChild);
    }
    // Bind file links and row clicks on new rows
    bindWfFileLinks(list);
    bindWfRowClicks(list);
  }

  function attachWfSentinel() {
    var list = document.getElementById("wf-list");
    if (!list) return;
    var hasMore = wfLoadedIndex < wfEntryHrefs.length;
    // Remove old sentinel
    var old = document.getElementById("wf-sentinel");
    if (old) {
      var oldRow = old.closest("tr") || old;
      oldRow.remove();
    }
    if (wfLoading) {
      var tr = document.createElement("tr");
      var td = document.createElement("td");
      td.setAttribute("colspan", "12");
      td.className = "empty";
      td.textContent = "Loading...";
      tr.appendChild(td);
      list.appendChild(tr);
    } else if (hasMore) {
      var str = document.createElement("tr");
      var std = document.createElement("td");
      std.setAttribute("colspan", "12");
      std.className = "wf-load-more";
      std.id = "wf-sentinel";
      std.textContent = "Scroll for more";
      str.appendChild(std);
      list.appendChild(str);
      var observer = new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting) {
          observer.disconnect();
          loadMoreWorkflows();
        }
      });
      observer.observe(std);
    }
  }

  function bindWfFileLinks(container) {
    container.querySelectorAll(".wf-file-indicator.active:not([data-bound])").forEach(function (link) {
      link.setAttribute("data-bound", "1");
      link.addEventListener("click", function (e) {
        e.stopPropagation();
        var isDir = link.dataset.isdir === "true";
        openWfFile(link.dataset.label, link.dataset.url, isDir);
      });
    });
  }

  function bindWfRowClicks(container) {
    container.querySelectorAll(".wf-row:not([data-row-bound])").forEach(function (row) {
      row.setAttribute("data-row-bound", "1");
      row.addEventListener("click", function (e) {
        // Do not trigger if the click was on a file indicator link
        if (e.target.closest(".wf-file-indicator.active")) return;
        // Do not trigger if the click was on a ticket badge
        if (e.target.closest(".wf-ticket-badge")) return;
        var entryKey = row.dataset.entry;
        var taskKey = row.dataset.task;
        var cmdKey = row.dataset.cmd;
        var w = WORKFLOWS.find(function (item) {
          return item.entry === entryKey && item.task === taskKey && item.command === cmdKey;
        });
        if (w) openWfDetail(w);
      });
    });
    // Ticket badge clicks: navigate to the linked ticket
    container.querySelectorAll(".wf-ticket-badge:not([data-badge-bound])").forEach(function (badge) {
      badge.setAttribute("data-badge-bound", "1");
      badge.addEventListener("click", function (e) {
        e.stopPropagation();
        var ticketNum = badge.dataset.ticketNum;
        var ticket = TICKETS.find(function (t) { return t.number === ticketNum; });
        if (ticket) openViewer(ticket);
      });
    });
  }

  function openWfDetail(w) {
    var tabId = "wfDetail:" + w.entry + "/" + w.task + "/" + w.command;
    var label = (w.number || w.entry) + " / " + w.task;
    var exists = viewerTabs.find(function (t) { return t.number === tabId; });
    if (!exists) {
      viewerTabs.push({ number: tabId, ticket: null, wfFile: null, wfDetail: w });
    } else {
      exists.wfDetail = w;
    }
    switchTab("viewer");
    activeViewerTab = tabId;
    renderViewer();
    saveUI();
  }

  function renderWfDetailView(w) {
    var h = '<div class="tv-container wf-detail-container">';

    // Header: linkedTicket 번호 또는 entry fallback + command + step
    var headerLinkedTicket = findTicketForWorkflow(w);
    h += '<div class="tv-header">';
    h += '<div class="tv-header-top">';
    if (headerLinkedTicket) {
      h += '<span class="tv-number">' + esc(headerLinkedTicket.number) + '</span>';
    } else {
      h += '<span class="tv-number wf-number-fallback">' + esc(w.entry) + '</span>';
    }
    var stepIsDone = (w.step || "").toUpperCase() === "DONE";
    var stepColors = stepIsDone ? STATUS_COLORS.Done : STATUS_COLORS["In Progress"];
    h += '<span class="badge wf-step-badge" style="background:' + stepColors.bg + ";color:" + stepColors.fg + '">' + esc(w.step || "NONE") + '</span>';
    if (w.command) {
      h += badge(w.command, CMD_COLORS[w.command] || { bg: "rgba(133,133,133,0.25)", fg: "#a0a0a0" });
    }
    h += '</div>';
    h += '<h1 class="tv-title">' + esc(w.task) + '</h1>';
    h += '<div class="tv-meta">';
    h += '<span class="tv-time">' + esc(formatTime(w.created_at)) + '</span>';
    h += '</div>';
    h += '</div>';

    // Info section
    h += '<div class="tv-section">';
    h += '<div class="tv-section-title">Info</div>';
    h += '<div class="wf-detail-info">';
    h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Entry</span><span class="wf-detail-info-value">' + esc(w.entry) + '</span></div>';
    h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Command</span><span class="wf-detail-info-value">' + esc(w.command) + '</span></div>';
    h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Step</span><span class="wf-detail-info-value">' + esc(w.step || "NONE") + '</span></div>';
    h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Created</span><span class="wf-detail-info-value">' + esc(formatTime(w.created_at)) + '</span></div>';
    h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Updated</span><span class="wf-detail-info-value">' + esc(formatTime(w.updated_at)) + '</span></div>';
    var infoTicket = findTicketForWorkflow(w);
    if (infoTicket) {
      h += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Ticket</span><span class="wf-detail-info-value"><span class="wf-detail-ticket-link" data-ticket-num="' + esc(infoTicket.number) + '">' + esc(infoTicket.number) + '</span></span></div>';
    }
    h += '</div>';
    h += '</div>';

    // Transitions timeline
    if (w.transitions && w.transitions.length > 0) {
      h += '<div class="tv-section">';
      h += '<div class="tv-section-title">Transitions</div>';
      h += '<div class="wf-detail-transitions">';
      h += '<table class="wf-detail-transition-table">';
      h += '<thead><tr><th>From</th><th>To</th><th>Time</th></tr></thead>';
      h += '<tbody>';
      w.transitions.forEach(function (tr) {
        h += '<tr>';
        h += '<td>' + esc(tr.from || "NONE") + '</td>';
        h += '<td>' + esc(tr.to || "") + '</td>';
        h += '<td class="wf-detail-transition-time">' + esc(formatTime(tr.at || "")) + '</td>';
        h += '</tr>';
      });
      h += '</tbody></table>';
      h += '</div>';
      h += '</div>';
    }

    // Artifact links
    if (w.fileMap) {
      h += '<div class="tv-section">';
      h += '<div class="tv-section-title">Artifacts</div>';
      h += '<div class="wf-detail-artifacts">';
      WF_FILE_COLS.forEach(function (key) {
        var info = w.fileMap[key];
        if (info && info.exists) {
          var isDir = info.isDir ? ' data-isdir="true"' : '';
          h += '<span class="wf-detail-artifact-link" data-label="' + esc(w.task + ' / ' + key) + '" data-url="' + esc(info.url) + '"' + isDir + '>' + esc(key) + '</span>';
        } else {
          h += '<span class="wf-detail-artifact-absent">' + esc(key) + '</span>';
        }
      });
      h += '</div>';
      h += '</div>';
    }

    // Connected ticket (try to fetch .context.json)
    h += '<div class="wf-detail-ticket-section" data-basepath="' + esc(w.basePath || "") + '"></div>';

    h += '</div>';
    return h;
  }

  function sortWorkflows(list) {
    var key = wfSortKey;
    var dir = wfSortDir === "asc" ? 1 : -1;
    return list.slice().sort(function (a, b) {
      var av = (a[key] || "").toString();
      var bv = (b[key] || "").toString();
      return dir * av.localeCompare(bv);
    });
  }

  function renderWorkflow() {
    var el = document.getElementById("view-workflow");
    var filtered = filterWorkflows(WORKFLOWS);
    var hasMore = wfLoadedIndex < wfEntryHrefs.length;

    var h = '<div class="wf-container">';

    // Search bar
    h += '<div class="wf-search-bar">';
    h += '<input class="wf-search" type="text" placeholder="Search workflows..." value="' + esc(wfSearchQuery) + '">';
    h += '<span class="wf-search-count">' + filtered.length + (hasMore ? '+' : '') + ' / ' + wfEntryHrefs.length + '</span>';
    h += '</div>';

    // Table
    var sortedFiltered = sortWorkflows(filtered);
    var cols = [
      { key: "step",       label: "상태" },
      { key: "number",     label: "번호" },
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

    h += '<div class="wf-table-wrap"><table class="wf-table">';
    h += '<thead><tr>';
    cols.forEach(function (col) {
      var indicator = "";
      if (!col.nosort) {
        if (wfSortKey === col.key) {
          indicator = wfSortDir === "asc"
            ? ' <span class="wf-sort-indicator">&#9650;</span>'
            : ' <span class="wf-sort-indicator">&#9660;</span>';
        } else {
          indicator = ' <span class="wf-sort-inactive">&#9650;&#9660;</span>';
        }
      }
      var sortable = col.nosort ? "" : ' class="wf-th-sortable" data-sort-key="' + col.key + '"';
      h += '<th' + sortable + '>' + col.label + indicator + '</th>';
    });
    h += '</tr></thead>';

    h += '<tbody id="wf-list">';
    if (sortedFiltered.length > 0) {
      sortedFiltered.forEach(function (w) { h += renderWfCard(w); });
    } else if (!wfLoading) {
      h += '<tr><td colspan="12" class="empty" style="margin-top:32px">' + (wfSearchQuery ? "No results" : "No workflows") + '</td></tr>';
    }
    h += '</tbody></table></div></div>';

    el.innerHTML = h;

    // Search input
    el.querySelector(".wf-search").addEventListener("input", function (e) {
      wfSearchQuery = e.target.value;
      wfInitialized = false;
      renderWorkflow();
      var input = el.querySelector(".wf-search");
      if (input) { input.focus(); input.selectionStart = input.selectionEnd = input.value.length; }
    });

    // Sort header clicks
    el.querySelectorAll("th[data-sort-key]").forEach(function (th) {
      th.addEventListener("click", function () {
        var key = th.getAttribute("data-sort-key");
        if (wfSortKey === key) {
          wfSortDir = wfSortDir === "asc" ? "desc" : "asc";
        } else {
          wfSortKey = key;
          wfSortDir = "desc";
        }
        renderWorkflow();
      });
    });

    bindWfFileLinks(el);
    bindWfRowClicks(el);
    attachWfSentinel();
    bindWfColResize(el);
  }

  // Counter for generating unique viewer IDs
  var codeViewerIdCounter = 0;

  function renderWfFileView(wfFile) {
    var h = '<div class="tv-container">';
    h += '<div class="tv-header"><h1 class="tv-title">' + esc(wfFile.label) + '</h1></div>';
    if (wfFile.content === null) {
      h += '<div class="empty">Loading...</div>';
    } else if (wfFile.isDirListing) {
      var parsed = JSON.parse(wfFile.content);
      h += renderDirListing(parsed.files, parsed.baseUrl);
    } else if (wfFile.url.endsWith(".md")) {
      h += '<div class="md-body">' + renderMd(wfFile.content, wfFile.url) + '</div>';
    } else {
      var lang = getHighlightLang(wfFile.url);
      var lines = wfFile.content.split("\n");
      var lineCount = lines.length;
      // Remove trailing empty line produced by split when file ends with newline
      if (lineCount > 0 && lines[lineCount - 1] === "") {
        lines = lines.slice(0, lineCount - 1);
        lineCount = lines.length;
      }
      var numWidth = String(lineCount).length;
      var rows = lines.map(function (line, i) {
        var num = String(i + 1);
        while (num.length < numWidth) num = " " + num;
        return '<span class="code-line-number">' + esc(num) + '</span><span class="code-line-content">' + esc(line) + '</span>';
      });

      var viewerId = "cv-" + (++codeViewerIdCounter);
      var INITIAL_LINES = 500;
      var LARGE_THRESHOLD = 3000;
      var isLarge = lineCount > LARGE_THRESHOLD;
      var initialRows = isLarge ? rows.slice(0, INITIAL_LINES) : rows;

      // Store pending rows and original lines for large files and search
      codeViewerStore[viewerId] = {
        pendingRows: isLarge ? rows.slice(INITIAL_LINES) : [],
        allLines: lines,
        nextChunk: INITIAL_LINES,
        searchMatches: [],
        searchIndex: -1,
        lang: lang
      };

      var searchBarHtml = '<div class="code-search-bar" style="display:none">'
        + '<input class="code-search-input" type="text" placeholder="Search..." aria-label="코드 검색" />'
        + '<span class="code-search-count"></span>'
        + '<button class="code-search-nav-btn" data-dir="prev" aria-label="이전 결과">&#9650;</button>'
        + '<button class="code-search-nav-btn" data-dir="next" aria-label="다음 결과">&#9660;</button>'
        + '<button class="code-search-close-btn" aria-label="검색 닫기">&times;</button>'
        + '</div>';

      var lazyAttr = isLarge ? ' data-lazy="true"' : '';
      h += '<div class="code-viewer" data-viewer-id="' + viewerId + '">'
        + '<button class="code-copy-btn" aria-label="코드 복사">Copy</button>'
        + searchBarHtml
        + '<pre><code class="hljs-pending language-' + esc(lang) + '"' + lazyAttr + '>'
        + initialRows.join("\n")
        + '</code></pre></div>';
    }
    h += '</div>';
    return h;
  }

  // ── Highlight.js Language Mapping ──
  function getHighlightLang(url) {
    var LANG_MAP = {
      ".py":   "python",
      ".js":   "javascript",
      ".ts":   "typescript",
      ".jsx":  "javascript",
      ".tsx":  "typescript",
      ".md":   "markdown",
      ".xml":  "xml",
      ".sh":   "bash",
      ".json": "json",
      ".css":  "css",
      ".html": "html",
      ".yml":  "yaml",
      ".yaml": "yaml"
    };
    var m = url && url.match(/(\.[^./?#]+)(?:[?#].*)?$/);
    if (!m) return "plaintext";
    return LANG_MAP[m[1].toLowerCase()] || "plaintext";
  }

  function initHighlight() {
    var blocks = document.querySelectorAll(".code-viewer code.hljs-pending, .md-body code.hljs-pending");
    blocks.forEach(function (block) {
      if (block.dataset.highlighted) return;
      block.dataset.highlighted = "true";
      block.classList.remove("hljs-pending");
      if (typeof hljs === "undefined") return;
      // Extract language from class name (e.g. "language-javascript")
      var lang = null;
      var classes = block.className.split(/\s+/);
      for (var i = 0; i < classes.length; i++) {
        var m = classes[i].match(/^language-(.+)$/);
        if (m) {
          lang = m[1];
          break;
        }
      }
      // Only highlight if language is registered; skip plaintext and unregistered languages
      if (lang && lang !== "plaintext" && hljs.getLanguage(lang)) {
        hljs.highlightElement(block);
      }
    });
  }

  // ── Markdown Rendering ──
  var mermaidCounter = 0;

  /** Returns the directory portion of a URL (up to and including the last '/'). */
  function urlDir(url) {
    if (!url) return "";
    return url.substring(0, url.lastIndexOf("/") + 1);
  }

  function renderMd(text, baseUrl) {
    if (typeof marked === "undefined") return '<pre class="wf-file-content">' + esc(text) + '</pre>';

    var renderer = new marked.Renderer();
    renderer.code = function (opts) {
      var code = typeof opts === "object" ? opts.text : opts;
      var lang = typeof opts === "object" ? opts.lang : arguments[1];
      if (lang === "mermaid") {
        var id = "mermaid-" + (++mermaidCounter);
        return '<div class="mermaid-block" data-mermaid-id="' + id + '">' + esc(code) + '</div>';
      }
      var langClass = lang ? lang : "plaintext";
      return '<pre class="md-code"><code class="hljs-pending language-' + esc(langClass) + '">' + esc(code) + '</code></pre>';
    };

    renderer.link = function (opts) {
      var href = typeof opts === "object" ? opts.href : opts;
      var title = typeof opts === "object" ? opts.title : arguments[1];
      var text = typeof opts === "object" ? opts.text : arguments[2];
      if (!href) return text || "";
      // External links: render as normal anchor with target="_blank"
      if (href.indexOf("http://") === 0 || href.indexOf("https://") === 0) {
        var titleAttr = title ? ' title="' + esc(title) + '"' : "";
        return '<a href="' + esc(href) + '"' + titleAttr + ' target="_blank" rel="noopener noreferrer">' + (text || esc(href)) + '</a>';
      }
      // Internal relative links: convert to md-file-link span
      var resolvedUrl;
      if (href.indexOf(".workflow/") === 0 || href.indexOf(".claude/") === 0) {
        // Project-root-relative path: prepend "../../" to reach project root from board.html
        resolvedUrl = "../../" + href;
      } else {
        // Report-relative path (e.g. "work/..."): resolve against baseUrl directory
        resolvedUrl = urlDir(baseUrl) + href;
      }
      return '<span class="md-file-link" data-filepath="' + esc(href) + '" data-url="' + esc(resolvedUrl) + '">' + (text || esc(href)) + '</span>';
    };

    var html = marked.parse(text, { renderer: renderer, gfm: true, breaks: true });

    // Post-process: convert file path patterns inside <code> tags to clickable links
    // Matches: paths with '/' or known file extensions
    var FILE_EXT_RE = /\.(md|js|ts|jsx|tsx|css|html|json|py|txt|log|xml|sh|yml|yaml|toml|env|csv)$/i;
    html = html.replace(/<code>([^<]+)<\/code>/g, function (match, inner) {
      var decoded = inner.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&#39;/g, "'").replace(/&quot;/g, '"');
      var isFilePath = decoded.indexOf("/") !== -1 || FILE_EXT_RE.test(decoded.trim());
      if (isFilePath) {
        var escaped = esc(decoded.trim());
        return '<code class="md-file-link" data-filepath="' + escaped + '">' + inner + '</code>';
      }
      return match;
    });

    return html;
  }

  function initMermaid() {
    var blocks = document.querySelectorAll(".mermaid-block");
    blocks.forEach(function (block) {
      var id = block.dataset.mermaidId;
      if (block.dataset.rendered) return;
      block.dataset.rendered = "true";
      var code = block.textContent;
      if (typeof mermaid !== "undefined") {
        mermaid.render(id, code).then(function (result) {
          block.innerHTML = result.svg;
        }).catch(function () {
          block.innerHTML = '<pre class="wf-file-content">' + esc(code) + '</pre>';
        });
      }
    });
  }

  var WF_FILE_COLS = ["query", "plan", "work", "report", "summary", "usage", "log"];

  function renderWfCard(w) {
    var h = '<tr class="wf-row" data-entry="' + esc(w.entry) + '" data-task="' + esc(w.task) + '" data-cmd="' + esc(w.command) + '">';
    // step cell
    var stepIsDone = (w.step || "").toUpperCase() === "DONE";
    var stepColors = stepIsDone ? STATUS_COLORS.Done : STATUS_COLORS["In Progress"];
    var stepText = esc(w.step || "NONE");
    var stepBadge = '<span class="badge wf-step-badge" style="background:' + stepColors.bg + ";color:" + stepColors.fg + '">' + stepText + '</span>';
    h += '<td class="wf-row-step">' + stepBadge + '</td>';
    // number cell: linkedTicket이 있으면 T-NNN 배지(클릭으로 티켓 뷰어 이동), 없으면 타임스탬프 fallback
    var linkedTicket = findTicketForWorkflow(w);
    if (linkedTicket) {
      h += '<td class="wf-row-number"><span class="wf-number-badge wf-ticket-badge" data-ticket-num="' + esc(linkedTicket.number) + '">' + esc(linkedTicket.number) + '</span></td>';
    } else {
      // Timestamp fallback: extract MMDD-HHMM from entry (format: YYYYMMDD-HHMMSS)
      var ts = w.entry || "";
      var fallback = ts.length >= 13 ? ts.substring(4, 8) + '-' + ts.substring(9, 13) : ts;
      h += '<td class="wf-row-number"><span class="wf-number-fallback">' + esc(fallback) + '</span></td>';
    }
    // command cell
    h += '<td class="wf-row-cmd">' + badge(w.command, CMD_COLORS[w.command] || { bg: "rgba(133,133,133,0.25)", fg: "#a0a0a0" }) + '</td>';
    // task cell
    h += '<td class="wf-row-title">' + esc(w.task) + '</td>';
    // file indicator cells (query, plan, work, report, summary, usage, log)
    WF_FILE_COLS.forEach(function (key) {
      var info = w.fileMap && w.fileMap[key];
      if (info && info.exists) {
        var isDir = info.isDir ? ' data-isdir="true"' : '';
        h += '<td class="wf-row-file"><span class="wf-file-indicator active" data-label="' + esc(w.task + ' / ' + key) + '" data-url="' + esc(info.url) + '"' + isDir + '>&#9679;</span></td>';
      } else {
        h += '<td class="wf-row-file"><span class="wf-file-indicator">&#9675;</span></td>';
      }
    });
    // updated_at cell
    h += '<td class="wf-row-time">' + esc(w.updated_at.substring(0, 16)) + '</td>';
    h += '</tr>';
    return h;
  }

  // ── Workflow Column Resize ──
  function bindWfColResize(container) {
    var table = container.querySelector(".wf-table");
    if (!table) return;
    var ths = table.querySelectorAll("thead th");
    ths.forEach(function (th, idx) {
      // Skip last column (no right handle needed on last)
      if (idx === ths.length - 1) return;
      var handle = th.querySelector(".wf-col-resize-handle");
      if (handle) return; // already bound
      handle = document.createElement("div");
      handle.className = "wf-col-resize-handle";
      th.appendChild(handle);

      var startX, startWidth, nextStartWidth, nextTh;

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
          var dx = ev.clientX - startX;
          var newWidth = Math.max(30, startWidth + dx);
          th.style.width = newWidth + "px";
          if (nextTh) {
            var newNext = Math.max(30, nextStartWidth - dx);
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

  // ── Dashboard ──
  var DASH_FILES = ["usage", "logs", "skills"];
  var dashData = {};          // { usage: text, logs: text, skills: text }
  var dashFetched = false;
  var dashChartInstances = {}; // { canvasId: Chart } - track instances for destroy-before-recreate

  /**
   * Fetches a single dashboard markdown file.
   * @param {string} name - file name without extension (usage|logs|skills)
   * @returns {Promise<string>}
   */
  function fetchDashboardFile(name) {
    var url = "../../.dashboard/." + name + ".md";
    return fetch(url, { cache: "no-store" }).then(function (res) {
      if (!res.ok) return "";
      return res.text();
    }).catch(function () { return ""; });
  }

  /**
   * Fetches all dashboard files in parallel and caches in dashData.
   * @returns {Promise<Object>}
   */
  function fetchAllDashboardFiles() {
    return Promise.all(DASH_FILES.map(fetchDashboardFile)).then(function (results) {
      DASH_FILES.forEach(function (name, i) { dashData[name] = results[i]; });
      dashFetched = true;
      return dashData;
    });
  }

  /**
   * Parses markdown table rows (skipping header and separator rows).
   * Returns array of row cell-arrays.
   * @param {string} text
   * @returns {Array<Array<string>>}
   */
  function parseMdTableRows(text) {
    var rows = [];
    var lines = (text || "").split("\n");
    var inTable = false;
    var headerSeen = false;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (!line.startsWith("|")) {
        if (inTable) break; // table ended
        continue;
      }
      if (!inTable) { inTable = true; headerSeen = false; continue; } // first row = header
      if (!headerSeen) { headerSeen = true; continue; }               // second row = separator
      var cells = line.split("|").slice(1, -1).map(function (c) { return c.trim(); });
      rows.push(cells);
    }
    return rows;
  }

  /**
   * Extracts header cells from first markdown table in text.
   * @param {string} text
   * @returns {Array<string>}
   */
  function parseMdTableHeader(text) {
    var lines = (text || "").split("\n");
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (line.startsWith("|")) {
        return line.split("|").slice(1, -1).map(function (c) { return c.trim(); });
      }
    }
    return [];
  }

  /**
   * Parses a token string like "1621k" to a number.
   * @param {string} val
   * @returns {number}
   */
  function parseToken(val) {
    if (!val || val === "-") return 0;
    var cleaned = val.replace(/,/g, "").trim();
    if (cleaned.endsWith("k")) return parseFloat(cleaned) * 1000;
    return parseFloat(cleaned) || 0;
  }

  /**
   * Computes KPI stats from raw dashboard text data.
   * @param {Object} data - { usage, logs, skills, history }
   * @returns {Object} stats with totalWorkflows, totalTokens, warnErrors, topSkill
   */
  function computeKpiStats(data) {
    // usage.md: count rows, sum 합계 column (index 10, last col)
    var usageRows = parseMdTableRows(data.usage || "");
    var totalWorkflows = usageRows.length;
    var totalTokens = 0;
    usageRows.forEach(function (cells) {
      // 합계 is the last column (index 10 for | 날짜 | 작업ID | 제목 | 명령 | ORC | PLN | WRK | EXP | VAL | RPT | 합계 |)
      var last = cells[cells.length - 1] || "-";
      totalTokens += parseToken(last);
    });

    // logs.md: count non-zero WARN (col 4) and ERROR (col 5)
    var logsRows = parseMdTableRows(data.logs || "");
    var warnErrors = 0;
    logsRows.forEach(function (cells) {
      var warn = parseInt(cells[4] || "0", 10) || 0;
      var error = parseInt(cells[5] || "0", 10) || 0;
      warnErrors += warn + error;
    });

    // skills.md: count skill occurrences, find top skill
    var skillsRows = parseMdTableRows(data.skills || "");
    var skillCount = {};
    skillsRows.forEach(function (cells) {
      // | 날짜 | 작업ID | 명령어 | 태스크수 | 고유스킬수 | 스킬 목록 | fallback | 토큰초과 |
      // 스킬 목록 is at index 5 - may contain <br> separated multiple skill groups
      var skillList = cells[5] || "";
      // split by <br> or comma
      var parts = skillList.split(/<br\s*\/?>/i);
      parts.forEach(function (part) {
        var skills = part.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
        skills.forEach(function (s) {
          skillCount[s] = (skillCount[s] || 0) + 1;
        });
      });
    });
    var topSkill = "-";
    var topCount = 0;
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

  /**
   * Formats token count to human-readable string (e.g. 1.6M, 500k).
   * @param {number} n
   * @returns {string}
   */
  function formatTokens(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
    if (n >= 1000) return Math.round(n / 1000) + "k";
    return String(Math.round(n));
  }

  /**
   * Renders the 4 KPI Summary Cards with left accent borders.
   * @param {Object} stats - KPI stats from computeKpiStats
   * @returns {string} HTML
   */
  function renderDashCards(stats) {
    var cards = [
      { label: "Total Workflows", value: String(stats.totalWorkflows), sub: "all time", accent: "#569cd6" },
      { label: "Total Tokens", value: formatTokens(stats.totalTokens), sub: "cumulative", accent: "#4ec9b0" },
      { label: "Warn / Error", value: String(stats.warnErrors), sub: "across all runs", accent: "#dcdcaa" },
      { label: "Top Skill", value: stats.topSkill, sub: "most used", accent: "#c586c0" },
    ];
    var h = '<div class="dash-cards">';
    cards.forEach(function (card) {
      h += '<div class="dash-card" style="border-left-color:' + card.accent + '">';
      h += '<div class="dash-card-label">' + esc(card.label) + '</div>';
      h += '<div class="dash-card-value">' + esc(card.value) + '</div>';
      h += '<div class="dash-card-sub">' + esc(card.sub) + '</div>';
      h += '</div>';
    });
    h += '</div>';
    return h;
  }

  /**
   * Renders a markdown table from header array + rows array to HTML table.
   * @param {Array<string>} headers
   * @param {Array<Array<string>>} rows
   * @returns {string} HTML
   */
  function renderMdTable(headers, rows) {
    if (!rows || rows.length === 0) return '<div class="empty">No data</div>';
    var h = '<div class="md-body"><table>';
    h += '<thead><tr>';
    headers.forEach(function (hdr) { h += '<th>' + esc(hdr) + '</th>'; });
    h += '</tr></thead>';
    h += '<tbody>';
    rows.forEach(function (cells) {
      h += '<tr>';
      cells.forEach(function (cell) {
        // Render markdown links inside cell: [text](url)
        var rendered = cell.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, text, url) {
          return '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(text) + '</a>';
        });
        // Render <br> as line break
        rendered = rendered.replace(/<br\s*\/?>/gi, "<br>");
        h += '<td>' + rendered + '</td>';
      });
      h += '</tr>';
    });
    h += '</tbody></table></div>';
    return h;
  }

  /**
   * Destroys an existing Chart instance by canvas ID, if any.
   * @param {string} canvasId - the id attribute of the canvas element
   */
  function destroyChart(canvasId) {
    if (dashChartInstances[canvasId]) {
      dashChartInstances[canvasId].destroy();
      delete dashChartInstances[canvasId];
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
    var canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    destroyChart(canvasId);
    var instance = new Chart(canvas.getContext("2d"), config);
    dashChartInstances[canvasId] = instance;
    return instance;
  }

  /**
   * Renders token usage bar+line composite chart.
   * Bar = token total per workflow, Line = same data as line overlay.
   * @param {Array<Array<string>>} rows - parsed usage table rows
   */
  function renderUsageChart(rows) {
    if (!rows.length) return;
    // Reverse to chronological order (oldest first)
    var chronoRows = rows.slice().reverse();
    var labels = chronoRows.map(function (c) { return c[0] || ""; });
    var values = chronoRows.map(function (c) { return parseToken(c[c.length - 1] || "0"); });

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
            order: 2
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
            order: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#cccccc", boxWidth: 12, font: { size: 11 } } }
        },
        scales: {
          x: {
            ticks: { color: "#858585", font: { size: 10 }, maxRotation: 45 },
            grid: { color: "#2d2d2d" }
          },
          y: {
            ticks: { color: "#858585", font: { size: 10 } },
            grid: { color: "#2d2d2d" }
          }
        }
      }
    });
  }

  /**
   * Renders command type pie chart from usage rows.
   * Aggregates command column (index 3) frequency.
   * @param {Array<Array<string>>} rows - parsed usage table rows
   */
  function renderCommandPieChart(rows) {
    if (!rows.length) return;
    var cmdCount = {};
    rows.forEach(function (cells) {
      var cmd = (cells[3] || "other").trim().toLowerCase();
      cmdCount[cmd] = (cmdCount[cmd] || 0) + 1;
    });

    var colorMap = {
      implement: "#569cd6",
      review: "#c586c0",
      research: "#dcdcaa"
    };

    var labels = Object.keys(cmdCount);
    var values = labels.map(function (k) { return cmdCount[k]; });
    var colors = labels.map(function (k) { return colorMap[k] || "#858585"; });

    createChart("chart-command", {
      type: "pie",
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: "#1e1e1e",
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "right",
            labels: { color: "#cccccc", padding: 12, font: { size: 11 } }
          }
        }
      }
    });
  }

  /**
   * Renders WARN/ERROR time series line chart from logs rows.
   * @param {Array<Array<string>>} rows - parsed logs table rows
   */
  function renderWarnErrorChart(rows) {
    if (!rows.length) return;
    var chronoRows = rows.slice().reverse();
    var labels = chronoRows.map(function (c) { return c[0] || ""; });
    var warns = chronoRows.map(function (c) { return parseInt(c[4] || "0", 10) || 0; });
    var errors = chronoRows.map(function (c) { return parseInt(c[5] || "0", 10) || 0; });

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
            tension: 0.2
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
            tension: 0.2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#cccccc", boxWidth: 12, font: { size: 11 } } }
        },
        scales: {
          x: {
            ticks: { color: "#858585", font: { size: 10 }, maxRotation: 45 },
            grid: { color: "#2d2d2d" }
          },
          y: {
            beginAtZero: true,
            ticks: { color: "#858585", font: { size: 10 } },
            grid: { color: "#2d2d2d" }
          }
        }
      }
    });
  }

  /**
   * Renders skill frequency horizontal bar chart from skills rows.
   * Shows top 10 most used skills.
   * @param {Array<Array<string>>} rows - parsed skills table rows
   */
  function renderSkillFreqChart(rows) {
    if (!rows.length) return;
    var skillCount = {};
    rows.forEach(function (cells) {
      var skillList = cells[5] || "";
      var parts = skillList.split(/<br\s*\/?>/i);
      parts.forEach(function (part) {
        var skills = part.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
        skills.forEach(function (s) {
          skillCount[s] = (skillCount[s] || 0) + 1;
        });
      });
    });

    // Sort by count descending, take top 10
    var sorted = Object.keys(skillCount).sort(function (a, b) {
      return skillCount[b] - skillCount[a];
    }).slice(0, 10);

    var labels = sorted;
    var values = sorted.map(function (k) { return skillCount[k]; });

    createChart("chart-skills", {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "Frequency",
          data: values,
          backgroundColor: "rgba(197,134,192,0.6)",
          borderColor: "#c586c0",
          borderWidth: 1
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: { color: "#858585", font: { size: 10 } },
            grid: { color: "#2d2d2d" }
          },
          y: {
            ticks: { color: "#cccccc", font: { size: 10 } },
            grid: { display: false }
          }
        }
      }
    });
  }

  /**
   * Main Dashboard render entry point.
   * Fetches data (first time) then renders KPI cards + chart sections + tables
   * in a single scrollable page layout.
   */
  function renderDashboard() {
    var el = document.getElementById("view-dashboard");
    if (!el) return;

    // Show loading state before data arrives
    if (!dashFetched) {
      el.innerHTML = '<div class="empty" style="margin-top:48px">Loading...</div>';
      fetchAllDashboardFiles().then(function () { renderDashboard(); });
      return;
    }

    // Set Chart.js dark theme defaults
    if (typeof Chart !== "undefined") {
      Chart.defaults.color = "#cccccc";
      Chart.defaults.borderColor = "#2d2d2d";
    }

    var stats = computeKpiStats(dashData);
    var h = renderDashCards(stats);

    // Parse all data
    var usageHeaders = parseMdTableHeader(dashData.usage || "");
    var usageRows = parseMdTableRows(dashData.usage || "");
    var logsHeaders = parseMdTableHeader(dashData.logs || "");
    var logsRows = parseMdTableRows(dashData.logs || "");
    var skillsHeaders = parseMdTableHeader(dashData.skills || "");
    var skillsRows = parseMdTableRows(dashData.skills || "");
    // Normalize skills column: replace commas with <br> so each skill is on its own line
    skillsRows.forEach(function (cells) {
      if (cells[5]) {
        cells[5] = cells[5].split(/,\s*|<br\s*\/?>/i).filter(Boolean).join("<br>");
      }
    });

    // ── Charts (all at top) ──
    h += '<div class="dash-section">';
    h += '<h3 class="dash-section-title">Charts</h3>';
    h += '<div class="dash-chart-row">';
    h += '<div class="dash-chart-container"><canvas id="chart-usage" height="260"></canvas></div>';
    h += '<div class="dash-chart-container"><canvas id="chart-command" height="260"></canvas></div>';
    h += '</div>';
    h += '<div class="dash-chart-row">';
    h += '<div class="dash-chart-container"><canvas id="chart-warn-error" height="260"></canvas></div>';
    h += '<div class="dash-chart-container"><canvas id="chart-skills" height="260"></canvas></div>';
    h += '</div>';
    h += '</div>';

    // ── Tables (bottom, tabbed) ──
    h += '<div class="dash-section">';
    h += '<h3 class="dash-section-title">Data</h3>';
    h += '<div class="dash-table-tabs">';
    h += '<button class="dash-table-tab active" data-table="usage">Usage</button>';
    h += '<button class="dash-table-tab" data-table="logs">Logs</button>';
    h += '<button class="dash-table-tab" data-table="skills">Skills</button>';
    h += '</div>';
    h += '<div class="dash-table-panel active" data-table="usage">' + renderMdTable(usageHeaders, usageRows) + '</div>';
    h += '<div class="dash-table-panel" data-table="logs">' + renderMdTable(logsHeaders, logsRows) + '</div>';
    h += '<div class="dash-table-panel" data-table="skills">' + renderMdTable(skillsHeaders, skillsRows) + '</div>';
    h += '</div>';

    el.innerHTML = h;

    // Wire up table tab switching
    el.querySelectorAll(".dash-table-tab").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var target = btn.getAttribute("data-table");
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

  // ── SSE / Polling ──
  var SSE_TIMEOUT = 3000;        // SSE 연결 타임아웃 (ms)
  var SSE_RETRY_INTERVAL = 30000; // SSE 재시도 간격 (ms)
  var POLL_INTERVAL = 2000;      // 폴링 간격 (ms)

  var sseConnected = false;
  var sseGaveUp = false;         // SSE를 포기하고 폴링 모드인지
  var sseRetryTimerId = null;
  var pollTimerId = null;

  var prevTicketJson = "";
  var prevWfJson = "";

  function ticketJson(tickets) {
    return JSON.stringify(tickets.map(function (t) {
      return { number: t.number, title: t.title, status: t.status, current: t.current,
               submit: t.submit, history: t.history };
    }));
  }

  // ── 칸반 갱신 (SSE/폴링 공용) ──
  /**
   * 칸반을 갱신한다.
   * @param {string[]} [files] - 변경된 파일명 배열. 있으면 선택적 fetch, 없으면 전체 fetch.
   */
  function refreshKanban(files) {
    var fetchPromise = (files && files.length > 0)
      ? fetchTicketsByFiles(files).then(function () { return TICKETS; })
      : fetchTickets().then(function (tickets) { TICKETS = tickets; return TICKETS; });

    fetchPromise.then(function (tickets) {
      var json = ticketJson(tickets);
      if (json !== prevTicketJson) {
        prevTicketJson = json;
        renderKanban();
        viewerTabs.forEach(function (vt) {
          if (vt.ticket) {
            var fresh = TICKETS.find(function (t) { return t.number === vt.number; });
            if (fresh) vt.ticket = fresh;
          }
        });
        var activeVt = viewerTabs.find(function (t) { return t.number === activeViewerTab; });
        if (activeVt && activeVt.ticket && activeTab === "viewer") renderViewer();
      }
    });
  }

  // ── 워크플로 갱신 (SSE/폴링 공용) ──
  function refreshWorkflow() {
    fetchWorkflowEntries().then(function (hrefs) {
      var json = JSON.stringify(hrefs);
      if (json !== prevWfJson) {
        prevWfJson = json;
        wfEntryHrefs = hrefs;
        wfLoadedIndex = 0;
        WORKFLOWS = [];
        wfInitialized = false;
        loadMoreWorkflows();
      }
    });
  }

  // ── 대시보드 갱신 (SSE/폴링 공용) ──
  function refreshDashboard() {
    fetchAllDashboardFiles().then(function () {
      if (activeTab === "dashboard") renderDashboard();
    });
  }

  // ── SSE ──
  function initSSE() {
    if (typeof EventSource === "undefined") {
      // EventSource 미지원 환경 -> 즉시 폴링 모드
      startPolling();
      return;
    }

    var es = new EventSource("/events");
    var timeoutId = setTimeout(function () {
      // 3초 내 onopen 미호출 -> 타임아웃, 폴링 모드로 전환
      if (!sseConnected) {
        es.close();
        startPolling();
        scheduleSSERetry();
      }
    }, SSE_TIMEOUT);

    es.onopen = function () {
      clearTimeout(timeoutId);
      sseConnected = true;
      stopPolling();
    };

    es.addEventListener("kanban", function () {
      refreshKanban();
    });

    es.addEventListener("workflow", function () {
      refreshWorkflow();
    });

    es.addEventListener("dashboard", function () {
      refreshDashboard();
    });

    es.onerror = function () {
      sseConnected = false;
      es.close(); // 명시적으로 닫아서 자동 재연결 방지
      clearTimeout(timeoutId);
      startPolling();
      scheduleSSERetry();
    };
  }

  // ── 폴링 ──
  function startPolling() {
    if (pollTimerId) return; // 이미 폴링 중
    sseGaveUp = true;
    pollChanges();
  }

  function stopPolling() {
    if (pollTimerId) {
      clearTimeout(pollTimerId);
      pollTimerId = null;
    }
    sseGaveUp = false;
  }

  function pollChanges() {
    fetch("/poll").then(function (res) {
      if (!res.ok) throw new Error("poll failed");
      return res.json();
    }).then(function (changes) {
      if (changes.kanban) {
        refreshKanban(changes.kanban);
      }
      if (changes.workflow) {
        refreshWorkflow();
      }
      if (changes.dashboard) {
        refreshDashboard();
      }
    }).catch(function () {
      // /poll 실패 시 조용히 처리 (콘솔 에러 없음)
    }).then(function () {
      // finally 대용 (ES5 호환: Promise.prototype.finally 미지원 환경 대비)
      if (sseGaveUp && !document.hidden) {
        pollTimerId = setTimeout(pollChanges, POLL_INTERVAL);
      } else {
        pollTimerId = null;
      }
    });
  }

  function scheduleSSERetry() {
    if (sseRetryTimerId) return; // 이미 재시도 예약됨
    sseRetryTimerId = setTimeout(function () {
      sseRetryTimerId = null;
      initSSE(); // SSE 재시도 (성공하면 onopen에서 폴링 중단)
    }, SSE_RETRY_INTERVAL);
  }

  // ── Init ──
  switchTab(activeTab);

  fetchTickets().then(function (tickets) {
    TICKETS = tickets;
    prevTicketJson = ticketJson(tickets);
    renderKanban();
    var savedTabs = savedState.viewerTabs || [];
    if (savedTabs.length > 0) {
      savedTabs.forEach(function (num) {
        var ticket = TICKETS.find(function (t) { return t.number === num; });
        if (ticket) {
          var exists = viewerTabs.find(function (t) { return t.number === num; });
          if (!exists) viewerTabs.push({ number: num, ticket: ticket });
        }
      });
      if (activeTab === "viewer") renderViewer();
    }
  });

  fetchWorkflowEntries().then(function (hrefs) {
    wfEntryHrefs = hrefs;
    prevWfJson = JSON.stringify(hrefs);
    loadMoreWorkflows();
  });

  // SSE 연결 시작 (실패 시 onerror에서 폴백 폴링 자동 재개)
  initSSE();

  // 탭 활성화 복귀 시 누락된 변경 보상
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) {
      if (sseConnected) {
        // SSE 연결 중일 때도 누락된 이벤트를 보상하기 위해 1회 fetch
        refreshKanban();
        refreshWorkflow();
      } else if (sseGaveUp) {
        // 폴링 모드: 탭 복귀 시 즉시 한 번 폴링 재개
        if (!pollTimerId) {
          pollChanges();
        }
      }
    }
  });

  // Pre-fetch dashboard data in background so it's ready on tab switch
  fetchAllDashboardFiles().then(function () {
    if (activeTab === "dashboard") renderDashboard();
  });

})();
