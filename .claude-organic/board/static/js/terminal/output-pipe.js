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
          return '<code class="term-inline-code">' + token.text + '</code>';
        },

        heading: function (token) {
          var depth = token.depth;
          return '<h' + depth + ' class="term-heading">' + token.text + '</h' + depth + '>';
        },

        table: function (token) {
          var header = "";
          for (var i = 0; i < token.header.length; i++) {
            header += '<th>' + token.header[i].text + '</th>';
          }
          var body = "";
          for (var r = 0; r < token.rows.length; r++) {
            var row = token.rows[r];
            var cells = "";
            for (var c = 0; c < row.length; c++) {
              cells += '<td>' + row[c].text + '</td>';
            }
            body += '<tr>' + cells + '</tr>';
          }
          return '<table class="term-table"><thead><tr>' + header + '</tr></thead><tbody>' + body + '</tbody></table>';
        },

        list: function (token) {
          var tag = token.ordered ? "ol" : "ul";
          var body = "";
          for (var i = 0; i < token.items.length; i++) {
            var itemContent = this.parser.parseInline(token.items[i].tokens);
            body += '<li>' + itemContent + '</li>';
          }
          return '<' + tag + ' class="term-list">' + body + '</' + tag + '>';
        },

        paragraph: function (token) {
          return '<p class="term-para">' + token.text + '</p>';
        },

        link: function (token) {
          var t = token.title ? ' title="' + esc(token.title) + '"' : '';
          return '<a href="' + esc(token.href) + '"' + t + ' target="_blank" rel="noopener">' + token.text + '</a>';
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
        // marked.js parse failure -- fallback
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
    if (M.isWorkflowMode) {
      // 워크플로우 모드: "Workflow Session: ..." 시스템 메시지는 탭 바 활성 탭으로 대체.
      // 스트림 연결 중 메시지만 표시한다.
      M.appendSystemMessage("Connecting to live stream...");
    } else {
      M.appendSystemMessage("Claude Code Terminal");
      M.appendSystemMessage('Press "Start" to begin a session.');
    }

    M.initMarked();

    // Wire up M.renderMarkdownToHtml for renderers.js
    if (Board.ToolResultRenderer && Board.ToolResultRenderer.setMarkdownRenderer) {
      Board.ToolResultRenderer.setMarkdownRenderer(M.renderMarkdownToHtml);
    }
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
