/**
 * @module conveyor
 *
 * Board SPA conveyor tab module.
 *
 * Handles workRequest fetching, sorting, and conveyor board rendering with
 * per-column sort dropdowns. Registers fetchWorkRequests, fetchWorkRequestsByFiles
 * on Board.fetch and renderConveyor on Board.render.
 *
 * Depends on: common.js (Board.util, Board.state)
 */
"use strict";

(function () {
  const {
    esc, badge, fetchXmlList, parseWorkRequest, CMD_COLORS, COLUMNS, CONVEYOR_SORT_LS_KEY,
  } = Board.util;

  // ── Relations Display ──
  const MAX_VISIBLE_RELATIONS = 5;

  // ── WR-475 Stage 3: launch asynchronousization — client status machine
  // idle → submitting → starting → running (LAUNCH STARTED Received) | failed (LAUNCH FAILED / User Selection)
  //
  // Use Flow:
  //   1. FAQ submit handler: HTTP 200 OK ({status:'starting'}) start the launchState registration + grace timer immediately after the response.
  //   2. FAQ SSE 'launch' Event (handleLaunchEvent): LAUNCH STARTED → launchState Removal + Remove Badge,
  //      LAUNCH FAILED → launchState removal + failure modal.
  //   3. FAQs Grace 60s Expired (onGraceExpired): User-selection only displays — auto-forced previews 0 (constraints compliance).
  //
  // Restore a new call: sessionStorage('Board.launchState.<workRequest>') to 1.02 state →
  // Rewrite grace residual time with restoreLaunchStateFromStorage() call and restart timer.
  //
  // SSE Convention (my-board-sse-convention §2.4): handleLaunchEvent calls to single listener —
  // Board.conveyor Namespace Exposure (addEventListener Anti-Registration).
  const LAUNCH_GRACE_MS = 60000;             // 60s grace
  const LAUNCH_STORAGE_PREFIX = "Board.launchState.";
  const launchState = new Map();              // workRequestNum → {state, since, command, sessionId, graceTimer}

  // ── Column Collapsed State (Complete / Draft) ──
  // Saves the foldable status by column key. "Complete" is a user-configured by maintaining an existing key
  // To ensure compatibility, other columns (currently "Draft") are column-collapsed:<key> format.
  const LEGACY_DONE_LS_KEY = "claude-board-done-collapsed";
  const COLLAPSIBLE_COLUMNS = new Set(["Complete", "Draft"]);

  function columnCollapsedKey(colKey) {
    if (colKey === "Complete") return LEGACY_DONE_LS_KEY;
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

  // ── Draft Manual Order ──
  // Draft Column supports user manual sorting (DnD location changes). New workRequest is always the best prepend.
  // Not synchronized with other browsers/ devices (localStorage only).
  const TODO_MANUAL_ORDER_LS_KEY = "conveyor_todo_manual_order_v1";
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
   * - Save order workRequests = in order
   * - WorkRequest without storage order (New) = Top quality prepend, number desc
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

  /** Go to the targetIndex location of manual order. */
  function reorderTodoManualOrder(workRequestNum, targetIndex) {
    const stored = loadTodoManualOrder();
    const filtered = stored.filter(function (n) { return n !== workRequestNum; });
    const clamped = Math.max(0, Math.min(targetIndex, filtered.length));
    filtered.splice(clamped, 0, workRequestNum);
    saveTodoManualOrder(filtered);
  }

  // ── Conveyor Sort State ──

  /** Loads persisted conveyor sort state from localStorage. */
  function loadConveyorSort() {
    const defaults = {};
    COLUMNS.forEach(function (col) {
      // Draft defaults manual sorting. The rest of the number of times.
      if (col.key === "Draft") {
        defaults[col.key] = { key: "manual", dir: "asc" };
      } else {
        defaults[col.key] = { key: "number", dir: "asc" };
      }
    });
    try {
      const stored = JSON.parse(localStorage.getItem(CONVEYOR_SORT_LS_KEY));
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

  const conveyorSort = loadConveyorSort();
  Board.state.conveyorSort = conveyorSort;

  /** Persists conveyor sort state to localStorage. */
  function saveConveyorSort() {
    try {
      localStorage.setItem(CONVEYOR_SORT_LS_KEY, JSON.stringify(conveyorSort));
    } catch (e) {}
  }

  // ── Conveyor Sort Logic ──

  /**
   * Returns the most recent datetime from a workRequest's datetime field.
   * @param {Object} t - WorkRequest object
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
   * Sorts workRequest array by the given key and direction.
   * @param {Array} items - WorkRequest array
   * @param {string} sortKey - Sort key (number, created, modified, title)
   * @param {string} sortDir - Sort direction (asc, desc)
   * @returns {Array} Sorted copy of the workRequest array
   */
  function sortWorkRequests(items, sortKey, sortDir) {
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

  // ── Fetch WorkRequests ──

  // ── Worktree Uncommitted Cache ──
  // For the card woo Sangdan woomit indica. null = not loaded
  var _worktreeUncommittedMap = null;

  // ── Complete Verdict Cache (WR-441) ──
  // Complete Card Mage Combination verdict. key=workRequest number, value={verdict,reason,details}.
  // "pending" value = during the query. undefined = undefined
  var _completeVerdictMap = {};

  // ── Verifying Verdict Cache (WR-463) ──
  // Verifying Card Rule Base 1st Auto Verdict (advisory only).
  // key=workRequest number, value={verdict, reason, details, violations}.
  // Verdict Value: PASS / WARN / FAIL / SKIP / UNKNOWN.
  // "pending" value = during the query. undefined = undefined
  // comment no speculative guards 2026-05-08, WR-411 0c970fa, WR-413 1ce3c2d.
  // Auto Forced / Forced Regression / Forced Regression 0 — User can run verdict FAIL
  var _verifyingVerdictMap = {};

  // ── Audit Verdict Cache (WR-477) ──
  // Verifying Card Auditor T3 advisory verdict. key=workRequest number, value={tier1,tier2,combined}.
  // "pending" = viewed. undefined = undefined
  var _auditVerdictMap = {};

  // ── Active Branch WorkRequest (WR-433 Phase 2) ──
  // The main working tree is currently active feature brand name workRequest number (e.g. "WR-433"). null = develop.
  // SSOT: derive from backend GET /api/conveyor/branch/active or SSE git branch event.
  // Only one card is active: Matching only .active, compared all the review cards in render.
  var _activeBranchWorkRequest = null;
  // First one fetch finished guard — initial visual restore with 1 GET when loading page.
  var _activeBranchFetched = false;
  // WR-NNN extraction regular expression — feat/WR-NNN-* pattern matching.
  var _FEAT_BRANCH_RE = /^feat\/(WR-\d+)/;

  /**
   * <# if ( data.meta.album ) { #>{{ data.meta.artist }}<# } #>
   * .active toggles only when receiving a response (full re-render avoidance — DOM direct patch).
   */
  function fetchAndApplyActiveBranch() {
    if (_activeBranchFetched) return;
    _activeBranchFetched = true;
    fetch("/api/conveyor/branch/active", { cache: "no-store" }).then(function (res) {
      if (!res.ok) return null;
      return res.json();
    }).then(function (data) {
      var workRequest = (data && data.active_work_request) || null;
      _activeBranchWorkRequest = workRequest;
      applyActiveBranchClassToCards();
    }).catch(function () {
      // backend not ready —  activeBranchWorkRequest retains null (Each OFF)
    });
  }

  /**
   * .has-active-branch /
   * Sync the Toggle button .active class (directly patch DOM without full re-render).
   * - Call after arrival of SSE git branch event
   * - Toggle click optimistic update call immediately
   */
  function applyActiveBranchClassToCards() {
    var cards = document.querySelectorAll('.card[data-col-key="Verifying"]');
    cards.forEach(function (card) {
      var num = card.dataset.num;
      var btn = card.querySelector(".card-branch-toggle");
      var isActive = (num && _activeBranchWorkRequest === num);
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
   * Extract WR-NNN from branch strings  activeBranchWorkRequest Update + DOM Patch.
   * @param {string null} branch - "feat/WR-NNN-..." or "develop"
   */
  function syncActiveBranchFromSSE(branch) {
    var workRequest = null;
    if (branch && typeof branch === "string") {
      var m = _FEAT_BRANCH_RE.exec(branch);
      if (m) workRequest = m[1];
    }
    if (workRequest === _activeBranchWorkRequest) return; // Skip to content
    _activeBranchWorkRequest = workRequest;
    applyActiveBranchClassToCards();
  }

  /**
   * Verifying Card 4 Toggle Button Click Handler.
   * - Current card is active if action=off, or action=on to POST.
   * - dirty / needs restart / guided moves according to failure response (automatic stash absolute X).
   * @param {string} workRequestNum - Click Card WR-NNN
   */
  function handleBranchToggleClick(workRequestNum) {
    if (!workRequestNum) return;
    var action = (_activeBranchWorkRequest === workRequestNum) ? "off" : "on";
    fetch("/api/conveyor/branch/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ work_request_number: workRequestNum, action: action })
    }).then(function (res) {
      return res.json().then(function (body) { return { ok: res.ok, body: body }; });
    }).then(function (r) {
      var body = r.body || {};
      if (body.ok === true) {
        // Success — active workRequest update (server response reflect SSOT, optimistic simultaneously)
        _activeBranchWorkRequest = body.active_work_request || null;
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
          if (item && item.work_request && item.uncommitted_count > 0) {
            map.set(item.work_request, item);
          }
        });
        _worktreeUncommittedMap = map;
      });
    }).catch(function () {
      // worktree mode off / API error — leave map unchanged
    });
  }

  /**
   * WR-441: Single Complete Card Verdict View (advisory).
   * The result is cached in  doneVerdictMap, and patches the corresponding card badge to DOM when loading is completed.
   * No polling — 1 call when card mount.
   * @param {string} workRequestNum - workRequest number (e.g. "WR-441")
   */
  function fetchAndRenderVerdict(workRequestNum) {
    // If you already have an inquiry or complete, skip
    if (_completeVerdictMap[workRequestNum] !== undefined) return;
    _completeVerdictMap[workRequestNum] = "pending";

    fetch("/api/conveyor/complete-verdict?work_request=" + encodeURIComponent(workRequestNum), { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        _completeVerdictMap[workRequestNum] = data;
        // DOM Patch: Replace the verdict badge of the corresponding card (without full re-render)
        var badge = document.querySelector(
          '.card[data-num="' + workRequestNum + '"][data-col-key="Complete"] .card-complete-verdict'
        );
        if (badge) {
          var newBadge = document.createElement("span");
          _applyVerdictBadge(newBadge, data);
          badge.parentNode.replaceChild(newBadge, badge);
        }
      })
      .catch(function () {
        _completeVerdictMap[workRequestNum] = { verdict: "UNKNOWN", reason: "fetch_error", details: { message: "Verdict View failed" } };
      });
  }

  /**
   * WR-441: Apply the status in the badge span based on verdict data.
   * @param {HTMLElement} el - target span element
   * @param {Object} data - verdict response data ({verdict, reason, details})
   */
  function _applyVerdictBadge(el, data) {
    var verdict = data && data.verdict;
    el.className = "card-complete-verdict";
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
   * WR-463: Single Verifying Card Verdict View (advisory only).
   * Results  reviewVerdictMap Cache, and patch the corresponding card badge to DOM when loading is completed.
   * No polling — 1 call when card mount.
   * @param {string} workRequestNum - workRequest number (e.g. "WR-463")
   */
  function fetchAndRenderVerifyingVerdict(workRequestNum) {
    // If you already have an inquiry or complete, skip
    if (_verifyingVerdictMap[workRequestNum] !== undefined) return;
    _verifyingVerdictMap[workRequestNum] = "pending";

    fetch("/api/conveyor/verifying-verdict?work_request=" + encodeURIComponent(workRequestNum), { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        _verifyingVerdictMap[workRequestNum] = data;
        // DOM Patch: Replace the verdict badge of the corresponding card (without full re-render)
        var badge = document.querySelector(
          '.card[data-num="' + workRequestNum + '"][data-col-key="Verifying"] .card-verifying-verdict'
        );
        if (badge) {
          var newBadge = document.createElement("span");
          _applyVerifyingVerdictBadge(newBadge, data);
          badge.parentNode.replaceChild(newBadge, badge);
        }
      })
      .catch(function () {
        _verifyingVerdictMap[workRequestNum] = { verdict: "UNKNOWN", reason: "fetch_error", details: {}, violations: [] };
      });
  }

  /**
   * WR-477: Auditor T3 audit verdict generates an HTML (inline call in the renderConveyor).
   * combination === "NONE" returns empty string (DOM mount X).
   * @param {string} workRequestNum - workRequest number
   * @returns {string} span.audit-badge HTML or empty string
   */
  function renderAuditBadgeHtml(workRequestNum) {
    var data = _auditVerdictMap[workRequestNum];
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
   * WR-477: Verifying card single audit verdict fetch + DOM badge patch.
   * Results  auditVerdictMap to cache. No polling — 1 time when card mount.
   * @param {string} workRequestNum - workRequest number
   */
  function fetchAndRenderAuditVerdict(workRequestNum) {
    if (_auditVerdictMap[workRequestNum] !== undefined) return;
    _auditVerdictMap[workRequestNum] = "pending";

    fetch("/api/conveyor/audit/verdict?work_request=" + encodeURIComponent(workRequestNum), { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        _auditVerdictMap[workRequestNum] = data;
        if ((data.combined || "NONE") === "NONE") return;
        var placeholder = document.querySelector(
          '.card[data-num="' + workRequestNum + '"][data-col-key="Verifying"] .audit-badge'
        );
        if (placeholder) {
          var newHtml = renderAuditBadgeHtml(workRequestNum);
          if (newHtml) {
            var tmp = document.createElement("span");
            tmp.innerHTML = newHtml;
            var newEl = tmp.firstChild;
            placeholder.parentNode.replaceChild(newEl, placeholder);
          }
        }
      })
      .catch(function () {
        _auditVerdictMap[workRequestNum] = { tier1: null, tier2: null, combined: "NONE" };
      });
  }

  /**
   * WR-463: The review verdict data is based on the status of the badge span.
   * - PASS / WARN / FAIL — Text Chip Display (verdict-pass / verdict-warn / verdict-fail)
   * - SKIP / UNKNOWN / pending — hidden badge (display:none)
   * - tooltip = violations list + "advisory only" guide (cursor:help)
   * - 0 clicks (advisory only canon)
   * @param {HTMLElement} el - target span element
   * @param {Object} data - verdict response data ({verdict, reason, details, violations})
   */
  function _applyVerifyingVerdictBadge(el, data) {
    var verdict = data && data.verdict;
    el.className = "card-verifying-verdict";
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
    var tooltip = lines.join("\n") + "\\n\\nadvisory only — Complete Mobile Freedom";
    el.setAttribute("data-verdict-msg", tooltip);
    el.setAttribute("title", tooltip);
  }

  /**
   * WR-463: Create a Verifying Card verdict badge HTML.
   * If there is no result in the cache, return the placeholder during loading, and the DOM patch will be completed.
   * The first child of the card-actions-row is inserted into the margin-right:auto and separated to the right top.
   * @param {string} workRequestNum - workRequest number (e.g. "WR-463")
   * @returns {string} span.card-verifying-verdict HTML
   */
  function renderVerifyingVerdictBadge(workRequestNum) {
    var data = _verifyingVerdictMap[workRequestNum];
    if (data === undefined || data === "pending") {
      // Loading — Unseen Placeholders.  applyVerifyingVerdictBadge DOM patch after fetch completion.
      return '<span class="card-verifying-verdict verdict-loading" style="display:none;margin-right:auto"></span>';
    }
    var verdict = data && data.verdict;
    if (verdict !== "PASS" && verdict !== "WARN" && verdict !== "FAIL") {
      // SKIP / UNKNOWN / Unknown Value — Unlock Badge
      return '<span class="card-verifying-verdict verdict-unknown" style="display:none;margin-right:auto"></span>';
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
    var tooltip = lines.join("\n") + "\\n\\nadvisory only — Complete Mobile Freedom";
    var cls = "verdict-" + verdict.toLowerCase();
    return (
      '<span class="card-verifying-verdict ' + cls + '"'
      + ' style="margin-right:auto"'
      + ' title="' + esc(tooltip) + '"'
      + ' data-verdict-msg="' + esc(tooltip) + '">'
      + esc(verdict)
      + '</span>'
    );
  }

  /** Fetches all workRequests via /api/conveyor (single request). */
  function fetchWorkRequests() {
    return fetch("/api/conveyor", { cache: "no-store" }).then(function (res) {
      if (!res.ok) return [];
      return res.json();
    }).then(function (map) {
      var workRequests = [];
      Object.keys(map).forEach(function (fn) {
        if (map[fn]) {
          var t = parseWorkRequest(map[fn]);
          if (t) workRequests.push(t);
        }
      });
      return workRequests;
    }).catch(function () { return []; }).then(function (workRequests) {
      // Co-fetch worktree uncommitted so renderConveyor always has fresh data.
      return fetchAndCacheWorktreeUncommitted().then(
        function () { return workRequests; },
        function () { return workRequests; }
      );
    });
  }

  /**
   * Selectively fetches and updates workRequests by file names via /api/conveyor?files=...
   * @param {string[]} files - Changed file names (e.g. ["WR-038.xml"])
   * @returns {Promise<void>}
   */
  function fetchWorkRequestsByFiles(files) {
    return fetch("/api/conveyor?files=" + encodeURIComponent(files.join(",")), { cache: "no-store" }).then(function (res) {
      if (!res.ok) return;
      return res.json().then(function (map) {
        Object.keys(map).forEach(function (fn) {
          var baseName = fn.replace(/\.xml$/, "");
          if (map[fn] === null) {
            Board.state.WORK_REQUESTS = Board.state.WORK_REQUESTS.filter(function (t) { return t.number !== baseName; });
          } else {
            var incoming = parseWorkRequest(map[fn]);
            if (!incoming) return;
            var idx = Board.state.WORK_REQUESTS.findIndex(function (t) { return t.number === incoming.number; });
            if (idx !== -1) {
              Board.state.WORK_REQUESTS[idx] = incoming;
            } else {
              Board.state.WORK_REQUESTS.push(incoming);
            }
          }
        });
      });
    }).catch(function () {});
  }

  // ── Conveyor Rendering ──

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
   * Create a stage icon HTML for the chain command workRequest.
   * @param {Object} workRequest object
   * @returns {string} card-chain div HTML
   */
  function renderChainIcons(workRequest) {
    const stages = workRequest.command.split(">").map(function (s) { return s.trim(); }).filter(Boolean);
    if (stages.length === 0) return "";

    const isComplete = workRequest.status === "Complete";
    const isInProgress = workRequest.status === "Executing";

    let parts = [];
    stages.forEach(function (stage, idx) {
      let stateClass;
      if (isComplete) {
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
   * @param {Object} workRequest object
   * @returns {string} card-relations div HTML
   */
  function renderRelations(workRequest) {
    if (!workRequest.relations || workRequest.relations.length === 0) return "";

    const typeMap = {
      "derived-from": { prefix: "\u2190", cssClass: "rel-derived" },   // ←
      "depends-on":   { prefix: "\u21D0", cssClass: "rel-depends" },   // ⇐
      "blocks":       { prefix: "\u2192", cssClass: "rel-blocks" },    // →
    };

    const relations = workRequest.relations;
    const visible = relations.length > MAX_VISIBLE_RELATIONS
      ? relations.slice(0, MAX_VISIBLE_RELATIONS)
      : relations;
    const overflow = relations.length > MAX_VISIBLE_RELATIONS
      ? relations.length - MAX_VISIBLE_RELATIONS
      : 0;

    let parts = [];
    visible.forEach(function (rel) {
      const info = typeMap[rel.type] || { prefix: "\u2194", cssClass: "rel-other" };
      const numStr = rel.workRequest ? rel.workRequest.replace(/^WR-/, "") : "?";
      parts.push('<span class="rel-item ' + info.cssClass + '">' + info.prefix + numStr + "</span>");
    });

    if (overflow > 0) {
      const workRequestNum = workRequest.number || "";
      const encodedRelations = esc(JSON.stringify(relations));
      const totalCount = relations.length;
      parts.push(
        '<button class="rel-overflow-chip"' +
        ' data-work-request="' + esc(workRequestNum) + '"' +
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
   * @param {Array<{type: string, work_request: string}>} relations - full relations array
   */
  function showRelationsPopover(triggerEl, relations) {
    hideRelationsPopover();

    var typeMap = {
      "derived-from": { prefix: "←", cssClass: "rel-derived" },  // ←
      "depends-on":   { prefix: "⇐", cssClass: "rel-depends" },  // ⇐
      "blocks":       { prefix: "→", cssClass: "rel-blocks" },   // →
    };

    // Build list HTML — prefix + workRequest# + type label per row
    var listHtml = '<ul class="rel-popover-list" role="list">';
    relations.forEach(function (rel) {
      var info = typeMap[rel.type] || { prefix: "↔", cssClass: "rel-other" };
      var numStr = rel.workRequest ? rel.workRequest.replace(/^WR-/, "") : "?";
      var label = rel.type === "derived-from" ? "Home"   // Home
        : rel.type === "depends-on" ? "Venue"             // Venue
        : rel.type === "blocks" ? "Home"                 // Home
        : esc(rel.type);
      listHtml += '<li class="rel-popover-item ' + info.cssClass + '">'
        + '<span class="rel-popover-prefix">' + info.prefix + '</span>'
        + '<span class="rel-popover-num">WR-' + esc(numStr) + '</span>'
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
   * Delegates to document so listeners survive conveyor re-renders.
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
   * WR-457 (Layer 3): Automatic Commit Trigger with 4 Commit button clicks.
   * to maintain fetch logic in existing handleUncommittedBadgeClick,
   * Only one DOM manipulator will be transferred to the 4th button.
   * .card-commit-action
   */
  function handleCommitButtonClick(btn) {
    var workRequest = btn.dataset.commitWorkRequest;
    if (!workRequest || btn.classList.contains("is-commiting")) return;
    btn.classList.add("is-commiting");
    btn.disabled = true;
    fetch("/api/conveyor/worktree-commit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ work_request: workRequest }),
    }).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, data: data };
      });
    }).then(function (r) {
      if (r.ok && r.data && r.data.ok) {
        // Success — Card Renewal (commit button + expects to disappear both one-on-the-box)
        if (_worktreeUncommittedMap) _worktreeUncommittedMap.delete(workRequest);
        Board.render.renderConveyor();
      } else {
        var msg = (r.data && r.data.error) || "Commit fails";
        btn.classList.remove("is-commiting");
        btn.disabled = false;
        Board.util.showInfoModal("Commit fails", workRequest + "Commit fail:" + msg, { severity: "error" });
      }
    }).catch(function (err) {
      btn.classList.remove("is-commiting");
      btn.disabled = false;
      Board.util.showInfoModal("Commit fails", workRequest + "Commit request failed:" + (err && err.message ? err.message : err), { severity: "error" });
    });
  }

  /**
   * Executing card 4 stop button click — POST /api/workflow/stop with workflow request.
   * showInfoModal in the event of a successful renderConveyor / failure.
   */
  function handleStopButtonClick(btn) {
    var workRequest = btn.dataset.stopWorkRequest;
    if (!workRequest || btn.classList.contains("is-stopping")) return;
    var msg = workRequest + "Stop workflow. \\nProceeds/jsonl/conveyor/worktree 4 axis. \\n\\n?";
    if (!window.confirm(msg)) return;
    btn.classList.add("is-stopping");
    btn.disabled = true;
    fetch("/api/workflow/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ work_request: workRequest }),
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
        if (Board.render && Board.render.renderConveyor) Board.render.renderConveyor();
      } else {
        var errs = (r.data && r.data.errors) || [];
        var errMsg = errs.length ? errs.join("\n") : ("HTTP " + r.status);
        Board.util.showInfoModal("Workflow failed", workRequest + "Warranty:" + errMsg, { severity: "error" });
      }
    }).catch(function (err) {
      btn.classList.remove("is-stopping");
      btn.disabled = false;
      Board.util.showInfoModal("Workflow failed", workRequest + "Tag:" + (err && err.message ? err.message : err), { severity: "error" });
    });
  }

  /**
   * Create a Card Indication HTML.
   * When the workflow regression (Watcher Committed), the user immediately commits to click.
   * @param {string} workRequestNum - workRequest number (e.g. "WR-422")
   * @returns {string} span.card-uncommitted-badge HTML or empty string
   */
  function renderUncommittedBadge(workRequestNum) {
    if (!_worktreeUncommittedMap) return "";
    var item = _worktreeUncommittedMap.get(workRequestNum);
    if (!item || item.uncommitted_count <= 0) return "";
    var label = item.uncommitted_count + "M";
    var tooltip = "Mickey Mouse" + item.uncommitted_count + "— Click Commit"; // "Mickeym N Gun — Automatic Commit"
    return '<span class="card-uncommitted-badge" data-uncommitted-work-request="' + esc(workRequestNum) + '" title="' + esc(tooltip) + '">' + esc(label) + "</span>";
  }

  /**
   * WR-457 (Layer 3): Card 1-on-right failure tag wrench.
   * schema: { reason, phase, retry count, context }
   * Guard: workRequest / workRequest.failure returns empty strings if falsy.
   * read-only — pointer-events:none (CSS), no click trigger.
   * The color is placeholder neutral (the user decides to wait — the one-line patch after the decision).
   * @param {object} workRequest - card workRequest object
   * @returns {string} span.card-failure-tag HTML or empty string
   */
  function renderFailureTag(workRequest) {
    if (!workRequest || !workRequest.failure) return "";
    var reason = workRequest.failure.reason || "Workflow Failure";
    var phase = workRequest.failure.phase || "";
    var label = "FAIL";
    var tooltip = phase ? (phase + "Step Failure —" + reason) : reason;
    return '<span class="card-failure-tag" title="' + esc(tooltip) + '">' + esc(label) + "</span>";
  }

  /**
   * WR-441: Create Complete Card verdict badge HTML.
   * If there is no result in the cache, return the placeholder during loading and the synchronous fetch trigger.
   * @param {string} workRequestNum - workRequest number (e.g. "WR-441")
   * @returns {string} span.card-complete-verdict HTML or empty string
   */
  function renderCompleteVerdictBadge(workRequestNum) {
    var data = _completeVerdictMap[workRequestNum];
    if (data === undefined || data === "pending") {
      // Loading — Small Placeholders (not seen, DOM patch after fetch finish)
      return '<span class="card-complete-verdict verdict-loading" style="display:none"></span>';
    }
    var verdict = data && data.verdict;
    if (verdict === "OK") {
      return (
        '<span class="card-complete-verdict verdict-ok" title'
        + '<svg width="11" height="11" viewBox="0 0 11 11" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        + '<polyline points="1.5,5.5 4.5,8.5 9.5,2.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
        + '</svg></span>'
      );
    }
    if (verdict === "FAIL") {
      var msg = (data.details && data.details.message) || "Develop head is mitigating";
      return (
        '<span class="card-complete-verdict verdict-fail"'
        + 'title="Merge Unemployment —' + esc(msg) + '(click to check details)"'
        + ' data-verdict-msg="' + esc(msg) + '">'
        + '<svg width="11" height="11" viewBox="0 0 11 11" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        + '<line x1="2" y1="2" x2="9" y2="9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
        + '<line x1="9" y1="2" x2="2" y2="9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
        + '</svg></span>'
      );
    }
    // UNKNOWN / SKIP
    return '<span class="card-complete-verdict verdict-unknown" style="display:none"></span>';
  }

  /**
   * Returns status label information based on the status of the workRequest.
   * Draft only returns TODO label.
   * WR-399: Submit transient step removed. WR-445: OPEN Label Closing.
   * @param {Object} workRequest object
   * @returns {{ label: string, cssClass: string } | null} State label and CSS class, or null
   */
  function getWorkflowStatus(workRequest) {
    if (workRequest && workRequest.status === "Draft") {
      return { label: "TODO", cssClass: "status-todo" };
    }
    return null;
  }

  /**
   * WR-399: Confirmation Modal Display — Accepted → Executing drop City Workflow Execution consciousness guaranteed.
   * @param {Object} workRequest - Drag workRequest object (number, command included)
   * @param {Function} onConfirm - [Run] Click Callback
   * @param {Function} onCancel - [Cancel]/ESC/overlay Click Callback
   */
  function showSubmitConfirmModal(workRequest, onConfirm, onCancel) {
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
      workRequest.number + "Go to Executing and start workflow. About Us";

    const actions = document.createElement("div");
    actions.className = "submit-confirm-actions";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "submit-confirm-btn submit-confirm-btn-cancel";
    cancelBtn.textContent = "Venue";

    const confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = "submit-confirm-btn submit-confirm-btn-confirm";
    confirmBtn.textContent = "Accepted";

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
   * WR-906: Verifying → Add Complete drop (confirm delivery + cmd done commission + result delivery).
   * @param {Object} workRequest - Drag workRequest object (number included)
   * @param {Function} onConfirm - [Finished] Click Callback
   * @param {Function} onCancel - [Cancel]/ESC/overlay Click Callback
   */
  function showCompleteConfirmModal(workRequest, onConfirm, onCancel) {
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
    const workRequestNumNode = document.createTextNode(workRequest.number + "Complete Treatment");
    title.appendChild(workRequestNumNode);

    const body = document.createElement("div");
    body.className = "submit-confirm-body";
    const introText = document.createTextNode("If you move this workRequest to Complete, then this will be done in a fairly NEWS");
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
   * WR-439: Verifying Card Velvet 1-click Complete Action Handler.
   * showCompleteConfirmModal → POST /api/conveyor/complete → showCompleteResultModal chain
   * DnD Verifying→Complete reuse as the same signature as the branch(conveyor.js:1791-1826).
   * @param {Object} workRequestObj - workRequest object (number included)
   */
  function handleVerifyingCompleteAction(workRequestObj) {
    var capturedNum = workRequestObj.number;
    showCompleteConfirmModal(
      workRequestObj,
      function () {
        // [Completion] Callback: POST /api/conveyor/complete → cmd done commission
        fetch("/api/conveyor/complete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ work_request: capturedNum }),
        }).then(function (res) {
          return res.json().then(function (body) {
            return { res: res, body: body };
          });
        }).then(function (r) {
          if (r.res.ok && r.body.ok) {
            showCompleteResultModal("success", r.body, function () {
              fetchWorkRequests().then(renderConveyor);
            });
          } else {
            var kind = r.body.error_kind === "merge_conflict" ? "conflict"
              : r.body.error_kind === "dirty_worktree" ? "dirty"
              : "error";
            showCompleteResultModal(kind, r.body, function () { renderConveyor(); });
          }
        }).catch(function (err) {
          console.error("[conveyor card-complete-action] complete failed:", err);
          showCompleteResultModal("error", { message: err.message }, function () { renderConveyor(); });
        });
      },
      function () {
        // [Cancellation]/ESC/overlay callback: Keep card origin
        renderConveyor();
      }
    );
  }

  /**
   * WR-418: Accepted → Complete direct transfer check modal.
   *
   * Go to Complete without mounting the Verifying. Worktree/feature Branding Waster.
   * LOGIN JOIN ORDER MYPAGE forward force dirty value to onConfirm.
   *
   * @param {Object} workRequest - Drag workRequest object (number included)
   * @param {Function} onConfirm - [Direct Complete Treatment] Click Callback (force dirty: bool argument passed)
   * @param {Function} onCancel - [Cancel]/ESC/overlay Click Callback
   */
  function showAcceptedCompleteConfirmModal(workRequest, onConfirm, onCancel) {
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
    title.appendChild(document.createTextNode(workRequest.number + "Accepted → Complete"));

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    const introText = document.createTextNode("Go directly to Complete without mounting the Verifying at Accepted stage. The following are non-invasively performed NEWS");
    body.appendChild(introText);

    const ul = document.createElement("ul");
    const li1 = document.createElement("li");
    li1.textContent = "Worktree and feature Brand Name Waster (No Development Merged)";
    const li2 = document.createElement("li");
    li2.textContent = "Complete WorkRequest Status";
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
    confirmBtn.textContent = "Direct Complete Treatment";

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
   * WR-418: Accepted → Complete direct transfer results.
   *
   * Unlike showCompleteResultModal, success without merge commit also normal processing.
   * "Causes of rehabilitation after rehabilitation"
   *
   * @param {"success" "dirty" "error"} kind - result type
   * @param {Object} payload - result data
   * @param {Function} onClose - Close Callback
   * @param {Function} onForceDirty - "Causes of rehabilitation after rehabilitation" button click callback
   */
  function showAcceptedCompleteResultModal(kind, payload, onClose, onForceDirty) {
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
      title.textContent = "Accepted → Complete";
      const msg = document.createElement("p");
      msg.textContent = (payload.work_request || "") + "WorkRequests were moved to Complete. Worktree and feature Brands were cleaned.";
      body.appendChild(msg);
    } else if (kind === "dirty") {
      title.textContent = "Complete Processing Failure — Minorm Change";
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
      title.textContent = "Complete processing failed";
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
   * WR-418: Deletion of workRequest confirmation modal.
   *
   * Red [delete] button. POST /api/conveyor/delete calls.
   * error kind='derived blocked' when alert is blocked by the show.
   *
   * @param {Object} workRequest - workRequest object to delete (number included)
   * @param {Function} onConfirm - Click Callback
   * @param {Function} onCancel - [Cancel]/ESC/overlay Click Callback
   */
  function showDeleteConfirmModal(workRequest, onConfirm, onCancel) {
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
    title.appendChild(document.createTextNode(workRequest.number + "Scots Gaelic"));

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    const introText = document.createTextNode(workRequest.number + "Please delete the workRequest. This work cannot be reverted.");
    body.appendChild(introText);

    const ul = document.createElement("ul");
    const li1 = document.createElement("li");
    li1.textContent = "Worktree and feature Brands are also cleaned together.";
    const li2 = document.createElement("li");
    li2.textContent = "Deletion is blocked if the derivation workRequest (derived-from) is completed.";
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
   * WR-906: Complete treatment result delivery.
   * @param {"success"|"conflict"|"dirty"|"error"} kind - result type
   * @param {Object} payload - result data (kind star difference)
   * @param {Function} onClose - Close Callback
   */
  function showCompleteResultModal(kind, payload, onClose) {
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
      console.warn("[showCompleteResultModal] success kind with empty merge_commit — converting to error");
      kind = "error";
      payload = Object.assign({}, payload, {
        message: "backend response format error — merge commit missing. See flow-conveyor output."
      });
    }

    if (kind === "success") {
      title.textContent = "Complete Treatment Complete";
      const msg = document.createElement("p");
      const workRequestStr = payload.merge_skipped
        ? (payload.work_request || "") + ": Verifying → Complete (No Merge — Research/Document)"
        : (payload.work_request || "") + ": " + (payload.merged_branch || "") + "→ develop merge completion (" + (payload.merge_commit || "") + ")";
      msg.textContent = workRequestStr;
      body.appendChild(msg);
    } else if (kind === "conflict") {
      title.textContent = "Complete Processing Failure — Merge Collision";
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
      title.textContent = "Complete Processing Failure — Minorm Change";
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
      title.textContent = "Complete processing failed";
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
   * WR-905 Phase 3: Complete card click → "Verifying" check modal.
   *
   * push(local-only) / push(origin/develop reach) branch guide + force option checkbox.
   * pre-detect: pre-check whether the conveyor result.merge commit exists
   * Please note that the force option is required when missing.
   *
   * @param {Object} workRequest - Complete column card workRequest object (number/result included)
   * @param {Function} onConfirm - confirm callback (force: bool argument passed)
   * @param {Function} onCancel - Cancel/ESC/overlay Callback
   */
  function showUndoCompleteConfirmModal(workRequest, onConfirm, onCancel) {
    const overlay = document.createElement("div");
    overlay.className = "submit-confirm-overlay";

    const dialog = document.createElement("div");
    dialog.className = "submit-confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "undo-complete-confirm-title");

    const title = document.createElement("h3");
    title.id = "undo-complete-confirm-title";
    title.className = "submit-confirm-title";
    title.appendChild(document.createTextNode(workRequest.number + "Verifying"));

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    const intro = document.createElement("p");
    intro.textContent = "Revert Complete processing of this workRequest. Developing the thumb result automatically quarterly NEWS";
    body.appendChild(intro);

    const ul = document.createElement("ul");
    const li1 = document.createElement("li");
    li1.textContent = "reset --hard";
    const li2 = document.createElement("li");
    li2.textContent = "after push(includes origin/develop): add reverse commit to revert -m 1 (noforce-push)";
    const li3 = document.createElement("li");
    li3.textContent = "feature Brand + Worktree Regeneration + Conveyor Complete → Verifying Forced Battle";
    ul.appendChild(li1);
    ul.appendChild(li2);
    ul.appendChild(li3);
    body.appendChild(ul);

    // result.merge commit
    const result = workRequest.result || {};
    const hasMergeCommit = !!(result.merge_commit && String(result.merge_commit).trim());
    if (!hasMergeCommit) {
      const warn = document.createElement("p");
      warn.style.color = "#D97757";
      warn.style.fontWeight = "600";
      warn.textContent = "Note: This workRequest does not have merge commit information (Phase 1 Infrastructure introduced earlier Complete). To try reflog fallback, please enable the following force option:";
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
    forceCheckbox.id = "undo-complete-force";
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
    confirmBtn.textContent = "Verifying";

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
   * WR-905 Phase 3: undo-complete results modal.
   * showCompleteResultModal pattern answer.
   *
   * "reset ok"
   * @param {Object} payload - result data
   *   - reset_ok / revert_ok: { workRequest, strategy, branch, worktree_path, message }
   *   - error: { workRequest, error, message, stderr }
   * @param {Function} onClose - Close callbacks (Utilization on automatic new callbacks in the field)
   */
  function showUndoCompleteResultModal(kind, payload, onClose) {
    const overlay = document.createElement("div");
    overlay.className = "submit-confirm-overlay";

    const dialog = document.createElement("div");
    dialog.className = "submit-confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "undo-complete-result-title");

    const title = document.createElement("h3");
    title.id = "undo-complete-result-title";
    title.className = "submit-confirm-title";

    const body = document.createElement("div");
    body.className = "submit-confirm-body";

    if (kind === "reset_ok" || kind === "revert_ok" || kind === "unknown_ok") {
      title.textContent = "Verifying";

      const summary = document.createElement("p");
      const workRequestStr = payload.work_request || "";
      const strategyStr = payload.strategy
        ? (payload.strategy === "reset" ? "reset --hard (push ago)" : payload.strategy === "revert" ? "revert -m 1 (after push)" : payload.strategy)
        : "?";
      summary.textContent = workRequestStr + "Rollback Finished — Strategy:" + strategyStr;
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
      liE.textContent = "/wf -e " + workRequestStr + "Edit workRequests or edit them directly";
      const liS = document.createElement("li");
      liS.textContent = "/wf -s " + workRequestStr + "Skip to content";
      ol.appendChild(liE);
      ol.appendChild(liS);
      body.appendChild(ol);
    } else {
      title.textContent = "Verifying";
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
   * WR-905 Phase 3: Complete card context menu (click).
   *
   * "Verifying" single item exposure. showUndoCompleteConfirmModal calls when clicked.
   * Click documentLevel or close to ESC.
   *
   * contextmenu
   * @param {Object} workRequest - Complete card workRequest object
   */
  function showCompleteCardContextMenu(event, workRequest) {
    // Removed if the existing context menu is open
    document.querySelectorAll(".conveyor-card-context-menu").forEach(function (m) {
      if (m.parentNode) m.parentNode.removeChild(m);
    });

    const menu = document.createElement("div");
    menu.className = "conveyor-card-context-menu";
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
    item.textContent = "Verifying";
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
      showUndoCompleteConfirmModal(
        workRequest,
        function (force) {
          // [Verifying by Rollback] Callback
          fetch("/api/conveyor/undo-complete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ work_request: workRequest.number, force: force }),
          }).then(function (res) {
            return res.json().then(function (body) {
              return { res: res, body: body };
            });
          }).then(function (r) {
            if (r.res.ok && r.body.ok) {
              showUndoCompleteResultModal(r.body.kind || "unknown_ok", r.body, function () {
                fetchWorkRequests().then(renderConveyor);
              });
            } else {
              showUndoCompleteResultModal("error", r.body || {}, function () { renderConveyor(); });
            }
          }).catch(function (err) {
            console.error("[conveyor undo-complete] failed:", err);
            showUndoCompleteResultModal("error", { message: err.message }, function () { renderConveyor(); });
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
   * WR-418: Accepted Card context menu (click).
   *
   * 2 menu items:
   *   - "Complete" → showAcceptedCompleteConfirmModal call
   *   - "TubeDupe" → showDeleteConfirmModal call
   *
   * showCompleteCardContextMenu (WR-905)
   *
   * contextmenu
   * @param {Object} workRequest - Accepted card workRequest object
   */
  function showAcceptedCardContextMenu(event, workRequest) {
    // Removed if the existing context menu is open
    document.querySelectorAll(".conveyor-card-context-menu").forEach(function (m) {
      if (m.parentNode) m.parentNode.removeChild(m);
    });

    const menu = document.createElement("div");
    menu.className = "conveyor-card-context-menu";
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

    const doneItem = makeMenuItem("Complete");
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

    // "Complete" Click Handler
    doneItem.addEventListener("click", function (e) {
      e.stopPropagation();
      cleanup();
      function callAcceptedComplete(forceDirty) {
        fetch("/api/conveyor/complete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ work_request: workRequest.number, force: true, force_dirty: forceDirty }),
        }).then(function (res) {
          return res.json().then(function (body) {
            return { res: res, body: body };
          });
        }).then(function (r) {
          if (r.res.ok && r.body.ok) {
            showAcceptedCompleteResultModal("success", r.body, function () {
              fetchWorkRequests().then(renderConveyor);
            });
          } else {
            const kind = r.body.error_kind === "dirty_worktree" ? "dirty" : "error";
            showAcceptedCompleteResultModal(kind, r.body, function () {
              renderConveyor();
            }, kind === "dirty" ? function () {
              callAcceptedComplete(true);
            } : undefined);
          }
        }).catch(function (err) {
          console.error("[conveyor Accepted contextmenu] open-complete failed:", err);
          showAcceptedCompleteResultModal("error", { message: err.message }, function () { renderConveyor(); });
        });
      }
      showAcceptedCompleteConfirmModal(
        workRequest,
        function (forceDirty) {
          callAcceptedComplete(forceDirty);
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
        workRequest,
        function () {
          fetch("/api/conveyor/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ work_request: workRequest.number }),
          }).then(function (res) {
            return res.json().then(function (body) {
              return { res: res, body: body };
            });
          }).then(function (r) {
            if (r.res.ok && r.body.ok) {
              fetchWorkRequests().then(renderConveyor);
            } else {
              if (r.body.error_kind === "derived_blocked") {
                const derivedList = (r.body.derived_workRequests || []).join(", ") || "(No roll)";
                Board.util.showInfoModal("Delete block", "Deletion: Derivative workRequests are unfinished. \\n\\nComplete Derivative WorkRequest:" + derivedList + "Complete the \\n\\n parasite workRequest first.", { severity: "warning", onClose: function () { renderConveyor(); } });
              } else {
                Board.util.showInfoModal("Delete failed", "Delete Failure:" + ((r.body && r.body.message) || "Unknown Errors"), { severity: "error", onClose: function () { renderConveyor(); } });
              }
            }
          }).catch(function (err) {
            console.error("[conveyor Accepted contextmenu] delete failed:", err);
            Board.util.showInfoModal("Delete failed", "Delete Failure:" + err.message, { severity: "error", onClose: function () { renderConveyor(); } });
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
   * Verifying Card Click context menu.
   * Optional: (a) Accepted to rework (POST /api/conveyor/move).
   * Chat attachments to DnD (WR-427).
   * Verifying → Before Executing, the User Expiration (2026-05-08).
   *
   * contextmenu
   * @param {Object} workRequest - Verifying card workRequest object
   */
  function showVerifyingCardContextMenu(event, workRequest) {
    document.querySelectorAll(".conveyor-card-context-menu").forEach(function (m) {
      if (m.parentNode) m.parentNode.removeChild(m);
    });

    const menu = document.createElement("div");
    menu.className = "conveyor-card-context-menu";
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

    const reopenItem = makeMenuItem("Rework with Accepted");

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
      fetch("/api/conveyor/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ work_request: workRequest.number, to: "accepted" }),
      }).then(function (res) {
        return res.json().then(function (body) { return { res: res, body: body }; });
      }).then(function (r) {
        if (r.res.ok && r.body.ok) {
          fetchWorkRequests().then(renderConveyor);
        } else {
          Board.util.showInfoModal("Rework failed", "Pre-work failed:" + ((r.body && r.body.error) || "Unknown Errors"), { severity: "error", onClose: function () { renderConveyor(); } });
        }
      }).catch(function (err) {
        Board.util.showInfoModal("Rework failed", "Rework work item failed:" + (err && err.message ? err.message : err), { severity: "error", onClose: function () { renderConveyor(); } });
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
   * Card drag and drop handler registration (WR-399: Draft ↔ Accepted + Accepted → Executing).
   * WR-906: Verifying → Add Complete drop (confirm delivery + cmd done commission + result delivery).
   *
   * dragstart: Save the workRequest number + Departure column to dataTransfer.
   * dragover: dragover-active display in dropable cards-droppable area.
   * drop:
   *   - Draft ↔ Accepted: POST /api/conveyor/move (In short time)
   *   - Accepted → Executing: Confirm Modal → POST /api/conveyor/submit (Workflow Execution)
   *   - Verifying → Complete: confirm Modal → POST /api/conveyor/complete (cmd done)
   * dragend: Clean up your visual feedback class.
   *
   * Executing card drag Invalid protection (delete degradation).
   * Verifying → Complete drop only confirm Modal allowed (WR-906).
   */
  function bindConveyorDnd(el) {
    let draggedNum = null;
    let draggedFrom = null;

    el.querySelectorAll(".card-draggable").forEach(function (card) {
      card.addEventListener("dragstart", function (e) {
        draggedNum = card.dataset.num;
        draggedFrom = card.dataset.colKey;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", draggedNum);
        // WR-427: Pass the workRequest JSON payload to MIME separately (for terminal drop branch only)
        var workRequestObj = (Board.state.WORK_REQUESTS || []).find(function (t) {
          return t.number === draggedNum;
        });
        if (workRequestObj) {
          var payload = {
            number: workRequestObj.number,
            title: workRequestObj.title || "",
            command: workRequestObj.command || "",
            prompt: workRequestObj.prompt || null,
            result: workRequestObj.result || null,
          };
          try {
            e.dataTransfer.setData("application/x-board-work-request", JSON.stringify(payload));
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
     *   Draft  → Draft(reorder) | Accepted
     *   Accepted   → Draft | Executing | Verifying | Complete
     *   Verifying → Complete | Accepted
     * Other combinations deny drop in dragover phase (Browner cursor is no-drop display).
     */
    function isValidDropTarget(fromCol, targetCol) {
      if (fromCol === "Draft") return targetCol === "Draft" || targetCol === "Accepted";
      if (fromCol === "Accepted") return targetCol === "Draft" || targetCol === "Executing" || targetCol === "Verifying" || targetCol === "Complete";
      if (fromCol === "Verifying") return targetCol === "Complete" || targetCol === "Accepted";
      return false;
    }

    /**
     * Draft manual alignment mode such as column reorder dragover when insert position indicator placement.
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
        // Draft manual sorting + like column drag — insert location indicator display
        if (zone.dataset.colKey === "Draft" && draggedFrom === "Draft"
            && conveyorSort["Draft"] && conveyorSort["Draft"].key === "manual") {
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
        // drop in column: Draft manual alignment mode only support, rest ignore
        if (targetCol === draggedFrom) {
          if (targetCol === "Draft" && conveyorSort["Draft"] && conveyorSort["Draft"].key === "manual") {
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
            renderConveyor();
          }
          return;
        }

        // WR-399: Executing drop quarter — Accepted card only allowed + confirm modal
        // Verifying Card Complete Unlike columns to drop — block
        // WR-418: Draft ↔ Accepted logic when trying to drop the Accepted Card to Complete outside column
        if (draggedFrom === "Verifying" && targetCol !== "Complete" && targetCol !== "Accepted") {
          Board.util.showInfoModal("DnD Lockout", "Verifying cards can only be dragging with Complete or Accepted columns.", { severity: "warning", onClose: function () { renderConveyor(); } });
          return;
        }

        if (targetCol === "Executing") {
          if (draggedFrom !== "Accepted") {
            // Executing move directly from other columns such as Draft
            Board.util.showInfoModal(
              "Draft → Executing",
              "Draft Card cannot be transferred directly to Executing. \\nReturn to Accepted",
              {
                severity: "info",
                onClose: function () {
                  renderConveyor();
                }
              }
            );
            return;
          }
          const workRequestObj = (Board.state.WORK_REQUESTS || []).find(function (t) {
            return t.number === draggedNum;
          });
          if (!workRequestObj) {
            renderConveyor();
            return;
          }
          const command = workRequestObj.command || "implement";
          showSubmitConfirmModal(
            workRequestObj,
            function () {
              // [Run] Callback: POST /api/conveyor/submit → driver
              // Stage 3-B race fix: registerLaunchStarting is called in fetch *function*
              // SSE LAUNCH STARTED guarantees that even if you arrive faster than HTTP response.
              // Instantly cleanupLaunchState when failure (stuck regression).
              const submitWorkRequest = workRequestObj.number;
              const submitCommand = command;
              registerLaunchStarting(submitWorkRequest, submitCommand);
              fetch("/api/conveyor/submit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ work_request: submitWorkRequest, command: submitCommand }),
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
                  cleanupLaunchState(submitWorkRequest);
                } else if (body.session_id && Board.workflowTabStorage
                           && Board.workflowTabStorage.add) {
                  // WR-516 — submit response body.session id also localStorage.
                  // Launch SSE LAUNCH STARTED handler and OR conditions — Helper dedupe safety.
                  Board.workflowTabStorage.add(body.session_id);
                }
                fetchWorkRequests().then(function () { renderConveyor(); });
              }).catch(function (err) {
                cleanupLaunchState(submitWorkRequest);
                console.error("[conveyor DnD] submit failed:", err);
                if (err && err.kind === "http") {
                  // WR-475 Stage 3 Static: HTTP 504 alone waiting for Modal Mileage (SSE LAUNCH FAILED).
                  // The 504 itself disappears after this synchronousization, but the defending quarterly preserved.
                  if (err.status === 504) {
                    renderConveyor();
                  } else {
                    Board.util.showInfoModal("Skip to content",
                      formatHttpRejectMessage(err.status, err.body),
                      { severity: "error", onClose: function () { renderConveyor(); } });
                  }
                } else {
                  // network / abort / other — instant notifications to users
                  Board.util.showInfoModal("Workflow failed to run",
                    "Tag:" + ((err && err.message) || String(err)),
                    { severity: "error", onClose: function () { renderConveyor(); } });
                }
              });
            },
            function () {
              // [Cancel]/ESC/overlay callback: Return card origin
              renderConveyor();
            }
          );
          return;
        } else if (targetCol === "Complete") {
          // WR-906: Verifying → Complete drop quarter
          // WR-418: Accepted → Complete direct prefix
          if (draggedFrom !== "Verifying" && draggedFrom !== "Accepted") {
            Board.util.showInfoModal("DnD Lockout", "You can drag only Complete with Verifying or Accepted Card.", { severity: "warning", onClose: function () { renderConveyor(); } });
            return;
          }
          const doneWorkRequestObj = (Board.state.WORK_REQUESTS || []).find(function (t) {
            return t.number === draggedNum;
          });
          if (!doneWorkRequestObj) {
            renderConveyor();
            return;
          }
          // dragend has a modal callback before running the regression that is reset to draggedNum=null:
          // Preserve workRequest number to closure capture variable
          const capturedNum = draggedNum;

          if (draggedFrom === "Accepted") {
            // WR-418: Accepted → Complete Direct Transfer (force=true)
            function callAcceptedCompleteDnd(forceDirty) {
              fetch("/api/conveyor/complete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ work_request: capturedNum, force: true, force_dirty: forceDirty }),
              }).then(function (res) {
                return res.json().then(function (body) {
                  return { res: res, body: body };
                });
              }).then(function (r) {
                if (r.res.ok && r.body.ok) {
                  showAcceptedCompleteResultModal("success", r.body, function () {
                    fetchWorkRequests().then(renderConveyor);
                  });
                } else {
                  const kind = r.body.error_kind === "dirty_worktree" ? "dirty" : "error";
                  showAcceptedCompleteResultModal(kind, r.body, function () {
                    renderConveyor();
                  }, kind === "dirty" ? function () {
                    callAcceptedCompleteDnd(true);
                  } : undefined);
                }
              }).catch(function (err) {
                console.error("[conveyor DnD] open-complete failed:", err);
                showAcceptedCompleteResultModal("error", { message: err.message }, function () { renderConveyor(); });
              });
            }
            showAcceptedCompleteConfirmModal(
              doneWorkRequestObj,
              function (forceDirty) {
                callAcceptedCompleteDnd(forceDirty);
              },
              function () {
                // [Cancel]/ESC/overlay callback: Return card origin
                renderConveyor();
              }
            );
          } else {
            // WR-906: Verifying → Complete drop
            showCompleteConfirmModal(
              doneWorkRequestObj,
              function () {
                // [Completion] Callback: POST /api/conveyor/complete → cmd done commission
                fetch("/api/conveyor/complete", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ work_request: capturedNum }),
                }).then(function (res) {
                  return res.json().then(function (body) {
                    return { res: res, body: body };
                  });
                }).then(function (r) {
                  if (r.res.ok && r.body.ok) {
                    showCompleteResultModal("success", r.body, function () {
                      fetchWorkRequests().then(renderConveyor);
                    });
                  } else {
                    const kind = r.body.error_kind === "merge_conflict" ? "conflict"
                      : r.body.error_kind === "dirty_worktree" ? "dirty"
                      : "error";
                    showCompleteResultModal(kind, r.body, function () { renderConveyor(); });
                  }
                }).catch(function (err) {
                  console.error("[conveyor DnD] complete failed:", err);
                  showCompleteResultModal("error", { message: err.message }, function () { renderConveyor(); });
                });
              },
              function () {
                // [Cancel]/ESC/overlay callback: Return card origin
                renderConveyor();
              }
            );
          }
          return;
        }

        // Draft allows to move only to Accepted (Verifying/Other Blocks)
        if (draggedFrom === "Draft" && targetCol !== "Accepted") {
          Board.util.showInfoModal("DnD Lockout", "Draft cards can be dragging only to Accepted Column.", { severity: "warning", onClose: function () { renderConveyor(); } });
          return;
        }

        // Draft ↔ Accepted ↔ Verifying Simplified (includes Accepted → Verifying direct transfer)
        const moveToMap = { "Draft": "todo", "Accepted": "open", "Verifying": "review" };
        const to = moveToMap[targetCol];
        if (!to) {
          console.error("[conveyor DnD] unknown target column:", targetCol);
          renderConveyor();
          return;
        }
        fetch("/api/conveyor/move", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ work_request: draggedNum, to: to }),
        }).then(function (res) {
          if (!res.ok) return res.json().then(function (j) { throw new Error(j.error || res.statusText); });
          return res.json();
        }).then(function () {
          fetchWorkRequests().then(function () { renderConveyor(); });
        }).catch(function (err) {
          console.error("[conveyor DnD] move failed:", err);
          Board.util.showInfoModal("WorkRequest Transfer Failure", "WorkRequest Transfer Failure:" + err.message, { severity: "error" });
        });
      });
    });
  }

  /** Renders the conveyor board with columns, cards, and sort controls. */
  function renderConveyor() {
    // Dismiss any stale popover before re-rendering the board DOM
    hideRelationsPopover();

    const el = document.getElementById("view-conveyor");
    // scroll-top location capture by column — scrollTop restore lost with innerHTML rotation
    const scrollPositions = {};
    el.querySelectorAll(".cards[data-col-key]").forEach(function (cards) {
      scrollPositions[cards.dataset.colKey] = cards.scrollTop;
    });
    let h = '<div class="conveyor-board">';
    COLUMNS.forEach(function (col) {
      const items = Board.state.WORK_REQUESTS.filter(function (t) {
        if (col.key === "Draft") { return t.status === "Draft"; }
        if (col.key === "Accepted") { return t.status === "Accepted"; }
        return t.status === col.key;
      });
      const colSort = conveyorSort[col.key] || { key: "number", dir: "asc" };
      const isManualTodo = (col.key === "Draft" && colSort.key === "manual");
      const sortedItems = isManualTodo
        ? applyTodoManualOrder(items)
        : sortWorkRequests(items, colSort.key, colSort.dir);
      const sortIcon = colSort.dir === "desc" ? SVG_DESC : SVG_ASC;

      // Build dropdown options HTML
      // Draft Column adds the option "About Us" in front of the main
      let dropHtml = '<div class="col-sort-dropdown" data-col="' + esc(col.key) + '">';
      const sortKeysForCol = (col.key === "Draft")
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

      // Complete / Draft Column Supports Fold Toggle
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
        // WR-399: Added to Executing drop target (available only on Accepted → Executing check modal).
        // WR-906: Added to Complete drop target (Verifying → Complete drop only confirm accepted as modal).
        // Accepted → Verifying Adds Directly: Verifying also drop target.
        const isDroppable = (col.key === "Draft" || col.key === "Accepted" || col.key === "Executing" || col.key === "Complete" || col.key === "Verifying");
        const droppableClass = isDroppable ? ' cards-droppable' : '';
        h += '<div class="cards' + droppableClass + '" data-col-key="' + esc(col.key) + '">';
        if (sortedItems.length === 0) {
          h += '<div class="empty">No items</div>';
        } else {
          sortedItems.forEach(function (t) {
            const done = col.key === "Complete" ? " done" : "";
            const status = getWorkflowStatus(t);
            // DnD: Draft / Accepted column card only draggable.
            // WR-399: Executing card drag indispensable protection (blocking workflow cancellations).
            // WR-906: Added Verifying card draggable (Verifying → Complete drop allowed).
            // Complete card is draggable=false (preventive protection).
            const isDraggable = (col.key === "Draft" || col.key === "Accepted" || col.key === "Verifying");
            const draggableAttr = isDraggable ? ' draggable="true"' : '';
            const draggableClass = isDraggable ? ' card-draggable' : '';
            // WR-433 Phase 2: The Verifying Card has-active-branch class grant (external glow vision).
            const branchActiveClass = (col.key === "Verifying" && _activeBranchWorkRequest === t.number) ? ' has-active-branch' : '';
            h += '<div class="card' + done + draggableClass + branchActiveClass + '" data-num="' + esc(t.number) + '" data-col-key="' + esc(col.key) + '"' + draggableAttr + '>';
            // Top: Left Group (WorkRequest number + Command badge), Right Status Label
            h += '<div class="card-top">';
            h += '<div class="card-top-left">';
            h += '<span class="card-num">' + esc(t.number.replace(/^WR-/, "")) + "</span>";
            if (t.command && t.command.indexOf(">") !== -1) {
              h += renderChainIcons(t);
            } else if (t.command) {
              var badgeAnim = (t.status === "Executing") ? "animation:chain-pulse 1.5s ease-in-out infinite" : "";
              h += badge(t.command, CMD_COLORS[t.command], badgeAnim);
            }
            h += "</div>";
            h += '<div class="card-top-right">';
            if (col.key === "Draft" && status) {
              h += '<span class="card-status ' + status.cssClass + '">' + esc(status.label) + "</span>";
            }
            h += renderUncommittedBadge(t.number);
            // WR-457 (Layer 3): failure tag (workRequest.failure exists) — guards inside the helper
            h += renderFailureTag(t);
            // WR-475 Stage 3: Start starting pulse badge (submit right after ~ LAUNCH STARTED before receiving)
            h += renderLaunchBadge(t.number);
            // WR-441: Complete Card verdict badge (advisory)
            if (col.key === "Complete") {
              h += renderCompleteVerdictBadge(t.number);
            }
            // WR-477: Verifying Card Auditor T3 Auditor (advisory only)
            if (col.key === "Verifying") {
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
            // WR-463: Verifying Card verdict badge (advisory only).
            // 4th action-row first child + margin-right:auto to left fixed, right commit/branch-toggle/done and separating.
            // Auto-blocking / forced pre-determined by verdict results $0 — user-sharing freedom.
            if (col.key === "Verifying") {
              h += renderVerifyingVerdictBadge(t.number);
            }
            // WR-457 (Layer 3): Micommit Worktree Commit Action Button — Mark if any column or micommit.
            // flex-end + left → enter the order commit to this left, done this position on the right side.
            if (_worktreeUncommittedMap) {
              var uitem = _worktreeUncommittedMap.get(t.number);
              if (uitem && uitem.uncommitted_count > 0) {
                var ctip = "Mickey Mouse" + uitem.uncommitted_count + "— Click Commit";
                h += '<button class="card-commit-action" data-commit-work-request="' + esc(t.number) + '" title="' + esc(ctip) + '" draggable="false">';
                // SVG: Commit graph dot motif (won + short line up/down)
                h += '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">';
                h += '<circle cx="7" cy="7" r="2.4" stroke="currentColor" stroke-width="1.6" fill="none"/>';
                h += '<line x1="7" y1="0.5" x2="7" y2="4.0" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>';
                h += '<line x1="7" y1="10.0" x2="7" y2="13.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>';
                h += '</svg>';
                h += '</button>';
              }
            }
            // Executing card: Workflow stop button (POST /api/workflow/stop) — 4 axis (process/jsonl/bar/worktree) integration.
            if (col.key === "Executing") {
              h += '<button class="card-stop-action" data-stop-work-request="' + esc(t.number) + '" title="Stop workflow (Proceed/jsonl/Collection/Worktree 4)" draggable="false">';
              h += '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">';
              h += '<rect x="3" y="3" width="8" height="8" rx="1" stroke="currentColor" stroke-width="1.6" fill="currentColor"/>';
              h += '</svg>';
              h += '</button>';
            }
            if (col.key === "Verifying") {
              // WR-433 Phase 2: Feature Brand-Activate/Remote Toggle Button (4-row left, batch button on left).
              // OFF: Grey outline / ON: Terracotta + Card Exterior Light glow.
              // Only one card is active guarantee —  activeBranchWorkRequest status standard .active grant.
              var isBranchActive = (_activeBranchWorkRequest === t.number);
              var toggleClass = isBranchActive ? " active" : "";
              var toggleTip = isBranchActive
                ? "feature Brand Name Active — Click to Return to develop"
                : "Click to switch main working tree to this feature branch";
              h += '<button class="card-branch-toggle' + toggleClass + '" data-branch-work-request="' + esc(t.number) + '" title="' + esc(toggleTip) + '" draggable="false">';
              // Lucide git-branch SVG (16px, currentColor) — e749003 Vocabulary Match
              h += '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">';
              h += '<line x1="6" y1="3" x2="6" y2="15"/>';
              h += '<circle cx="18" cy="6" r="3"/>';
              h += '<circle cx="6" cy="18" r="3"/>';
              h += '<path d="M18 9a9 9 0 0 1-9 9"/>';
              h += '</svg>';
              h += '</button>';
              h += '<button class="card-complete-action" data-num="' + esc(t.number) + '" title="finishing" draggable="false">';
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

    // ScrollTop Restore Capture
    Object.keys(scrollPositions).forEach(function (colKey) {
      const cards = el.querySelector('.cards[data-col-key="' + colKey + '"]');
      if (cards) cards.scrollTop = scrollPositions[colKey];
    });

    // Bind card clicks
    el.querySelectorAll(".card").forEach(function (card) {
      card.addEventListener("click", function (e) {
        // WR-457 (Layer 3): 4th Commit button click → Worktree auto commit action commission.
        // .card-uncommitted-badge is modified to read-only mark label — no click trigger)
        var commitBtn = e.target.closest(".card-commit-action");
        if (commitBtn) {
          e.stopPropagation();
          handleCommitButtonClick(commitBtn);
          return;
        }
        // Executing card 4 workflow stop button → handleStopButtonClick position
        var stopBtn = e.target.closest(".card-stop-action");
        if (stopBtn) {
          e.stopPropagation();
          handleStopButtonClick(stopBtn);
          return;
        }
        // WR-433 Phase 2: Click on the Brand Match Toggle button on the Verifying card → enter handleBranchToggleClick
        var branchToggle = e.target.closest(".card-branch-toggle");
        if (branchToggle) {
          e.stopPropagation();
          var bnum = branchToggle.dataset.branchWorkRequest || card.dataset.num;
          handleBranchToggleClick(bnum);
          return;
        }
        // WR-439: Verifying Card Velvet Finished Action Button Click → HandleVerifyingCompleteAction
        var doneAction = e.target.closest(".card-complete-action");
        if (doneAction) {
          e.stopPropagation();
          const num = card.dataset.num;
          const workRequest = Board.state.WORK_REQUESTS.find(function (t) { return t.number === num; });
          if (workRequest) handleVerifyingCompleteAction(workRequest);
          return;
        }
        // WR-441: Complete card verdict FAIL badge click → Show details message (advisory)
        var verdictFail = e.target.closest(".card-complete-verdict.verdict-fail");
        if (verdictFail) {
          e.stopPropagation();
          var workRequestNum = card.dataset.num;
          var msg = verdictFail.dataset.verdictMsg || "Develop head is mitigating";
          var verdictData = workRequestNum ? _completeVerdictMap[workRequestNum] : null;
          var detail = (verdictData && verdictData.details) || {};
          var bodyMsg = msg;
          if (detail.develop_head) bodyMsg += "\n\ndevelop HEAD : " + detail.develop_head.slice(0, 8);
          if (detail.merge_commit) bodyMsg += "\nmerge commit: " + detail.merge_commit.slice(0, 8);
          bodyMsg += "\\n\\n may not be reflected in development. \\n* advisory only — no automatic ream. Please check it manually.";
          Board.util.showInfoModal("Mage Commodity FAIL", bodyMsg, { severity: "warning" });
          return;
        }
        const num = card.dataset.num;
        const workRequest = Board.state.WORK_REQUESTS.find(function (t) { return t.number === num; });
        if (workRequest) Board.render.openViewer(workRequest);
      });
    });

    // WR-905 Phase 3: Right-click context menu binding to Complete column card ("Verifying")
    el.querySelectorAll('.card[data-col-key="Complete"]').forEach(function (card) {
      card.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        const num = card.dataset.num;
        const workRequest = Board.state.WORK_REQUESTS.find(function (t) { return t.number === num; });
        if (workRequest) showCompleteCardContextMenu(e, workRequest);
      });
    });

    // WR-441: Complete Card verdict fetch trigger (advisory)
    el.querySelectorAll('.card[data-col-key="Complete"]').forEach(function (card) {
      var num = card.dataset.num;
      if (num) {
        // Mickey Card Only Fetch (Skip when hitting)
        fetchAndRenderVerdict(num);
      }
    });

    // WR-463: Verifying Card Verdict Fetch Trigger (advisory only)
    // One call (no locking) when card mount. Skip to main content
    el.querySelectorAll('.card[data-col-key="Verifying"]').forEach(function (card) {
      var num = card.dataset.num;
      if (num) {
        fetchAndRenderVerifyingVerdict(num);
      }
    });

    // WR-477: Verifying card audit verdict fetch trigger (advisory)
    el.querySelectorAll('.card[data-col-key="Verifying"]').forEach(function (card) {
      var num = card.dataset.num;
      if (num) {
        fetchAndRenderAuditVerdict(num);
      }
    });

    // WR-418: Right-click context menu binding on Accepted Column Card ("Complete" + "Tube")
    el.querySelectorAll('.card[data-col-key="Accepted"]').forEach(function (card) {
      card.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const num = card.dataset.num;
        const workRequest = Board.state.WORK_REQUESTS.find(function (t) { return t.number === num; });
        if (workRequest) showAcceptedCardContextMenu(e, workRequest);
      });
    });

    // Verifying Click context menu binding on column card ("Rework with Accepted" single option)
    el.querySelectorAll('.card[data-col-key="Verifying"]').forEach(function (card) {
      card.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const num = card.dataset.num;
        const workRequest = Board.state.WORK_REQUESTS.find(function (t) { return t.number === num; });
        if (workRequest) showVerifyingCardContextMenu(e, workRequest);
      });
    });

    // ── DnD: Draft ↔ Accepted Card Drag & Drop ──
    // Safety DnD Policy: Exemption without cracking effect allowed (Executing / Complete separately command)
    // WR-418: Accepted → Complete allows direct transition check modal (force=true)
    bindConveyorDnd(el);

    // Bind sort button clicks (toggle dropdown)
    el.querySelectorAll(".col-sort-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        const dropdown = btn.parentNode.querySelector(".col-sort-dropdown");
        const isAccepted = dropdown.classList.contains("open");
        el.querySelectorAll(".col-sort-dropdown.open").forEach(function (d) {
          d.classList.remove("open");
        });
        if (!isAccepted) {
          dropdown.classList.add("open");
        }
      });
    });

    // Bind sort option clicks
    el.querySelectorAll(".col-sort-option").forEach(function (opt) {
      opt.addEventListener("click", function (e) {
        e.stopPropagation();
        const colKey = opt.dataset.col;
        const current = conveyorSort[colKey] || { key: "number", dir: "asc" };
        if (opt.dataset.sortKey && !opt.dataset.sortDir) {
          conveyorSort[colKey] = { key: opt.dataset.sortKey, dir: current.dir };
        } else if (opt.dataset.sortDir && !opt.dataset.sortKey) {
          conveyorSort[colKey] = { key: current.key, dir: opt.dataset.sortDir };
        }
        saveConveyorSort();
        renderConveyor();
      });
    });

    // Bind collapse toggle buttons (unfolded). Complete/Draft Common.
    el.querySelectorAll(".column-toggle-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        const colKey = btn.dataset.colKey;
        if (!colKey) return;
        saveColumnCollapsed(colKey, !loadColumnCollapsed(colKey));
        renderConveyor();
      });
    });

    // Bind collapsed bar click (directed → unfold). Complete/Draft Common.
    el.querySelectorAll(".column-collapsed-bar").forEach(function (bar) {
      bar.addEventListener("click", function (e) {
        e.stopPropagation();
        const colKey = bar.dataset.colKey;
        if (!colKey) return;
        saveColumnCollapsed(colKey, false);
        renderConveyor();
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

    // WR-433 Phase 2: Initial fetch in the first active branch in the page load (after call is ignored by guard).
    // syncActiveBranchFromSSE is synchronized when SSE git branch event arrives.
    fetchAndApplyActiveBranch();
  }

  // ──────────────────────────────────────────────────────────────────────
  // WR-475 Stage 3 Helper — launch asynchronous client state machine
  // ──────────────────────────────────────────────────────────────────────

  /**
   * Starting status card 1 right-hand pulse badge HTML.
   * Exposure while the workRequest registered in launchState is 'starting'.
   */
  function renderLaunchBadge(workRequestNum) {
    const cur = launchState.get(workRequestNum);
    if (!cur || cur.state !== "starting") return "";
    return '<span class="card-launch-badge">';
  }

  /**
   * launchState + sessionStorage cleanup single entry point.
   * grace timer Clear + Delete Map + Delete storage + (Optional) renderConveyor.
   * Close-up helper for stuck revolving blocks.
   */
  function cleanupLaunchState(workRequestNum, opts) {
    const cur = launchState.get(workRequestNum);
    if (cur && cur.graceTimer) clearTimeout(cur.graceTimer);
    launchState.delete(workRequestNum);
    try { sessionStorage.removeItem(LAUNCH_STORAGE_PREFIX + workRequestNum); } catch (_) {}
    if (opts && opts.render && Board.render && Board.render.renderConveyor) {
      Board.render.renderConveyor();
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
  function registerLaunchStarting(workRequestNum, command) {
    // Default object view. Click to enlarge
    const prev = launchState.get(workRequestNum);
    if (prev && prev.graceTimer) clearTimeout(prev.graceTimer);
    const since = Date.now();
    const entry = {
      state: "starting",
      since: since,
      command: command,
      sessionId: null,
      graceTimer: setTimeout(function () { onGraceExpired(workRequestNum); }, LAUNCH_GRACE_MS),
    };
    launchState.set(workRequestNum, entry);
    try {
      sessionStorage.setItem(
        LAUNCH_STORAGE_PREFIX + workRequestNum,
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
    if (!data || !data.work_request) return;
    const workRequestNum = data.work_request;
    const cur = launchState.get(workRequestNum);
    // This client only handles the submitted card — other tabs/browser submits are synchronized with fetchWorkRequests
    if (!cur) return;

    if (data.event === "LAUNCH_STARTED") {
      if (cur.graceTimer) clearTimeout(cur.graceTimer);
      launchState.set(workRequestNum, {
        state: "running",
        since: cur.since,
        command: cur.command,
        sessionId: data.session_id || "",
        graceTimer: null,
      });
      // WR-495 P2 — production-line ramen session id to board.productionLineWorkflow
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
      // WR-516 — Workflow ID to localStorage single source.
      // Because the helper handles dedupe, submit response add calls and compatible safety (OR conditions).
      if (data.session_id && Board.workflowTabStorage && Board.workflowTabStorage.add) {
        Board.workflowTabStorage.add(data.session_id);
      }
      // After running, it is necessary to remove the badge immediately after running, so it is possible to clean the launchState immediately.
      // However, debug/released after conserving the possibility of SSE (the following renderConveyor calls disappeared).
      launchState.delete(workRequestNum);
      try { sessionStorage.removeItem(LAUNCH_STORAGE_PREFIX + workRequestNum); } catch (_) {}
      // Remove Badge + Executing Column Top Mark
      if (Board.render.renderConveyor) Board.render.renderConveyor();
    } else if (data.event === "LAUNCH_FAILED") {
      if (cur.graceTimer) clearTimeout(cur.graceTimer);
      launchState.delete(workRequestNum);
      try { sessionStorage.removeItem(LAUNCH_STORAGE_PREFIX + workRequestNum); } catch (_) {}
      Board.util.showInfoModal(
        "Workflow failed to run",
        formatLaunchFailReason(data.reason, data.error_message),
        {
          severity: "error",
          onClose: function () {
            if (Board.fetch.fetchWorkRequests && Board.render.renderConveyor) {
              Board.fetch.fetchWorkRequests().then(function () { Board.render.renderConveyor(); });
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
  function onGraceExpired(workRequestNum) {
    const cur = launchState.get(workRequestNum);
    if (!cur || cur.state !== "starting") return;
    cleanupLaunchState(workRequestNum);
    if (Board.render && Board.render.renderConveyor) Board.render.renderConveyor();
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
        label = "WorkRequests are Draft status. Go to Accepted and try again.";
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
      var workRequestNum = key.slice(LAUNCH_STORAGE_PREFIX.length);
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
        launchState.set(workRequestNum, {
          state: "starting",
          since: since,
          command: stored.command || "",
          sessionId: null,
          graceTimer: setTimeout(function () { onGraceExpired(workRequestNum); }, remaining),
        });
      }
    });
  }

  // ── Register on Board namespace ──
  Board.fetch.fetchWorkRequests = fetchWorkRequests;
  Board.fetch.fetchWorkRequestsByFiles = fetchWorkRequestsByFiles;
  Board.render.renderConveyor = renderConveyor;
  // WR-433 Phase 2: SSE git branch event listener calls synchronized entry-point.
  // (sse.js has a single listener — addEventListener duplicate registration prevention §2.4)
  Board.render.syncActiveBranchFromSSE = syncActiveBranchFromSSE;

  // WR-475 Stage 3: SSE 'launch' event dispatch + restore entry-point when loading page.
  // (sse.js single listener call Board.conveyor.handleLaunchEvent — addEventListener duplicate)
  Board.conveyor = Board.conveyor || {};
  Board.conveyor.handleLaunchEvent = handleLaunchEvent;
  Board.conveyor.restoreLaunchStateFromStorage = restoreLaunchStateFromStorage;

  // WR-473: Bind relations popover delegated events once at module init time.
  // bindRelationsPopoverEvents() is idempotent (_relPopoverBound guard),
  // but we call it once here to ensure listeners are registered before first render.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindRelationsPopoverEvents);
  } else {
    bindRelationsPopoverEvents();
  }
})();
