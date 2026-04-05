/**
 * @module terminal
 *
 * Board SPA terminal tab module.
 *
 * Provides a web-based terminal UI for interacting with Claude Code via
 * NDJSON stream-json protocol. Uses HTML div-based output renderer with
 * marked.js for markdown rendering. Manages SSE event stream for real-time
 * output, session lifecycle (start/kill), and user input submission.
 *
 * Depends on: common.js (Board.state, Board.util, Board.render)
 * Optional:   marked.js (CDN, fallback to plain text if unavailable)
 */
"use strict";

(function () {
  var esc = Board.util.esc;

  // ── Markdown Renderer (marked.js wrapper with fallback) ──

  /**
   * Configures marked.js with custom renderer for terminal-specific HTML output.
   * Falls back to plain text in <pre> if marked.js is unavailable.
   */
  function initMarked() {
    if (typeof marked === "undefined") return;

    marked.use({
      breaks: true,
      gfm: true,
      renderer: {
        code: function (token) {
          var text = token.text;
          var lang = token.lang;
          var langLabel = lang ? esc(lang) : "code";
          var highlighted = "";
          // Try highlight.js for syntax coloring
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
          // v5: header is TableCell[], rows is TableCell[][]
          // Each cell has .text (pre-rendered inline HTML string)
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
          // v5: token.items is ListItem[]; each item has .text (rendered inline HTML)
          var tag = token.ordered ? "ol" : "ul";
          var body = "";
          for (var i = 0; i < token.items.length; i++) {
            body += '<li>' + token.items[i].text + '</li>';
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
  }

  /**
   * Parses markdown text to HTML using marked.js.
   * Falls back to escaped text in <pre> if marked.js is not loaded.
   * @param {string} text - markdown text
   * @returns {string} HTML string
   */
  function renderMarkdownToHtml(text) {
    if (typeof marked !== "undefined" && marked.parse) {
      try {
        return marked.parse(text);
      } catch (e) {
        // marked.js parse failure — fallback
      }
    }
    // Fallback: plain text in <pre>
    return '<pre class="term-fallback">' + esc(text) + '</pre>';
  }

  // ── Constants ──
  var SSE_RECONNECT_INTERVAL = 3000;  // SSE reconnect delay (ms)
  var MAX_OUTPUT_NODES = 10000;       // max child nodes in output div

  var TOOL_ICONS = {
    Bash: "\u2699",       // ⚙
    Read: "\u25b6",       // ▶
    Edit: "\u270e",       // ✎
    Write: "\u270d",      // ✍
    Grep: "\u2315",       // ⌕
    Glob: "\u2605",       // ★
    Agent: "\u2726",      // ✦
    WebSearch: "\u2301",  // ⌁
    WebFetch: "\u21e9",   // ⇩
    Skill: "\u269b",      // ⚛
    TodoWrite: "\u2611",  // ☑
    NotebookEdit: "\u2630" // ☰
  };
  // Default icon for unknown tools
  var DEFAULT_TOOL_ICON = "\u25c8"; // ◈

  // ── Session dispatcher ──
  // Query param `?session=wf-T-NNN-...` routes all endpoints to the workflow
  // session variants. Absence (or `?session=main`) uses the default single
  // claude_process endpoints.
  var workflowSessionId = (function () {
    try {
      var p = new URLSearchParams(window.location.search);
      var s = p.get("session");
      if (s && s !== "main" && s.indexOf("wf-") === 0) return s;
    } catch (e) {}
    return null;
  })();
  var isWorkflowMode = workflowSessionId !== null;

  /**
   * Returns endpoint URLs for the current session mode.
   * @returns {{events:string, input:string, kill:string, status:string, inputBody:function(Object):Object}}
   */
  function endpoints() {
    if (isWorkflowMode) {
      var sid = encodeURIComponent(workflowSessionId);
      return {
        events: "/terminal/workflow/events?session_id=" + sid,
        input: "/terminal/workflow/input",
        kill: "/terminal/workflow/kill",
        status: "/terminal/workflow/status?session_id=" + sid,
        inputBody: function (extra) {
          var b = { session_id: workflowSessionId };
          for (var k in extra) if (extra.hasOwnProperty(k)) b[k] = extra[k];
          return b;
        },
      };
    }
    return {
      events: "/terminal/events",
      input: "/terminal/input",
      kill: "/terminal/kill",
      status: "/terminal/status",
      inputBody: function (extra) { return extra; },
    };
  }

  // ── State ──
  Board.state.termConnected = false;
  Board.state.termSessionId = isWorkflowMode ? workflowSessionId : null;
  // In workflow mode the session is already running (started by launcher)
  Board.state.termStatus = isWorkflowMode ? "running" : "stopped"; // running | idle | stopped

  /** @type {HTMLElement|null} output div reference */
  var outputDiv = null;
  /** @type {HTMLElement|null} current tool box <details> element for tool result insertion */
  var currentToolBox = null;
  /** @type {EventSource|null} SSE connection */
  var termEventSource = null;
  /** @type {number|null} SSE reconnect timer */
  var reconnectTimerId = null;
  /** @type {boolean} whether terminal tab has been rendered at least once */
  var termInitialized = false;
  /** @type {boolean} whether input is currently disabled (waiting for result) */
  var inputLocked = false;
  /** @type {boolean} whether streaming chunks were received for current response */
  var receivedChunks = false;
  /** @type {string} buffer for streaming text to render markdown on completion */
  var textBuffer = "";
  /** @type {number} accumulated cost for session */
  var sessionCost = 0;
  /** @type {number} total tokens used */
  var sessionTokens = { input: 0, output: 0 };
  /** @type {string} model display name */
  var sessionModel = '--';
  /** @type {number} context window size */
  var contextWindow = 1000000;

  // ── Output Div Management ──

  /**
   * Initializes the HTML div output container.
   * Sets up #terminal-output as a scrollable div and inserts initial messages.
   */
  function initOutputDiv() {
    outputDiv = document.getElementById("terminal-output");
    if (!outputDiv) return;

    outputDiv.innerHTML = "";
    if (isWorkflowMode) {
      appendSystemMessage("Workflow Session: " + workflowSessionId);
      appendSystemMessage("Connecting to live stream...");
    } else {
      appendSystemMessage("Claude Code Terminal");
      appendSystemMessage('Press "Start" to begin a session.');
    }

    // Configure marked.js
    initMarked();
  }

  // ── Smart Auto-Scroll ──
  var SCROLL_NEAR_BOTTOM_THRESHOLD = 100; // px — "하단 근처" 허용 범위

  /**
   * Returns true if the element's scroll position is within THRESHOLD px of bottom.
   * Must be called BEFORE appending new content (post-append scrollHeight is larger).
   * @param {HTMLElement} el
   * @returns {boolean}
   */
  function isNearBottom(el) {
    if (!el) return true;
    return (el.scrollHeight - el.scrollTop - el.clientHeight) <= SCROLL_NEAR_BOTTOM_THRESHOLD;
  }

  /**
   * Scrolls element to bottom only if it was near the bottom before the append.
   * @param {HTMLElement} el
   * @param {boolean} wasNearBottom — snapshot taken before content mutation
   */
  function scrollToBottomIfFollowing(el, wasNearBottom) {
    if (el && wasNearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }

  /**
   * Appends an HTML element to the output div and auto-scrolls to bottom.
   * Enforces MAX_OUTPUT_NODES limit by removing oldest children.
   * @param {HTMLElement} el - DOM element to append
   */
  function appendToOutput(el) {
    if (!outputDiv) return;

    var follow = isNearBottom(outputDiv);

    // Enforce node limit
    while (outputDiv.childNodes.length >= MAX_OUTPUT_NODES) {
      outputDiv.removeChild(outputDiv.firstChild);
    }

    outputDiv.appendChild(el);
    scrollToBottomIfFollowing(outputDiv, follow);
  }

  /**
   * Appends an HTML string as a div to the output.
   * @param {string} html - HTML content
   * @param {string} [className] - optional CSS class for the wrapper div
   */
  function appendHtmlBlock(html, className) {
    var div = document.createElement("div");
    if (className) div.className = className;
    div.innerHTML = html;
    appendToOutput(div);
  }

  /**
   * Appends a system message to the output div.
   * @param {string} text - plain text message
   */
  function appendSystemMessage(text) {
    var div = document.createElement("div");
    div.className = "term-system";
    div.textContent = text;
    appendToOutput(div);
  }

  /**
   * Appends an error message to the output div.
   * @param {string} text - plain text error message
   */
  function appendErrorMessage(text) {
    var div = document.createElement("div");
    div.className = "term-error";
    div.textContent = text;
    appendToOutput(div);
  }

  // ── Tool Result Renderer ──

  /**
   * ToolResultRenderer namespace.
   * Provides utility functions and renderer registry for tool output rendering.
   * Renderers (util.*, dispatch) are populated here (util) and in W02-W05.
   */
  var ToolResultRenderer = { util: {}, renderers: {}, dispatch: null };

  /**
   * Byte threshold above which tool result HTML is auto-collapsed into <details>.
   * @const {number}
   */
  var AUTO_COLLAPSE_BYTES = 2048;

  /**
   * Regex patterns for stripping LLM-injected meta text from tool results.
   * @const {Array<RegExp>}
   */
  var LLM_META_PATTERNS = [
    /^REMINDER:.*$/gm,
    /Please proceed with the current tasks.*$/gm,
    /Ensure that you continue to use the todo list.*$/gm,
    /<system-reminder>[\s\S]*?<\/system-reminder>/g,
  ];

  /**
   * Strips LLM-injected meta text (REMINDER, system-reminder tags, etc.) from raw text.
   * Normalises consecutive blank lines to at most two newlines.
   * @param {string} text - raw tool result text
   * @returns {string} cleaned text
   */
  ToolResultRenderer.util.stripLlmMeta = function (text) {
    if (!text) return text;
    var cleaned = text;
    for (var i = 0; i < LLM_META_PATTERNS.length; i++) {
      cleaned = cleaned.replace(LLM_META_PATTERNS[i], "");
    }
    // Normalise 3+ consecutive blank lines to 2
    cleaned = cleaned.replace(/\n{3,}/g, "\n\n");
    return cleaned;
  };

  /**
   * Wraps htmlContent in a collapsible <details> when rawByteLen exceeds AUTO_COLLAPSE_BYTES.
   * @param {string} htmlContent - already-rendered HTML string
   * @param {number} rawByteLen - byte length of the original raw text (for threshold check)
   * @param {string} summary - label text for the <summary> element
   * @returns {string} HTML string (collapsed or plain)
   */
  ToolResultRenderer.util.autoCollapse = function (htmlContent, rawByteLen, summary) {
    if (rawByteLen > AUTO_COLLAPSE_BYTES) {
      return (
        '<details class="term-result-collapse">' +
        '<summary>' + esc(summary) + ' (' + rawByteLen + ' bytes)</summary>' +
        htmlContent +
        '</details>'
      );
    }
    return htmlContent;
  };

  /**
   * Replaces well-known identifier patterns in already-escaped HTML text with
   * clickable <a> spans carrying data-kind and data-id attributes.
   * Must be called on text that has already been HTML-escaped (no raw user HTML).
   * @param {string} escapedText - HTML-escaped text
   * @returns {string} text with ID patterns wrapped in anchor tags
   */
  ToolResultRenderer.util.linkifyIds = function (escapedText) {
    if (!escapedText) return escapedText;

    // ticket_id: T-NNN or T-NNNN
    var result = escapedText.replace(/\bT-(\d{3,4})\b/g, function (_, id) {
      return '<a class="term-id-link" data-kind="ticket_id" data-id="T-' + id + '">T-' + id + '</a>';
    });

    // task_id field: task_id: "abc123" or task_id: abc123
    result = result.replace(/task_id["']?\s*:\s*["']?([a-z0-9]{6,12})/g, function (match, id) {
      return match.replace(id, '<a class="term-id-link" data-kind="task_id" data-id="' + id + '">' + id + '</a>');
    });

    // job_id: job_id / job id pattern
    result = result.replace(/job[_\s]([a-z0-9]{8,})/g, function (match, id) {
      return match.replace(id, '<a class="term-id-link" data-kind="job_id" data-id="' + id + '">' + id + '</a>');
    });

    // Cron one-shot: "Scheduled one-shot task <id>"
    result = result.replace(/Scheduled one-shot task ([a-z0-9]{8})/g, function (match, id) {
      return match.replace(id, '<a class="term-id-link" data-kind="cron_job_id" data-id="' + id + '">' + id + '</a>');
    });

    return result;
  };

  /**
   * Re-exposes Board.util.esc as a single import point for all sub-renderers.
   * @param {string} s - string to HTML-escape
   * @returns {string} escaped string
   */
  ToolResultRenderer.util.safeEsc = function (s) {
    return esc(s);
  };

  // ── Renderers: statusBadge ──

  /**
   * Renders a single-line confirmation message as an inline badge.
   * Target tools: Write, Edit, CronCreate, CronDelete, TodoWrite,
   *               Bash(1-line && < 200 bytes), CronList("No scheduled jobs.")
   * @param {string} text - stripped, 1-line text (< 200 chars expected)
   * @param {object} [meta] - reserved, unused
   * @returns {string} HTML string
   */
  ToolResultRenderer.renderers.statusBadge = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;

    var trimmed = (text || "").trim();
    if (!trimmed) {
      return '<span class="term-status-badge">(empty response)</span>';
    }

    // Replace line breaks with <br> for 2-line edge cases
    var escaped = safeEsc(trimmed).replace(/\n/g, "<br>");
    return '<span class="term-status-badge">' + linkifyIds(escaped) + "</span>";
  };

  // ── Renderers: fallbackPlain ──

  /**
   * Fallback renderer: wraps text in a <pre> block with HTML escaping.
   * Strips ANSI colour codes before rendering.
   * Target tools: unmapped tools, Bash (multi-line), Grep (content mode)
   * @param {string} text - any text
   * @param {object} [meta] - reserved, unused
   * @returns {string} HTML string
   */
  ToolResultRenderer.renderers.fallbackPlain = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;

    // Strip ANSI colour escape sequences
    var cleaned = (text || "").replace(/\x1b\[[0-9;]*m/g, "");
    var escaped = safeEsc(cleaned);
    return '<pre class="term-plain">' + linkifyIds(escaped) + "</pre>";
  };

  // ── Renderers: list ──

  /**
   * Renders a line-separated path list as <ul> with data-path attributes.
   * Handles "No matches found" / "No files found" by delegating to statusBadge.
   * Target tools: Glob, Grep (files_with_matches / count modes)
   * @param {string} text - newline-separated paths or "path:count" lines
   * @param {object} [meta] - optional, meta.toolName for Glob/Grep distinction
   * @returns {string} HTML string
   */
  ToolResultRenderer.renderers.list = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;
    var statusBadge = ToolResultRenderer.renderers.statusBadge;

    var trimmed = (text || "").trim();

    // Special-case: empty-match messages delegate to statusBadge
    if (trimmed === "No matches found" || trimmed === "No files found") {
      return statusBadge(trimmed, meta);
    }

    var lines = trimmed.split("\n").filter(Boolean);

    if (!lines.length) {
      return statusBadge("(empty list)", meta);
    }

    var items = lines.map(function (line) {
      // "path:count" format — wrap count part in <code>
      var countMatch = line.match(/^(.+):(\d+)$/);
      if (countMatch) {
        var pathPart = countMatch[1];
        var countPart = countMatch[2];
        var escapedPath = safeEsc(pathPart);
        return (
          '<li data-path="' +
          escapedPath +
          '">' +
          linkifyIds(escapedPath) +
          ":<code>" +
          safeEsc(countPart) +
          "</code></li>"
        );
      }

      // Plain path line
      var escapedLine = safeEsc(line);
      return (
        '<li data-path="' +
        escapedLine +
        '">' +
        linkifyIds(escapedLine) +
        "</li>"
      );
    });

    return '<ul class="term-path-list">' + items.join("") + "</ul>";
  };

  // ── Renderers: json ──

  /**
   * Renders JSON output with optional HTTP status badge (RemoteTrigger pattern).
   * Falls back to fallbackPlain when JSON.parse fails.
   * Target tools: TaskStop, RemoteTrigger
   * @param {string} text - pure JSON string OR "HTTP NNN\n{json}" format
   * @param {object} [meta] - reserved, unused
   * @returns {string} HTML string
   */
  ToolResultRenderer.renderers.json = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;
    var fallbackPlain = ToolResultRenderer.renderers.fallbackPlain;

    var trimmed = (text || "").trim();
    var httpBadgeHtml = "";
    var jsonBody = trimmed;

    // Detect leading "HTTP NNN" line (RemoteTrigger pattern)
    var httpMatch = trimmed.match(/^(HTTP\s+(\d{3}))\n([\s\S]*)$/);
    if (httpMatch) {
      var httpLine = httpMatch[1];
      var statusCode = parseInt(httpMatch[2], 10);
      var statusClass = "ok";
      if (statusCode >= 300 && statusCode < 400) {
        statusClass = "redirect";
      } else if (statusCode >= 400 && statusCode < 500) {
        statusClass = "client-err";
      } else if (statusCode >= 500) {
        statusClass = "server-err";
      }
      httpBadgeHtml =
        '<span class="term-http-badge term-http-' +
        statusClass +
        '">' +
        safeEsc(httpLine) +
        "</span>";
      jsonBody = httpMatch[3].trim();
    }

    // Attempt JSON.parse → pretty-print
    var parsed;
    try {
      parsed = JSON.parse(jsonBody);
    } catch (e) {
      // JSON.parse failed — delegate to fallbackPlain (full original text)
      return fallbackPlain(text, meta);
    }

    var prettyJson = JSON.stringify(parsed, null, 2);
    var prettyHtml =
      '<pre class="term-json-pretty">' +
      linkifyIds(safeEsc(prettyJson)) +
      "</pre>";

    return (
      '<div class="term-json-result">' +
      httpBadgeHtml +
      prettyHtml +
      "</div>"
    );
  };

  // ── Renderers: fileContent ──

  /**
   * Renders Read tool output in cat -n format (line-number gutter + content).
   * Parses lines matching /^\s*(\d+)\t(.*)$/ and builds a two-column table.
   * Non-matching lines are placed in the content column with an empty lineNum.
   * Target tools: Read
   * @param {string} text - cat -n formatted text
   * @param {object} [meta] - reserved, unused
   * @returns {string} HTML string
   */
  ToolResultRenderer.renderers.fileContent = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;

    var lines = (text || "").split("\n");
    // Remove trailing empty entry caused by trailing newline
    if (lines.length && lines[lines.length - 1] === "") {
      lines = lines.slice(0, lines.length - 1);
    }

    var rows = lines.map(function (line) {
      var m = line.match(/^(\s*\d+)\t(.*)$/);
      var lineNum, lineBody;
      if (m) {
        lineNum = safeEsc(m[1].trim());
        lineBody = linkifyIds(safeEsc(m[2]));
      } else {
        lineNum = "";
        lineBody = linkifyIds(safeEsc(line));
      }
      return (
        "<tr>" +
        '<td class="term-line-num">' + lineNum + "</td>" +
        '<td class="term-line-body">' + lineBody + "</td>" +
        "</tr>"
      );
    });

    return (
      '<table class="term-file-content"><tbody>' +
      rows.join("") +
      "</tbody></table>"
    );
  };

  // ── Renderers: markdown ──

  /**
   * Renders markdown content using the existing renderMarkdownToHtml function.
   * Wraps the result in <div class="term-md-result">.
   * Target tools: WebSearch, WebFetch, Agent, Task
   * @param {string} text - markdown text (stripLlmMeta already applied by dispatch)
   * @param {object} [meta] - reserved, unused
   * @returns {string} HTML string
   */
  ToolResultRenderer.renderers.markdown = function (text, meta) {
    // Reuse T-243 renderMarkdownToHtml — do NOT redefine or post-process with linkifyIds
    // (marked.js handles linkification; post-processing would break link structure)
    var mdHtml = renderMarkdownToHtml(text || "");
    return '<div class="term-md-result">' + mdHtml + "</div>";
  };

  // ── Renderers: xmlLike ──

  /**
   * Renders XML-like structured tool output (TaskOutput, task-notification pushes).
   * Parses <tag>value</tag> pairs into a <dl> list.
   * The <output> tag content is preserved in a <pre> block.
   * <task-notification> wrapper is detected and unwrapped before parsing inner tags.
   * Falls back to fallbackPlain when no tags are matched.
   * Target tools: TaskOutput, task-notification system messages
   * @param {string} text - XML-like tagged text
   * @param {object} [meta] - reserved, unused
   * @returns {string} HTML string
   */
  ToolResultRenderer.renderers.xmlLike = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;
    var fallbackPlain = ToolResultRenderer.renderers.fallbackPlain;

    var source = (text || "").trim();

    // W04-T2: Detect <task-notification> wrapper and unwrap inner content
    var notifMatch = source.match(/^<task-notification>([\s\S]*?)<\/task-notification>$/i);
    if (notifMatch) {
      source = notifMatch[1].trim();
    }

    // Parse <tag>value</tag> pairs (non-greedy, case-insensitive tag names)
    var tagRegex = /<([a-z][a-z0-9\-_]*)>([\s\S]*?)<\/\1>/gi;
    var items = [];
    var match;

    while ((match = tagRegex.exec(source)) !== null) {
      var tagName = match[1];
      var rawValue = match[2];

      var dtHtml = '<dt>' + safeEsc(tagName) + '</dt>';
      var ddHtml;

      if (tagName.toLowerCase() === 'output') {
        // Preserve <output> block content in <pre> to maintain multi-line structure
        ddHtml = '<dd><pre class="term-xml-output">' + safeEsc(rawValue) + '</pre></dd>';
      } else {
        // For status tags, attach data-status attribute for CSS colour control
        var statusAttr = '';
        if (tagName.toLowerCase() === 'status' || tagName.toLowerCase() === 'retrieval_status') {
          var statusVal = rawValue.trim().toLowerCase();
          statusAttr = ' data-status="' + safeEsc(statusVal) + '"';
        }
        var escapedVal = linkifyIds(safeEsc(rawValue.trim()));
        ddHtml = '<dd' + statusAttr + '>' + escapedVal + '</dd>';
      }

      items.push(dtHtml + ddHtml);
    }

    // No tags matched — fall back to plain rendering
    if (!items.length) {
      return fallbackPlain(text, meta);
    }

    return '<dl class="term-xml-result">' + items.join('') + '</dl>';
  };

  // ── Renderers: schema ──

  /**
   * Renders ToolSearch output: extracts <function> JSON blocks and builds
   * collapsed cards showing name and description for each tool.
   * Falls back to fallbackPlain when no valid function blocks are found.
   * Target tools: ToolSearch
   * @param {string} text - <functions>...</functions> wrapper with <function>{json}</function> entries
   * @param {object} [meta] - reserved, unused
   * @returns {string} HTML string
   */
  ToolResultRenderer.renderers.schema = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var fallbackPlain = ToolResultRenderer.renderers.fallbackPlain;

    var source = (text || '').trim();

    // Extract individual <function>...</function> blocks
    var funcRegex = /<function>([\s\S]*?)<\/function>/gi;
    var cards = [];
    var match;

    while ((match = funcRegex.exec(source)) !== null) {
      var blockText = match[1].trim();
      var parsed;
      try {
        parsed = JSON.parse(blockText);
      } catch (e) {
        // Skip malformed JSON blocks silently
        continue;
      }

      var name = (parsed && parsed.name) ? String(parsed.name) : '';
      var desc = (parsed && parsed.description) ? String(parsed.description) : '';

      // linkifyIds is intentionally NOT applied to schema text (schema pollution risk)
      cards.push(
        '<div class="term-schema-card">' +
        '<strong class="term-schema-name">' + safeEsc(name) + '</strong>' +
        '<p class="term-schema-desc">' + safeEsc(desc) + '</p>' +
        '</div>'
      );
    }

    // No valid cards extracted — fall back to plain rendering
    if (!cards.length) {
      return fallbackPlain(text, meta);
    }

    return (
      '<details class="term-schema-collapse" open="">' +
      '<summary>Functions (' + cards.length + ')</summary>' +
      '<div class="term-schema-cards">' + cards.join('') + '</div>' +
      '</details>'
    );
  };

  // ── Renderers: taskStream ──

  /**
   * Renders Bash(run_in_background) output: extracts task_id and output file path
   * from the "Command running in background with ID: ..." signature line.
   * Falls back to fallbackPlain when the signature line is not detected.
   * Target tools: Bash (run_in_background=true)
   * @param {string} text - stripped text starting with background task signature
   * @param {object} [meta] - reserved, unused
   * @returns {string} HTML string
   */
  ToolResultRenderer.renderers.taskStream = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var fallbackPlain = ToolResultRenderer.renderers.fallbackPlain;

    var source = (text || '').trim();

    // Primary form: "Command running in background with ID: <id>. Output is being written to: <path>"
    var full = source.match(/Command running in background with ID:\s*(\S+?)\.\s*Output is being written to:\s*(\S+)/);
    var taskId = '';
    var outputPath = '';

    if (full) {
      taskId = full[1];
      outputPath = full[2];
    } else {
      // Split form: ID-only on first match line, scan remainder for output path
      var idOnly = source.match(/Command running in background with ID:\s*(\S+)/);
      if (!idOnly) {
        return fallbackPlain(text, meta);
      }
      taskId = idOnly[1].replace(/\.+$/, '');
      // Scan subsequent lines for a plausible output file path (e.g., /tmp/*.log)
      var pathMatch = source.match(/(?:Output is being written to|Output file|output)[^\S\r\n]*[:\-]?\s*(\/[^\s"']+)/i);
      if (pathMatch) {
        outputPath = pathMatch[1];
      } else {
        // Last-ditch: any /tmp/... path referenced anywhere in text
        var tmpMatch = source.match(/(\/(?:tmp|var\/log|var\/tmp)\/\S+)/);
        if (tmpMatch) outputPath = tmpMatch[1];
      }
    }

    if (!taskId) {
      return fallbackPlain(text, meta);
    }

    var escapedId = safeEsc(taskId);
    var html = '<div class="term-taskstream">' +
      '<span class="term-task-badge">' +
      'task <a class="term-id-link" data-kind="task_id" data-id="' + escapedId + '">' + escapedId + '</a>' +
      '</span>';

    if (outputPath) {
      var escapedPath = safeEsc(outputPath);
      html += '<span class="term-task-output-path">' +
        ' &rarr; <code>' + escapedPath + '</code>' +
        '</span>' +
        '<button class="term-fetch-output-btn" type="button"' +
        ' data-task-id="' + escapedId + '"' +
        ' data-output-path="' + escapedPath + '">' +
        'fetch output' +
        '</button>';
    }

    html += '</div>';
    return html;
  };

  // ── dispatch: tool → renderer routing ──

  /**
   * Tool name → renderer key mapping.
   * "auto" values indicate content-heuristic branching inside dispatch().
   * @const {Object<string, string>}
   */
  var TOOL_RENDERER_MAP = {
    "Bash": "auto",
    "Glob": "list",
    "Grep": "auto",
    "Read": "fileContent",
    "Write": "statusBadge",
    "Edit": "statusBadge",
    "ToolSearch": "schema",
    "TodoWrite": "statusBadge",
    "WebSearch": "markdown",
    "WebFetch": "markdown",
    "CronList": "auto",
    "CronCreate": "statusBadge",
    "CronDelete": "statusBadge",
    "TaskOutput": "xmlLike",
    "TaskStop": "json",
    "RemoteTrigger": "json",
    "Agent": "markdown",
    "Task": "markdown"
  };

  // Expose for external inspection / tests
  ToolResultRenderer.TOOL_RENDERER_MAP = TOOL_RENDERER_MAP;

  /**
   * Resolves an "auto" mapping to a concrete renderer key based on text heuristics.
   * @param {string} toolName
   * @param {string} text - stripLlmMeta-cleaned text
   * @returns {string} concrete renderer key
   */
  function resolveAutoRenderer(toolName, text) {
    var t = (text || '').trim();

    if (toolName === 'Bash') {
      if (/Command running in background with ID:/.test(t)) return 'taskStream';
      var lineCount = t.length === 0 ? 0 : t.split(/\n/).length;
      if (lineCount === 1 && t.length < 200) return 'statusBadge';
      return 'fallbackPlain';
    }

    if (toolName === 'Grep') {
      if (t === 'No matches found') return 'statusBadge';
      // content mode: file:lineno:content
      if (/^[^:\n]+:\d+:/m.test(t)) return 'fallbackPlain';
      // count mode: file:count  or  files_with_matches (plain paths)
      return 'list';
    }

    if (toolName === 'CronList') {
      if (t === 'No scheduled jobs.') return 'statusBadge';
      return 'list';
    }

    // Unknown auto target: safest default
    return 'fallbackPlain';
  }

  /**
   * Dispatches tool output text to the appropriate renderer.
   * Pipeline: stripLlmMeta → renderer resolution → renderer invocation (with fallback)
   *           → autoCollapse → return HTML.
   * @param {string} toolName - tool name (may be undefined/null for legacy callers)
   * @param {string} text - raw tool result text
   * @param {object} [meta] - optional metadata forwarded to renderer
   * @returns {string} HTML string
   */
  ToolResultRenderer.dispatch = function (toolName, text, meta) {
    var util = ToolResultRenderer.util;
    var renderers = ToolResultRenderer.renderers;

    // [1] Preprocess: strip LLM meta noise
    var cleanText = util.stripLlmMeta(text || '');

    // Compute raw byte length for autoCollapse threshold
    var rawByteLen;
    try {
      rawByteLen = (typeof TextEncoder !== 'undefined')
        ? new TextEncoder().encode(cleanText).length
        : cleanText.length;
    } catch (e) {
      rawByteLen = cleanText.length;
    }

    // [2] Resolve renderer key
    var mapped = toolName ? TOOL_RENDERER_MAP[toolName] : undefined;
    var rendererKey;
    if (mapped === undefined) {
      rendererKey = 'fallbackPlain';
    } else if (mapped === 'auto') {
      rendererKey = resolveAutoRenderer(toolName, cleanText);
    } else {
      rendererKey = mapped;
    }

    // [3] Invoke renderer with fallback on runtime error
    var htmlContent;
    var renderFn = renderers[rendererKey] || renderers.fallbackPlain;
    try {
      htmlContent = renderFn(cleanText, meta);
    } catch (e) {
      try {
        htmlContent = renderers.fallbackPlain(cleanText, meta);
      } catch (e2) {
        htmlContent = '<pre class="term-plain">' + util.safeEsc(cleanText) + '</pre>';
      }
    }

    // [4] Post-process: wrap in collapsible <details> when oversized
    var summary = (toolName || 'tool') + ' result';
    return util.autoCollapse(htmlContent, rawByteLen, summary);
  };

  // ── WorkflowRenderer: ANSI strip utility ──

  /**
   * Removes ANSI SGR escape sequences from text.
   * Banner scripts emit colour codes (e.g. \033[38;2;222;115;86m) that must be
   * stripped before pattern matching.
   * @param {string} text - raw text possibly containing ANSI escape codes
   * @returns {string} text with ANSI codes removed
   */
  var ANSI_STRIP_RE = /\x1b\[[0-9;]*m/g;
  function stripAnsi(text) {
    return (text || "").replace(ANSI_STRIP_RE, "");
  }

  // ── WorkflowRenderer namespace ──

  /**
   * WorkflowRenderer namespace.
   *
   * Parses Bash tool_use_result text for workflow banner patterns emitted by
   * flow-claude, flow-init, flow-step, flow-phase, and flow-finish scripts.
   * Maintains phaseTimeline state and returns consumed=true when any banner
   * line is detected, signalling callers to skip normal insertToolResult().
   *
   * This module is purely a parser + state machine (no DOM access).
   * DOM rendering is handled by W03 (renderTimelineBar / renderStatusBadge).
   *
   * Only active when isWorkflowMode === true.
   */
  var WorkflowRenderer = (function () {

    // ── Pattern constants (W01 design §1.2–1.9) ──

    var P = {
      // flow-claude start: box top border
      workflowBoxTop:    /╔[═]+╗/,
      // flow-claude start: ▶ command line inside box
      workflowStartCmd:  /║\s+▶\s+(\S+)/,
      // flow-claude end: [OK] workId · title (command)
      workflowEnd:       /║\s+\[OK\]\s+(\S+)\s+·\s+(.+?)(?:\s+\((\w+)\))?$/,
      // flow-claude end: trailing border line of ══ chars
      endBorder:         /^[═]{10,}$/,
      // flow-init: INIT title line
      init:              /║\s+INIT:\s+(.+)$/,
      // flow-init: workDir line (second line after INIT)
      initWorkDir:       /║\s+(\.claude\.workflow\/workflow\/[^\s]+)$/,
      // flow-step start: [● ○ ○] STEP_NAME inside box
      stepStart:         /║\s+\[●[^\]]*\]\s+(PLAN|WORK|REPORT|DONE)/,
      // flow-step end: [● ● ○] STEP_NAME - timestamp
      stepEnd:           /║\s+\[●[^\]]*\]\s+(PLAN|WORK|REPORT|DONE)\s+-\s+(.+)$/,
      // flow-step end artifact path line
      artifactLine:      /║\s+(\.claude\.workflow\/workflow\/[^\s]+\.(?:md|json|txt))$/,
      // flow-step [OK] label
      stepOk:            /║\s+\[OK\]\s+(\S+)$/,
      // flow-step [ASK] label
      stepAsk:           /║\s+\[ASK\]\s+(\S+)$/,
      // flow-phase: STATE Phase N mode
      phase:             /║\s+STATE:\s+Phase\s+(\d+)\s+(sequential|parallel)/,
      // flow-phase: >> agents [taskIds]
      phaseAgents:       /║\s+>>\s+([^\[]+?)(?:\s+\[([^\]]+)\])?$/,
      // flow-finish: DONE 완료 or 실패
      finishDone:        /║\s+DONE:\s+워크플로우\s+(완료|실패)/,
      // flow-finish: registryKey line
      finishKey:         /║\s+(\d{8}-\d{6})$/,
      // FAIL: bare FAIL line (initialization/finalization early exit)
      fail:              /^FAIL$/
    };

    // ── Default state (mirrors W01 design §2.2) ──

    var DEFAULT_STATE = {
      command:      "",
      workId:       "",
      title:        "",
      workDir:      "",
      currentStep:  "unknown",
      currentPhase: -1,
      phases:       [],
      artifacts:    [],
      status:       "running",
      error:        undefined
    };

    // ── Internal mutable state ──

    /** @type {Object} phaseTimeline state */
    var _state = {};

    // Parser flags for multi-line banner sequences
    /** @type {boolean} waiting for initWorkDir line after INIT line */
    var _pendingInit = false;
    /** @type {string} title captured from INIT line, awaiting workDir */
    var _pendingInitTitle = "";

    /** @type {boolean} waiting for artifact/ok/ask lines after stepEnd line */
    var _pendingStepEnd = false;
    /** @type {string} step name captured from stepEnd line */
    var _pendingStepEndName = "";
    /** @type {string} timestamp captured from stepEnd line */
    var _pendingStepEndTs = "";

    /** @type {boolean} waiting for phaseAgents line after phase line */
    var _pendingPhase = false;
    /** @type {number} phase number captured from phase line */
    var _pendingPhaseN = -1;
    /** @type {string} phase mode captured from phase line */
    var _pendingPhaseMode = "";

    /** @type {boolean} inside a ╔═╗ box (workflow start or step start) */
    var _inBox = false;
    /** @type {boolean} box seen ▶ command → confirmed workflow start (not step start) */
    var _boxHasCmd = false;

    /** @type {boolean} waiting for finishKey line after finishDone */
    var _pendingFinish = false;
    /** @type {string} "완료" or "실패" from finishDone */
    var _pendingFinishResult = "";

    // ── phaseTimeline state management methods ──

    /**
     * Resets state to defaults and optionally stores command.
     * Called when a new workflow start banner (╔═╗ + ▶ command) is detected.
     * @param {string} [command]
     */
    function _reset(command) {
      _state = {
        command:      command || "",
        workId:       "",
        title:        "",
        workDir:      "",
        currentStep:  "unknown",
        currentPhase: -1,
        phases:       [],
        artifacts:    [],
        status:       "running",
        error:        undefined
      };
      _clearParserFlags();
    }

    /**
     * Clears all multi-line parser flags.
     */
    function _clearParserFlags() {
      _pendingInit = false;
      _pendingInitTitle = "";
      _pendingStepEnd = false;
      _pendingStepEndName = "";
      _pendingStepEndTs = "";
      _pendingPhase = false;
      _pendingPhaseN = -1;
      _pendingPhaseMode = "";
      _inBox = false;
      _boxHasCmd = false;
      _pendingFinish = false;
      _pendingFinishResult = "";
    }

    /**
     * Stores INIT title+workDir and sets currentStep to "init".
     * @param {string} title
     * @param {string} workDir
     */
    function _setInit(title, workDir) {
      _state.title = title;
      _state.workDir = workDir;
      _state.currentStep = "init";
    }

    /**
     * Advances currentStep to the given step name (lowercased).
     * @param {string} stepName - "PLAN"|"WORK"|"REPORT"|"DONE"
     */
    function _setStep(stepName) {
      _state.currentStep = stepName.toLowerCase();
    }

    /**
     * Adds a new phase entry to phases[] and updates currentPhase.
     * @param {number} n - phase number
     * @param {string} mode - "sequential"|"parallel"
     * @param {string[]} [agents]
     * @param {string[]} [taskIds]
     */
    function _setPhase(n, mode, agents, taskIds) {
      _state.phases.push({
        n:       n,
        agents:  agents  || [],
        taskIds: taskIds || [],
        mode:    mode
      });
      _state.currentPhase = n;
    }

    /**
     * Adds an artifact entry.
     * @param {string} path - relative path of the artifact file
     */
    function _addArtifact(path) {
      if (!path) return;
      var label = path.split("/").pop();
      var type = "other";
      if (/plan\.md$/.test(path))   type = "plan";
      else if (/report\.md$/.test(path)) type = "report";
      else if (/work\//.test(path)) type = "work";
      _state.artifacts.push({
        type:  type,
        path:  path,
        at:    new Date().toISOString(),
        label: label
      });
    }

    /**
     * Updates workId and title from flow-claude end banner.
     * @param {string} workId
     * @param {string} title
     */
    function _setWorkflowEnd(workId, title) {
      if (workId) _state.workId = workId;
      if (title)  _state.title  = title;
    }

    /**
     * Marks the workflow as successfully completed.
     */
    function _complete() {
      _state.status      = "done";
      _state.currentStep = "done";
    }

    /**
     * Marks the workflow as failed.
     * @param {string} [msg]
     */
    function _fail(msg) {
      _state.status      = "failed";
      _state.currentStep = "failed";
      _state.error       = msg || "FAIL";
    }

    // ── Per-line pattern matching functions ──

    /**
     * Attempts to match and process a single stripped line.
     * Returns true if the line matched any banner pattern.
     * @param {string} line - ANSI-stripped, trimmed line
     * @returns {boolean}
     */
    function _parseLine(line) {
      var m;

      // ── Box-top detection (╔═══╗) ──
      if (P.workflowBoxTop.test(line)) {
        _inBox    = true;
        _boxHasCmd = false;
        return true;
      }

      // ── End-border (════) — close any pending stepEnd or workflowEnd scan ──
      if (P.endBorder.test(line)) {
        _pendingStepEnd = false;
        return true;
      }

      // ── Inside box: ▶ command → workflow start confirmed ──
      if (_inBox && (m = P.workflowStartCmd.exec(line))) {
        _boxHasCmd = true;
        _inBox     = false;
        _reset(m[1]);
        return true;
      }

      // ── Inside box: [● ...] STEP → step start ──
      if (_inBox && !_boxHasCmd && (m = P.stepStart.exec(line))) {
        _inBox = false;
        _setStep(m[1]);
        return true;
      }

      // ── Box close line ╚═══╝ (close box state without command) ──
      if (/╚[═]+╝/.test(line)) {
        _inBox     = false;
        _boxHasCmd = false;
        return true;
      }

      // ── flow-claude end: [OK] workId · title ──
      if ((m = P.workflowEnd.exec(line))) {
        _setWorkflowEnd(m[1], m[2].trim());
        return true;
      }

      // ── flow-init: INIT: title ──
      if ((m = P.init.exec(line))) {
        _pendingInit      = true;
        _pendingInitTitle = m[1].trim();
        // Clear other pending flags to avoid interference
        _pendingStepEnd = false;
        _pendingPhase   = false;
        return true;
      }

      // ── flow-init: workDir line (follows INIT line) ──
      if (_pendingInit && (m = P.initWorkDir.exec(line))) {
        _setInit(_pendingInitTitle, m[1].trim());
        _pendingInit      = false;
        _pendingInitTitle = "";
        return true;
      }

      // ── flow-step end: [● ● ○] STEP - timestamp ──
      if ((m = P.stepEnd.exec(line))) {
        _pendingStepEnd     = true;
        _pendingStepEndName = m[1];
        _pendingStepEndTs   = m[2].trim();
        // Advance step (step end updates currentStep)
        _setStep(m[1]);
        return true;
      }

      // ── Artifact line (follows step end) ──
      if ((m = P.artifactLine.exec(line))) {
        _addArtifact(m[1].trim());
        return true;
      }

      // ── [OK] / [ASK] result lines (follow step end) ──
      if (_pendingStepEnd && (P.stepOk.test(line) || P.stepAsk.test(line))) {
        _pendingStepEnd = false;
        return true;
      }

      // ── flow-phase: STATE: Phase N mode ──
      if ((m = P.phase.exec(line))) {
        _pendingPhase    = true;
        _pendingPhaseN   = parseInt(m[1], 10);
        _pendingPhaseMode = m[2];
        return true;
      }

      // ── flow-phase: >> agents [taskIds] ──
      if (_pendingPhase && (m = P.phaseAgents.exec(line))) {
        var agentsRaw = m[1].trim();
        var taskIdsRaw = m[2] ? m[2].trim() : "";
        var agents  = agentsRaw  ? agentsRaw.split(/[\s,]+/).filter(Boolean) : [];
        var taskIds = taskIdsRaw ? taskIdsRaw.split(/[\s,]+/).filter(Boolean) : [];
        _setPhase(_pendingPhaseN, _pendingPhaseMode, agents, taskIds);
        _pendingPhase     = false;
        _pendingPhaseN    = -1;
        _pendingPhaseMode = "";
        return true;
      }

      // ── flow-finish: DONE: 워크플로우 완료|실패 ──
      if ((m = P.finishDone.exec(line))) {
        _pendingFinish       = true;
        _pendingFinishResult = m[1]; // "완료" or "실패"
        return true;
      }

      // ── flow-finish: registryKey line ──
      if (_pendingFinish && (m = P.finishKey.exec(line))) {
        _pendingFinish = false;
        if (_pendingFinishResult === "완료") {
          _complete();
        } else {
          _fail("워크플로우 실패 (" + m[1] + ")");
        }
        _pendingFinishResult = "";
        return true;
      }

      // ── FAIL bare line (early exit) ──
      if (P.fail.test(line)) {
        _fail("FAIL");
        return true;
      }

      return false;
    }

    // ── Public API ──

    return {
      /**
       * phaseTimeline state accessor (read-only reference).
       * W03 DOM renderer reads this to build the timeline bar.
       * @type {Object}
       */
      get state() { return _state; },

      /**
       * Pattern constants (exposed for testing).
       * @type {Object}
       */
      patterns: P,

      /**
       * Processes raw Bash tool_use_result text.
       * Strips ANSI codes, splits into lines, and runs each through _parseLine().
       * Returns true if at least one banner pattern was matched.
       * @param {string} text - raw tool_use_result stdout text
       * @returns {boolean} true = banner(s) detected, false = no banner found
       */
      tap: function (text) {
        var stripped = stripAnsi(text);
        var lines    = stripped.split("\n");
        var consumed = false;

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim();
          if (line && _parseLine(line)) {
            consumed = true;
          }
        }

        return consumed;
      },

      /**
       * Resets the parser to its initial state.
       * Call before starting a new workflow observation.
       */
      reset: function () {
        _reset();
      }
    };
  })();

  // ── phaseTimeline DOM Renderer (W03) ──

  /**
   * phaseTimeline: DOM renderer singleton for workflow session timeline bar.
   *
   * Reads WorkflowRenderer.state and builds / updates the .wf-timeline-bar
   * element fixed below the terminal-session-bar.  Also provides
   * renderStatusBadge() for done/failed overlays and renderArtifactLinks()
   * to refresh the artifact row.
   *
   * Only active when isWorkflowMode === true.
   * All DOM mutations are guarded by `isWorkflowMode && outputDiv`.
   */
  var phaseTimeline = (function () {

    // ── Internal helpers ──

    /**
     * Returns the .wf-timeline-bar element, creating it (and inserting it
     * below .terminal-session-bar) if it does not yet exist.
     * @returns {HTMLElement|null}
     */
    function _getOrCreateBar() {
      var existing = document.getElementById("wf-timeline-bar");
      if (existing) return existing;

      var sessionBar = document.querySelector(".terminal-session-bar");
      if (!sessionBar) return null;

      var bar = document.createElement("div");
      bar.className = "wf-timeline-bar";
      bar.id = "wf-timeline-bar";

      // Insert immediately after .terminal-session-bar
      var parent = sessionBar.parentNode;
      if (parent) {
        parent.insertBefore(bar, sessionBar.nextSibling);
      }
      return bar;
    }

    /**
     * HTML-escapes a string for safe attribute / text node insertion.
     * @param {string} s
     * @returns {string}
     */
    function _esc(s) {
      return String(s || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    /**
     * Builds the HTML for the .wf-steps-row based on current state.
     * Steps: INIT → PLAN → WORK (Phase N) → REPORT → DONE
     * @param {Object} st - WorkflowRenderer.state snapshot
     * @returns {string} HTML fragment
     */
    function _buildStepsRowHtml(st) {
      var steps = ["init", "plan", "work", "report", "done", "failed"];
      var labels = { init: "INIT", plan: "PLAN", work: "WORK", report: "REPORT", done: "DONE", failed: "FAIL" };
      var current = st.currentStep || "unknown";

      var orderedSteps = ["init", "plan", "work", "report", "done"];
      // If failed, append "failed" at end
      if (current === "failed") {
        orderedSteps.push("failed");
      }

      var stepOrder = {};
      orderedSteps.forEach(function (s, i) { stepOrder[s] = i; });
      var currentIdx = stepOrder[current];

      var html = '<div class="wf-steps-row">';
      orderedSteps.forEach(function (step, idx) {
        // Determine CSS class
        var cls = "wf-timeline-step";
        if (step === current) {
          cls += " active";
        } else if (currentIdx !== undefined && idx < currentIdx) {
          cls += " done";
        } else {
          cls += " pending";
        }

        html += '<div class="' + cls + '" data-step="' + _esc(step) + '">';
        html += _esc(labels[step] || step.toUpperCase());

        // Phase badge for WORK step
        if (step === "work" && st.currentPhase >= 0) {
          html += '<span class="wf-phase-badge">Phase ' + _esc(String(st.currentPhase)) + '</span>';
        }

        html += '</div>';

        // Separator between steps (not after last)
        if (idx < orderedSteps.length - 1) {
          html += '<div class="wf-timeline-sep">&rarr;</div>';
        }
      });
      html += '</div>';
      return html;
    }

    /**
     * Builds the HTML for the .wf-meta-row.
     * @param {Object} st
     * @returns {string}
     */
    function _buildMetaRowHtml(st) {
      if (!st.command && !st.title) return "";
      var html = '<div class="wf-meta-row">';
      if (st.command) {
        html += '<span class="wf-meta-command">' + _esc(st.command) + '</span>';
        html += '<span class="wf-meta-sep">&middot;</span>';
      }
      if (st.title) {
        html += '<span class="wf-meta-title">' + _esc(st.title) + '</span>';
      }
      if (st.workId) {
        html += '<span class="wf-meta-id">#' + _esc(st.workId) + '</span>';
      }
      html += '</div>';
      return html;
    }

    /**
     * Builds the HTML for the .wf-artifacts-row.
     * @param {Array} artifacts
     * @returns {string}
     */
    function _buildArtifactsRowHtml(artifacts) {
      if (!artifacts || artifacts.length === 0) return "";
      var html = '<div class="wf-artifacts-row">';
      artifacts.forEach(function (a) {
        html += '<a class="wf-timeline-artifact" data-path="' + _esc(a.path) + '"'
          + ' href="#" title="' + _esc(a.label) + ' 열기">'
          + _esc(a.label) + '</a>';
      });
      html += '</div>';
      return html;
    }

    // ── Public API ──

    return {

      /**
       * Renders (or re-renders) the .wf-timeline-bar below .terminal-session-bar.
       * Reads WorkflowRenderer.state for current step, phase, and artifacts.
       * Guards: isWorkflowMode && outputDiv.
       */
      renderTimelineBar: function () {
        if (!isWorkflowMode || !outputDiv) return;

        var bar = _getOrCreateBar();
        if (!bar) return;

        var st = WorkflowRenderer.state;

        var html = "";
        html += _buildMetaRowHtml(st);
        html += _buildStepsRowHtml(st);
        html += _buildArtifactsRowHtml(st.artifacts);

        bar.innerHTML = html;

        // Bind artifact link click handlers
        var links = bar.querySelectorAll(".wf-timeline-artifact[data-path]");
        for (var i = 0; i < links.length; i++) {
          (function (link) {
            link.addEventListener("click", function (e) {
              e.preventDefault();
              var path = link.getAttribute("data-path");
              if (path) {
                phaseTimeline.openArtifact(path);
              }
            });
          })(links[i]);
        }
      },

      /**
       * Renders or updates the .wf-artifacts-row inside the timeline bar.
       * Called incrementally when a new artifact is added mid-session.
       */
      renderArtifactLinks: function () {
        if (!isWorkflowMode || !outputDiv) return;

        var bar = document.getElementById("wf-timeline-bar");
        if (!bar) {
          // Bar not yet created — fall back to full render
          phaseTimeline.renderTimelineBar();
          return;
        }

        var st = WorkflowRenderer.state;

        // Update or insert artifact row
        var existingRow = bar.querySelector(".wf-artifacts-row");
        var newHtml = _buildArtifactsRowHtml(st.artifacts);

        if (newHtml) {
          if (existingRow) {
            existingRow.outerHTML = newHtml;
          } else {
            bar.insertAdjacentHTML("beforeend", newHtml);
          }
          // Re-bind click handlers on the updated row
          var links = bar.querySelectorAll(".wf-timeline-artifact[data-path]");
          for (var i = 0; i < links.length; i++) {
            (function (link) {
              link.addEventListener("click", function (e) {
                e.preventDefault();
                var path = link.getAttribute("data-path");
                if (path) phaseTimeline.openArtifact(path);
              });
            })(links[i]);
          }
        } else if (existingRow) {
          existingRow.parentNode.removeChild(existingRow);
        }
      },

      /**
       * Renders a completion or failure status badge inside .terminal-output.
       * The badge uses `position: sticky; bottom: 0` so it anchors to the
       * bottom of the visible output area without covering the timeline bar.
       *
       * @param {"ok"|"fail"} status
       * @param {string} [msg] - optional detail text shown in .wf-badge-sub
       */
      renderStatusBadge: function (status, msg) {
        if (!isWorkflowMode || !outputDiv) return;

        var follow = isNearBottom(outputDiv);

        // Remove any existing badge first
        var existing = outputDiv.querySelector(".wf-status-badge");
        if (existing) existing.parentNode.removeChild(existing);

        var st = WorkflowRenderer.state;
        var isOk = (status === "ok");

        var badge = document.createElement("div");
        badge.className = "wf-status-badge";
        badge.setAttribute("data-status", isOk ? "ok" : "fail");

        var iconChar = isOk ? "&#10003;" : "&#10005;";
        var labelText = isOk ? "워크플로우 완료" : "워크플로우 실패";
        var subText = msg || (isOk
          ? ("#" + (st.workId || "") + " · " + (st.title || ""))
          : (st.error || "FAIL"));

        badge.innerHTML =
          '<span class="wf-badge-icon">' + iconChar + '</span>' +
          '<span class="wf-badge-text">' + _esc(labelText) + '</span>' +
          '<span class="wf-badge-sub">' + _esc(subText) + '</span>';

        outputDiv.appendChild(badge);
        scrollToBottomIfFollowing(outputDiv, follow);
      },

      /**
       * Full render helper called by WorkflowRenderer.tap() integration (W04).
       * Runs renderTimelineBar() and, if workflow ended, renderStatusBadge().
       */
      render: function () {
        phaseTimeline.renderTimelineBar();

        var st = WorkflowRenderer.state;
        if (st.status === "done") {
          phaseTimeline.renderStatusBadge("ok");
        } else if (st.status === "failed") {
          phaseTimeline.renderStatusBadge("fail", st.error);
        }
      },

      /**
       * Opens an artifact file.  Currently opens via
       * `/api/workflow/artifact?path=<encoded>` in a new tab, falling back to
       * a simple alert.  W05 will provide the actual server route.
       * @param {string} path - relative artifact path
       */
      openArtifact: function (path) {
        var url = "/api/workflow/artifact?path=" + encodeURIComponent(path);
        window.open(url, "_blank");
      },

      /**
       * Inserts the .wf-timeline-bar placeholder immediately below
       * .terminal-session-bar at page initialization time.
       * Called from renderTerminal() when isWorkflowMode === true.
       */
      insertPlaceholder: function () {
        if (!isWorkflowMode) return;
        _getOrCreateBar();
      }

    };
  })();

  // ── Tool Box Renderer ──

  /**
   * Creates a collapsible tool use box with <details> + <summary>.
   * @param {string} toolName - name of the tool
   * @returns {HTMLElement} the <details> element
   */
  function createToolBox(toolName) {
    var icon = TOOL_ICONS[toolName] || DEFAULT_TOOL_ICON;

    var details = document.createElement("details");
    details.className = "term-tool-box";
    // Store tool name for downstream dispatch lookup (insertToolResult)
    if (toolName) {
      details.setAttribute("data-tool-name", toolName);
    }

    var summary = document.createElement("summary");
    summary.textContent = icon + " " + toolName;
    details.appendChild(summary);

    var resultDiv = document.createElement("div");
    resultDiv.className = "term-tool-result";
    details.appendChild(resultDiv);

    appendToOutput(details);
    currentToolBox = details;

    return details;
  }

  /**
   * Inserts tool result text into the current tool box.
   * Keeps the <details> closed (user can click to expand).
   * Routes through ToolResultRenderer.dispatch for per-tool rendering.
   * Backward compatible: the 2-argument form (text, isError) is still supported —
   * when toolName is omitted, dispatch falls back to fallbackPlain via its
   * undefined-mapping branch.
   * @param {string} text - result text
   * @param {boolean} [isError] - whether this is an error result
   * @param {string} [toolName] - optional tool name (falls back to currentToolBox dataset)
   */
  function insertToolResult(text, isError, toolName) {
    if (!currentToolBox) return;
    var resultDiv = currentToolBox.querySelector(".term-tool-result");
    if (!resultDiv) return;

    // Resolve tool name: explicit arg > dataset on current box
    var resolvedToolName = toolName;
    if (!resolvedToolName && currentToolBox.getAttribute) {
      resolvedToolName = currentToolBox.getAttribute("data-tool-name") || undefined;
    }

    var html;
    try {
      html = ToolResultRenderer.dispatch(resolvedToolName, text, { isError: !!isError });
    } catch (e) {
      // Defensive fallback if dispatch itself throws (should not happen)
      html = '<pre class="term-plain">' + esc(text || '') + '</pre>';
    }

    var container = document.createElement("div");
    container.className = isError ? "term-tool-error" : "term-tool-result-rendered";
    container.innerHTML = html;
    resultDiv.appendChild(container);

    // Keep closed
    currentToolBox.removeAttribute("open");
  }

  // ── Thinking Spinner ──

  /** @type {HTMLElement|null} thinking spinner element */
  var thinkingEl = null;

  function startSpinner() {
    if (thinkingEl) return;
    if (!outputDiv) return;

    thinkingEl = document.createElement("div");
    thinkingEl.className = "term-thinking";
    thinkingEl.id = "term-thinking-active";
    thinkingEl.innerHTML = '<span class="term-thinking-dot"></span> Thinking...';
    appendToOutput(thinkingEl);
  }

  function stopSpinner() {
    if (thinkingEl && thinkingEl.parentNode) {
      thinkingEl.parentNode.removeChild(thinkingEl);
    }
    thinkingEl = null;
  }

  // ── Copy Panel ──

  /** @type {string} plain text log of all terminal output */
  var plainLog = "";
  /** @type {boolean} whether textarea view is active */
  var textViewActive = false;

  function appendPlainLog(text) {
    plainLog += text;
    var ta = document.getElementById("terminal-text-output");
    if (ta && textViewActive) {
      var follow = isNearBottom(ta);
      ta.value = plainLog;
      scrollToBottomIfFollowing(ta, follow);
    }
  }

  function toggleTextView() {
    textViewActive = !textViewActive;
    var outputEl = document.getElementById("terminal-output");
    var textEl = document.getElementById("terminal-text-output");
    var btn = document.getElementById("terminal-copy-btn");
    if (!outputEl || !textEl) return;

    if (textViewActive) {
      outputEl.style.display = "none";
      textEl.style.display = "block";
      textEl.value = plainLog;
      textEl.scrollTop = textEl.scrollHeight;
      if (btn) btn.textContent = "Terminal";
    } else {
      outputEl.style.display = "";
      textEl.style.display = "none";
      if (btn) btn.textContent = "Text";
    }
  }

  // ── Utility ──

  /**
   * Sends a POST request with JSON body to the given path.
   * @param {string} path - URL path (e.g. "/terminal/start")
   * @param {Object} [body] - JSON body to send
   * @returns {Promise<Object>} parsed JSON response
   */
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
   * Fetches current terminal status from the server.
   * @returns {Promise<void>}
   */
  function fetchStatus() {
    return fetch(endpoints().status, { cache: "no-store" }).then(function (res) {
      if (!res.ok) return;
      return res.json();
    }).then(function (data) {
      if (!data) return;
      Board.state.termStatus = data.status || "stopped";
      Board.state.termSessionId = data.session_id || null;
      if (data.model) {
        var raw = data.model;
        var ctxMatch = raw.match(/\[(\d+)([mk])\]/i);
        if (ctxMatch) {
          contextWindow = ctxMatch[2].toLowerCase() === "m" ? parseInt(ctxMatch[1]) * 1000000 : parseInt(ctxMatch[1]) * 1000;
        }
        var clean = raw.replace(/\[.*\]/, "").replace(/^claude-/, "");
        clean = clean.replace(/-(\d+)-(\d+)/, " $1.$2").replace(/-/g, " ");
        sessionModel = clean.charAt(0).toUpperCase() + clean.slice(1);
      }
      if (data.permission_mode) {
        var modeEl = document.getElementById("terminal-sl-mode");
        if (modeEl) modeEl.textContent = data.permission_mode;
      }
      if (data.branch) {
        var branchEl = document.getElementById("terminal-sl-branch");
        if (branchEl) branchEl.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:3px"><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M6 15V9a6 6 0 0 0 6-6h0a6 6 0 0 0 6 6"/></svg>' + data.branch;
      }
      updateControlBar();
    }).catch(function () {});
  }

  // ── SSE Connection ──

  /**
   * Returns a Promise that resolves when the SSE connection is open.
   * If the connection is already open, resolves immediately.
   * Otherwise calls connectSSE() and waits for the open event (timeout: 5s).
   * @returns {Promise<void>}
   */
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

  /**
   * Connects to the terminal SSE event stream.
   * Handles stdout, result, system, and permission events.
   * All output is rendered as HTML div elements (no xterm.js dependency).
   */
  function connectSSE() {
    disconnectSSE();

    termEventSource = new EventSource(endpoints().events);

    termEventSource.addEventListener("open", function () {
      Board.state.termConnected = true;
      updateControlBar();
    });

    termEventSource.addEventListener("stdout", function (e) {
      try {
        var data = JSON.parse(e.data);

        if (data.chunk && data.kind === "text_delta") {
          receivedChunks = true;
          textBuffer += data.chunk;
        } else if (data.text && data.kind === "assistant" && !receivedChunks) {
          textBuffer += data.text;
        } else if (data.kind === "content_block_start" && data.raw) {
          var block = data.raw.content_block || {};
          if (block.type === "tool_use" && block.name) {
            createToolBox(block.name);
            appendPlainLog("\n" + (TOOL_ICONS[block.name] || DEFAULT_TOOL_ICON) + " " + block.name + "\n");
          }
        } else if (data.kind === "user" && data.raw) {
          var tr = data.raw.tool_use_result;
          var mc = data.raw.message && data.raw.message.content;
          var resultText = "";

          if (tr) {
            if (tr.stdout) resultText = tr.stdout;
            else if (tr.file && tr.file.content) resultText = tr.file.content;
            else if (typeof tr.content === "string") resultText = tr.content;
          }
          if (!resultText && mc && mc[0] && typeof mc[0].content === "string") {
            resultText = mc[0].content;
          }

          if (resultText) {
            // W04: WorkflowRenderer tap integration
            // In workflow mode, try to parse banner patterns first.
            // If tap() returns true (banner detected), render the timeline and
            // skip the normal insertToolResult() path to avoid double-rendering.
            var bannerConsumed = false;
            if (isWorkflowMode) {
              try {
                bannerConsumed = WorkflowRenderer.tap(resultText);
                if (bannerConsumed) {
                  phaseTimeline.render();
                }
              } catch (tapErr) {
                // Fallback: if tap/render throws, proceed with normal rendering
                bannerConsumed = false;
              }
            }
            if (!bannerConsumed) {
              insertToolResult(resultText, false);
            }
            appendPlainLog(resultText + "\n");
          }
          if (tr && tr.stderr) {
            insertToolResult("[stderr] " + tr.stderr, true);
            appendPlainLog("[stderr] " + tr.stderr + "\n");
          }
          if (mc && mc[0] && mc[0].is_error) {
            insertToolResult("[Tool Error]", true);
            appendPlainLog("[Tool Error]\n");
          }
        }
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("result", function (e) {
      try {
        var data = JSON.parse(e.data);
        if (data.done) {
          stopSpinner();
          // cost_usd: 세션 누적값 (assign) / tokens: 해당 턴 값 (assign)
          if (typeof data.cost_usd === "number") sessionCost = data.cost_usd;
          if (typeof data.input_tokens === "number") sessionTokens.input = data.input_tokens;
          if (typeof data.output_tokens === "number") sessionTokens.output = data.output_tokens;

          if (textBuffer) {
            var html = renderMarkdownToHtml(textBuffer);
            appendHtmlBlock(html, "term-message term-assistant");
            appendPlainLog("\n" + textBuffer + "\n");
          }
          textBuffer = "";
          currentToolBox = null;

          appendSystemMessage("Response complete");

          Board.state.termStatus = "idle";
          receivedChunks = false;
          setInputLocked(false);
          updateControlBar();
        }
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("system", function (e) {
      try {
        var data = JSON.parse(e.data);
        if (data.subtype === "init" && data.session_id) {
          Board.state.termSessionId = data.session_id;
          Board.state.termStatus = "idle";
          // NOTE: 토큰/비용 리셋은 process_exit에서만 수행 (init은 세션 재연결 시에도 fire됨)
          // Extract model and context window from raw init data
          if (data.raw && data.raw.model) {
            var rawModel = data.raw.model;
            var ctxMatch = rawModel.match(/\[(\d+)([mk])\]/i);
            if (ctxMatch) {
              var ctxNum = parseInt(ctxMatch[1]);
              contextWindow = ctxMatch[2].toLowerCase() === "m" ? ctxNum * 1000000 : ctxNum * 1000;
            }
            var clean = rawModel.replace(/\[.*\]/, "").replace(/^claude-/, "");
            clean = clean.replace(/-(\d+)-(\d+)/, " $1.$2").replace(/-/g, " ");
            clean = clean.charAt(0).toUpperCase() + clean.slice(1);
            sessionModel = clean;
          }
          // Permission mode
          if (data.raw && data.raw.permissionMode) {
            var modeEl = document.getElementById("terminal-sl-mode");
            if (modeEl) modeEl.textContent = data.raw.permissionMode;
          }
          appendSystemMessage("Session started");
          setInputLocked(false);
          updateControlBar();
        } else if (data.subtype === "process_exit") {
          Board.state.termStatus = "stopped";
          Board.state.termSessionId = null;
          // 세션 종료 시 누적 토큰/비용 리셋
          sessionCost = 0;
          sessionTokens = { input: 0, output: 0 };
          stopSpinner();
          var exitCode = data.exit_code;
          if (exitCode !== 0 && exitCode !== 143 && exitCode !== undefined) {
            appendErrorMessage("Process exited with code " + exitCode);
          }
          setInputLocked(false);
          updateControlBar();
        }
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("permission", function (e) {
      try {
        var data = JSON.parse(e.data);
        var div = document.createElement("div");
        div.className = "term-system term-permission";
        div.innerHTML = '<span class="term-permission-label">[Permission Request]</span> ' + esc(data.description || "Tool use requested");
        appendToOutput(div);
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("error", function (e) {
      try {
        var data = JSON.parse(e.data);
        // Kill(143) / normal exit(0) — ignore
        if (data.exit_code === 143 || data.exit_code === 0) return;
        stopSpinner();
        appendErrorMessage("[Error] " + (data.message || "Process error"));
        Board.state.termStatus = "stopped";
        Board.state.termSessionId = null;
        setInputLocked(false);
        updateControlBar();
      } catch (err) {
        // Ignore non-JSON error events
      }
    });

    termEventSource.onerror = function () {
      Board.state.termConnected = false;
      termEventSource.close();
      termEventSource = null;
      updateControlBar();

      // Schedule reconnection
      if (!reconnectTimerId) {
        reconnectTimerId = setTimeout(function () {
          reconnectTimerId = null;
          connectSSE();
        }, SSE_RECONNECT_INTERVAL);
      }
    };
  }

  /**
   * Disconnects the terminal SSE event stream.
   */
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

  // ── Input Management ──

  /**
   * Sets the input locked state and updates the UI accordingly.
   * @param {boolean} locked - Whether input should be locked
   */
  function setInputLocked(locked) {
    inputLocked = locked;
    var input = document.getElementById("terminal-input");
    var sendBtn = document.getElementById("terminal-send-btn");
    if (input) {
      input.disabled = locked || Board.state.termStatus === "stopped";
      if (!locked && Board.state.termStatus !== "stopped") {
        input.focus();
      }
    }
    if (sendBtn) {
      sendBtn.disabled = locked || Board.state.termStatus === "stopped";
    }
  }

  /**
   * Sends user input text to the terminal server.
   * Displays input as a user message in the output div.
   */
  function sendInput() {
    var input = document.getElementById("terminal-input");
    if (!input) return;
    var text = input.value.trim();
    if (!text) return;
    if (inputLocked || Board.state.termStatus === "stopped") return;

    // Display user input as HTML message
    var div = document.createElement("div");
    div.className = "term-message term-user";
    div.textContent = text;
    appendToOutput(div);
    appendPlainLog("\n> " + text + "\n");

    setInputLocked(true);
    startSpinner();
    Board.state.termStatus = "running";
    updateControlBar();
    input.value = "";
    input.style.height = "auto";

    var ep = endpoints();
    postJson(ep.input, ep.inputBody({ text: text })).catch(function (err) {
      stopSpinner();
      appendErrorMessage("[Error] " + err.message);
      setInputLocked(false);
      Board.state.termStatus = "idle";
      updateControlBar();
    });
  }

  // ── Session Management ──

  /**
   * Starts a new Claude Code session.
   * Ensures SSE connection is ready before calling /terminal/start so that
   * the system/init event is never missed.
   */
  function startSession() {
    if (Board.state.termStatus === "running") return;
    if (isWorkflowMode) {
      // Workflow sessions are started by flow-launcher, not by the UI.
      // Just connect SSE to the already-running session.
      clearOutput();
      appendSystemMessage("Connecting to workflow session " + workflowSessionId + "...");
      connectSSEReady().catch(function (err) {
        appendErrorMessage("[Error] SSE connect failed: " + err.message);
      });
      return;
    }

    clearOutput();
    appendSystemMessage("Starting session...");

    Board.state.termStatus = "running";
    updateControlBar();

    connectSSEReady().then(function () {
      return postJson("/terminal/start");
    }).then(function (data) {
      if (data.session_id) {
        Board.state.termSessionId = data.session_id;
        Board.state.termStatus = "idle";
        updateControlBar();
      }
      startSpinner();
      setInputLocked(true);
      postJson("/terminal/input", { text: "첫 메시지입니다. '세션이 초기화 되었습니다.' 라고만 답하세요." }).catch(function () {});
    }).catch(function (err) {
      appendErrorMessage("[Error] Failed to start session: " + err.message);
      Board.state.termStatus = "stopped";
      updateControlBar();
    });
  }

  /**
   * Kills the current Claude Code session.
   */
  function killSession() {
    if (Board.state.termStatus === "stopped") return;

    var epK = endpoints();
    postJson(epK.kill, epK.inputBody({})).then(function () {
      appendSystemMessage("Session terminated");
      Board.state.termStatus = "stopped";
      Board.state.termSessionId = null;
      setInputLocked(false);
      updateControlBar();
    }).catch(function (err) {
      appendErrorMessage("[Error] Failed to kill session: " + err.message);
    });
  }

  // ── Output Clear ──

  /**
   * Clears the output div contents.
   */
  function clearOutput() {
    if (outputDiv) {
      outputDiv.innerHTML = "";
    }
    plainLog = "";
  }

  // ── UI Update ──

  /**
   * Updates the control bar UI to reflect current session state.
   * Called whenever state changes occur.
   */
  function updateControlBar() {
    var startBtn = document.getElementById("terminal-start-btn");
    var killBtn = document.getElementById("terminal-kill-btn");
    var statusDot = document.getElementById("terminal-status-dot");
    var statusText = document.getElementById("terminal-status-text");
    if (startBtn) {
      if (isWorkflowMode) {
        startBtn.style.display = "none";
      } else {
        // 세션이 이미 존재하면(idle/running) Start 비활성화 — stopped일 때만 활성
        startBtn.disabled = Board.state.termStatus !== "stopped";
      }
    }
    if (killBtn) {
      killBtn.disabled = Board.state.termStatus === "stopped";
    }
    if (statusDot) {
      statusDot.className = "terminal-status-dot terminal-status-" + Board.state.termStatus;
    }
    var statusContainer = document.querySelector(".terminal-status");
    if (statusContainer) {
      statusContainer.setAttribute("data-state", Board.state.termStatus);
    }
    if (statusText) {
      statusText.textContent = Board.state.termStatus;
    }
    var sessionIdEl = document.getElementById("terminal-session-id");
    if (sessionIdEl) {
      sessionIdEl.textContent = Board.state.termSessionId || '';
    }

    // Update status line
    updateStatusLine();

    // Update input field state
    setInputLocked(inputLocked);
  }

  function updateStatusLine() {
    var slModel = document.getElementById("terminal-sl-model");
    var slTokens = document.getElementById("terminal-sl-tokens");
    var slCost = document.getElementById("terminal-sl-cost");

    if (slModel) slModel.textContent = sessionModel;

    // Branch: add git branch SVG icon prefix if element has content
    var slBranch = document.getElementById("terminal-sl-branch");
    if (slBranch) {
      var branchText = slBranch.textContent.replace(/^\ue0a0\s*/, "").trim();
      if (!branchText || branchText === "--") branchText = slBranch.textContent.trim();
      // Strip any previous icon (SVG or text)
      var existingSvg = slBranch.querySelector("svg");
      if (existingSvg) {
        branchText = slBranch.textContent.trim();
        existingSvg.remove();
      }
      if (branchText && branchText !== "--") {
        slBranch.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:3px"><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M6 15V9a6 6 0 0 0 6-6h0a6 6 0 0 0 6 6"/></svg>' + branchText;
      }
    }

    // Context progress bar
    var totalTokens = sessionTokens.input + sessionTokens.output;
    var pct = contextWindow > 0 ? Math.min(totalTokens / contextWindow * 100, 100) : 0;
    var barFill = document.getElementById("terminal-sl-bar-fill");
    var barPct = document.getElementById("terminal-sl-bar-pct");
    if (barFill) barFill.style.width = pct.toFixed(1) + "%";
    if (barPct) barPct.textContent = pct.toFixed(1) + "%";

    // Token display
    if (slTokens) {
      var fmtTotal = totalTokens >= 1000 ? Math.round(totalTokens / 1000) + "k" : totalTokens;
      var fmtCtx = contextWindow >= 1000000 ? (contextWindow / 1000000) + "M" : Math.round(contextWindow / 1000) + "k";
      slTokens.textContent = "(" + fmtTotal + "/" + fmtCtx + ")";
    }

    if (slCost) slCost.textContent = "$" + sessionCost.toFixed(4);
  }

  // ── Main Render ──

  /**
   * Detects whether running in SPA mode (index.html) or standalone mode (terminal.html).
   * SPA mode:        document.getElementById("view-terminal") exists
   * Standalone mode: document.getElementById("terminal-standalone") or <body> fallback
   * @returns {HTMLElement|null} container element, or null if not available
   */
  function getContainer() {
    var spaEl = document.getElementById("view-terminal");
    if (spaEl) return spaEl;
    var standaloneEl = document.getElementById("terminal-standalone");
    if (standaloneEl) return standaloneEl;
    return null;
  }

  /**
   * Main Terminal tab render entry point.
   * On first call, builds the full terminal UI layout, initializes the HTML
   * div output container and SSE connection. On subsequent calls (tab
   * re-activation), only updates the control bar state without
   * destroying/rebuilding the DOM, so that output history is preserved
   * across tab switches.
   *
   * Supports dual mode:
   *  - SPA mode (index.html): renders into #view-terminal
   *  - Standalone mode (terminal.html): renders into #terminal-standalone
   */
  function renderTerminal() {
    var el = getContainer();
    if (!el) return;

    // If already initialized and the DOM container still exists, just refresh state
    if (termInitialized && document.getElementById("terminal-output")) {
      updateControlBar();
      return;
    }

    var h = "";

    // Terminal container
    h += '<div class="terminal-container">';

    // Session control bar
    h += '<div class="terminal-session-bar">';
    h += '<div class="terminal-session-left">';
    h += '<div class="terminal-status" data-state="' + esc(Board.state.termStatus) + '">';
    h += '<span class="terminal-status-dot terminal-status-' + esc(Board.state.termStatus) + '" id="terminal-status-dot"></span>';
    h += '<span class="terminal-status-text" id="terminal-status-text">' + esc(Board.state.termStatus) + '</span>';
    h += '</div>';
    h += '<span class="terminal-session-id" id="terminal-session-id">'
      + esc(Board.state.termSessionId || '')
      + '</span>';
    h += '</div>';
    h += '<div class="terminal-session-controls">';
    h += '<button class="terminal-btn terminal-btn-start" id="terminal-start-btn">Start</button>';
    h += '<button class="terminal-btn terminal-btn-kill" id="terminal-kill-btn">Kill</button>';
    h += '<button class="terminal-btn terminal-btn-copy" id="terminal-copy-btn" title="Toggle text view (F2)">Text</button>';
    h += '<span class="terminal-controls-divider"></span>';
    h += '<button class="terminal-btn terminal-btn-sessions" id="terminal-sessions-btn" title="Workflow sessions">';
    h += '<span id="terminal-sessions-label">Sessions</span>';
    h += '<span class="terminal-sessions-count" id="terminal-sessions-count" style="display:none"></span>';
    h += '</button>';
    h += '<div class="terminal-sessions-dropdown" id="terminal-sessions-dropdown"></div>';
    h += '<span class="terminal-controls-divider"></span>';
    h += '<button class="terminal-btn terminal-btn-settings" id="terminal-settings-btn" title="Settings">';
    h += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">';
    h += '<circle cx="12" cy="12" r="3"/>';
    h += '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>';
    h += '</svg></button>';
    h += '</div>';
    // Settings dropdown (hidden by default)
    h += '<div class="terminal-settings-dropdown" id="terminal-settings-dropdown">';
    h += '<button class="terminal-settings-item" id="terminal-restart-server">Restart Server</button>';
    h += '<button class="terminal-settings-item" id="terminal-clear-output">Clear Output</button>';
    h += '</div>';
    h += '</div>';

    // HTML div output area
    h += '<div class="terminal-output" id="terminal-output"></div>';
    h += '<textarea class="terminal-text-output" id="terminal-text-output" readonly spellcheck="false" style="display:none"></textarea>';

    // Input card (Claude-style)
    h += '<div class="terminal-input-card">';
    h += '<textarea class="terminal-input" id="terminal-input"'
      + ' placeholder="메시지를 입력하세요..." rows="1"'
      + ' autocomplete="off" spellcheck="false"'
      + (Board.state.termStatus === "stopped" ? " disabled" : "")
      + '></textarea>';
    h += '<div class="terminal-input-bottom">';
    h += '<div class="terminal-input-bottom-left"></div>';
    h += '<div class="terminal-input-bottom-right">';
    h += '<span class="terminal-input-hint">Enter 전송 · Shift+Enter 줄바꿈</span>';
    h += '<button class="terminal-send-btn" id="terminal-send-btn"'
      + (Board.state.termStatus === "stopped" ? " disabled" : "")
      + '><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg></button>';
    h += '</div>';
    h += '</div>';
    h += '</div>';

    // Status line
    h += '<div class="terminal-statusline" id="terminal-statusline">';
    h += '<span class="terminal-sl-model" id="terminal-sl-model">--</span>';
    h += '<span class="terminal-sl-branch" id="terminal-sl-branch">--</span>';
    h += '<span class="terminal-sl-bar" id="terminal-sl-bar"><span class="terminal-sl-bar-track"><span class="terminal-sl-bar-fill" id="terminal-sl-bar-fill" style="width:0%"></span></span><span id="terminal-sl-bar-pct">0%</span></span>';
    h += '<span class="terminal-sl-tokens" id="terminal-sl-tokens">(0/0)</span>';
    h += '<span class="terminal-sl-right">';
    h += '<span class="terminal-sl-mode" id="terminal-sl-mode"></span>';
    h += '<span id="terminal-sl-cost">$0.00</span>';
    h += '<span id="terminal-sl-port">port:' + location.port + '</span>';
    h += '</span>';
    h += '</div>';

    h += '</div>'; // .terminal-container

    el.innerHTML = h;

    // Initialize HTML div output container
    initOutputDiv();

    // Workflow mode: insert timeline bar placeholder below session-bar
    if (isWorkflowMode) {
      phaseTimeline.insertPlaceholder();
    }

    // Connect SSE if not already connected
    if (!termEventSource) {
      connectSSE();
    }
    // Fetch initial status
    fetchStatus();

    // Bind event handlers
    var startBtn = document.getElementById("terminal-start-btn");
    var killBtn = document.getElementById("terminal-kill-btn");
    var sendBtn = document.getElementById("terminal-send-btn");
    var inputEl = document.getElementById("terminal-input");

    if (startBtn) {
      startBtn.addEventListener("click", startSession);
    }
    if (killBtn) {
      killBtn.addEventListener("click", killSession);
    }
    if (sendBtn) {
      sendBtn.addEventListener("click", sendInput);
    }

    // Settings dropdown
    var settingsBtn = document.getElementById("terminal-settings-btn");
    var settingsDropdown = document.getElementById("terminal-settings-dropdown");
    if (settingsBtn && settingsDropdown) {
      settingsBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        settingsDropdown.classList.toggle("visible");
      });
      document.addEventListener("click", function () {
        settingsDropdown.classList.remove("visible");
      });
    }
    var restartBtn = document.getElementById("terminal-restart-server");
    if (restartBtn) {
      restartBtn.addEventListener("click", function () {
        settingsDropdown.classList.remove("visible");
        postJson("/api/restart").then(function () {
          setTimeout(function () { location.reload(); }, 1500);
        }).catch(function () {
          setTimeout(function () { location.reload(); }, 2000);
        });
      });
    }
    var clearBtn = document.getElementById("terminal-clear-output");
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        settingsDropdown.classList.remove("visible");
        clearOutput();
      });
    }
    var copyBtn = document.getElementById("terminal-copy-btn");
    if (copyBtn) {
      copyBtn.addEventListener("click", toggleTextView);
    }
    if (inputEl) {
      inputEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendInput();
          return;
        }
        e.stopPropagation();
      });
      // Auto-resize textarea
      inputEl.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 120) + "px";
      });
    }

    // Keyboard shortcuts (document-level, skip when input focused)
    document.addEventListener("keydown", function (e) {
      if (document.activeElement && document.activeElement.tagName === "TEXTAREA") return;
      // F2 or Ctrl+Shift+C: toggle text view
      if (e.key === "F2" || (e.ctrlKey && e.shiftKey && (e.key === "C" || e.key === "c"))) {
        e.preventDefault();
        toggleTextView();
      }
    });

    termInitialized = true;

    // Workflow sessions dropdown — wire up
    var sessionsBtn = document.getElementById("terminal-sessions-btn");
    var sessionsDropdown = document.getElementById("terminal-sessions-dropdown");
    if (sessionsBtn && sessionsDropdown) {
      sessionsBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        sessionsDropdown.classList.toggle("visible");
      });
      document.addEventListener("click", function () {
        sessionsDropdown.classList.remove("visible");
      });
    }
    refreshWorkflowSessions();
    setInterval(refreshWorkflowSessions, 5000);

    // Fetch branch on load
    fetch("/api/branch").then(function (r) { return r.json(); }).then(function (d) {
      if (d.branch) {
        var el = document.getElementById("terminal-sl-branch");
        if (el) el.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:3px"><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M6 15V9a6 6 0 0 0 6-6h0a6 6 0 0 0 6 6"/></svg>' + d.branch;
      }
    }).catch(function () {});
  }

  // ── Workflow sessions list ──

  /**
   * Fetches the active workflow sessions and updates the dropdown + count.
   */
  /**
   * Purges a stopped workflow session (removes metadata + disk file).
   */
  function purgeSession(sid) {
    return fetch("/terminal/workflow/kill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sid, purge: true }),
    }).then(function () { refreshWorkflowSessions(); });
  }

  /**
   * Purges all stopped sessions in the current list.
   */
  function purgeAllStopped() {
    fetch("/terminal/workflow/list", { cache: "no-store" }).then(function (r) {
      return r.json();
    }).then(function (sessions) {
      var stopped = (sessions || []).filter(function (s) { return s.status === "stopped"; });
      return Promise.all(stopped.map(function (s) { return purgeSession(s.session_id); }));
    }).catch(function () {});
  }

  function refreshWorkflowSessions() {
    fetch("/terminal/workflow/list", { cache: "no-store" }).then(function (r) {
      return r.json();
    }).then(function (sessions) {
      sessions = Array.isArray(sessions) ? sessions : [];

      // 그룹 분리: running / stopped
      var running = sessions.filter(function (s) { return s.status === "running"; });
      var stopped = sessions.filter(function (s) { return s.status !== "running"; });

      // 정렬: created_at 역순 (최신이 위)
      var byDateDesc = function (a, b) { return (b.created_at || "").localeCompare(a.created_at || ""); };
      running.sort(byDateDesc);
      stopped.sort(byDateDesc);

      // 카운트 배지: 실행 중만 강조
      var countEl = document.getElementById("terminal-sessions-count");
      var dropdown = document.getElementById("terminal-sessions-dropdown");
      if (countEl) {
        if (running.length > 0) {
          countEl.textContent = running.length;
          countEl.style.display = "";
        } else {
          countEl.style.display = "none";
        }
      }
      if (!dropdown) return;

      // 세션 1개를 HTML row로 렌더
      var renderRow = function (s) {
        if (s.session_id === workflowSessionId) return "";
        var url = "terminal.html?session=" + encodeURIComponent(s.session_id);
        var time = (s.created_at || "").slice(11, 16); // HH:MM 부분만
        var html = '';
        html += '<div class="terminal-sessions-row" data-status="' + (s.status || "") + '">';
        html += '<a class="terminal-sessions-item" href="' + url + '">';
        html += '<span class="terminal-sessions-item-ticket">' + (s.ticket_id || "") + '</span>';
        html += '<span class="terminal-sessions-item-label">' + (s.command || "") + '</span>';
        html += '<span class="terminal-sessions-item-time">' + time + '</span>';
        html += '<span class="terminal-sessions-item-status" data-status="' + (s.status || "") + '">' + (s.status || "") + '</span>';
        html += '</a>';
        if (s.status !== "running") {
          html += '<button class="terminal-sessions-purge" data-sid="' + s.session_id + '" title="Remove">×</button>';
        }
        html += '</div>';
        return html;
      };

      var h = "";
      // "Main" link (워크플로우 모드일 때만)
      if (isWorkflowMode) {
        h += '<a class="terminal-sessions-item terminal-sessions-main" href="terminal.html">';
        h += '<span class="terminal-sessions-item-label">↩ Main session</span>';
        h += '</a>';
        h += '<div class="terminal-sessions-divider"></div>';
      }

      if (running.length > 0) {
        h += '<div class="terminal-sessions-header">Running (' + running.length + ')</div>';
        running.forEach(function (s) { h += renderRow(s); });
      }
      if (stopped.length > 0) {
        if (running.length > 0) h += '<div class="terminal-sessions-divider"></div>';
        h += '<div class="terminal-sessions-header">Stopped (' + stopped.length + ') <button class="terminal-sessions-clear-all" id="terminal-sessions-clear-all">Clear all</button></div>';
        stopped.forEach(function (s) { h += renderRow(s); });
      }
      if (running.length === 0 && stopped.length === 0 && !isWorkflowMode) {
        h += '<div class="terminal-sessions-empty">No workflow sessions</div>';
      }
      dropdown.innerHTML = h;

      // Wire purge buttons
      dropdown.querySelectorAll(".terminal-sessions-purge").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          purgeSession(btn.getAttribute("data-sid"));
        });
      });
      var clearAll = document.getElementById("terminal-sessions-clear-all");
      if (clearAll) {
        clearAll.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          if (confirm("Remove all " + stopped.length + " stopped session(s)?")) {
            purgeAllStopped();
          }
        });
      }
    }).catch(function () {});
  }

  // ── Cleanup ──

  /**
   * Cleans up terminal resources when the tab is deactivated.
   * Called externally if needed.
   */
  function cleanupTerminal() {
    disconnectSSE();
    outputDiv = null;
    currentToolBox = null;
    thinkingEl = null;
    termInitialized = false;
  }

  // ── Hook into switchTab (SPA mode only) ──
  if (Board.util.switchTab) {
    var originalSwitchTab = Board.util.switchTab;
    Board.util.switchTab = function (target, skipPush) {
      originalSwitchTab(target, skipPush);
      if (target === "terminal" && Board.render.renderTerminal) {
        Board.render.renderTerminal();
      }
    };
  }

  // Also re-bind existing tab click listeners
  document.querySelectorAll(".tab").forEach(function (t) {
    t.addEventListener("click", function () {
      if (t.dataset.view === "terminal" && Board.render.renderTerminal) {
        Board.render.renderTerminal();
      }
    });
  });

  // ── Register on Board namespace ──
  Board.render.renderTerminal = renderTerminal;
  Board.render.cleanupTerminal = cleanupTerminal;
})();
