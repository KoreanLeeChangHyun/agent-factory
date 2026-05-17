/**
 * @module v2-viewer
 *
 * Board.v2Viewer — T-495 P3 산출물 / 로그 / metrics viewer.
 *
 * 3종 viewer 진입점:
 *   openArtifact(sessionId, relPath)      — 단일 산출물 (plan.md / work/P*.md / report.md /
 *                                            validate-report.md / summary.txt / usage.json)
 *   openLogTail(sessionId)                — workflow.log polling tail
 *   openMetricsTail(sessionId)            — metrics.jsonl polling tail (NDJSON)
 *
 * 모두 같은 floating overlay panel 을 재사용. 한 번에 한 viewer 만 표시.
 *
 * polling 주기: 2000ms (idle), 1000ms (활성 워크플로우 추정 시).
 * idle 판정 = workflow status === "done" / "failed".
 *
 * Depends on: common.js (Board namespace), v2-workflow.js (artifactUrl/fetchArtifact)
 * Registers:  Board.v2Viewer
 */
"use strict";

(function () {

  // ── 상수 ──

  var TAIL_INTERVAL_ACTIVE_MS = 1000;
  var TAIL_INTERVAL_IDLE_MS = 2000;

  /** 가장 최근 250 줄만 화면에 보존 (DOM 무게 관리) */
  var MAX_TAIL_LINES = 250;

  // ── 내부 상태 ──

  /** @type {{sessionId: string, relPath: string, kind: string, timer: number|null} | null} */
  var _active = null;

  /** @type {HTMLElement|null} viewer overlay DOM */
  var _overlay = null;

  // ── DOM helper ──

  function _esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /**
   * overlay DOM 을 게으르게 생성. 한 번 만들면 body 에 영구 부착.
   * @returns {HTMLElement}
   */
  function _ensureOverlay() {
    if (_overlay && document.body.contains(_overlay)) return _overlay;
    var el = document.createElement("div");
    el.className = "wf-v2-viewer hidden";
    el.id = "wf-v2-viewer";
    el.innerHTML = ''
      + '<div class="wf-v2-viewer-header">'
      +   '<span class="wf-v2-viewer-title"></span>'
      +   '<span class="wf-v2-viewer-meta"></span>'
      +   '<button class="wf-v2-viewer-refresh" type="button" title="새로고침">↻</button>'
      +   '<button class="wf-v2-viewer-newtab" type="button" title="새 탭으로 열기">↗</button>'
      +   '<button class="wf-v2-viewer-close" type="button" title="닫기">×</button>'
      + '</div>'
      + '<pre class="wf-v2-viewer-body"></pre>';
    document.body.appendChild(el);
    _overlay = el;

    el.querySelector(".wf-v2-viewer-close").addEventListener("click", function () {
      close();
    });
    el.querySelector(".wf-v2-viewer-refresh").addEventListener("click", function () {
      if (_active) _fetchAndRender(_active.sessionId, _active.relPath);
    });
    el.querySelector(".wf-v2-viewer-newtab").addEventListener("click", function () {
      if (!_active || !Board.v2Workflow) return;
      var url = Board.v2Workflow.artifactUrl(_active.sessionId, _active.relPath);
      window.open(url, "_blank");
    });
    return el;
  }

  function _setTitle(title, meta) {
    var el = _ensureOverlay();
    var t = el.querySelector(".wf-v2-viewer-title");
    var m = el.querySelector(".wf-v2-viewer-meta");
    if (t) t.textContent = title || "";
    if (m) m.textContent = meta || "";
  }

  function _setBody(text) {
    var el = _ensureOverlay();
    var body = el.querySelector(".wf-v2-viewer-body");
    if (!body) return;
    if (typeof text === "string") {
      // tail 만 보존
      var lines = text.split("\n");
      var displayed = lines.length > MAX_TAIL_LINES
        ? lines.slice(lines.length - MAX_TAIL_LINES)
        : lines;
      body.textContent = displayed.join("\n");
      // scroll to bottom for tail
      body.scrollTop = body.scrollHeight;
    } else {
      body.textContent = "(empty)";
    }
  }

  function _show() {
    var el = _ensureOverlay();
    el.classList.remove("hidden");
  }

  function _hide() {
    if (_overlay) _overlay.classList.add("hidden");
  }

  // ── fetch ──

  function _fetchAndRender(sessionId, relPath) {
    if (!Board.v2Workflow || !Board.v2Workflow.fetchArtifact) return;
    Board.v2Workflow.fetchArtifact(sessionId, relPath).then(function (text) {
      if (!_active || _active.sessionId !== sessionId || _active.relPath !== relPath) return;
      if (text == null) {
        _setBody("(파일 없음: " + relPath + ")");
      } else {
        _setBody(text);
      }
      var now = new Date();
      var hh = String(now.getHours()).padStart(2, "0");
      var mm = String(now.getMinutes()).padStart(2, "0");
      var ss = String(now.getSeconds()).padStart(2, "0");
      _setTitle(_active.title || relPath, "갱신 " + hh + ":" + mm + ":" + ss);
    }).catch(function (err) {
      _setBody("[오류] " + (err && err.message || err));
    });
  }

  function _startPolling(sessionId, relPath, intervalMs) {
    _stopPolling();
    _active.timer = setInterval(function () {
      _fetchAndRender(sessionId, relPath);
    }, intervalMs);
  }

  function _stopPolling() {
    if (_active && _active.timer) {
      clearInterval(_active.timer);
      _active.timer = null;
    }
  }

  // ── Public API ──

  /**
   * 단일 산출물 viewer (1회 fetch, polling 없음).
   * @param {string} sessionId
   * @param {string} relPath  — 예: "plan.md" / "work/P1.md" / "report.md"
   */
  function openArtifact(sessionId, relPath) {
    if (!sessionId || !relPath) return;
    _stopPolling();
    _active = { sessionId: sessionId, relPath: relPath, kind: "artifact", timer: null, title: relPath };
    _show();
    _setTitle(relPath, "로딩...");
    _setBody("");
    _fetchAndRender(sessionId, relPath);
  }

  /**
   * workflow.log tail viewer (polling 2s).
   * @param {string} sessionId
   */
  function openLogTail(sessionId) {
    if (!sessionId) return;
    _stopPolling();
    _active = {
      sessionId: sessionId, relPath: "workflow.log", kind: "log",
      timer: null, title: "workflow.log (tail)",
    };
    _show();
    _setTitle("workflow.log (tail)", "polling...");
    _setBody("");
    _fetchAndRender(sessionId, "workflow.log");
    _startPolling(sessionId, "workflow.log", _activeIntervalMs());
  }

  /**
   * metrics.jsonl stream viewer (polling 2s, NDJSON).
   * @param {string} sessionId
   */
  function openMetricsTail(sessionId) {
    if (!sessionId) return;
    _stopPolling();
    _active = {
      sessionId: sessionId, relPath: "metrics.jsonl", kind: "metrics",
      timer: null, title: "metrics.jsonl (stream)",
    };
    _show();
    _setTitle("metrics.jsonl (stream)", "polling...");
    _setBody("");
    _fetchAndRender(sessionId, "metrics.jsonl");
    _startPolling(sessionId, "metrics.jsonl", _activeIntervalMs());
  }

  /** viewer 닫기 + polling 중단. */
  function close() {
    _stopPolling();
    _active = null;
    _hide();
  }

  /** 워크플로우 활성 추정 시 1s, 종료 후 2s. */
  function _activeIntervalMs() {
    try {
      var st = Board.WorkflowRenderer && Board.WorkflowRenderer.state;
      if (st && (st.status === "done" || st.status === "failed")) {
        return TAIL_INTERVAL_IDLE_MS;
      }
    } catch (_) {}
    return TAIL_INTERVAL_ACTIVE_MS;
  }

  // ── Register ──
  Board.v2Viewer = {
    openArtifact: openArtifact,
    openLogTail: openLogTail,
    openMetricsTail: openMetricsTail,
    close: close,
  };
})();
