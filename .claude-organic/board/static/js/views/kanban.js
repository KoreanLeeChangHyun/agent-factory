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

  // ── Kanban Sort State ──

  /** Loads persisted kanban sort state from localStorage. */
  function loadKanbanSort() {
    const defaults = {};
    COLUMNS.forEach(function (col) {
      defaults[col.key] = { key: "number", dir: "asc" };
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

  // ── Worktree Status Cache ──
  // 1 fetch per renderKanban cycle. null = not yet loaded (graceful: badge omitted).
  var _worktreeStatusMap = null;

  /**
   * Fetches /api/worktree/status/all and populates _worktreeStatusMap.
   * Silently degrades on error (map remains null or stale).
   * @returns {Promise<void>}
   */
  function fetchAndCacheWorktreeStatus() {
    return fetch("/api/worktree/status/all", { cache: "no-store" }).then(function (res) {
      if (!res.ok) return;
      return res.json().then(function (list) {
        if (!Array.isArray(list)) return;
        var map = new Map();
        list.forEach(function (item) {
          if (item && item.ticket) map.set(item.ticket, item);
        });
        _worktreeStatusMap = map;
      });
    }).catch(function () {
      // API unavailable (worktree mode off, etc.) — leave map unchanged
    });
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
      // Co-fetch worktree status so renderKanban always has fresh data.
      // fetchAndCacheWorktreeStatus is fire-and-forget w.r.t. error handling.
      return fetchAndCacheWorktreeStatus().then(
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
   * 날짜 문자열을 한국어 형식의 날짜/시간 분리 객체로 변환한다.
   * @param {string} datetimeStr - "YYYY-MM-DD HH:MM:SS" 형식 날짜 문자열
   * @returns {{ datePart: string, timePart: string }} 날짜 파트와 시간 파트 객체
   */
  function formatKoreanDate(datetimeStr) {
    if (!datetimeStr) { return { datePart: "", timePart: "" }; }
    const parts = datetimeStr.split(" ");
    if (parts.length < 2) { return { datePart: datetimeStr, timePart: "" }; }
    const dateParts = parts[0].split("-");
    const timeParts = parts[1].split(":");
    if (dateParts.length < 3 || timeParts.length < 2) { return { datePart: datetimeStr, timePart: "" }; }
    const year = parseInt(dateParts[0], 10);
    const month = parseInt(dateParts[1], 10);
    const day = parseInt(dateParts[2], 10);
    const hour24 = parseInt(timeParts[0], 10);
    const minute = timeParts[1];
    const ampm = hour24 < 12 ? "\uC624\uC804" : "\uC624\uD6C4"; // 오전/오후
    let hour12 = hour24 % 12;
    if (hour12 === 0) { hour12 = 12; }
    return {
      datePart: `${year}\uB144 ${month}\uC6D4 ${day}\uC77C`,
      timePart: `${ampm} ${hour12}\uC2DC ${minute}\uBD84`,
    };
  }

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
   * T-419: 워크트리 상태 배지 HTML을 생성한다.
   * 작업물이 있는 티켓(uncommitted_count > 0 || feature_commits > 0 || lock)만 표시.
   * @param {string} ticketNum - 티켓 번호 (예: "T-419")
   * @returns {string} span.card-worktree-badge HTML 또는 빈 문자열
   */
  function renderWorktreeBadge(ticketNum) {
    if (!_worktreeStatusMap) return "";
    var st = _worktreeStatusMap.get(ticketNum);
    if (!st) return "";
    var hasWork = st.lock || (st.uncommitted_count > 0) || (st.feature_commits > 0);
    if (!hasWork) return "";

    var parts = [];
    if (st.lock) {
      parts.push("wt locked");
    } else {
      if (st.uncommitted_count > 0) parts.push("wt " + st.uncommitted_count + "M");
      if (st.feature_commits > 0) parts.push((parts.length > 0 ? "/ " : "wt ") + st.feature_commits + "c");
    }
    var label = parts.join(" ");

    var tooltip = [
      "branch: " + (st.branch || ""),
      "head: " + (st.head || ""),
      "uncommitted: " + (st.uncommitted_count || 0),
      "commits ahead: " + (st.feature_commits || 0),
      "locked: " + (!!st.lock),
    ].join(" | ");

    return '<span class="card-worktree-badge" title="' + esc(tooltip) + '">' + esc(label) + "</span>";
  }

  /**
   * 티켓의 status를 기반으로 상태 라벨 정보를 반환한다.
   * status가 "To Do"인 경우 TODO 라벨, 그 외 모든 경우 OPEN 라벨을 반환한다.
   * T-399: Submit transient 단계 제거됨.
   * @param {Object} ticket - 티켓 객체
   * @returns {{ label: string, cssClass: string }} 상태 라벨과 CSS 클래스
   */
  function getWorkflowStatus(ticket) {
    if (ticket && ticket.status === "To Do") {
      return { label: "TODO", cssClass: "status-todo" };
    }
    return { label: "OPEN", cssClass: "status-open" };
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

    if (kind === "success" && !payload.merge_commit) {
      console.warn("[showDoneResultModal] success kind with empty merge_commit — converting to error");
      kind = "error";
      payload = Object.assign({}, payload, {
        message: "백엔드 응답 형식 오류 — merge_commit 누락. flow-kanban 출력을 확인하세요."
      });
    }

    if (kind === "success") {
      title.textContent = "Done 처리 완료";
      const msg = document.createElement("p");
      const ticketStr = (payload.ticket || "") + ": " + (payload.merged_branch || "") + " → develop 병합 완료 (" + (payload.merge_commit || "") + ")";
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
        card.classList.add("card-dragging");
      });
      card.addEventListener("dragend", function () {
        card.classList.remove("card-dragging");
        el.querySelectorAll(".cards-droppable.dragover-active").forEach(function (z) {
          z.classList.remove("dragover-active");
        });
        draggedNum = null;
        draggedFrom = null;
      });
    });

    el.querySelectorAll(".cards-droppable").forEach(function (zone) {
      zone.addEventListener("dragover", function (e) {
        if (!draggedNum) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        zone.classList.add("dragover-active");
      });
      zone.addEventListener("dragleave", function (e) {
        if (e.target === zone) zone.classList.remove("dragover-active");
      });
      zone.addEventListener("drop", function (e) {
        e.preventDefault();
        zone.classList.remove("dragover-active");
        const targetCol = zone.dataset.colKey;
        if (!draggedNum || !targetCol) return;
        if (targetCol === draggedFrom) return; // 같은 컬럼 내 drop 은 무시 (정렬 미지원)

        // T-399: In Progress drop 분기 — Open 카드만 허용 + confirm 모달
        // Review 카드를 Done 이외 컬럼으로 drop 시도 — 차단
        if (draggedFrom === "Review" && targetCol !== "Done") {
          alert("Review 카드는 Done 컬럼으로만 드래그할 수 있습니다.");
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
          // T-906: Review → Done drop 분기 — Review 카드만 허용 + confirm 모달
          if (draggedFrom !== "Review") {
            alert("Review 카드만 Done 으로 드래그할 수 있습니다.");
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
          showDoneConfirmModal(
            doneTicketObj,
            function () {
              // [완료 처리] 콜백: POST /api/kanban/done → cmd_done 위임
              fetch("/api/kanban/done", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ticket: draggedNum }),
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
          return;
        }

        // To Do ↔ Open 단순 전이
        const to = (targetCol === "To Do") ? "todo" : "open";
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
    let h = '<div class="kanban-board">';
    COLUMNS.forEach(function (col) {
      const items = Board.state.TICKETS.filter(function (t) {
        if (col.key === "To Do") { return t.status === "To Do"; }
        if (col.key === "Open") { return t.status === "Open"; }
        return t.status === col.key;
      });
      const colSort = kanbanSort[col.key] || { key: "number", dir: "asc" };
      const sortedItems = sortTickets(items, colSort.key, colSort.dir);
      const sortIcon = colSort.dir === "desc" ? SVG_DESC : SVG_ASC;

      // Build dropdown options HTML
      let dropHtml = '<div class="col-sort-dropdown" data-col="' + esc(col.key) + '">';
      SORT_KEYS.forEach(function (opt) {
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
        const isDroppable = (col.key === "To Do" || col.key === "Open" || col.key === "In Progress" || col.key === "Done");
        const droppableClass = isDroppable ? ' cards-droppable' : '';
        h += '<div class="cards' + droppableClass + '" data-col-key="' + esc(col.key) + '">';
        if (sortedItems.length === 0) {
          h += '<div class="empty">No items</div>';
        } else {
          sortedItems.forEach(function (t) {
            const done = col.key === "Done" ? " done" : "";
            const status = getWorkflowStatus(t);
            const dateObj = formatKoreanDate(t.updated || t.created);
            // DnD: To Do / Open 컬럼 카드만 draggable.
            // T-399: In Progress 카드 drag 불가는 의도된 보호 (워크플로우 취소 부수효과 차단).
            // T-906: Review 카드 draggable 추가 (Review → Done drop 허용).
            // Done 카드는 draggable=false (부수효과 보호).
            const isDraggable = (col.key === "To Do" || col.key === "Open" || col.key === "Review");
            const draggableAttr = isDraggable ? ' draggable="true"' : '';
            const draggableClass = isDraggable ? ' card-draggable' : '';
            h += '<div class="card' + done + draggableClass + '" data-num="' + esc(t.number) + '" data-col-key="' + esc(col.key) + '"' + draggableAttr + '>';
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
            if (col.key === "Open" || col.key === "To Do") {
              h += '<span class="card-status ' + status.cssClass + '">' + status.label + "</span>";
            }
            h += "</div>";
            // 중단: 제목 (2줄 clamp)
            h += '<div class="card-mid"><div class="card-title">' + esc(t.title || "(No title)") + "</div></div>";
            // 하단: 왼쪽(체인/관계) + 오른쪽(날짜)
            h += '<div class="card-bottom">';
            h += '<div class="card-bottom-left">';
            const hasRelations = t.relations && t.relations.length > 0;
            if (hasRelations) {
              h += renderRelations(t);
            }
            h += renderWorktreeBadge(t.number);
            h += '</div>';
            h += '<div class="card-bottom-right">';
            h += '<div class="card-date">' + esc(dateObj.datePart) + "</div>";
            h += '<div class="card-time">' + esc(dateObj.timePart) + "</div>";
            h += '</div>';
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

    // Bind card clicks
    el.querySelectorAll(".card").forEach(function (card) {
      card.addEventListener("click", function () {
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

    // ── DnD: To Do ↔ Open 카드 드래그 앤 드랍 ──
    // 안전 DnD 정책: 부수 효과 없는 전이만 허용 (In Progress / Done 은 별도 명령)
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
  }

  // ── Register on Board namespace ──
  Board.fetch.fetchTickets = fetchTickets;
  Board.fetch.fetchTicketsByFiles = fetchTicketsByFiles;
  Board.render.renderKanban = renderKanban;
})();
