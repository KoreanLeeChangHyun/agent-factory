/**
 * @module terminal/output-pipe
 * Split from terminal.js. Functions attach to Board._term (M) namespace.
 */
"use strict";

(function () {
  var esc = Board.util.esc;
  var M = (Board._term = Board._term || {});

  // ── Markdown Renderer (marked.js wrapper with fallback) ──

  M._termMermaidCounter = 0;

  M._markedConfigured = false;

  M.initMarked = function() {
    if (typeof marked === "undefined") return;
    if (M._markedConfigured) return;
    M._markedConfigured = true;

    marked.use({
      breaks: true,
      gfm: true,
      renderer: {
        code: function (token) {
          var text = token.text;
          var lang = token.lang;
          if (lang === "mermaid") {
            var mid = "term-mermaid-" + (++M._termMermaidCounter);
            return '<div class="mermaid-block" data-mermaid-id="' + mid + '">' + esc(text) + '</div>';
          }
          var langLabel = lang ? esc(lang) : "code";
          var highlighted = "";
          if (typeof hljs !== "undefined" && lang && hljs.getLanguage(lang)) {
            try {
              highlighted = hljs.highlight(text, { language: lang }).value;
            } catch (e) {
              highlighted = "";
            }
          }
          if (!highlighted) {
            highlighted = token.escaped ? text : esc(text);
          }
          return '<pre class="term-code-block"><span class="term-code-lang">' + langLabel + '</span><code class="lang-' + esc(lang || "") + '">' + highlighted + '</code></pre>';
        },

        codespan: function (token) {
          return '<code class="term-inline-code">' + esc(token.text) + '</code>';
        },

        heading: function (token) {
          var depth = token.depth;
          return '<h' + depth + ' class="term-heading">' + this.parser.parseInline(token.tokens) + '</h' + depth + '>';
        },

        table: function (token) {
          // GFM `:---:` / `---:` / `:---` align information is entered into 'center'/'right'/'left'/null in token.align[i].
          var align = token.align || [];
          var header = "";
          for (var i = 0; i < token.header.length; i++) {
            var thStyle = align[i] ? ' style="text-align:' + align[i] + '"' : '';
            header += '<th' + thStyle + '>' + this.parser.parseInline(token.header[i].tokens) + '</th>';
          }
          var body = "";
          for (var r = 0; r < token.rows.length; r++) {
            var row = token.rows[r];
            var cells = "";
            for (var c = 0; c < row.length; c++) {
              var tdStyle = align[c] ? ' style="text-align:' + align[c] + '"' : '';
              cells += '<td' + tdStyle + '>' + this.parser.parseInline(row[c].tokens) + '</td>';
            }
            body += '<tr>' + cells + '</tr>';
          }
          return '<table class="term-table"><thead><tr>' + header + '</tr></thead><tbody>' + body + '</tbody></table>';
        },

        paragraph: function (token) {
          return '<p class="term-para">' + this.parser.parseInline(token.tokens) + '</p>';
        },

        link: function (token) {
          var t = token.title ? ' title="' + esc(token.title) + '"' : '';
          return '<a href="' + esc(token.href) + '"' + t + ' target="_blank" rel="noopener">' + this.parser.parseInline(token.tokens) + '</a>';
        }
      }
    });
  };

  M.renderMarkdownToHtml = function(text) {
    if (typeof marked !== "undefined" && marked.parse) {
      if (!M._markedConfigured) M.initMarked();
      try {
        var html = marked.parse(text);
        // Mermaid blocks need post-insert init (DOM not ready until caller appends)
        if (Board.render && Board.render.initMermaid) {
          setTimeout(Board.render.initMermaid, 0);
        }
        return html;
      } catch (e) {
        console.error("[md] parse failed:", e);
      }
    }
    return '<pre class="term-fallback">' + esc(text) + '</pre>';
  };

  // ── Constants ──
  var MAX_OUTPUT_NODES = 10000;

  // ── Output Div Management ──

  M.initOutputDiv = function() {
    M.outputDiv = document.getElementById("terminal-output");
    if (!M.outputDiv) return;

    M.outputDiv.innerHTML = "";

    M.initMarked();

    // Wire up M.renderMarkdownToHtml for renderers.js
    if (Board.ToolResultRenderer && Board.ToolResultRenderer.setMarkdownRenderer) {
      Board.ToolResultRenderer.setMarkdownRenderer(M.renderMarkdownToHtml);
    }

    if (typeof M.setupToolBoxDelegation === "function") {
      M.setupToolBoxDelegation();
    }
  };

  M._emptyStateShown = false;
  M._historyLoaded = false;

  M.showEmptyState = function() {
    // placeholder does not output when reloading.
    M._emptyStateShown = true;
  };

  M._historyLastTimestamp = "";

  function _renderThinking(text) {
    var details = document.createElement("details");
    details.className = "term-message term-thinking-block";
    var summary = document.createElement("summary");
    summary.textContent = "thinking";
    details.appendChild(summary);
    var body = document.createElement("div");
    body.className = "term-thinking-body";
    body.textContent = text;
    details.appendChild(body);
    M.appendToOutput(details);
  }

  function _renderToolUse(ev) {
    if (typeof M.createToolBox !== "function") return;
    M.createToolBox(ev.name || "", ev.tool_use_id || "");
    M.currentToolName = ev.name || "";
    if (ev.input && typeof ev.input === "object") {
      try {
        M.toolInputBuffer = JSON.stringify(ev.input);
      } catch (_e) {
        M.toolInputBuffer = "";
      }
    } else {
      M.toolInputBuffer = "";
    }
  }

  function _renderToolResult(ev) {
    if (typeof M.insertToolResult !== "function") return;
    var targetBox = ev.tool_use_id && M.toolBoxMap ? M.toolBoxMap[ev.tool_use_id] : null;
    var toolName = targetBox && targetBox.getAttribute
      ? (targetBox.getAttribute("data-tool-name") || undefined)
      : undefined;
    M.insertToolResult(ev.text || "", !!ev.is_error, toolName, ev.tool_use_id || "");
    M.toolInputBuffer = "";
  }

  M.renderHistory = function(events) {
    if (Board.debugLog) Board.debugLog('renderHistory.entry', {
      events: events ? events.length : 0,
      hasOutputDiv: !!M.outputDiv,
      termStatus: Board.state.termStatus,
    });
    if (!M.outputDiv || !events || !events.length) return;
    var sawInFlight = false;

    for (var i = 0; i < events.length; i++) {
      var ev = events[i];
      var kind = ev.kind || "text";
      if (ev.in_flight) sawInFlight = true;

      // in flight event Claude CLI has not yet flush in jsonl
      // "Blocks currently streaming" Add to the DOM like a complete block
      // Live text delta leads to two pieces of responses to create a distinct block
      // About Us Text/Tools to "live streaming buffer" in the client
      // The following delta will lead naturally.
      if (ev.in_flight) {
        if (kind === "text" && ev.role === "assistant") {
          // Paste the existing textBuffer without changing.
          M.textBuffer = (ev.text || "") + (M.textBuffer || "");
        } else if (kind === "tool_use") {
          _renderToolUse(ev);
          if (typeof ev.partial_input_json === "string" && ev.partial_input_json) {
            // content block stop This is an input if this is a JSON string,
            // Replacing buffer for display screens as partial json (unavailable JSON transition)
            // toolInputBuffer is handled by strings shortly before rendering).
            M.toolInputBuffer = ev.partial_input_json;
          }
          if (Board.session && typeof Board.session.seedInFlightToolUse === "function") {
            Board.session.seedInFlightToolUse(
              ev.tool_use_id || "",
              ev.partial_input_json || ""
            );
          }
        } else if (kind === "thinking") {
          // Thinking is a block that is not rendered in the live stream, so it is done in the same way.
          // Green in shape. If the assistant NDJSON arrives, it is a reminder
          // There is no duplicate.
          if (ev.text) _renderThinking(ev.text);
        }
        continue;
      }
      if (kind === "text") {
        var text = ev.text || "";
        if (!text) continue;
        if (ev.role === "user") {
          // 1:1 turn model: user message always append with outputDiv direct self.
          // turn-card user-group routing disposal.
          var userDiv = document.createElement("div");
          userDiv.className = "term-message term-user";
          if (ev.timestamp) userDiv.setAttribute("data-timestamp", ev.timestamp);
          // server history handler is given to stoped=true after sidecar matching
          // user event grants .interrupted classes (CSS displays the “About Us” badge on the right side).
          if (ev.interrupted) userDiv.classList.add("interrupted");
          userDiv.textContent = text;
          M.appendToOutput(userDiv);
          // T-429: ev.attachments are non-empty array render to separate containers.
          // The legacy message (no ev.attachments or blank array) is intact (return 0).
          // ESC intermittent messages also add .interrupted class preserved scoring cards to userDiv.
          if (ev.attachments && ev.attachments.length > 0 &&
              M.attachmentCard && typeof M.attachmentCard.create === "function") {
            var attachContainer = document.createElement("div");
            attachContainer.className = "term-message-attachments";
            ev.attachments.forEach(function (att) {
              attachContainer.appendChild(M.attachmentCard.create(att));
            });
            M.appendToOutput(attachContainer);
          }
        } else if (ev.role === "assistant") {
          var html = M.renderMarkdownToHtml(text);
          M.appendHtmlBlock(html, "term-message term-assistant");
        }
      } else if (kind === "thinking") {
        if (ev.text) _renderThinking(ev.text);
      } else if (kind === "tool_use") {
        _renderToolUse(ev);
      } else if (kind === "tool_result") {
        _renderToolResult(ev);
      }
    }

    // LLM is currently streaming.
    // Since the page has been reconfigured with a new call, it recovers the spinner and termStatus
    // Rewrite the related UI, such as holding a busy position.
    // pending turn branch (in loadHistory) is also responsible for the restoration of spinner.
    if (sawInFlight && !M.isWorkflowMode) {
      if (Board.debugLog) Board.debugLog('renderHistory.inFlightDetected', {
        events: events.length, termStatus: Board.state.termStatus,
      });
      Board.state.setTermStatus("busy");
      if (M.startSpinner) M.startSpinner();
    }
  };

  /**
   * reflects the cumulative token/cost restored in jsonl in-memory status.
   * The last usage / last cost usd of server response is the most recent value in the entire session
   * set is covered with meaning (no limit). Session Load/Registration/SSE Reconnect to zero
   * Responsible roles to resubmit the remaining state.
   *
   * Guard: If the live SSE event is already filled with tokens(= current value 0 not)
   * It is not covered. jsonl is append after turn is finished, so the file-based value is live
   * If you have any questions, please feel free to contact us. First Road(=0,0)
   * or reconnecting gap-fill(=Integrity value) only reflects substantially.
   */
  function _applyHistoryUsage(data, force) {
    if (!data) return;
    // force=true is loadHistory(second load/set switch) path. Previous Session
    // jsonl jsonl jsonl
    // force=false(default) is fetchHistorySince(gap-fill) path. Bhubaneswar – Puri – Konark
    // jsonl jsonl jsonl jsonl
    var alreadyLive = !force && (M.sessionTokens.input !== 0 || M.sessionTokens.output !== 0);
    var changed = false;
    if (!alreadyLive && data.last_usage && typeof data.last_usage === "object") {
      if (typeof data.last_usage.input_tokens === "number") {
        M.sessionTokens.input = data.last_usage.input_tokens;
        changed = true;
      }
      if (typeof data.last_usage.output_tokens === "number") {
        M.sessionTokens.output = data.last_usage.output_tokens;
        changed = true;
      }
    }
    if (M.sessionCost === 0 && typeof data.last_cost_usd === "number") {
      M.sessionCost = data.last_cost_usd;
      changed = true;
    }
    if (changed && typeof M.updateStatusLine === "function") {
      M.updateStatusLine();
    }
  }

  M.loadHistory = function(sessionId) {
    if (Board.debugLog) Board.debugLog('loadHistory.entry', {
      sessionId: sessionId || null,
      historyLoaded: !!M._historyLoaded,
      isWorkflowMode: !!M.isWorkflowMode,
      termStatus: Board.state.termStatus,
    });
    if (!sessionId || M._historyLoaded || M.isWorkflowMode) return Promise.resolve();
    M._historyLoaded = true;
    return fetch("/terminal/history?session_id=" + encodeURIComponent(sessionId), {
      cache: "no-store"
    }).then(function (res) {
      if (!res.ok) return null;
      return res.json();
    }).then(function (data) {
      if (Board.debugLog) Board.debugLog('loadHistory.response', {
        hasData: !!data,
        events: data && data.events ? data.events.length : 0,
        pendingTurn: !!(data && data.pending_turn),
        lastTimestamp: (data && data.last_timestamp) || null,
        lastEventKinds: data && data.events
          ? data.events.slice(-3).map(function (e) {
              return {
                kind: e.kind || 'text',
                role: e.role || null,
                inFlight: !!e.in_flight,
                interrupted: !!e.interrupted,
                textSample: e.text ? String(e.text).slice(0, 60) : null,
              };
            })
          : [],
      });
      if (!data) {
        M.showEmptyState();
        return;
      }
      // usage/cost reflects the event inevitable.
      // force=true: When the session switch is overlapped with the last usage of the previous session.
      _applyHistoryUsage(data, true);
      // Session meta: jsonl restores the model of last assistant message to status bar.
      // /terminal/status is not /terminal/history
      // <% if (imgObj.width >= imgObj.height) { %>
      // "The model used" is meant to be right.
      if (data.last_model && Board.session && Board.session.applyRawModel) {
        Board.session.applyRawModel(data.last_model);
      }
      if (!data.events || !data.events.length) {
        M.showEmptyState();
        return;
      }
      M.renderHistory(data.events);
      M._historyLastTimestamp = data.last_timestamp || "";
      // pending turn: The last user event is immediately after response wait or not yet in flight.
      // activate spinner without closing turn-card.
      // (in flight)
      if (data.pending_turn && !M.isWorkflowMode) {
        if (Board.debugLog) Board.debugLog('loadHistory.pendingTurnDetected', {
          events: data.events ? data.events.length : 0,
          termStatusBefore: Board.state.termStatus,
        });
        Board.state.setTermStatus("busy");
        if (M.startSpinner) M.startSpinner();
      }
      _scrollOutputToBottomSoon();
    }).catch(function () {
      // Network Error and so on: See also the minimum placeholder
      M.showEmptyState();
    });
  };

  function _scrollOutputToBottomSoon() {
    if (!M.outputDiv) return;
    // Since the markdown/mermaid asynchronous wrench extends its height, scrolling behind the two frames.
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        if (M.outputDiv) M.outputDiv.scrollTop = M.outputDiv.scrollHeight;
      });
    });
  }

  /**
   * Reconnecting gap supplements: only new events after the last restore timestamp and added.
   * SSE is only live, so the event you missed during the network blister is here.
   * usage/cost is since and the whole new value is unobtrusive, so the gap is empty.
   * resetTokens()
   */
  M.fetchHistorySince = function(sessionId) {
    if (!sessionId || M.isWorkflowMode) return Promise.resolve();
    var since = M._historyLastTimestamp || "";
    // since, the initial load (loadHistory) must be in charge.
    // If the whole history is fetched, loadHistory results and foldable rendered
    // The sessions dropdown immediately after the call is two bugs.
    if (!since) return Promise.resolve();
    var url = "/terminal/history?session_id=" + encodeURIComponent(sessionId)
      + "&since=" + encodeURIComponent(since);
    return fetch(url, { cache: "no-store" }).then(function (res) {
      if (!res.ok) return null;
      return res.json();
    }).then(function (data) {
      if (!data) return;
      _applyHistoryUsage(data);
      if (!data.events || !data.events.length) return;
      M.renderHistory(data.events);
      if (data.last_timestamp) M._historyLastTimestamp = data.last_timestamp;
    }).catch(function () { /* silent */ });
  };

  // ── Smart Auto-Scroll ──
  var SCROLL_NEAR_BOTTOM_THRESHOLD = 100;

  M.isNearBottom = function(el) {
    if (!el) return true;
    return (el.scrollHeight - el.scrollTop - el.clientHeight) <= SCROLL_NEAR_BOTTOM_THRESHOLD;
  };

  M.scrollToBottomIfFollowing = function(el, wasNearBottom) {
    if (el && wasNearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  };

  M.appendToOutput = function(el) {
    if (!M.outputDiv) return;

    var follow = M.isNearBottom(M.outputDiv);

    // All elements are outputDiv direct self-proend (turn-card grouping waste).
    while (M.outputDiv.childNodes.length >= MAX_OUTPUT_NODES) {
      M.outputDiv.removeChild(M.outputDiv.firstChild);
    }

    M.outputDiv.appendChild(el);
    M.scrollToBottomIfFollowing(M.outputDiv, follow);
  };

  M.appendHtmlBlock = function(html, className) {
    var div = document.createElement("div");
    if (className) div.className = className;
    div.innerHTML = html;
    M.appendToOutput(div);
  };

  M.appendSystemMessage = function(text) {
    var div = document.createElement("div");
    div.className = "term-system";
    div.textContent = text;
    M.appendToOutput(div);
  };

  M.appendErrorMessage = function(text) {
    var div = document.createElement("div");
    div.className = "term-error";
    div.textContent = text;
    M.appendToOutput(div);
  };

  // ── UI Helpers ──

  M.escapeHtml = function(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  };

  M.formatRelativeTime = function(isoString) {
    if (!isoString) return "";
    var dt;
    try {
      dt = new Date(isoString);
    } catch (_e) {
      return String(isoString);
    }
    var ts = dt.getTime();
    if (isNaN(ts)) return String(isoString);

    var diffSec = Math.floor((Date.now() - ts) / 1000);
    if (diffSec < 0) diffSec = 0;
    if (diffSec < 60) return "About Us";
    var diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return diffMin + "About Us";
    var diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return diffHour + "YepTube";
    var diffDay = Math.floor(diffHour / 24);
    if (diffDay < 7) return diffDay + "About Us";
    // 7 days or more
    try {
      return dt.toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" });
    } catch (_e2) {
      return String(isoString);
    }
  };

})();
