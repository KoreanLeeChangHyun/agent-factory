/**
 * @module sse
 *
 * Board SPA real-time update module.
 *
 * Manages Server-Sent Events (SSE) connection with automatic fallback to
 * polling when SSE is unavailable or fails. Handles conveyor, workflow,
 * and dashboard refresh on data changes. Also contains the application
 * initialization sequence (must be loaded last).
 *
 * Depends on: common.js, conveyor.js, viewer.js, workflow.js, dashboard.js
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

  let prevWorkRequestJson = "";
  let prevWfJson = "";

  // ── Helpers ──

  /**
   * Serializes workRequests to a JSON string for change detection.
   * @param {Array} workRequests - workRequest array
   * @returns {string} JSON string
   */
  function workRequestJson(workRequests) {
    return JSON.stringify(workRequests.map(function (t) {
      return { number: t.number, title: t.title, status: t.status,
               command: t.command, prompt: t.prompt, result: t.result };
    }));
  }

  // ── Conveyor Refresh (SSE/Polling shared) ──

  /**
   * Refreshes the conveyor board.
   * @param {string[]} [files] - Changed file names. If provided, selective fetch; otherwise full fetch.
   */
  function refreshConveyor(files) {
    var fetchPromise = (files && files.length > 0)
      ? Board.fetch.fetchWorkRequestsByFiles(files).then(function () { return Board.state.WORK_REQUESTS; })
      : Board.fetch.fetchWorkRequests().then(function (workRequests) {
          // Preserve existing data if fetch returned empty due to error
          // (fetchWorkRequests catch handler returns [] on failure; skip overwrite if we already have data)
          if (!workRequests || (workRequests.length === 0 && Board.state.WORK_REQUESTS.length > 0)) {
            return Board.state.WORK_REQUESTS;
          }
          Board.state.WORK_REQUESTS = workRequests;
          return Board.state.WORK_REQUESTS;
        });

    fetchPromise.then(function (workRequests) {
      if (!workRequests) return; // fetch failed: preserve existing data, skip update
      const json = workRequestJson(workRequests);
      if (json !== prevWorkRequestJson) {
        prevWorkRequestJson = json;
        Board.render.renderConveyor();
        if (Board.state.activeTab === "relations" && Board.render.renderRelations) {
          Board.render.renderRelations();
        }
        // workflow tab rely on workRequest mapping — WORK_REQUESTS update only
        // (Specification of shells to preserve the bar·scroll·spoker)
        if (Board.state.activeTab === "workflow" && Board.render.renderWfTbody) {
          Board.render.renderWfTbody();
        }
        Board.state.viewerTabs.forEach(function (vt) {
          if (vt.workRequest) {
            const fresh = Board.state.WORK_REQUESTS.find(function (t) { return t.number === vt.number; });
            if (fresh) vt.workRequest = fresh;
          }
        });
        const activeVt = Board.state.viewerTabs.find(function (t) { return t.number === Board.state.activeViewerTab; });
        if (activeVt && activeVt.workRequest && Board.state.activeTab === "viewer") Board.render.renderViewer();
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

  // ── Git Branch Refresh (SSE/Polling shared) ──

  /**
   * Updates the status bar branch indicator from a fresh value.
   *
   * SSE git branch event uses branch delivered by payload directly,
   * /api/branch re-fetch due to polling fallback only changes signal.
   *
   * @param {string null} branch - SSE payload branch value. without fetch.
   */
  function refreshBranch(branch) {
    if (branch) {
      if (Board.util.setBranchStatusBar) Board.util.setBranchStatusBar(branch);
      return;
    }
    fetch("/api/branch").then(function (r) { return r.json(); }).then(function (d) {
      if (Board.util.setBranchStatusBar) Board.util.setBranchStatusBar(d.branch);
    }).catch(function () {});
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
      refreshConveyor();
      refreshWorkflow();
      refreshDashboard();
    };

    es.addEventListener("conveyor", function (e) {
      try {
        var d = JSON.parse(e.data);
        refreshConveyor(d.files);
      } catch (_) {
        refreshConveyor();
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

    es.addEventListener("roadmap", function () {
      if (Board.render.refreshRoadmap) Board.render.refreshRoadmap();
    });

    es.addEventListener("git_branch", function (e) {
      var branchVal = null;
      try {
        var d = JSON.parse(e.data);
        branchVal = d && d.branch;
      } catch (_) {
        branchVal = null;
      }
      refreshBranch(branchVal);
      // WR-433 Phase 2: Verifying Card Toggle Visual Synchronization (only when registering the Conveyor module)
      if (Board.render.syncActiveBranchFromSSE) {
        Board.render.syncActiveBranchFromSSE(branchVal);
      }
    });

    // WR-475 Stage 3: Launch Asynchronousization — LAUNCH PENDING/STARTED/FAILED DESIGN
    // sse manager.broadcast('launch', data={event:..., work_request:..., ...})
    // handleLaunchEvent in the conveyor module manipulates the launchState machine (addEventListener duplicates §2.4).
    es.addEventListener("launch", function (e) {
      try {
        var d = JSON.parse(e.data);
        if (Board.conveyor && Board.conveyor.handleLaunchEvent) {
          Board.conveyor.handleLaunchEvent(d);
        }
      } catch (_) { /* malformed payload — silently skip */ }
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
      if (changes.conveyor) {
        refreshConveyor(changes.conveyor);
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
      if (changes.roadmap) {
        if (Board.render.refreshRoadmap) Board.render.refreshRoadmap();
      }
      if (changes.git_branch) {
        // polling payload [branch] list — use the last value
        var arr = changes.git_branch;
        var last = (arr && arr.length) ? arr[arr.length - 1] : null;
        refreshBranch(last);
        // WR-433 Phase 2: Sync Verifying Card Toggles Vision even polling fallback
        if (Board.render.syncActiveBranchFromSSE) {
          Board.render.syncActiveBranchFromSSE(last);
        }
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
  // Query String First, restore viewer status with localStorage bag
  var qsParams = new URLSearchParams(window.location.search);
  var qsTab = qsParams.get("tab");
  var qsWorkRequest = qsParams.get("work_request");
  var initSavedTabs = (Board.util.loadUI().viewerTabs || []).slice();

  // Add to saveTabs if there is a workRequest to the query string
  if (qsTab === "viewer" && qsWorkRequest) {
    Board.state.activeTab = "viewer";
    Board.state.activeViewerTab = qsWorkRequest;
    if (initSavedTabs.indexOf(qsWorkRequest) === -1) initSavedTabs.push(qsWorkRequest);
  } else if (qsTab === "metrics") {
    // ? tab=metrics — Metrics tab redirect to Dashboard (WR-461 Phase 3)
    Board.state.activeTab = "dashboard";
    var pathOnly = window.location.pathname;
    history.replaceState(null, "", pathOnly);
  }

  // restore viewerTabs as placeholder before switchTab (anti-saveUI)
  initSavedTabs.forEach(function (num) {
    Board.state.viewerTabs.push({ number: num, workRequest: null });
  });
  switchTab(Board.state.activeTab);
  document.body.style.opacity = "";

  // WR-475 Stage 3: Launch starting status sessionStorage Restore (fetchWorkRequests call before response)
  // When the first renderConveyor point, the pulse badge will be immediately exposed. grace residual time recalculate + restart timer.
  if (Board.conveyor && Board.conveyor.restoreLaunchStateFromStorage) {
    Board.conveyor.restoreLaunchStateFromStorage();
  }

  Board.fetch.fetchWorkRequests().then(function (workRequests) {
    Board.state.WORK_REQUESTS = workRequests;
    prevWorkRequestJson = workRequestJson(workRequests);
    Board.render.renderConveyor();
    // Race Calibration: When the first renderer is finished before fetchWorkRequests is finished, WORK_REQUESTS= resolves all the lines with the[].
    // Tbody only re-draws and fills the workRequest map (Search bar, roll, pointer preserve).
    if (Board.state.wfInitialized && Board.render.renderWfTbody) Board.render.renderWfTbody();
    if (initSavedTabs.length > 0) {
      initSavedTabs.forEach(function (num) {
        var workRequest = Board.state.WORK_REQUESTS.find(function (t) { return t.number === num; });
        var existing = Board.state.viewerTabs.find(function (t) { return t.number === num; });
        if (workRequest && existing) {
          existing.workRequest = workRequest;
        } else if (!workRequest && existing) {
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
        refreshConveyor();
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
