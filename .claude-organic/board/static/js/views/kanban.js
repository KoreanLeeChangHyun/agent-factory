/**
 * @module kanban
 *
 * Board SPA kanban tab module.
 *
 * Handles ticket fetching, sorting, and kanban board rendering with
 * per-column sort dropdowns. Registers fetchTickets, fetchTicketsByFiles
 * on Board.fetch and renderKanban on Board.render.
 *
 * Depends on: common.js (Board.util, Board.state)
 */
"use strict";

(function () {
  const { esc, badge, fetchXmlList, parseTicket, CMD_COLORS, COLUMNS, KANBAN_SORT_LS_KEY } = Board.util;

  // ── Column Collapsed State (Done / To Do) ──
  // 컬럼 키별로 접힘 상태를 독립 저장한다. "Done"은 기존 키를 유지해 사용자 설정
  // 호환성을 보장하고, 그 외 컬럼(현재 "To Do")은 column-collapsed:<key> 형식.
  const LEGACY_DONE_LS_KEY = "claude-board-done-collapsed";
  const COLLAPSIBLE_COLUMNS = new Set(["Done", "To Do"]);

  function columnCollapsedKey(colKey) {
    if (colKey === "Done") return LEGACY_DONE_LS_KEY;
    return "claude-board-column-collapsed:" + colKey;
  }

  /** Loads a column's collapsed state from localStorage. Default: false (expanded). */
  function loadColumnCollapsed(colKey) {
    try {
      const stored = localStorage.getItem(columnCollapsedKey(colKey));
      if (stored !== null) return stored === "true";
    } catch (e) {}
    return false;
  }

  /** Persists a column's collapsed state to localStorage. */
  function saveColumnCollapsed(colKey, collapsed) {
    try {
      localStorage.setItem(columnCollapsedKey(colKey), String(collapsed));
    } catch (e) {}
  }

  // ── To Do Manual Order ──
  // To Do 컬럼은 사용자 수동 정렬 (DnD 위치 변경) 지원. 신규 티켓은 항상 최상단 prepend.
  // 다른 브라우저/기기에서는 동기화되지 않음 (localStorage 한정).
  const TODO_MANUAL_ORDER_LS_KEY = "kanban_todo_manual_order_v1";

  function loadTodoManualOrder() {
    try {
      const stored = JSON.parse(localStorage.getItem(TODO_MANUAL_ORDER_LS_KEY));
      if (Array.isArray(stored)) return stored;
    } catch (e) {}
    return [];
  }

  function saveTodoManualOrder(order) {
    try {
      localStorage.setItem(TODO_MANUAL_ORDER_LS_KEY, JSON.stringify(order));
    } catch (e) {}
  }

  /**
   * 수동 정렬 적용:
   * - 저장 순서 안의 티켓 = 그 순서대로
   * - 저장 순서에 없는 티켓 (신규) = 최상단 prepend, 번호 desc 순
   * - 결과 순서를 다시 저장 (신규 항목이 manual order 에 자동 등록되며 stale 정리)
   */
  function applyTodoManualOrder(items) {
    const stored = loadTodoManualOrder();
    const indexMap = new Map();
    stored.forEach(function (num, idx) { indexMap.set(num, idx); });

    const known = [];
    const unknown = [];
    items.forEach(function (t) {
      if (indexMap.has(t.number)) known.push(t);
      else unknown.push(t);
    });

    known.sort(function (a, b) {
      return indexMap.get(a.number) - indexMap.get(b.number);
    });
    unknown.sort(function (a, b) {
      return (b.number || "").localeCompare(a.number || "");
    });

    const result = unknown.concat(known);
    const newOrder = result.map(function (t) { return t.number; });
    const changed = (newOrder.length !== stored.length)
      || newOrder.some(function (n, i) { return n !== stored[i]; });
    if (changed) saveTodoManualOrder(newOrder);
    return result;
  }

  /** 특정 티켓을 manual order 의 targetIndex 위치로 이동. */
  function reorderTodoManualOrder(ticketNum, targetIndex) {
    const stored = loadTodoManualOrder();
    const filtered = stored.filter(function (n) { return n !== ticketNum; });
    const clamped = Math.max(0, Math.min(targetIndex, filtered.length));
    filtered.splice(clamped, 0, ticketNum);
    saveTodoManualOrder(filtered);
  }

  // ── Kanban Sort State ──

  /** Loads persisted kanban sort state from localStorage. */
  function loadKanbanSort() {
    const defaults = {};
    COLUMNS.forEach(function (col) {
      // To Do 는 수동 정렬이 기본값. 나머지는 번호 오름차순.
      if (col.key === "To Do") {
        defaults[col.key] = { key: "manual", dir: "asc" };
      } else {
        defaults[col.key] = { key: "number", dir: "asc" };
      }
    });
    try {
      const stored = JSON.parse(localStorage.getItem(KANBAN_SORT_LS_KEY));
      if (stored && typeof stored === "object") {
        COLUMNS.forEach(function (col) {
          if (!stored[col.key] || !stored[col.key].key) {
            stored[col.key] = defaults[col.key];
          }
        });
        return stored;
      }
    } catch (e) {}
    return defaults;
  }

  const kanbanSort = loadKanbanSort();
  Board.state.kanbanSort = kanbanSort;

  /** Persists kanban sort state to localStorage. */
  function saveKanbanSort() {
    try {
      localStorage.setItem(KANBAN_SORT_LS_KEY, JSON.stringify(kanbanSort));
    } catch (e) {}
  }

  // ── Kanban Sort Logic ──

  /**
   * Returns the most recent datetime from a ticket's datetime field.
   * @param {Object} t - Ticket object
   * @returns {string} Most recent datetime string
   */
  function getModifiedDate(t) {
    const candidates = [];
    if (candidates.length === 0) return t.updated || t.created || "";
    return candidates.reduce(function (a, b) {
      return a > b ? a : b;
    });
  }

  /**
   * Sorts ticket array by the given key and direction.
   * @param {Array} items - Ticket array
   * @param {string} sortKey - Sort key (number, created, modified, title)
   * @param {string} sortDir - Sort direction (asc, desc)
   * @returns {Array} Sorted copy of the ticket array
   */
  function sortTickets(items, sortKey, sortDir) {
    const dir = sortDir === "desc" ? -1 : 1;
    return items.slice().sort(function (a, b) {
      let av, bv, cmp;
      if (sortKey === "number") {
        av = a.number || "";
        bv = b.number || "";
        cmp = av.localeCompare(bv);
      } else if (sortKey === "created") {
        av = a.created || "";
        bv = b.created || "";
        cmp = av.localeCompare(bv);
      } else if (sortKey === "modified") {
        av = getModifiedDate(a);
        bv = getModifiedDate(b);
        cmp = av.localeCompare(bv);
      } else if (sortKey === "title") {
        av = a.title || "";
        bv = b.title || "";
        cmp = av.localeCompare(bv, "ko");
      } else {
        cmp = 0;
      }
      return dir * cmp;
    });
  }

  // ── Inline SVG Icons for sort direction ──
  const SVG_ASC = '<svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M5 2L9 8H1L5 2Z"/></svg>';
  const SVG_DESC = '<svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M5 8L1 2H9L5 8Z"/></svg>';

  // ── Sort Options ──
  const SORT_KEYS = [
    { key: "number",   label: "\uBC88\uD638" },
    { key: "created",  label: "\uC0DD\uC131\uC77C" },
    { key: "modified", label: "\uC218\uC815\uC77C" },
    { key: "title",    label: "\uC81C\uBAA9" },
  ];
  const SORT_DIRS = [
    { dir: "asc",  label: "\uC624\uB984\uCC28\uC21C" },
    { dir: "desc", label: "\uB0B4\uB9BC\uCC28\uC21C" },
  ];

  // ── Fetch Tickets ──

  // ── Worktree Uncommitted Cache ──
  // 카드 우상단 미커밋 인디케이터용. null = not loaded (graceful: 인디케이터 omit).
  var _worktreeUncommittedMap = null;

  // ── Done Verdict Cache (T-441) ──
  // Done 카드 머지 정합성 verdict. key=ticket number, value={verdict,reason,details}.
  // "pending" 값 = 조회 중. undefined = 미조회.
  var _doneVerdictMap = {};

  // ── Active Branch Ticket (T-433 Phase 2) ──
  // 메인 working tree 가 현재 활성화한 feature 브랜치의 ticket 번호 (예: "T-433"). null = develop.
  // SSOT: backend GET /api/kanban/branch/active 또는 SSE git_branch 이벤트에서 derive.
  // 한 카드만 active 보장: render 시 모든 Review 카드를 비교해 매칭만 .active 부여.
  var _activeBranchTicket = null;
  // 첫 1회 fetch 완료 가드 — 페이지 로드 시 1회 GET 으로 초기 시각 복원.
  var _activeBranchFetched = false;
  // T-NNN 추출 정규식 — feat/T-NNN-* 패턴 매칭.
  var _FEAT_BRANCH_RE = /^feat\/(T-\d+)/;

  /**
   * 페이지 로드 시 1회 호출되어 _activeBranchTicket 을 초기화한다.
   * 응답 도착 시 카드 시각만 .active 토글 (전체 re-render 회피 — DOM 직접 패치).
   */
  function fetchAndApplyActiveBranch() {
    if (_activeBranchFetched) return;
    _activeBranchFetched = true;
    fetch("/api/kanban/branch/active", { cache: "no-store" }).then(function (res) {
      if (!res.ok) return null;
      return res.json();
    }).then(function (data) {
      var ticket = (data && data.active_ticket) || null;
      _activeBranchTicket = ticket;
      applyActiveBranchClassToCards();
    }).catch(function () {
      // backend not ready — _activeBranchTicket 은 null 유지 (시각 OFF)
    });
  }

  /**
   * 현재 _activeBranchTicket 값에 맞춰 모든 Review 카드의 .has-active-branch /
   * 토글 버튼 .active 클래스를 동기화 한다 (전체 re-render 없이 DOM 직접 패치).
   * - SSE git_branch 이벤트 도착 후 호출
   * - 토글 클릭 optimistic update 직후 호출
   */
  function applyActiveBranchClassToCards() {
    var cards = document.querySelectorAll('.card[data-col-key="Review"]');
    cards.forEach(function (card) {
      var num = card.dataset.num;
      var btn = card.querySelector(".card-branch-toggle");
      var isActive = (num && _activeBranchTicket === num);
      if (isActive) {
        card.classList.add("has-active-branch");
        if (btn) btn.classList.add("active");
      } else {
        card.classList.remove("has-active-branch");
        if (btn) btn.classList.remove("active");
      }
    });
  }

  /**
   * SSE git_branch 이벤트 도착 시 외부에서 호출 (sse.js).
   * branch 문자열에서 T-NNN 을 추출해 _activeBranchTicket 업데이트 + DOM 패치.
   * @param {string|null} branch - "feat/T-NNN-..." 또는 "develop" 등
   */
  function syncActiveBranchFromSSE(branch) {
    var ticket = null;
    if (branch && typeof branch === "string") {
      var m = _FEAT_BRANCH_RE.exec(branch);
      if (m) ticket = m[1];
    }
    if (ticket === _activeBranchTicket) return; // 변동 없음 — skip
    _activeBranchTicket = ticket;
    applyActiveBranchClassToCards();
  }

  /**
   * Review 카드 4행 토글 버튼 클릭 핸들러.
   * - 현재 카드가 active 면 action=off, 아니면 action=on 으로 POST.
   * - dirty / needs_restart / 실패 응답에 따라 안내 모달 발동 (자동 stash 절대 X).
   * @param {string} ticketNum - 클릭된 카드의 T-NNN
   */
  function handleBranchToggleClick(ticketNum) {
    if (!ticketNum) return;
    var action = (_activeBranchTicket === ticketNum) ? "off" : "on";
    fetch("/api/kanban/branch/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket_number: ticketNum, action: action })
    }).then(function (res) {
      return res.json().then(function (body) { return { ok: res.ok, body: body }; });
    }).then(function (r) {
      var body = r.body || {};
      if (body.ok === true) {
        // 성공 — active_ticket 갱신 (서버 응답이 SSOT, optimistic 도 동시 반영)
        _activeBranchTicket = body.active_ticket || null;
        applyActiveBranchClassToCards();
        if (body.needs_restart) {
          alert(
            "[브랜치 활성 — backend 변경 감지]\n\n" +
            "이 feature 브랜치는 board/server/** 변경을 포함합니다.\n" +
            "board 서버를 재기동해야 변경된 backend 가 정상 동작합니다.\n\n" +
            "수동으로 board 서버를 재기동한 뒤 페이지를 새로고침하세요.\n" +
            "(frontend 정적 파일은 자동 갱신 — hard reload 만 수행하면 충분)"
          );
        }
        return;
      }
      // 실패 — reason 별 분기
      var reason = body.reason || "";
      if (reason === "dirty") {
        var files = (body.files || []).slice(0, 20);
        var fileList = files.map(function (f) { return "  - " + f; }).join("\n");
        var more = (body.files && body.files.length > 20) ? "\n  ... (" + (body.files.length - 20) + "개 더)" : "";
        var msg = body.modal_message ||
          ("메인 working tree 에 미커밋 변경이 있습니다.\n" +
           "수동으로 commit / stash / reset 후 다시 시도하세요.");
        alert("[브랜치 토글 차단 — dirty]\n\n" + msg + "\n\n변경 파일:\n" + fileList + more);
        return;
      }
      if (reason === "feature_branch_not_found") {
        alert("[브랜치 토글 실패]\n\n" + (body.message || "feature 브랜치를 찾을 수 없습니다."));
        return;
      }
      if (reason === "git_switch_failed") {
        alert("[git switch 실패]\n\n" + (body.message || "git switch 가 실패했습니다."));
        return;
      }
      // 기타 알 수 없는 실패
      alert("[브랜치 토글 실패]\n\n" + (body.message || JSON.stringify(body)));
    }).catch(function (err) {
      alert("[브랜치 토글 요청 실패]\n\n" + (err && err.message ? err.message : err));
    });
  }

  /**
   * Fetches /api/worktree/uncommitted/all and populates _worktreeUncommittedMap.
   * Silently degrades on error (map remains null or stale).
   */
  function fetchAndCacheWorktreeUncommitted() {
    return fetch("/api/worktree/uncommitted/all", { cache: "no-store" }).then(function (res) {
      if (!res.ok) return;
      return res.json().then(function (list) {
        if (!Array.isArray(list)) return;
        var map = new Map();
        list.forEach(function (item) {
          if (item && item.ticket && item.uncommitted_count > 0) {
            map.set(item.ticket, item);
          }
        });
        _worktreeUncommittedMap = map;
      });
    }).catch(function () {
      // worktree mode off / API error — leave map unchanged
    });
  }

  /**
   * T-441: 단일 Done 카드 verdict 조회 (advisory).
   * 결과를 _doneVerdictMap 에 캐시하고, 로드 완료 시 해당 카드 배지를 DOM 에 패치.
   * 폴링 없음 — 카드 mount 시 1회 호출.
   * @param {string} ticketNum - 티켓 번호 (예: "T-441")
   */
  function fetchAndRenderVerdict(ticketNum) {
    // 이미 조회 중이거나 완료된 경우 건너뜀
    if (_doneVerdictMap[ticketNum] !== undefined) return;
    _doneVerdictMap[ticketNum] = "pending";

    fetch("/api/kanban/done-verdict?ticket=" + encodeURIComponent(ticketNum), { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        _doneVerdictMap[ticketNum] = data;
        // DOM 패치: 해당 카드의 verdict 배지 교체 (전체 re-render 없이)
        var badge = document.querySelector(
          '.card[data-num="' + ticketNum + '"][data-col-key="Done"] .card-done-verdict'
        );
        if (badge) {
          var newBadge = document.createElement("span");
          _applyVerdictBadge(newBadge, data);
          badge.parentNode.replaceChild(newBadge, badge);
        }
      })
      .catch(function () {
        _doneVerdictMap[ticketNum] = { verdict: "UNKNOWN", reason: "fetch_error", details: { message: "verdict 조회 실패" } };
      });
  }

  /**
   * T-441: verdict 데이터를 기반으로 badge span 에 상태를 적용한다.
   * @param {HTMLElement} el - 대상 span 요소
   * @param {Object} data - verdict 응답 데이터 ({verdict, reason, details})
   */
  function _applyVerdictBadge(el, data) {
    var verdict = data && data.verdict;
    el.className = "card-done-verdict";
    if (verdict === "OK") {
      el.className += " verdict-ok";
      el.title = "머지 정합성 확인 (develop HEAD == merge commit)";
      el.innerHTML = '<svg width="11" height="11" viewBox="0 0 11 11" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><polyline points="1.5,5.5 4.5,8.5 9.5,2.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>';
    } else if (verdict === "FAIL") {
      var msg = (data.details && data.details.message) || "develop HEAD 가 머지 commit 아님";
      el.className += " verdict-fail";
      el.title = "머지 불일치 — " + msg + " (클릭하면 상세 확인)";
      el.setAttribute("data-verdict-msg", msg);
      el.innerHTML = '<svg width="11" height="11" viewBox="0 0 11 11" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><line x1="2" y1="2" x2="9" y2="9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="9" y1="2" x2="2" y2="9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
    } else {
      // UNKNOWN / SKIP / pending — 배지 숨김 (공간 낭비 없음)
      el.className += " verdict-unknown";
      el.style.display = "none";
    }
  }

  /** Fetches all tickets via /api/kanban (single request). */
  function fetchTickets() {
    return fetch("/api/kanban", { cache: "no-store" }).then(function (res) {
      if (!res.ok) return [];
      return res.json();
    }).then(function (map) {
      var tickets = [];
      Object.keys(map).forEach(function (fn) {
        if (map[fn]) {
          var t = parseTicket(map[fn]);
          if (t) tickets.push(t);
        }
      });
      return tickets;
    }).catch(function () { return []; }).then(function (tickets) {
      // Co-fetch worktree uncommitted so renderKanban always has fresh data.
      return fetchAndCacheWorktreeUncommitted().then(
        function () { return tickets; },
        function () { return tickets; }
      );
    });
  }

  /**
   * Selectively fetches and updates tickets by file names via /api/kanban?files=...
   * @param {string[]} files - Changed file names (e.g. ["T-038.xml"])
   * @returns {Promise<void>}
   */
  function fetchTicketsByFiles(files) {
    return fetch("/api/kanban?files=" + encodeURIComponent(files.join(",")), { cache: "no-store" }).then(function (res) {
      if (!res.ok) return;
      return res.json().then(function (map) {
        Object.keys(map).forEach(function (fn) {
          var baseName = fn.replace(/\.xml$/, "");
          if (map[fn] === null) {
            Board.state.TICKETS = Board.state.TICKETS.filter(function (t) { return t.number !== baseName; });
          } else {
            var incoming = parseTicket(map[fn]);
            if (!incoming) return;
            var idx = Board.state.TICKETS.findIndex(function (t) { return t.number === incoming.number; });
            if (idx !== -1) {
              Board.state.TICKETS[idx] = incoming;
            } else {
              Board.state.TICKETS.push(incoming);
            }
          }
        });
      });
    }).catch(function () {});
  }

  // ── Kanban Rendering ──

  /**
   * 스테이지 이름을 3글자 약어로 변환한다.
   * @param {string} stage - 스테이지 이름 (예: "research", "implement", "review")
   * @returns {string} 3글자 약어 (예: "res", "imp", "rev")
   */
  function stageAbbr(stage) {
    var abbr = Board.util.CMD_ABBR;
    var s = stage.trim().toLowerCase();
    return abbr[s] || s.slice(0, 3).toUpperCase();
  }

  /**
   * 체인 커맨드 티켓의 스테이지 아이콘 HTML을 생성한다.
   * @param {Object} ticket - 티켓 객체
   * @returns {string} card-chain div HTML
   */
  function renderChainIcons(ticket) {
    const stages = ticket.command.split(">").map(function (s) { return s.trim(); }).filter(Boolean);
    if (stages.length === 0) return "";

    const isDone = ticket.status === "Done";
    const isInProgress = ticket.status === "In Progress";

    let parts = [];
    stages.forEach(function (stage, idx) {
      let stateClass;
      if (isDone) {
        stateClass = "done";
      } else if (isInProgress && idx === 0) {
        stateClass = "active";
      } else {
        stateClass = "waiting";
      }
      if (idx > 0) {
        parts.push('<span class="chain-sep">\u203A</span>');
      }
      var colors = CMD_COLORS[stage.trim()] || { bg: "rgba(160,160,160,0.2)", fg: "#888" };
      var anim = stateClass === "active" ? "animation:chain-pulse 1.5s ease-in-out infinite;" : "";
      parts.push('<span class="chain-stage ' + stateClass + '" style="background:' + colors.bg + ';color:' + colors.fg + ';' + anim + '">' + stageAbbr(stage) + "</span>");
    });

    return '<div class="card-chain">' + parts.join("") + "</div>";
  }

  /**
   * 관계 링크 HTML을 생성한다.
   * @param {Object} ticket - 티켓 객체
   * @returns {string} card-relations div HTML
   */
  function renderRelations(ticket) {
    if (!ticket.relations || ticket.relations.length === 0) return "";

    const typeMap = {
      "derived-from": { prefix: "\u2190", cssClass: "rel-derived" },   // ←
      "depends-on":   { prefix: "\u21D0", cssClass: "rel-depends" },   // ⇐
      "blocks":       { prefix: "\u2192", cssClass: "rel-blocks" },    // →
    };

    let parts = [];
    ticket.relations.forEach(function (rel) {
      const info = typeMap[rel.type] || { prefix: "\u2194", cssClass: "rel-other" };
      const numStr = rel.ticket ? rel.ticket.replace(/^T-/, "") : "?";
      parts.push('<span class="rel-item ' + info.cssClass + '">' + info.prefix + numStr + "</span>");
    });

    return '<div class="card-relations">' + parts.join("") + "</div>";
  }

  /**
   * T-457 (Layer 3): 4행 commit 버튼 클릭 시 워크트리 자동 commit 트리거.
   * 기존 handleUncommittedBadgeClick 의 fetch 로직을 그대로 유지하고,
   * DOM 조작 대상만 1행 badge → 4행 button 으로 이전.
   * @param {HTMLButtonElement} btn - .card-commit-action 요소
   */
  function handleCommitButtonClick(btn) {
    var ticket = btn.dataset.commitTicket;
    if (!ticket || btn.classList.contains("is-commiting")) return;
    btn.classList.add("is-commiting");
    btn.disabled = true;
    fetch("/api/kanban/worktree-commit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket: ticket }),
    }).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, data: data };
      });
    }).then(function (r) {
      if (r.ok && r.data && r.data.ok) {
        // 성공 — 카드 갱신 (commit 버튼 + 1행 badge 둘 다 사라짐 기대)
        if (_worktreeUncommittedMap) _worktreeUncommittedMap.delete(ticket);
        Board.render.renderKanban();
      } else {
        var msg = (r.data && r.data.error) || "commit 실패";
        btn.classList.remove("is-commiting");
        btn.disabled = false;
        alert(ticket + " commit 실패: " + msg);
      }
    }).catch(function (err) {
      btn.classList.remove("is-commiting");
      btn.disabled = false;
      alert(ticket + " commit 요청 실패: " + (err && err.message ? err.message : err));
    });
  }

  /**
   * 카드 우상단 미커밋 인디케이터 HTML 을 생성한다.
   * 워크플로우 회귀(워커 commit 누락) 시 사용자가 클릭으로 즉시 commit.
   * @param {string} ticketNum - 티켓 번호 (예: "T-422")
   * @returns {string} span.card-uncommitted-badge HTML 또는 빈 문자열
   */
  function renderUncommittedBadge(ticketNum) {
    if (!_worktreeUncommittedMap) return "";
    var item = _worktreeUncommittedMap.get(ticketNum);
    if (!item || item.uncommitted_count <= 0) return "";
    var label = item.uncommitted_count + "M";
    var tooltip = "미커밋 " + item.uncommitted_count + "건 — 클릭하면 자동 commit"; // "미커밋 N건 — 클릭하면 자동 commit"
    return '<span class="card-uncommitted-badge" data-uncommitted-ticket="' + esc(ticketNum) + '" title="' + esc(tooltip) + '">' + esc(label) + "</span>";
  }

  /**
   * T-457 (Layer 3): 카드 1행 우측 failure tag 렌더 헬퍼.
   * ticket.failure schema (T-NNN-D 도입 예정): { reason, phase, retry_count, context }
   * 가드: ticket / ticket.failure 가 falsy 면 빈 문자열 반환 (자연스럽게 비표시).
   * read-only — pointer-events:none (CSS), 클릭 트리거 없음.
   * 색상은 placeholder neutral (사용자 결정 대기 — 결정 후 1줄 패치 예정).
   * @param {object} ticket - 카드 티켓 객체
   * @returns {string} span.card-failure-tag HTML 또는 빈 문자열
   */
  function renderFailureTag(ticket) {
    if (!ticket || !ticket.failure) return "";
    var reason = ticket.failure.reason || "워크플로우 실패";
    var phase = ticket.failure.phase || "";
    var label = "FAIL";
    var tooltip = phase ? (phase + " 단계 실패 — " + reason) : reason;
    return '<span class="card-failure-tag" title="' + esc(tooltip) + '">' + esc(label) + "</span>";
  }

  /**
   * T-441: Done 카드 verdict 배지 HTML 을 생성한다.
   * 캐시에 결과가 없으면 로딩 중 플레이스홀더를 반환하고 비동기 fetch 트리거.
   * @param {string} ticketNum - 티켓 번호 (예: "T-441")
   * @returns {string} span.card-done-verdict HTML 또는 빈 문자열
   */
  function renderDoneVerdictBadge(ticketNum) {
    var data = _doneVerdictMap[ticketNum];
    if (data === undefined || data === "pending") {
      // 로딩 중 — 작은 플레이스홀더 (보이지 않음, fetch 완료 후 DOM 패치)
      return '<span class="card-done-verdict verdict-loading" style="display:none"></span>';
    }
    var verdict = data && data.verdict;
    if (verdict === "OK") {
      return (
        '<span class="card-done-verdict verdict-ok" title="머지 정합성 확인 (develop HEAD == merge commit)">'
        + '<svg width="11" height="11" viewBox="0 0 11 11" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        + '<polyline points="1.5,5.5 4.5,8.5 9.5,2.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
        + '</svg></span>'
      );
    }
    if (verdict === "FAIL") {
      var msg = (data.details && data.details.message) || "develop HEAD 가 머지 commit 아님";
      return (
        '<span class="card-done-verdict verdict-fail"'
        + ' title="머지 불일치 — ' + esc(msg) + ' (클릭하면 상세 확인)"'
        + ' data-verdict-msg="' + esc(msg) + '">'
        + '<svg width="11" height="11" viewBox="0 0 11 11" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        + '<line x1="2" y1="2" x2="9" y2="9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
        + '<line x1="9" y1="2" x2="2" y2="9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
        + '</svg></span>'
      );
    }
    // UNKNOWN / SKIP — 배지 숨김
    return '<span class="card-done-verdict verdict-unknown" style="display:none"></span>';
  }

  /**
   * 티켓의 status를 기반으로 상태 라벨 정보를 반환한다.
   * To Do 카드만 TODO 라벨을 반환한다.
   * T-399: Submit transient 단계 제거됨. T-445: OPEN 라벨 폐기.
   * @param {Object} ticket - 티켓 객체
   * @returns {{ label: string, cssClass: string } | null} 상태 라벨과 CSS 클래스, 또는 null
   */
  function getWorkflowStatus(ticket) {
    if (ticket && ticket.status === "To Do") {
      return { label: "TODO", cssClass: "status-todo" };
    }
    return null;
  }

  /**
   * T-399: confirm 모달 표시 — Open → In Progress drop 시 워크플로우 실행 의식 보장.
   * @param {Object} ticket - 드래그된 티켓 객체 (number, command 포함)
   * @param {Function} onConfirm - [실행] 클릭 콜백
   * @param {Function} onCancel - [취소]/ESC/overlay 클릭 콜백
   */
  function showSubmitConfirmModal(ticket, onConfirm, onCancel) {
    const overlay = document.createElement("div");
    overlay.className = "submit-confirm-overlay";

    const dialog = document.createElement("div");
    dialog.className = "submit-confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "submit-confirm-title");

    const title = document.createElement("h3");
    title.id = "submit-confirm-title";
    title.className = "submit-confirm-title";
    title.textContent = "워크플로우 실행";

    const body = document.createElement("p");
    body.className = "submit-confirm-body";
    body.textContent =
      ticket.number + " 을 In Progress 로 이동하고 워크플로우를 시작합니다. 계속할까요?";

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    cancelBtn.textContent = "취소";

    const confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    confirmBtn.textContent = "실행";

    actions.appendChild(cancelBtn);
    actions.appendChild(confirmBtn);
    dialog.appendChild(title);
    dialog.appendChild(body);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);

    function cleanup() {
      document.removeEventListener("keydown", onKey);
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }
    function fireCancel() {
      cleanup();
      if (typeof onCancel === "function") onCancel();
    }
    function fireConfirm() {
      cleanup();
      if (typeof onConfirm === "function") onConfirm();
    }
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        fireCancel();
      }
    }

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) fireCancel();
    });
    cancelBtn.addEventListener("click", fireCancel);
    confirmBtn.addEventListener("click", fireConfirm);
    document.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    confirmBtn.focus();
  }

  /**
   * T-906: Review → Done drop 추가 (confirm 모달 + cmd_done 위임 + 결과 모달).
   * @param {Object} ticket - 드래그된 티켓 객체 (number 포함)
   * @param {Function} onConfirm - [완료 처리] 클릭 콜백
   * @param {Function} onCancel - [취소]/ESC/overlay 클릭 콜백
   */
  function showDoneConfirmModal(ticket, onConfirm, onCancel) {
    const overlay = document.createElement("div");
    overlay.className = "submit-confirm-overlay";

    const dialog = document.createElement("div");
    dialog.className = "submit-confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "submit-confirm-title");

    const title = document.createElement("h3");
    title.id = "submit-confirm-title";
    title.className = "submit-confirm-title";
    const ticketNumNode = document.createTextNode(ticket.number + " Done 처리");
    title.appendChild(ticketNumNode);

    const body = document.createElement("div");
    body.className = "submit-confirm-body";
    const introText = document.createTextNode("이 티켓을 Done 으로 이동하면 다음이 비가역적으로 수행됩니다:");
    body.appendChild(introText);
    const ul = document.createElement("ul");
    const li1 = document.createElement("li");
    li1.textContent = "feature 브랜치를 develop 에 --no-ff 머지";
    const li2 = document.createElement("li");
    li2.textContent = "워크트리 및 feature 브랜치 삭제";
    ul.appendChild(li1);
    ul.appendChild(li2);
    body.appendChild(ul);
    const continueText = document.createTextNode("계속할까요?");
    body.appendChild(continueText);

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    cancelBtn.textContent = "취소";

    const confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    confirmBtn.textContent = "완료 처리";

    actions.appendChild(cancelBtn);
    actions.appendChild(confirmBtn);
    dialog.appendChild(title);
    dialog.appendChild(body);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);

    function cleanup() {
      document.removeEventListener("keydown", onKey);
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }
    function fireCancel() {
      cleanup();
      if (typeof onCancel === "function") onCancel();
    }
    function fireConfirm() {
      cleanup();
      if (typeof onConfirm === "function") onConfirm();
    }
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        fireCancel();
      }
    }

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) fireCancel();
    });
    cancelBtn.addEventListener("click", fireCancel);
    confirmBtn.addEventListener("click", fireConfirm);
    document.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    confirmBtn.focus();
  }

  /**
   * T-439: Review 카드 우하단 1-click 완료 액션 핸들러.
   * showDoneConfirmModal → POST /api/kanban/done → showDoneResultModal 체인을
   * DnD Review→Done 분기(kanban.js:1791-1826)와 동일한 시그니처로 재사용한다.
   * @param {Object} ticketObj - 티켓 객체 (number 포함)
   */
  function handleReviewDoneAction(ticketObj) {
    var capturedNum = ticketObj.number;
    showDoneConfirmModal(
      ticketObj,
      function () {
        // [완료 처리] 콜백: POST /api/kanban/done → cmd_done 위임
        fetch("/api/kanban/done", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticket: capturedNum }),
        }).then(function (res) {
          return res.json().then(function (body) {
            return { res: res, body: body };
          });
        }).then(function (r) {
          if (r.res.ok && r.body.ok) {
            showDoneResultModal("success", r.body, function () {
              fetchTickets().then(renderKanban);
            });
          } else {
            var kind = r.body.error_kind === "merge_conflict" ? "conflict"
              : r.body.error_kind === "dirty_worktree" ? "dirty"
              : "error";
            showDoneResultModal(kind, r.body, function () { renderKanban(); });
          }
        }).catch(function (err) {
          console.error("[kanban card-done-action] done failed:", err);
          showDoneResultModal("error", { message: err.message }, function () { renderKanban(); });
        });
      },
      function () {
        // [취소]/ESC/overlay 콜백: 카드 원위치 유지
        renderKanban();
      }
    );
  }

  /**
   * T-418: Open → Done 직접 전이 confirm 모달.
   *
   * Review 를 거치지 않고 Done 으로 이동. 워크트리/feature 브랜치 폐기.
   * "미커밋 변경 폐기 동의" 체크박스 포함. onConfirm 에 force_dirty 값 전달.
   *
   * @param {Object} ticket - 드래그된 티켓 객체 (number 포함)
   * @param {Function} onConfirm - [직접 Done 처리] 클릭 콜백 (force_dirty: bool 인자 전달)
   * @param {Function} onCancel - [취소]/ESC/overlay 클릭 콜백
   */
  function showOpenDoneConfirmModal(ticket, onConfirm, onCancel) {
    const overlay = document.createElement("div");
    overlay.className = "submit-confirm-overlay";

    const dialog = document.createElement("div");
    dialog.className = "submit-confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "open-done-confirm-title");

    const title = document.createElement("h3");
    title.id = "open-done-confirm-title";
    title.className = "submit-confirm-title";
    title.appendChild(document.createTextNode(ticket.number + " Open → Done 직접 전이"));

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    const introText = document.createTextNode("Open 단계에서 Review 를 거치지 않고 Done 으로 직접 이동합니다. 다음이 비가역적으로 수행됩니다:");
    body.appendChild(introText);

    const ul = document.createElement("ul");
    const li1 = document.createElement("li");
    li1.textContent = "워크트리 및 feature 브랜치 폐기 (develop 병합 없음)";
    const li2 = document.createElement("li");
    li2.textContent = "티켓 상태를 Done 으로 강제 전이";
    ul.appendChild(li1);
    ul.appendChild(li2);
    body.appendChild(ul);

    const dirtyLabel = document.createElement("label");
    dirtyLabel.style.display = "flex";
    dirtyLabel.style.alignItems = "center";
    dirtyLabel.style.gap = "6px";
    dirtyLabel.style.marginTop = "10px";
    dirtyLabel.style.fontSize = "12px";
    dirtyLabel.style.color = "#cccccc";
    dirtyLabel.style.cursor = "pointer";

    const dirtyCheckbox = document.createElement("input");
    dirtyCheckbox.type = "checkbox";
    dirtyCheckbox.id = "open-done-force-dirty";
    dirtyCheckbox.style.cursor = "pointer";

    const dirtyLabelText = document.createTextNode("미커밋 변경이 있더라도 폐기하고 진행");
    dirtyLabel.appendChild(dirtyCheckbox);
    dirtyLabel.appendChild(dirtyLabelText);
    body.appendChild(dirtyLabel);

    const continueText = document.createElement("p");
    continueText.style.marginTop = "10px";
    continueText.appendChild(document.createTextNode("계속할까요?"));
    body.appendChild(continueText);

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    cancelBtn.textContent = "취소";

    const confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    confirmBtn.textContent = "직접 Done 처리";

    actions.appendChild(cancelBtn);
    actions.appendChild(confirmBtn);
    dialog.appendChild(title);
    dialog.appendChild(body);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);

    function cleanup() {
      document.removeEventListener("keydown", onKey);
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }
    function fireCancel() {
      cleanup();
      if (typeof onCancel === "function") onCancel();
    }
    function fireConfirm() {
      const forceDirty = dirtyCheckbox.checked;
      cleanup();
      if (typeof onConfirm === "function") onConfirm(forceDirty);
    }
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        fireCancel();
      }
    }

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) fireCancel();
    });
    cancelBtn.addEventListener("click", fireCancel);
    confirmBtn.addEventListener("click", fireConfirm);
    document.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    confirmBtn.focus();
  }

  /**
   * T-418: Open → Done 직접 전이 결과 모달.
   *
   * showDoneResultModal 과 달리 merge_commit 없는 성공도 정상 처리.
   * error_kind='dirty_worktree' 시 "강제 폐기 후 재시도" 버튼 노출.
   *
   * @param {"success"|"dirty"|"error"} kind - 결과 종류
   * @param {Object} payload - 결과 데이터
   * @param {Function} onClose - 닫기 콜백
   * @param {Function} onForceDirty - "강제 폐기 후 재시도" 버튼 클릭 콜백 (dirty 시만)
   */
  function showOpenDoneResultModal(kind, payload, onClose, onForceDirty) {
    const overlay = document.createElement("div");
    overlay.className = "submit-confirm-overlay";

    const dialog = document.createElement("div");
    dialog.className = "submit-confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "open-done-result-title");

    const title = document.createElement("h3");
    title.id = "open-done-result-title";
    title.className = "submit-confirm-title";

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    if (kind === "success") {
      title.textContent = "Open → Done 직접 전이 완료";
      const msg = document.createElement("p");
      msg.textContent = (payload.ticket || "") + " 티켓이 Done 으로 이동되었습니다. 워크트리 및 feature 브랜치가 정리되었습니다.";
      body.appendChild(msg);
    } else if (kind === "dirty") {
      title.textContent = "Done 처리 실패 — 미커밋 변경";
      const ul = document.createElement("ul");
      const files = (payload.dirty_files || []);
      if (files.length > 0) {
        files.forEach(function (f) {
          const li = document.createElement("li");
          li.textContent = f;
          ul.appendChild(li);
        });
      } else {
        const li = document.createElement("li");
        li.textContent = "(미커밋 파일 목록 없음)";
        ul.appendChild(li);
      }
      body.appendChild(ul);
      const guide = document.createElement("p");
      guide.textContent = "워크트리에 미커밋 변경이 있습니다. 폐기 동의 후 강제 진행하거나 취소하세요.";
      body.appendChild(guide);
    } else {
      title.textContent = "Done 처리 실패";
      const msg = document.createElement("p");
      msg.textContent = (payload && payload.message) ? payload.message : "알 수 없는 오류가 발생했습니다.";
      body.appendChild(msg);
    }

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    closeBtn.textContent = kind === "success" ? "확인" : "취소";

    actions.appendChild(closeBtn);

    if (kind === "dirty" && typeof onForceDirty === "function") {
      const forceBtn = document.createElement("button");
      forceBtn.type = "button";
      forceBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
      forceBtn.textContent = "강제 폐기 후 재시도";
      forceBtn.style.background = "#c0392b";
      forceBtn.style.borderColor = "#c0392b";
      forceBtn.addEventListener("click", function () {
        cleanup();
        onForceDirty();
      });
      actions.appendChild(forceBtn);
    }

    dialog.appendChild(title);
    dialog.appendChild(body);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);

    function cleanup() {
      document.removeEventListener("keydown", onKey);
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }
    function fireClose() {
      cleanup();
      if (typeof onClose === "function") onClose();
    }
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        fireClose();
      }
    }

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) fireClose();
    });
    closeBtn.addEventListener("click", fireClose);
    document.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    closeBtn.focus();
  }

  /**
   * T-418: 티켓 삭제 confirm 모달.
   *
   * 빨간 [삭제] 버튼. POST /api/kanban/delete 호출.
   * error_kind='derived_blocked' 시 alert 으로 차단 사유 표시.
   *
   * @param {Object} ticket - 삭제할 티켓 객체 (number 포함)
   * @param {Function} onConfirm - [삭제] 클릭 콜백
   * @param {Function} onCancel - [취소]/ESC/overlay 클릭 콜백
   */
  function showDeleteConfirmModal(ticket, onConfirm, onCancel) {
    const overlay = document.createElement("div");
    overlay.className = "submit-confirm-overlay";

    const dialog = document.createElement("div");
    dialog.className = "submit-confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "delete-confirm-title");

    const title = document.createElement("h3");
    title.id = "delete-confirm-title";
    title.className = "submit-confirm-title";
    title.appendChild(document.createTextNode(ticket.number + " 티켓 삭제"));

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    const introText = document.createTextNode(ticket.number + " 티켓을 삭제합니다. 이 작업은 되돌릴 수 없습니다.");
    body.appendChild(introText);

    const ul = document.createElement("ul");
    const li1 = document.createElement("li");
    li1.textContent = "워크트리 및 feature 브랜치도 함께 정리됩니다.";
    const li2 = document.createElement("li");
    li2.textContent = "파생 티켓(derived-from)이 미완료 상태면 삭제가 차단됩니다.";
    ul.appendChild(li1);
    ul.appendChild(li2);
    body.appendChild(ul);

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    cancelBtn.textContent = "취소";

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    deleteBtn.textContent = "삭제";
    deleteBtn.style.background = "#c0392b";
    deleteBtn.style.borderColor = "#c0392b";

    actions.appendChild(cancelBtn);
    actions.appendChild(deleteBtn);
    dialog.appendChild(title);
    dialog.appendChild(body);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);

    function cleanup() {
      document.removeEventListener("keydown", onKey);
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }
    function fireCancel() {
      cleanup();
      if (typeof onCancel === "function") onCancel();
    }
    function fireConfirm() {
      cleanup();
      if (typeof onConfirm === "function") onConfirm();
    }
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        fireCancel();
      }
    }

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) fireCancel();
    });
    cancelBtn.addEventListener("click", fireCancel);
    deleteBtn.addEventListener("click", fireConfirm);
    document.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    deleteBtn.focus();
  }

  /**
   * T-906: Done 처리 결과 모달.
   * @param {"success"|"conflict"|"dirty"|"error"} kind - 결과 종류
   * @param {Object} payload - 결과 데이터 (kind 별 다름)
   * @param {Function} onClose - 닫기 콜백
   */
  function showDoneResultModal(kind, payload, onClose) {
    const overlay = document.createElement("div");
    overlay.className = "submit-confirm-overlay";

    const dialog = document.createElement("div");
    dialog.className = "submit-confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "done-result-title");

    const title = document.createElement("h3");
    title.id = "done-result-title";
    title.className = "submit-confirm-title";

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    if (kind === "success" && !payload.merge_commit && !payload.merge_skipped) {
      console.warn("[showDoneResultModal] success kind with empty merge_commit — converting to error");
      kind = "error";
      payload = Object.assign({}, payload, {
        message: "백엔드 응답 형식 오류 — merge_commit 누락. flow-kanban 출력을 확인하세요."
      });
    }

    if (kind === "success") {
      title.textContent = "Done 처리 완료";
      const msg = document.createElement("p");
      const ticketStr = payload.merge_skipped
        ? (payload.ticket || "") + ": Review → Done (merge 없음 — research/문서 등)"
        : (payload.ticket || "") + ": " + (payload.merged_branch || "") + " → develop 병합 완료 (" + (payload.merge_commit || "") + ")";
      msg.textContent = ticketStr;
      body.appendChild(msg);
    } else if (kind === "conflict") {
      title.textContent = "Done 처리 실패 — 병합 충돌";
      const ul = document.createElement("ul");
      const files = (payload.conflicts || []);
      if (files.length > 0) {
        files.forEach(function (f) {
          const li = document.createElement("li");
          li.textContent = f;
          ul.appendChild(li);
        });
      } else {
        const li = document.createElement("li");
        li.textContent = "(충돌 파일 목록 없음)";
        ul.appendChild(li);
      }
      body.appendChild(ul);
      const guide = document.createElement("p");
      guide.textContent = "워크트리에서 충돌을 해결한 뒤 다시 시도하세요.";
      body.appendChild(guide);
    } else if (kind === "dirty") {
      title.textContent = "Done 처리 실패 — 미커밋 변경";
      const ul = document.createElement("ul");
      const files = (payload.dirty_files || []);
      if (files.length > 0) {
        files.forEach(function (f) {
          const li = document.createElement("li");
          li.textContent = f;
          ul.appendChild(li);
        });
      } else {
        const li = document.createElement("li");
        li.textContent = "(미커밋 파일 목록 없음)";
        ul.appendChild(li);
      }
      body.appendChild(ul);
      const guide = document.createElement("p");
      guide.textContent = "워크트리에서 변경을 커밋하거나 flow-merge 로 처리한 뒤 다시 시도하세요.";
      body.appendChild(guide);
    } else {
      title.textContent = "Done 처리 실패";
      const msg = document.createElement("p");
      msg.textContent = (payload && payload.message) ? payload.message : "알 수 없는 오류가 발생했습니다.";
      body.appendChild(msg);
    }

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    closeBtn.textContent = "확인";

    actions.appendChild(closeBtn);
    dialog.appendChild(title);
    dialog.appendChild(body);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);

    function cleanup() {
      document.removeEventListener("keydown", onKey);
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }
    function fireClose() {
      cleanup();
      if (typeof onClose === "function") onClose();
    }
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        fireClose();
      }
    }

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) fireClose();
    });
    closeBtn.addEventListener("click", fireClose);
    document.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    closeBtn.focus();
  }

  /**
   * T-905 Phase 3: Done 카드 우클릭 → "Review 로 롤백" 확인 모달.
   *
   * push 전(local-only) / push 후(origin/develop 도달) 분기 안내 + force 옵션 체크박스.
   * pre-detect: 칸반 result.merge_commit 존재 여부를 사전 점검하여
   * 누락 시 force 옵션이 필요함을 명시 안내한다.
   *
   * @param {Object} ticket - Done 컬럼 카드 티켓 객체 (number/result 포함)
   * @param {Function} onConfirm - confirm 콜백 (force: bool 인자 전달)
   * @param {Function} onCancel - 취소/ESC/overlay 콜백
   */
  function showUndoDoneConfirmModal(ticket, onConfirm, onCancel) {
    const overlay = document.createElement("div");
    overlay.className = "submit-confirm-overlay";

    const dialog = document.createElement("div");
    dialog.className = "submit-confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "undo-done-confirm-title");

    const title = document.createElement("h3");
    title.id = "undo-done-confirm-title";
    title.className = "submit-confirm-title";
    title.appendChild(document.createTextNode(ticket.number + " Review 로 롤백"));

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    const intro = document.createElement("p");
    intro.textContent = "이 티켓의 Done 처리를 되돌립니다. develop 의 머지 결과를 자동으로 분기 처리합니다:";
    body.appendChild(intro);

    const ul = document.createElement("ul");
    const li1 = document.createElement("li");
    li1.textContent = "push 전(local-only): reset --hard 로 머지 commit 제거";
    const li2 = document.createElement("li");
    li2.textContent = "push 후(origin/develop 포함): revert -m 1 로 역방향 commit 추가 (force-push 없음)";
    const li3 = document.createElement("li");
    li3.textContent = "feature 브랜치 + 워크트리 재생성 + 칸반 Done → Review 강제 전이";
    ul.appendChild(li1);
    ul.appendChild(li2);
    ul.appendChild(li3);
    body.appendChild(ul);

    // pre-detect: result.merge_commit 누락 여부
    const result = ticket.result || {};
    const hasMergeCommit = !!(result.merge_commit && String(result.merge_commit).trim());
    if (!hasMergeCommit) {
      const warn = document.createElement("p");
      warn.style.color = "#D97757";
      warn.style.fontWeight = "600";
      warn.textContent = "주의: 이 티켓에는 merge_commit 정보가 없습니다 (Phase 1 인프라 도입 이전 Done). reflog fallback 을 시도하려면 아래 force 옵션을 활성화하세요.";
      body.appendChild(warn);
    }

    // force 옵션 체크박스
    const forceWrapper = document.createElement("label");
    forceWrapper.style.display = "flex";
    forceWrapper.style.alignItems = "center";
    forceWrapper.style.gap = "8px";
    forceWrapper.style.marginTop = "10px";
    forceWrapper.style.cursor = "pointer";
    const forceCheckbox = document.createElement("input");
    forceCheckbox.type = "checkbox";
    forceCheckbox.id = "undo-done-force";
    if (!hasMergeCommit) {
      forceCheckbox.checked = true;
    }
    const forceLabel = document.createElement("span");
    forceLabel.textContent = "--force (점유 경고 무시 + reflog fallback 활성화)";
    forceWrapper.appendChild(forceCheckbox);
    forceWrapper.appendChild(forceLabel);
    body.appendChild(forceWrapper);

    const tail = document.createElement("p");
    tail.style.marginTop = "10px";
    tail.textContent = "계속할까요?";
    body.appendChild(tail);

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    cancelBtn.textContent = "취소";

    const confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    confirmBtn.textContent = "Review 로 롤백";

    actions.appendChild(cancelBtn);
    actions.appendChild(confirmBtn);
    dialog.appendChild(title);
    dialog.appendChild(body);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);

    function cleanup() {
      document.removeEventListener("keydown", onKey);
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }
    function fireCancel() {
      cleanup();
      if (typeof onCancel === "function") onCancel();
    }
    function fireConfirm() {
      const force = !!forceCheckbox.checked;
      cleanup();
      if (typeof onConfirm === "function") onConfirm(force);
    }
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        fireCancel();
      }
    }

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) fireCancel();
    });
    cancelBtn.addEventListener("click", fireCancel);
    confirmBtn.addEventListener("click", fireConfirm);
    document.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    confirmBtn.focus();
  }

  /**
   * T-905 Phase 3: undo-done 결과 모달.
   * showDoneResultModal 패턴 답습.
   *
   * @param {"reset_ok"|"revert_ok"|"unknown_ok"|"error"} kind - 결과 종류
   * @param {Object} payload - 결과 데이터
   *   - reset_ok / revert_ok: { ticket, strategy, branch, worktree_path, message }
   *   - error: { ticket, error, message, stderr }
   * @param {Function} onClose - 닫기 콜백 (성공 시 보드 자동 새로고침에 활용)
   */
  function showUndoDoneResultModal(kind, payload, onClose) {
    const overlay = document.createElement("div");
    overlay.className = "submit-confirm-overlay";

    const dialog = document.createElement("div");
    dialog.className = "submit-confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "undo-done-result-title");

    const title = document.createElement("h3");
    title.id = "undo-done-result-title";
    title.className = "submit-confirm-title";

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    if (kind === "reset_ok" || kind === "revert_ok" || kind === "unknown_ok") {
      title.textContent = "Review 로 롤백 완료";

      const summary = document.createElement("p");
      const ticketStr = payload.ticket || "";
      const strategyStr = payload.strategy
        ? (payload.strategy === "reset" ? "reset --hard (push 전)" : payload.strategy === "revert" ? "revert -m 1 (push 후)" : payload.strategy)
        : "?";
      summary.textContent = ticketStr + " 롤백 완료 — 전략: " + strategyStr;
      body.appendChild(summary);

      if (payload.branch) {
        const br = document.createElement("p");
        br.textContent = "재생성된 feature 브랜치: " + payload.branch;
        body.appendChild(br);
      }
      if (payload.worktree_path) {
        const wt = document.createElement("p");
        wt.textContent = "재생성된 워크트리: " + payload.worktree_path;
        body.appendChild(wt);
      }

      const guideTitle = document.createElement("p");
      guideTitle.style.marginTop = "10px";
      guideTitle.style.fontWeight = "600";
      guideTitle.textContent = "다음 절차:";
      body.appendChild(guideTitle);
      const ol = document.createElement("ol");
      const liE = document.createElement("li");
      liE.textContent = "/wf -e " + ticketStr + " 로 티켓을 편집하거나 직접 수정";
      const liS = document.createElement("li");
      liS.textContent = "/wf -s " + ticketStr + " 로 워크플로우 재실행";
      ol.appendChild(liE);
      ol.appendChild(liS);
      body.appendChild(ol);
    } else {
      title.textContent = "Review 로 롤백 실패";
      const msg = document.createElement("p");
      msg.textContent = (payload && (payload.error || payload.message)) || "알 수 없는 오류가 발생했습니다.";
      body.appendChild(msg);

      if (payload && payload.stderr) {
        const stderrTitle = document.createElement("p");
        stderrTitle.style.marginTop = "8px";
        stderrTitle.style.fontWeight = "600";
        stderrTitle.textContent = "stderr:";
        body.appendChild(stderrTitle);
        const pre = document.createElement("pre");
        pre.style.maxHeight = "200px";
        pre.style.overflow = "auto";
        pre.style.background = "#1e1e1e";
        pre.style.padding = "8px";
        pre.style.fontSize = "11px";
        pre.textContent = payload.stderr;
        body.appendChild(pre);
      }
    }

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    closeBtn.textContent = "확인";

    actions.appendChild(closeBtn);
    dialog.appendChild(title);
    dialog.appendChild(body);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);

    function cleanup() {
      document.removeEventListener("keydown", onKey);
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }
    function fireClose() {
      cleanup();
      if (typeof onClose === "function") onClose();
    }
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        fireClose();
      }
    }

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) fireClose();
    });
    closeBtn.addEventListener("click", fireClose);
    document.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    closeBtn.focus();
  }

  /**
   * T-905 Phase 3: Done 카드 컨텍스트 메뉴 (우클릭).
   *
   * "Review 로 롤백" 단일 항목 노출. 클릭 시 showUndoDoneConfirmModal 호출.
   * 메뉴는 documentLevel 클릭 또는 ESC 로 닫힌다.
   *
   * @param {MouseEvent} event - contextmenu 이벤트
   * @param {Object} ticket - Done 카드 티켓 객체
   */
  function showDoneCardContextMenu(event, ticket) {
    // 기존 컨텍스트 메뉴가 열려 있으면 제거
    document.querySelectorAll(".kanban-card-context-menu").forEach(function (m) {
      if (m.parentNode) m.parentNode.removeChild(m);
    });

    const menu = document.createElement("div");
    menu.className = "kanban-card-context-menu";
    menu.style.position = "fixed";
    menu.style.zIndex = "10000";
    menu.style.background = "#252526";
    menu.style.border = "1px solid #3c3c3c";
    menu.style.borderRadius = "4px";
    menu.style.boxShadow = "0 4px 12px rgba(0, 0, 0, 0.4)";
    menu.style.minWidth = "180px";
    menu.style.padding = "4px 0";
    menu.style.fontSize = "13px";

    const item = document.createElement("button");
    item.type = "button";
    item.style.display = "block";
    item.style.width = "100%";
    item.style.padding = "6px 12px";
    item.style.textAlign = "left";
    item.style.background = "transparent";
    item.style.border = "none";
    item.style.color = "#cccccc";
    item.style.cursor = "pointer";
    item.style.fontSize = "13px";
    item.textContent = "Review 로 롤백";
    item.addEventListener("mouseenter", function () {
      item.style.background = "#094771";
    });
    item.addEventListener("mouseleave", function () {
      item.style.background = "transparent";
    });

    function cleanup() {
      document.removeEventListener("click", outsideHandler, true);
      document.removeEventListener("keydown", onKey);
      if (menu.parentNode) menu.parentNode.removeChild(menu);
    }
    function outsideHandler(e) {
      if (!menu.contains(e.target)) cleanup();
    }
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        cleanup();
      }
    }

    item.addEventListener("click", function (e) {
      e.stopPropagation();
      cleanup();
      showUndoDoneConfirmModal(
        ticket,
        function (force) {
          // [Review 로 롤백] 콜백
          fetch("/api/workflow/undo-done", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticket: ticket.number, force: force }),
          }).then(function (res) {
            return res.json().then(function (body) {
              return { res: res, body: body };
            });
          }).then(function (r) {
            if (r.res.ok && r.body.ok) {
              showUndoDoneResultModal(r.body.kind || "unknown_ok", r.body, function () {
                fetchTickets().then(renderKanban);
              });
            } else {
              showUndoDoneResultModal("error", r.body || {}, function () { renderKanban(); });
            }
          }).catch(function (err) {
            console.error("[kanban undo-done] failed:", err);
            showUndoDoneResultModal("error", { message: err.message }, function () { renderKanban(); });
          });
        },
        function () {
          // 취소: 아무 것도 안 함
        }
      );
    });

    menu.appendChild(item);
    document.body.appendChild(menu);

    // 위치 보정: viewport 밖으로 나가지 않도록
    const x = event.clientX;
    const y = event.clientY;
    menu.style.left = x + "px";
    menu.style.top = y + "px";
    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      menu.style.left = (window.innerWidth - rect.width - 8) + "px";
    }
    if (rect.bottom > window.innerHeight) {
      menu.style.top = (window.innerHeight - rect.height - 8) + "px";
    }

    // 외부 클릭 / ESC 로 닫기
    setTimeout(function () {
      document.addEventListener("click", outsideHandler, true);
      document.addEventListener("keydown", onKey);
    }, 0);
  }

  /**
   * T-418: Open 카드 컨텍스트 메뉴 (우클릭).
   *
   * 메뉴 항목 2개:
   *   - "Done 으로 완료(직접)" → showOpenDoneConfirmModal 호출
   *   - "삭제" → showDeleteConfirmModal 호출
   *
   * showDoneCardContextMenu 패턴 답습 (T-905).
   *
   * @param {MouseEvent} event - contextmenu 이벤트
   * @param {Object} ticket - Open 카드 티켓 객체
   */
  function showOpenCardContextMenu(event, ticket) {
    // 기존 컨텍스트 메뉴가 열려 있으면 제거
    document.querySelectorAll(".kanban-card-context-menu").forEach(function (m) {
      if (m.parentNode) m.parentNode.removeChild(m);
    });

    const menu = document.createElement("div");
    menu.className = "kanban-card-context-menu";
    menu.style.position = "fixed";
    menu.style.zIndex = "10000";
    menu.style.background = "#252526";
    menu.style.border = "1px solid #3c3c3c";
    menu.style.borderRadius = "4px";
    menu.style.boxShadow = "0 4px 12px rgba(0, 0, 0, 0.4)";
    menu.style.minWidth = "180px";
    menu.style.padding = "4px 0";
    menu.style.fontSize = "13px";

    function makeMenuItem(text, color) {
      const item = document.createElement("button");
      item.type = "button";
      item.style.display = "block";
      item.style.width = "100%";
      item.style.padding = "6px 12px";
      item.style.textAlign = "left";
      item.style.background = "transparent";
      item.style.border = "none";
      item.style.color = color || "#cccccc";
      item.style.cursor = "pointer";
      item.style.fontSize = "13px";
      item.textContent = text;
      item.addEventListener("mouseenter", function () {
        item.style.background = "#094771";
      });
      item.addEventListener("mouseleave", function () {
        item.style.background = "transparent";
      });
      return item;
    }

    const doneItem = makeMenuItem("Done 으로 완료(직접)");
    const deleteItem = makeMenuItem("삭제", "#f48771");

    function cleanup() {
      document.removeEventListener("click", outsideHandler, true);
      document.removeEventListener("keydown", onKey);
      if (menu.parentNode) menu.parentNode.removeChild(menu);
    }
    function outsideHandler(e) {
      if (!menu.contains(e.target)) cleanup();
    }
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        cleanup();
      }
    }

    // "Done 으로 완료(직접)" 클릭 핸들러
    doneItem.addEventListener("click", function (e) {
      e.stopPropagation();
      cleanup();
      function callOpenDone(forceDirty) {
        fetch("/api/kanban/done", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticket: ticket.number, force: true, force_dirty: forceDirty }),
        }).then(function (res) {
          return res.json().then(function (body) {
            return { res: res, body: body };
          });
        }).then(function (r) {
          if (r.res.ok && r.body.ok) {
            showOpenDoneResultModal("success", r.body, function () {
              fetchTickets().then(renderKanban);
            });
          } else {
            const kind = r.body.error_kind === "dirty_worktree" ? "dirty" : "error";
            showOpenDoneResultModal(kind, r.body, function () {
              renderKanban();
            }, kind === "dirty" ? function () {
              callOpenDone(true);
            } : undefined);
          }
        }).catch(function (err) {
          console.error("[kanban Open contextmenu] open-done failed:", err);
          showOpenDoneResultModal("error", { message: err.message }, function () { renderKanban(); });
        });
      }
      showOpenDoneConfirmModal(
        ticket,
        function (forceDirty) {
          callOpenDone(forceDirty);
        },
        function () {
          // 취소: 아무 것도 안 함
        }
      );
    });

    // "삭제" 클릭 핸들러
    deleteItem.addEventListener("click", function (e) {
      e.stopPropagation();
      cleanup();
      showDeleteConfirmModal(
        ticket,
        function () {
          fetch("/api/kanban/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticket: ticket.number }),
          }).then(function (res) {
            return res.json().then(function (body) {
              return { res: res, body: body };
            });
          }).then(function (r) {
            if (r.res.ok && r.body.ok) {
              fetchTickets().then(renderKanban);
            } else {
              if (r.body.error_kind === "derived_blocked") {
                const derivedList = (r.body.derived_tickets || []).join(", ") || "(목록 없음)";
                alert("삭제 차단: 파생 티켓이 미완료 상태입니다.\n\n미완료 파생 티켓: " + derivedList + "\n\n파생 티켓을 먼저 완료하세요.");
              } else {
                alert("삭제 실패: " + ((r.body && r.body.message) || "알 수 없는 오류"));
              }
              renderKanban();
            }
          }).catch(function (err) {
            console.error("[kanban Open contextmenu] delete failed:", err);
            alert("삭제 실패: " + err.message);
            renderKanban();
          });
        },
        function () {
          // 취소: 아무 것도 안 함
        }
      );
    });

    menu.appendChild(doneItem);
    menu.appendChild(deleteItem);
    document.body.appendChild(menu);

    // 위치 보정: viewport 밖으로 나가지 않도록
    const x = event.clientX;
    const y = event.clientY;
    menu.style.left = x + "px";
    menu.style.top = y + "px";

    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      menu.style.left = (window.innerWidth - rect.width - 8) + "px";
    }
    if (rect.bottom > window.innerHeight) {
      menu.style.top = (window.innerHeight - rect.height - 8) + "px";
    }

    // 외부 클릭 / ESC 로 닫기
    setTimeout(function () {
      document.addEventListener("click", outsideHandler, true);
      document.addEventListener("keydown", onKey);
    }, 0);
  }

  /**
   * Review 카드 우클릭 컨텍스트 메뉴.
   * 옵션: (a) Open 으로 재작업 (POST /api/kanban/move).
   * 채팅 첨부는 DnD 로 일원화 (T-427).
   * Review → In Progress 전이 폐기 (2026-05-08 사용자 명시).
   *
   * @param {MouseEvent} event - contextmenu 이벤트
   * @param {Object} ticket - Review 카드 티켓 객체
   */
  function showReviewCardContextMenu(event, ticket) {
    document.querySelectorAll(".kanban-card-context-menu").forEach(function (m) {
      if (m.parentNode) m.parentNode.removeChild(m);
    });

    const menu = document.createElement("div");
    menu.className = "kanban-card-context-menu";
    menu.style.position = "fixed";
    menu.style.zIndex = "10000";
    menu.style.background = "#252526";
    menu.style.border = "1px solid #3c3c3c";
    menu.style.borderRadius = "4px";
    menu.style.boxShadow = "0 4px 12px rgba(0, 0, 0, 0.4)";
    menu.style.minWidth = "180px";
    menu.style.padding = "4px 0";
    menu.style.fontSize = "13px";

    function makeMenuItem(text, color) {
      const item = document.createElement("button");
      item.type = "button";
      item.style.display = "block";
      item.style.width = "100%";
      item.style.padding = "6px 12px";
      item.style.textAlign = "left";
      item.style.background = "transparent";
      item.style.border = "none";
      item.style.color = color || "#cccccc";
      item.style.cursor = "pointer";
      item.style.fontSize = "13px";
      item.textContent = text;
      item.addEventListener("mouseenter", function () { item.style.background = "#094771"; });
      item.addEventListener("mouseleave", function () { item.style.background = "transparent"; });
      return item;
    }

    const reopenItem = makeMenuItem("Open 으로 재작업");

    function cleanup() {
      document.removeEventListener("click", outsideHandler, true);
      document.removeEventListener("keydown", onKey);
      if (menu.parentNode) menu.parentNode.removeChild(menu);
    }
    function outsideHandler(e) { if (!menu.contains(e.target)) cleanup(); }
    function onKey(e) {
      if (e.key === "Escape") { e.preventDefault(); cleanup(); }
    }

    reopenItem.addEventListener("click", function (e) {
      e.stopPropagation();
      cleanup();
      fetch("/api/kanban/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket: ticket.number, to: "open" }),
      }).then(function (res) {
        return res.json().then(function (body) { return { res: res, body: body }; });
      }).then(function (r) {
        if (r.res.ok && r.body.ok) {
          fetchTickets().then(renderKanban);
        } else {
          alert("재작업 전이 실패: " + ((r.body && r.body.error) || "알 수 없는 오류"));
          renderKanban();
        }
      }).catch(function (err) {
        alert("재작업 요청 실패: " + (err && err.message ? err.message : err));
        renderKanban();
      });
    });

    menu.appendChild(reopenItem);
    document.body.appendChild(menu);

    const x = event.clientX;
    const y = event.clientY;
    menu.style.left = x + "px";
    menu.style.top = y + "px";

    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      menu.style.left = (window.innerWidth - rect.width - 8) + "px";
    }
    if (rect.bottom > window.innerHeight) {
      menu.style.top = (window.innerHeight - rect.height - 8) + "px";
    }

    setTimeout(function () {
      document.addEventListener("click", outsideHandler, true);
      document.addEventListener("keydown", onKey);
    }, 0);
  }

  /**
   * 카드 드래그 앤 드랍 핸들러 등록 (T-399: To Do ↔ Open + Open → In Progress).
   * T-906: Review → Done drop 추가 (confirm 모달 + cmd_done 위임 + 결과 모달).
   *
   * dragstart: 카드에서 ticket 번호 + 출발 컬럼을 dataTransfer 에 저장.
   * dragover: drop 가능한 cards-droppable 영역에서 dragover-active 표시.
   * drop:
   *   - To Do ↔ Open: POST /api/kanban/move (단순 전이)
   *   - Open → In Progress: confirm 모달 → POST /api/kanban/submit (워크플로우 실행)
   *   - Review → Done: confirm 모달 → POST /api/kanban/done (cmd_done 위임)
   * dragend: 시각 피드백 클래스 정리.
   *
   * In Progress 카드 drag 불가는 의도된 보호 (취소 부수효과 차단).
   * Review → Done drop 만 confirm 모달로 허용 (T-906).
   */
  function bindKanbanDnd(el) {
    let draggedNum = null;
    let draggedFrom = null;

    el.querySelectorAll(".card-draggable").forEach(function (card) {
      card.addEventListener("dragstart", function (e) {
        draggedNum = card.dataset.num;
        draggedFrom = card.dataset.colKey;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", draggedNum);
        // T-427: ticket JSON 페이로드를 별도 MIME 으로 전달 (터미널 drop 분기 전용)
        var ticketObj = (Board.state.TICKETS || []).find(function (t) {
          return t.number === draggedNum;
        });
        if (ticketObj) {
          var payload = {
            number: ticketObj.number,
            title: ticketObj.title || "",
            command: ticketObj.command || "",
            prompt: ticketObj.prompt || null,
            result: ticketObj.result || null,
          };
          try {
            e.dataTransfer.setData("application/x-board-ticket", JSON.stringify(payload));
          } catch (ex) { /* 일부 브라우저 제한 — 무시 */ }
        }
        card.classList.add("card-dragging");
      });
      card.addEventListener("dragend", function () {
        card.classList.remove("card-dragging");
        el.querySelectorAll(".cards-droppable.dragover-active").forEach(function (z) {
          z.classList.remove("dragover-active");
        });
        el.querySelectorAll(".card-drop-indicator").forEach(function (ind) {
          ind.remove();
        });
        draggedNum = null;
        draggedFrom = null;
      });
    });

    /**
     * draggedFrom → targetCol 전이가 허용되는지 판정.
     * 허용 표:
     *   To Do  → To Do(reorder) | Open
     *   Open   → To Do | In Progress | Review | Done
     *   Review → Done | Open
     * 그 외 조합은 dragover 단계에서 drop 거부 (브라우저 cursor 가 no-drop 표시).
     */
    function isValidDropTarget(fromCol, targetCol) {
      if (fromCol === "To Do") return targetCol === "To Do" || targetCol === "Open";
      if (fromCol === "Open") return targetCol === "To Do" || targetCol === "In Progress" || targetCol === "Review" || targetCol === "Done";
      if (fromCol === "Review") return targetCol === "Done" || targetCol === "Open";
      return false;
    }

    /**
     * To Do 수동 정렬 모드의 같은 컬럼 reorder dragover 시 삽입 위치 인디케이터 배치.
     * Y 좌표 기준 target index 계산 후 zone 내부에 indicator element 를 insert/move.
     */
    function placeDropIndicator(zone, clientY) {
      const cards = Array.from(zone.querySelectorAll('.card[data-num]'))
        .filter(function (c) { return c.dataset.num !== draggedNum; });
      let targetIdx = cards.length;
      for (let i = 0; i < cards.length; i++) {
        const rect = cards[i].getBoundingClientRect();
        if (clientY < rect.top + rect.height / 2) {
          targetIdx = i;
          break;
        }
      }
      let indicator = zone.querySelector('.card-drop-indicator');
      if (!indicator) {
        indicator = document.createElement('div');
        indicator.className = 'card-drop-indicator';
      }
      if (targetIdx >= cards.length) {
        zone.appendChild(indicator);
      } else if (cards[targetIdx].previousSibling !== indicator) {
        zone.insertBefore(indicator, cards[targetIdx]);
      }
    }

    el.querySelectorAll(".cards-droppable").forEach(function (zone) {
      zone.addEventListener("dragover", function (e) {
        if (!draggedNum) return;
        // 유효하지 않은 전이는 drop 자체 거부 (preventDefault 미호출 → 브라우저가 drop 차단)
        if (!isValidDropTarget(draggedFrom, zone.dataset.colKey)) {
          e.dataTransfer.dropEffect = "none";
          return;
        }
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        zone.classList.add("dragover-active");
        // To Do 수동 정렬 + 같은 컬럼 drag — 삽입 위치 인디케이터 표시
        if (zone.dataset.colKey === "To Do" && draggedFrom === "To Do"
            && kanbanSort["To Do"] && kanbanSort["To Do"].key === "manual") {
          placeDropIndicator(zone, e.clientY);
        }
      });
      zone.addEventListener("dragleave", function (e) {
        // 진짜로 zone 밖으로 나갈 때만 정리 (자식 element 진입은 무시)
        if (!e.relatedTarget || !zone.contains(e.relatedTarget)) {
          zone.classList.remove("dragover-active");
          const ind = zone.querySelector('.card-drop-indicator');
          if (ind) ind.remove();
        }
      });
      zone.addEventListener("drop", function (e) {
        e.preventDefault();
        zone.classList.remove("dragover-active");
        const targetCol = zone.dataset.colKey;
        if (!draggedNum || !targetCol) return;
        // 같은 컬럼 내 drop: To Do 수동 정렬 모드만 지원, 나머지는 무시
        if (targetCol === draggedFrom) {
          if (targetCol === "To Do" && kanbanSort["To Do"] && kanbanSort["To Do"].key === "manual") {
            const cards = Array.from(zone.querySelectorAll('.card[data-num]'))
              .filter(function (c) { return c.dataset.num !== draggedNum; });
            let targetIdx = cards.length;
            for (let i = 0; i < cards.length; i++) {
              const rect = cards[i].getBoundingClientRect();
              if (e.clientY < rect.top + rect.height / 2) {
                targetIdx = i;
                break;
              }
            }
            reorderTodoManualOrder(draggedNum, targetIdx);
            renderKanban();
          }
          return;
        }

        // T-399: In Progress drop 분기 — Open 카드만 허용 + confirm 모달
        // Review 카드를 Done 이외 컬럼으로 drop 시도 — 차단
        // T-418: Open 카드를 Done 이외 컬럼으로 drop 시도 시 기존 To Do ↔ Open 전이 로직으로 처리
        if (draggedFrom === "Review" && targetCol !== "Done" && targetCol !== "Open") {
          alert("Review 카드는 Done 또는 Open 컬럼으로만 드래그할 수 있습니다.");
          renderKanban();
          return;
        }

        if (targetCol === "In Progress") {
          if (draggedFrom !== "Open") {
            // To Do 등 다른 컬럼에서 직접 In Progress 이동은 차단
            alert("To Do 카드는 직접 In Progress 로 옮길 수 없습니다. 먼저 Open 으로 이동하세요.");
            renderKanban();
            return;
          }
          const ticketObj = (Board.state.TICKETS || []).find(function (t) {
            return t.number === draggedNum;
          });
          if (!ticketObj) {
            renderKanban();
            return;
          }
          const command = ticketObj.command || "implement";
          showSubmitConfirmModal(
            ticketObj,
            function () {
              // [실행] 콜백: POST /api/kanban/submit → launcher 호출
              fetch("/api/kanban/submit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ticket: ticketObj.number, command: command }),
              }).then(function (res) {
                if (!res.ok) {
                  return res.json().then(function (j) {
                    throw new Error(j.error || res.statusText);
                  });
                }
                return res.json();
              }).then(function () {
                fetchTickets().then(function () { renderKanban(); });
              }).catch(function (err) {
                console.error("[kanban DnD] submit failed:", err);
                alert("워크플로우 실행 실패: " + err.message);
                renderKanban();
              });
            },
            function () {
              // [취소]/ESC/overlay 콜백: 카드 원위치 복귀
              renderKanban();
            }
          );
          return;
        } else if (targetCol === "Done") {
          // T-906: Review → Done drop 분기
          // T-418: Open → Done 직접 전이 분기 추가
          if (draggedFrom !== "Review" && draggedFrom !== "Open") {
            alert("Review 또는 Open 카드만 Done 으로 드래그할 수 있습니다.");
            renderKanban();
            return;
          }
          const doneTicketObj = (Board.state.TICKETS || []).find(function (t) {
            return t.number === draggedNum;
          });
          if (!doneTicketObj) {
            renderKanban();
            return;
          }
          // dragend 가 modal 콜백 실행 전 발생해 draggedNum=null 로 reset 되는 회귀 차단:
          // ticket 번호를 closure 캡처 변수로 보존
          const capturedNum = draggedNum;

          if (draggedFrom === "Open") {
            // T-418: Open → Done 직접 전이 (force=true)
            function callOpenDoneDnd(forceDirty) {
              fetch("/api/kanban/done", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ticket: capturedNum, force: true, force_dirty: forceDirty }),
              }).then(function (res) {
                return res.json().then(function (body) {
                  return { res: res, body: body };
                });
              }).then(function (r) {
                if (r.res.ok && r.body.ok) {
                  showOpenDoneResultModal("success", r.body, function () {
                    fetchTickets().then(renderKanban);
                  });
                } else {
                  const kind = r.body.error_kind === "dirty_worktree" ? "dirty" : "error";
                  showOpenDoneResultModal(kind, r.body, function () {
                    renderKanban();
                  }, kind === "dirty" ? function () {
                    callOpenDoneDnd(true);
                  } : undefined);
                }
              }).catch(function (err) {
                console.error("[kanban DnD] open-done failed:", err);
                showOpenDoneResultModal("error", { message: err.message }, function () { renderKanban(); });
              });
            }
            showOpenDoneConfirmModal(
              doneTicketObj,
              function (forceDirty) {
                callOpenDoneDnd(forceDirty);
              },
              function () {
                // [취소]/ESC/overlay 콜백: 카드 원위치 복귀
                renderKanban();
              }
            );
          } else {
            // T-906: Review → Done drop (기존 로직)
            showDoneConfirmModal(
              doneTicketObj,
              function () {
                // [완료 처리] 콜백: POST /api/kanban/done → cmd_done 위임
                fetch("/api/kanban/done", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ ticket: capturedNum }),
                }).then(function (res) {
                  return res.json().then(function (body) {
                    return { res: res, body: body };
                  });
                }).then(function (r) {
                  if (r.res.ok && r.body.ok) {
                    showDoneResultModal("success", r.body, function () {
                      fetchTickets().then(renderKanban);
                    });
                  } else {
                    const kind = r.body.error_kind === "merge_conflict" ? "conflict"
                      : r.body.error_kind === "dirty_worktree" ? "dirty"
                      : "error";
                    showDoneResultModal(kind, r.body, function () { renderKanban(); });
                  }
                }).catch(function (err) {
                  console.error("[kanban DnD] done failed:", err);
                  showDoneResultModal("error", { message: err.message }, function () { renderKanban(); });
                });
              },
              function () {
                // [취소]/ESC/overlay 콜백: 카드 원위치 복귀
                renderKanban();
              }
            );
          }
          return;
        }

        // To Do 는 Open 으로만 이동 허용 (Review/그 외 차단)
        if (draggedFrom === "To Do" && targetCol !== "Open") {
          alert("To Do 카드는 Open 컬럼으로만 드래그할 수 있습니다.");
          renderKanban();
          return;
        }

        // To Do ↔ Open ↔ Review 단순 전이 (Open → Review 직접 이동 포함)
        const moveToMap = { "To Do": "todo", "Open": "open", "Review": "review" };
        const to = moveToMap[targetCol];
        if (!to) {
          console.error("[kanban DnD] unknown target column:", targetCol);
          renderKanban();
          return;
        }
        fetch("/api/kanban/move", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticket: draggedNum, to: to }),
        }).then(function (res) {
          if (!res.ok) return res.json().then(function (j) { throw new Error(j.error || res.statusText); });
          return res.json();
        }).then(function () {
          fetchTickets().then(function () { renderKanban(); });
        }).catch(function (err) {
          console.error("[kanban DnD] move failed:", err);
          alert("티켓 이동 실패: " + err.message);
        });
      });
    });
  }

  /** Renders the kanban board with columns, cards, and sort controls. */
  function renderKanban() {
    const el = document.getElementById("view-kanban");
    // 컬럼별 스크롤 위치 캡처 — innerHTML 교체로 잃어버리는 scrollTop 복원용
    const scrollPositions = {};
    el.querySelectorAll(".cards[data-col-key]").forEach(function (cards) {
      scrollPositions[cards.dataset.colKey] = cards.scrollTop;
    });
    let h = '<div class="kanban-board">';
    COLUMNS.forEach(function (col) {
      const items = Board.state.TICKETS.filter(function (t) {
        if (col.key === "To Do") { return t.status === "To Do"; }
        if (col.key === "Open") { return t.status === "Open"; }
        return t.status === col.key;
      });
      const colSort = kanbanSort[col.key] || { key: "number", dir: "asc" };
      const isManualTodo = (col.key === "To Do" && colSort.key === "manual");
      const sortedItems = isManualTodo
        ? applyTodoManualOrder(items)
        : sortTickets(items, colSort.key, colSort.dir);
      const sortIcon = colSort.dir === "desc" ? SVG_DESC : SVG_ASC;

      // Build dropdown options HTML
      // To Do 컬럼은 "수동" 옵션을 맨 앞에 추가 (수동이 기본 정렬)
      let dropHtml = '<div class="col-sort-dropdown" data-col="' + esc(col.key) + '">';
      const sortKeysForCol = (col.key === "To Do")
        ? [{ key: "manual", label: "수동" }].concat(SORT_KEYS)
        : SORT_KEYS;
      sortKeysForCol.forEach(function (opt) {
        const isActive = (opt.key === colSort.key) ? " active" : "";
        dropHtml += '<button class="col-sort-option' + isActive + '"'
          + ' data-col="' + esc(col.key) + '"'
          + ' data-sort-key="' + esc(opt.key) + '">'
          + esc(opt.label) + '</button>';
      });
      dropHtml += '<div class="col-sort-divider"></div>';
      SORT_DIRS.forEach(function (opt) {
        const isActive = (opt.dir === colSort.dir) ? " active" : "";
        dropHtml += '<button class="col-sort-option' + isActive + '"'
          + ' data-col="' + esc(col.key) + '"'
          + ' data-sort-dir="' + esc(opt.dir) + '">'
          + esc(opt.label) + '</button>';
      });
      dropHtml += '</div>';

      // Done / To Do 컬럼은 접기 토글 지원
      const isCollapsible = COLLAPSIBLE_COLUMNS.has(col.key);
      const isCollapsed = isCollapsible && loadColumnCollapsed(col.key);
      const chevronSvg = isCollapsible
        ? (isCollapsed
          ? '<svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M4 2L8 6L4 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>'
          : '<svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M2 4L6 8L10 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>')
        : "";

      const columnCollapsedClass = isCollapsed ? " collapsed" : "";
      h += '<div class="column' + columnCollapsedClass + '" data-col-key="' + esc(col.key) + '">';

      if (isCollapsed) {
        // 접힌 상태: 세로 바 렌더링
        h += '<div class="column-collapsed-bar" data-col-key="' + esc(col.key) + '">';
        h += '<span class="bar-label">' + esc(col.label) + '</span>';
        h += '<span class="bar-count">' + items.length + '</span>';
        h += '</div>';
      } else {
        // 펼친 상태: 기존 헤더 + 카드 렌더링
        h += '<div class="col-header">';
        h += '<span class="col-dot ' + col.dot + '"></span>';
        h += '<div class="col-sort-wrapper">';
        h += '<button class="col-sort-btn" data-col="' + esc(col.key) + '" title="\uC815\uB82C">' + sortIcon + '</button>';
        h += dropHtml;
        h += '</div>';
        h += esc(col.label);
        h += '<span class="col-count">' + items.length + "</span>";
        if (isCollapsible) {
          h += '<button class="column-toggle-btn" data-col-key="' + esc(col.key) + '" title="\uC811\uAE30">' + chevronSvg + '</button>';
        }
        h += "</div>";
        // DnD drop target: To Do / Open 컬럼만 cards-droppable 클래스 부여
        // T-399: In Progress 도 drop target 으로 추가 (Open → In Progress 만 confirm 모달로 허용).
        // T-906: Done 도 drop target 으로 추가 (Review → Done drop 만 confirm 모달로 허용).
        // Open → Review 직접 전이 추가: Review 도 drop target.
        const isDroppable = (col.key === "To Do" || col.key === "Open" || col.key === "In Progress" || col.key === "Done" || col.key === "Review");
        const droppableClass = isDroppable ? ' cards-droppable' : '';
        h += '<div class="cards' + droppableClass + '" data-col-key="' + esc(col.key) + '">';
        if (sortedItems.length === 0) {
          h += '<div class="empty">No items</div>';
        } else {
          sortedItems.forEach(function (t) {
            const done = col.key === "Done" ? " done" : "";
            const status = getWorkflowStatus(t);
            // DnD: To Do / Open 컬럼 카드만 draggable.
            // T-399: In Progress 카드 drag 불가는 의도된 보호 (워크플로우 취소 부수효과 차단).
            // T-906: Review 카드 draggable 추가 (Review → Done drop 허용).
            // Done 카드는 draggable=false (부수효과 보호).
            const isDraggable = (col.key === "To Do" || col.key === "Open" || col.key === "Review");
            const draggableAttr = isDraggable ? ' draggable="true"' : '';
            const draggableClass = isDraggable ? ' card-draggable' : '';
            // T-433 Phase 2: Review 카드에 한해 has-active-branch 클래스 부여 (외곽 glow 시각).
            const branchActiveClass = (col.key === "Review" && _activeBranchTicket === t.number) ? ' has-active-branch' : '';
            h += '<div class="card' + done + draggableClass + branchActiveClass + '" data-num="' + esc(t.number) + '" data-col-key="' + esc(col.key) + '"' + draggableAttr + '>';
            // 상단: 좌측 그룹(티켓번호 + 커맨드배지), 우측 상태라벨
            h += '<div class="card-top">';
            h += '<div class="card-top-left">';
            h += '<span class="card-num">' + esc(t.number.replace(/^T-/, "")) + "</span>";
            if (t.command && t.command.indexOf(">") !== -1) {
              h += renderChainIcons(t);
            } else if (t.command) {
              var badgeAnim = (t.status === "In Progress") ? "animation:chain-pulse 1.5s ease-in-out infinite" : "";
              h += badge(t.command, CMD_COLORS[t.command], badgeAnim);
            }
            h += "</div>";
            h += '<div class="card-top-right">';
            if (col.key === "To Do" && status) {
              h += '<span class="card-status ' + status.cssClass + '">' + status.label + "</span>";
            }
            h += renderUncommittedBadge(t.number);
            // T-457 (Layer 3): failure tag (ticket.failure 존재 시) — 가드는 헬퍼 내부
            h += renderFailureTag(t);
            // T-441: Done 카드 verdict 배지 (advisory)
            if (col.key === "Done") {
              h += renderDoneVerdictBadge(t.number);
            }
            h += "</div>";
            h += "</div>";
            // 2행: 제목 (2줄 clamp)
            h += '<div class="card-mid"><div class="card-title">' + esc(t.title || "(No title)") + "</div></div>";
            // 3행: 관계 & 종속 (없어도 자리 보존)
            h += '<div class="card-relations-row">';
            const hasRelations = t.relations && t.relations.length > 0;
            if (hasRelations) {
              h += renderRelations(t);
            }
            h += '</div>';
            // 4행: Action 버튼 (없어도 자리 보존, 카드 높이 일정 유지)
            h += '<div class="card-actions-row">';
            // T-457 (Layer 3): 미커밋 워크트리 commit 액션 버튼 — 어느 컬럼이든 미커밋 있으면 표시.
            // flex-end + 좌→우 추가 순서로 commit 이 왼쪽, done 이 가장 우측에 위치.
            if (_worktreeUncommittedMap) {
              var uitem = _worktreeUncommittedMap.get(t.number);
              if (uitem && uitem.uncommitted_count > 0) {
                var ctip = "미커밋 " + uitem.uncommitted_count + "건 — 클릭하면 자동 commit";
                h += '<button class="card-commit-action" data-commit-ticket="' + esc(t.number) + '" title="' + esc(ctip) + '" draggable="false">';
                // SVG (자체 그림 — 외부 라이브러리 금지 룰): commit graph dot 모티프 (원 + 위/아래 짧은 선)
                h += '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">';
                h += '<circle cx="7" cy="7" r="2.4" stroke="currentColor" stroke-width="1.6" fill="none"/>';
                h += '<line x1="7" y1="0.5" x2="7" y2="4.0" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>';
                h += '<line x1="7" y1="10.0" x2="7" y2="13.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>';
                h += '</svg>';
                h += '</button>';
              }
            }
            if (col.key === "Review") {
              // T-433 Phase 2: feature 브랜치 활성/해제 토글 버튼 (4행 좌측, done 버튼 좌측에 배치).
              // OFF: 회색 outline / ON: 테라코타 채움 + 카드 외곽 light glow.
              // 한 카드만 active 보장 — _activeBranchTicket 상태 기준 .active 부여.
              var isBranchActive = (_activeBranchTicket === t.number);
              var toggleClass = isBranchActive ? " active" : "";
              var toggleTip = isBranchActive
                ? "feature 브랜치 활성 중 — 클릭하면 develop 으로 복귀"
                : "클릭하면 메인 working tree 를 이 feature 브랜치로 전환";
              h += '<button class="card-branch-toggle' + toggleClass + '" data-branch-ticket="' + esc(t.number) + '" title="' + esc(toggleTip) + '" draggable="false">';
              // Lucide git-branch SVG (16px, currentColor) — e749003 어휘 일치
              h += '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">';
              h += '<line x1="6" y1="3" x2="6" y2="15"/>';
              h += '<circle cx="18" cy="6" r="3"/>';
              h += '<circle cx="6" cy="18" r="3"/>';
              h += '<path d="M18 9a9 9 0 0 1-9 9"/>';
              h += '</svg>';
              h += '</button>';
              h += '<button class="card-done-action" data-num="' + esc(t.number) + '" title="완료 처리" draggable="false">';
              h += '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">';
              h += '<polyline points="2,7 5.5,10.5 12,3.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>';
              h += '</svg>';
              h += '</button>';
            }
            h += "</div>";
            h += "</div>";
          });
        }
        h += "</div>";
      }

      h += "</div>";
    });
    h += "</div>";
    el.innerHTML = h;

    // 캡처된 컬럼별 scrollTop 복원
    Object.keys(scrollPositions).forEach(function (colKey) {
      const cards = el.querySelector('.cards[data-col-key="' + colKey + '"]');
      if (cards) cards.scrollTop = scrollPositions[colKey];
    });

    // Bind card clicks
    el.querySelectorAll(".card").forEach(function (card) {
      card.addEventListener("click", function (e) {
        // T-457 (Layer 3): 4행 commit 버튼 클릭 → 워크트리 자동 commit 액션 위임.
        // (1행 .card-uncommitted-badge 는 read-only 표시 라벨로 변경됨 — 클릭 트리거 없음)
        var commitBtn = e.target.closest(".card-commit-action");
        if (commitBtn) {
          e.stopPropagation();
          handleCommitButtonClick(commitBtn);
          return;
        }
        // T-433 Phase 2: Review 카드 4행 feature 브랜치 토글 버튼 클릭 → handleBranchToggleClick 위임
        var branchToggle = e.target.closest(".card-branch-toggle");
        if (branchToggle) {
          e.stopPropagation();
          var bnum = branchToggle.dataset.branchTicket || card.dataset.num;
          handleBranchToggleClick(bnum);
          return;
        }
        // T-439: Review 카드 우하단 완료 액션 버튼 클릭 → handleReviewDoneAction 위임
        var doneAction = e.target.closest(".card-done-action");
        if (doneAction) {
          e.stopPropagation();
          const num = card.dataset.num;
          const ticket = Board.state.TICKETS.find(function (t) { return t.number === num; });
          if (ticket) handleReviewDoneAction(ticket);
          return;
        }
        // T-441: Done 카드 verdict FAIL 배지 클릭 → 상세 메시지 표시 (advisory)
        var verdictFail = e.target.closest(".card-done-verdict.verdict-fail");
        if (verdictFail) {
          e.stopPropagation();
          var ticketNum = card.dataset.num;
          var msg = verdictFail.dataset.verdictMsg || "develop HEAD 가 머지 commit 아님";
          var verdictData = ticketNum ? _doneVerdictMap[ticketNum] : null;
          var detail = (verdictData && verdictData.details) || {};
          var fullMsg = "[T-441 머지 정합성 FAIL]\n\n" + msg;
          if (detail.develop_head) fullMsg += "\n\ndevelop HEAD : " + detail.develop_head.slice(0, 8);
          if (detail.merge_commit) fullMsg += "\nmerge commit: " + detail.merge_commit.slice(0, 8);
          fullMsg += "\n\n이 티켓의 변경분이 develop 에 정상 반영되지 않았을 수 있습니다.\n※ advisory only — 자동 재머지 없음. 수동으로 확인하세요.";
          alert(fullMsg);
          return;
        }
        const num = card.dataset.num;
        const ticket = Board.state.TICKETS.find(function (t) { return t.number === num; });
        if (ticket) Board.render.openViewer(ticket);
      });
    });

    // T-905 Phase 3: Done 컬럼 카드에 우클릭 컨텍스트 메뉴 바인딩 ("Review 로 롤백")
    el.querySelectorAll('.card[data-col-key="Done"]').forEach(function (card) {
      card.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        const num = card.dataset.num;
        const ticket = Board.state.TICKETS.find(function (t) { return t.number === num; });
        if (ticket) showDoneCardContextMenu(e, ticket);
      });
    });

    // T-441: Done 카드 verdict fetch 트리거 (advisory)
    el.querySelectorAll('.card[data-col-key="Done"]').forEach(function (card) {
      var num = card.dataset.num;
      if (num) {
        // 미조회 카드만 fetch (캐시 히트 시 스킵)
        fetchAndRenderVerdict(num);
      }
    });

    // T-418: Open 컬럼 카드에 우클릭 컨텍스트 메뉴 바인딩 ("Done 으로 완료(직접)" + "삭제")
    el.querySelectorAll('.card[data-col-key="Open"]').forEach(function (card) {
      card.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const num = card.dataset.num;
        const ticket = Board.state.TICKETS.find(function (t) { return t.number === num; });
        if (ticket) showOpenCardContextMenu(e, ticket);
      });
    });

    // Review 컬럼 카드에 우클릭 컨텍스트 메뉴 바인딩 ("Open 으로 재작업" 단일 옵션)
    el.querySelectorAll('.card[data-col-key="Review"]').forEach(function (card) {
      card.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const num = card.dataset.num;
        const ticket = Board.state.TICKETS.find(function (t) { return t.number === num; });
        if (ticket) showReviewCardContextMenu(e, ticket);
      });
    });

    // ── DnD: To Do ↔ Open 카드 드래그 앤 드랍 ──
    // 안전 DnD 정책: 부수 효과 없는 전이만 허용 (In Progress / Done 은 별도 명령)
    // T-418: Open → Done 직접 전이도 confirm 모달로 허용 (force=true)
    bindKanbanDnd(el);

    // Bind sort button clicks (toggle dropdown)
    el.querySelectorAll(".col-sort-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        const dropdown = btn.parentNode.querySelector(".col-sort-dropdown");
        const isOpen = dropdown.classList.contains("open");
        el.querySelectorAll(".col-sort-dropdown.open").forEach(function (d) {
          d.classList.remove("open");
        });
        if (!isOpen) {
          dropdown.classList.add("open");
        }
      });
    });

    // Bind sort option clicks
    el.querySelectorAll(".col-sort-option").forEach(function (opt) {
      opt.addEventListener("click", function (e) {
        e.stopPropagation();
        const colKey = opt.dataset.col;
        const current = kanbanSort[colKey] || { key: "number", dir: "asc" };
        if (opt.dataset.sortKey && !opt.dataset.sortDir) {
          kanbanSort[colKey] = { key: opt.dataset.sortKey, dir: current.dir };
        } else if (opt.dataset.sortDir && !opt.dataset.sortKey) {
          kanbanSort[colKey] = { key: current.key, dir: opt.dataset.sortDir };
        }
        saveKanbanSort();
        renderKanban();
      });
    });

    // Bind collapse toggle buttons (펼친 상태 → 접기). Done/To Do 공통.
    el.querySelectorAll(".column-toggle-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        const colKey = btn.dataset.colKey;
        if (!colKey) return;
        saveColumnCollapsed(colKey, !loadColumnCollapsed(colKey));
        renderKanban();
      });
    });

    // Bind collapsed bar click (접힌 상태 → 펼치기). Done/To Do 공통.
    el.querySelectorAll(".column-collapsed-bar").forEach(function (bar) {
      bar.addEventListener("click", function (e) {
        e.stopPropagation();
        const colKey = bar.dataset.colKey;
        if (!colKey) return;
        saveColumnCollapsed(colKey, false);
        renderKanban();
      });
    });

    // Close dropdowns on outside click
    const outsideHandler = function (e) {
      if (!e.target.closest(".col-sort-wrapper")) {
        el.querySelectorAll(".col-sort-dropdown.open").forEach(function (d) {
          d.classList.remove("open");
        });
      }
    };
    document.addEventListener("click", outsideHandler);
    if (el._sortOutsideHandler) {
      document.removeEventListener("click", el._sortOutsideHandler);
    }
    el._sortOutsideHandler = outsideHandler;

    // T-433 Phase 2: 페이지 로드 시 1회 active branch 초기 fetch (이후 호출은 가드로 무시).
    // SSE git_branch 이벤트 도착 시 syncActiveBranchFromSSE 가 동기화 담당.
    fetchAndApplyActiveBranch();
  }

  // ── Register on Board namespace ──
  Board.fetch.fetchTickets = fetchTickets;
  Board.fetch.fetchTicketsByFiles = fetchTicketsByFiles;
  Board.render.renderKanban = renderKanban;
  // T-433 Phase 2: SSE git_branch 이벤트 listener 가 호출하는 동기화 entry-point.
  // (sse.js 가 단일 listener — addEventListener 중복 등록 방지 §2.4)
  Board.render.syncActiveBranchFromSSE = syncActiveBranchFromSSE;
})();
