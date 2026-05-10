// js/terminal/terminal-branch-sync.js
// Terminal-only isolated SSE client for git_branch event.
// Intentionally does NOT reuse js/core/sse.js — sse.js calls Board.render.*
// and Board.fetch.* functions that are not loaded in terminal.html.
"use strict";

(function () {
  if (typeof EventSource === "undefined") return;

  var SSE_RETRY_MS = 30000;
  var currentES = null;
  var retryTimerId = null;

  function connect() {
    if (currentES) {
      currentES.close();
      currentES = null;
    }

    var es = new EventSource("/events");
    currentES = es;

    es.addEventListener("git_branch", function (e) {
      var branch = null;
      try {
        var d = JSON.parse(e.data);
        branch = d && d.branch;
      } catch (_) {
        branch = null;
      }
      if (branch && Board.util && Board.util.setBranchStatusBar) {
        Board.util.setBranchStatusBar(branch);
      }
    });

    es.onerror = function () {
      es.close();
      if (currentES === es) currentES = null;
      scheduleRetry();
    };
  }

  function scheduleRetry() {
    if (retryTimerId) return;
    retryTimerId = setTimeout(function () {
      retryTimerId = null;
      connect();
    }, SSE_RETRY_MS);
  }

  connect();
})();
