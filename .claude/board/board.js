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
          if (rt) obj[rc.tagName] = rt;
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
  var MAX_GAP = 10; // 연속 404 허용 횟수

  function fetchTickets() {
    var tickets = [];
    function tryFetch(n, misses) {
      if (misses >= MAX_GAP) return Promise.resolve();
      var url = "../../.kanban/T-" + String(n).padStart(3, "0") + ".xml";
      return fetch(url).then(function (res) {
        if (!res.ok) return tryFetch(n + 1, misses + 1);
        return res.text().then(function (text) {
          var t = parseTicket(text);
          if (t) tickets.push(t);
          return tryFetch(n + 1, 0);
        });
      }).catch(function () { return tryFetch(n + 1, misses + 1); });
    }
    function tryFetchDone(n, misses) {
      if (misses >= MAX_GAP) return Promise.resolve();
      var url = "../../.kanban/done/T-" + String(n).padStart(3, "0") + ".xml";
      return fetch(url).then(function (res) {
        if (!res.ok) return tryFetchDone(n + 1, misses + 1);
        return res.text().then(function (text) {
          var t = parseTicket(text);
          if (t) tickets.push(t);
          return tryFetchDone(n + 1, 0);
        });
      }).catch(function () { return tryFetchDone(n + 1, misses + 1); });
    }
    return tryFetch(1, 0).then(function () {
      return tryFetchDone(1, 0);
    }).then(function () { return tickets; });
  }

  // ── UI State Persistence ──
  var LS_KEY = "claude-board-ui";

  function saveUI() {
    var openNums = viewerTabs.map(function (t) { return t.number; });
    var state = { tab: activeTab, viewerTabs: openNums, activeViewerTab: activeViewerTab };
    try { localStorage.setItem(LS_KEY, JSON.stringify(state)); } catch (e) {}
  }

  function loadUI() {
    try { return JSON.parse(localStorage.getItem(LS_KEY)) || {}; } catch (e) { return {}; }
  }

  var savedState = loadUI();

  // ── Tab Switching ──
  var tabs = document.querySelectorAll(".tab");
  var views = document.querySelectorAll(".view");
  var activeTab = savedState.tab || "kanban";

  function switchTab(target) {
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
      h += '<div class="column">';
      h += '<div class="col-header"><span class="col-dot ' + col.dot + '"></span>' + esc(col.label);
      h += '<span class="col-count">' + items.length + "</span></div>";
      h += '<div class="cards">';
      if (items.length === 0) {
        h += '<div class="empty">No items</div>';
      } else {
        items.forEach(function (t) {
          var done = col.key === "Done" ? " done" : "";
          h += '<div class="card' + done + '" data-num="' + esc(t.number) + '">';
          h += '<div class="card-title">' + esc(t.title || "(No title)") + "</div>";
          h += '<div class="card-meta">';
          h += '<span class="card-num">' + esc(t.number) + "</span>";
          if (t.submit && t.submit.command) {
            h += badge(t.submit.command, CMD_COLORS[t.submit.command]);
          }
          h += "</div></div>";
        });
      }
      h += "</div></div>";
    });
    h += "</div>";
    el.innerHTML = h;
    el.querySelectorAll(".card").forEach(function (card) {
      card.addEventListener("click", function () {
        var num = card.dataset.num;
        var ticket = TICKETS.find(function (t) { return t.number === num; });
        if (ticket) openViewer(ticket);
      });
    });
  }

  // ── Viewer Tabs ──
  var viewerTabs = [];
  var activeViewerTab = savedState.activeViewerTab || null;

  function openViewer(ticket) {
    var exists = viewerTabs.find(function (t) { return t.number === ticket.number; });
    if (!exists) {
      viewerTabs.push({ number: ticket.number, ticket: ticket });
    } else {
      exists.ticket = ticket;
    }
    activeViewerTab = ticket.number;
    switchTab("viewer");
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
    viewerTabs.forEach(function (t) {
      var ac = t.number === activeViewerTab ? " vt-tab-active" : "";
      h += '<div class="vt-tab' + ac + '" data-num="' + esc(t.number) + '">';
      var tabLabel = t.wfFile ? t.wfFile.label : t.number;
      h += '<span class="vt-tab-label">' + esc(tabLabel) + '</span>';
      h += '<span class="vt-tab-close" data-close="' + esc(t.number) + '">&times;</span>';
      h += '</div>';
    });
    h += '</div>';

    // Content
    h += '<div class="vt-content">';
    var active = viewerTabs.find(function (t) { return t.number === activeViewerTab; });
    if (active && active.wfFile) {
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

    initMermaid();
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

  /** Renders result object keys as clickable links for Viewer tab. */
  function renderResultLinks(result) {
    var keys = ["plan", "work", "report"];
    var h = '<div class="tv-result-links">';
    keys.forEach(function (k) {
      if (!result[k]) return;
      var url = "../../" + result[k];
      var isDir = k === "work";
      h += '<span class="tv-result-link" data-label="' + esc(k) + '" data-url="' + esc(url) + '"' + (isDir ? ' data-isdir="true"' : '') + '>' + esc(k) + '</span>';
    });
    // render any extra keys not in the standard list
    Object.keys(result).forEach(function (k) {
      if (keys.indexOf(k) === -1) {
        var url = "../../" + result[k];
        h += '<span class="tv-result-link" data-label="' + esc(k) + '" data-url="' + esc(url) + '">' + esc(k) + '</span>';
      }
    });
    h += "</div>";
    return h;
  }

  // ── Workflow ──
  var WORKFLOWS = [];


  // Files to show as links in workflow cards
  var WF_FILES = [
    { key: "query", file: "user_prompt.txt", label: "query" },
    { key: "plan", file: "plan.md", label: "plan" },
    { key: "report", file: "report.md", label: "report" },
    { key: "summary", file: "summary.txt", label: "summary" },
    { key: "log", file: "workflow.log", label: "log" },
    { key: "usage", file: "usage.json", label: "usage" },
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
    return fetch(baseHref).then(function (res) {
      if (!res.ok) return [];
      return res.text();
    }).then(function (html) {
      return parseDirLinks(html).dirs.filter(function (h) {
        return /\/\d{8}-\d{6}\/$/.test(h);
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
    return fetch(entryHref).then(function (r) { return r.text(); }).then(function (h2) {
      var taskLinks = parseDirLinks(h2).dirs;
      return Promise.all(taskLinks.map(function (taskHref) {
        var task = lastSegment(taskHref);
        return fetch(taskHref).then(function (r) { return r.text(); }).then(function (h3) {
          var cmdLinks = parseDirLinks(h3).dirs;
          return Promise.all(cmdLinks.map(function (cmdHref) {
            var cmd = lastSegment(cmdHref);
            var basePath = cmdHref;
            return fetch(basePath + "status.json")
              .then(function (r) { return r.ok ? r.json() : null; })
              .then(function (status) {
                if (!status) return null;
                return fetch(basePath).then(function (r) { return r.text(); }).then(function (listing) {
                  var parsed = parseDirLinks(listing);
                  var fileNames = parsed.files.map(function (f) { return lastSegment(f); });
                  var availableFiles = [];
                  var hasWork = parsed.dirs.some(function (d) { return lastSegment(d) === "work"; });
                  WF_FILES.forEach(function (wf) {
                    if (fileNames.indexOf(wf.file) !== -1) {
                      availableFiles.push({ label: wf.label, url: basePath + wf.file });
                    }
                    // Insert work after plan
                    if (wf.key === "plan" && hasWork) {
                      availableFiles.push({ label: "work", url: basePath + "work/", isDir: true });
                    }
                  });
                  return {
                    entry: entry, task: task, command: cmd, basePath: basePath,
                    step: status.step || "NONE",
                    created_at: status.created_at || "",
                    updated_at: status.updated_at || "",
                    transitions: status.transitions || [],
                    files: availableFiles,
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
    activeViewerTab = tabId;
    switchTab("viewer");
    renderViewer();
    // Fetch content
    var effectiveIsDir = isDir || url.endsWith("/");
    if (effectiveIsDir) {
      fetch(url).then(function (r) { return r.text(); }).then(function (html) {
        var tab = viewerTabs.find(function (t) { return t.number === tabId; });
        if (tab && tab.wfFile) {
          var parsed = parseDirLinks(html);
          tab.wfFile.content = JSON.stringify({ files: parsed.files, baseUrl: url });
          tab.wfFile.isDirListing = true;
          if (activeViewerTab === tabId) renderViewer();
        }
      }).catch(function () {});
    } else {
      fetch(url).then(function (r) { return r.text(); }).then(function (text) {
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
    if (loading) loading.remove();
    // Append new rows
    var temp = document.createElement("div");
    var h = "";
    items.forEach(function (w) { h += renderWfCard(w); });
    temp.innerHTML = h;
    while (temp.firstChild) {
      list.appendChild(temp.firstChild);
    }
    // Bind file links on new rows
    bindWfFileLinks(list);
  }

  function attachWfSentinel() {
    var list = document.getElementById("wf-list");
    if (!list) return;
    var hasMore = wfLoadedIndex < wfEntryHrefs.length;
    // Remove old sentinel
    var old = document.getElementById("wf-sentinel");
    if (old) old.remove();
    if (wfLoading) {
      var el = document.createElement("div");
      el.className = "empty";
      el.textContent = "Loading...";
      list.appendChild(el);
    } else if (hasMore) {
      var s = document.createElement("div");
      s.className = "wf-load-more";
      s.id = "wf-sentinel";
      s.textContent = "Scroll for more";
      list.appendChild(s);
      var observer = new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting) {
          observer.disconnect();
          loadMoreWorkflows();
        }
      });
      observer.observe(s);
    }
  }

  function bindWfFileLinks(container) {
    container.querySelectorAll(".wf-file-link:not([data-bound])").forEach(function (link) {
      link.setAttribute("data-bound", "1");
      link.addEventListener("click", function (e) {
        e.stopPropagation();
        openWfFile(link.dataset.label, link.dataset.url);
      });
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

    // List
    h += '<div class="wf-list" id="wf-list">';

    if (filtered.length > 0) {
      filtered.forEach(function (w) { h += renderWfCard(w); });
    } else if (!wfLoading) {
      h += '<div class="empty" style="margin-top:32px">' + (wfSearchQuery ? "No results" : "No workflows") + '</div>';
    }

    h += '</div></div>';
    el.innerHTML = h;

    // Search input
    el.querySelector(".wf-search").addEventListener("input", function (e) {
      wfSearchQuery = e.target.value;
      wfInitialized = false;
      renderWorkflow();
      var input = el.querySelector(".wf-search");
      if (input) { input.focus(); input.selectionStart = input.selectionEnd = input.value.length; }
    });

    bindWfFileLinks(el);
    attachWfSentinel();
  }

  function renderWfFileView(wfFile) {
    var h = '<div class="tv-container">';
    h += '<div class="tv-header"><h1 class="tv-title">' + esc(wfFile.label) + '</h1></div>';
    if (wfFile.content === null) {
      h += '<div class="empty">Loading...</div>';
    } else if (wfFile.isDirListing) {
      var parsed = JSON.parse(wfFile.content);
      h += renderDirListing(parsed.files, parsed.baseUrl);
    } else if (wfFile.url.endsWith(".md")) {
      h += '<div class="md-body">' + renderMd(wfFile.content) + '</div>';
    } else {
      h += '<pre class="wf-file-content">' + esc(wfFile.content) + '</pre>';
    }
    h += '</div>';
    return h;
  }

  // ── Markdown Rendering ──
  var mermaidCounter = 0;

  function renderMd(text) {
    if (typeof marked === "undefined") return '<pre class="wf-file-content">' + esc(text) + '</pre>';

    var renderer = new marked.Renderer();
    renderer.code = function (opts) {
      var code = typeof opts === "object" ? opts.text : opts;
      var lang = typeof opts === "object" ? opts.lang : arguments[1];
      if (lang === "mermaid") {
        var id = "mermaid-" + (++mermaidCounter);
        return '<div class="mermaid-block" data-mermaid-id="' + id + '">' + esc(code) + '</div>';
      }
      return '<pre class="md-code"><code>' + esc(code) + '</code></pre>';
    };

    return marked.parse(text, { renderer: renderer, gfm: true, breaks: true });
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

  function renderWfCard(w) {
    var h = '<div class="wf-row">';
    h += '<span class="wf-row-cmd">' + badge(w.command, CMD_COLORS[w.command] || { bg: "rgba(133,133,133,0.25)", fg: "#a0a0a0" }) + '</span>';
    h += '<span class="wf-row-title">' + esc(w.task) + '</span>';
    if (w.files && w.files.length > 0) {
      h += '<span class="wf-row-files">';
      w.files.forEach(function (f) {
        h += '<span class="wf-file-link" data-label="' + esc(w.task + ' / ' + f.label) + '" data-url="' + esc(f.url) + '">' + esc(f.label) + '</span>';
      });
      h += '</span>';
    }
    h += '<span class="wf-row-time">' + esc(w.updated_at.substring(0, 16)) + '</span>';
    h += '</div>';
    return h;
  }

  // ── Dashboard ──
  var DASH_PAGE_SIZE = 50;
  var DASH_FILES = ["usage", "logs", "skills", "history"];
  var dashData = {};          // { usage: text, logs: text, skills: text, history: text }
  var dashFetched = false;
  var dashActiveSubtab = "usage";
  var dashHistoryRows = [];   // parsed history table rows (array of strings)
  var dashHistoryPage = 0;

  /**
   * Fetches a single dashboard markdown file.
   * @param {string} name - file name without extension (usage|logs|skills|history)
   * @returns {Promise<string>}
   */
  function fetchDashboardFile(name) {
    var url = "../../.dashboard/." + name + ".md";
    return fetch(url).then(function (res) {
      if (!res.ok) return "";
      return res.text();
    }).catch(function () { return ""; });
  }

  /**
   * Fetches all four dashboard files in parallel and caches in dashData.
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
   * Renders the 4 KPI Summary Cards into #view-dashboard.
   * @param {Object} stats
   * @returns {string} HTML
   */
  function renderDashCards(stats) {
    var cards = [
      { label: "Total Workflows", value: String(stats.totalWorkflows), sub: "all time" },
      { label: "Total Tokens", value: formatTokens(stats.totalTokens), sub: "cumulative" },
      { label: "Warn / Error", value: String(stats.warnErrors), sub: "across all runs" },
      { label: "Top Skill", value: stats.topSkill, sub: "most used" },
    ];
    var h = '<div class="dash-cards">';
    cards.forEach(function (card) {
      h += '<div class="dash-card">';
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
   * Renders the History subtab content with pagination.
   * @param {string} historyText
   * @param {HTMLElement} contentEl
   */
  function renderHistoryPage(historyText, contentEl) {
    if (!dashHistoryRows.length) {
      dashHistoryRows = parseMdTableRows(historyText || "");
      // history.md is newest-first, so no sort needed; just reverse for "most recent first"
    }
    var headers = parseMdTableHeader(historyText || "");
    var totalPages = Math.ceil(dashHistoryRows.length / DASH_PAGE_SIZE);
    var start = dashHistoryPage * DASH_PAGE_SIZE;
    var pageRows = dashHistoryRows.slice(start, start + DASH_PAGE_SIZE);

    var h = renderMdTable(headers, pageRows);

    // Pagination
    if (totalPages > 1) {
      h += '<div class="dash-pagination">';
      for (var p = 0; p < totalPages; p++) {
        var isActive = p === dashHistoryPage ? " active" : "";
        h += '<button class="dash-page-btn' + isActive + '" data-page="' + p + '">' + (p + 1) + '</button>';
      }
      h += '</div>';
    }

    contentEl.innerHTML = h;

    contentEl.querySelectorAll(".dash-page-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        dashHistoryPage = parseInt(btn.dataset.page, 10);
        renderHistoryPage(historyText, contentEl);
      });
    });
  }

  /**
   * Main Dashboard render entry point.
   * Fetches data (first time) then renders cards + subtab UI.
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

    var stats = computeKpiStats(dashData);
    var h = renderDashCards(stats);

    // Subtabs bar
    var subtabs = ["Usage", "Logs", "Skills", "History"];
    h += '<div class="dash-subtabs">';
    subtabs.forEach(function (name) {
      var key = name.toLowerCase();
      var isActive = key === dashActiveSubtab ? " active" : "";
      h += '<button class="dash-subtab' + isActive + '" data-subtab="' + key + '">' + esc(name) + '</button>';
    });
    h += '</div>';

    // Subtab content container
    h += '<div class="dash-content" id="dash-content"></div>';

    el.innerHTML = h;

    // Bind subtab clicks
    el.querySelectorAll(".dash-subtab").forEach(function (btn) {
      btn.addEventListener("click", function () {
        dashActiveSubtab = btn.dataset.subtab;
        dashHistoryPage = 0;
        el.querySelectorAll(".dash-subtab").forEach(function (b) {
          b.classList.toggle("active", b.dataset.subtab === dashActiveSubtab);
        });
        renderDashSubtabContent();
      });
    });

    renderDashSubtabContent();
  }

  /**
   * Renders the active subtab content into #dash-content.
   */
  function renderDashSubtabContent() {
    var contentEl = document.getElementById("dash-content");
    if (!contentEl) return;

    var key = dashActiveSubtab;
    var text = dashData[key] || "";

    if (key === "history") {
      dashHistoryRows = []; // reset to force re-parse on tab switch
      renderHistoryPage(text, contentEl);
    } else {
      var headers = parseMdTableHeader(text);
      var rows = parseMdTableRows(text);
      contentEl.innerHTML = renderMdTable(headers, rows);
    }
  }

  // ── Polling ──
  var POLL_INTERVAL = 500;
  var prevTicketJson = "";
  var prevWfJson = "";

  function ticketJson(tickets) {
    return JSON.stringify(tickets.map(function (t) {
      return { number: t.number, title: t.title, status: t.status, current: t.current,
               submit: t.submit, history: t.history };
    }));
  }

  function pollTickets() {
    fetchTickets().then(function (tickets) {
      var json = ticketJson(tickets);
      if (json !== prevTicketJson) {
        TICKETS = tickets;
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
      setTimeout(pollTickets, POLL_INTERVAL);
    });
  }

  function pollWorkflows() {
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
      setTimeout(pollWorkflows, POLL_INTERVAL);
    });
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
    setTimeout(pollTickets, POLL_INTERVAL);
  });

  fetchWorkflowEntries().then(function (hrefs) {
    wfEntryHrefs = hrefs;
    prevWfJson = JSON.stringify(hrefs);
    loadMoreWorkflows();
    setTimeout(pollWorkflows, POLL_INTERVAL);
  });

  // Pre-fetch dashboard data in background so it's ready on tab switch
  fetchAllDashboardFiles().then(function () {
    if (activeTab === "dashboard") renderDashboard();
  });

})();
