/**
 * @module renderers
 *
 * ToolResultRenderer: tool output rendering pipeline.
 *
 * Provides utility functions and renderer registry for tool output rendering.
 * 9 renderers: statusBadge, fallbackPlain, list, json, fileContent, markdown,
 * xmlLike, schema, taskStream, flowCommand.
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

  // ── Renderers: flowCommand ──

  /**
   * flowCommand renderer — flow-* Bash command output rendering.
   *
   * Detects structured output patterns from flow-kanban, flow-init,
   * flow-finish, flow-launcher, flow-update and renders compact cards.
   */
  ToolResultRenderer.renderers.flowCommand = (function () {

    // ── Pattern constants ──

    var RE_TRANSITION   = /^(T-\d+):\s+(.+?)\s*→\s*(.+)$/;
    var RE_CREATE       = /^(T-\d+):\s+(.+)\(([^)]+)\)\s*$/;
    var RE_DELETE       = /^(T-\d+):\s+삭제됨\s*$/;
    var RE_UPDATE       = /^(T-\d+):\s+(.+)(갱신됨|추가됨|제거됨)\s*$/;
    var RE_ALREADY      = /^(T-\d+)은\(?는?\)?\s*이미\s+(.+)$/;
    var RE_LAUNCHER     = /^(LAUNCH|INLINE):\s+(.+)$/;
    var RE_SYSTEM       = /^\[(INIT|DONE|STATE|STEP|PHASE|WORKFLOW)\]\s*(.*)$/;
    var RE_ERROR        = /^\[(ERROR)\]\s*(.*)$/;
    var RE_WARN         = /^\[(WARN)\]\s*(.*)$/;
    var RE_FAIL         = /^FAIL$/;
    var RE_SHOW_HEADER  = /^##\s+(T-\d+):\s+(.+)$/;
    var RE_BOARD_HEADER = /^##\s+Kanban Board/;
    var RE_DETAIL_LINE  = /^>>\s*(.+)$/;
    var RE_FILE_MOVE    = /^파일 이동:\s+(.+?)\s*→\s*(.+)$/;

    // ── Status color mapping ──

    var STATUS_CLASS_MAP = {
      'open':          'flow-st-open',
      'in progress':   'flow-st-progress',
      'submit':        'flow-st-progress',
      'progress':      'flow-st-progress',
      'review':        'flow-st-review',
      'done':          'flow-st-done'
    };

    function statusClass(status) {
      var key = (status || '').toLowerCase().trim();
      return STATUS_CLASS_MAP[key] || 'flow-st-default';
    }

    // ── Internal HTML builders ──

    var safeEsc = ToolResultRenderer.util.safeEsc;
    var linkifyIds = ToolResultRenderer.util.linkifyIds;

    function badge(ticketId) {
      return '<span class="flow-cmd-badge">' + linkifyIds(safeEsc(ticketId)) + '</span>';
    }

    function actionLabel(text, cls) {
      return '<span class="flow-cmd-action ' + (cls || '') + '">' + safeEsc(text) + '</span>';
    }

    function detailBlock(lines) {
      if (!lines || !lines.length) return '';
      var html = '<div class="flow-cmd-detail">';
      for (var i = 0; i < lines.length; i++) {
        html += '<div>' + linkifyIds(safeEsc(lines[i])) + '</div>';
      }
      html += '</div>';
      return html;
    }

    function wrapCard(inner, extraClass) {
      return '<div class="flow-cmd-card' + (extraClass ? ' ' + extraClass : '') + '">' + inner + '</div>';
    }

    // ── Line-level classifiers ──

    function classifyLine(line) {
      var m;

      m = RE_FILE_MOVE.exec(line);
      if (m) return { type: 'file-move', from: m[1], to: m[2] };

      m = RE_TRANSITION.exec(line);
      if (m) return { type: 'transition', id: m[1], from: m[2], to: m[3] };

      m = RE_CREATE.exec(line);
      if (m) return { type: 'create', id: m[1], title: m[2].trim(), command: m[3].trim() };

      m = RE_DELETE.exec(line);
      if (m) return { type: 'delete', id: m[1] };

      m = RE_UPDATE.exec(line);
      if (m) return { type: 'update', id: m[1], desc: m[2].trim(), action: m[3] };

      m = RE_ALREADY.exec(line);
      if (m) return { type: 'already', id: m[1], message: m[2] };

      m = RE_LAUNCHER.exec(line);
      if (m) return { type: 'launcher', kind: m[1], message: m[2] };

      m = RE_ERROR.exec(line);
      if (m) return { type: 'error', message: m[2] };

      m = RE_WARN.exec(line);
      if (m) return { type: 'warn', message: m[2] };

      m = RE_FAIL.exec(line);
      if (m) return { type: 'error', message: 'FAIL' };

      m = RE_SYSTEM.exec(line);
      if (m) return { type: 'system', tag: m[1], message: m[2] };

      m = RE_DETAIL_LINE.exec(line);
      if (m) return { type: 'detail', text: m[1] };

      return null;
    }

    // ── Card renderers per type ──

    function renderTransition(cl, details) {
      var fromCls = statusClass(cl.from);
      var toCls   = statusClass(cl.to);
      var inner = badge(cl.id) +
        '<span class="flow-cmd-transition">' +
          '<span class="flow-cmd-from ' + fromCls + '">' + safeEsc(cl.from) + '</span>' +
          '<span class="flow-cmd-arrow">&rarr;</span>' +
          '<span class="flow-cmd-to ' + toCls + '">' + safeEsc(cl.to) + '</span>' +
        '</span>';
      return wrapCard(inner + detailBlock(details), 'flow-cmd-transition-card');
    }

    function renderCreate(cl) {
      var inner = badge(cl.id) +
        '<span class="flow-cmd-title">' + linkifyIds(safeEsc(cl.title)) + '</span>' +
        actionLabel(cl.command, 'flow-cmd-command');
      return wrapCard(inner, 'flow-cmd-create-card');
    }

    function renderDelete(cl) {
      var inner = badge(cl.id) + actionLabel('삭제됨', 'flow-cmd-deleted');
      return wrapCard(inner, 'flow-cmd-delete-card');
    }

    function renderUpdate(cl) {
      var inner = badge(cl.id) +
        '<span class="flow-cmd-update-desc">' + linkifyIds(safeEsc(cl.desc)) + '</span>' +
        actionLabel(cl.action, 'flow-cmd-updated');
      return wrapCard(inner, 'flow-cmd-update-card');
    }

    function renderAlready(cl) {
      var inner = badge(cl.id) +
        '<span class="flow-cmd-info-text">' + safeEsc(cl.message) + '</span>';
      return wrapCard(inner, 'flow-cmd-info');
    }

    function renderLauncher(cl) {
      var kindClass = cl.kind === 'LAUNCH' ? 'flow-cmd-launch' : 'flow-cmd-inline';
      var inner =
        '<span class="flow-cmd-launcher-type ' + kindClass + '">' + safeEsc(cl.kind) + '</span>' +
        '<span class="flow-cmd-launcher-msg">' + linkifyIds(safeEsc(cl.message)) + '</span>';
      return wrapCard(inner, 'flow-cmd-launcher');
    }

    function renderSystem(cl, details) {
      var tagClass = 'flow-sys-' + cl.tag.toLowerCase();
      var inner =
        '<span class="flow-cmd-system-tag ' + tagClass + '">' + safeEsc(cl.tag) + '</span>' +
        '<span class="flow-cmd-system-msg">' + linkifyIds(safeEsc(cl.message)) + '</span>';
      return wrapCard(inner + detailBlock(details), 'flow-cmd-system');
    }

    function renderError(cl, details) {
      var inner = '<span class="flow-cmd-error-msg">' + linkifyIds(safeEsc(cl.message)) + '</span>';
      return wrapCard(inner + detailBlock(details), 'flow-cmd-error');
    }

    function renderWarn(cl, details) {
      var inner = '<span class="flow-cmd-warn-msg">' + linkifyIds(safeEsc(cl.message)) + '</span>';
      return wrapCard(inner + detailBlock(details), 'flow-cmd-warn');
    }

    // ── Multiline: kanban show ──

    function renderKanbanShow(text) {
      var lines = text.split('\n');
      var html = '<div class="flow-cmd-multi flow-cmd-show">';
      var headerMatch = RE_SHOW_HEADER.exec(lines[0]);
      if (headerMatch) {
        html += '<div class="flow-cmd-show-header">' +
          badge(headerMatch[1]) +
          '<span class="flow-cmd-show-title">' + linkifyIds(safeEsc(headerMatch[2])) + '</span>' +
          '</div>';
      }

      // Parse key: value pairs and sections
      var bodyLines = lines.slice(1);
      var currentSection = '';
      var sectionContent = [];

      function flushSection() {
        if (currentSection && sectionContent.length) {
          html += '<div class="flow-cmd-show-section">' +
            '<div class="flow-cmd-show-section-label">' + safeEsc(currentSection) + '</div>' +
            '<div class="flow-cmd-show-section-body">' + linkifyIds(safeEsc(sectionContent.join('\n'))) + '</div>' +
            '</div>';
        }
        currentSection = '';
        sectionContent = [];
      }

      for (var i = 0; i < bodyLines.length; i++) {
        var line = bodyLines[i];
        var trimmed = line.trim();
        if (!trimmed) continue;

        // Section headers like "### Prompt", "### Result"
        var sectionMatch = trimmed.match(/^###\s+(.+)$/);
        if (sectionMatch) {
          flushSection();
          currentSection = sectionMatch[1];
          continue;
        }

        // Key: value metadata lines
        var kvMatch = trimmed.match(/^-\s+\*\*(.+?)\*\*:\s*(.+)$/);
        if (kvMatch && !currentSection) {
          html += '<div class="flow-cmd-show-kv">' +
            '<span class="flow-cmd-show-key">' + safeEsc(kvMatch[1]) + '</span>' +
            '<span class="flow-cmd-show-val">' + linkifyIds(safeEsc(kvMatch[2])) + '</span>' +
            '</div>';
          continue;
        }

        sectionContent.push(trimmed);
      }
      flushSection();

      html += '</div>';
      return html;
    }

    // ── Multiline: kanban board/list ──

    function renderKanbanBoard(text) {
      var lines = text.split('\n');
      var html = '<div class="flow-cmd-multi flow-cmd-board">';
      html += '<div class="flow-cmd-board-header">Kanban Board</div>';

      var currentColumn = '';
      for (var i = 1; i < lines.length; i++) {
        var line = lines[i];
        var trimmed = line.trim();
        if (!trimmed) continue;

        var colMatch = trimmed.match(/^###\s+(.+)\s*\(\d+\)\s*$/);
        if (colMatch) {
          currentColumn = colMatch[1];
          html += '<div class="flow-cmd-board-col">' +
            '<div class="flow-cmd-board-col-name">' + safeEsc(currentColumn) + '</div>';
          continue;
        }

        var itemMatch = trimmed.match(/^-\s+(T-\d+):\s+(.+)$/);
        if (itemMatch) {
          html += '<div class="flow-cmd-board-item">' +
            badge(itemMatch[1]) +
            '<span class="flow-cmd-board-item-title">' + linkifyIds(safeEsc(itemMatch[2])) + '</span>' +
            '</div>';
          continue;
        }

        // Column closing: next section or end
        if (/^###/.test(trimmed) || /^##/.test(trimmed)) {
          html += '</div>';
        }
      }

      html += '</div>';
      return html;
    }

    // ── Main renderer entry point ──

    function render(content, meta) {
      var text = (content || '').trim();
      if (!text) return '<span class="flow-cmd-card flow-cmd-empty">(empty)</span>';

      // Check for multiline structured outputs first
      var firstLine = text.split('\n')[0];

      if (RE_SHOW_HEADER.test(firstLine)) {
        return renderKanbanShow(text);
      }

      if (RE_BOARD_HEADER.test(firstLine)) {
        return renderKanbanBoard(text);
      }

      // Process line-by-line for single or multi-line simple outputs
      var lines = text.split('\n');
      var cards = [];
      var pendingDetails = [];
      var pendingFileMove = null;
      var lastCard = null;

      for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (!line) continue;

        var cl = classifyLine(line);
        if (!cl) {
          // Unrecognized line — render as compact plain text
          cards.push('<div class="flow-cmd-plain">' + linkifyIds(safeEsc(line)) + '</div>');
          continue;
        }

        if (cl.type === 'detail') {
          pendingDetails.push(cl.text);
          continue;
        }

        // Flush pending details to the previous card
        if (pendingDetails.length && lastCard !== null) {
          cards[lastCard] = cards[lastCard].replace(
            /<\/div>$/,
            detailBlock(pendingDetails) + '</div>'
          );
          pendingDetails = [];
        }

        if (cl.type === 'file-move') {
          pendingFileMove = cl;
          continue;
        }

        var html;
        switch (cl.type) {
          case 'transition':
            var details = [];
            if (pendingFileMove) {
              details.push('파일 이동: ' + pendingFileMove.from + ' → ' + pendingFileMove.to);
              pendingFileMove = null;
            }
            html = renderTransition(cl, details);
            break;
          case 'create':
            html = renderCreate(cl);
            break;
          case 'delete':
            html = renderDelete(cl);
            break;
          case 'update':
            html = renderUpdate(cl);
            break;
          case 'already':
            html = renderAlready(cl);
            break;
          case 'launcher':
            html = renderLauncher(cl);
            break;
          case 'system':
            html = renderSystem(cl, []);
            break;
          case 'error':
            html = renderError(cl, []);
            break;
          case 'warn':
            html = renderWarn(cl, []);
            break;
          default:
            html = '<div class="flow-cmd-plain">' + linkifyIds(safeEsc(line)) + '</div>';
        }

        cards.push(html);
        lastCard = cards.length - 1;
      }

      // Flush remaining details
      if (pendingDetails.length && lastCard !== null) {
        cards[lastCard] = cards[lastCard].replace(
          /<\/div>$/,
          detailBlock(pendingDetails) + '</div>'
        );
      }

      // Flush remaining file-move as standalone detail
      if (pendingFileMove) {
        cards.push(wrapCard(
          '<span class="flow-cmd-info-text">파일 이동: ' +
          safeEsc(pendingFileMove.from) + ' → ' + safeEsc(pendingFileMove.to) + '</span>',
          'flow-cmd-info'
        ));
      }

      if (cards.length === 1) return cards[0];
      return '<div class="flow-cmd-multi">' + cards.join('') + '</div>';
    }

    return render;
  })();

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
      // flow-* command output detection
      if (/T-\d+:|T-\d+은/.test(t) ||
          /^(LAUNCH|INLINE):/m.test(t) ||
          /^\[(INIT|DONE|STATE|STEP|PHASE|WORKFLOW|ERROR|WARN)\]/m.test(t) ||
          /^FAIL$/m.test(t)) {
        return 'flowCommand';
      }
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
