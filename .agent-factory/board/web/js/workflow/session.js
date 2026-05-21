/**
 * @module session
 *
 * SSE connection and session lifecycle management for the terminal.
 *
 * Provides connectSSE, disconnectSSE, startSession, killSession,
 * fetchStatus, postJson, and SSE event handlers.
 *
 * Depends on: common.js (Board namespace), renderers.js, workflow-bar.js
 * Registers:  Board.session
 */
"use strict";

(function () {
  var esc = Board.util.esc;

  // ── Constants ──
  var SSE_RECONNECT_INTERVAL = 3000;

  // ── Internal state ──
  /** Session switch/start duplicate request prevention flag. True until the spawn response comes. */
  var _startInFlight = false;
  /** @type {EventSource|null} */
  var termEventSource = null;
  /** @type {number|null} */
  var reconnectTimerId = null;
  /**
   * Tracks texts sent via sendInput() to avoid duplicate DOM insertion
   * when the same text arrives back as a user_input SSE event.
   * During history replay the set is empty, so all user_input events
   * are rendered into the DOM as expected.
   * @type {Set<string>}
   */
  var _sentTexts = new Set();

  /**
   * Tracks the tool_use_id of the most recently started tool invocation.
   * Updated on each content_block_start event; used by input_json_delta
   * to route chunks into the correct per-tool input buffer.
   * @type {string|null}
   */
  var _currentToolUseId = null;

  /**
   * Accumulates text_delta chunks between flush points.
   * Used to call WorkflowRenderer.tap() at flush time in workflow mode,
   * so that [STATE] banners arriving via text stream are also parsed.
   * @type {string}
   */
  var _pendingTextBuffer = "";

  /**
   * True while the server is replaying history (between replay_start
   * and replay_end SSE events). During replay, phaseTimeline renders
   * are deferred to avoid intermediate DOM thrashing.
   * @type {boolean}
   */
  var _isReplaying = false;

  /**
   * Last SSE event id successfully received by the client.
   * Used on reconnect to request history replay from the next id, avoiding
   * full-history re-replay that caused panel duplication on tab switch.
   *
   * EventSource does not allow setting custom headers, so we pass this
   * via `last_event_id` URL query parameter. The server accepts either
   * the native Last-Event-ID header or this query parameter.
   *
   * @type {number}
   */
  var _lastEventId = -1;
  /** @type {Object<string, number>} sessionId -> last-event-id */
  var _lastEventIdBySession = {};
  /** Set true when server sends archived_end or fetchStatus 404; disables reconnect. */
  var _sessionArchived = false;

  /**
   * rate_limit banner single instance reference. When receiving the same (status, limitType) continuously
   * A dedupe anchor to only update timestamps instead of regenerating the DOM.
   * @type {HTMLElement|null}
   */
  var _rateLimitBanner = null;
  /**
   * Handle to the 5-second automatic dismissal timer for the `allowed` status banner.
   * ClearTimeout target when creating a new banner/explicitly dismissing it.
   * @type {number|null}
   */
  var _rateLimitDismissTimer = null;

  // ── task state storage (T-390) ──
  /**
   * Subagent task state map. task_id -> TaskState.
   * TaskState fields: description, status("running"|"completed"|"error"),
   *   toolName, summary, startedAt, updatedAt.
   * @type {Object<string, {description:string, status:string, toolName:string, summary:string, startedAt:number, updatedAt:number}>}
   */
  var _taskStatusMap = {};
  /**
   * requestAnimationFrame token. If it is 0, it is not reserved.
   * Guard to prevent duplicate reservation of the same frame.
   * @type {number}
   */
  var _taskRenderRafId = 0;

  function _sessionKey() {
    if (_ctx && _ctx.isWorkflowMode && _ctx.isWorkflowMode()) {
      return (_ctx.getWorkflowSessionId && _ctx.getWorkflowSessionId()) || "main";
    }
    return "main";
  }

  function _captureEventId(e) {
    if (!e || e.lastEventId == null) return;
    var n = parseInt(e.lastEventId, 10);
    if (isNaN(n)) return;
    if (n > _lastEventId) _lastEventId = n;
    var key = _sessionKey();
    if (!(key in _lastEventIdBySession) || n > _lastEventIdBySession[key]) {
      _lastEventIdBySession[key] = n;
    }
  }

  // ── rate_limit banner helper (T-389) ──
  // SVG inline icons (general.md MUST: no external icon libraries/fonts).
  // 16x16 simple path — info: i-circle, warn/danger: !-triangle, dismiss: x.
  var _RL_ICON_INFO =
    '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"' +
    ' xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
    '<circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5"/>' +
    '<path d="M8 7v4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>' +
    '<circle cx="8" cy="4.75" r="0.9" fill="currentColor"/>' +
    '</svg>';
  var _RL_ICON_WARN =
    '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"' +
    ' xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
    '<path d="M8 1.5 15 14H1L8 1.5Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>' +
    '<path d="M8 6v3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>' +
    '<circle cx="8" cy="11.75" r="0.9" fill="currentColor"/>' +
    '</svg>';
  var _RL_ICON_DISMISS =
    '<svg width="12" height="12" viewBox="0 0 12 12" fill="none"' +
    ' xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
    '<path d="M2.5 2.5l7 7M9.5 2.5l-7 7" stroke="currentColor"' +
    ' stroke-width="1.5" stroke-linecap="round"/>' +
    '</svg>';

  /**
   * status → variant (CSS class suffix) + icon SVG mapping.
   * Unspecified status is a defensive fallback to info.
   */
  function _rateLimitVariant(status) {
    if (status === "exceeded") return { variant: "danger", icon: _RL_ICON_WARN };
    if (status === "allowed_warning") return { variant: "warn", icon: _RL_ICON_WARN };
    if (status === "allowed") return { variant: "info", icon: _RL_ICON_INFO };
    return { variant: "info", icon: _RL_ICON_INFO };
  }

  /**
   * epoch seconds → ko-KR HH:mm format. If null/invalid, it is an empty string.
   * @param {number|null} resetsAt epoch seconds
   * @returns {string}
   */
  function _formatResetsAt(resetsAt) {
    if (resetsAt == null || isNaN(resetsAt)) return "";
    try {
      return new Date(resetsAt * 1000).toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit"
      });
    } catch (err) {
      return "";
    }
  }

  /**
   * Build the detail line ("limit_type · resets HH:mm"). If both are empty, an empty string.
   */
  function _buildRateLimitDetail(limitType, resetsAt) {
    var parts = [];
    if (limitType) parts.push(limitType);
    var t = _formatResetsAt(resetsAt);
    if (t) parts.push("resets " + t);
    return parts.join(" · ");
  }

  /**
   * rate_limit Banner DOM creation. The structure is the same as the plan.md Phase 2 T2-1 specification.
   * @param {string} status
   * @param {string} limitType
   * @param {number|null} resetsAt epoch seconds or null
   * @returns {HTMLElement}
   */
  function _buildRateLimitBanner(status, limitType, resetsAt) {
    var v = _rateLimitVariant(status);
    var banner = document.createElement("div");
    banner.className =
      "term-rate-limit-banner term-rate-limit-banner--" + v.variant;
    banner.dataset.status = status;
    banner.dataset.limitType = limitType;

    var iconSpan = document.createElement("span");
    iconSpan.className = "term-rate-limit-icon";
    iconSpan.innerHTML = v.icon;
    banner.appendChild(iconSpan);

    var content = document.createElement("div");
    content.className = "term-rate-limit-content";

    var title = document.createElement("span");
    title.className = "term-rate-limit-title";
    title.textContent = "Rate limit: " + status;
    content.appendChild(title);

    var detailText = _buildRateLimitDetail(limitType, resetsAt);
    if (detailText) {
      var detail = document.createElement("span");
      detail.className = "term-rate-limit-detail";
      detail.textContent = detailText;
      content.appendChild(detail);
    }
    banner.appendChild(content);

    var btn = document.createElement("button");
    btn.className = "term-rate-limit-dismiss";
    btn.type = "button";
    btn.setAttribute("aria-label", "close");
    btn.innerHTML = _RL_ICON_DISMISS;
    btn.addEventListener("click", _dismissRateLimitBanner);
    banner.appendChild(btn);

    return banner;
  }

  /**
   * In the dedupe path, only the detail line of the existing banner is updated. The title is immutable because its status is the same.
   * @param {HTMLElement} banner
   * @param {string} limitType
   * @param {number|null} resetsAt
   */
  function _updateRateLimitBannerDetail(banner, limitType, resetsAt) {
    if (!banner) return;
    var detailText = _buildRateLimitDetail(limitType, resetsAt);
    var content = banner.querySelector(".term-rate-limit-content");
    if (!content) return;
    var detail = content.querySelector(".term-rate-limit-detail");
    if (detailText) {
      if (!detail) {
        detail = document.createElement("span");
        detail.className = "term-rate-limit-detail";
        content.appendChild(detail);
      }
      detail.textContent = detailText;
    } else if (detail) {
      detail.remove();
    }
  }

  /**
   * Remove active banner + clean up timer. idempotent.
   */
  function _dismissRateLimitBanner() {
    if (_rateLimitDismissTimer) {
      clearTimeout(_rateLimitDismissTimer);
      _rateLimitDismissTimer = null;
    }
    if (_rateLimitBanner) {
      try {
        if (_rateLimitBanner.parentNode) {
          _rateLimitBanner.parentNode.removeChild(_rateLimitBanner);
        }
      } catch (err) {
        // Ignored if DOM has already been cleaned up with clearOutput etc.
      }
      _rateLimitBanner = null;
    }
  }

  // ── task status helper (T-390) ──

  /**
   * Create a taskId item in _taskStatusMap or merge it into a patch.
   * updatedAt is always updated with Date.now().
   * @param {string} taskId
   * @param {Object} patch
   */
  function _upsertTaskState(taskId, patch) {
    if (!taskId) return;
    var existing = _taskStatusMap[taskId] || {
      description: "",
      status: "running",
      toolName: "",
      summary: "",
      startedAt: Date.now(),
      updatedAt: 0
    };
    _taskStatusMap[taskId] = Object.assign({}, existing, patch, { updatedAt: Date.now() });
  }

  /**
   * Reserve rAF and coalesce so that _flushTaskRender is called only once per frame.
   * If a reservation has already been made, do not make a duplicate reservation.
   */
  function _scheduleTaskRender() {
    if (_taskRenderRafId !== 0) return; // Already booked — skip
    _taskRenderRafId = requestAnimationFrame(function () {
      _taskRenderRafId = 0;
      _flushTaskRender();
    });
  }

  /**
   * rAF callback. Call phaseTimeline.renderTaskRow only when in workflow mode.
   */
  function _flushTaskRender() {
    if (!_ctx || !_ctx.isWorkflowMode || !_ctx.isWorkflowMode()) return;
    if (Board.phaseTimeline && typeof Board.phaseTimeline.renderTaskRow === "function") {
      Board.phaseTimeline.renderTaskRow(_taskStatusMap);
    }
  }

  /**
   * Per-tool_use_id input buffer map.
   * Parallel tool calls may interleave input_json_delta events, so each
   * tool_use_id gets its own accumulator instead of a single shared buffer.
   * @type {Object<string, string>}
   */
  var _toolInputMap = {};

  // ── Accessor for terminal core state ──
  // These are set by terminal.js core via Board.session._bind()
  var _ctx = null;

  /**
   * Binds the session module to terminal core context.
   * Called by terminal.js core after initialization.
   * @param {object} ctx - context object with core references
   */
  function bind(ctx) {
    _ctx = ctx;
  }

  // ── Utility ──

  function postJson(path, body) {
    var opts = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    };
    if (body !== undefined) {
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (res) {
      if (!res.ok) {
        return res.json().then(function (err) {
          throw new Error(err.error || "Request failed: " + res.status);
        }).catch(function (parseErr) {
          if (parseErr.message && parseErr.message.indexOf("Request failed") === 0) throw parseErr;
          throw new Error("Request failed: " + res.status);
        });
      }
      return res.json();
    });
  }

  /**
   * Parse the server model string and set the context window size and model display name.
   * It operates regardless of 1:1 turn simplification (W01~W04). The token accumulation logic is also similar to this function
   * Because it is processed in separate paths (_onStdout data.usage, _onResult data.*)
   * Confirm that there is no side effect of changing the turn model (regression verification item).
   */
  function _applyRawModel(raw) {
    if (!_ctx || !raw) return;
    var ctxMatch = raw.match(/\[(\d+)([mk])\]/i);
    if (ctxMatch) {
      var ctxNum = parseInt(ctxMatch[1]);
      _ctx.setContextWindow(ctxMatch[2].toLowerCase() === "m" ? ctxNum * 1000000 : ctxNum * 1000);
    }
    var clean = raw.replace(/\[.*\]/, "").replace(/^claude-/, "");
    clean = clean.replace(/-(\d+)-(\d+)/, " $1.$2").replace(/-/g, " ");
    _ctx.setSessionModel(clean.charAt(0).toUpperCase() + clean.slice(1));
  }

  function fetchStatus() {
    if (!_ctx) return Promise.resolve();
    if (Board.debugLog) Board.debugLog('fetchStatus.call', {
      url: _ctx.endpoints().status, termStatus: Board.state.termStatus,
    });
    return fetch(_ctx.endpoints().status, { cache: "no-store" }).then(function (res) {
      if (res.status === 404) {
        _sessionArchived = true;
        Board.state.setTermStatus("missing");
        Board.state.termConnected = false;
        _ctx.stopSpinner();
        _ctx.appendErrorMessage("[Error] Session not found. It has already been terminated or cleaned up.");
        _ctx.updateControlBar();
        return;
      }
      if (!res.ok) return;
      return res.json();
    }).then(function (data) {
      if (!data) return;
      if (Board.debugLog) Board.debugLog('fetchStatus.response', {
        status: data.status, archived: !!data.archived, session_id: data.session_id,
        awaiting_response: !!data.awaiting_response,
      });
      var termModStatus = Board._term;
      if (termModStatus) {
        termModStatus.terminalProvider = data.provider || termModStatus.terminalProvider || "claude";
        if (data.capabilities && typeof data.capabilities === "object") {
          termModStatus.terminalCapabilities = data.capabilities;
        }
      }
      if (data.archived) {
        _sessionArchived = true;
        Board.state.setTermStatus("archived");
      } else {
        // Merge server response (stopped/running) and server expansion status (idle/busy/starting).
        Board.state.reconcileTermStatus(data.status);
        // The server's awaiting_response=true is the "After sending user input and before receiving result" signal.
        // claude_process._status continues to be 'idle' after the result, so this alone is not enough.
        // Since spinner recovery is not possible, check this flag separately and raise it to busy.
        if (data.awaiting_response && !_ctx.isWorkflowMode()) {
          Board.state.setTermStatus("busy");
        }
        // If busy, spinner recovery (idempotent).
        if (Board.state.termStatus === "busy" && !_ctx.isWorkflowMode()) {
          var termMod = Board._term;
          if (Board.debugLog) Board.debugLog('fetchStatus.busy-spinner-attempt', {
            termMod: !!termMod, hasStart: !!(termMod && termMod.startSpinner),
          });
          if (termMod && termMod.startSpinner) termMod.startSpinner();
        }
      }
      // If you keep session_id in stopped state, the server will change .last-session-id to
      // The restored old UUID remains, and the first system/init event after Start is "Session Replacement"
      // It is mistaken for , and the user speech bubble just entered with clearOutput disappears.
      // If stopped, it is assumed that there is no active sid and set to null.
      Board.state.termSessionId = (data.status === "stopped")
        ? null
        : (data.session_id || null);
      // last_session_id: Field added by W01 server (previous/current session UUID)
      if (data.last_session_id) {
        Board.state.termLastSessionId = data.last_session_id;
      } else if (data.session_id) {
        Board.state.termLastSessionId = data.session_id || Board.state.termLastSessionId || null;
      }
      if (data.model) {
        _applyRawModel(data.model);
      }
      if (data.permission_mode || data.provider) {
        var modeEl = document.getElementById("terminal-sl-mode");
        if (modeEl) modeEl.textContent = data.permission_mode || data.provider;
      }
      Board.util.setBranchStatusBar(data.branch);
      _ctx.updateControlBar();
    }).catch(function () {});
  }

  // ── SSE Event Handlers (shared between SSE stream and REST history injection) ──

  /**
   * workflow_step event data processing.
   * handleStepEvent is idempotent, so it must be called even during replay to accumulate the FSM state.
   * Past step sequences are reflected in the phase timeline. Live render ends replay
   * Since _injectRestHistory is called in batches, it is skipped during replay.
   * @param {Object} data Parsed event data object
   */
  function _onWorkflowStep(data) {
    if (Board.WorkflowRenderer && Board.WorkflowRenderer.handleStepEvent) {
      Board.WorkflowRenderer.handleStepEvent(data);
    }
    if (!_isReplaying && _ctx && _ctx.isWorkflowMode()) {
      try { Board.phaseTimeline.render(); } catch (re) {}
    }
  }

  /**
   * Processing stdout event data.
   * Shared by SSE "stdout" listener and REST event injection.
   * @param {Object} data Parsed event data object
   */
  function _onStdout(data) {
    if (!_ctx) return;
    if (data.chunk && data.kind === "text_delta") {
      _ctx.setReceivedChunks(true);
      _ctx.appendTextBuffer(data.chunk);
      if (_ctx.isWorkflowMode()) {
        _pendingTextBuffer += data.chunk;
      }
    } else if (data.text && data.kind === "assistant" && !_ctx.getReceivedChunks()) {
      _ctx.appendTextBuffer(data.text);
    } else if (data.kind === "input_json_delta" && typeof data.chunk === "string") {
      if (_currentToolUseId) {
        if (!_toolInputMap[_currentToolUseId]) {
          _toolInputMap[_currentToolUseId] = "";
        }
        _toolInputMap[_currentToolUseId] += data.chunk;
      }
      _ctx.appendToolInputBuffer(data.chunk);
    } else if (data.kind === "content_block_start" && data.raw) {
      var block = data.raw.content_block || {};
      if (block.type === "tool_use" && block.name) {
        if (_ctx.isWorkflowMode() && _pendingTextBuffer) {
          try {
            var flushedText = _pendingTextBuffer;
            _pendingTextBuffer = "";
            var textBannerConsumed = Board.WorkflowRenderer.tap(flushedText);
            if (textBannerConsumed && !_isReplaying) {
              Board.phaseTimeline.render();
            }
          } catch (tapFlushErr) {
            _pendingTextBuffer = "";
          }
        } else {
          _pendingTextBuffer = "";
        }
        _ctx.flushTextBuffer();
        _ctx.resetToolInputBuffer();
        _ctx.setCurrentToolName(block.name);

        var toolUseId = block.id || null;
        _currentToolUseId = toolUseId;
        if (toolUseId) {
          _toolInputMap[toolUseId] = "";
        }

        if (_ctx.isWorkflowMode()) {
          _ctx.createWorkflowToolCard(block.name);
        } else {
          _ctx.createToolBox(block.name, toolUseId);
        }
      }
    } else if (data.kind === "user" && data.raw) {
      if (_ctx.isWorkflowMode() && _pendingTextBuffer) {
        try {
          var userFlushText = _pendingTextBuffer;
          _pendingTextBuffer = "";
          var userTextBannerConsumed = Board.WorkflowRenderer.tap(userFlushText);
          if (userTextBannerConsumed && !_isReplaying) {
            Board.phaseTimeline.render();
          }
        } catch (userTapErr) {
          _pendingTextBuffer = "";
        }
      } else {
        _pendingTextBuffer = "";
      }
      _ctx.flushTextBuffer();
      // [W04/W05 patch] Claude Agent SDK supports stdout/stderr with `toolUseResult` (camelCase) key.
      // Send the object together. Some variant/legacy payloads are `tool_use_result` (snake_case)
      // Both keys can be checked as fallback. The tr object key structure itself is tool specific.
      // Same (stdout/file.content/filenames/content) so no risk of regression.
      var tr = data.raw.toolUseResult || data.raw.tool_use_result || null;
      var mc = data.raw.message && data.raw.message.content;
      var resultText = "";

      // Extract tool_use_id: camelCase tr(toolUseResult) object has no tool_use_id field, so
      // Set mc[0].tool_use_id as the 1st priority, and snake_case tr.tool_use_id as the 2nd priority (legacy).
      var userToolUseId = null;
      if (mc && mc[0] && mc[0].tool_use_id) {
        userToolUseId = mc[0].tool_use_id;
      } else if (tr && tr.tool_use_id) {
        userToolUseId = tr.tool_use_id;
      }

      var userToolName = null;
      if (userToolUseId) {
        var map = _ctx.getToolBoxMap ? _ctx.getToolBoxMap() : {};
        var matchedBox = map[userToolUseId];
        if (matchedBox && matchedBox.getAttribute) {
          userToolName = matchedBox.getAttribute("data-tool-name");
        }
      }

      if (tr) {
        if (tr.stdout) resultText = tr.stdout;
        else if (tr.file && tr.file.content) resultText = tr.file.content;
        else if (Array.isArray(tr.filenames)) resultText = tr.filenames.join("\n");
        else if (typeof tr.content === "string") resultText = tr.content;
      }
      if (!resultText && mc && mc[0]) {
        if (typeof mc[0].content === "string") {
          resultText = mc[0].content;
        } else if (Array.isArray(mc[0].content)) {
          resultText = mc[0].content
            .filter(function(item) { return item && item.type === "text" && item.text; })
            .map(function(item) { return item.text; })
            .join("\n");
        }
      }

      if (userToolUseId && _toolInputMap[userToolUseId] !== undefined) {
        _ctx.resetToolInputBuffer();
        _ctx.appendToolInputBuffer(_toolInputMap[userToolUseId]);
        delete _toolInputMap[userToolUseId];
      }

      if (resultText && resultText.trim()) {
        var bannerConsumed = false;
        if (_ctx.isWorkflowMode()) {
          try {
            bannerConsumed = Board.WorkflowRenderer.tap(resultText);
            if (bannerConsumed && !_isReplaying) {
              Board.phaseTimeline.render();
              _ctx.removeEmptyWorkflowToolCard();
            }
          } catch (tapErr) {
            bannerConsumed = false;
          }
        }
        if (!bannerConsumed) {
          if (_ctx.isWorkflowMode()) {
            _ctx.insertWorkflowResult(resultText, false);
          } else {
            _ctx.insertToolResult(resultText, false, userToolName, userToolUseId);
          }
        }
      } else {
        _ctx.removeEmptyToolBox(userToolUseId);
      }
      if (tr && tr.stderr) {
        if (_ctx.isWorkflowMode()) {
          _ctx.insertWorkflowResult("[stderr] " + tr.stderr, true);
        } else {
          _ctx.insertToolResult("[stderr] " + tr.stderr, true, userToolName, userToolUseId);
        }
      }
      if (mc && mc[0] && mc[0].is_error) {
        if (_ctx.isWorkflowMode()) {
          _ctx.insertWorkflowResult("[Tool Error]", true);
        } else {
          _ctx.insertToolResult("[Tool Error]", true, userToolName, userToolUseId);
        }
      }
    }

    if (data.usage) {
      if (typeof data.usage.input_tokens === "number") {
        _ctx.setInputTokens(data.usage.input_tokens);
      }
      if (typeof data.usage.output_tokens === "number") {
        _ctx.setOutputTokens(data.usage.output_tokens);
      }
      _ctx.updateStatusLine();
    }
  }

  /**
   * result Event data processing.
   * Shared by SSE "result" listener and REST event injection.
   * @param {Object} data Parsed event data object
   */
  function _onResult(data) {
    if (!_ctx) return;
    if (Board.debugLog) Board.debugLog('_onResult', {
      done: !!data.done, isReplaying: _isReplaying, termStatus: Board.state.termStatus,
    });
    if (data.done) {
      _ctx.stopSpinner();
      if (typeof data.cost_usd === "number") _ctx.setSessionCost(data.cost_usd);
      if (!_ctx.isWorkflowMode() && _ctx.getSessionTokens().input === 0 && _ctx.getSessionTokens().output === 0) {
        if (typeof data.input_tokens === "number") _ctx.setInputTokens(data.input_tokens);
        if (typeof data.output_tokens === "number") _ctx.setOutputTokens(data.output_tokens);
      }
      _ctx.updateStatusLine();

      if (_ctx.isWorkflowMode() && _pendingTextBuffer) {
        try {
          var resultFlushText = _pendingTextBuffer;
          _pendingTextBuffer = "";
          Board.WorkflowRenderer.tap(resultFlushText);
        } catch (e) {
          _pendingTextBuffer = "";
        }
      } else {
        _pendingTextBuffer = "";
      }
      _ctx.flushTextBuffer();

      if (_ctx.isWorkflowMode() && !_isReplaying) {
        try {
          Board.phaseTimeline.render();
        } catch (renderErr) {}
      }

      _ctx.removeEmptyToolBox();
      _ctx.clearCurrentToolBox();
      if (_ctx.clearCurrentWorkflowToolCard) _ctx.clearCurrentWorkflowToolCard();
      _ctx.resetToolInputBuffer();
      _ctx.setCurrentToolName(null);

      _currentToolUseId = null;
      _toolInputMap = {};
      if (_ctx.resetToolBoxMap) _ctx.resetToolBoxMap();

      Board.state.setTermStatus("idle");
      _ctx.setReceivedChunks(false);
      _ctx.setInputLocked(false);
      // Result arrives after interrupt — Only clears the button inactivity flag.
      // [ESC Preservation Guard] termSessionId and conversation DOM are not touched.
      // Even after an ESC interrupt, the session ID and conversation history must remain the same.
      // It should be possible to restore history after refreshing. State changes on this path are
      // _interruptInFlight is limited to release (prevents regression).
      var termMod = Board._term;
      if (termMod && termMod._interruptInFlight) termMod._interruptInFlight = false;
      _ctx.updateControlBar();

      // W04 (1:1 turn model): result SSE arrival = 1 turn currently being processed is completed.
      // advanceTurn is if there are any remaining entries in the queue after the spinner stops + idle transition.
      // Immediately send the next entry with commitQueue() (1 turn = 1 message).
      // If the queue is empty, only idle cleanup (updateControlBar) is performed.
      // In environments where advanceTurn is not defined (old version polyfill), it falls back to drainQueue.
      //
      // [ESC race guard] _recentInterrupt In Windows, advanceTurn is skipped.
      // The process_exit + autoResume flow that arrives immediately after is responsible for processing the queue.
      // If you commit here, a queue entry is sent to the dying process and a response is received.
      // There was a regression where you couldn't receive it (2026-05-13 fix).
      var termMod2 = Board._term;
      var skipAdvanceForInterrupt = !!(termMod2 && termMod2._recentInterrupt);
      if (Board.debugLog) Board.debugLog('onResult.advanceTurnDecision', {
        hasAdvance: !!(termMod2 && typeof termMod2.advanceTurn === 'function'),
        recentInterrupt: !!(termMod2 && termMod2._recentInterrupt),
        skip: skipAdvanceForInterrupt,
      });
      if (skipAdvanceForInterrupt) {
        // skip — commitQueue at the completion of autoResume in startSession.setIdle.
      } else if (termMod2 && typeof termMod2.advanceTurn === "function") {
        termMod2.advanceTurn();
      } else if (_ctx.getInputQueue && _ctx.getInputQueue().length > 0) {
        _ctx.drainQueue();
      }
    }
  }

  /**
   * System event data processing.
   * Shared by SSE "system" listener and REST event injection.
   * @param {Object} data Parsed event data object
   */
  function _onSystem(data) {
    if (!_ctx) return;
    if (data.subtype === "init" && data.session_id) {
      var prevSid = Board.state.termSessionId;
      var isNewSession = !prevSid || String(prevSid) !== String(data.session_id);
      if (Board.debugLog) Board.debugLog('system.init', {
        prevSid: prevSid || null,
        newSid: data.session_id,
        isNewSession: isNewSession,
        termStatusBefore: Board.state.termStatus,
      });
      if (prevSid && String(prevSid) !== String(data.session_id)) {
        _ctx.clearOutput();
        _resetSessionDerivedState();
        var termModSwap = Board._term;
        if (termModSwap && typeof termModSwap.loadHistory === "function") {
          termModSwap.loadHistory(data.session_id);
        }
      }
      Board.state.termSessionId = data.session_id;
      // The SDK reissues system init for every user query (session_id is the same).
      // Therefore, idle is forced only when init arrives = "Start session or swap" in the same session.
      // When making a new turn, the status is preserved (maintained busy). Previously unconditionally idle was forced to be busy
      // A regression occurs where the next user input is incorrectly released into the idle branch.
      if (isNewSession) {
        Board.state.setTermStatus("idle");
      }
      if (data.raw && data.raw.model) {
        _applyRawModel(data.raw.model);
      }
      if (data.raw && data.raw.permissionMode) {
        var modeEl = document.getElementById("terminal-sl-mode");
        if (modeEl) modeEl.textContent = data.raw.permissionMode;
      }
      // setInputLocked / updateControlBar also only when in a new session. Same session on new turn
      // Because commitQueue already called setInputLocked(true) + updateControlBar
      // Here, if set to false, the input lock is released immediately while busy.
      if (isNewSession) {
        _ctx.setInputLocked(false);
        _ctx.updateControlBar();
      }
    } else if (data.subtype === "user_input_interrupted") {
      // A live signal indicating that the last user message has been stopped by an ESC interrupt.
      // timestamp matching .term-user or the most recent .term-user in outputDiv
      // Give it the .interrupted class to display a visual marker (a "stopped" badge).
      var ts = data.timestamp || "";
      var userMsgs = document.querySelectorAll(".terminal-output .term-user");
      var target = null;
      if (ts) {
        for (var ui = userMsgs.length - 1; ui >= 0; ui--) {
          if (userMsgs[ui].getAttribute("data-timestamp") === ts) {
            target = userMsgs[ui];
            break;
          }
        }
      }
      if (!target && userMsgs.length > 0) {
        target = userMsgs[userMsgs.length - 1];
        // Even if timestamp matching fails, the last user will soon stop the message at the time of live.
        if (ts) target.setAttribute("data-timestamp", ts);
      }
      if (target) target.classList.add("interrupted");
    } else if (data.subtype === "process_exit") {
      if (Board.debugLog) Board.debugLog('processExit.entry', {
        exitCode: data.exit_code,
        termStatusBefore: Board.state.termStatus,
        sessionId: data.session_id || null,
      });
      var wasActive = Board.state.termStatus === "busy" ||
                      Board.state.termStatus === "starting";
      if (wasActive) {
        _ctx.setReceivedChunks(false);
        _ctx.resetToolInputBuffer();
        _pendingTextBuffer = "";
        _ctx.flushTextBuffer();
        _currentToolUseId = null;
        _toolInputMap = {};
      }
      // [ESC Preservation Guard] termSessionId and clearOutput/ in process_exit path
      // Do not call _resetSessionDerivedState. ESC interrupt (exitCode 130)
      // Or normal completion (exitCode 0), SIGTERM (exitCode 143) both session ID and
      // The conversation DOM must be preserved. Even if the user refreshes the history
      // Since it must be restored, touching the session identifier in this path is a regression.
      // Session ID null processing is only performed in _finalizeStoppedUI of killSession().
      if (Board.debugLog) Board.debugLog('processExit.setStopped', {
        termStatusBefore: Board.state.termStatus,
      });
      Board.state.setTermStatus("stopped");
      // Tokens/costs are not intentionally reset. When a session is switched, the server terminates the old process.
      // When killing, process_exit comes first, and if you push it to 0 here, the following
      // The bar blinks to 0% while loadHistory fills with the new session's last_usage.
      // If the user explicitly kills it, _finalizeStoppedUI resets it separately.
      _ctx.stopSpinner();
      // process_exit can also be the end point of an interrupt response (e.g. exit without result).
      var termModExit = Board._term;
      if (termModExit && termModExit._interruptInFlight) termModExit._interruptInFlight = false;
      var exitCode = data.exit_code;
      // exitCode 0: Normal termination, 130: SIGINT (ESC interrupt), 143: SIGTERM — No error message required.
      // Only other codes are displayed as errors.
      if (exitCode !== 0 && exitCode !== 130 && exitCode !== 143 && exitCode !== undefined) {
        _ctx.appendErrorMessage("Process exited with code " + exitCode);
      }

      // [ESC automatic resume] Process_exit that arrives immediately after ESC is with the same session_id.
      // It respawns immediately so the user can immediately continue to the next message without the STOPPED screen.
      // Allow it to be sent.
      //
      // Trigger conditions:
      // - exitCode 130 (SIGINT directly) or
      // - _recentInterrupt flag (5 second window after entering interruptSession)
      //   → Covers even if the SDK receives SIGINT and returns a different exit_code through graceful shutdown.
      //
      // Workflow mode has its own life cycle, so it is not subject to automatic resume.
      var termMod3 = Board._term;
      var isRecentInterrupt = !!(termMod3 && termMod3._recentInterrupt);
      var isMainMode = !_ctx.isWorkflowMode || !_ctx.isWorkflowMode();
      // The ESC restoration text in localStorage is a persistent signal of "ESC sequence in progress".
      // Even if the memory flag (_recentInterrupt) is initialized by refreshing, this signal
      // You can trigger automatic resume. When a user specifies Kill, killSession is
      // Because this key is cleared, automatic resume is not activated.
      var hasEscRestoreLS = false;
      try { hasEscRestoreLS = !!localStorage.getItem("board.term.lastSentText"); } catch (e) {}
      var willAutoResume = (exitCode === 130 || isRecentInterrupt || hasEscRestoreLS)
          && Board.state.termSessionId && isMainMode;
      if (Board.debugLog) Board.debugLog('processExit.autoResumeDecision', {
        exitCode: exitCode,
        isRecentInterrupt: isRecentInterrupt,
        hasEscRestoreLS: hasEscRestoreLS,
        sid: Board.state.termSessionId || null,
        isMainMode: !!isMainMode,
        willAutoResume: !!willAutoResume,
      });
      // In the willAutoResume branch, turn on the _inAutoResume flag.
      // While this flag is on, the inputtable verdict of setInputLocked is
      // Stopped/starting is also treated as allowed → input.disabled is not maintained → blinks 0.
      // Turn off startSession.setIdle upon arrival.
      if (willAutoResume) {
        Board.state._inAutoResume = true;
      } else {
        _ctx.setInputLocked(false);
      }
      _ctx.updateControlBar();
      if (willAutoResume) {
        var sidToResume = Board.state.termSessionId;
        setTimeout(function () {
          // race guard: between user explicit actions (killSession,
          // If you do a session switch, etc.), give up automatic resume.
          if (Board.debugLog) Board.debugLog('processExit.autoResumeFire', {
            termStatus: Board.state.termStatus,
            sidNow: Board.state.termSessionId || null,
            sidToResume: sidToResume,
            willFire: Board.state.termStatus === "stopped"
              && Board.state.termSessionId === sidToResume,
          });
          if (Board.state.termStatus === "stopped"
              && Board.state.termSessionId === sidToResume) {
            startSession(sidToResume, { silent: true });
          }
        }, 50);
      }
    } else if (
      data.subtype === "task_started" ||
      data.subtype === "task_progress" ||
      data.subtype === "task_notification"
    ) {
      if (!_ctx || !_ctx.isWorkflowMode || !_ctx.isWorkflowMode()) return;

      var taskId = data.task_id || (data.tool_use_id || "");
      if (!taskId) return;

      if (data.subtype === "task_started") {
        _upsertTaskState(taskId, {
          description: data.description || "",
          status: "running",
          toolName: data.last_tool_name || "",
          startedAt: Date.now()
        });
        _scheduleTaskRender();
      } else if (data.subtype === "task_progress") {
        _upsertTaskState(taskId, {
          description: data.description || "",
          toolName: data.last_tool_name || ""
        });
        _scheduleTaskRender();
      } else if (data.subtype === "task_notification") {
        var taskFinalStatus = (data.status === "completed") ? "completed" : "error";
        _upsertTaskState(taskId, {
          status: taskFinalStatus,
          summary: data.summary || ""
        });
        _flushTaskRender();
      }
    }
  }

  /**
   * User_input event data processing.
   * Shared by SSE "user_input" listener and REST event injection.
   * @param {Object} data Parsed event data object
   */
  function _onUserInput(data) {
    if (!_ctx) return;
    if (!data.text) return;
    // When REST event injection (_isReplaying=true), _sentTexts is empty, so
    // Always render to DOM. When receiving SSE live, duplication of local transmission is prevented.
    // self-echo skip: Skip the entire text + attached card (already drawn in the direct echo path).
    if (!_isReplaying && _sentTexts.has(data.text)) {
      return;
    }
    var div = document.createElement("div");
    div.className = "term-message term-user";
    div.textContent = data.text;
    _ctx.appendToOutput(div);
    // T-429: Render attachments card (REST replay and multi-client SSE paths).
    // If it has already been drawn in the sendInput direct echo path, it is completely skipped by checking _sentTexts above.
    if (data.attachments && data.attachments.length > 0) {
      var termMod = Board && Board._term;
      if (termMod && termMod.attachmentCard && typeof termMod.attachmentCard.create === "function") {
        var attachContainer = document.createElement("div");
        attachContainer.className = "term-message-attachments";
        data.attachments.forEach(function (att) {
          attachContainer.appendChild(termMod.attachmentCard.create(att));
        });
        _ctx.appendToOutput(attachContainer);
      }
    }
  }

  /**
   * REST The event array received from /terminal/workflow/history is sequentially injected into the DOM.
   *
   * - Set _isReplaying = true to block live-only paths such as FSM transition and rate_limit banner.
   * - After completion, restore _isReplaying = false and perform final render of the timeline.
   * - In case of error/404, console.error is recorded and resolved (SSE subscription continues).
   *
   * @param {string} sessionId Workflow session ID
   * @returns {Promise<void>}
   */
  function _injectRestHistory(sessionId) {
    if (!sessionId) return Promise.resolve();
    var url = "/terminal/workflow/history?session_id=" + encodeURIComponent(sessionId);
    return fetch(url, { cache: "no-store" }).then(function (res) {
      if (!res.ok) {
        console.error("[session] REST history fetch failed: HTTP " + res.status + " for session " + sessionId);
        return;
      }
      return res.json().then(function (payload) {
        var events = Array.isArray(payload && payload.events) ? payload.events : [];
        if (!events.length) return;

        // Enable replay flag: Block live-only paths such as FSM transition and rate_limit banner
        _isReplaying = true;
        try {
          for (var i = 0; i < events.length; i++) {
            var evt = events[i];
            var eventType = evt.event || "";
            var dataObj = evt.data;
            // If data is a string, parse is attempted (supports jsonl format diversity)
            if (typeof dataObj === "string") {
              try { dataObj = JSON.parse(dataObj); } catch (e) { /* keep as string */ }
            }
            if (!dataObj || typeof dataObj !== "object") continue;
            try {
              if (eventType === "workflow_step") {
                _onWorkflowStep(dataObj);
              } else if (eventType === "stdout") {
                _onStdout(dataObj);
              } else if (eventType === "result") {
                _onResult(dataObj);
              } else if (eventType === "system") {
                _onSystem(dataObj);
              } else if (eventType === "user_input") {
                _onUserInput(dataObj);
              }
              // Live-only events such as skill_listing, permission, rate_limit, etc.
              // Do not render during _isReplaying (intentional skip).
            } catch (dispatchErr) {
              console.error("[session] REST history event dispatch error (seq=" + evt.seq + ", type=" + eventType + "):", dispatchErr);
            }
          }
        } finally {
          _isReplaying = false;
        }

        // Timeline final render after replay completion
        if (_ctx && _ctx.isWorkflowMode()) {
          try { Board.phaseTimeline.render(); } catch (e) {}
        }
        // Converge final UI status after completing REST replay (fetchStatus)
        try { fetchStatus(); } catch (fsErr) {}
        // Scroll to the bottom after refreshing (wait 2 frames compared to markdown/mermaid asynchronous render)
        var M = Board && Board._term;
        if (M && M.outputDiv) {
          requestAnimationFrame(function () {
            requestAnimationFrame(function () {
              if (M.outputDiv) M.outputDiv.scrollTop = M.outputDiv.scrollHeight;
            });
          });
        }
      });
    }).catch(function (err) {
      console.error("[session] REST history fetch error for session " + sessionId + ":", err);
      // _isReplaying ensures unlocking in case of error
      _isReplaying = false;
    });
  }

  // ── production-line session entry point ──

  /** @type {{close: function, sessionId: string}|null} Handle to the currently active production-line subscription */
  var _productionLineSubscription = null;

  /**
   * Starting/re-entering a production-line session.
   *
   * Directly register 4 types of SSE event handles with Board.productionLineWorkflow.subscribe (T-507 P3
   * Discard the old production-line-stdout-bridge.js bypass module → session.js (single absorption point).
   *
   *   workflow_step → Board.stepOverlay (Step/Phase hierarchy + termination processing)
   *   workflow_stdout → _onProductionLineStdout (text/raw branch render)
   *                     + Board.stepOverlay.handleStdout (Step/Phase not stdout container forward)
   *   workflow_phase  → Board.stepOverlay
   *   workflow_finish → Board.stepOverlay + Workflow completion UI
   *
   * Step/Phase hierarchical renders are handled as independent subscriptions by Board.stepOverlay.subscribe.
   * session.js handles stdout body + termStatus / controlBar life cycle
   * + Responsible for stepOverlay.handleStdout forward.
   *
   * @param {string} sessionId
   */
  function _startProductionLineWorkflowSession(sessionId) {
    if (!sessionId) return;

    // Clean up existing production-line subscriptions
    if (_productionLineSubscription) {
      try { _productionLineSubscription.close(); } catch (_) {}
      _productionLineSubscription = null;
    }

    // Subscription by Step/Phase hierarchy — stepOverlay maintains its own _stepMap machine
    if (Board.stepOverlay && typeof Board.stepOverlay.subscribe === "function") {
      try { Board.stepOverlay.subscribe(sessionId); } catch (_) {}
    }

    // T-508 — Restore step/phase ts first (before fetchSession) with localStorage fallback.
    // Immediately after refreshing and before the backend GET response arrives, the first render blinks as 0 elapsed.
    // Regression blocking. When a fetchSession response arrives, overwrite it with a newer ts (guard built-in).
    if (Board.WorkflowRenderer && Board.WorkflowRenderer.restoreProductionLineState) {
      try { Board.WorkflowRenderer.restoreProductionLineState(); } catch (_) {}
    }

    // 1) Detailed fetch — Restore step/phase at the point of entry (idempotent)
    if (Board.productionLineWorkflow && Board.productionLineWorkflow.fetchSession) {
      Board.productionLineWorkflow.fetchSession(sessionId).then(function (detail) {
        if (!detail) return;
        if (Board.WorkflowRenderer && Board.WorkflowRenderer.handleProductionLineStepEvent) {
          // T-508 — Specify cycle_start_ts / step_ts of backend response in payload.
          // workflow-bar.js handleProductionLineStepEvent absorbs ts into _state.stepTimestamps
          // Setting start to external ts (blocking Date.now() fallback).
          Board.WorkflowRenderer.handleProductionLineStepEvent({
            session_id: detail.session_id,
            step: detail.current_step,
            phase: detail.current_phase,
            prev_step: "",
            cycle_start_ts: detail.cycle_start_ts,
            step_ts: detail.step_ts,
          });
        }
        if (Board.phaseTimeline && Board.phaseTimeline.render) {
          try { Board.phaseTimeline.render(); } catch (_) {}
        }
      });
    }

    // 2) SSE Subscription
    if (!Board.productionLineWorkflow || !Board.productionLineWorkflow.subscribe) {
      _ctx.appendErrorMessage(
        "[Error] Board.productionLineWorkflow not loaded — terminal.html script missing. Need to check"
      );
      return;
    }

    _productionLineSubscription = Board.productionLineWorkflow.subscribe(sessionId, {
      onOpen: function () {
        Board.state.termConnected = true;
        Board.state.setTermStatus("running");
        _ctx.updateControlBar();
      },
      onStep: function (data) {
        // Step/Phase hierarchy updates are handled by Board.stepOverlay as a star subscription.
        // session.js idempotently re-render only the timeline-bar.
        if (Board.phaseTimeline && Board.phaseTimeline.render) {
          try { Board.phaseTimeline.render(); } catch (_) {}
        }
      },
      onStdout: function (data) {
        _onProductionLineStdout(data);
        // T-507 P3 — Absorbs forward responsibility of old production-line-stdout-bridge.js.
        // step-overlay renders to the stdout container of the currently active Step/Phase.
        if (Board.stepOverlay && typeof Board.stepOverlay.handleStdout === "function") {
          try { Board.stepOverlay.handleStdout(data); } catch (err) {
            if (Board.debugLog) Board.debugLog("production_line.stdout.forward.error", {
              sessionId: sessionId, message: err && err.message
            });
          }
        }
      },
      onPhase: function (data) {
        if (Board.phaseTimeline && Board.phaseTimeline.render) {
          try { Board.phaseTimeline.render(); } catch (_) {}
        }
      },
      onFinish: function (data) {
        if (Board.phaseTimeline && Board.phaseTimeline.renderStatusBadge) {
          Board.phaseTimeline.renderStatusBadge(
            data && data.outcome === "ok" ? "ok" : "fail",
            data && data.summary
          );
        }
        if (Board.phaseTimeline && Board.phaseTimeline.stopTimer) {
          try { Board.phaseTimeline.stopTimer(); } catch (_) {}
        }
        Board.state.setTermStatus("idle");
        _ctx.updateControlBar();
      },
      onError: function (err) {
        Board.state.termConnected = false;
        _ctx.updateControlBar();
        if (Board.debugLog) Board.debugLog("production_line.sse.error", {
          sessionId: sessionId,
          message: err && err.message,
        });
      },
    });
  }

  /**
   * Handling production-line workflow_stdout events (T-495 P3 — NDJSON branch render).
   * payload: { session_id, text, raw? }
   *
   * Branch by raw.type (visibility 8 axis #3):
   *   - assistant: content[] traversal → text block accumulation + tool_use block carding
   *   - tool_use: tool name + input 1-line summary card
   *   - result: subtype/duration_ms/usage/terminal_reason meta card
   *   - system: init meta (model/cwd/tools count) displayed once
   *   - rate_limit_event: warning marker
   *   - Other text only: stdout line accumulation
   *
   * 5 types of regression.pattern / When tool.deny flows into the stdout body
   * Immediate display of error/warning marker cards (auxiliary to visibility #4).
   *
   * @param {Object} data
   */
  function _onProductionLineStdout(data) {
    if (!data) return;
    var text = data.text || "";
    var raw = data.raw || null;

    if (!raw || typeof raw !== "object") {
      if (text) {
        _productionLineDetectAndMarkRegression(text);
        _productionLineAppendStdoutText(text);
      }
      return;
    }

    var rawType = raw.type || "";

    if (rawType === "assistant") {
      _productionLineRenderAssistant(raw, text);
    } else if (rawType === "tool_use") {
      _productionLineRenderToolUse(raw);
    } else if (rawType === "result") {
      _productionLineRenderResult(raw);
    } else if (rawType === "system") {
      _productionLineRenderSystemInit(raw);
    } else if (rawType === "rate_limit_event") {
      _productionLineRenderWarning("rate_limit", raw);
    } else if (text) {
      _productionLineDetectAndMarkRegression(text);
      _productionLineAppendStdoutText(text);
    }
  }

  /**
   * assistant NDJSON line render. By traversing content[], text blocks are accumulated,
   * The tool_use block is displayed as a card.
   */
  function _productionLineRenderAssistant(raw, textJoined) {
    var msg = raw && raw.message;
    var content = msg && Array.isArray(msg.content) ? msg.content : null;
    if (!content) {
      if (textJoined) _productionLineAppendStdoutText(textJoined);
      return;
    }
    for (var i = 0; i < content.length; i++) {
      var blk = content[i];
      if (!blk || typeof blk !== "object") continue;
      if (blk.type === "text" && blk.text) {
        _productionLineDetectAndMarkRegression(blk.text);
        _productionLineAppendStdoutText(blk.text);
      } else if (blk.type === "tool_use") {
        _productionLineRenderToolUse(blk);
      }
    }
  }

  /**
   * tool_use card render — name + input 1 line summary.
   * In the case of Bash, command, Read/Edit take precedence over file_path, and Grep takes precedence over pattern.
   */
  function _productionLineRenderToolUse(blk) {
    if (!blk) return;
    var name = blk.name || "tool";
    var input = blk.input || {};
    var summary = "";
    if (typeof input.command === "string") summary = input.command;
    else if (typeof input.file_path === "string") summary = input.file_path;
    else if (typeof input.pattern === "string") summary = input.pattern;
    else if (typeof input.prompt === "string") summary = input.prompt;
    else summary = JSON.stringify(input).slice(0, 140);

    if (summary.length > 220) summary = summary.slice(0, 217) + "…";

    if (Board.WorkflowRenderer && Board.WorkflowRenderer.insertToCurrentPanel) {
      try {
        var html = '<div class="wf-production-line-tool-use">'
          + '<span class="wf-production-line-tool-name">' + Board.util.esc(name) + '</span>'
          + '<span class="wf-production-line-tool-summary">' + Board.util.esc(summary) + '</span>'
          + '</div>';
        Board.WorkflowRenderer.insertToCurrentPanel(html);
      } catch (_) {}
    }
  }

  /**
   * result NDJSON card — subtype + duration_ms + usage(in/out) + terminal_reason.
   */
  function _productionLineRenderResult(raw) {
    if (!Board.WorkflowRenderer || !Board.WorkflowRenderer.insertToCurrentPanel) return;
    var subtype = raw.subtype || "";
    var parts = [];
    if (subtype) parts.push(subtype);
    if (raw.duration_ms != null) parts.push(raw.duration_ms + "ms");
    if (raw.usage && typeof raw.usage === "object") {
      var u = raw.usage;
      var inTok = u.input_tokens != null ? u.input_tokens : null;
      var outTok = u.output_tokens != null ? u.output_tokens : null;
      if (inTok != null || outTok != null) {
        parts.push("in=" + (inTok || 0) + " out=" + (outTok || 0));
      }
    }
    if (raw.terminal_reason) parts.push(raw.terminal_reason);
    var statusClass = subtype === "success" ? "ok" : "fail";
    try {
      Board.WorkflowRenderer.insertToCurrentPanel(
        '<div class="wf-production-line-result-meta" data-status="' + Board.util.esc(statusClass) + '">'
          + '<span class="wf-production-line-result-label">[result]</span> '
          + Board.util.esc(parts.join(" · "))
          + '</div>'
      );
    } catch (_) {}
  }

  /** system init one-line summary card — model/cwd/tools count. */
  function _productionLineRenderSystemInit(raw) {
    if (raw.subtype !== "init") return;
    if (!Board.WorkflowRenderer || !Board.WorkflowRenderer.insertToCurrentPanel) return;
    var pieces = [];
    if (raw.model) pieces.push("model=" + raw.model);
    if (raw.cwd) pieces.push("cwd=" + (raw.cwd.split("/").slice(-2).join("/") || raw.cwd));
    if (Array.isArray(raw.tools)) pieces.push("tools=" + raw.tools.length);
    try {
      Board.WorkflowRenderer.insertToCurrentPanel(
        '<div class="wf-production-line-system-init">'
          + '<span class="wf-production-line-system-label">[init]</span> '
          + Board.util.esc(pieces.join(" · "))
          + '</div>'
      );
    } catch (_) {}
  }

  /** Stream-level warning markers such as rate_limit. */
  function _productionLineRenderWarning(kind, raw) {
    if (!Board.WorkflowRenderer || !Board.WorkflowRenderer.insertToCurrentPanel) return;
    var summary = "";
    try { summary = JSON.stringify(raw).slice(0, 200); } catch (_) {}
    try {
      Board.WorkflowRenderer.insertToCurrentPanel(
        '<div class="wf-production-line-warning" data-kind="' + Board.util.esc(kind) + '">'
          + '<span class="wf-production-line-warning-label">[' + Board.util.esc(kind) + ']</span> '
          + Board.util.esc(summary)
          + '</div>'
      );
    } catch (_) {}
  }

  /**
   * 5 types of regression.pattern / tool.deny / hook deny keywords are immediately detected in stdout text.
   * When found, an error/warning marker card is added to the step card.
   * 5 types = worker_false_success / hook_deny / empty_bash_card /
   *       stage_header_leak / worktree_commit_missing
   */
  var PRODUCTION_LINE_REGRESSION_PATTERNS = [
    { re: /worker_false_success/i,      label: "worker_false_success" },
    { re: /hook_deny|hookSpecificOutput.*deny/i, label: "hook_deny" },
    { re: /empty_bash_card/i,           label: "empty_bash_card" },
    { re: /stage_header_leak/i,         label: "stage_header_leak" },
    { re: /worktree_commit_missing/i,   label: "worktree_commit_missing" },
    { re: /\btool\.deny\b/i,            label: "tool.deny" }
  ];

  function _productionLineDetectAndMarkRegression(text) {
    if (!text || !Board.WorkflowRenderer
        || !Board.WorkflowRenderer.insertToCurrentPanel) return;
    for (var i = 0; i < PRODUCTION_LINE_REGRESSION_PATTERNS.length; i++) {
      var p = PRODUCTION_LINE_REGRESSION_PATTERNS[i];
      if (p.re.test(text)) {
        try {
          Board.WorkflowRenderer.insertToCurrentPanel(
            '<div class="wf-production-line-regression" data-pattern="' + Board.util.esc(p.label) + '">'
              + '<span class="wf-production-line-regression-label">[regression]</span> '
              + Board.util.esc(p.label)
              + '</div>'
          );
        } catch (_) {}
        break;
      }
    }
  }

  /**
   * Appends stdout text to the body of the currently active step card.
   */
  function _productionLineAppendStdoutText(text) {
    if (!text) return;
    if (Board.WorkflowRenderer && Board.WorkflowRenderer.insertToCurrentPanel) {
      try {
        var html = '<div class="wf-production-line-stdout-line">'
          + Board.util.esc(text) + '</div>';
        Board.WorkflowRenderer.insertToCurrentPanel(html);
      } catch (_) {}
    }
  }

  /**
   * Explicitly terminates a production-line subscription (called when a session is switched).
   * Independent subscriptions to Board.stepOverlay are also organized.
   */
  function _disconnectProductionLine() {
    if (_productionLineSubscription) {
      try { _productionLineSubscription.close(); } catch (_) {}
      _productionLineSubscription = null;
    }
    if (Board.stepOverlay && typeof Board.stepOverlay.disconnect === "function") {
      try { Board.stepOverlay.disconnect(); } catch (_) {}
    }
  }

  // ── SSE Connection ──

  function connectSSEReady() {
    return new Promise(function (resolve, reject) {
      if (
        termEventSource &&
        termEventSource.readyState === EventSource.OPEN
      ) {
        resolve();
        return;
      }

      var timer = setTimeout(function () {
        reject(new Error("SSE connection timeout"));
      }, 5000);

      connectSSE();

      var source = termEventSource;
      if (!source) {
        clearTimeout(timer);
        reject(new Error("SSE source not created"));
        return;
      }

      if (source.readyState === EventSource.OPEN) {
        clearTimeout(timer);
        resolve();
        return;
      }

      function onOpen() {
        clearTimeout(timer);
        source.removeEventListener("open", onOpen);
        resolve();
      }

      function onError() {
        clearTimeout(timer);
        source.removeEventListener("open", onOpen);
        source.removeEventListener("error", onError);
        reject(new Error("SSE connection failed"));
      }

      source.addEventListener("open", onOpen);
      source.addEventListener("error", onError);
    });
  }

  function connectSSE() {
    if (!_ctx) return;
    disconnectSSE();

    // Tokens/costs are accumulated because they are overwritten with set meaning when receiving an assistant event.
    // There is no risk. Resetting on every reconnect will result in an empty SSE gap or gap-fill response.
    // When it is late, the status is fixed at 0 and is not reset. Session switch/restart/
    // Each process_exit path already calls resetTokens.

    // Clear sent-text tracking so that history-replayed user_input events
    // are rendered into the DOM (they are not duplicates).
    _sentTexts.clear();

    // Reset parallel-tool tracking state on reconnect
    _currentToolUseId = null;
    _toolInputMap = {};

    // Reset pending text buffer and replay flag on reconnect
    _pendingTextBuffer = "";
    _isReplaying = false;

    // Resume from last received event id to prevent full-history replay on reconnect
    var eventsUrl = _ctx.endpoints().events;
    var qsSep = function () { return eventsUrl.indexOf("?") >= 0 ? "&" : "?"; };
    var termMod = Board._term;
    if (_lastEventId >= 0) {
      eventsUrl += qsSep() + "last_event_id=" + _lastEventId;
      // Because SSE ring buffer playback may not include the most recent assistant events,
      // Rehydrate the latest usage/cost with REST (even if there is an empty gap, the server is currently
      // returns the total).
      if (!_ctx.isWorkflowMode() && termMod && termMod._historyLoaded &&
          typeof termMod.fetchHistorySince === "function") {
        termMod.fetchHistorySince(Board.state.termSessionId);
      }
    } else if (!_ctx.isWorkflowMode()) {
      // Main session: REST /terminal/history is the authoritative source for the past, so
      // SSE ring buffer playback is omitted. The server does not even send replay_start/end frames.
      eventsUrl += qsSep() + "skip_replay=1";
      // If reconnected (already loaded once), the gap is filled with REST.
      if (termMod && termMod._historyLoaded && typeof termMod.fetchHistorySince === "function") {
        termMod.fetchHistorySince(Board.state.termSessionId);
      }
    } else {
      // Workflow session: initial events are restored to REST /terminal/workflow/history so
      // SSE ring buffer playback is always skipped. Specify skip_replay=1 to set the server-side replay path.
      // Deactivate.
      eventsUrl += qsSep() + "skip_replay=1";
    }
    termEventSource = new EventSource(eventsUrl);

    termEventSource.addEventListener("archived_end", function (e) {
      _captureEventId(e);
      _sessionArchived = true;
      Board.state.setTermStatus("archived");
      Board.state.termConnected = false;
      _ctx.updateControlBar();
      if (termEventSource) {
        termEventSource.close();
        termEventSource = null;
      }
    });

    // T-497: replay_start / replay_end SSE listener fires 0 servers + REST
    // Abolished by unification decision. _isReplaying SSOT is _injectRestHistory driver
    // (REST /terminal/workflow/history path). board.md See §1.1.

    // T-383 Phase 5 (T5-1, T5-3): Skip workflow_step during replay.
    // Principle (T-379 Phase 2): workflow_step SSE is the only path for FSM transition.
    // This gate does not violate this principle — "It's not time to transition yet"
    // It is interpreted as During replay, DOM reconstruction ( rebuildStepPanelsFromDom ) occurs.
    // _restoreSession is performed on the path, so the UI state converges to another path,
    // The final FSM status is corrected with fetchStatus() immediately after _injectRestHistory finally.
    // _captureEventId is always called even during replay and returns from-id when reconnecting.
    // Guaranteed (if omitted, history duplicate playback bug may reoccur).
    termEventSource.addEventListener("workflow_step", function (e) {
      _captureEventId(e);
      try {
        var data = JSON.parse(e.data);
        _onWorkflowStep(data);
      } catch (err) {}
    });

    termEventSource.addEventListener("open", function () {
      Board.state.termConnected = true;
      _ctx.updateControlBar();
    });

    termEventSource.addEventListener("stdout", function (e) {
      _captureEventId(e);
      try {
        var data = JSON.parse(e.data);
        _onStdout(data);
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("result", function (e) {
      _captureEventId(e);
      try {
        var data = JSON.parse(e.data);
        _onResult(data);
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("system", function (e) {
      _captureEventId(e);
      try {
        var data = JSON.parse(e.data);
        _onSystem(data);
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("permission", function (e) {
      _captureEventId(e);
      try {
        var data = JSON.parse(e.data);
        var requestId = data.request_id || "";
        var toolName = data.tool_name || "";
        var description = data.description || (data.raw && data.raw.request && data.raw.request.description) || "";

        // Build permission request DOM
        var div = document.createElement("div");
        div.className = "term-system term-permission";
        if (requestId) div.dataset.requestId = requestId;

        var labelSpan = document.createElement("span");
        labelSpan.className = "term-permission-label";
        labelSpan.textContent = "[Permission Request]";
        div.appendChild(labelSpan);

        if (toolName) {
          div.appendChild(document.createTextNode(" "));
          var toolSpan = document.createElement("span");
          toolSpan.className = "term-permission-tool";
          toolSpan.textContent = toolName;
          div.appendChild(toolSpan);
        }

        if (description) {
          var descDiv = document.createElement("div");
          descDiv.className = "term-permission-desc";
          descDiv.textContent = description;
          div.appendChild(descDiv);
        }

        // Collapsible input parameters
        if (data.input && typeof data.input === "object" && Object.keys(data.input).length > 0) {
          var inputWrapDiv = document.createElement("div");
          inputWrapDiv.className = "term-permission-input";

          var inputToggleBtn = document.createElement("button");
          inputToggleBtn.className = "term-permission-input-toggle";
          inputToggleBtn.textContent = "▶ Show input parameters";

          var inputContentDiv = document.createElement("div");
          inputContentDiv.className = "term-permission-input-content";
          inputContentDiv.textContent = JSON.stringify(data.input, null, 2);

          inputToggleBtn.addEventListener("click", function () {
            var expanded = inputContentDiv.classList.toggle("expanded");
            inputToggleBtn.textContent = expanded ? "▼ Hide input parameters" : "▶ Show input parameters";
          });

          inputWrapDiv.appendChild(inputToggleBtn);
          inputWrapDiv.appendChild(inputContentDiv);
          div.appendChild(inputWrapDiv);
        }

        // Action buttons
        var actionsDiv = document.createElement("div");
        actionsDiv.className = "term-permission-actions";

        var allowBtn = document.createElement("button");
        allowBtn.className = "term-permission-btn allow";
        allowBtn.textContent = "Allow";

        var denyBtn = document.createElement("button");
        denyBtn.className = "term-permission-btn deny";
        denyBtn.textContent = "Deny";

        actionsDiv.appendChild(allowBtn);
        actionsDiv.appendChild(denyBtn);
        div.appendChild(actionsDiv);

        // Click handler helper
        function sendPermissionDecision(decision) {
          allowBtn.disabled = true;
          denyBtn.disabled = true;

          var body = { request_id: requestId, decision: decision };
          if (_ctx.isWorkflowMode()) {
            body.session_id = _ctx.getWorkflowSessionId();
          }

          postJson("/terminal/permission", body).then(function () {
            actionsDiv.classList.add("resolved");
            var resultDiv = document.createElement("div");
            resultDiv.className = "term-permission-result " + (decision === "allow" ? "allowed" : "denied");
            resultDiv.textContent = decision === "allow" ? "Allowed" : "Denied";
            actionsDiv.appendChild(resultDiv);
          }).catch(function (err) {
            var errDiv = document.createElement("div");
            errDiv.className = "term-permission-result denied";
            errDiv.textContent = "Error: " + (err.message || "Request failed");
            div.appendChild(errDiv);
            allowBtn.disabled = false;
            denyBtn.disabled = false;
          });
        }

        allowBtn.addEventListener("click", function () {
          sendPermissionDecision("allow");
        });

        denyBtn.addEventListener("click", function () {
          sendPermissionDecision("deny");
        });

        _ctx.appendToOutput(div);
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("skill_listing", function (e) {
      _captureEventId(e);
      try {
        var data = JSON.parse(e.data);
        var content = data.content || "";
        var skillCount = data.skillCount != null ? data.skillCount : 0;

        var div = document.createElement("div");
        div.className = "term-skill-listing";

        var labelSpan = document.createElement("span");
        labelSpan.className = "term-skill-label";
        labelSpan.textContent = "[Skills Loaded] " + skillCount + " skills";
        div.appendChild(labelSpan);

        if (content) {
          var details = document.createElement("details");
          details.className = "term-skill-details";

          var summary = document.createElement("summary");
          summary.className = "term-skill-summary";
          summary.textContent = "Show skill list";
          details.appendChild(summary);

          var lines = content.split("\n");
          for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (!line) continue;
            var itemDiv = document.createElement("div");
            itemDiv.className = "term-skill-item";
            itemDiv.textContent = line;
            details.appendChild(itemDiv);
          }

          div.appendChild(details);
        }

        _ctx.appendToOutput(div);
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("user_input", function (e) {
      _captureEventId(e);
      try {
        var data = JSON.parse(e.data);
        // SSE live reception path: _isReplaying=false, so _sentTexts duplication prevention works.
        _onUserInput(data);
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("error", function (e) {
      _captureEventId(e);
      try {
        var data = JSON.parse(e.data);
        if (data.exit_code === 143 || data.exit_code === 0) return;
        _ctx.stopSpinner();
        _ctx.appendErrorMessage("[Error] " + (data.message || "Process error"));
        Board.state.setTermStatus("stopped");
        _ctx.setInputLocked(false);
        _ctx.updateControlBar();
      } catch (err) {
        // Ignore non-JSON error events
      }
    });

    // T-389: Dedicated SSE listener for rate_limit_event in Claude CLI.
    // Implemented as an independent listener and separated from the existing stdout handler (L353) — TK-4 (T-390)
    // stdout refactor and physical conflict avoidance (T-386 research G-2 recommendation).
    // Server payload shape (terminal_channel._build_payload):
    //   { kind:"rate_limit", status, resets_at, rate_limit_type,
    //     is_using_overage, overage_status, session_id }
    termEventSource.addEventListener("rate_limit", function (e) {
      _captureEventId(e);
      try {
        var data = JSON.parse(e.data);
        var status = data.status || "unknown";
        var limitType = data.rate_limit_type || "";
        var resetsAt = (typeof data.resets_at === "number") ? data.resets_at : null;

        // During replay, DOM creation is skipped. The rate_limit at the time of restoration is in the past
        // Since it is a snapshot, incorrect information may be exposed if left in the current UI.
        // When receiving a live event, the banner is regenerated in the normal path.
        if (_isReplaying) return;

        // dedupe: If the same (status, limitType) banner is already floating, only timestamp is updated.
        if (_rateLimitBanner &&
            _rateLimitBanner.dataset.status === status &&
            _rateLimitBanner.dataset.limitType === limitType) {
          _updateRateLimitBannerDetail(_rateLimitBanner, limitType, resetsAt);
          return;
        }

        _dismissRateLimitBanner();

        var banner = _buildRateLimitBanner(status, limitType, resetsAt);
        _rateLimitBanner = banner;
        _ctx.appendToOutput(banner);

        // Automatic dismiss only for allowed (informational). warning / exceeded / unknown means user
        // Requires manual dismiss — ensures opportunity to confirm reset time.
        if (status === "allowed") {
          _rateLimitDismissTimer = setTimeout(_dismissRateLimitBanner, 5000);
        }
      } catch (err) {
        // Ignore non-JSON rate_limit events (same as existing listener, silent ignore)
      }
    });

    termEventSource.onerror = function () {
      Board.state.termConnected = false;
      if (termEventSource) {
        termEventSource.close();
        termEventSource = null;
      }
      _ctx.updateControlBar();

      if (_sessionArchived) {
        // Archived session: server closed stream after replay. Do not reconnect.
        return;
      }

      if (!reconnectTimerId) {
        reconnectTimerId = setTimeout(function () {
          reconnectTimerId = null;
          connectSSE();
        }, SSE_RECONNECT_INTERVAL);
      }
    };
  }

  function disconnectSSE() {
    if (reconnectTimerId) {
      clearTimeout(reconnectTimerId);
      reconnectTimerId = null;
    }
    if (termEventSource) {
      termEventSource.close();
      termEventSource = null;
    }
    // T-495 P2 — Production-line subscriptions are also organized (session switch race blocked)
    _disconnectProductionLine();
    Board.state.termConnected = false;
  }

  // ── Session Management ──

  // UUID v1~v5 loose type validation (36 characters including hyphens)
  var UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  /**
   * Upon session switch/restart, all accumulated derived state is initialized.
   * - Module scope: _pendingTextBuffer, _sentTexts, _currentToolUseId, _toolInputMap, _isReplaying
   * - M namespace: thinking spinner, tool-box mapping, toolInputBuffer, currentToolName, sessionTokens/Cost
   * - WorkflowRenderer reset (if present)
   * DOM output is handled separately by the caller with clearOutput.
   */
  function _resetSessionDerivedState() {
    _pendingTextBuffer = "";
    _sentTexts.clear();
    _currentToolUseId = null;
    _toolInputMap = {};
    _isReplaying = false;
    // T-389: Remove rate_limit banner/timer left over from previous session.
    _dismissRateLimitBanner();
    // T-390: task state map + rAF token initialization.
    _taskStatusMap = {};
    if (_taskRenderRafId !== 0) {
      cancelAnimationFrame(_taskRenderRafId);
      _taskRenderRafId = 0;
    }
    if (_ctx) {
      _ctx.setReceivedChunks && _ctx.setReceivedChunks(false);
    }
    // Token reset is context-dependent: in fresh start, startSession is specified.
    // Call _applyHistoryUsage of loadHistory in resume/session-switch
    // Overwritten with jsonl's last_usage. If you reset to 0 here, the bar will be 0%.
    // Flicker that blinks and then fills — intentionally excluded.
    var termMod = Board._term;
    if (termMod) {
      termMod.stopSpinner && termMod.stopSpinner();
      termMod.currentToolBox = null;
      termMod.toolBoxMap = {};
      termMod.currentToolName = null;
      termMod.toolInputBuffer = "";
      termMod._historyLoaded = false;
      termMod._historyLastTimestamp = "";
    }
    if (Board.WorkflowRenderer && Board.WorkflowRenderer.reset) {
      Board.WorkflowRenderer.reset();
    }
  }

  function startSession(resumeSessionId, opts) {
    if (!_ctx) return;
    // Avoid duplicate requests: ignore additional clicks until spawn response.
    if (_startInFlight) return;
    var isResume = !!resumeSessionId;
    // silent: Only for paths that require “Preserve user-visible conversations” such as ESC automatic resume.
    // - Skip clearOutput / loadHistory (prevent DOM duplication/flicker).
    // - Only termSessionId is guaranteed to be set, token/SSE reconnection/spawn flow is the same.
    var silent = !!(opts && opts.silent);
    var termModStart = Board._term;
    if (isResume && termModStart && termModStart.hasCapability && !termModStart.hasCapability("resume")) {
      _ctx.appendErrorMessage("[Error] Current provider does not support session resume");
      return;
    }

    // Preemptive UUID verification: If the resume request is not in UUID format, it immediately fails instead of server fallback.
    if (isResume && !UUID_RE.test(String(resumeSessionId))) {
      _ctx.appendErrorMessage("[Error] Invalid session ID format:" + String(resumeSessionId).substring(0, 16));
      return;
    }

    // If there is already an active session, it is considered a session switch and the connection is reset.
    // Because the server's claude_process.spawn() internally kills existing processes,
    // There is no need to call HTTP kill separately.
    if (Board.state.termStatus !== "stopped") {
      disconnectSSE();
      Board.state.setTermStatus("stopped");
      Board.state.termSessionId = null;
      _ctx.updateControlBar();
    }

    // When starting a new session (isResume=false), termSessionId is explicitly cleared.
    // If you press Start in the stopped state, fetchStatus is already set to null, but
    // Defensively, it is also cleared here to completely block the "Session Replacement" condition in system/init.
    // The isResume path is explicitly set as resumeSessionId near Line 966 below.
    if (!isResume) {
      Board.state.termSessionId = null;
    }

    // Full reset of derived state — tool-box mappings/text buffers from previous session
    // Avoid mixing in new session event processing.
    _resetSessionDerivedState();

    // Since fresh start is a new conversation, we explicitly reset the token to 0.
    // resume is loadHistory's _applyHistoryUsage(force=true) of the previous session.
    // I'm restoring the accumulated token from jsonl so I don't reset it here — otherwise
    // A flicker occurs where the bar blinks to 0 and then fills with a new value.
    if (!isResume) {
      _ctx.resetTokens && _ctx.resetTokens();
    }

    // Since a new session start (or resume) is the start of a new event stream,
    // The last-event-id of the previous channel is meaningless.
    _lastEventId = -1;
    _sessionArchived = false;

    if (_ctx.isWorkflowMode()) {
      _ctx.clearOutput();
      var wfSessionId = _ctx.getWorkflowSessionId && _ctx.getWorkflowSessionId();

      // T-495 P2 — For production-line sessions, use a single entry point: Board.productionLineWorkflow.subscribe.
      // Separated from v1's /terminal/workflow/history + /terminal/workflow/events flow.
      if (Board.productionLineWorkflow && Board.productionLineWorkflow.isProductionLineSessionId &&
          Board.productionLineWorkflow.isProductionLineSessionId(wfSessionId)) {
        _startProductionLineWorkflowSession(wfSessionId);
        return;
      }

      // Workflow session initial load (v1):
      // 1) Inject all past events into the DOM with REST /terminal/workflow/history.
      //    (Ringbuffer alternate path — processed in order under _isReplaying=true guard)
      // 2) After completing REST (regardless of success or failure), start subscribing to SSE.
      //    Because skip_replay=1 is given to the SSE URL, ring buffer playback does not occur.
      // 3) If REST fails, console.error is logged and SSE subscription continues (silent fallback).
      _injectRestHistory(wfSessionId).then(function () {
        return connectSSEReady();
      }).catch(function (err) {
        _ctx.appendErrorMessage("[Error] SSE connect failed: " + err.message);
      });
      return;
    }

    if (silent) {
      // silent resume (ESC automatic return): DOM preservation is key.
      // Both clearOutput and loadHistory are skipped and only termSessionId is guaranteed.
      // The conversation on the screen remains the same as before the interrupt, and returns to idle after the spawn response.
      // Once converted, the user can immediately send the next message.
      if (isResume) {
        Board.state.termSessionId = resumeSessionId;
      }
    } else {
      _ctx.clearOutput();
      if (isResume) {
        // Load past conversations into the UI immediately (without waiting for Claude CLI spawn response).
        // spawn runs in the background, and resume may take more than 10 seconds in a large session.
        // Therefore, fill in REST /terminal/history first for user experience UX.
        // Caution: If the server gracefully falls back, the actual session_id will be returned in the init event.
        // otherwise arrives, then reloads the past conversation (see system/init listener).
        Board.state.termSessionId = resumeSessionId;
        var termModResume = Board._term;
        if (termModResume && typeof termModResume.loadHistory === "function") {
          termModResume.loadHistory(resumeSessionId);
        }
      }
    }

    // "starting" until the spawn request ~ init event is received. Input is still inactive.
    if (Board.debugLog) Board.debugLog('startSession.setStarting', {
      isResume: !!isResume,
      silent: !!silent,
      termStatusBefore: Board.state.termStatus,
    });
    Board.state.setTermStatus("starting");
    _ctx.updateControlBar();

    _startInFlight = true;
    connectSSEReady().then(function () {
      var startBody = isResume ? { resume_session_id: resumeSessionId } : undefined;
      return postJson("/terminal/start", startBody);
    }).then(function (data) {
      // spawn response = process ready. claude -p until the first stdin input
      // Since system/init does not emit events, here instead of waiting for init
      // Transitions to idle. Immediately activates the input window/button.
      // The spinner is turned on in the sendInput route when Claude actually starts responding.
      if (data && data.session_id) {
        Board.state.termSessionId = data.session_id;
      }
      if (Board.debugLog) Board.debugLog('startSession.setIdle', {
        termStatusBefore: Board.state.termStatus,
        inAutoResume: !!Board.state._inAutoResume,
      });
      var wasInAutoResume = !!Board.state._inAutoResume;
      Board.state.setTermStatus("idle");
      // ESC autoResume Shut down window — Release flag because normal idle has been reached.
      Board.state._inAutoResume = false;
      _ctx.setInputLocked(false);
      _ctx.updateControlBar();
      // [ESC race guard follow-up] _onResult's advanceTurn is _recentInterrupt in window
      // Since it is skipped, the remaining queue is processed when the new process spawn is completed (setIdle).
      // Fires only if wasInAutoResume=true — the normal new start flow requires the user to send
      // Queuing explicitly.
      if (wasInAutoResume) {
        var termModResume = Board._term;
        var queueSize = (termModResume && termModResume.inputQueue)
          ? termModResume.inputQueue.length : 0;
        if (Board.debugLog) Board.debugLog('startSession.setIdle.advanceTurnAfterResume', {
          queueSize: queueSize,
          hasAdvance: !!(termModResume && typeof termModResume.advanceTurn === 'function'),
        });
        if (termModResume && typeof termModResume.advanceTurn === 'function') {
          termModResume.advanceTurn();
        }
      }
    }).catch(function (err) {
      var reason = err && err.message ? err.message : "unknown error";
      var prefix = isResume ? "[Error] Session resumption failed" : "[Error] Failed to start session";
      _ctx.appendErrorMessage(prefix + ": " + reason);
      // Prevent _inAutoResume leak when autoResume fails.
      Board.state._inAutoResume = false;
      Board.state.setTermStatus("stopped");
      _ctx.updateControlBar();
    }).then(function () {
      _startInFlight = false;
    }, function () {
      _startInFlight = false;
    });
  }

  // Flag to prevent duplicate kill calls
  var _killingInProgress = false;

  function killSession() {
    if (!_ctx) return;
    var killable = Board.util.TERM_STATUS_KILLABLE;
    if (!killable.has(Board.state.termStatus)) return;
    // Avoid duplicate kill requests
    if (_killingInProgress) return;
    _killingInProgress = true;

    // User specified Kill = ESC Ends automatic resume sequence. Restore text in localStorage
    // Clear the signal so that the process_exit handler does not automatically resume.
    try { localStorage.removeItem("board.term.lastSentText"); } catch (e) {}
    var termModK = Board._term;
    if (termModK) termModK._recentInterrupt = false;

    var prevStatus = Board.state.termStatus;
    var epK = _ctx.endpoints();
    // Clean up the UI when closing — Perform the same reset as the process_exit path
    // Prevents dialogs/tokens/costs/spinners from being awkwardly left in the stopped state.
    function _finalizeStoppedUI() {
      _ctx.stopSpinner();
      _ctx.clearOutput();
      _ctx.resetTokens();
      _ctx.setSessionCost(0);
      _ctx.setSessionModel("--");
      _ctx.setReceivedChunks(false);
      _ctx.resetToolInputBuffer();
      _pendingTextBuffer = "";
      _currentToolUseId = null;
      _toolInputMap = {};
      if (_ctx.resetToolBoxMap) _ctx.resetToolBoxMap();
      _ctx.clearCurrentToolBox();
      if (_ctx.clearCurrentWorkflowToolCard) _ctx.clearCurrentWorkflowToolCard();
      // Permission mode indication is directly controlled by the DOM (no state storage such as setSessionModel)
      var modeEl = document.getElementById("terminal-sl-mode");
      if (modeEl) modeEl.textContent = "";
      Board.state.termSessionId = null;
    }
    // User-specified kill → autoResume immediately releases the window (prevents residual flags).
    Board.state._inAutoResume = false;
    postJson(epK.kill, epK.inputBody({})).then(function () {
      Board.state.setTermStatus("stopped");
      _ctx.setInputLocked(false);
      _finalizeStoppedUI();
      _ctx.updateControlBar();
      // Clean up SSE connection after successful kill: prevent residual events from reversing state
      disconnectSSE();
    }).catch(function (err) {
      // 409: If the process has already ended → recover to stopped
      var is409 = err.message && err.message.indexOf("409") !== -1;
      if (is409) {
        Board.state.setTermStatus("stopped");
        _ctx.setInputLocked(false);
        _finalizeStoppedUI();
        _ctx.updateControlBar();
        disconnectSSE();
      } else {
        // Other errors: Restore to previous state to prevent button sticking
        _ctx.appendErrorMessage("[Error] Failed to kill session: " + err.message);
        Board.state.setTermStatus(prevStatus);
        _ctx.setInputLocked(false);
        _ctx.updateControlBar();
      }
    }).finally(function () {
      _killingInProgress = false;
    });
  }

  /**
   * SSE reconnection for session switching.
   * The order of disconnectSSE() → connectSSE() → fetchStatus() is guaranteed.
   * Same as calling switchSession() directly inside, but also outside
   * You can use "Reconnect only" when you explicitly want to.
   *
   * @returns {Promise<void>}
   */
  function reconnectSSE() {
    if (!_ctx) return Promise.resolve();
    disconnectSSE();
    connectSSE();
    return fetchStatus();
  }

  /**
   * Record a text that was just sent via sendInput().
   * When the corresponding user_input SSE event arrives, the handler
   * will skip DOM insertion to avoid duplicates.
   *
   * No semantic change in 1:1 turn model:
   * - Call markSent in the sendInput path immediately after commitQueue echoes 1 entry
   * - If SSE user_input echo returns, skip it because it is the text registered in _sentTexts.
   * - Prevents duplicate insertion of speech bubbles already exposed to the DOM
   * - During history replay(_isReplaying=true), _sentTexts is empty, so
   *   All user_input events are rendered normally (refresh restoration path guaranteed)
   *
   * @param {string} text
   */
  function markSent(text) {
    if (text) _sentTexts.add(text);
  }

  /**
   * Reset last-event-id tracker. Call when switching to a different session
   * or starting a fresh session so that history replay starts from the
   * beginning of the new channel instead of carrying over an unrelated id.
   */
  function resetLastEventId() {
    _lastEventId = -1;
    _lastEventIdBySession = {};
    _sessionArchived = false;
  }

  /**
   * Switch the active last-event-id tracker to a specific session.
   * Used by switchSession() so tab round-trips resume from the last
   * seen event instead of replaying full history.
   * @param {string} sessionId
   */
  function adoptLastEventIdForSession(sessionId) {
    var key = sessionId || "main";
    if (key in _lastEventIdBySession) {
      _lastEventId = _lastEventIdBySession[key];
    } else {
      _lastEventId = -1;
    }
    _sessionArchived = false;
  }

  /**
   * When reconnecting/restoring history, add the in-flight tool_use block to the live input_json_delta path.
   * Seed function for reconnecting. tool_use with renderHistory in_flight=true
   * Called when an event is encountered.
   *
   * 1:1 turn simplified regression verification:
   * - Even after discarding turn-card grouping (W02), tool_use routing is done as a direct child of outputDiv.
   *   This has no effect on the seeding behavior of this function, as it is maintained.
   * - In the 1 turn = 1 message model, the in-flight tool exists only within a single turn.
   *   No change in probability of parallel tool_use conflicts.
   *
   * @param {string} toolUseId
   * @param {string} partialJson input_json fragment already received (can be an empty string)
   */
  function seedInFlightToolUse(toolUseId, partialJson) {
    if (!toolUseId) return;
    _currentToolUseId = toolUseId;
    _toolInputMap[toolUseId] = partialJson || "";
  }

  // ── Register on Board namespace ──
  Board.session = {
    connectSSE: connectSSE,
    connectSSEReady: connectSSEReady,
    disconnectSSE: disconnectSSE,
    reconnectSSE: reconnectSSE,
    startSession: startSession,
    killSession: killSession,
    fetchStatus: fetchStatus,
    postJson: postJson,
    resetLastEventId: resetLastEventId,
    adoptLastEventIdForSession: adoptLastEventIdForSession,
    seedInFlightToolUse: seedInFlightToolUse,
    injectRestHistory: _injectRestHistory,
    applyRawModel: _applyRawModel,
    // T-495 P2 — production-line session entry point (for external calls)
    startProductionLineSession: _startProductionLineWorkflowSession,
    disconnectProductionLine: _disconnectProductionLine,
    _bind: bind,
    _markSent: markSent
  };
})();
