/**
 * @module production-line-workflow
 *
 * Board.productionLineWorkflow — WR-495 P2 frontend client for production-line subprocess.
 *
 * v1 /terminal/workflow/events single SSE channel and separated production-line only client.
 * backend 7 endpoint and 1:1 mapping:
 *   GET  /api/v2/sessions                       — list
 *   GET  /api/v2/sessions/<id>                  — detail (current_step / phase / artifacts / ts)
 *   GET /api/v2/sessions/<id>/events — SSE Subscription (per-session)
 *   GET /api/v2/sessions/<id>/history — persist NDJSON Event (REST Single Source)
 *   GET /api/v2/sessions/<id>/artifacts/<rel> — output read
 *
 * SSE event name (v1 'stdout'/'result'/'system' and separated):
 *   <% if (imgObj.width >= imgObj.height) { %>
 *   workflow_stdout  — claude -p stdout NDJSON chunk
 *   workflow phase — WORK internal phase transformation
 *   workflow finish — cycle closing
 *
 * Depends on: common.js (Board namespace)
 * Registers:  Board.productionLineWorkflow
 *
 * Public API:
 *   fetchSessions()                  → Promise<Array<sessionMeta>>
 *   fetchSession(sessionId)          → Promise<sessionDetail|null>
 *   fetchArtifact(sessionId, relPath) → Promise<string|null>
 *   subscribe(sessionId, handlers)   → { close, sessionId }
 *   isProductionLineSessionId(sessionId)         → boolean
 *
 * handlers parameter shape (full optional):
 *   {
 *     onOpen()                              — EventSource open
 *     onStep({step, prev_step, phase, ts})  — workflow_step
 *     onStdout({text, raw, ts})             — workflow_stdout
 *     onPhase({phase, action, ts})          — workflow_phase
 *     onFinish({outcome, summary, ts})      — workflow_finish
 *     onError(err) — Network/Pushing Error
 *   }
 */
"use strict";

(function () {

  // ── VIEW

  /** production-line session id pattern — `wf-WR-NNN-<registry key>`. v1 also like prefix la backend with authority. */
  var PRODUCTION_LINE_SESSION_PREFIX = "wf-";

  /** SSE reconnect interval (ms) — Same as v1 session.js. */
  var SSE_RECONNECT_INTERVAL = 3000;

  // ── Internal Helper ──

  /**
   * fetch wrapper — returning JSON response. 404/network error returns null.
   * @param {string} url
   * @returns {Promise<any|null>}
   */
  function _fetchJson(url) {
    return fetch(url, { cache: "no-store" }).then(function (res) {
      if (res.status === 404) return null;
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    }).catch(function (err) {
      console.error("[production-line-workflow] fetch failed:", url, err);
      return null;
    });
  }

  /**
   * fetch wrapper — return text response (for artifact viewer). 404 → null
   * @param {string} url
   * @returns {Promise<string|null>}
   */
  function _fetchText(url) {
    return fetch(url, { cache: "no-store" }).then(function (res) {
      if (res.status === 404) return null;
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.text();
    }).catch(function (err) {
      console.error("[production-line-workflow] fetch text failed:", url, err);
      return null;
    });
  }

  /**
   * SSE event.data → JSON parse. null return + console.error when malformed.
   */
  function _safeParse(raw) {
    if (typeof raw !== "string") return null;
    try {
      return JSON.parse(raw);
    } catch (err) {
      console.error("[production-line-workflow] SSE parse error:", err, raw);
      return null;
    }
  }

  // ── REST API ──

  /**
   * return the full production-line session list.
   * @returns {Promise<Array<{session_id, work_request, command, work_dir, worktree_path, status, current_step, current_phase, cycle_start_ts, step_ts, created_at}>>}
   */
  function fetchSessions() {
    return _fetchJson("/api/v2/sessions").then(function (data) {
      return Array.isArray(data) ? data : [];
    });
  }

  /**
   * Returns the details of a single production-line session. 404 → null
   * @param {string} sessionId
   * @returns {Promise<object|null>}
   */
  function fetchSession(sessionId) {
    if (!sessionId) return Promise.resolve(null);
    return _fetchJson("/api/v2/sessions/" + encodeURIComponent(sessionId));
  }

  /**
   * returns the output file to text. work dir standard relative path.
   * @param {string} sessionId
   * @param {string} relPath — example: "plan.md", "work/P1.md", "metrics.jsonl"
   * @returns {Promise<string|null>}
   */
  function fetchArtifact(sessionId, relPath) {
    if (!sessionId || !relPath) return Promise.resolve(null);
    var url = "/api/v2/sessions/" + encodeURIComponent(sessionId)
      + "/artifacts/" + relPath.split("/").map(encodeURIComponent).join("/");
    return _fetchText(url);
  }

  /**
   * Output URL — used when calling viewer with a new tab.
   * @param {string} sessionId
   * @param {string} relPath
   * @returns {string}
   */
  function artifactUrl(sessionId, relPath) {
    return "/api/v2/sessions/" + encodeURIComponent(sessionId)
      + "/artifacts/" + relPath.split("/").map(encodeURIComponent).join("/");
  }

  /**
   * WR-513 P3 — REST single source history loader.
   *
   * When reconnecting, SSE will load the past event before registration. SSE Ring Buffer Replay
   * REST GET /api/v2/sessions/<id>/history
   * (WR-497 Crystal). schema: {session id, total count,
   * event: [{ts, event, payload}]}. 404/network error return empty array.
   *
   * @param {string} sessionId
   * @returns {Promise<Array<{ts:number,event:string,payload:object}>>}
   */
  function fetchHistory(sessionId) {
    if (!sessionId) return Promise.resolve([]);
    var url = "/api/v2/sessions/" + encodeURIComponent(sessionId) + "/history";
    return _fetchJson(url).then(function (data) {
      if (!data || !Array.isArray(data.events)) return [];
      return data.events;
    });
  }

  // ── SSE Subscription ──

  /**
   * the per-session SSE stream of production-line.
   *
   * Single entry point — 4 types event quarters with handler callback (workflow step / stdout /
   * phase / finish). reconnect can be specified + explicit close for EventSource default operation.
   *
   * @param {string} sessionId
   * @param {object} handlers - collection of callbacks (more optional)
   * @returns {{close: function, sessionId: string}}
   */
  function subscribe(sessionId, handlers) {
    if (!sessionId) {
      return { close: function () {}, sessionId: null };
    }
    var h = handlers || {};

    var url = "/api/v2/sessions/" + encodeURIComponent(sessionId) + "/events";
    var es = null;
    var closed = false;
    var reconnectTimer = null;
    var lastEventId = -1;

    function _open() {
      if (closed) return;
      var suffix = lastEventId >= 0
        ? (url.indexOf("?") >= 0 ? "&" : "?") + "last_event_id=" + lastEventId
        : "";
      try {
        es = new EventSource(url + suffix);
      } catch (err) {
        if (typeof h.onError === "function") h.onError(err);
        _scheduleReconnect();
        return;
      }

      es.addEventListener("open", function () {
        if (typeof h.onOpen === "function") h.onOpen();
      });

      es.addEventListener("workflow_step", function (e) {
        _captureId(e);
        var data = _safeParse(e.data);
        if (data && typeof h.onStep === "function") h.onStep(data);
      });

      es.addEventListener("workflow_stdout", function (e) {
        _captureId(e);
        var data = _safeParse(e.data);
        if (data && typeof h.onStdout === "function") h.onStdout(data);
      });

      es.addEventListener("workflow_phase", function (e) {
        _captureId(e);
        var data = _safeParse(e.data);
        if (data && typeof h.onPhase === "function") h.onPhase(data);
      });

      es.addEventListener("workflow_finish", function (e) {
        _captureId(e);
        var data = _safeParse(e.data);
        if (data && typeof h.onFinish === "function") h.onFinish(data);
      });

      es.onerror = function () {
        if (closed) return;
        if (typeof h.onError === "function") h.onError(new Error("SSE error"));
        try { es.close(); } catch (_) {}
        es = null;
        _scheduleReconnect();
      };
    }

    function _captureId(e) {
      if (!e || e.lastEventId == null) return;
      var n = parseInt(e.lastEventId, 10);
      if (!isNaN(n) && n > lastEventId) lastEventId = n;
    }

    function _scheduleReconnect() {
      if (closed || reconnectTimer) return;
      reconnectTimer = setTimeout(function () {
        reconnectTimer = null;
        _open();
      }, SSE_RECONNECT_INTERVAL);
    }

    function close() {
      closed = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (es) {
        try { es.close(); } catch (_) {}
        es = null;
      }
    }

    _open();
    return { close: close, sessionId: sessionId };
  }

  // ── Quarterfinal ──

  /**
   * sessionId is registered in production-line backend and cache-line correction.
   * synchronous helper for instant use — known set to false return.
   * Asynchronous check with fetchSession.
   *
   * @param {string} sessionId
   * @returns {boolean}
   */
  function isProductionLineSessionId(sessionId) {
    if (!sessionId || typeof sessionId !== "string") return false;
    return _knownSessions.has(sessionId);
  }

  /**
   * Registered the production-line session id to be found in the backend response.
   * (e.g. LAUNCH STARTED event payload, /api/v2/sessions response, etc.)
   * @param {string} sessionId
   */
  function registerKnown(sessionId) {
    if (sessionId && typeof sessionId === "string") {
      _knownSessions.add(sessionId);
    }
  }

  /**
   * Once synchronized the known production-line session list (recommended to call on page load).
   * @returns {Promise<Set<string>>}
   */
  function syncKnownSessions() {
    return fetchSessions().then(function (sessions) {
      sessions.forEach(function (s) {
        if (s && s.session_id) _knownSessions.add(s.session_id);
      });
      return _knownSessions;
    });
  }

  // ── Internal Status ──

  /** @type {Set<string>} backend registered production-line session id cache */
  var _knownSessions = new Set();

  // ── Register on Board namespace ──
  Board.productionLineWorkflow = {
    // About Us
    isProductionLineSessionId: isProductionLineSessionId,
    registerKnown: registerKnown,
    syncKnownSessions: syncKnownSessions,
    // REST
    fetchSessions: fetchSessions,
    fetchSession: fetchSession,
    fetchArtifact: fetchArtifact,
    artifactUrl: artifactUrl,
    fetchHistory: fetchHistory,
    // SSE
    subscribe: subscribe,
    // Constant exposure (Forest / Debug)
    _PRODUCTION_LINE_SESSION_PREFIX: PRODUCTION_LINE_SESSION_PREFIX,
  };

  // Backend and once synchronization with page loads.
  // standalone (terminal.html) syncs immediately after loading this module.
  if (typeof window !== "undefined") {
    syncKnownSessions().catch(function (err) {
      console.error("[production-line-workflow] initial sync failed:", err);
    });
  }
})();
