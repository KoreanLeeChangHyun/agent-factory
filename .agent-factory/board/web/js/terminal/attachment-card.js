/**
 * @module terminal/attachment-card
 * Attachment Ticket Card DOM Generating Helper — Single Truth Supplier.
 *
 * Input side (.terminal-image-preview preview) and message renderer side (.term-message-attachments)
 * Board. term.attachmentCard.create(att) to share the same DOM structure and look&fill.
 *
 * int object structure: {number, command, title, prompt?, report?, result?, fetched at?, subtitle? } else {
 */
"use strict";

(function () {
  var M = (Board._term = Board._term || {});

  /**
   * Map the command code to the card badge text.
   * T/T, Western Union, MoneyGram
   *
   * @param {string|undefined} command
   * @returns {string}
   */
  function _ticketCmdLabel(command) {
    if (!command) return "TKT";
    var c = String(command).toLowerCase();
    if (c === "implement") return "IMP";
    if (c === "research") return "RSC";
    if (c === "review") return "REV";
    return "TKT";
  }

  /**
   * Extract timestamp from the `runs/YYYYMMDD-HMMSS/...` pattern of workdir path.
   * null in failure.
   *
   * @param {string|undefined} workdir
   * @returns {string|null}
   */
  function _extractTicketDate(workdir) {
    if (!workdir) return null;
    var m = String(workdir).match(/runs\/(\d{8})-(\d{6})/);
    if (!m) return null;
    var ymd = m[1]; // YYYYMMDD
    var hms = m[2]; // HHMMSS
    var year = parseInt(ymd.slice(0, 4), 10);
    var month = parseInt(ymd.slice(4, 6), 10);
    var day = parseInt(ymd.slice(6, 8), 10);
    var hour = parseInt(hms.slice(0, 2), 10);
    var minute = parseInt(hms.slice(2, 4), 10);
    if (!year || !month || !day) return null;
    var ampm = hour < 12 ? "Home" : "Afternoon";
    var hour12 = hour % 12;
    if (hour12 === 0) hour12 = 12;
    return year + "Year" + month + "Month" + day + "News" + ampm + " " + hour12 + "City" + minute + "About Us";
  }

  /**
   * Calculate subtitle strings from the att object.
   *
   * subtitle Priority:
   * 1. att.subtitle explicit value (with direct delivery from outside)
   * 2. Extract date from att.result.workdir
   * 3. FAQs att.report
   * 4. "no report"
   *
   * @param {object} att
   * @returns {string}
   */
  function _resolveSubtitle(att) {
    if (att.subtitle) return att.subtitle;
    var workdir = att.result && att.result.workdir;
    if (workdir) {
      var dateStr = _extractTicketDate(workdir);
      if (dateStr) return dateStr;
    }
    if (att.report) {
      var lineCount = String(att.report).split(/\r?\n/).length;
      return "report " + lineCount + "About Us";
    }
    return "no report";
  }

  /**
   * returns by creating an attachment ticket card DOM element.
   *
   * The generated card uses the `.terminal-ticket-card` class.
   * remove button does not include — M.renderTicketPreview in the input side view is
   * Separately put the remove button, and the message wrender side should not be remove button.
   *
   * @param {object} att - {number, command, title, prompt?, report?, result?, subtitle?}
   * @returns {HTMLElement} .terminal-ticket-card div
   */
  function create(att) {
    att = att || {};
    var attType = att.type || "ticket";

    var card = document.createElement("div");
    card.className = "terminal-ticket-card";
    card.setAttribute("data-att-type", attType);
    if (att.number) {
      card.setAttribute("data-ticket-number", att.number);
    }
    if (attType === "memory" && att.name) {
      card.setAttribute("data-memory-name", att.name);
    }

    // Badge: ticket = command code (IMP/RSC/REV/TKT) / memory = "MEM"
    var cmdEl = document.createElement("div");
    cmdEl.className = "terminal-ticket-card-cmd";
    cmdEl.textContent = attType === "memory" ? "MEM" : _ticketCmdLabel(att.command);

    // Body: title + subtitle
    var bodyEl = document.createElement("div");
    bodyEl.className = "terminal-ticket-card-body";

    var titleEl = document.createElement("div");
    titleEl.className = "terminal-ticket-card-title";
    var titleText;
    if (attType === "memory") {
      titleText = att.title || att.name || "memory";
    } else {
      var numStr = att.number || "T-???";
      var ticketTitle = (att.title || "").trim();
      titleText = ticketTitle ? (numStr + " " + ticketTitle) : numStr;
    }
    titleEl.textContent = titleText;
    titleEl.title = titleText;

    var subtitleEl = document.createElement("div");
    subtitleEl.className = "terminal-ticket-card-sub";
    var subtitle = attType === "memory"
      ? (att.subtitle || att.name || "")
      : _resolveSubtitle(att);
    subtitleEl.textContent = subtitle;
    subtitleEl.title = subtitle;

    bodyEl.appendChild(titleEl);
    bodyEl.appendChild(subtitleEl);

    card.appendChild(cmdEl);
    card.appendChild(bodyEl);

    return card;
  }

  // ── Module Exposure ──
  M.attachmentCard = {
    create: create,
    // internal testing
    _ticketCmdLabel: _ticketCmdLabel,
    _extractTicketDate: _extractTicketDate,
    _resolveSubtitle: _resolveSubtitle
  };

})();
