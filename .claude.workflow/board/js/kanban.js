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

  // ── Done Column Collapsed State ──
  const DONE_COLLAPSED_LS_KEY = "claude-board-done-collapsed";

  /** Loads Done column collapsed state from localStorage. Default: false (expanded). */
  function loadDoneCollapsed() {
    try {
      const stored = localStorage.getItem(DONE_COLLAPSED_LS_KEY);
      if (stored !== null) return stored === "true";
    } catch (e) {}
    return false;
  }

  /** Persists Done column collapsed state to localStorage. */
  function saveDoneCollapsed(collapsed) {
    try {
      localStorage.setItem(DONE_COLLAPSED_LS_KEY, String(collapsed));
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
   * Returns the most recent datetime from a ticket's history/submit entries.
   * @param {Object} t - Ticket object
   * @returns {string} Most recent datetime string
   */
  function getModifiedDate(t) {
    const candidates = [];
    if (candidates.length === 0) return t.datetime || "";
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
        av = a.datetime || "";
        bv = b.datetime || "";
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
    }).catch(function () { return []; });
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
   * 티켓의 status와 editing 플래그를 기반으로 상태 라벨 정보를 반환한다.
   * status가 "Submit"인 경우 SUBMIT 라벨을 반환한다.
   * editing 플래그가 true인 경우 EDIT 라벨을 반환한다.
   * 그 외 모든 경우 OPEN 라벨을 반환한다.
   * @param {Object} ticket - 티켓 객체
   * @returns {{ label: string, cssClass: string }} 상태 라벨과 CSS 클래스
   */
  function getWorkflowStatus(ticket) {
    if (ticket && ticket.status === "Submit") {
      return { label: "SUBMIT", cssClass: "status-submit" };
    }
    return { label: "OPEN", cssClass: "status-open" };
  }

  /** Renders the kanban board with columns, cards, and sort controls. */
  function renderKanban() {
    const el = document.getElementById("view-kanban");
    const doneCollapsed = loadDoneCollapsed();
    let h = '<div class="kanban-board">';
    COLUMNS.forEach(function (col) {
      const items = Board.state.TICKETS.filter(function (t) {
        if (col.key === "Open") { return t.status === "Open" || t.status === "Submit"; }
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

      // Done 칼럼 토글 버튼 (chevron)
      const isDone = col.key === "Done";
      const chevronSvg = isDone
        ? (doneCollapsed
          ? '<svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M4 2L8 6L4 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>'
          : '<svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M2 4L6 8L10 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>')
        : "";

      const columnCollapsedClass = isDone && doneCollapsed ? " collapsed" : "";
      h += '<div class="column' + columnCollapsedClass + '">';

      if (isDone && doneCollapsed) {
        // 접힌 상태: 세로 바 렌더링
        h += '<div class="done-collapsed-bar">';
        h += '<span class="bar-label">Done</span>';
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
        if (isDone) {
          h += '<button class="done-toggle-btn" title="\uC811\uAE30">' + chevronSvg + '</button>';
        }
        h += "</div>";
        h += '<div class="cards">';
        if (sortedItems.length === 0) {
          h += '<div class="empty">No items</div>';
        } else {
          sortedItems.forEach(function (t) {
            const done = col.key === "Done" ? " done" : "";
            const status = getWorkflowStatus(t);
            const dateObj = formatKoreanDate(t.datetime);
            h += '<div class="card' + done + '" data-num="' + esc(t.number) + '">';
            // 상단: 좌측 그룹(티켓번호 + 커맨드배지), 우측 상태라벨
            h += '<div class="card-top">';
            h += '<div class="card-top-left">';
            h += '<span class="card-num">' + esc(t.number.replace(/^T-/, "")) + "</span>";
            if (t.command) {
              h += badge(t.command, CMD_COLORS[t.command]);
            }
            if (t.relations && t.relations.length > 0) {
              h += '<span class="card-relations-icon">\uD83D\uDD17 ' + t.relations.length + "</span>";
            }
            h += "</div>";
            if (col.key === "Open") {
              h += '<span class="card-status ' + status.cssClass + '">' + status.label + "</span>";
            }
            h += "</div>";
            // 중단: 제목 (2줄 clamp)
            h += '<div class="card-mid"><div class="card-title">' + esc(t.title || "(No title)") + "</div></div>";
            // 하단: 날짜/시간 2줄 우측 정렬
            h += '<div class="card-bottom">';
            h += '<div class="card-date">' + esc(dateObj.datePart) + "</div>";
            h += '<div class="card-time">' + esc(dateObj.timePart) + "</div>";
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

    // Bind Done toggle button click (펼친 상태 → 접기)
    const doneToggleBtn = el.querySelector(".done-toggle-btn");
    if (doneToggleBtn) {
      doneToggleBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        saveDoneCollapsed(!loadDoneCollapsed());
        renderKanban();
      });
    }

    // Bind Done collapsed bar click (접힌 상태 → 펼치기)
    const doneCollapsedBar = el.querySelector(".done-collapsed-bar");
    if (doneCollapsedBar) {
      doneCollapsedBar.addEventListener("click", function (e) {
        e.stopPropagation();
        saveDoneCollapsed(false);
        renderKanban();
      });
    }

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
