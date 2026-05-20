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
  const {
    esc, badge, fetchXmlList, parseTicket, CMD_COLORS, COLUMNS, KANBAN_SORT_LS_KEY,
    PRODUCT_LABELS,
  } = Board.util;

  // ── Relations Display ──
  const MAX_VISIBLE_RELATIONS = 5;

  // ── T-475 Stage 3: launch asynchronousization — client status machine
  // idle → submitting → starting → running (LAUNCH STARTED Received) | failed (LAUNCH FAILED / User Selection)
  //
  // Use Flow:
  //   1. FAQ submit handler: HTTP 200 OK ({status:'starting'}) start the launchState registration + grace timer immediately after the response.
  //   2. FAQ SSE 'launch' Event (handleLaunchEvent): LAUNCH STARTED → launchState Removal + Remove Badge,
  //      LAUNCH FAILED → launchState removal + failure modal.
  //   3. FAQs Grace 60s Expired (onGraceExpired): User-selection only displays — auto-forced previews 0 (constraints compliance).
  //
  // Restore a new call: sessionStorage('Board.launchState.<ticket>') to 1.02 state →
  // Rewrite grace residual time with restoreLaunchStateFromStorage() call and restart timer.
  //
  // SSE Convention (my-board-sse-convention §2.4): handleLaunchEvent calls to single listener —
  // Board.kanban Namespace Exposure (addEventListener Anti-Registration).
  const LAUNCH_GRACE_MS = 60000;             // 60s grace
  const LAUNCH_STORAGE_PREFIX = "Board.launchState.";
  const launchState = new Map();              // ticketNum → {state, since, command, sessionId, graceTimer}

  // ── Column Collapsed State (Done / To Do) ──
  // Saves the foldable status by column key. "Done" is a user-configured by maintaining an existing key
  // To ensure compatibility, other columns (currently "To Do") are column-collapsed:<key> format.
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
  // To Do Column supports user manual sorting (DnD location changes). New ticket is always the best prepend.
  // Not synchronized with other browsers/ devices (localStorage only).
  const TODO_MANUAL_ORDER_LS_KEY = "kanban_todo_manual_order_v1";
  const WR_FORM_STATE_KEY = "agent-factory-workrequest-form-expanded";

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
   * Tag:
   * - Save order tickets = in order
   * - Ticket without storage order (New) = Top quality prepend, number desc
   * - Save the result order again (New item is automatically registered in manual order and STAle clearance)
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

  function loadWorkRequestFormExpanded() {
    try { return localStorage.getItem(WR_FORM_STATE_KEY) === "1"; } catch (e) { return false; }
  }

  function saveWorkRequestFormExpanded(expanded) {
    try { localStorage.setItem(WR_FORM_STATE_KEY, expanded ? "1" : "0"); } catch (e) {}
  }

  function collectWorkRequestPayload(form, action) {
    return {
      action: action,
      ticket: (form.querySelector('[name="ticket"]') || {}).value || "",
      title: (form.querySelector('[name="title"]') || {}).value || "",
      command: (form.querySelector('[name="command"]') || {}).value || "implement",
      status: (form.querySelector('[name="status"]') || {}).value || "todo",
      goal: (form.querySelector('[name="goal"]') || {}).value || "",
      target: (form.querySelector('[name="target"]') || {}).value || "",
      constraints: (form.querySelector('[name="constraints"]') || {}).value || "",
      criteria: (form.querySelector('[name="criteria"]') || {}).value || "",
      context: (form.querySelector('[name="context"]') || {}).value || "",
    };
  }

  function setWorkRequestFormStatus(root, kind, message) {
    var status = root.querySelector(".wr-author-status");
    if (!status) return;
    status.className = "wr-author-status " + (kind || "");
    status.textContent = message || "";
  }

  function submitWorkRequest(root, action) {
    var form = root.querySelector(".wr-author-form");
    if (!form) return;
    var payload = collectWorkRequestPayload(form, action);
    var buttons = root.querySelectorAll(".wr-author-actions button");
    buttons.forEach(function (btn) { btn.disabled = true; });
    setWorkRequestFormStatus(root, "running", action === "create" ? "Creating..." : action === "accept" ? "Accepting..." : "Refining...");
    fetch("/api/kanban/workrequest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (body) {
        return { ok: res.ok, body: body };
      });
    }).then(function (r) {
      if (!r.ok || !r.body.ok) {
        throw new Error((r.body && (r.body.error || r.body.message)) || "Request update failed");
      }
      setWorkRequestFormStatus(root, "ok", r.body.ticket ? r.body.ticket + " updated" : "Updated");
      if (action === "create") {
        form.reset();
        var command = form.querySelector('[name="command"]');
        if (command) command.value = "implement";
      }
      return fetchTickets().then(renderKanban);
    }).catch(function (err) {
      setWorkRequestFormStatus(root, "error", err && err.message ? err.message : "Request failed");
    }).finally(function () {
      buttons.forEach(function (btn) { btn.disabled = false; });
    });
  }

  function renderWorkRequestAuthoring() {
    var expanded = loadWorkRequestFormExpanded();
    return ''
      + '<section class="wr-author' + (expanded ? ' expanded' : '') + '">'
      + '<div class="wr-author-head">'
      + '<div><div class="wr-author-title">' + esc(PRODUCT_LABELS.workRequest) + ' Console</div>'
      + '<div class="wr-author-meta">Create, refine, and accept requests before execution.</div></div>'
      + '<button class="wr-author-toggle" type="button">' + (expanded ? 'Hide' : 'Author') + '</button>'
      + '</div>'
      + '<form class="wr-author-form">'
      + '<div class="wr-author-grid wr-author-grid-top">'
      + '<label>Existing ID<input name="ticket" placeholder="T-520"></label>'
      + '<label>Title<input name="title" placeholder="Short request title"></label>'
      + '<label>Mode<select name="command"><option value="implement">Execute</option><option value="research">Research</option><option value="review">Review</option></select></label>'
      + '<label>Initial state<select name="status"><option value="todo">Draft</option><option value="open">Accepted</option></select></label>'
      + '</div>'
      + '<div class="wr-author-grid wr-author-grid-fields">'
      + '<label>Goal<textarea name="goal" rows="2"></textarea></label>'
      + '<label>Target<textarea name="target" rows="2"></textarea></label>'
      + '<label>Criteria<textarea name="criteria" rows="2"></textarea></label>'
      + '<label>Constraints<textarea name="constraints" rows="2"></textarea></label>'
      + '<label class="wr-author-wide">Context<textarea name="context" rows="2"></textarea></label>'
      + '</div>'
      + '<div class="wr-author-actions">'
      + '<span class="wr-author-status"></span>'
      + '<button type="button" data-wr-action="create">Create</button>'
      + '<button type="button" data-wr-action="refine">Refine</button>'
      + '<button type="button" data-wr-action="accept">Accept</button>'
      + '</div>'
      + '</form>'
      + '</section>';
  }

  /** Go to the targetIndex location of manual order. */
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
      // To Do defaults manual sorting. The rest of the number of times.
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
  // For the card woo Sangdan woomit indica. null = not loaded
  var _worktreeUncommittedMap = null;

  // ── Done Verdict Cache (T-441) ──
  // Done Card Mage Combination verdict. key=ticket number, value={verdict,reason,details}.
  // "pending" value = during the query. undefined = undefined
  var _doneVerdictMap = {};

  // ── Review Verdict Cache (T-463) ──
  // Review Card Rule Base 1st Auto Verdict (advisory only).
  // key=ticket number, value={verdict, reason, details, violations}.
  // Verdict Value: PASS / WARN / FAIL / SKIP / UNKNOWN.
  // "pending" value = during the query. undefined = undefined
  // comment no speculative guards 2026-05-08, T-411 0c970fa, T-413 1ce3c2d.
  // Auto Forced / Forced Regression / Forced Regression 0 — User can run verdict FAIL
  var _reviewVerdictMap = {};

  // ── Audit Verdict Cache (T-477) ──
  // Review Card Auditor T3 advisory verdict. key=ticket number, value={tier1,tier2,combined}.
  // "pending" = viewed. undefined = undefined
  var _auditVerdictMap = {};

  // ── Active Branch Ticket (T-433 Phase 2) ──
  // The main working tree is currently active feature brand name ticket number (e.g. "T-433"). null = develop.
  // SSOT: derive from backend GET /api/kanban/branch/active or SSE git branch event.
  // Only one card is active: Matching only .active, compared all the review cards in render.
  var _activeBranchTicket = null;
  // First one fetch finished guard — initial visual restore with 1 GET when loading page.
  var _activeBranchFetched = false;
  // T-NNN extraction regular expression — feat/T-NNN-* pattern matching.
  var _FEAT_BRANCH_RE = /^feat\/(T-\d+)/;

  /**
   * <# if ( data.meta.album ) { #>{{ data.meta.artist }}<# } #>
   * .active toggles only when receiving a response (full re-render avoidance — DOM direct patch).
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
      // backend not ready —  activeBranchTicket retains null (Each OFF)
    });
  }

  /**
   * .has-active-branch /
   * Sync the Toggle button .active class (directly patch DOM without full re-render).
   * - Call after arrival of SSE git branch event
   * - Toggle click optimistic update call immediately
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
   * SSE git branch event calls outside (sse.js).
   * Extract T-NNN from branch strings  activeBranchTicket Update + DOM Patch.
   * @param {string null} branch - "feat/T-NNN-..." or "develop"
   */
  function syncActiveBranchFromSSE(branch) {
    var ticket = null;
    if (branch && typeof branch === "string") {
      var m = _FEAT_BRANCH_RE.exec(branch);
      if (m) ticket = m[1];
    }
    if (ticket === _activeBranchTicket) return; // Skip to content
    _activeBranchTicket = ticket;
    applyActiveBranchClassToCards();
  }

  /**
   * Review Card 4 Toggle Button Click Handler.
   * - Current card is active if action=off, or action=on to POST.
   * - dirty / needs restart / guided moves according to failure response (automatic stash absolute X).
   * @param {string} ticketNum - Click Card T-NNN
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
        // Success — active ticket update (server response reflect SSOT, optimistic simultaneously)
        _activeBranchTicket = body.active_ticket || null;
        applyActiveBranchClassToCards();
        if (body.needs_restart) {
          Board.util.showInfoModal(
            "Brand Name Active — Backend Change Detection",
            "This feature brand contains board/server/** changes. \\n" +
            "the backend to reboot the board server is normal. \\n\\n" +
            "Rewrite the board server manually and refresh the page. \\n" +
            "(frontend static files are automatically updated — only hard reload is enough)",
            { severity: "warning" }
          );
        }
        return;
      }
      // Failure — reason quarterly
      var reason = body.reason || "";
      if (reason === "dirty") {
        var files = (body.files || []).slice(0, 20);
        var fileList = files.map(function (f) { return "  - " + f; }).join("\n");
        var more = (body.files && body.files.length > 20) ? "\n  ... (" + (body.files.length - 20) + "More" : "";
        var msg = body.modal_message ||
          ("The main working tree has a mitigation change. \\n" +
           "Retry after commit / stash / reset manually.");
        Board.util.showInfoModal(
          "Broch Toggle Lockout — dirty",
          msg + "\\n\\n Change Files:\\n" + fileList + more,
          { severity: "warning" }
        );
        return;
      }
      if (reason === "feature_branch_not_found") {
        Board.util.showInfoModal(
          "Branch Toggle Failure",
          body.message || "feature not found a brand",
          { severity: "error" }
        );
        return;
      }
      if (reason === "git_switch_failed") {
        Board.util.showInfoModal(
          "git switch failure",
          body.message || "git switch failed.",
          { severity: "warning" }
        );
        return;
      }
      // Other unknown failures
      Board.util.showInfoModal(
        "Branch Toggle Failure",
        body.message || JSON.stringify(body),
        { severity: "error" }
      );
    }).catch(function (err) {
      Board.util.showInfoModal(
        "Branch Toggle request failed",
        (err && err.message) ? err.message : String(err),
        { severity: "error" }
      );
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
   * T-441: Single Done Card Verdict View (advisory).
   * The result is cached in  doneVerdictMap, and patches the corresponding card badge to DOM when loading is completed.
   * No polling — 1 call when card mount.
   * @param {string} ticketNum - ticket number (e.g. "T-441")
   */
  function fetchAndRenderVerdict(ticketNum) {
    // If you already have an inquiry or complete, skip
    if (_doneVerdictMap[ticketNum] !== undefined) return;
    _doneVerdictMap[ticketNum] = "pending";

    fetch("/api/kanban/done-verdict?ticket=" + encodeURIComponent(ticketNum), { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        _doneVerdictMap[ticketNum] = data;
        // DOM Patch: Replace the verdict badge of the corresponding card (without full re-render)
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
        _doneVerdictMap[ticketNum] = { verdict: "UNKNOWN", reason: "fetch_error", details: { message: "Verdict View failed" } };
      });
  }

  /**
   * T-441: Apply the status in the badge span based on verdict data.
   * @param {HTMLElement} el - target span element
   * @param {Object} data - verdict response data ({verdict, reason, details})
   */
  function _applyVerdictBadge(el, data) {
    var verdict = data && data.verdict;
    el.className = "card-done-verdict";
    if (verdict === "OK") {
      el.className += " verdict-ok";
      el.title = "(develop HEAD == merge commit)";
      el.innerHTML = '<svg width="11" height="11" viewBox="0 0 11 11" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><polyline points="1.5,5.5 4.5,8.5 9.5,2.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>';
    } else if (verdict === "FAIL") {
      var msg = (data.details && data.details.message) || "Develop head is mitigating";
      el.className += " verdict-fail";
      el.title = "Mudfish —" + msg + "(Click for details)";
      el.setAttribute("data-verdict-msg", msg);
      el.innerHTML = '<svg width="11" height="11" viewBox="0 0 11 11" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><line x1="2" y1="2" x2="9" y2="9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="9" y1="2" x2="2" y2="9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
    } else {
      // UNKNOWN / SKIP / pending — No space waste
      el.className += " verdict-unknown";
      el.style.display = "none";
    }
  }

  /**
   * T-463: Single Review Card Verdict View (advisory only).
   * Results  reviewVerdictMap Cache, and patch the corresponding card badge to DOM when loading is completed.
   * No polling — 1 call when card mount.
   * @param {string} ticketNum - ticket number (e.g. "T-463")
   */
  function fetchAndRenderReviewVerdict(ticketNum) {
    // If you already have an inquiry or complete, skip
    if (_reviewVerdictMap[ticketNum] !== undefined) return;
    _reviewVerdictMap[ticketNum] = "pending";

    fetch("/api/kanban/review-verdict?ticket=" + encodeURIComponent(ticketNum), { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        _reviewVerdictMap[ticketNum] = data;
        // DOM Patch: Replace the verdict badge of the corresponding card (without full re-render)
        var badge = document.querySelector(
          '.card[data-num="' + ticketNum + '"][data-col-key="Review"] .card-review-verdict'
        );
        if (badge) {
          var newBadge = document.createElement("span");
          _applyReviewVerdictBadge(newBadge, data);
          badge.parentNode.replaceChild(newBadge, badge);
        }
      })
      .catch(function () {
        _reviewVerdictMap[ticketNum] = { verdict: "UNKNOWN", reason: "fetch_error", details: {}, violations: [] };
      });
  }

  /**
   * T-477: Auditor T3 audit verdict generates an HTML (inline call in the renderKanban).
   * combination === "NONE" returns empty string (DOM mount X).
   * @param {string} ticketNum - ticket number
   * @returns {string} span.audit-badge HTML or empty string
   */
  function renderAuditBadgeHtml(ticketNum) {
    var data = _auditVerdictMap[ticketNum];
    if (!data || data === "pending") {
      return '<span class="audit-badge audit-loading" style="display:none"></span>';
    }
    var combined = (data && data.combined) || "NONE";
    if (combined === "NONE") return "";
    var cls = "audit-badge";
    if (combined === "PASS") cls += " audit-pass";
    else if (combined === "WARN") cls += " audit-warn";
    else if (combined === "FAIL") cls += " audit-fail";
    var tip = "Auditor T3: " + combined;
    var hgf = data.tier2 && data.tier2.hard_gate_failed;
    if (hgf && hgf.length) {
      tip += " — hard gate FAIL: " + hgf.join(", ");
    }
    return '<span class="' + cls + '" title="' + tip.replace(/"/g, "&quot;") + '">' + combined + "</span>";
  }

  /**
   * T-477: Review card single audit verdict fetch + DOM badge patch.
   * Results  auditVerdictMap to cache. No polling — 1 time when card mount.
   * @param {string} ticketNum - ticket number
   */
  function fetchAndRenderAuditVerdict(ticketNum) {
    if (_auditVerdictMap[ticketNum] !== undefined) return;
    _auditVerdictMap[ticketNum] = "pending";

    fetch("/api/kanban/audit/verdict?ticket=" + encodeURIComponent(ticketNum), { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        _auditVerdictMap[ticketNum] = data;
        if ((data.combined || "NONE") === "NONE") return;
        var placeholder = document.querySelector(
          '.card[data-num="' + ticketNum + '"][data-col-key="Review"] .audit-badge'
        );
        if (placeholder) {
          var newHtml = renderAuditBadgeHtml(ticketNum);
          if (newHtml) {
            var tmp = document.createElement("span");
            tmp.innerHTML = newHtml;
            var newEl = tmp.firstChild;
            placeholder.parentNode.replaceChild(newEl, placeholder);
          }
        }
      })
      .catch(function () {
        _auditVerdictMap[ticketNum] = { tier1: null, tier2: null, combined: "NONE" };
      });
  }

  /**
   * T-463: The review verdict data is based on the status of the badge span.
   * - PASS / WARN / FAIL — Text Chip Display (verdict-pass / verdict-warn / verdict-fail)
   * - SKIP / UNKNOWN / pending — hidden badge (display:none)
   * - tooltip = violations list + "advisory only" guide (cursor:help)
   * - 0 clicks (advisory only canon)
   * @param {HTMLElement} el - target span element
   * @param {Object} data - verdict response data ({verdict, reason, details, violations})
   */
  function _applyReviewVerdictBadge(el, data) {
    var verdict = data && data.verdict;
    el.className = "card-review-verdict";
    // margin-right:auto inline preservation — 4 action-row left + right toggle/done button separation
    el.style.marginRight = "auto";
    if (verdict !== "PASS" && verdict !== "WARN" && verdict !== "FAIL") {
      // SKIP / UNKNOWN / Unknown Value — Unlock Badge
      el.className += " verdict-unknown";
      el.style.display = "none";
      return;
    }
    el.className += " verdict-" + verdict.toLowerCase();
    el.textContent = verdict;
    // tooltip: violations list or reason only show + advisory guidance
    var violations = (data && data.violations) || [];
    var lines = [];
    if (violations.length > 0) {
      violations.forEach(function (v) {
        var rid = v.rule_id || "?";
        var sev = v.severity ? ("(" + v.severity + ")") : "";
        var msg = v.message || "";
        lines.push("[" + rid + "]" + sev + " " + msg);
      });
    } else {
      var reason = (data && data.reason) || "ok";
      lines.push(verdict + " (" + reason + ")");
    }
    var tooltip = lines.join("\n") + "\\n\\nadvisory only — Done Mobile Freedom";
    el.setAttribute("data-verdict-msg", tooltip);
    el.setAttribute("title", tooltip);
  }

  /**
   * T-463: Create a Review Card verdict badge HTML.
   * If there is no result in the cache, return the placeholder during loading, and the DOM patch will be completed.
   * The first child of the card-actions-row is inserted into the margin-right:auto and separated to the right top.
   * @param {string} ticketNum - ticket number (e.g. "T-463")
   * @returns {string} span.card-review-verdict HTML
   */
  function renderReviewVerdictBadge(ticketNum) {
    var data = _reviewVerdictMap[ticketNum];
    if (data === undefined || data === "pending") {
      // Loading — Unseen Placeholders.  applyReviewVerdictBadge DOM patch after fetch completion.
      return '<span class="card-review-verdict verdict-loading" style="display:none;margin-right:auto"></span>';
    }
    var verdict = data && data.verdict;
    if (verdict !== "PASS" && verdict !== "WARN" && verdict !== "FAIL") {
      // SKIP / UNKNOWN / Unknown Value — Unlock Badge
      return '<span class="card-review-verdict verdict-unknown" style="display:none;margin-right:auto"></span>';
    }
    var violations = (data && data.violations) || [];
    var lines = [];
    if (violations.length > 0) {
      violations.forEach(function (v) {
        var rid = v.rule_id || "?";
        var sev = v.severity ? ("(" + v.severity + ")") : "";
        var msg = v.message || "";
        lines.push("[" + rid + "]" + sev + " " + msg);
      });
    } else {
      var reason = (data && data.reason) || "ok";
      lines.push(verdict + " (" + reason + ")");
    }
    var tooltip = lines.join("\n") + "\\n\\nadvisory only — Done Mobile Freedom";
    var cls = "verdict-" + verdict.toLowerCase();
    return (
      '<span class="card-review-verdict ' + cls + '"'
      + ' style="margin-right:auto"'
      + ' title="' + esc(tooltip) + '"'
      + ' data-verdict-msg="' + esc(tooltip) + '">'
      + esc(verdict)
      + '</span>'
    );
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
   * Convert Stage Name to 3 letters.
   * @param {string} stage - stage name (e.g. "research", "implement", "review")
   * @returns {string} 3-character Abbreviation (e.g. "res", "imp", "rev")
   */
  function stageAbbr(stage) {
    var abbr = Board.util.CMD_ABBR;
    var s = stage.trim().toLowerCase();
    return abbr[s] || s.slice(0, 3).toUpperCase();
  }

  /**
   * Create a stage icon HTML for the chain command ticket.
   * @param {Object} ticket object
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
   * Create a relationship link HTML.
   * @param {Object} ticket object
   * @returns {string} card-relations div HTML
   */
  function renderRelations(ticket) {
    if (!ticket.relations || ticket.relations.length === 0) return "";

    const typeMap = {
      "derived-from": { prefix: "\u2190", cssClass: "rel-derived" },   // ←
      "depends-on":   { prefix: "\u21D0", cssClass: "rel-depends" },   // ⇐
      "blocks":       { prefix: "\u2192", cssClass: "rel-blocks" },    // →
    };

    const relations = ticket.relations;
    const visible = relations.length > MAX_VISIBLE_RELATIONS
      ? relations.slice(0, MAX_VISIBLE_RELATIONS)
      : relations;
    const overflow = relations.length > MAX_VISIBLE_RELATIONS
      ? relations.length - MAX_VISIBLE_RELATIONS
      : 0;

    let parts = [];
    visible.forEach(function (rel) {
      const info = typeMap[rel.type] || { prefix: "\u2194", cssClass: "rel-other" };
      const numStr = rel.ticket ? rel.ticket.replace(/^T-/, "") : "?";
      parts.push('<span class="rel-item ' + info.cssClass + '">' + info.prefix + numStr + "</span>");
    });

    if (overflow > 0) {
      const ticketNum = ticket.number || "";
      const encodedRelations = esc(JSON.stringify(relations));
      const totalCount = relations.length;
      parts.push(
        '<button class="rel-overflow-chip"' +
        ' data-ticket="' + esc(ticketNum) + '"' +
        ' data-relations="' + encodedRelations + '"' +
        ' aria-label="\uad00\uacc4 ' + totalCount + '\uac1c \ubaa8\ub450 \ubcf4\uae30">' +
        '+' + overflow +
        '</button>'
      );
    }

    return '<div class="card-relations">' + parts.join("") + "</div>";
  }

  // ── Relations Popover ──
  // Single popover policy: only one #rel-popover-active exists at a time.
  // Close triggers: ESC key, document overlay click outside popover, hover leave
  // (card + popover both) with 200ms debounce.

  /** @type {number|null} setTimeout handle for hover-leave debounce */
  var _relPopoverLeaveTimer = null;

  /** @type {boolean} guard: ensures bindRelationsPopoverEvents runs only once */
  var _relPopoverBound = false;

  /**
   * Removes the active relations popover from the DOM, if present.
   * Also clears any pending hover-leave close timer.
   */
  function hideRelationsPopover() {
    if (_relPopoverLeaveTimer !== null) {
      clearTimeout(_relPopoverLeaveTimer);
      _relPopoverLeaveTimer = null;
    }
    var existing = document.getElementById("rel-popover-active");
    if (existing) existing.remove();
  }

  /**
   * Creates and positions the relations popover anchored to triggerEl.
   * Applies viewport boundary flip (top / right-align) when popover would overflow.
   *
   * @param {HTMLElement} triggerEl - .rel-overflow-chip element that was activated
   * @param {Array<{type: string, ticket: string}>} relations - full relations array
   */
  function showRelationsPopover(triggerEl, relations) {
    hideRelationsPopover();

    var typeMap = {
      "derived-from": { prefix: "←", cssClass: "rel-derived" },  // ←
      "depends-on":   { prefix: "⇐", cssClass: "rel-depends" },  // ⇐
      "blocks":       { prefix: "→", cssClass: "rel-blocks" },   // →
    };

    // Build list HTML — prefix + ticket# + type label per row
    var listHtml = '<ul class="rel-popover-list" role="list">';
    relations.forEach(function (rel) {
      var info = typeMap[rel.type] || { prefix: "↔", cssClass: "rel-other" };
      var numStr = rel.ticket ? rel.ticket.replace(/^T-/, "") : "?";
      var label = rel.type === "derived-from" ? "Home"   // Home
        : rel.type === "depends-on" ? "Venue"             // Venue
        : rel.type === "blocks" ? "Home"                 // Home
        : esc(rel.type);
      listHtml += '<li class="rel-popover-item ' + info.cssClass + '">'
        + '<span class="rel-popover-prefix">' + info.prefix + '</span>'
        + '<span class="rel-popover-num">T-' + esc(numStr) + '</span>'
        + '<span class="rel-popover-type">' + label + '</span>'
        + '</li>';
    });
    listHtml += '</ul>';

    var popover = document.createElement("div");
    popover.id = "rel-popover-active";
    popover.className = "rel-popover";
    popover.setAttribute("role", "tooltip");
    popover.setAttribute("aria-label", "Company" + relations.length + "dog full"); // Relationship N Entire
    popover.innerHTML = listHtml;
    document.body.appendChild(popover);

    // Position: left-aligned below trigger; flip right/top if viewport overflow
    var rect = triggerEl.getBoundingClientRect();
    var scrollX = window.scrollX || window.pageXOffset;
    var scrollY = window.scrollY || window.pageYOffset;
    var vpW = document.documentElement.clientWidth;
    var vpH = document.documentElement.clientHeight;
    var popW = popover.offsetWidth;
    var popH = popover.offsetHeight;

    var left = rect.left + scrollX;
    var top = rect.bottom + scrollY + 4;

    // Horizontal: right-align to trigger if right edge overflows
    if (rect.left + popW > vpW) {
      left = Math.max(0, rect.right + scrollX - popW);
    }

    // Vertical: show above trigger if not enough space below
    if (rect.bottom + 4 + popH > vpH) {
      top = rect.top + scrollY - popH - 4;
      if (top < scrollY) top = scrollY + 4; // clamp to viewport top
    }

    popover.style.left = left + "px";
    popover.style.top = top + "px";

    // Keep-alive: entering popover cancels the hover-leave close timer
    popover.addEventListener("mouseenter", function () {
      if (_relPopoverLeaveTimer !== null) {
        clearTimeout(_relPopoverLeaveTimer);
        _relPopoverLeaveTimer = null;
      }
    });
    popover.addEventListener("mouseleave", function () {
      _scheduleRelPopoverClose();
    });

    // Store trigger for focus restoration on ESC
    popover._relTriggerEl = triggerEl;
  }

  /**
   * Schedules popover close after 200ms debounce.
   * Cancelled if cursor re-enters the popover or the trigger chip.
   */
  function _scheduleRelPopoverClose() {
    if (_relPopoverLeaveTimer !== null) clearTimeout(_relPopoverLeaveTimer);
    _relPopoverLeaveTimer = setTimeout(function () {
      _relPopoverLeaveTimer = null;
      hideRelationsPopover();
    }, 200);
  }

  /**
   * Binds delegated event listeners for relations popover on document.
   * Must be called once at module init time (guarded by _relPopoverBound).
   * Delegates to document so listeners survive kanban re-renders.
   *
   * Triggers:
   *   - click on .rel-overflow-chip → open (toggle: second click closes)
   *   - mouseenter on .rel-overflow-chip → hover-open
   *   - mouseleave on .rel-overflow-chip → schedule close (200ms debounce)
   *   - click outside popover and chip → close
   *   - ESC key → close + restore focus to trigger
   */
  function bindRelationsPopoverEvents() {
    if (_relPopoverBound) return;
    _relPopoverBound = true;

    // Click: open/toggle popover (capture phase to intercept before card click handler)
    document.addEventListener("click", function (e) {
      var chip = e.target.closest(".rel-overflow-chip");
      if (chip) {
        e.stopPropagation();
        var existing = document.getElementById("rel-popover-active");
        // Toggle: click on same chip again → close
        if (existing && existing._relTriggerEl === chip) {
          hideRelationsPopover();
          return;
        }
        var relStr = chip.dataset.relations;
        var relations;
        try { relations = JSON.parse(relStr); } catch (_e) { relations = []; }
        showRelationsPopover(chip, relations);
        return;
      }
      // Click outside both chip and popover → close
      var pop = e.target.closest("#rel-popover-active");
      if (!pop) {
        hideRelationsPopover();
      }
    }, true);

    // Hover open: mouseenter on overflow chip
    document.addEventListener("mouseenter", function (e) {
      var chip = e.target.closest(".rel-overflow-chip");
      if (!chip) return;
      if (_relPopoverLeaveTimer !== null) {
        clearTimeout(_relPopoverLeaveTimer);
        _relPopoverLeaveTimer = null;
      }
      var relStr = chip.dataset.relations;
      var relations;
      try { relations = JSON.parse(relStr); } catch (_e) { relations = []; }
      showRelationsPopover(chip, relations);
    }, true);

    // Hover leave: chip mouseleave → debounce close
    document.addEventListener("mouseleave", function (e) {
      var chip = e.target.closest(".rel-overflow-chip");
      if (chip) {
        _scheduleRelPopoverClose();
      }
    }, true);

    // ESC key → close popover, restore focus to trigger chip
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" || e.key === "Esc") {
        var pop = document.getElementById("rel-popover-active");
        if (pop) {
          var trigger = pop._relTriggerEl;
          hideRelationsPopover();
          if (trigger) trigger.focus();
        }
      }
    });
  }

  /**
   * T-457 (Layer 3): Automatic Commit Trigger with 4 Commit button clicks.
   * to maintain fetch logic in existing handleUncommittedBadgeClick,
   * Only one DOM manipulator will be transferred to the 4th button.
   * .card-commit-action
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
        // Success — Card Renewal (commit button + expects to disappear both one-on-the-box)
        if (_worktreeUncommittedMap) _worktreeUncommittedMap.delete(ticket);
        Board.render.renderKanban();
      } else {
        var msg = (r.data && r.data.error) || "Commit fails";
        btn.classList.remove("is-commiting");
        btn.disabled = false;
        Board.util.showInfoModal("Commit fails", ticket + "Commit fail:" + msg, { severity: "error" });
      }
    }).catch(function (err) {
      btn.classList.remove("is-commiting");
      btn.disabled = false;
      Board.util.showInfoModal("Commit fails", ticket + "Commit request failed:" + (err && err.message ? err.message : err), { severity: "error" });
    });
  }

  /**
   * In Progress card 4 stop button click — POST /api/workflow/stop with workflow request.
   * showInfoModal in the event of a successful renderKanban / failure.
   */
  function handleStopButtonClick(btn) {
    var ticket = btn.dataset.stopTicket;
    if (!ticket || btn.classList.contains("is-stopping")) return;
    var msg = ticket + "Stop workflow. \\nProceeds/jsonl/kanban/worktree 4 axis. \\n\\n?";
    if (!window.confirm(msg)) return;
    btn.classList.add("is-stopping");
    btn.disabled = true;
    fetch("/api/workflow/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket: ticket }),
    }).then(function (res) {
      return res.json().then(function (data) {
        return { status: res.status, ok: res.ok, data: data };
      }).catch(function () {
        return { status: res.status, ok: res.ok, data: null };
      });
    }).then(function (r) {
      btn.classList.remove("is-stopping");
      btn.disabled = false;
      if (r.ok && r.data && r.data.ok !== false) {
        if (Board.render && Board.render.renderKanban) Board.render.renderKanban();
      } else {
        var errs = (r.data && r.data.errors) || [];
        var errMsg = errs.length ? errs.join("\n") : ("HTTP " + r.status);
        Board.util.showInfoModal("Workflow failed", ticket + "Warranty:" + errMsg, { severity: "error" });
      }
    }).catch(function (err) {
      btn.classList.remove("is-stopping");
      btn.disabled = false;
      Board.util.showInfoModal("Workflow failed", ticket + "Tag:" + (err && err.message ? err.message : err), { severity: "error" });
    });
  }

  /**
   * Create a Card Indication HTML.
   * When the workflow regression (Watcher Committed), the user immediately commits to click.
   * @param {string} ticketNum - ticket number (e.g. "T-422")
   * @returns {string} span.card-uncommitted-badge HTML or empty string
   */
  function renderUncommittedBadge(ticketNum) {
    if (!_worktreeUncommittedMap) return "";
    var item = _worktreeUncommittedMap.get(ticketNum);
    if (!item || item.uncommitted_count <= 0) return "";
    var label = item.uncommitted_count + "M";
    var tooltip = "Mickey Mouse" + item.uncommitted_count + "— Click Commit"; // "Mickeym N Gun — Automatic Commit"
    return '<span class="card-uncommitted-badge" data-uncommitted-ticket="' + esc(ticketNum) + '" title="' + esc(tooltip) + '">' + esc(label) + "</span>";
  }

  /**
   * T-457 (Layer 3): Card 1-on-right failure tag wrench.
   * schema: { reason, phase, retry count, context }
   * Guard: ticket / ticket.failure returns empty strings if falsy.
   * read-only — pointer-events:none (CSS), no click trigger.
   * The color is placeholder neutral (the user decides to wait — the one-line patch after the decision).
   * @param {object} ticket - card ticket object
   * @returns {string} span.card-failure-tag HTML or empty string
   */
  function renderFailureTag(ticket) {
    if (!ticket || !ticket.failure) return "";
    var reason = ticket.failure.reason || "Workflow Failure";
    var phase = ticket.failure.phase || "";
    var label = "FAIL";
    var tooltip = phase ? (phase + "Step Failure —" + reason) : reason;
    return '<span class="card-failure-tag" title="' + esc(tooltip) + '">' + esc(label) + "</span>";
  }

  /**
   * T-441: Create Done Card verdict badge HTML.
   * If there is no result in the cache, return the placeholder during loading and the synchronous fetch trigger.
   * @param {string} ticketNum - ticket number (e.g. "T-441")
   * @returns {string} span.card-done-verdict HTML or empty string
   */
  function renderDoneVerdictBadge(ticketNum) {
    var data = _doneVerdictMap[ticketNum];
    if (data === undefined || data === "pending") {
      // Loading — Small Placeholders (not seen, DOM patch after fetch finish)
      return '<span class="card-done-verdict verdict-loading" style="display:none"></span>';
    }
    var verdict = data && data.verdict;
    if (verdict === "OK") {
      return (
        '<span class="card-done-verdict verdict-ok" title'
        + '<svg width="11" height="11" viewBox="0 0 11 11" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        + '<polyline points="1.5,5.5 4.5,8.5 9.5,2.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
        + '</svg></span>'
      );
    }
    if (verdict === "FAIL") {
      var msg = (data.details && data.details.message) || "Develop head is mitigating";
      return (
        '<span class="card-done-verdict verdict-fail"'
        + 'title="Merge Unemployment —' + esc(msg) + '(click to check details)"'
        + ' data-verdict-msg="' + esc(msg) + '">'
        + '<svg width="11" height="11" viewBox="0 0 11 11" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        + '<line x1="2" y1="2" x2="9" y2="9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
        + '<line x1="9" y1="2" x2="2" y2="9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
        + '</svg></span>'
      );
    }
    // UNKNOWN / SKIP
    return '<span class="card-done-verdict verdict-unknown" style="display:none"></span>';
  }

  /**
   * Returns status label information based on the status of the ticket.
   * To Do only returns TODO label.
   * T-399: Submit transient step removed. T-445: OPEN Label Closing.
   * @param {Object} ticket object
   * @returns {{ label: string, cssClass: string } | null} State label and CSS class, or null
   */
  function getWorkflowStatus(ticket) {
    if (ticket && ticket.status === "To Do") {
      return { label: "TODO", cssClass: "status-todo" };
    }
    return null;
  }

  /**
   * T-399: Confirmation Modal Display — Open → In Progress drop City Workflow Execution consciousness guaranteed.
   * @param {Object} ticket - Drag ticket object (number, command included)
   * @param {Function} onConfirm - [Run] Click Callback
   * @param {Function} onCancel - [Cancel]/ESC/overlay Click Callback
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
    title.textContent = "Skip to content";

    const body = document.createElement("p");
    body.className = "submit-confirm-body";
    body.textContent =
      ticket.number + "Go to In Progress and start workflow. About Us";

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    cancelBtn.textContent = "Venue";

    const confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    confirmBtn.textContent = "Open";

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
   * T-906: Review → Add Done drop (confirm delivery + cmd done commission + result delivery).
   * @param {Object} ticket - Drag ticket object (number included)
   * @param {Function} onConfirm - [Finished] Click Callback
   * @param {Function} onCancel - [Cancel]/ESC/overlay Click Callback
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
    const ticketNumNode = document.createTextNode(ticket.number + "Done Treatment");
    title.appendChild(ticketNumNode);

    const body = document.createElement("div");
    body.className = "submit-confirm-body";
    const introText = document.createTextNode("If you move this ticket to Done, then this will be done in a fairly NEWS");
    body.appendChild(introText);
    const ul = document.createElement("ul");
    const li1 = document.createElement("li");
    li1.textContent = "Feature Branding on --no-ff mourn";
    const li2 = document.createElement("li");
    li2.textContent = "Deleting worktree and feature brand";
    ul.appendChild(li1);
    ul.appendChild(li2);
    body.appendChild(ul);
    const continueText = document.createTextNode("About Us");
    body.appendChild(continueText);

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    cancelBtn.textContent = "Venue";

    const confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    confirmBtn.textContent = "Venue";

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
   * T-439: Review Card Velvet 1-click Complete Action Handler.
   * showDoneConfirmModal → POST /api/kanban/done → showDoneResultModal chain
   * DnD Review→Done reuse as the same signature as the branch(kanban.js:1791-1826).
   * @param {Object} ticketObj - ticket object (number included)
   */
  function handleReviewDoneAction(ticketObj) {
    var capturedNum = ticketObj.number;
    showDoneConfirmModal(
      ticketObj,
      function () {
        // [Completion] Callback: POST /api/kanban/done → cmd done commission
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
        // [Cancellation]/ESC/overlay callback: Keep card origin
        renderKanban();
      }
    );
  }

  /**
   * T-418: Open → Done direct transfer check modal.
   *
   * Go to Done without mounting the Review. Worktree/feature Branding Waster.
   * LOGIN JOIN ORDER MYPAGE forward force dirty value to onConfirm.
   *
   * @param {Object} ticket - Drag ticket object (number included)
   * @param {Function} onConfirm - [Direct Done Treatment] Click Callback (force dirty: bool argument passed)
   * @param {Function} onCancel - [Cancel]/ESC/overlay Click Callback
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
    title.appendChild(document.createTextNode(ticket.number + "Open → Done"));

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    const introText = document.createTextNode("Go directly to Done without mounting the Review at Open stage. The following are non-invasively performed NEWS");
    body.appendChild(introText);

    const ul = document.createElement("ul");
    const li1 = document.createElement("li");
    li1.textContent = "Worktree and feature Brand Name Waster (No Development Merged)";
    const li2 = document.createElement("li");
    li2.textContent = "Done Ticket Status";
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

    const dirtyLabelText = document.createTextNode("If you have any questions, please contact us.");
    dirtyLabel.appendChild(dirtyCheckbox);
    dirtyLabel.appendChild(dirtyLabelText);
    body.appendChild(dirtyLabel);

    const continueText = document.createElement("p");
    continueText.style.marginTop = "10px";
    continueText.appendChild(document.createTextNode("About Us"));
    body.appendChild(continueText);

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    cancelBtn.textContent = "Venue";

    const confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    confirmBtn.textContent = "Direct Done Treatment";

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
   * T-418: Open → Done direct transfer results.
   *
   * Unlike showDoneResultModal, success without merge commit also normal processing.
   * "Causes of rehabilitation after rehabilitation"
   *
   * @param {"success" "dirty" "error"} kind - result type
   * @param {Object} payload - result data
   * @param {Function} onClose - Close Callback
   * @param {Function} onForceDirty - "Causes of rehabilitation after rehabilitation" button click callback
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
      title.textContent = "Open → Done";
      const msg = document.createElement("p");
      msg.textContent = (payload.ticket || "") + "Tickets were moved to Done. Worktree and feature Brands were cleaned.";
      body.appendChild(msg);
    } else if (kind === "dirty") {
      title.textContent = "Done Processing Failure — Minorm Change";
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
        li.textContent = "(No Micommit File List)";
        ul.appendChild(li);
      }
      body.appendChild(ul);
      const guide = document.createElement("p");
      guide.textContent = "There is a change to the work tree. If you have any questions, please contact us.";
      body.appendChild(guide);
    } else {
      title.textContent = "Done processing failed";
      const msg = document.createElement("p");
      msg.textContent = (payload && payload.message) ? payload.message : "You can't see the error.";
      body.appendChild(msg);
    }

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    closeBtn.textContent = kind === "success" ? "About Us" : "Venue";

    actions.appendChild(closeBtn);

    if (kind === "dirty" && typeof onForceDirty === "function") {
      const forceBtn = document.createElement("button");
      forceBtn.type = "button";
      forceBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
      forceBtn.textContent = "Causes of rehabilitation after rehabilitation";
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
   * T-418: Deletion of ticket confirmation modal.
   *
   * Red [delete] button. POST /api/kanban/delete calls.
   * error kind='derived blocked' when alert is blocked by the show.
   *
   * @param {Object} ticket - ticket object to delete (number included)
   * @param {Function} onConfirm - Click Callback
   * @param {Function} onCancel - [Cancel]/ESC/overlay Click Callback
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
    title.appendChild(document.createTextNode(ticket.number + "Scots Gaelic"));

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    const introText = document.createTextNode(ticket.number + "Please delete the ticket. This work cannot be reverted.");
    body.appendChild(introText);

    const ul = document.createElement("ul");
    const li1 = document.createElement("li");
    li1.textContent = "Worktree and feature Brands are also cleaned together.";
    const li2 = document.createElement("li");
    li2.textContent = "Deletion is blocked if the derivation ticket (derived-from) is completed.";
    ul.appendChild(li1);
    ul.appendChild(li2);
    body.appendChild(ul);

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    cancelBtn.textContent = "Venue";

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    deleteBtn.textContent = "TubeDupe";
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
   * T-906: Done treatment result delivery.
   * @param {"success"|"conflict"|"dirty"|"error"} kind - result type
   * @param {Object} payload - result data (kind star difference)
   * @param {Function} onClose - Close Callback
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
        message: "backend response format error — merge commit missing. See flow-kanban output."
      });
    }

    if (kind === "success") {
      title.textContent = "Done Treatment Complete";
      const msg = document.createElement("p");
      const ticketStr = payload.merge_skipped
        ? (payload.ticket || "") + ": Review → Done (No Merge — Research/Document)"
        : (payload.ticket || "") + ": " + (payload.merged_branch || "") + "→ develop merge completion (" + (payload.merge_commit || "") + ")";
      msg.textContent = ticketStr;
      body.appendChild(msg);
    } else if (kind === "conflict") {
      title.textContent = "Done Processing Failure — Merge Collision";
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
        li.textContent = "(no pistol file list)";
        ul.appendChild(li);
      }
      body.appendChild(ul);
      const guide = document.createElement("p");
      guide.textContent = "Solve crashes in worktree and try again.";
      body.appendChild(guide);
    } else if (kind === "dirty") {
      title.textContent = "Done Processing Failure — Minorm Change";
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
        li.textContent = "(No Micommit File List)";
        ul.appendChild(li);
      }
      body.appendChild(ul);
      const guide = document.createElement("p");
      guide.textContent = "commit changes in worktrees or process flow-merge and try again.";
      body.appendChild(guide);
    } else {
      title.textContent = "Done processing failed";
      const msg = document.createElement("p");
      msg.textContent = (payload && payload.message) ? payload.message : "You can't see the error.";
      body.appendChild(msg);
    }

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    closeBtn.textContent = "About Us";

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
   * T-905 Phase 3: Done card click → "Review" check modal.
   *
   * push(local-only) / push(origin/develop reach) branch guide + force option checkbox.
   * pre-detect: pre-check whether the kanban result.merge commit exists
   * Please note that the force option is required when missing.
   *
   * @param {Object} ticket - Done column card ticket object (number/result included)
   * @param {Function} onConfirm - confirm callback (force: bool argument passed)
   * @param {Function} onCancel - Cancel/ESC/overlay Callback
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
    title.appendChild(document.createTextNode(ticket.number + "Review"));

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    const intro = document.createElement("p");
    intro.textContent = "Revert Done processing of this ticket. Developing the thumb result automatically quarterly NEWS";
    body.appendChild(intro);

    const ul = document.createElement("ul");
    const li1 = document.createElement("li");
    li1.textContent = "reset --hard";
    const li2 = document.createElement("li");
    li2.textContent = "after push(includes origin/develop): add reverse commit to revert -m 1 (noforce-push)";
    const li3 = document.createElement("li");
    li3.textContent = "feature Brand + Worktree Regeneration + Kanban Done → Review Forced Battle";
    ul.appendChild(li1);
    ul.appendChild(li2);
    ul.appendChild(li3);
    body.appendChild(ul);

    // result.merge commit
    const result = ticket.result || {};
    const hasMergeCommit = !!(result.merge_commit && String(result.merge_commit).trim());
    if (!hasMergeCommit) {
      const warn = document.createElement("p");
      warn.style.color = "#D97757";
      warn.style.fontWeight = "600";
      warn.textContent = "Note: This ticket does not have merge commit information (Phase 1 Infrastructure introduced earlier Done). To try reflog fallback, please enable the following force option:";
      body.appendChild(warn);
    }

    // force option checkbox
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
    forceLabel.textContent = "--force (lower warning ignore + reflog fallback activation)";
    forceWrapper.appendChild(forceCheckbox);
    forceWrapper.appendChild(forceLabel);
    body.appendChild(forceWrapper);

    const tail = document.createElement("p");
    tail.style.marginTop = "10px";
    tail.textContent = "About Us";
    body.appendChild(tail);

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    cancelBtn.textContent = "Venue";

    const confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    confirmBtn.textContent = "Review";

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
   * T-905 Phase 3: undo-done results modal.
   * showDoneResultModal pattern answer.
   *
   * "reset ok"
   * @param {Object} payload - result data
   *   - reset_ok / revert_ok: { ticket, strategy, branch, worktree_path, message }
   *   - error: { ticket, error, message, stderr }
   * @param {Function} onClose - Close callbacks (Utilization on automatic new callbacks in the field)
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
      title.textContent = "Review";

      const summary = document.createElement("p");
      const ticketStr = payload.ticket || "";
      const strategyStr = payload.strategy
        ? (payload.strategy === "reset" ? "reset --hard (push ago)" : payload.strategy === "revert" ? "revert -m 1 (after push)" : payload.strategy)
        : "?";
      summary.textContent = ticketStr + "Rollback Finished — Strategy:" + strategyStr;
      body.appendChild(summary);

      if (payload.branch) {
        const br = document.createElement("p");
        br.textContent = "Renewable feature Brand:" + payload.branch;
        body.appendChild(br);
      }
      if (payload.worktree_path) {
        const wt = document.createElement("p");
        wt.textContent = "Renewable Worktree:" + payload.worktree_path;
        body.appendChild(wt);
      }

      const guideTitle = document.createElement("p");
      guideTitle.style.marginTop = "10px";
      guideTitle.style.fontWeight = "600";
      guideTitle.textContent = "Tag:";
      body.appendChild(guideTitle);
      const ol = document.createElement("ol");
      const liE = document.createElement("li");
      liE.textContent = "/wf -e " + ticketStr + "Edit tickets or edit them directly";
      const liS = document.createElement("li");
      liS.textContent = "/wf -s " + ticketStr + "Skip to content";
      ol.appendChild(liE);
      ol.appendChild(liS);
      body.appendChild(ol);
    } else {
      title.textContent = "Review";
      const msg = document.createElement("p");
      msg.textContent = (payload && (payload.error || payload.message)) || "You can't see the error.";
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
    closeBtn.textContent = "About Us";

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
   * T-905 Phase 3: Done card context menu (click).
   *
   * "Review" single item exposure. showUndoDoneConfirmModal calls when clicked.
   * Click documentLevel or close to ESC.
   *
   * contextmenu
   * @param {Object} ticket - Done card ticket object
   */
  function showDoneCardContextMenu(event, ticket) {
    // Removed if the existing context menu is open
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
    item.textContent = "Review";
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
          // [Review by Rollback] Callback
          fetch("/api/kanban/undo-done", {
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
          // Cancel: No
        }
      );
    });

    menu.appendChild(item);
    document.body.appendChild(menu);

    // location correction: not to go out of viewport
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

    // External Click / Close to ESC
    setTimeout(function () {
      document.addEventListener("click", outsideHandler, true);
      document.addEventListener("keydown", onKey);
    }, 0);
  }

  /**
   * T-418: Open Card context menu (click).
   *
   * 2 menu items:
   *   - "Done" → showOpenDoneConfirmModal call
   *   - "TubeDupe" → showDeleteConfirmModal call
   *
   * showDoneCardContextMenu (T-905)
   *
   * contextmenu
   * @param {Object} ticket - Open card ticket object
   */
  function showOpenCardContextMenu(event, ticket) {
    // Removed if the existing context menu is open
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

    const doneItem = makeMenuItem("Done");
    const deleteItem = makeMenuItem("TubeDupe", "#f48771");

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

    // "Done" Click Handler
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
          // Cancel: No
        }
      );
    });

    // "TubeDupe" click handler
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
                const derivedList = (r.body.derived_tickets || []).join(", ") || "(No roll)";
                Board.util.showInfoModal("Delete block", "Deletion: Derivative tickets are unfinished. \\n\\nComplete Derivative Ticket:" + derivedList + "Complete the \\n\\n parasite ticket first.", { severity: "warning", onClose: function () { renderKanban(); } });
              } else {
                Board.util.showInfoModal("Delete failed", "Delete Failure:" + ((r.body && r.body.message) || "Unknown Errors"), { severity: "error", onClose: function () { renderKanban(); } });
              }
            }
          }).catch(function (err) {
            console.error("[kanban Open contextmenu] delete failed:", err);
            Board.util.showInfoModal("Delete failed", "Delete Failure:" + err.message, { severity: "error", onClose: function () { renderKanban(); } });
          });
        },
        function () {
          // Cancel: No
        }
      );
    });

    menu.appendChild(doneItem);
    menu.appendChild(deleteItem);
    document.body.appendChild(menu);

    // location correction: not to go out of viewport
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

    // External Click / Close to ESC
    setTimeout(function () {
      document.addEventListener("click", outsideHandler, true);
      document.addEventListener("keydown", onKey);
    }, 0);
  }

  /**
   * Review Card Click context menu.
   * Optional: (a) Open to rework (POST /api/kanban/move).
   * Chat attachments to DnD (T-427).
   * Review → Before In Progress, the User Expiration (2026-05-08).
   *
   * contextmenu
   * @param {Object} ticket - Review card ticket object
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

    const reopenItem = makeMenuItem("Rework with Open");

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
          Board.util.showInfoModal("Rework failed", "Pre-work failed:" + ((r.body && r.body.error) || "Unknown Errors"), { severity: "error", onClose: function () { renderKanban(); } });
        }
      }).catch(function (err) {
        Board.util.showInfoModal("Rework failed", "Rework request failed:" + (err && err.message ? err.message : err), { severity: "error", onClose: function () { renderKanban(); } });
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
   * Card drag and drop handler registration (T-399: To Do ↔ Open + Open → In Progress).
   * T-906: Review → Add Done drop (confirm delivery + cmd done commission + result delivery).
   *
   * dragstart: Save the ticket number + Departure column to dataTransfer.
   * dragover: dragover-active display in dropable cards-droppable area.
   * drop:
   *   - To Do ↔ Open: POST /api/kanban/move (In short time)
   *   - Open → In Progress: Confirm Modal → POST /api/kanban/submit (Workflow Execution)
   *   - Review → Done: confirm Modal → POST /api/kanban/done (cmd done)
   * dragend: Clean up your visual feedback class.
   *
   * In Progress card drag Invalid protection (delete degradation).
   * Review → Done drop only confirm Modal allowed (T-906).
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
        // T-427: Pass the ticket JSON payload to MIME separately (for terminal drop branch only)
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
          } catch (ex) { /* Some browser limits — ignore */ }
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
     * draggedFrom → targetCol prefix.
     * Payment Terms:
     *   To Do  → To Do(reorder) | Open
     *   Open   → To Do | In Progress | Review | Done
     *   Review → Done | Open
     * Other combinations deny drop in dragover phase (Browner cursor is no-drop display).
     */
    function isValidDropTarget(fromCol, targetCol) {
      if (fromCol === "To Do") return targetCol === "To Do" || targetCol === "Open";
      if (fromCol === "Open") return targetCol === "To Do" || targetCol === "In Progress" || targetCol === "Review" || targetCol === "Done";
      if (fromCol === "Review") return targetCol === "Done" || targetCol === "Open";
      return false;
    }

    /**
     * To Do manual alignment mode such as column reorder dragover when insert position indicator placement.
     * insert/move the indicator element inside the zone after the target index calculation of Y coordinates.
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
        // Unvalid predecessor drop self-reject (preventDefault migration → browser drop block)
        if (!isValidDropTarget(draggedFrom, zone.dataset.colKey)) {
          e.dataTransfer.dropEffect = "none";
          return;
        }
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        zone.classList.add("dragover-active");
        // To Do manual sorting + like column drag — insert location indicator display
        if (zone.dataset.colKey === "To Do" && draggedFrom === "To Do"
            && kanbanSort["To Do"] && kanbanSort["To Do"].key === "manual") {
          placeDropIndicator(zone, e.clientY);
        }
      });
      zone.addEventListener("dragleave", function (e) {
        // Only cleans up when you go out of real zone (Ignore the child element entry)
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
        // drop in column: To Do manual alignment mode only support, rest ignore
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

        // T-399: In Progress drop quarter — Open card only allowed + confirm modal
        // Review Card Done Unlike columns to drop — block
        // T-418: To Do ↔ Open logic when trying to drop the Open Card to Done outside column
        if (draggedFrom === "Review" && targetCol !== "Done" && targetCol !== "Open") {
          Board.util.showInfoModal("DnD Lockout", "Review cards can only be dragging with Done or Open columns.", { severity: "warning", onClose: function () { renderKanban(); } });
          return;
        }

        if (targetCol === "In Progress") {
          if (draggedFrom !== "Open") {
            // In Progress move directly from other columns such as To Do
            Board.util.showInfoModal(
              "To Do → In Progress",
              "To Do Card cannot be transferred directly to In Progress. \\nReturn to Open",
              {
                severity: "info",
                onClose: function () {
                  renderKanban();
                }
              }
            );
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
              // [Run] Callback: POST /api/kanban/submit → driver
              // Stage 3-B race fix: registerLaunchStarting is called in fetch *function*
              // SSE LAUNCH STARTED guarantees that even if you arrive faster than HTTP response.
              // Instantly cleanupLaunchState when failure (stuck regression).
              const submitTicket = ticketObj.number;
              const submitCommand = command;
              registerLaunchStarting(submitTicket, submitCommand);
              fetch("/api/kanban/submit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ticket: submitTicket, command: submitCommand }),
              }).then(function (res) {
                if (!res.ok) {
                  return res.json().then(function (j) {
                    throw { kind: "http", status: res.status, body: j };
                  }, function () {
                    throw { kind: "http", status: res.status, body: null };
                  });
                }
                return res.json();
              }).then(function (body) {
                if (!body || body.status !== "starting") {
                  // static response — launchState clearance (registration complete fetch position)
                  cleanupLaunchState(submitTicket);
                } else if (body.session_id && Board.workflowTabStorage
                           && Board.workflowTabStorage.add) {
                  // T-516 — submit response body.session id also localStorage.
                  // Launch SSE LAUNCH STARTED handler and OR conditions — Helper dedupe safety.
                  Board.workflowTabStorage.add(body.session_id);
                }
                fetchTickets().then(function () { renderKanban(); });
              }).catch(function (err) {
                cleanupLaunchState(submitTicket);
                console.error("[kanban DnD] submit failed:", err);
                if (err && err.kind === "http") {
                  // T-475 Stage 3 Static: HTTP 504 alone waiting for Modal Mileage (SSE LAUNCH FAILED).
                  // The 504 itself disappears after this synchronousization, but the defending quarterly preserved.
                  if (err.status === 504) {
                    renderKanban();
                  } else {
                    Board.util.showInfoModal("Skip to content",
                      formatHttpRejectMessage(err.status, err.body),
                      { severity: "error", onClose: function () { renderKanban(); } });
                  }
                } else {
                  // network / abort / other — instant notifications to users
                  Board.util.showInfoModal("Workflow failed to run",
                    "Tag:" + ((err && err.message) || String(err)),
                    { severity: "error", onClose: function () { renderKanban(); } });
                }
              });
            },
            function () {
              // [Cancel]/ESC/overlay callback: Return card origin
              renderKanban();
            }
          );
          return;
        } else if (targetCol === "Done") {
          // T-906: Review → Done drop quarter
          // T-418: Open → Done direct prefix
          if (draggedFrom !== "Review" && draggedFrom !== "Open") {
            Board.util.showInfoModal("DnD Lockout", "You can drag only Done with Review or Open Card.", { severity: "warning", onClose: function () { renderKanban(); } });
            return;
          }
          const doneTicketObj = (Board.state.TICKETS || []).find(function (t) {
            return t.number === draggedNum;
          });
          if (!doneTicketObj) {
            renderKanban();
            return;
          }
          // dragend has a modal callback before running the regression that is reset to draggedNum=null:
          // Preserve ticket number to closure capture variable
          const capturedNum = draggedNum;

          if (draggedFrom === "Open") {
            // T-418: Open → Done Direct Transfer (force=true)
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
                // [Cancel]/ESC/overlay callback: Return card origin
                renderKanban();
              }
            );
          } else {
            // T-906: Review → Done drop
            showDoneConfirmModal(
              doneTicketObj,
              function () {
                // [Completion] Callback: POST /api/kanban/done → cmd done commission
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
                // [Cancel]/ESC/overlay callback: Return card origin
                renderKanban();
              }
            );
          }
          return;
        }

        // To Do allows to move only to Open (Review/Other Blocks)
        if (draggedFrom === "To Do" && targetCol !== "Open") {
          Board.util.showInfoModal("DnD Lockout", "To Do cards can be dragging only to Open Column.", { severity: "warning", onClose: function () { renderKanban(); } });
          return;
        }

        // To Do ↔ Open ↔ Review Simplified (includes Open → Review direct transfer)
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
          Board.util.showInfoModal("Ticket Transfer Failure", "Ticket Transfer Failure:" + err.message, { severity: "error" });
        });
      });
    });
  }

  /** Renders the kanban board with columns, cards, and sort controls. */
  function renderKanban() {
    // Dismiss any stale popover before re-rendering the board DOM
    hideRelationsPopover();

    const el = document.getElementById("view-kanban");
    // scroll-top location capture by column — scrollTop restore lost with innerHTML rotation
    const scrollPositions = {};
    el.querySelectorAll(".cards[data-col-key]").forEach(function (cards) {
      scrollPositions[cards.dataset.colKey] = cards.scrollTop;
    });
    let h = renderWorkRequestAuthoring();
    h += '<div class="kanban-board">';
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
      // To Do Column adds the option "About Us" in front of the main
      let dropHtml = '<div class="col-sort-dropdown" data-col="' + esc(col.key) + '">';
      const sortKeysForCol = (col.key === "To Do")
        ? [{ key: "manual", label: "About Us" }].concat(SORT_KEYS)
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

      // Done / To Do Column Supports Fold Toggle
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
        // Folded Status: Vertical Bar Rendering
        h += '<div class="column-collapsed-bar" data-col-key="' + esc(col.key) + '">';
        h += '<span class="bar-label">' + esc(col.label) + '</span>';
        h += '<span class="bar-count">' + items.length + '</span>';
        h += '</div>';
      } else {
        // Unfolded Status: Original Header + Card Rendering
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
        // <img height="1" width="1" alt="" alt="" src="https://www.facebook.com/tr?id=2" />
        // T-399: Added to In Progress drop target (available only on Open → In Progress check modal).
        // T-906: Added to Done drop target (Review → Done drop only confirm accepted as modal).
        // Open → Review Adds Directly: Review also drop target.
        const isDroppable = (col.key === "To Do" || col.key === "Open" || col.key === "In Progress" || col.key === "Done" || col.key === "Review");
        const droppableClass = isDroppable ? ' cards-droppable' : '';
        h += '<div class="cards' + droppableClass + '" data-col-key="' + esc(col.key) + '">';
        if (sortedItems.length === 0) {
          h += '<div class="empty">No items</div>';
        } else {
          sortedItems.forEach(function (t) {
            const done = col.key === "Done" ? " done" : "";
            const status = getWorkflowStatus(t);
            // DnD: To Do / Open column card only draggable.
            // T-399: In Progress card drag indispensable protection (blocking workflow cancellations).
            // T-906: Added Review card draggable (Review → Done drop allowed).
            // Done card is draggable=false (preventive protection).
            const isDraggable = (col.key === "To Do" || col.key === "Open" || col.key === "Review");
            const draggableAttr = isDraggable ? ' draggable="true"' : '';
            const draggableClass = isDraggable ? ' card-draggable' : '';
            // T-433 Phase 2: The Review Card has-active-branch class grant (external glow vision).
            const branchActiveClass = (col.key === "Review" && _activeBranchTicket === t.number) ? ' has-active-branch' : '';
            h += '<div class="card' + done + draggableClass + branchActiveClass + '" data-num="' + esc(t.number) + '" data-col-key="' + esc(col.key) + '"' + draggableAttr + '>';
            // Top: Left Group (Ticket number + Command badge), Right Status Label
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
              h += '<span class="card-status ' + status.cssClass + '">' + esc(status.label) + "</span>";
            }
            h += renderUncommittedBadge(t.number);
            // T-457 (Layer 3): failure tag (ticket.failure exists) — guards inside the helper
            h += renderFailureTag(t);
            // T-475 Stage 3: Start starting pulse badge (submit right after ~ LAUNCH STARTED before receiving)
            h += renderLaunchBadge(t.number);
            // T-441: Done Card verdict badge (advisory)
            if (col.key === "Done") {
              h += renderDoneVerdictBadge(t.number);
            }
            // T-477: Review Card Auditor T3 Auditor (advisory only)
            if (col.key === "Review") {
              h += renderAuditBadgeHtml(t.number);
            }
            h += "</div>";
            h += "</div>";
            // 2nd row: title (2 row clamp)
            h += '<div class="card-mid"><div class="card-title">' + esc(t.title || "(No title)") + "</div></div>";
            // 3: Relationship & Dependence (no spot conservation)
            h += '<div class="card-relations-row">';
            const hasRelations = t.relations && t.relations.length > 0;
            if (hasRelations) {
              h += renderRelations(t);
            }
            h += '</div>';
            // 4: Action button (no spot conservation, keep card height schedule)
            h += '<div class="card-actions-row">';
            // T-463: Review Card verdict badge (advisory only).
            // 4th action-row first child + margin-right:auto to left fixed, right commit/branch-toggle/done and separating.
            // Auto-blocking / forced pre-determined by verdict results $0 — user-sharing freedom.
            if (col.key === "Review") {
              h += renderReviewVerdictBadge(t.number);
            }
            // T-457 (Layer 3): Micommit Worktree Commit Action Button — Mark if any column or micommit.
            // flex-end + left → enter the order commit to this left, done this position on the right side.
            if (_worktreeUncommittedMap) {
              var uitem = _worktreeUncommittedMap.get(t.number);
              if (uitem && uitem.uncommitted_count > 0) {
                var ctip = "Mickey Mouse" + uitem.uncommitted_count + "— Click Commit";
                h += '<button class="card-commit-action" data-commit-ticket="' + esc(t.number) + '" title="' + esc(ctip) + '" draggable="false">';
                // SVG: Commit graph dot motif (won + short line up/down)
                h += '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">';
                h += '<circle cx="7" cy="7" r="2.4" stroke="currentColor" stroke-width="1.6" fill="none"/>';
                h += '<line x1="7" y1="0.5" x2="7" y2="4.0" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>';
                h += '<line x1="7" y1="10.0" x2="7" y2="13.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>';
                h += '</svg>';
                h += '</button>';
              }
            }
            // In Progress card: Workflow stop button (POST /api/workflow/stop) — 4 axis (process/jsonl/bar/worktree) integration.
            if (col.key === "In Progress") {
              h += '<button class="card-stop-action" data-stop-ticket="' + esc(t.number) + '" title="Stop workflow (Proceed/jsonl/Collection/Worktree 4)" draggable="false">';
              h += '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">';
              h += '<rect x="3" y="3" width="8" height="8" rx="1" stroke="currentColor" stroke-width="1.6" fill="currentColor"/>';
              h += '</svg>';
              h += '</button>';
            }
            if (col.key === "Review") {
              // T-433 Phase 2: Feature Brand-Activate/Remote Toggle Button (4-row left, batch button on left).
              // OFF: Grey outline / ON: Terracotta + Card Exterior Light glow.
              // Only one card is active guarantee —  activeBranchTicket status standard .active grant.
              var isBranchActive = (_activeBranchTicket === t.number);
              var toggleClass = isBranchActive ? " active" : "";
              var toggleTip = isBranchActive
                ? "feature Brand Name Active — Click to Return to develop"
                : "Click to switch main working tree to this feature branch";
              h += '<button class="card-branch-toggle' + toggleClass + '" data-branch-ticket="' + esc(t.number) + '" title="' + esc(toggleTip) + '" draggable="false">';
              // Lucide git-branch SVG (16px, currentColor) — e749003 Vocabulary Match
              h += '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">';
              h += '<line x1="6" y1="3" x2="6" y2="15"/>';
              h += '<circle cx="18" cy="6" r="3"/>';
              h += '<circle cx="6" cy="18" r="3"/>';
              h += '<path d="M18 9a9 9 0 0 1-9 9"/>';
              h += '</svg>';
              h += '</button>';
              h += '<button class="card-done-action" data-num="' + esc(t.number) + '" title="finishing" draggable="false">';
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

    var wrAuthor = el.querySelector(".wr-author");
    if (wrAuthor) {
      var toggle = wrAuthor.querySelector(".wr-author-toggle");
      if (toggle) {
        toggle.addEventListener("click", function () {
          var next = !wrAuthor.classList.contains("expanded");
          saveWorkRequestFormExpanded(next);
          renderKanban();
        });
      }
      wrAuthor.querySelectorAll("[data-wr-action]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          submitWorkRequest(wrAuthor, btn.dataset.wrAction);
        });
      });
    }

    // ScrollTop Restore Capture
    Object.keys(scrollPositions).forEach(function (colKey) {
      const cards = el.querySelector('.cards[data-col-key="' + colKey + '"]');
      if (cards) cards.scrollTop = scrollPositions[colKey];
    });

    // Bind card clicks
    el.querySelectorAll(".card").forEach(function (card) {
      card.addEventListener("click", function (e) {
        // T-457 (Layer 3): 4th Commit button click → Worktree auto commit action commission.
        // .card-uncommitted-badge is modified to read-only mark label — no click trigger)
        var commitBtn = e.target.closest(".card-commit-action");
        if (commitBtn) {
          e.stopPropagation();
          handleCommitButtonClick(commitBtn);
          return;
        }
        // In Progress card 4 workflow stop button → handleStopButtonClick position
        var stopBtn = e.target.closest(".card-stop-action");
        if (stopBtn) {
          e.stopPropagation();
          handleStopButtonClick(stopBtn);
          return;
        }
        // T-433 Phase 2: Click on the Brand Match Toggle button on the Review card → enter handleBranchToggleClick
        var branchToggle = e.target.closest(".card-branch-toggle");
        if (branchToggle) {
          e.stopPropagation();
          var bnum = branchToggle.dataset.branchTicket || card.dataset.num;
          handleBranchToggleClick(bnum);
          return;
        }
        // T-439: Review Card Velvet Finished Action Button Click → HandleReviewDoneAction
        var doneAction = e.target.closest(".card-done-action");
        if (doneAction) {
          e.stopPropagation();
          const num = card.dataset.num;
          const ticket = Board.state.TICKETS.find(function (t) { return t.number === num; });
          if (ticket) handleReviewDoneAction(ticket);
          return;
        }
        // T-441: Done card verdict FAIL badge click → Show details message (advisory)
        var verdictFail = e.target.closest(".card-done-verdict.verdict-fail");
        if (verdictFail) {
          e.stopPropagation();
          var ticketNum = card.dataset.num;
          var msg = verdictFail.dataset.verdictMsg || "Develop head is mitigating";
          var verdictData = ticketNum ? _doneVerdictMap[ticketNum] : null;
          var detail = (verdictData && verdictData.details) || {};
          var bodyMsg = msg;
          if (detail.develop_head) bodyMsg += "\n\ndevelop HEAD : " + detail.develop_head.slice(0, 8);
          if (detail.merge_commit) bodyMsg += "\nmerge commit: " + detail.merge_commit.slice(0, 8);
          bodyMsg += "\\n\\n may not be reflected in development. \\n* advisory only — no automatic ream. Please check it manually.";
          Board.util.showInfoModal("Mage Commodity FAIL", bodyMsg, { severity: "warning" });
          return;
        }
        const num = card.dataset.num;
        const ticket = Board.state.TICKETS.find(function (t) { return t.number === num; });
        if (ticket) Board.render.openViewer(ticket);
      });
    });

    // T-905 Phase 3: Right-click context menu binding to Done column card ("Review")
    el.querySelectorAll('.card[data-col-key="Done"]').forEach(function (card) {
      card.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        const num = card.dataset.num;
        const ticket = Board.state.TICKETS.find(function (t) { return t.number === num; });
        if (ticket) showDoneCardContextMenu(e, ticket);
      });
    });

    // T-441: Done Card verdict fetch trigger (advisory)
    el.querySelectorAll('.card[data-col-key="Done"]').forEach(function (card) {
      var num = card.dataset.num;
      if (num) {
        // Mickey Card Only Fetch (Skip when hitting)
        fetchAndRenderVerdict(num);
      }
    });

    // T-463: Review Card Verdict Fetch Trigger (advisory only)
    // One call (no locking) when card mount. Skip to main content
    el.querySelectorAll('.card[data-col-key="Review"]').forEach(function (card) {
      var num = card.dataset.num;
      if (num) {
        fetchAndRenderReviewVerdict(num);
      }
    });

    // T-477: Review card audit verdict fetch trigger (advisory)
    el.querySelectorAll('.card[data-col-key="Review"]').forEach(function (card) {
      var num = card.dataset.num;
      if (num) {
        fetchAndRenderAuditVerdict(num);
      }
    });

    // T-418: Right-click context menu binding on Open Column Card ("Done" + "Tube")
    el.querySelectorAll('.card[data-col-key="Open"]').forEach(function (card) {
      card.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const num = card.dataset.num;
        const ticket = Board.state.TICKETS.find(function (t) { return t.number === num; });
        if (ticket) showOpenCardContextMenu(e, ticket);
      });
    });

    // Review Click context menu binding on column card ("Rework with Open" single option)
    el.querySelectorAll('.card[data-col-key="Review"]').forEach(function (card) {
      card.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const num = card.dataset.num;
        const ticket = Board.state.TICKETS.find(function (t) { return t.number === num; });
        if (ticket) showReviewCardContextMenu(e, ticket);
      });
    });

    // ── DnD: To Do ↔ Open Card Drag & Drop ──
    // Safety DnD Policy: Exemption without cracking effect allowed (In Progress / Done separately command)
    // T-418: Open → Done allows direct transition check modal (force=true)
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

    // Bind collapse toggle buttons (unfolded). Done/To Do Common.
    el.querySelectorAll(".column-toggle-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        const colKey = btn.dataset.colKey;
        if (!colKey) return;
        saveColumnCollapsed(colKey, !loadColumnCollapsed(colKey));
        renderKanban();
      });
    });

    // Bind collapsed bar click (directed → unfold). Done/To Do Common.
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

    // T-433 Phase 2: Initial fetch in the first active branch in the page load (after call is ignored by guard).
    // syncActiveBranchFromSSE is synchronized when SSE git branch event arrives.
    fetchAndApplyActiveBranch();
  }

  // ──────────────────────────────────────────────────────────────────────
  // T-475 Stage 3 Helper — launch asynchronous client state machine
  // ──────────────────────────────────────────────────────────────────────

  /**
   * Starting status card 1 right-hand pulse badge HTML.
   * Exposure while the ticket registered in launchState is 'starting'.
   */
  function renderLaunchBadge(ticketNum) {
    const cur = launchState.get(ticketNum);
    if (!cur || cur.state !== "starting") return "";
    return '<span class="card-launch-badge">';
  }

  /**
   * launchState + sessionStorage cleanup single entry point.
   * grace timer Clear + Delete Map + Delete storage + (Optional) renderKanban.
   * Close-up helper for stuck revolving blocks.
   */
  function cleanupLaunchState(ticketNum, opts) {
    const cur = launchState.get(ticketNum);
    if (cur && cur.graceTimer) clearTimeout(cur.graceTimer);
    launchState.delete(ticketNum);
    try { sessionStorage.removeItem(LAUNCH_STORAGE_PREFIX + ticketNum); } catch (_) {}
    if (opts && opts.render && Board.render && Board.render.renderKanban) {
      Board.render.renderKanban();
    }
  }

  /**
   * Apache HTTP Server Version 2.0
   * sessionStorage persist (for page refreshment restore).
   *
   * For SSE race blocking, you must call submit fetch *Commission*.
   * SSE LAUNCH STARTED is a handleLaunchEvent if you arrive faster than HTTP response
   * Guaranteed to find the launchState (i.e. call → SSE missing).
   */
  function registerLaunchStarting(ticketNum, command) {
    // Default object view. Click to enlarge
    const prev = launchState.get(ticketNum);
    if (prev && prev.graceTimer) clearTimeout(prev.graceTimer);
    const since = Date.now();
    const entry = {
      state: "starting",
      since: since,
      command: command,
      sessionId: null,
      graceTimer: setTimeout(function () { onGraceExpired(ticketNum); }, LAUNCH_GRACE_MS),
    };
    launchState.set(ticketNum, entry);
    try {
      sessionStorage.setItem(
        LAUNCH_STORAGE_PREFIX + ticketNum,
        JSON.stringify({ state: "starting", since: since, command: command })
      );
    } catch (_) { /* quota / disabled — in action */ }
  }

  /**
   * SSE 'launch' event handler — call sse.js to a single entry point (addEventListener duplicate).
   *   data.event ∈ {LAUNCH_PENDING, LAUNCH_STARTED, LAUNCH_FAILED}
   * LAUNCH PENDING is registered directly after the submission of this client, so it is unnecessary to handle (for other CL monitoring).
   */
  function handleLaunchEvent(data) {
    if (!data || !data.ticket) return;
    const ticketNum = data.ticket;
    const cur = launchState.get(ticketNum);
    // This client only handles the submitted card — other tabs/browser submits are synchronized with fetchTickets
    if (!cur) return;

    if (data.event === "LAUNCH_STARTED") {
      if (cur.graceTimer) clearTimeout(cur.graceTimer);
      launchState.set(ticketNum, {
        state: "running",
        since: cur.since,
        command: cur.command,
        sessionId: data.session_id || "",
        graceTimer: null,
      });
      // T-495 P2 — production-line ramen session id to board.productionLineWorkflow
      // Instantly register and follow-up session-switcher/workflow-sessions is a production-line branch
      // to be recognized. mode=production line This specifies or session id is wf- prefix.
      if (data.session_id && Board.productionLineWorkflow && Board.productionLineWorkflow.registerKnown
          && (data.mode === "production_line" || data.mode === "v2" || data.session_id.indexOf("wf-") === 0)) {
        Board.productionLineWorkflow.registerKnown(data.session_id);
        // workflow-sessions Instant refresh — Display the production-line tab on the tab bar
        if (Board.workflowSessions && Board.workflowSessions.refresh) {
          try { Board.workflowSessions.refresh(); } catch (_) {}
        }
      }
      // T-516 — Workflow ID to localStorage single source.
      // Because the helper handles dedupe, submit response add calls and compatible safety (OR conditions).
      if (data.session_id && Board.workflowTabStorage && Board.workflowTabStorage.add) {
        Board.workflowTabStorage.add(data.session_id);
      }
      // After running, it is necessary to remove the badge immediately after running, so it is possible to clean the launchState immediately.
      // However, debug/released after conserving the possibility of SSE (the following renderKanban calls disappeared).
      launchState.delete(ticketNum);
      try { sessionStorage.removeItem(LAUNCH_STORAGE_PREFIX + ticketNum); } catch (_) {}
      // Remove Badge + In Progress Column Top Mark
      if (Board.render.renderKanban) Board.render.renderKanban();
    } else if (data.event === "LAUNCH_FAILED") {
      if (cur.graceTimer) clearTimeout(cur.graceTimer);
      launchState.delete(ticketNum);
      try { sessionStorage.removeItem(LAUNCH_STORAGE_PREFIX + ticketNum); } catch (_) {}
      Board.util.showInfoModal(
        "Workflow failed to run",
        formatLaunchFailReason(data.reason, data.error_message),
        {
          severity: "error",
          onClose: function () {
            if (Board.fetch.fetchTickets && Board.render.renderKanban) {
              Board.fetch.fetchTickets().then(function () { Board.render.renderKanban(); });
            }
          },
        }
      );
    }
    // LAUNCH PENDING
  }

  /**
   * grace 60s Expiration — Stage 3-B fix:
   * modal display + launchState/sessionStorage automatic cleanup (stuck regression block).
   *
   * Change Previous: "About Us" badge permanent residency even after launchState preservation → user "About Us"
   * + Restoration sessionStorage → Restoration. "SSE Late Processing"
   * However, if the SSE inside the 60s, the failure is considered natural — auto cleanup is corrected.
   */
  function onGraceExpired(ticketNum) {
    const cur = launchState.get(ticketNum);
    if (!cur || cur.state !== "starting") return;
    cleanupLaunchState(ticketNum);
    if (Board.render && Board.render.renderKanban) Board.render.renderKanban();
  }

  /**
   * reason enum → user friendly Korean messages.
   * enum synchronization with classify failure reason: to do status / http post timeout /
   * http_post_error / workflow_start_error / reader_loop_exception / unknown.
   */
  function formatLaunchFailReason(reason, errorMessage) {
    var label;
    switch (reason) {
      case "to_do_status":
        label = "Tickets are To Do status. Go to Open and try again.";
        break;
      case "http_post_timeout":
        label = "Board server did not respond to your workflow startup request. Check the server status.";
        break;
      case "http_post_error":
        label = "Board server communication has occurred network errors.";
        break;
      case "workflow_start_error":
        label = "failed in the workflow spawn step. See Worktree/git status.";
        break;
      case "reader_loop_exception":
        label = "We’ve got an exception from the workflow start monitor itself. Check Board server logs.";
        break;
      default:
        label = "I've failed to start workingflow with unknown reasons.";
        break;
    }
    var detail = (errorMessage || "").toString().trim();
    if (detail.length > 0) {
      // Too long, some cut user modal toxic protection (full board server log)
      if (detail.length > 400) detail = detail.slice(0, 400) + "…";
      return label + "\\n\\n" + detail;
    }
    return label;
  }

  /**
   * User messages for HTTP 4xx/5xx (504 excluded) responses.
   * if body.error is used first, not the status only.
   */
  function formatHttpRejectMessage(status, body) {
    var detail = "";
    if (body && typeof body === "object") {
      if (body.error) detail = String(body.error);
      else if (body.message) detail = String(body.message);
    }
    var prefix = "HTTP " + status + "— Board server refused to run workflow.";
    return detail ? prefix + "\\n\\n" + detail : prefix;
  }

  /**
   * Restoration of the sessionStorage after page load.
   * grace residual time reorganization (now - since standard), immediately call onGraceExpired.
   * One call in the Board init stream (sse.js).
   */
  function restoreLaunchStateFromStorage() {
    var keys = [];
    try {
      for (var i = 0; i < sessionStorage.length; i++) {
        var k = sessionStorage.key(i);
        if (k && k.indexOf(LAUNCH_STORAGE_PREFIX) === 0) keys.push(k);
      }
    } catch (_) { return; }

    keys.forEach(function (key) {
      var raw;
      try { raw = sessionStorage.getItem(key); } catch (_) { return; }
      if (!raw) return;
      var stored;
      try { stored = JSON.parse(raw); } catch (_) {
        try { sessionStorage.removeItem(key); } catch (_) {}
        return;
      }
      if (!stored || stored.state !== "starting") {
        try { sessionStorage.removeItem(key); } catch (_) {}
        return;
      }
      var ticketNum = key.slice(LAUNCH_STORAGE_PREFIX.length);
      var since = stored.since || Date.now();
      var elapsed = Date.now() - since;
      var remaining = LAUNCH_GRACE_MS - elapsed;
      if (remaining <= 0) {
        // already grace expired stuck — Stage 3-B fix: natural cleanup (modal display X).
        // SSE at the time of refreshing page is separately mapped (workflow step / launch event)
        // If the card status is exactly displayed, it is enough to clean this sessionStorage statement.
        try { sessionStorage.removeItem(key); } catch (_) {}
        return;
      } else {
        launchState.set(ticketNum, {
          state: "starting",
          since: since,
          command: stored.command || "",
          sessionId: null,
          graceTimer: setTimeout(function () { onGraceExpired(ticketNum); }, remaining),
        });
      }
    });
  }

  // ── Register on Board namespace ──
  Board.fetch.fetchTickets = fetchTickets;
  Board.fetch.fetchTicketsByFiles = fetchTicketsByFiles;
  Board.render.renderKanban = renderKanban;
  // T-433 Phase 2: SSE git branch event listener calls synchronized entry-point.
  // (sse.js has a single listener — addEventListener duplicate registration prevention §2.4)
  Board.render.syncActiveBranchFromSSE = syncActiveBranchFromSSE;

  // T-475 Stage 3: SSE 'launch' event dispatch + restore entry-point when loading page.
  // (sse.js single listener call Board.kanban.handleLaunchEvent — addEventListener duplicate)
  Board.kanban = Board.kanban || {};
  Board.kanban.handleLaunchEvent = handleLaunchEvent;
  Board.kanban.restoreLaunchStateFromStorage = restoreLaunchStateFromStorage;

  // T-473: Bind relations popover delegated events once at module init time.
  // bindRelationsPopoverEvents() is idempotent (_relPopoverBound guard),
  // but we call it once here to ensure listeners are registered before first render.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindRelationsPopoverEvents);
  } else {
    bindRelationsPopoverEvents();
  }
})();
