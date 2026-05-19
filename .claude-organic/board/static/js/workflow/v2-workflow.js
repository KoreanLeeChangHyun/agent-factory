/**
 * @module v2-workflow
 *
 * Board.v2Workflow — T-495 P2 frontend client for v2 driver subprocess.
 *
 * v1 의 /terminal/workflow/events 단일 SSE 채널과 분리된 v2 전용 client.
 * backend 의 7 endpoint 와 1:1 매핑:
 *   GET  /api/v2/sessions                       — list
 *   GET  /api/v2/sessions/<id>                  — detail (current_step / phase / artifacts / ts)
 *   GET  /api/v2/sessions/<id>/events           — SSE 구독 (per-session)
 *   GET  /api/v2/sessions/<id>/history          — persist NDJSON 이벤트 (REST 단일 출처)
 *   GET  /api/v2/sessions/<id>/artifacts/<rel>  — 산출물 read
 *
 * SSE event 이름 (v1 'stdout'/'result'/'system' 과 분리):
 *   workflow_step    — Step 전이 (NONE/INIT/PLAN/WORK/VALIDATE/REPORT/DONE/FAILED)
 *   workflow_stdout  — claude -p stdout NDJSON chunk
 *   workflow_phase   — WORK 내부 phase 전이
 *   workflow_finish  — 사이클 종결
 *
 * Depends on: common.js (Board namespace)
 * Registers:  Board.v2Workflow
 *
 * 공개 API:
 *   fetchSessions()                  → Promise<Array<sessionMeta>>
 *   fetchSession(sessionId)          → Promise<sessionDetail|null>
 *   fetchArtifact(sessionId, relPath) → Promise<string|null>
 *   subscribe(sessionId, handlers)   → { close, sessionId }
 *   isV2SessionId(sessionId)         → boolean
 *
 * handlers 매개변수 shape (모두 optional):
 *   {
 *     onOpen()                              — EventSource open
 *     onStep({step, prev_step, phase, ts})  — workflow_step
 *     onStdout({text, raw, ts})             — workflow_stdout
 *     onPhase({phase, action, ts})          — workflow_phase
 *     onFinish({outcome, summary, ts})      — workflow_finish
 *     onError(err)                          — 네트워크/파싱 에러
 *   }
 */
"use strict";

(function () {

  // ── 상수 ──

  /** v2 session_id 패턴 — `wf-T-NNN-<registry_key>`. v1 도 같은 prefix 라 backend 가 권위. */
  var V2_SESSION_PREFIX = "wf-";

  /** SSE 재연결 간격 (ms) — v1 session.js 와 동일. */
  var SSE_RECONNECT_INTERVAL = 3000;

  // ── 내부 헬퍼 ──

  /**
   * fetch wrapper — JSON 응답을 파싱하여 반환. 404/네트워크 에러는 null 반환.
   * @param {string} url
   * @returns {Promise<any|null>}
   */
  function _fetchJson(url) {
    return fetch(url, { cache: "no-store" }).then(function (res) {
      if (res.status === 404) return null;
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    }).catch(function (err) {
      console.error("[v2-workflow] fetch failed:", url, err);
      return null;
    });
  }

  /**
   * fetch wrapper — text 응답을 반환 (artifact viewer 용). 404 → null.
   * @param {string} url
   * @returns {Promise<string|null>}
   */
  function _fetchText(url) {
    return fetch(url, { cache: "no-store" }).then(function (res) {
      if (res.status === 404) return null;
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.text();
    }).catch(function (err) {
      console.error("[v2-workflow] fetch text failed:", url, err);
      return null;
    });
  }

  /**
   * SSE event.data → JSON 파싱. malformed 시 null 반환 + console.error.
   */
  function _safeParse(raw) {
    if (typeof raw !== "string") return null;
    try {
      return JSON.parse(raw);
    } catch (err) {
      console.error("[v2-workflow] SSE parse error:", err, raw);
      return null;
    }
  }

  // ── REST API ──

  /**
   * 전체 v2 세션 목록을 반환한다.
   * @returns {Promise<Array<{session_id, ticket_id, command, work_dir, worktree_path, status, current_step, current_phase, cycle_start_ts, step_ts, created_at}>>}
   */
  function fetchSessions() {
    return _fetchJson("/api/v2/sessions").then(function (data) {
      return Array.isArray(data) ? data : [];
    });
  }

  /**
   * 단일 v2 세션의 상세 정보를 반환한다. 404 → null.
   * @param {string} sessionId
   * @returns {Promise<object|null>}
   */
  function fetchSession(sessionId) {
    if (!sessionId) return Promise.resolve(null);
    return _fetchJson("/api/v2/sessions/" + encodeURIComponent(sessionId));
  }

  /**
   * 산출물 파일을 text 로 반환한다. work_dir 기준 상대 경로.
   * @param {string} sessionId
   * @param {string} relPath — 예: "plan.md", "work/P1.md", "metrics.jsonl"
   * @returns {Promise<string|null>}
   */
  function fetchArtifact(sessionId, relPath) {
    if (!sessionId || !relPath) return Promise.resolve(null);
    var url = "/api/v2/sessions/" + encodeURIComponent(sessionId)
      + "/artifacts/" + relPath.split("/").map(encodeURIComponent).join("/");
    return _fetchText(url);
  }

  /**
   * 산출물 URL — 새 탭으로 viewer 호출 시 사용.
   * @param {string} sessionId
   * @param {string} relPath
   * @returns {string}
   */
  function artifactUrl(sessionId, relPath) {
    return "/api/v2/sessions/" + encodeURIComponent(sessionId)
      + "/artifacts/" + relPath.split("/").map(encodeURIComponent).join("/");
  }

  /**
   * T-513 P3 — REST 단일 출처 history loader.
   *
   * 재연결 시 SSE 라이브 등록 전 과거 이벤트를 일괄 적재한다. SSE 링버퍼 replay 는
   * 사용하지 않고 REST GET /api/v2/sessions/<id>/history 가 단일 출처
   * (T-497 결정점 정합). 응답 schema: {session_id, total_count,
   * events: [{ts, event, payload}]}. 404/네트워크 에러 시 빈 배열 반환.
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

  // ── SSE 구독 ──

  /**
   * v2 driver 의 per-session SSE 스트림을 구독한다.
   *
   * 단일 진입점 — handler 콜백으로 4 종 이벤트 분기 (workflow_step / stdout /
   * phase / finish). reconnect 는 EventSource 기본 동작에 위임 + 명시적 close 가능.
   *
   * @param {string} sessionId
   * @param {object} handlers - 콜백 모음 (모두 optional)
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

  // ── 분기 판정 ──

  /**
   * sessionId 가 v2 backend 에 등록되어 있는지 캐시-우선 판정.
   * 즉시 사용을 위한 동기 helper — known set 에 없으면 false 반환.
   * 비동기 확인은 fetchSession 으로.
   *
   * @param {string} sessionId
   * @returns {boolean}
   */
  function isV2SessionId(sessionId) {
    if (!sessionId || typeof sessionId !== "string") return false;
    return _knownSessions.has(sessionId);
  }

  /**
   * 외부 호출자가 backend 응답에서 알게 된 v2 session_id 를 등록한다.
   * (예: LAUNCH_STARTED 이벤트 payload, /api/v2/sessions 응답 등)
   * @param {string} sessionId
   */
  function registerKnown(sessionId) {
    if (sessionId && typeof sessionId === "string") {
      _knownSessions.add(sessionId);
    }
  }

  /**
   * 알려진 v2 세션 목록을 한번 동기화 (페이지 로드 시 호출 권장).
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

  // ── 내부 상태 ──

  /** @type {Set<string>} backend 에 등록된 v2 session_id 캐시 */
  var _knownSessions = new Set();

  // ── Register on Board namespace ──
  Board.v2Workflow = {
    // 분기 판정
    isV2SessionId: isV2SessionId,
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
    // 상수 노출 (테스트 / 디버그 용)
    _V2_SESSION_PREFIX: V2_SESSION_PREFIX,
  };

  // 페이지 로드 시 known 캐시를 backend 와 한 번 동기화.
  // standalone (terminal.html) 에서는 본 모듈을 로드한 직후 즉시 동기화한다.
  if (typeof window !== "undefined") {
    syncKnownSessions().catch(function (err) {
      console.error("[v2-workflow] initial sync failed:", err);
    });
  }
})();
