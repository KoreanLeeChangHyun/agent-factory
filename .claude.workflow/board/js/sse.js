/**
 * @module sse
 *
 * Board SPA real-time update module.
 *
 * Manages Server-Sent Events (SSE) connection with automatic fallback to
 * polling when SSE is unavailable or fails. Handles kanban, workflow,
 * and dashboard refresh on data changes. Also contains the application
 * initialization sequence (must be loaded last).
 *
 * Depends on: common.js, kanban.js, viewer.js, workflow.js, dashboard.js
 */
"use strict";

(function () {
  const { switchTab, saveUI } = Board.util;

  // ── SSE / Polling Constants ──
  const SSE_TIMEOUT = 3000;        // SSE connection timeout (ms)
  const SSE_RETRY_INTERVAL = 30000; // SSE retry interval (ms)
  const POLL_INTERVAL = 2000;      // Polling interval (ms)

  // ── SSE / Polling State ──
  let currentES = null;          // Current EventSource instance
  let sseConnected = false;
  let sseGaveUp = false;         // SSE abandoned, polling mode active
  let sseRetryTimerId = null;
  let pollTimerId = null;

  let prevTicketJson = "";
  let prevWfJson = "";

  // ── Helpers ──

  /**
   * Serializes tickets to a JSON string for change detection.
   * @param {Array} tickets - ticket array
   * @returns {string} JSON string
   */
  function ticketJson(tickets) {
    return JSON.stringify(tickets.map(function (t) {
      return { number: t.number, title: t.title, status: t.status,
               command: t.command, prompt: t.prompt, result: t.result };
    }));
  }

  // ── Kanban Refresh (SSE/Polling shared) ──

  /**
   * Refreshes the kanban board.
   * @param {string[]} [files] - Changed file names. If provided, selective fetch; otherwise full fetch.
   */
  function refreshKanban(files) {
    var fetchPromise = (files && files.length > 0)
      ? Board.fetch.fetchTicketsByFiles(files).then(function () { return Board.state.TICKETS; })
      : Board.fetch.fetchTickets().then(function (tickets) {
          // Preserve existing data if fetch returned empty due to error
          // (fetchTickets catch handler returns [] on failure; skip overwrite if we already have data)
          if (!tickets || (tickets.length === 0 && Board.state.TICKETS.length > 0)) {
            return Board.state.TICKETS;
          }
          Board.state.TICKETS = tickets;
          return Board.state.TICKETS;
        });

    fetchPromise.then(function (tickets) {
      if (!tickets) return; // fetch failed: preserve existing data, skip update
      const json = ticketJson(tickets);
      if (json !== prevTicketJson) {
        prevTicketJson = json;
        Board.render.renderKanban();
        if (Board.state.activeTab === "roadmap" && Board.render.renderRoadmap) {
          Board.render.renderRoadmap();
        }
        Board.state.viewerTabs.forEach(function (vt) {
          if (vt.ticket) {
            const fresh = Board.state.TICKETS.find(function (t) { return t.number === vt.number; });
            if (fresh) vt.ticket = fresh;
          }
        });
        const activeVt = Board.state.viewerTabs.find(function (t) { return t.number === Board.state.activeViewerTab; });
        if (activeVt && activeVt.ticket && Board.state.activeTab === "viewer") Board.render.renderViewer();
      }
    });
  }

  // ── Workflow Refresh (SSE/Polling shared) ──

  /** Refreshes the workflow tab data. */
  function refreshWorkflow() {
    Board.fetch.fetchWorkflowEntries().then(function (hrefs) {
      const json = JSON.stringify(hrefs);
      if (json !== prevWfJson) {
        prevWfJson = json;
        Board.state.wfEntryHrefs = hrefs;
        Board.state.wfLoadedIndex = 0;
        Board.state.WORKFLOWS = [];
        Board.state.wfInitialized = false;
        Board.render.loadMoreWorkflows();
      }
    });
  }

  // ── Dashboard Refresh (SSE/Polling shared) ──

  /** Refreshes the dashboard tab data. */
  function refreshDashboard() {
    Board.fetch.fetchAllDashboardFiles().then(function () {
      if (Board.state.activeTab === "dashboard") Board.render.renderDashboard();
    });
  }

  // ── Memory Refresh (SSE/Polling shared) ──

  /** Refreshes the memory tab data on external file changes. */
  function refreshMemory() {
    if (Board.render.refreshMemory) Board.render.refreshMemory();
  }

  // ── SSE ──

  /** Initializes SSE connection. Falls back to polling on failure/timeout. */
  function initSSE() {
    if (typeof EventSource === "undefined") {
      // EventSource not supported -> immediate polling mode
      startPolling();
      return;
    }

    // Close existing EventSource to prevent duplicate connections
    if (currentES) {
      currentES.close();
      currentES = null;
    }

    const es = new EventSource("/events");
    currentES = es;

    const timeoutId = setTimeout(function () {
      // 3s without onopen -> timeout, switch to polling
      if (es.readyState !== EventSource.OPEN) {
        es.close();
        startPolling();
        scheduleSSERetry();
      }
    }, SSE_TIMEOUT);

    es.onopen = function () {
      clearTimeout(timeoutId);
      sseConnected = true;
      stopPolling();
      // Compensate for changes missed during polling period
      refreshKanban();
      refreshWorkflow();
      refreshDashboard();
    };

    es.addEventListener("kanban", function (e) {
      try {
        var d = JSON.parse(e.data);
        refreshKanban(d.files);
      } catch (_) {
        refreshKanban();
      }
    });

    es.addEventListener("workflow", function () {
      refreshWorkflow();
    });

    es.addEventListener("dashboard", function () {
      refreshDashboard();
    });

    es.addEventListener("memory", function () {
      refreshMemory();
    });

    es.onerror = function () {
      sseConnected = false;
      es.close(); // Explicitly close to prevent auto-reconnect
      clearTimeout(timeoutId);
      startPolling();
      scheduleSSERetry();
    };
  }

  // ── Polling ──

  /** Starts polling mode. */
  function startPolling() {
    if (pollTimerId) return; // Already polling
    sseGaveUp = true;
    pollChanges();
  }

  /** Stops polling mode. */
  function stopPolling() {
    if (pollTimerId) {
      clearTimeout(pollTimerId);
      pollTimerId = null;
    }
    sseGaveUp = false;
  }

  /** Performs a single poll request and schedules the next one. */
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
      if (changes.memory) {
        refreshMemory();
      }
    }).catch(function () {
      // /poll failure: handle silently (no console error)
    }).then(function () {
      // finally polyfill (ES5 compat: Promise.prototype.finally not available)
      if (sseGaveUp && !document.hidden) {
        pollTimerId = setTimeout(pollChanges, POLL_INTERVAL);
      } else {
        pollTimerId = null;
      }
    });
  }

  /** Schedules SSE reconnection attempt after interval. */
  function scheduleSSERetry() {
    if (sseRetryTimerId) return; // Already scheduled
    sseRetryTimerId = setTimeout(function () {
      sseRetryTimerId = null;
      initSSE(); // Retry SSE (on success, onopen stops polling)
    }, SSE_RETRY_INTERVAL);
  }

  // ── Init ──
  // 쿼리 스트링 우선, localStorage 폴백으로 viewer 상태 복원
  var qsParams = new URLSearchParams(window.location.search);
  var qsTab = qsParams.get("tab");
  var qsTicket = qsParams.get("ticket");
  var initSavedTabs = (Board.util.loadUI().viewerTabs || []).slice();

  // 쿼리 스트링에 ticket이 있으면 savedTabs에 추가 (중복 방지)
  if (qsTab === "viewer" && qsTicket) {
    Board.state.activeTab = "viewer";
    Board.state.activeViewerTab = qsTicket;
    if (initSavedTabs.indexOf(qsTicket) === -1) initSavedTabs.push(qsTicket);
  }

  // switchTab 전에 placeholder로 viewerTabs 복원 (saveUI 덮어쓰기 방지)
  initSavedTabs.forEach(function (num) {
    Board.state.viewerTabs.push({ number: num, ticket: null });
  });
  switchTab(Board.state.activeTab);
  document.body.style.opacity = "";

  Board.fetch.fetchTickets().then(function (tickets) {
    Board.state.TICKETS = tickets;
    prevTicketJson = ticketJson(tickets);
    Board.render.renderKanban();
    if (initSavedTabs.length > 0) {
      initSavedTabs.forEach(function (num) {
        var ticket = Board.state.TICKETS.find(function (t) { return t.number === num; });
        var existing = Board.state.viewerTabs.find(function (t) { return t.number === num; });
        if (ticket && existing) {
          existing.ticket = ticket;
        } else if (!ticket && existing) {
          Board.state.viewerTabs = Board.state.viewerTabs.filter(function (t) { return t.number !== num; });
        }
      });
      Board.util.saveUI();
      if (Board.state.activeTab === "viewer") Board.render.renderViewer();
    }
  });

  Board.fetch.fetchWorkflowEntries().then(function (hrefs) {
    Board.state.wfEntryHrefs = hrefs;
    prevWfJson = JSON.stringify(hrefs);
    Board.render.loadMoreWorkflows();
  });

  // Start SSE connection (falls back to polling on error)
  initSSE();

  // Compensate for missed changes when tab regains visibility
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) {
      if (sseConnected) {
        // SSE connected: compensate for potentially missed events
        refreshKanban();
        refreshWorkflow();
      } else if (sseGaveUp) {
        // Polling mode: resume polling immediately on tab return
        if (!pollTimerId) {
          pollChanges();
        }
      }
    }
  });

  // Pre-fetch dashboard data in background so it's ready on tab switch
  Board.fetch.fetchAllDashboardFiles().then(function () {
    if (Board.state.activeTab === "dashboard") Board.render.renderDashboard();
  });

})();
