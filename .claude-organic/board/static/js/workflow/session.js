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
  /** 세션 스위치/시작 중복 요청 방지 플래그. spawn 응답이 올 때까지 true. */
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

  function fetchStatus() {
    if (!_ctx) return Promise.resolve();
    return fetch(_ctx.endpoints().status, { cache: "no-store" }).then(function (res) {
      if (res.status === 404) {
        _sessionArchived = true;
        Board.state.setTermStatus("missing");
        Board.state.termConnected = false;
        _ctx.stopSpinner();
        _ctx.appendErrorMessage("[Error] 세션을 찾을 수 없습니다. 이미 종료되었거나 정리되었습니다.");
        _ctx.updateControlBar();
        return;
      }
      if (!res.ok) return;
      return res.json();
    }).then(function (data) {
      if (!data) return;
      if (data.archived) {
        _sessionArchived = true;
        Board.state.setTermStatus("archived");
      } else {
        // 서버 응답(stopped/running)과 클라 확장 상태(idle/busy/starting)를 병합.
        Board.state.reconcileTermStatus(data.status);
      }
      // stopped 상태에서 session_id 를 유지하면 서버가 .last-session-id 에서
      // 복원한 예전 UUID 가 남고, Start 후 첫 system/init 이벤트가 "세션 교체"
      // 로 오인되어 clearOutput 으로 방금 입력한 사용자 말풍선이 사라진다.
      // stopped 면 활성 sid 없음으로 간주하고 null 로 세팅한다.
      Board.state.termSessionId = (data.status === "stopped")
        ? null
        : (data.session_id || null);
      // last_session_id: W01 서버에서 추가된 필드 (이전/현재 세션 UUID)
      if (data.last_session_id) {
        Board.state.termLastSessionId = data.last_session_id;
      } else if (data.session_id) {
        Board.state.termLastSessionId = data.session_id || Board.state.termLastSessionId || null;
      }
      if (data.model) {
        var raw = data.model;
        var ctxMatch = raw.match(/\[(\d+)([mk])\]/i);
        if (ctxMatch) {
          _ctx.setContextWindow(ctxMatch[2].toLowerCase() === "m" ? parseInt(ctxMatch[1]) * 1000000 : parseInt(ctxMatch[1]) * 1000);
        }
        var clean = raw.replace(/\[.*\]/, "").replace(/^claude-/, "");
        clean = clean.replace(/-(\d+)-(\d+)/, " $1.$2").replace(/-/g, " ");
        _ctx.setSessionModel(clean.charAt(0).toUpperCase() + clean.slice(1));
      }
      if (data.permission_mode) {
        var modeEl = document.getElementById("terminal-sl-mode");
        if (modeEl) modeEl.textContent = data.permission_mode;
      }
      if (data.branch) {
        var branchEl = document.getElementById("terminal-sl-branch");
        if (branchEl) branchEl.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:3px"><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M6 15V9a6 6 0 0 0 6-6h0a6 6 0 0 0 6 6"/></svg>' + data.branch;
      }
      _ctx.updateControlBar();
    }).catch(function () {});
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

    // 토큰/비용은 assistant 이벤트 수신 시 set 의미로 덮어쓰기 때문에 누적
    // 위험이 없다. 재연결마다 리셋하면 SSE gap 이 비어 있거나 gap-fill 응답이
    // 늦을 때 상태가 0 으로 고착되므로 리셋하지 않는다. 세션 전환/재시작/
    // process_exit 경로는 각자 resetTokens 을 이미 호출한다.

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
      // SSE 링버퍼 재생에 가장 최근 assistant 이벤트가 포함되지 않을 수 있으므로
      // REST 로도 최신 usage/cost 를 재수화한다 (empty gap 이어도 서버는 현재
      // 총계를 돌려준다).
      if (!_ctx.isWorkflowMode() && termMod && termMod._historyLoaded &&
          typeof termMod.fetchHistorySince === "function") {
        termMod.fetchHistorySince(Board.state.termSessionId);
      }
    } else if (!_ctx.isWorkflowMode()) {
      // 메인 세션: REST /terminal/history 가 과거의 권위 있는 출처이므로
      // SSE 링버퍼 재생은 생략한다. 서버는 replay_start/end 프레임도 보내지 않는다.
      eventsUrl += qsSep() + "skip_replay=1";
      // 재연결 (already loaded once) 이면 REST 로 gap 을 보충한다.
      if (termMod && termMod._historyLoaded && typeof termMod.fetchHistorySince === "function") {
        termMod.fetchHistorySince(Board.state.termSessionId);
      }
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

    termEventSource.addEventListener("replay_start", function () {
      _isReplaying = true;
    });

    termEventSource.addEventListener("replay_end", function () {
      _isReplaying = false;
      // replay 완료 후 타임라인 최종 렌더
      if (_ctx.isWorkflowMode()) {
        try { Board.phaseTimeline.render(); } catch (e) {}
      }
      // T-383 Phase 5 (T5-2): replay 후 최종 상태 수렴.
      // replay 중 workflow_step 이벤트는 FSM 전이를 수행하지 않고 DOM 재건
      // 경로에만 의존하므로, replay 종료 시점에 서버 보유 최종 workflow 상태를
      // REST 로 재조회하여 UI 상태( Board.state 등 )를 보정한다.
      // 초기 connectSSEReady().then(fetchStatus) 경로와는 시점이 다르다:
      // 그 호출은 replay 시작 직전이며, 본 호출은 replay 완료 "후" 최종 상태.
      try { fetchStatus(); } catch (fsErr) {}
    });

    // T-383 Phase 5 (T5-1, T5-3): replay 중 workflow_step 스킵.
    // 원칙(T-379 Phase 2): workflow_step SSE 가 FSM 전이의 유일한 경로.
    // 본 게이트는 이 원칙을 위반하지 않는다 — "아직 전이할 시점이 아니다"
    // 로 해석한다. replay 중에는 DOM 재건( rebuildStepPanelsFromDom )이
    // _restoreSession 경로에서 수행되므로 UI 상태는 다른 경로로 수렴하며,
    // 최종 FSM 상태는 replay_end 시 fetchStatus()로 보정된다.
    // _captureEventId 는 replay 중에도 항상 호출하여 재접속 시 from-id 를
    // 보장한다(누락 시 히스토리 중복 재생 버그 재발 가능).
    termEventSource.addEventListener("workflow_step", function (e) {
      _captureEventId(e);
      if (_isReplaying) {
        // replay 중: FSM 전이( handleStepEvent ) 및 타임라인 렌더 스킵.
        // 실시간 이벤트 수신 시점에 정상적으로 전이가 수행된다.
        return;
      }
      try {
        var data = JSON.parse(e.data);
        if (Board.WorkflowRenderer && Board.WorkflowRenderer.handleStepEvent) {
          Board.WorkflowRenderer.handleStepEvent(data);
        }
        if (_ctx.isWorkflowMode()) {
          try { Board.phaseTimeline.render(); } catch (re) {}
        }
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

        if (data.chunk && data.kind === "text_delta") {
          _ctx.setReceivedChunks(true);
          _ctx.appendTextBuffer(data.chunk);
          // Accumulate for WorkflowRenderer.tap() at flush time
          if (_ctx.isWorkflowMode()) {
            _pendingTextBuffer += data.chunk;
          }
        } else if (data.text && data.kind === "assistant" && !_ctx.getReceivedChunks()) {
          _ctx.appendTextBuffer(data.text);
        } else if (data.kind === "input_json_delta" && typeof data.chunk === "string") {
          // Route input chunk into per-tool_use_id buffer (parallel-safe)
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
            // Flush accumulated text_delta chunks through WorkflowRenderer before clearing
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

            // Track current tool_use_id for input_json_delta routing
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
          // Flush accumulated text_delta chunks through WorkflowRenderer before clearing
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
          var tr = data.raw.tool_use_result;
          var mc = data.raw.message && data.raw.message.content;
          var resultText = "";

          // Extract tool_use_id from the user event for parallel-safe box matching.
          // The tool_use_id may appear in:
          //   - tr.tool_use_id (tool_use_result shorthand)
          //   - mc[0].tool_use_id (message.content array element)
          var userToolUseId = null;
          if (tr && tr.tool_use_id) {
            userToolUseId = tr.tool_use_id;
          } else if (mc && mc[0] && mc[0].tool_use_id) {
            userToolUseId = mc[0].tool_use_id;
          }

          // Resolve tool name from the matched box's data attribute or currentToolName
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

          // Before calling insertToolResult, swap terminal.js's shared toolInputBuffer
          // to the per-tool_use_id buffer so the correct input is rendered.
          if (userToolUseId && _toolInputMap[userToolUseId] !== undefined) {
            _ctx.resetToolInputBuffer();
            _ctx.appendToolInputBuffer(_toolInputMap[userToolUseId]);
            delete _toolInputMap[userToolUseId];
          }

          if (resultText && resultText.trim()) {
            // WorkflowRenderer tap integration
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
            // Phase 4 fix: remove empty tool box when resultText is falsy
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

        // Usage realtime update — set (not add): each event carries
        // the full context usage for that API call, not a delta.
        if (data.usage) {
          if (typeof data.usage.input_tokens === "number") {
            _ctx.setInputTokens(data.usage.input_tokens);
          }
          if (typeof data.usage.output_tokens === "number") {
            _ctx.setOutputTokens(data.usage.output_tokens);
          }
          _ctx.updateStatusLine();
        }
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("result", function (e) {
      _captureEventId(e);
      try {
        var data = JSON.parse(e.data);
        if (data.done) {
          _ctx.stopSpinner();
          if (typeof data.cost_usd === "number") _ctx.setSessionCost(data.cost_usd);
          if (!_ctx.isWorkflowMode() && _ctx.getSessionTokens().input === 0 && _ctx.getSessionTokens().output === 0) {
            if (typeof data.input_tokens === "number") _ctx.setInputTokens(data.input_tokens);
            if (typeof data.output_tokens === "number") _ctx.setOutputTokens(data.output_tokens);
          }
          _ctx.updateStatusLine();

          // Flush any remaining text_delta chunks through WorkflowRenderer
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

          // In workflow mode, re-render timeline bar to update timers on response complete
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

          // Reset parallel-tool tracking state
          _currentToolUseId = null;
          _toolInputMap = {};
          if (_ctx.resetToolBoxMap) _ctx.resetToolBoxMap();

          Board.state.setTermStatus("idle");
          _ctx.setReceivedChunks(false);
          _ctx.setInputLocked(false);
          _ctx.updateControlBar();

          // 큐에 대기 중인 메시지가 있으면 자동으로 다음 메시지를 전송
          if (_ctx.getInputQueue && _ctx.getInputQueue().length > 0) {
            _ctx.drainQueue();
          }
        }
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("system", function (e) {
      _captureEventId(e);
      try {
        var data = JSON.parse(e.data);
        if (data.subtype === "init" && data.session_id) {
          // 서버가 resume_session_id 선반영한 UUID 와 실제 CLI 세션 UUID 가
          // 다른 케이스 (graceful fallback 등). 이전 UUID 기준으로 REST
          // 로드된 과거 대화를 버리고 새 UUID 로 다시 로드한다.
          var prevSid = Board.state.termSessionId;
          if (prevSid && String(prevSid) !== String(data.session_id)) {
            _ctx.clearOutput();
            _resetSessionDerivedState();
            var termModSwap = Board._term;
            if (termModSwap && typeof termModSwap.loadHistory === "function") {
              termModSwap.loadHistory(data.session_id);
            }
          }
          Board.state.termSessionId = data.session_id;
          Board.state.setTermStatus("idle");
          if (data.raw && data.raw.model) {
            var rawModel = data.raw.model;
            var ctxMatch = rawModel.match(/\[(\d+)([mk])\]/i);
            if (ctxMatch) {
              var ctxNum = parseInt(ctxMatch[1]);
              _ctx.setContextWindow(ctxMatch[2].toLowerCase() === "m" ? ctxNum * 1000000 : ctxNum * 1000);
            }
            var clean = rawModel.replace(/\[.*\]/, "").replace(/^claude-/, "");
            clean = clean.replace(/-(\d+)-(\d+)/, " $1.$2").replace(/-/g, " ");
            clean = clean.charAt(0).toUpperCase() + clean.slice(1);
            _ctx.setSessionModel(clean);
          }
          if (data.raw && data.raw.permissionMode) {
            var modeEl = document.getElementById("terminal-sl-mode");
            if (modeEl) modeEl.textContent = data.raw.permissionMode;
          }
          _ctx.setInputLocked(false);
          _ctx.updateControlBar();
        } else if (data.subtype === "process_exit") {
          // busy/starting/idle 중 어느 상태든 process_exit 은 stopped 로 전이한다.
          // (이전 코드는 running 상태에서 early return하여 상태가 고착되는 버그가 있었음)
          var wasActive = Board.state.termStatus === "busy" ||
                          Board.state.termStatus === "starting";
          if (wasActive) {
            // 응답/준비 중 process_exit: result 이벤트와 동일한 UI 정리 수행
            _ctx.setReceivedChunks(false);
            _ctx.resetToolInputBuffer();
            _pendingTextBuffer = "";
            _ctx.flushTextBuffer();
            _currentToolUseId = null;
            _toolInputMap = {};
          }
          Board.state.setTermStatus("stopped");
          _ctx.resetTokens();
          _ctx.setSessionCost(0);
          _ctx.stopSpinner();
          var exitCode = data.exit_code;
          if (exitCode !== 0 && exitCode !== 143 && exitCode !== undefined) {
            _ctx.appendErrorMessage("Process exited with code " + exitCode);
          }
          _ctx.setInputLocked(false);
          _ctx.updateControlBar();
        }
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
        if (!data.text) return;

        // If this text was sent by the local sendInput(), skip DOM insertion
        // (sendInput already added the element). Keep in Set because the
        // server may echo user_input twice (input handler + CLI NDJSON).
        // The set is cleared on SSE reconnect, so history replay works.
        if (_sentTexts.has(data.text)) {
          return;
        }

        var div = document.createElement("div");
        div.className = "term-message term-user";
        div.textContent = data.text;
        _ctx.appendToOutput(div);
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
    Board.state.termConnected = false;
  }

  // ── Session Management ──

  // UUID v1~v5 느슨한 형식 검증 (하이픈 포함 36자)
  var UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  /**
   * 세션 스위치/재시작 시 누적된 파생 상태를 전부 초기화한다.
   * - 모듈 스코프: _pendingTextBuffer, _sentTexts, _currentToolUseId, _toolInputMap, _isReplaying
   * - M 네임스페이스: thinking spinner, tool-box 매핑, toolInputBuffer, currentToolName, sessionTokens/Cost
   * - WorkflowRenderer reset (있을 때)
   * DOM 출력은 호출자가 clearOutput 으로 별도 처리.
   */
  function _resetSessionDerivedState() {
    _pendingTextBuffer = "";
    _sentTexts.clear();
    _currentToolUseId = null;
    _toolInputMap = {};
    _isReplaying = false;
    if (_ctx) {
      _ctx.resetTokens && _ctx.resetTokens();
      _ctx.setReceivedChunks && _ctx.setReceivedChunks(false);
    }
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

  function startSession(resumeSessionId) {
    if (!_ctx) return;
    // 중복 요청 방지: spawn 응답이 올 때까지 추가 클릭 무시.
    if (_startInFlight) return;
    var isResume = !!resumeSessionId;

    // 선제 UUID 검증: resume 요청인데 UUID 형식이 아니면 서버 fallback 대신 즉시 실패 처리
    if (isResume && !UUID_RE.test(String(resumeSessionId))) {
      _ctx.appendErrorMessage("[오류] 잘못된 세션 ID 형식입니다: " + String(resumeSessionId).substring(0, 16));
      return;
    }

    // 이미 활성 세션이 있으면 세션 스위치로 간주하고 연결을 리셋한다.
    // 서버의 claude_process.spawn() 이 내부에서 기존 프로세스를 kill 하므로
    // HTTP kill 을 별도로 호출할 필요는 없다.
    if (Board.state.termStatus !== "stopped") {
      disconnectSSE();
      Board.state.setTermStatus("stopped");
      Board.state.termSessionId = null;
      _ctx.updateControlBar();
    }

    // 새 세션(isResume=false) 시작 시 termSessionId 를 명시적으로 비운다.
    // stopped 상태에서 Start 를 누른 경우 fetchStatus 가 이미 null 로 돌려두지만,
    // 방어적으로 여기서도 클리어해 system/init 의 "세션 교체" 조건을 원천 차단한다.
    // isResume 경로는 아래 Line 966 부근에서 resumeSessionId 로 명시 세팅된다.
    if (!isResume) {
      Board.state.termSessionId = null;
    }

    // 파생 상태 전체 리셋 — 이전 세션의 tool-box 매핑 / 텍스트 버퍼가
    // 새 세션 이벤트 처리에 섞이지 않도록 한다.
    _resetSessionDerivedState();

    // 새 세션 시작(또는 resume)은 새로운 이벤트 스트림의 시작이므로
    // 이전 채널의 last-event-id는 의미가 없다.
    _lastEventId = -1;
    _sessionArchived = false;

    if (_ctx.isWorkflowMode()) {
      _ctx.clearOutput();
      connectSSEReady().catch(function (err) {
        _ctx.appendErrorMessage("[Error] SSE connect failed: " + err.message);
      });
      return;
    }

    _ctx.clearOutput();
    if (isResume) {
      // 과거 대화를 즉시 UI 에 로드 (Claude CLI spawn 응답을 기다리지 않음).
      // spawn 은 백그라운드로 진행되며, resume 은 큰 세션에서 10초 이상 걸릴 수
      // 있으므로 사용자 체감 UX 를 위해 REST /terminal/history 로 먼저 채운다.
      // 주의: 서버가 graceful fallback 하면 init 이벤트에서 실제 session_id
      // 가 달리 도착하고, 그때 과거 대화를 재로딩한다 (system/init 리스너 참조).
      Board.state.termSessionId = resumeSessionId;
      var termModResume = Board._term;
      if (termModResume && typeof termModResume.loadHistory === "function") {
        termModResume.loadHistory(resumeSessionId);
      }
    }

    // spawn 요청 ~ init 이벤트 수신 전까지는 "starting". 입력은 아직 비활성.
    Board.state.setTermStatus("starting");
    _ctx.updateControlBar();

    _startInFlight = true;
    connectSSEReady().then(function () {
      var startBody = isResume ? { resume_session_id: resumeSessionId } : undefined;
      return postJson("/terminal/start", startBody);
    }).then(function (data) {
      // spawn 응답 = 프로세스 준비 완료. claude -p 는 첫 stdin 입력 전까지
      // system/init 이벤트를 emit 하지 않기 때문에 init 대기 대신 여기서
      // idle 로 전이한다. 입력창/버튼을 즉시 활성화한다.
      // 스피너는 Claude 가 실제로 응답을 시작할 때 sendInput 경로에서 켠다.
      if (data && data.session_id) {
        Board.state.termSessionId = data.session_id;
      }
      Board.state.setTermStatus("idle");
      _ctx.setInputLocked(false);
      _ctx.updateControlBar();
    }).catch(function (err) {
      var reason = err && err.message ? err.message : "알 수 없는 오류";
      var prefix = isResume ? "[오류] 세션 재개 실패" : "[Error] Failed to start session";
      _ctx.appendErrorMessage(prefix + ": " + reason);
      Board.state.setTermStatus("stopped");
      _ctx.updateControlBar();
    }).then(function () {
      _startInFlight = false;
    }, function () {
      _startInFlight = false;
    });
  }

  // 중복 kill 호출 방지 플래그
  var _killingInProgress = false;

  function killSession() {
    if (!_ctx) return;
    var killable = Board.util.TERM_STATUS_KILLABLE;
    if (!killable.has(Board.state.termStatus)) return;
    // 중복 kill 요청 방지
    if (_killingInProgress) return;
    _killingInProgress = true;

    var prevStatus = Board.state.termStatus;
    var epK = _ctx.endpoints();
    // Close 시 UI 정리 — process_exit 경로와 동일한 리셋을 수행해
    // 대화창 / 토큰 / 비용 / 스피너가 stopped 상태에 어색하게 남지 않도록 한다.
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
      // permission mode 표시는 DOM 직접 제어 (setSessionModel 같은 상태 저장소 없음)
      var modeEl = document.getElementById("terminal-sl-mode");
      if (modeEl) modeEl.textContent = "";
      Board.state.termSessionId = null;
    }
    postJson(epK.kill, epK.inputBody({})).then(function () {
      Board.state.setTermStatus("stopped");
      _ctx.setInputLocked(false);
      _finalizeStoppedUI();
      _ctx.updateControlBar();
      // kill 성공 후 SSE 연결 정리: 잔여 이벤트가 상태를 되돌리지 않도록 한다
      disconnectSSE();
    }).catch(function (err) {
      // 409: 프로세스가 이미 종료된 경우 → stopped로 복구
      var is409 = err.message && err.message.indexOf("409") !== -1;
      if (is409) {
        Board.state.setTermStatus("stopped");
        _ctx.setInputLocked(false);
        _finalizeStoppedUI();
        _ctx.updateControlBar();
        disconnectSSE();
      } else {
        // 그 외 에러: 이전 상태로 복구하여 버튼 고착 방지
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
   * 세션 전환용 SSE 재연결.
   * disconnectSSE() → connectSSE() → fetchStatus() 순서를 보장한다.
   * switchSession() 내부에서 직접 호출하는 것과 동일하지만, 외부에서도
   * 명시적으로 "재연결만" 원할 때 사용할 수 있다.
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
    _bind: bind,
    _markSent: markSent
  };
})();
