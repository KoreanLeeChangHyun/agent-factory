/**
 * @module viewer
 *
 * Board SPA viewer tab module.
 *
 * Manages viewer tabs (ticket view, workflow file view, workflow detail view),
 * code viewer with lazy loading and search, markdown rendering, and directory
 * listing. Registers openViewer, renderViewer, openWfFile on Board.render.
 *
 * Depends on: common.js (Board.util, Board.state, Board.render)
 */
"use strict";

(function () {
  const { esc, badge, formatTime, CMD_COLORS, STATUS_COLORS, saveUI, switchTab, parseDirLinks,
          resolveResultPath, urlDir, getHighlightLang } = Board.util;

  // ── Viewer Tab Management ──

  /**
   * Opens a ticket in the viewer tab, creating a new tab if needed.
   * @param {Object} ticket - Ticket data object
   */
  function openViewer(ticket) {
    const exists = Board.state.viewerTabs.find(function (t) { return t.number === ticket.number; });
    if (!exists) {
      Board.state.viewerTabs.push({ number: ticket.number, ticket: ticket });
    } else {
      exists.ticket = ticket;
    }
    switchTab("viewer");
    Board.state.activeViewerTab = ticket.number;
    renderViewer();
    saveUI();
  }

  /** Closes a viewer tab by number and activates the previous tab. */
  function closeViewerTab(number) {
    Board.state.viewerTabs = Board.state.viewerTabs.filter(function (t) { return t.number !== number; });
    if (Board.state.activeViewerTab === number) {
      Board.state.activeViewerTab = Board.state.viewerTabs.length > 0
        ? Board.state.viewerTabs[Board.state.viewerTabs.length - 1].number
        : null;
    }
    renderViewer();
    saveUI();
  }

  // ── Viewer Rendering ──

  /** Renders the entire viewer tab including tab bar and content area. */
  function renderViewer() {
    const el = document.getElementById("view-viewer");
    let h = "";

    // Tab bar
    h += '<div class="vt-bar">';
    const backDim = Board.state.tabHistory.length === 0 ? " vt-nav-dim" : "";
    const fwdDim = Board.state.forwardHistory.length === 0 ? " vt-nav-dim" : "";
    h += '<button class="vt-back-btn' + backDim + '" id="vt-back-btn">&lt;</button>';
    h += '<button class="vt-back-btn' + fwdDim + '" id="vt-fwd-btn">&gt;</button>';
    Board.state.viewerTabs.forEach(function (t) {
      const ac = t.number === Board.state.activeViewerTab ? " vt-tab-active" : "";
      h += '<div class="vt-tab' + ac + '" data-num="' + esc(t.number) + '">';
      const tabLabel = t.wfDetail ? (t.wfDetail.number || t.wfDetail.entry) : (t.wfFile ? t.wfFile.label : t.number.replace(/^T-/, ""));
      h += '<span class="vt-tab-label">' + esc(tabLabel) + '</span>';
      h += '<span class="vt-tab-close" data-close="' + esc(t.number) + '">&times;</span>';
      h += '</div>';
    });
    h += '</div>';

    // Content
    h += '<div class="vt-content">';
    const active = Board.state.viewerTabs.find(function (t) { return t.number === Board.state.activeViewerTab; });
    if (active && active.wfDetail) {
      h += Board.render.renderWfDetailView(active.wfDetail);
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
        const prevViewerTab = Board.state.activeViewerTab;
        if (tab.dataset.num !== prevViewerTab) {
          Board.state.tabHistory.push({ tab: "viewer", viewerTab: prevViewerTab });
          if (Board.state.tabHistory.length > 100) Board.state.tabHistory.shift();
          Board.state.forwardHistory.length = 0;
        }
        Board.state.activeViewerTab = tab.dataset.num;
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
        const isDir = link.dataset.isdir === "true";
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
        const isDir = link.dataset.isdir === "true";
        openWfFile(link.dataset.label, link.dataset.url, isDir);
      });
    });

    // Lazy-load connected ticket for wfDetail views
    el.querySelectorAll(".wf-detail-ticket-section[data-basepath]").forEach(function (section) {
      const basePath = section.dataset.basepath;
      if (!basePath || section.dataset.fetched) return;
      section.dataset.fetched = "1";
      fetch(basePath + ".context.json", { cache: "no-store" }).then(function (r) {
        if (!r.ok) return null;
        return r.json();
      }).then(function (ctx) {
        if (!ctx) return;
        const ticketNum = ctx.ticketNumber || "";
        const title = ctx.title || "";
        const workId = ctx.workId || "";
        if (!ticketNum && !title && !workId) return;
        let ctxHtml = '<div class="tv-section">';
        ctxHtml += '<div class="tv-section-title">Context</div>';
        ctxHtml += '<div class="wf-detail-info">';
        if (ticketNum) ctxHtml += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Ticket</span><span class="wf-detail-info-value">' + esc(ticketNum) + '</span></div>';
        if (title) ctxHtml += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Title</span><span class="wf-detail-info-value">' + esc(title) + '</span></div>';
        if (workId) ctxHtml += '<div class="wf-detail-info-row"><span class="wf-detail-info-label">Work ID</span><span class="wf-detail-info-value">' + esc(workId) + '</span></div>';
        ctxHtml += '</div></div>';
        section.innerHTML = ctxHtml;
      }).catch(function () {});
    });

    // Bind back button
    const backBtn = el.querySelector("#vt-back-btn");
    if (backBtn) {
      backBtn.addEventListener("click", function () {
        while (Board.state.tabHistory.length > 0) {
          const entry = Board.state.tabHistory.pop();
          if (entry && entry.tab === "viewer" && entry.viewerTab) {
            const stillOpen = Board.state.viewerTabs.find(function (t) { return t.number === entry.viewerTab; });
            if (!stillOpen) continue;
            Board.state.forwardHistory.push({ tab: "viewer", viewerTab: Board.state.activeViewerTab });
            Board.state.activeViewerTab = entry.viewerTab;
            renderViewer();
            saveUI();
            return;
          }
          Board.state.forwardHistory.push({ tab: Board.state.activeTab, viewerTab: Board.state.activeTab === "viewer" ? Board.state.activeViewerTab : null });
          switchTab(entry && entry.tab ? entry.tab : "kanban", true);
          return;
        }
        switchTab("kanban", true);
      });
    }

    // Bind forward button
    const fwdBtn = el.querySelector("#vt-fwd-btn");
    if (fwdBtn) {
      fwdBtn.addEventListener("click", function () {
        while (Board.state.forwardHistory.length > 0) {
          const entry = Board.state.forwardHistory.pop();
          if (entry && entry.tab === "viewer" && entry.viewerTab) {
            const stillOpen = Board.state.viewerTabs.find(function (t) { return t.number === entry.viewerTab; });
            if (!stillOpen) continue;
            Board.state.tabHistory.push({ tab: "viewer", viewerTab: Board.state.activeViewerTab });
            if (Board.state.tabHistory.length > 100) Board.state.tabHistory.shift();
            Board.state.activeViewerTab = entry.viewerTab;
            renderViewer();
            saveUI();
            return;
          }
          Board.state.tabHistory.push({ tab: Board.state.activeTab, viewerTab: Board.state.activeTab === "viewer" ? Board.state.activeViewerTab : null });
          if (Board.state.tabHistory.length > 100) Board.state.tabHistory.shift();
          switchTab(entry && entry.tab ? entry.tab : "kanban", true);
          return;
        }
      });
    }

    // Bind wfDetail ticket link clicks
    el.querySelectorAll(".wf-detail-ticket-link").forEach(function (link) {
      link.addEventListener("click", function () {
        const ticketNum = link.dataset.ticketNum;
        const ticket = Board.state.TICKETS.find(function (t) { return t.number === ticketNum; });
        if (ticket) openViewer(ticket);
      });
    });

    // Bind ticket viewer workflow links
    el.querySelectorAll(".tv-result-workflow[data-wf-entry]").forEach(function (link) {
      link.addEventListener("click", function () {
        const entryKey = link.dataset.wfEntry;
        const taskKey = link.dataset.wfTask;
        const cmdKey = link.dataset.wfCmd;
        const w = Board.state.WORKFLOWS.find(function (item) {
          return item.entry === entryKey && item.task === taskKey && item.command === cmdKey;
        });
        if (w) Board.render.openWfDetail(w);
      });
    });

    // Bind md-file-link clicks
    el.querySelectorAll(".md-file-link").forEach(function (link) {
      link.addEventListener("click", function () {
        const filePath = link.dataset.filepath;
        if (!filePath) return;
        let url;
        if (link.dataset.url) {
          url = link.dataset.url;
        } else if (filePath.indexOf(".workflow/") === 0 || filePath.indexOf(".claude/") === 0) {
          url = "../../" + resolveResultPath(filePath);
        } else {
          const activeTab = Board.state.viewerTabs.find(function (t) { return t.number === Board.state.activeViewerTab; });
          const baseUrl = activeTab && activeTab.wfFile ? activeTab.wfFile.url : "";
          url = urlDir(baseUrl) + filePath;
        }
        openWfFile(filePath, url);
      });
    });

    // Bind copy button clicks
    el.querySelectorAll(".code-copy-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const viewer = btn.closest(".code-viewer");
        if (!viewer) return;
        const lineContents = viewer.querySelectorAll(".code-line-content");
        const text = Array.prototype.map.call(lineContents, function (span) {
          return span.textContent;
        }).join("\n");
        navigator.clipboard.writeText(text).then(function () {
          const original = btn.textContent;
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
      const viewerId = viewer.dataset.viewerId;
      if (!viewerId || !Board.state.codeViewerStore[viewerId]) return;
      const store = Board.state.codeViewerStore[viewerId];
      if (store.pendingRows.length === 0) return;

      const CHUNK_SIZE = 200;
      const SCROLL_THRESHOLD = 200;

      function appendNextChunk() {
        if (store.pendingRows.length === 0) return;
        const chunk = store.pendingRows.splice(0, CHUNK_SIZE);
        const code = viewer.querySelector("code");
        if (!code) return;
        const chunkHtml = "\n" + chunk.join("\n");
        const lang = store.lang;
        let highlightedHtml = null;
        if (typeof hljs !== "undefined" && lang && lang !== "plaintext") {
          try {
            const result = hljs.highlight(chunkHtml, { language: lang });
            highlightedHtml = result.value;
          } catch (e) {
            highlightedHtml = null;
          }
        }
        const frag = document.createDocumentFragment();
        const wrapper = document.createElement("span");
        if (highlightedHtml !== null) {
          wrapper.innerHTML = highlightedHtml;
        } else {
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
        const distFromBottom = viewer.scrollHeight - viewer.scrollTop - viewer.clientHeight;
        if (distFromBottom < SCROLL_THRESHOLD) {
          appendNextChunk();
        }
      }

      viewer.addEventListener("scroll", onScroll);
    });

    // Bind code search (Ctrl+F / Cmd+F)
    el.querySelectorAll(".code-viewer").forEach(function (viewer) {
      const viewerId = viewer.dataset.viewerId;
      if (!viewerId || !Board.state.codeViewerStore[viewerId]) return;
      const store = Board.state.codeViewerStore[viewerId];
      const searchBar = viewer.querySelector(".code-search-bar");
      const searchInput = viewer.querySelector(".code-search-input");
      const searchCount = viewer.querySelector(".code-search-count");

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
          const parent = mark.parentNode;
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
        const lowerQuery = query.toLowerCase();
        const lineContents = viewer.querySelectorAll(".code-line-content");
        lineContents.forEach(function (span) {
          const text = span.textContent;
          if (text.toLowerCase().indexOf(lowerQuery) === -1) return;
          store.searchMatches.push(span);
          const walker = document.createTreeWalker(span, NodeFilter.SHOW_TEXT, null, false);
          const textNodes = [];
          let node;
          while ((node = walker.nextNode())) {
            textNodes.push(node);
          }
          textNodes.forEach(function (textNode) {
            const nodeText = textNode.nodeValue;
            const lowerNodeText = nodeText.toLowerCase();
            let idx = 0;
            let found = lowerNodeText.indexOf(lowerQuery, idx);
            if (found === -1) return;
            const parent = textNode.parentNode;
            const frag = document.createDocumentFragment();
            while (idx < nodeText.length) {
              found = lowerNodeText.indexOf(lowerQuery, idx);
              if (found === -1) {
                frag.appendChild(document.createTextNode(nodeText.substring(idx)));
                break;
              }
              if (found > idx) {
                frag.appendChild(document.createTextNode(nodeText.substring(idx, found)));
              }
              const mark = document.createElement("mark");
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
        if (store.searchIndex >= 0 && store.searchIndex < store.searchMatches.length) {
          store.searchMatches[store.searchIndex].classList.remove("code-search-active");
        }
        if (dir === "next") {
          store.searchIndex = (store.searchIndex + 1) % store.searchMatches.length;
        } else {
          store.searchIndex = (store.searchIndex - 1 + store.searchMatches.length) % store.searchMatches.length;
        }
        const activeSpan = store.searchMatches[store.searchIndex];
        activeSpan.classList.add("code-search-active");
        if (searchCount) {
          searchCount.textContent = (store.searchIndex + 1) + "/" + store.searchMatches.length;
        }
        activeSpan.scrollIntoView({ block: "center" });
      }

      viewer.addEventListener("keydown", function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === "f") {
          e.preventDefault();
          openSearch();
        }
        if (e.key === "Escape") {
          closeSearch();
        }
      });

      if (!viewer.getAttribute("tabindex")) {
        viewer.setAttribute("tabindex", "0");
      }

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
      const closeBtn = viewer.querySelector(".code-search-close-btn");
      if (closeBtn) {
        closeBtn.addEventListener("click", function () {
          closeSearch();
        });
      }
    });

    Board.render.initMermaid();
    Board.render.initHighlight();
    requestAnimationFrame(Board.render.initHighlight);
  }

  // ── Ticket HTML Rendering ──

  /**
   * Renders a ticket's detail view HTML.
   * @param {Object} ticket - Ticket data object
   * @returns {string} HTML string
   */
  function renderTicketHtml(ticket) {
    const sc = STATUS_COLORS[ticket.status] || STATUS_COLORS.Open;
    let h = '<div class="tv-container">';

    h += '<div class="tv-header">';
    h += '<div class="tv-header-top">';
    h += '<span class="tv-number">' + esc(ticket.number.replace(/^T-/, "")) + "</span>";
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

    const connectedWfs = Board.render.findWorkflowsForTicket(ticket);
    if (connectedWfs.length > 0) {
      h += '<div class="tv-section">';
      h += '<div class="tv-section-title">Workflows</div>';
      h += '<div class="tv-result-links">';
      connectedWfs.forEach(function (w) {
        const label = w.number ? w.number + " / " + w.task : w.task;
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
        const ac = entry.active ? " active" : "";
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

  // ── Prompt Fields Rendering ──

  /**
   * Renders prompt fields (goal, target, constraints, criteria, etc.).
   * @param {Object} prompt - Prompt data object
   * @returns {string} HTML string
   */
  function renderPromptFields(prompt) {
    const fields = ["goal", "target", "constraints", "criteria"];
    let h = '<div class="tv-fields">';
    fields.forEach(function (f) {
      if (prompt[f]) {
        h += '<div class="tv-field">';
        h += '<div class="tv-field-label">' + f + "</div>";
        h += '<div class="tv-field-value">' + esc(prompt[f]) + "</div>";
        h += "</div>";
      }
    });
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

  // ── Result Links Rendering ──

  /**
   * Renders result object keys as clickable links.
   * @param {Object} result - Result data object
   * @returns {string} HTML string
   */
  function renderResultLinks(result) {
    if (result.workflow) {
      let h = '<div class="tv-result-links">';
      h += '<span class="tv-result-link tv-result-workflow" data-workflow="' + esc(result.workflow) + '">' + esc(result.workflow) + '</span>';
      h += '</div>';
      return h;
    }
    const keys = ["plan", "work", "report"];
    let h = '<div class="tv-result-links">';
    if (result.registrykey) {
      h += '<span class="tv-result-id">' + esc(result.registrykey) + '</span>';
    }
    keys.forEach(function (k) {
      if (!result[k]) return;
      const url = encodeURI("../../" + resolveResultPath(result[k]));
      const isDir = k === "work";
      h += '<span class="tv-result-link" data-label="' + esc(k) + '" data-url="' + esc(url) + '"' + (isDir ? ' data-isdir="true"' : '') + '>' + esc(k) + '</span>';
    });
    const excludedKeys = ["workdir", "registrykey"];
    Object.keys(result).forEach(function (k) {
      if (keys.indexOf(k) === -1 && excludedKeys.indexOf(k) === -1) {
        const url = encodeURI("../../" + resolveResultPath(result[k]));
        h += '<span class="tv-result-link" data-label="' + esc(k) + '" data-url="' + esc(url) + '">' + esc(k) + '</span>';
      }
    });
    h += "</div>";
    return h;
  }

  // ── Workflow File Viewer ──

  /**
   * Opens a workflow file in the viewer tab.
   * @param {string} label - Display label for the tab
   * @param {string} url - URL to fetch the file from
   * @param {boolean} [isDir] - Whether the URL points to a directory
   */
  function openWfFile(label, url, isDir) {
    const tabId = "wf:" + url;
    const exists = Board.state.viewerTabs.find(function (t) { return t.number === tabId; });
    if (!exists) {
      Board.state.viewerTabs.push({ number: tabId, ticket: null, wfFile: { label: label, url: url, content: null, isDir: isDir || url.endsWith("/") } });
    }
    switchTab("viewer");
    Board.state.activeViewerTab = tabId;
    renderViewer();
    const effectiveIsDir = isDir || url.endsWith("/");
    if (effectiveIsDir) {
      fetch(url, { cache: "no-store" }).then(function (r) { return r.text(); }).then(function (html) {
        const tab = Board.state.viewerTabs.find(function (t) { return t.number === tabId; });
        if (tab && tab.wfFile) {
          const parsed = parseDirLinks(html);
          tab.wfFile.content = JSON.stringify({ files: parsed.files, baseUrl: url });
          tab.wfFile.isDirListing = true;
          if (Board.state.activeViewerTab === tabId) renderViewer();
        }
      }).catch(function () {});
    } else {
      fetch(url, { cache: "no-store" }).then(function (r) { return r.text(); }).then(function (text) {
        const tab = Board.state.viewerTabs.find(function (t) { return t.number === tabId; });
        if (tab && tab.wfFile) {
          tab.wfFile.content = text;
          if (Board.state.activeViewerTab === tabId) renderViewer();
        }
      });
    }
  }

  // ── Directory Listing Rendering ──

  /**
   * Renders a file list as clickable links.
   * @param {string[]} files - Array of file hrefs
   * @param {string} baseUrl - Base URL for resolving relative paths
   * @returns {string} HTML string
   */
  function renderDirListing(files, baseUrl) {
    if (!files || files.length === 0) {
      return '<div class="empty" style="margin-top:16px">No files</div>';
    }
    const extClass = {
      ".md": "dir-file-md",
      ".json": "dir-file-json",
      ".txt": "dir-file-text",
      ".log": "dir-file-text",
    };
    let h = '<div class="wf-dir-listing">';
    files.forEach(function (href) {
      const name = decodeURIComponent(href.split("/").pop());
      const dotIdx = name.lastIndexOf(".");
      const ext = dotIdx !== -1 ? name.substring(dotIdx) : "";
      const cls = extClass[ext] || "dir-file-other";
      const fileUrl = href.startsWith("http") || href.startsWith("../../") ? href : baseUrl + href;
      h += '<span class="wf-dir-file-link ' + cls + '" data-label="' + esc(name) + '" data-url="' + esc(fileUrl) + '">' + esc(name) + '</span>';
    });
    h += '</div>';
    return h;
  }

  // ── Workflow File View Rendering ──

  /**
   * Renders a workflow file view (markdown, code, or directory listing).
   * @param {Object} wfFile - Workflow file object with label, url, content
   * @returns {string} HTML string
   */
  function renderWfFileView(wfFile) {
    let h = '<div class="tv-container">';
    h += '<div class="tv-header"><h1 class="tv-title">' + esc(wfFile.label) + '</h1></div>';
    if (wfFile.content === null) {
      h += '<div class="empty">Loading...</div>';
    } else if (wfFile.isDirListing) {
      const parsed = JSON.parse(wfFile.content);
      h += renderDirListing(parsed.files, parsed.baseUrl);
    } else if (wfFile.url.endsWith(".md")) {
      h += '<div class="md-body">' + Board.render.renderMd(wfFile.content, wfFile.url) + '</div>';
    } else {
      const lang = getHighlightLang(wfFile.url);
      let lines = wfFile.content.split("\n");
      let lineCount = lines.length;
      if (lineCount > 0 && lines[lineCount - 1] === "") {
        lines = lines.slice(0, lineCount - 1);
        lineCount = lines.length;
      }
      const numWidth = String(lineCount).length;
      const rows = lines.map(function (line, i) {
        let num = String(i + 1);
        while (num.length < numWidth) num = " " + num;
        return '<span class="code-line-number">' + esc(num) + '</span><span class="code-line-content">' + esc(line) + '</span>';
      });

      const viewerId = "cv-" + (++Board.state.codeViewerIdCounter);
      const INITIAL_LINES = 500;
      const LARGE_THRESHOLD = 3000;
      const isLarge = lineCount > LARGE_THRESHOLD;
      const initialRows = isLarge ? rows.slice(0, INITIAL_LINES) : rows;

      Board.state.codeViewerStore[viewerId] = {
        pendingRows: isLarge ? rows.slice(INITIAL_LINES) : [],
        allLines: lines,
        nextChunk: INITIAL_LINES,
        searchMatches: [],
        searchIndex: -1,
        lang: lang,
      };

      const searchBarHtml = '<div class="code-search-bar" style="display:none">'
        + '<input class="code-search-input" type="text" placeholder="Search..." aria-label="\uCF54\uB4DC \uAC80\uC0C9" />'
        + '<span class="code-search-count"></span>'
        + '<button class="code-search-nav-btn" data-dir="prev" aria-label="\uC774\uC804 \uACB0\uACFC">&#9650;</button>'
        + '<button class="code-search-nav-btn" data-dir="next" aria-label="\uB2E4\uC74C \uACB0\uACFC">&#9660;</button>'
        + '<button class="code-search-close-btn" aria-label="\uAC80\uC0C9 \uB2EB\uAE30">&times;</button>'
        + '</div>';

      const lazyAttr = isLarge ? ' data-lazy="true"' : '';
      h += '<div class="code-viewer" data-viewer-id="' + viewerId + '">'
        + '<button class="code-copy-btn" aria-label="\uCF54\uB4DC \uBCF5\uC0AC">Copy</button>'
        + searchBarHtml
        + '<pre><code class="hljs-pending language-' + esc(lang) + '"' + lazyAttr + '>'
        + initialRows.join("\n")
        + '</code></pre></div>';
    }
    h += '</div>';
    return h;
  }

  // ── Register on Board namespace ──
  Board.render.openViewer = openViewer;
  Board.render.renderViewer = renderViewer;
  Board.render.openWfFile = openWfFile;
})();
