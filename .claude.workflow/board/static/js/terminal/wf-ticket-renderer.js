/**
 * @module wf-ticket-renderer
 *
 * Parses /wf command output in the Board terminal and renders it as
 * interactive card UI with clickable menu buttons.
 *
 * Detects patterns like:  `[T-NNN]` : `[WF -e]` ...
 * Parses numbered menu items:  `N.` text -- description
 *
 * Depends on: common.js (Board namespace)
 * Registers: Board.WfTicketRenderer
 */
"use strict";

Board.WfTicketRenderer = (function () {

  // ── Pattern constants ──

  var RE_HEADER    = /`\[T-\d+\]`\s*:\s*`\[WF/;
  var RE_MENU_ITEM = /^`?(\d+)\.`?\s+(.+)$/;
  var RE_TICKET_ID = /`\[(T-\d+)\]`/;
  var RE_WF_FLAG   = /`\[WF\s*([^\]]*)\]`/;

  // ── Context references (injected via setContext) ──

  var _ctx = null;

  function setContext(ctx) {
    _ctx = ctx;
  }

  // ── Markdown rendering helper ──
  // Uses ctx.renderMarkdownToHtml if available, otherwise falls back to
  // marked.parse (loaded globally), or plain-text escaping.

  function _renderMd(text) {
    if (_ctx && _ctx.renderMarkdownToHtml) {
      return _ctx.renderMarkdownToHtml(text);
    }
    if (typeof marked !== "undefined" && marked.parse) {
      try { return marked.parse(text); } catch (e) { /* fallback */ }
    }
    return "<pre>" + String(text || "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") + "</pre>";
  }

  // ── Detection ──

  function detect(text) {
    return RE_HEADER.test(text);
  }

  // ── Internal parsers ──

  function _parseHeader(text) {
    var ticketMatch = RE_TICKET_ID.exec(text);
    var flagMatch   = RE_WF_FLAG.exec(text);
    return {
      ticketId: ticketMatch ? ticketMatch[1] : "",
      flag:     flagMatch   ? flagMatch[1].trim() : ""
    };
  }

  function _parseMenuItems(text) {
    var lines = text.split("\n");
    var items = [];
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      var m = RE_MENU_ITEM.exec(line);
      if (m) {
        var num     = parseInt(m[1], 10);
        var rest    = m[2];
        var parts   = rest.split(/\s+--\s+/);
        var label   = parts[0].trim();
        var desc    = parts.length > 1 ? parts.slice(1).join(" -- ").trim() : "";
        items.push({ num: num, label: label, desc: desc });
      }
    }
    return items;
  }

  function _isMenuOutput(text) {
    var items = _parseMenuItems(text);
    return items.length >= 2;
  }

  // ── Body text extraction ──
  // Extract the text between the header line and the first menu item

  function _extractBody(text) {
    var lines = text.split("\n");
    var headerEnd = -1;
    var menuStart = lines.length;

    for (var i = 0; i < lines.length; i++) {
      if (RE_HEADER.test(lines[i])) {
        headerEnd = i;
      }
    }
    for (var j = headerEnd + 1; j < lines.length; j++) {
      if (RE_MENU_ITEM.test(lines[j].trim())) {
        menuStart = j;
        break;
      }
    }

    if (headerEnd < 0) return "";
    var bodyLines = lines.slice(headerEnd + 1, menuStart);
    return bodyLines.join("\n").trim();
  }

  // ── Renderers ──

  function _renderMenu(text) {
    var header = _parseHeader(text);
    var items  = _parseMenuItems(text);
    var body   = _extractBody(text);

    // Card container
    var card = document.createElement("div");
    card.className = "wf-ticket-block";

    // Header row
    var hdr = document.createElement("div");
    hdr.className = "wf-ticket-header";

    if (header.ticketId) {
      var idSpan = document.createElement("span");
      idSpan.className = "wf-ticket-id";
      idSpan.textContent = header.ticketId;
      hdr.appendChild(idSpan);
    }
    if (header.flag) {
      var flagSpan = document.createElement("span");
      flagSpan.className = "wf-ticket-flag";
      flagSpan.textContent = "WF " + header.flag;
      hdr.appendChild(flagSpan);
    }
    card.appendChild(hdr);

    // Body (markdown rendered)
    if (body) {
      var bodyDiv = document.createElement("div");
      bodyDiv.className = "wf-ticket-body";
      bodyDiv.innerHTML = _renderMd(body);
      card.appendChild(bodyDiv);
    }

    // Menu buttons container
    var menu = document.createElement("div");
    menu.className = "wf-ticket-menu";

    // Separate normal items and cancel item (0)
    var normalItems = [];
    var cancelItem  = null;
    for (var i = 0; i < items.length; i++) {
      if (items[i].num === 0) {
        cancelItem = items[i];
      } else {
        normalItems.push(items[i]);
      }
    }

    // Create buttons for normal items
    function createBtn(item) {
      var btn = document.createElement("button");
      btn.className = "wf-ticket-btn";
      btn.type = "button";

      var numSpan = document.createElement("span");
      numSpan.className = "btn-number";
      numSpan.textContent = item.num + ".";
      btn.appendChild(numSpan);

      var textNode = document.createTextNode(" " + item.label);
      btn.appendChild(textNode);

      if (item.desc) {
        var descSpan = document.createElement("span");
        descSpan.className = "btn-desc";
        descSpan.textContent = " -- " + item.desc;
        btn.appendChild(descSpan);
      }

      btn.addEventListener("click", function () {
        _handleMenuClick(item.num, btn, menu);
      });

      return btn;
    }

    for (var n = 0; n < normalItems.length; n++) {
      menu.appendChild(createBtn(normalItems[n]));
    }

    // Cancel/exit button last, with separator style
    if (cancelItem) {
      var cancelBtn = createBtn(cancelItem);
      cancelBtn.classList.add("is-cancel");
      menu.appendChild(cancelBtn);
    }

    card.appendChild(menu);

    // Append to output
    if (_ctx && _ctx.appendToOutput) {
      _ctx.appendToOutput(card);
    }
  }

  function _handleMenuClick(num, clickedBtn, menuEl) {
    // Disable all buttons
    var buttons = menuEl.querySelectorAll(".wf-ticket-btn");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].disabled = true;
    }

    // Highlight selected button
    clickedBtn.classList.add("wf-ticket-selected");

    // Insert user message bubble
    var userDiv = document.createElement("div");
    userDiv.className = "term-message term-user";
    userDiv.textContent = String(num);
    if (_ctx && _ctx.appendToOutput) {
      _ctx.appendToOutput(userDiv);
    }

    // Lock input, start spinner, set running
    if (_ctx && _ctx.setInputLocked)  _ctx.setInputLocked(true);
    if (_ctx && _ctx.startSpinner)    _ctx.startSpinner();
    Board.state.termStatus = "running";
    if (_ctx && _ctx.updateControlBar) _ctx.updateControlBar();

    // Send input via endpoints
    var ep = _ctx && _ctx.endpoints ? _ctx.endpoints() : null;
    if (ep) {
      Board.session.postJson(ep.input, ep.inputBody({ text: String(num) }))
        .catch(function (err) {
          if (_ctx && _ctx.stopSpinner)        _ctx.stopSpinner();
          if (_ctx && _ctx.appendErrorMessage) _ctx.appendErrorMessage("[Error] " + err.message);
          if (_ctx && _ctx.setInputLocked)     _ctx.setInputLocked(false);
          Board.state.termStatus = "idle";
          if (_ctx && _ctx.updateControlBar)   _ctx.updateControlBar();
        });
    }
  }

  function _renderStatus(text) {
    var header = _parseHeader(text);
    var isOk   = /완료|Done|성공/.test(text);

    var card = document.createElement("div");
    card.className = "wf-ticket-block " + (isOk ? "wf-status-ok" : "wf-status-err");

    var hdr = document.createElement("div");
    hdr.className = "wf-ticket-header";

    if (header.ticketId) {
      var idSpan = document.createElement("span");
      idSpan.className = "wf-ticket-id";
      idSpan.textContent = header.ticketId;
      hdr.appendChild(idSpan);
    }

    var badge = document.createElement("span");
    badge.className = "wf-status-badge";
    badge.textContent = isOk ? "Done" : "Error";
    hdr.appendChild(badge);

    card.appendChild(hdr);

    // Body
    var bodyDiv = document.createElement("div");
    bodyDiv.className = "wf-ticket-body";
    bodyDiv.innerHTML = _renderMd(text);
    card.appendChild(bodyDiv);

    if (_ctx && _ctx.appendToOutput) {
      _ctx.appendToOutput(card);
    }
  }

  function _renderDefault(text) {
    var header = _parseHeader(text);

    var card = document.createElement("div");
    card.className = "wf-ticket-block";

    var hdr = document.createElement("div");
    hdr.className = "wf-ticket-header";

    if (header.ticketId) {
      var idSpan = document.createElement("span");
      idSpan.className = "wf-ticket-id";
      idSpan.textContent = header.ticketId;
      hdr.appendChild(idSpan);
    }
    if (header.flag) {
      var flagSpan = document.createElement("span");
      flagSpan.className = "wf-ticket-flag";
      flagSpan.textContent = "WF " + header.flag;
      hdr.appendChild(flagSpan);
    }
    card.appendChild(hdr);

    var bodyDiv = document.createElement("div");
    bodyDiv.className = "wf-ticket-body";
    bodyDiv.innerHTML = _renderMd(text);
    card.appendChild(bodyDiv);

    if (_ctx && _ctx.appendToOutput) {
      _ctx.appendToOutput(card);
    }
  }

  // ── Public render dispatcher ──

  function render(text) {
    if (_isMenuOutput(text)) {
      _renderMenu(text);
    } else if (/완료|Done|성공|실패|Error/.test(text) && !_isMenuOutput(text)) {
      _renderStatus(text);
    } else {
      _renderDefault(text);
    }
  }

  // ── Public API ──

  return {
    detect:     detect,
    render:     render,
    setContext:  setContext
  };

})();
