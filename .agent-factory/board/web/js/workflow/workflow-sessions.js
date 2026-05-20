/**
 * @module workflow-sessions
 *
 * Terminal sessions dropdown — main sessions from /terminal/sessions (title + UUID).
 *
 * T-516 — 워크플로우 탭 동기화 책임은 본 모듈에서 제거됨. 클라이언트 측 단일
 * 출처는 localStorage (Board.workflowTabStorage) — terminal.js init 의 render
 * 흐름 + kanban.js 의 LAUNCH_STARTED add 가 라이프사이클을 담당한다. 닫기
 * 버튼만이 유일한 종결 트리거.
 *
 * Depends on: common.js (Board namespace), session.js (Board.session)
 * Registers:  Board.workflowSessions
 */
"use strict";

(function () {

  /**
   * Purges a stopped workflow session (removes metadata + disk file).
   * @param {string} sid - session ID
   * @returns {Promise}
   */
  function purgeSession(sid) {
    return fetch("/terminal/workflow/kill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sid, purge: true }),
    }).then(function () { refresh(); });
  }

  /**
   * Formats a UTC ISO timestamp to "HH:mm" for display.
   */
  function formatHm(iso) {
    if (!iso) return "";
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return "";
      var hh = String(d.getHours()).padStart(2, "0");
      var mm = String(d.getMinutes()).padStart(2, "0");
      return hh + ":" + mm;
    } catch (_e) { return ""; }
  }

  function formatSize(bytes) {
    if (typeof bytes !== "number" || bytes < 0) return "";
    if (bytes < 1024) return bytes + "B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + "KB";
    return (bytes / (1024 * 1024)).toFixed(1) + "MB";
  }

  /**
   * Fetches main sessions from /terminal/sessions and renders them into the dropdown.
   */
  function renderMainSessionsDropdown() {
    var dropdown = document.getElementById("terminal-sessions-dropdown");
    if (!dropdown) return;

    fetch("/terminal/sessions", { cache: "no-store" }).then(function (r) {
      return r.json();
    }).then(function (sessions) {
      sessions = Array.isArray(sessions) ? sessions : [];

      // count 뱃지는 메인 세션 드롭다운에선 사용하지 않음 → 숨김
      var countEl = document.getElementById("terminal-sessions-count");
      if (countEl) countEl.style.display = "none";

      var esc = (Board._term && Board._term.escapeHtml) || function (s) {
        return String(s == null ? "" : s)
          .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
      };

      var h = "";
      if (sessions.length === 0) {
        h += '<div class="terminal-sessions-empty">세션 없음</div>';
        dropdown.innerHTML = h;
        return;
      }

      h += '<div class="terminal-sessions-header">Main Sessions (' + sessions.length + ')</div>';
      sessions.forEach(function (s) {
        var sid = s.session_id || "";
        var shortId = sid.substring(0, 8);
        var time = formatHm(s.last_active);
        var title = s.title || shortId;
        var branch = s.branch || "";
        var size = formatSize(s.size_bytes);
        var isCurrent = !!s.is_current;
        var isLast = !!s.is_last;
        var rowAttrs = 'data-main-session="1"';
        if (isCurrent) rowAttrs += ' data-current="1"';
        if (isLast) rowAttrs += ' data-last="1"';
        h += '<div class="terminal-sessions-row" ' + rowAttrs + '>';
        h += '<button class="terminal-sessions-item" data-resume-sid="' + esc(sid) + '" title="' + esc(sid) + '">';
        if (isLast && !isCurrent) {
          h += '<span class="terminal-sessions-item-badge">last</span>';
        }
        h += '<div class="terminal-sessions-item-body">';
        h += '<span class="terminal-sessions-item-label">' + esc(title) + '</span>';
        var metaParts = [];
        if (time) metaParts.push(esc(time));
        if (branch) metaParts.push(esc(branch));
        if (size) metaParts.push(esc(size));
        metaParts.push(esc(shortId));
        h += '<span class="terminal-sessions-item-meta">' + metaParts.join(' · ') + '</span>';
        h += '</div>';
        h += '</button>';
        h += '</div>';
      });
      dropdown.innerHTML = h;

      // Wire resume buttons: 세션 클릭 → 해당 UUID로 resume 시도
      dropdown.querySelectorAll("[data-resume-sid]").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          var sid = btn.getAttribute("data-resume-sid");
          if (!sid) return;
          dropdown.classList.remove("visible");
          if (Board.session && Board.session.startSession) {
            Board.session.startSession(sid);
          }
        });
      });
    }).catch(function () {
      dropdown.innerHTML = '<div class="terminal-sessions-empty">세션 목록 로드 실패</div>';
    });
  }

  /**
   * Main sessions dropdown refresh.
   *
   * T-516 — 워크플로우 탭 sync 분기는 폐기. 본 함수는 드롭다운 갱신만 담당.
   * 매개변수는 callsite 시그니처 호환 유지용 (호출자 수정 회피).
   *
   * @param {string|null} _currentWorkflowSessionId - 미사용 (호환 유지)
   * @param {boolean} _isWorkflowMode - 미사용 (호환 유지)
   */
  function refresh(_currentWorkflowSessionId, _isWorkflowMode) {
    renderMainSessionsDropdown();
  }

  // ── Register on Board namespace ──
  Board.workflowSessions = {
    refresh: refresh,
    renderDropdown: renderMainSessionsDropdown,
    purge: purgeSession,
  };
})();
