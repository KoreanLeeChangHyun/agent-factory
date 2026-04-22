/**
 * @module workflow-sessions
 *
 * Workflow sessions list UI for the terminal sessions dropdown.
 *
 * Provides purgeSession, purgeAllStopped, and refreshWorkflowSessions.
 *
 * Depends on: common.js (Board namespace)
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
    }).then(function () { refreshWorkflowSessions(); });
  }

  /**
   * Purges all stopped sessions in the current list.
   */
  function purgeAllStopped() {
    fetch("/terminal/workflow/list", { cache: "no-store" }).then(function (r) {
      return r.json();
    }).then(function (sessions) {
      var stopped = (sessions || []).filter(function (s) { return s.status === "stopped"; });
      return Promise.all(stopped.map(function (s) { return purgeSession(s.session_id); }));
    }).catch(function () {});
  }

  /**
   * Fetches the active workflow sessions and updates the dropdown + count + tab bar.
   * @param {string|null} currentWorkflowSessionId - current workflow session ID (may be excluded or used for tab sync)
   * @param {boolean} isWorkflowMode - whether in workflow mode
   */
  function refreshWorkflowSessions(currentWorkflowSessionId, isWorkflowMode) {
    fetch("/terminal/workflow/list", { cache: "no-store" }).then(function (r) {
      return r.json();
    }).then(function (sessions) {
      sessions = Array.isArray(sessions) ? sessions : [];

      var running = sessions.filter(function (s) { return s.status === "running"; });
      var stopped = sessions.filter(function (s) { return s.status !== "running"; });

      var byDateDesc = function (a, b) { return (b.created_at || "").localeCompare(a.created_at || ""); };
      running.sort(byDateDesc);
      stopped.sort(byDateDesc);

      var countEl = document.getElementById("terminal-sessions-count");
      var dropdown = document.getElementById("terminal-sessions-dropdown");
      if (countEl) {
        if (running.length > 0) {
          countEl.textContent = running.length;
          countEl.style.display = "";
        } else {
          countEl.style.display = "none";
        }
      }

      // ── 탭 바 동기화 ──
      // running 세션이 탭 바에 없으면 추가, stopped+purge 세션은 탭 바에서 제거
      if (Board.sessionSwitcher) {
        var sessionList = Board.sessionSwitcher.getSessionList ? Board.sessionSwitcher.getSessionList() : [];
        var tabSessionIds = sessionList.map(function (e) { return e.id; });

        // running 세션 → 탭 바에 없으면 추가 (내부 맵에도 등록)
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

        // stopped 세션 → 탭 바에서 제거 (단, 현재 활성 탭은 제거하지 않음)
        stopped.forEach(function (s) {
          if (s.session_id === "main") return;
          var currentActive = Board.sessionSwitcher.getCurrentSession ? Board.sessionSwitcher.getCurrentSession() : null;
          if (s.session_id === currentActive) {
            // 현재 활성 탭이 stopped 상태 → 상태 점만 업데이트
            if (Board.sessionSwitcher.setTabStatus) {
              Board.sessionSwitcher.setTabStatus(s.session_id, "stopped");
            }
          } else {
            // 비활성 stopped 탭 제거
            if (Board.sessionSwitcher.removeTab) {
              Board.sessionSwitcher.removeTab(s.session_id);
            }
            if (Board.sessionSwitcher.removeSession) {
              Board.sessionSwitcher.removeSession(s.session_id);
            }
          }
        });
      }

      if (!dropdown) return;

      var renderRow = function (s) {
        var time = (s.created_at || "").slice(11, 16);
        var html = '';
        html += '<div class="terminal-sessions-row" data-status="' + (s.status || "") + '">';
        // 세션 클릭: 페이지 이동 대신 switchSession() 호출로 탭 추가 + 전환
        html += '<button class="terminal-sessions-item" data-switch-sid="' + s.session_id + '">';
        html += '<span class="terminal-sessions-item-ticket">' + (s.ticket_id || "") + '</span>';
        html += '<span class="terminal-sessions-item-label">' + (s.command || "") + '</span>';
        html += '<span class="terminal-sessions-item-time">' + time + '</span>';
        html += '<span class="terminal-sessions-item-status" data-status="' + (s.status || "") + '">' + (s.status || "") + '</span>';
        html += '</button>';
        if (s.status !== "running") {
          html += '<button class="terminal-sessions-purge" data-sid="' + s.session_id + '" title="Remove">x</button>';
        }
        html += '</div>';
        return html;
      };

      var h = "";
      if (isWorkflowMode) {
        // 워크플로우 모드: Main 세션 전환 버튼
        h += '<button class="terminal-sessions-item terminal-sessions-main" data-switch-sid="main">';
        h += '<span class="terminal-sessions-item-label">\u21A9 Main session</span>';
        h += '</button>';
        h += '<div class="terminal-sessions-divider"></div>';
      }

      if (running.length > 0) {
        h += '<div class="terminal-sessions-header">Running (' + running.length + ')</div>';
        running.forEach(function (s) { h += renderRow(s); });
      }
      if (stopped.length > 0) {
        if (running.length > 0) h += '<div class="terminal-sessions-divider"></div>';
        h += '<div class="terminal-sessions-header">Stopped (' + stopped.length + ') <button class="terminal-sessions-clear-all" id="terminal-sessions-clear-all">Clear all</button></div>';
        stopped.forEach(function (s) { h += renderRow(s); });
      }
      if (running.length === 0 && stopped.length === 0 && !isWorkflowMode) {
        h += '<div class="terminal-sessions-empty">No workflow sessions</div>';
      }
      dropdown.innerHTML = h;

      // Wire session switch buttons (드롭다운 세션 클릭 → switchSession 호출)
      dropdown.querySelectorAll("[data-switch-sid]").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          var sid = btn.getAttribute("data-switch-sid");
          if (!sid) return;

          // 탭 바에 추가 (없으면)
          if (sid !== "main" && Board.sessionSwitcher && Board.sessionSwitcher.addTab) {
            var rowEl = btn.closest(".terminal-sessions-row");
            var ticketEl = btn.querySelector(".terminal-sessions-item-ticket");
            var label = ticketEl ? (ticketEl.textContent || sid) : sid;
            var statusEl = btn.querySelector(".terminal-sessions-item-status");
            var status = statusEl ? (statusEl.textContent || "running") : "running";
            Board.sessionSwitcher.addTab(sid, label, status);
            if (Board.sessionSwitcher.addSession) {
              Board.sessionSwitcher.addSession(sid, { status: status });
            }
          }

          // 세션 전환
          if (Board.sessionSwitcher && Board.sessionSwitcher.switchSession) {
            Board.sessionSwitcher.switchSession(sid);
          }

          // 드롭다운 닫기
          dropdown.classList.remove("visible");
        });
      });

      // Wire purge buttons
      dropdown.querySelectorAll(".terminal-sessions-purge").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          purgeSession(btn.getAttribute("data-sid"));
        });
      });
      var clearAll = document.getElementById("terminal-sessions-clear-all");
      if (clearAll) {
        clearAll.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          if (confirm("Remove all " + stopped.length + " stopped session(s)?")) {
            purgeAllStopped();
          }
        });
      }
    }).catch(function () {});
  }

  // ── Register on Board namespace ──
  Board.workflowSessions = {
    refresh: refreshWorkflowSessions,
    purge: purgeSession,
    purgeAllStopped: purgeAllStopped
  };
})();
