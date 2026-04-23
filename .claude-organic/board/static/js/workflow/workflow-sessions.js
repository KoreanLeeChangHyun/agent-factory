/**
 * @module workflow-sessions
 *
 * Terminal sessions dropdown + workflow tab bar synchronization.
 *
 * - Tab bar: synced with /terminal/workflow/list (running/stopped workflow sessions)
 * - Dropdown content: main sessions from /terminal/sessions (title + UUID)
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
   * Syncs the session tab bar with /terminal/workflow/list.
   * Running sessions appear as tabs; stopped sessions are removed (except the active tab).
   * @param {string|null} currentWorkflowSessionId - current workflow session ID
   * @param {boolean} isWorkflowMode - whether in workflow mode
   */
  function syncWorkflowTabs(currentWorkflowSessionId, isWorkflowMode) {
    fetch("/terminal/workflow/list", { cache: "no-store" }).then(function (r) {
      return r.json();
    }).then(function (sessions) {
      sessions = Array.isArray(sessions) ? sessions : [];

      var running = sessions.filter(function (s) { return s.status === "running"; });
      var stopped = sessions.filter(function (s) { return s.status !== "running"; });

      if (!Board.sessionSwitcher) return;

      // running 세션 → 탭 바에 없으면 추가
      running.forEach(function (s) {
        if (s.session_id === "main") return;
        if (Board.sessionSwitcher.addSession) {
          Board.sessionSwitcher.addSession(s.session_id, { status: "running" });
        }
        if (Board.sessionSwitcher.addTab) {
          var label = (s.ticket_id || s.session_id).replace(/^wf-/, "");
          Board.sessionSwitcher.addTab(s.session_id, label, "running");
        }
        if (Board.sessionSwitcher.setTabStatus) {
          Board.sessionSwitcher.setTabStatus(s.session_id, "running");
        }
      });

      // stopped 세션 → 비활성 탭은 제거, 활성 탭은 상태만 업데이트
      stopped.forEach(function (s) {
        if (s.session_id === "main") return;
        var currentActive = Board.sessionSwitcher.getCurrentSession
          ? Board.sessionSwitcher.getCurrentSession()
          : null;
        if (s.session_id === currentActive) {
          if (Board.sessionSwitcher.setTabStatus) {
            Board.sessionSwitcher.setTabStatus(s.session_id, "stopped");
          }
        } else {
          if (Board.sessionSwitcher.removeTab) {
            Board.sessionSwitcher.removeTab(s.session_id);
          }
          if (Board.sessionSwitcher.removeSession) {
            Board.sessionSwitcher.removeSession(s.session_id);
          }
        }
      });
    }).catch(function () {});
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
        h += '<span class="terminal-sessions-item-label">' + esc(title) + '</span>';
        h += '<span class="terminal-sessions-item-sub">' + esc(shortId) + '</span>';
        h += '<span class="terminal-sessions-item-time">' + esc(time) + '</span>';
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
   * Combined refresh: sync workflow tabs + render main sessions in dropdown.
   * Maintains the original Board.workflowSessions.refresh() callsite signature.
   */
  function refresh(currentWorkflowSessionId, isWorkflowMode) {
    syncWorkflowTabs(currentWorkflowSessionId, isWorkflowMode);
    renderMainSessionsDropdown();
  }

  // ── Register on Board namespace ──
  Board.workflowSessions = {
    refresh: refresh,
    syncTabs: syncWorkflowTabs,
    renderDropdown: renderMainSessionsDropdown,
    purge: purgeSession,
  };
})();
