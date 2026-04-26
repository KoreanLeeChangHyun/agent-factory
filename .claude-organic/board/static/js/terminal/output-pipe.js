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
          var header = "";
          for (var i = 0; i < token.header.length; i++) {
            header += '<th>' + this.parser.parseInline(token.header[i].tokens) + '</th>';
          }
          var body = "";
          for (var r = 0; r < token.rows.length; r++) {
            var row = token.rows[r];
            var cells = "";
            for (var c = 0; c < row.length; c++) {
              cells += '<td>' + this.parser.parseInline(row[c].tokens) + '</td>';
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
    // 재로드 시 복원되지 않는 placeholder는 출력하지 않는다.
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
    if (!M.outputDiv || !events || !events.length) return;
    var sawInFlight = false;
    for (var i = 0; i < events.length; i++) {
      var ev = events[i];
      var kind = ev.kind || "text";
      if (ev.in_flight) sawInFlight = true;
      // in_flight 이벤트는 Claude CLI 가 jsonl 에 아직 flush 하지 못한
      // "현재 스트리밍 중인 블록" 이다. 완성된 블록처럼 DOM 에 추가하면
      // 이어지는 라이브 text_delta 가 별개 블록을 만들어 응답이 두 조각으로
      // 쪼개진다. 텍스트/툴은 클라이언트의 "live 스트리밍 버퍼" 에 시딩해서
      // 다음 delta 가 자연스럽게 이어붙도록 한다.
      if (ev.in_flight) {
        if (kind === "text" && ev.role === "assistant") {
          // 기존 textBuffer 를 교체하지 않고 앞에 붙여 이어받는다.
          M.textBuffer = (ev.text || "") + (M.textBuffer || "");
        } else if (kind === "tool_use") {
          _renderToolUse(ev);
          if (typeof ev.partial_input_json === "string" && ev.partial_input_json) {
            // content_block_stop 이 오기 전이라 input 이 부분 JSON 문자열인 경우,
            // 화면 표시용 버퍼도 partial_json 으로 교체 (유효하지 않은 JSON 이어도
            // toolInputBuffer 는 렌더링 직전에 문자열 누적으로 처리된다).
            M.toolInputBuffer = ev.partial_input_json;
          }
          if (Board.session && typeof Board.session.seedInFlightToolUse === "function") {
            Board.session.seedInFlightToolUse(
              ev.tool_use_id || "",
              ev.partial_input_json || ""
            );
          }
        } else if (kind === "thinking") {
          // thinking 은 라이브 스트림에서 렌더되지 않는 블록이므로 그대로 완성된
          // 형태로 그린다. 이후 assistant NDJSON 이 도착해도 thinking 재렌더가
          // 없으므로 중복 걱정 없음.
          if (ev.text) _renderThinking(ev.text);
        }
        continue;
      }
      if (kind === "text") {
        var text = ev.text || "";
        if (!text) continue;
        if (ev.role === "user") {
          var userDiv = document.createElement("div");
          userDiv.className = "term-message term-user";
          userDiv.textContent = text;
          M.appendToOutput(userDiv);
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
    // in_flight 이벤트를 만났다는 것은 LLM 이 현재 스트리밍 중이라는 뜻.
    // 새로고침으로 페이지가 재구성된 상태이므로 스피너를 복구하고 termStatus
    // 를 busy 로 올려 입력 잠금 등 관련 UI 를 재개한다.
    if (sawInFlight && !M.isWorkflowMode) {
      if (Board.debugLog) Board.debugLog('renderHistory.inFlightDetected', {
        events: events.length, termStatus: Board.state.termStatus,
      });
      Board.state.setTermStatus("busy");
      if (M.startSpinner) M.startSpinner();
    }
  };

  /**
   * jsonl 에서 복원된 누적 토큰/비용을 in-memory 상태에 반영한다.
   * 서버 응답의 last_usage / last_cost_usd 는 세션 전체에서 가장 최근 값이므로
   * set 의미(누적 아님)로 덮어쓴다. 세션 로드/재개/SSE 재연결 시 0 으로
   * 남아 있는 상태를 재수화하는 역할.
   *
   * 가드: 라이브 SSE 이벤트가 이미 토큰을 채워 놓았다면(= 현재 값이 0 이 아님)
   * 덮어쓰지 않는다. jsonl 은 턴이 끝난 뒤 append 되므로 파일 기반 값이 라이브
   * 이벤트보다 한 턴 뒤처질 수 있어, 라이브가 항상 최신이다. 첫 로드(=0,0)
   * 또는 재연결 gap-fill(=동일 값) 경로에서만 실질적으로 반영된다.
   */
  function _applyHistoryUsage(data, force) {
    if (!data) return;
    // force=true 는 loadHistory(초기 로드/세션 스위치) 경로. 이전 세션의
    // 토큰이 visible 하게 남아있어도 jsonl 의 last_usage 로 덮어써야 한다.
    // force=false(기본) 는 fetchHistorySince(gap-fill) 경로. 라이브 이벤트가
    // 이미 채운 값을 jsonl 의 이전 턴 값으로 되돌리면 안 되므로 guard.
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
    if (!sessionId || M._historyLoaded || M.isWorkflowMode) return Promise.resolve();
    M._historyLoaded = true;
    return fetch("/terminal/history?session_id=" + encodeURIComponent(sessionId), {
      cache: "no-store"
    }).then(function (res) {
      if (!res.ok) return null;
      return res.json();
    }).then(function (data) {
      if (!data) {
        M.showEmptyState();
        return;
      }
      // usage/cost 는 events 유무와 무관하게 반영한다.
      // force=true: 세션 스위치 시 이전 세션의 토큰을 이 세션의 last_usage 로 덮어쓰기.
      _applyHistoryUsage(data, true);
      // 세션 메타: jsonl 마지막 assistant 메시지의 model 을 status bar 에 복원.
      // /terminal/status 가 아닌 /terminal/history 에서 가져오는 이유는,
      // resume 시 새 spawn 프로세스의 라이브 model 이 아니라 "이 세션이 실제로
      // 사용한 model" 이 의미적으로 옳기 때문이다.
      if (data.last_model && Board.session && Board.session.applyRawModel) {
        Board.session.applyRawModel(data.last_model);
      }
      if (!data.events || !data.events.length) {
        M.showEmptyState();
        return;
      }
      M.renderHistory(data.events);
      M._historyLastTimestamp = data.last_timestamp || "";
      _scrollOutputToBottomSoon();
    }).catch(function () {
      // 네트워크 오류 등: 최소한 placeholder라도 보이게
      M.showEmptyState();
    });
  };

  function _scrollOutputToBottomSoon() {
    if (!M.outputDiv) return;
    // 마크다운/mermaid 비동기 렌더 이후 높이가 확장되므로 두 프레임 뒤 스크롤.
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        if (M.outputDiv) M.outputDiv.scrollTop = M.outputDiv.scrollHeight;
      });
    });
  }

  /**
   * 재연결 gap 보충: 마지막 복원 timestamp 이후의 새 이벤트만 가져와 덧붙인다.
   * SSE가 라이브만 전달하므로 네트워크 블립 동안 놓친 이벤트는 여기서 메운다.
   * usage/cost 는 since 와 무관하게 전체 최신값이 실리므로 gap 이 비어 있어도
   * connectSSE 의 resetTokens() 로 날아간 값을 복구한다.
   */
  M.fetchHistorySince = function(sessionId) {
    if (!sessionId || M.isWorkflowMode) return Promise.resolve();
    var since = M._historyLastTimestamp || "";
    // since 가 비어 있으면 초기 로드(loadHistory)가 담당해야 한다.
    // 여기서 전체 history 를 fetch 하면 loadHistory 결과와 겹쳐 렌더되어
    // Sessions 드롭다운 resume 직후 대화가 2벌로 찍히는 버그가 발생한다.
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
    if (diffSec < 60) return "방금 전";
    var diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return diffMin + "분 전";
    var diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return diffHour + "시간 전";
    var diffDay = Math.floor(diffHour / 24);
    if (diffDay < 7) return diffDay + "일 전";
    // 7일 이상은 날짜 표기
    try {
      return dt.toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" });
    } catch (_e2) {
      return String(isoString);
    }
  };

})();
