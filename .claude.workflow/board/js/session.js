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

  function _captureEventId(e) {
    if (!e || e.lastEventId == null) return;
    var n = parseInt(e.lastEventId, 10);
    if (!isNaN(n) && n > _lastEventId) _lastEventId = n;
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
      if (!res.ok) return;
      return res.json();
    }).then(function (data) {
      if (!data) return;
      Board.state.termStatus = data.status || "stopped";
      Board.state.termSessionId = data.session_id || null;
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

    // Reset tokens on reconnect to avoid duplicate accumulation from history replay
    _ctx.resetTokens();

    // Clear sent-text tracking so that history-replayed user_input events
    // are rendered into the DOM (they are not duplicates).
    _sentTexts.clear();

    // Reset parallel-tool tracking state on reconnect
    _currentToolUseId = null;
    _toolInputMap = {};

    // Reset pending text buffer on reconnect
    _pendingTextBuffer = "";

    // Resume from last received event id to prevent full-history replay on reconnect
    var eventsUrl = _ctx.endpoints().events;
    if (_lastEventId >= 0) {
      eventsUrl += (eventsUrl.indexOf("?") >= 0 ? "&" : "?") + "last_event_id=" + _lastEventId;
    }
    termEventSource = new EventSource(eventsUrl);

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
                if (textBannerConsumed) {
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
              if (userTextBannerConsumed) {
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
                if (bannerConsumed) {
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
          if (_ctx.isWorkflowMode()) {
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

          _ctx.appendSystemMessage("Response complete");

          Board.state.termStatus = "idle";
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
          Board.state.termSessionId = data.session_id;
          Board.state.termStatus = "idle";
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
          _ctx.appendSystemMessage("Session started");
          _ctx.setInputLocked(false);
          _ctx.updateControlBar();
        } else if (data.subtype === "process_exit") {
          // running 상태에서도 process_exit를 처리하여 stopped로 전이한다.
          // (이전 코드는 running 상태에서 early return하여 상태가 고착되는 버그가 있었음)
          if (Board.state.termStatus === "running") {
            // running 중 process_exit: result 이벤트와 동일한 UI 정리 수행
            _ctx.stopSpinner();
            _ctx.setReceivedChunks(false);
            _ctx.resetToolInputBuffer();
            _pendingTextBuffer = "";
            _ctx.flushTextBuffer();
            _currentToolUseId = null;
            _toolInputMap = {};
          }
          Board.state.termStatus = "stopped";
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
        Board.state.termStatus = "stopped";
        _ctx.setInputLocked(false);
        _ctx.updateControlBar();
      } catch (err) {
        // Ignore non-JSON error events
      }
    });

    termEventSource.onerror = function () {
      Board.state.termConnected = false;
      termEventSource.close();
      termEventSource = null;
      _ctx.updateControlBar();

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

  function startSession(resumeSessionId) {
    if (!_ctx) return;
    if (Board.state.termStatus !== "stopped") return;
    var isResume = !!resumeSessionId;

    // 선제 UUID 검증: resume 요청인데 UUID 형식이 아니면 서버 fallback 대신 즉시 실패 처리
    if (isResume && !UUID_RE.test(String(resumeSessionId))) {
      _ctx.appendErrorMessage("[오류] 잘못된 세션 ID 형식입니다: " + String(resumeSessionId).substring(0, 16));
      return;
    }

    // 새 세션 시작(또는 resume)은 새로운 이벤트 스트림의 시작이므로
    // 이전 채널의 last-event-id는 의미가 없다. 리셋하여 새 히스토리를 받도록 한다.
    _lastEventId = -1;

    if (_ctx.isWorkflowMode()) {
      _ctx.clearOutput();
      _ctx.appendSystemMessage("Connecting to workflow session " + _ctx.getWorkflowSessionId() + "...");
      connectSSEReady().catch(function (err) {
        _ctx.appendErrorMessage("[Error] SSE connect failed: " + err.message);
      });
      return;
    }

    _ctx.clearOutput();
    if (isResume) {
      _ctx.appendSystemMessage("세션 재개 중... (" + String(resumeSessionId).substring(0, 8) + ")");
    } else {
      _ctx.appendSystemMessage("Starting session...");
    }

    Board.state.termStatus = "running";
    _ctx.updateControlBar();

    connectSSEReady().then(function () {
      var startBody = isResume ? { resume_session_id: resumeSessionId } : undefined;
      return postJson("/terminal/start", startBody);
    }).then(function (data) {
      _ctx.startSpinner();
      _ctx.setInputLocked(true);
      if (data && data.session_id) {
        Board.state.termSessionId = data.session_id;
        Board.state.termStatus = "idle";
        _ctx.updateControlBar();

        // 서버가 fallback으로 새 세션을 만들었는지 감지
        // (server.py는 잘못된 resume_session_id 시 새 세션으로 graceful fallback함)
        if (isResume && String(data.session_id) !== String(resumeSessionId)) {
          _ctx.appendSystemMessage(
            "[안내] 요청한 세션(" + String(resumeSessionId).substring(0, 8) +
            ")을 재개할 수 없어 새 세션(" + String(data.session_id).substring(0, 8) + ")이 생성되었습니다."
          );
        } else if (isResume) {
          _ctx.appendSystemMessage("세션 " + String(data.session_id).substring(0, 8) + "... 재개됨");
        }
      }
      if (!isResume) {
        var initText = "첫 메시지입니다. '세션이 초기화 되었습니다.' 라고만 답하세요.";
        _sentTexts.add(initText);
        postJson("/terminal/input", { text: initText }).catch(function () {});
      }
    }).catch(function (err) {
      var reason = err && err.message ? err.message : "알 수 없는 오류";
      var prefix = isResume ? "[오류] 세션 재개 실패" : "[Error] Failed to start session";
      _ctx.appendErrorMessage(prefix + ": " + reason);
      Board.state.termStatus = "stopped";
      _ctx.updateControlBar();
    });
  }

  // 중복 kill 호출 방지 플래그
  var _killingInProgress = false;

  function killSession() {
    if (!_ctx) return;
    if (Board.state.termStatus === "stopped") return;
    // 중복 kill 요청 방지
    if (_killingInProgress) return;
    _killingInProgress = true;

    var prevStatus = Board.state.termStatus;
    var epK = _ctx.endpoints();
    postJson(epK.kill, epK.inputBody({})).then(function () {
      _ctx.appendSystemMessage("Session terminated");
      Board.state.termStatus = "stopped";
      _ctx.setInputLocked(false);
      _ctx.updateControlBar();
      // kill 성공 후 SSE 연결 정리: 잔여 이벤트가 상태를 되돌리지 않도록 한다
      disconnectSSE();
    }).catch(function (err) {
      // 409: 프로세스가 이미 종료된 경우 → stopped로 복구
      var is409 = err.message && err.message.indexOf("409") !== -1;
      if (is409) {
        Board.state.termStatus = "stopped";
        _ctx.setInputLocked(false);
        _ctx.updateControlBar();
        disconnectSSE();
      } else {
        // 그 외 에러: 이전 상태로 복구하여 버튼 고착 방지
        _ctx.appendErrorMessage("[Error] Failed to kill session: " + err.message);
        Board.state.termStatus = prevStatus;
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
    _bind: bind,
    _markSent: markSent
  };
})();
