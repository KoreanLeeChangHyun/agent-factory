/**
 * @module renderers
 *
 * ToolResultRenderer: tool output rendering pipeline.
 *
 * Provides utility functions and renderer registry for tool output rendering.
 * 8 renderers: statusBadge, fallbackPlain, list, json, fileContent, markdown,
 * xmlLike, schema, taskStream.
 *
 * Depends on: common.js (Board.util.esc)
 * Registers:  Board.ToolResultRenderer
 */
"use strict";

(function () {
  var esc = Board.util.esc;

  // ── ToolResultRenderer namespace ──

  var ToolResultRenderer = { util: {}, renderers: {}, dispatch: null };

  /** @type {function} renderMarkdownToHtml — set by terminal.js core after init */
  var _renderMarkdownToHtml = null;

  /**
   * Setter for renderMarkdownToHtml dependency.
   * Called by terminal.js core after marked.js initialization.
   * @param {function} fn
   */
  ToolResultRenderer.setMarkdownRenderer = function (fn) {
    _renderMarkdownToHtml = fn;
  };

  // ── Constants ──

  var AUTO_COLLAPSE_BYTES = 2048;

  var LLM_META_PATTERNS = [
    /^REMINDER:.*$/gm,
    /Please proceed with the current tasks.*$/gm,
    /Ensure that you continue to use the todo list.*$/gm,
    /<system-reminder>[\s\S]*?<\/system-reminder>/g,
  ];

  // ── Utility functions ──

  ToolResultRenderer.util.stripLlmMeta = function (text) {
    if (!text) return text;
    var cleaned = text;
    for (var i = 0; i < LLM_META_PATTERNS.length; i++) {
      cleaned = cleaned.replace(LLM_META_PATTERNS[i], "");
    }
    cleaned = cleaned.replace(/\n{3,}/g, "\n\n");
    return cleaned;
  };

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

  ToolResultRenderer.util.collapsibleResult = function (htmlContent, rawText, options) {
    var opts = options || {};
    var previewLines = opts.previewLines !== undefined ? opts.previewLines : 3;
    var summaryLabel = opts.summaryLabel !== undefined ? opts.summaryLabel : 'result';

    var text = rawText || '';
    var lines = text.length === 0 ? [] : text.split('\n');
    var totalLines = lines.length;

    if (totalLines <= previewLines) {
      return htmlContent;
    }

    var extraLines = totalLines - previewLines;
    var previewText = lines.slice(0, previewLines).join('\n');
    var escapedPreview = esc(previewText);

    return (
      '<details class="term-collapsible">' +
      '<summary>' +
      '<pre class="term-preview">' + escapedPreview + '</pre>' +
      '<span class="term-collapsible-count">... (+' + extraLines + ' lines)</span>' +
      '</summary>' +
      '<div class="term-collapsible-full">' + htmlContent + '</div>' +
      '</details>'
    );
  };

  ToolResultRenderer.util.linkifyIds = function (escapedText) {
    if (!escapedText) return escapedText;

    var result = escapedText.replace(/\bT-(\d{3,4})\b/g, function (_, id) {
      return '<a class="term-id-link" data-kind="ticket_id" data-id="T-' + id + '">T-' + id + '</a>';
    });

    result = result.replace(/task_id["']?\s*:\s*["']?([a-z0-9]{6,12})/g, function (match, id) {
      return match.replace(id, '<a class="term-id-link" data-kind="task_id" data-id="' + id + '">' + id + '</a>');
    });

    result = result.replace(/job[_\s]([a-z0-9]{8,})/g, function (match, id) {
      return match.replace(id, '<a class="term-id-link" data-kind="job_id" data-id="' + id + '">' + id + '</a>');
    });

    result = result.replace(/Scheduled one-shot task ([a-z0-9]{8})/g, function (match, id) {
      return match.replace(id, '<a class="term-id-link" data-kind="cron_job_id" data-id="' + id + '">' + id + '</a>');
    });

    return result;
  };

  ToolResultRenderer.util.safeEsc = function (s) {
    return esc(s);
  };

  // ── Renderers: statusBadge ──

  ToolResultRenderer.renderers.statusBadge = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;

    var trimmed = (text || "").trim();
    if (!trimmed) {
      return '<span class="term-status-badge">(empty response)</span>';
    }

    var escaped = safeEsc(trimmed).replace(/\n/g, "<br>");
    return '<span class="term-status-badge">' + linkifyIds(escaped) + "</span>";
  };

  // ── Renderers: fallbackPlain ──

  ToolResultRenderer.renderers.fallbackPlain = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;

    var cleaned = (text || "").replace(/\x1b\[[0-9;]*m/g, "");
    var escaped = safeEsc(cleaned);
    return '<pre class="term-plain">' + linkifyIds(escaped) + "</pre>";
  };

  // ── Renderers: list ──

  ToolResultRenderer.renderers.list = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;
    var statusBadge = ToolResultRenderer.renderers.statusBadge;

    var trimmed = (text || "").trim();

    if (trimmed === "No matches found" || trimmed === "No files found") {
      return statusBadge(trimmed, meta);
    }

    var lines = trimmed.split("\n").filter(Boolean);

    if (!lines.length) {
      return statusBadge("(empty list)", meta);
    }

    var items = lines.map(function (line) {
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

  ToolResultRenderer.renderers.json = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;
    var fallbackPlain = ToolResultRenderer.renderers.fallbackPlain;

    var trimmed = (text || "").trim();
    var httpBadgeHtml = "";
    var jsonBody = trimmed;

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

    var parsed;
    try {
      parsed = JSON.parse(jsonBody);
    } catch (e) {
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

  ToolResultRenderer.renderers.fileContent = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;

    var lines = (text || "").split("\n");
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

  ToolResultRenderer.renderers.markdown = function (text, meta) {
    var renderFn = _renderMarkdownToHtml || function (t) {
      return '<pre class="term-fallback">' + esc(t) + '</pre>';
    };
    var mdHtml = renderFn(text || "");
    return '<div class="term-md-result">' + mdHtml + "</div>";
  };

  // ── Renderers: xmlLike ──

  ToolResultRenderer.renderers.xmlLike = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;
    var fallbackPlain = ToolResultRenderer.renderers.fallbackPlain;

    var source = (text || "").trim();

    var notifMatch = source.match(/^<task-notification>([\s\S]*?)<\/task-notification>$/i);
    if (notifMatch) {
      source = notifMatch[1].trim();
    }

    var tagRegex = /<([a-z][a-z0-9\-_]*)>([\s\S]*?)<\/\1>/gi;
    var items = [];
    var match;

    while ((match = tagRegex.exec(source)) !== null) {
      var tagName = match[1];
      var rawValue = match[2];

      var dtHtml = '<dt>' + safeEsc(tagName) + '</dt>';
      var ddHtml;

      if (tagName.toLowerCase() === 'output') {
        ddHtml = '<dd><pre class="term-xml-output">' + safeEsc(rawValue) + '</pre></dd>';
      } else {
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

    if (!items.length) {
      return fallbackPlain(text, meta);
    }

    return '<dl class="term-xml-result">' + items.join('') + '</dl>';
  };

  // ── Renderers: schema ──

  ToolResultRenderer.renderers.schema = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var fallbackPlain = ToolResultRenderer.renderers.fallbackPlain;

    var source = (text || '').trim();

    var funcRegex = /<function>([\s\S]*?)<\/function>/gi;
    var cards = [];
    var match;

    while ((match = funcRegex.exec(source)) !== null) {
      var blockText = match[1].trim();
      var parsed;
      try {
        parsed = JSON.parse(blockText);
      } catch (e) {
        continue;
      }

      var name = (parsed && parsed.name) ? String(parsed.name) : '';
      var desc = (parsed && parsed.description) ? String(parsed.description) : '';

      cards.push(
        '<div class="term-schema-card">' +
        '<strong class="term-schema-name">' + safeEsc(name) + '</strong>' +
        '<p class="term-schema-desc">' + safeEsc(desc) + '</p>' +
        '</div>'
      );
    }

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

  ToolResultRenderer.renderers.taskStream = function (text, meta) {
    var safeEsc = ToolResultRenderer.util.safeEsc;
    var fallbackPlain = ToolResultRenderer.renderers.fallbackPlain;

    var source = (text || '').trim();

    var full = source.match(/Command running in background with ID:\s*(\S+?)\.\s*Output is being written to:\s*(\S+)/);
    var taskId = '';
    var outputPath = '';

    if (full) {
      taskId = full[1];
      outputPath = full[2];
    } else {
      var idOnly = source.match(/Command running in background with ID:\s*(\S+)/);
      if (!idOnly) {
        return fallbackPlain(text, meta);
      }
      taskId = idOnly[1].replace(/\.+$/, '');
      var pathMatch = source.match(/(?:Output is being written to|Output file|output)[^\S\r\n]*[:\-]?\s*(\/[^\s"']+)/i);
      if (pathMatch) {
        outputPath = pathMatch[1];
      } else {
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

  // ── dispatch: tool -> renderer routing ──

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

  ToolResultRenderer.TOOL_RENDERER_MAP = TOOL_RENDERER_MAP;

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
      if (/^[^:\n]+:\d+:/m.test(t)) return 'fallbackPlain';
      return 'list';
    }

    if (toolName === 'CronList') {
      if (t === 'No scheduled jobs.') return 'statusBadge';
      return 'list';
    }

    return 'fallbackPlain';
  }

  ToolResultRenderer.dispatch = function (toolName, text, meta) {
    var util = ToolResultRenderer.util;
    var renderers = ToolResultRenderer.renderers;

    var cleanText = util.stripLlmMeta(text || '');

    var rawByteLen;
    try {
      rawByteLen = (typeof TextEncoder !== 'undefined')
        ? new TextEncoder().encode(cleanText).length
        : cleanText.length;
    } catch (e) {
      rawByteLen = cleanText.length;
    }

    var mapped = toolName ? TOOL_RENDERER_MAP[toolName] : undefined;
    var rendererKey;
    if (mapped === undefined) {
      rendererKey = 'fallbackPlain';
    } else if (mapped === 'auto') {
      rendererKey = resolveAutoRenderer(toolName, cleanText);
    } else {
      rendererKey = mapped;
    }

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

    var summary = (toolName || 'tool') + ' result';
    return util.autoCollapse(htmlContent, rawByteLen, summary);
  };

  // ── Register on Board namespace ──
  Board.ToolResultRenderer = ToolResultRenderer;
})();
