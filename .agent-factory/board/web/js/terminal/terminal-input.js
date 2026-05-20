/**
 * @module terminal/terminal-input
 * Split from terminal.js. Functions attach to Board._term (M) namespace.
 */
"use strict";

(function () {
  var esc = Board.util.esc;
  var M = (Board._term = Board._term || {});

  // ── Thinking Spinner ──

  M.thinkingEl = null;

  // Claude CLI's witching thinking verb pool is a different word.
  // The rotation interval is between 7 to 14 seconds, and the random is more natural than the fixed cycle.
  var THINKING_VERBS = [
    "Thinking", "Pondering", "Noodling", "Channelling", "Tomfoolering",
    "Ruminating", "Contemplating", "Brewing", "Cogitating", "Puzzling",
    "Synthesizing", "Wrangling", "Simmering", "Musing", "Scheming",
    "Percolating", "Deliberating", "Unravelling",
  ];
  var THINKING_ROTATE_MIN_MS = 7000;
  var THINKING_ROTATE_MAX_MS = 14000;

  function _pickThinkingVerb(prev) {
    if (THINKING_VERBS.length <= 1) return THINKING_VERBS[0];
    var next;
    // The word like the right is to reduce the damage forging.
    do {
      next = THINKING_VERBS[Math.floor(Math.random() * THINKING_VERBS.length)];
    } while (next === prev);
    return next;
  }

  function _pickRotateDelay() {
    return THINKING_ROTATE_MIN_MS + Math.random() * (THINKING_ROTATE_MAX_MS - THINKING_ROTATE_MIN_MS);
  }

  M.startSpinner = function() {
    if (Board.debugLog) Board.debugLog('startSpinner', {
      thinkingEl: !!M.thinkingEl, outputDiv: !!M.outputDiv, termStatus: Board.state.termStatus,
    });
    if (M.thinkingEl) return;
    if (!M.outputDiv) return;

    M.thinkingEl = document.createElement("div");
    M.thinkingEl.className = "term-thinking";
    M.thinkingEl.id = "term-thinking-active";
    var dot = document.createElement("span");
    dot.className = "term-thinking-dot";
    var label = document.createElement("span");
    label.className = "term-thinking-label";
    M.thinkingEl.appendChild(dot);
    M.thinkingEl.appendChild(document.createTextNode(" "));
    M.thinkingEl.appendChild(label);

    var currentVerb = _pickThinkingVerb(null);
    label.textContent = currentVerb + "…";

    var el = M.thinkingEl;
    function _scheduleRotate() {
      el._rotator = setTimeout(function () {
        if (el !== M.thinkingEl) return;
        currentVerb = _pickThinkingVerb(currentVerb);
        label.textContent = currentVerb + "…";
        _scheduleRotate();
      }, _pickRotateDelay());
    }
    _scheduleRotate();

    // Insert the M.outputDiv right back (input-card right front) to fix the bottom
    M.outputDiv.parentNode.insertBefore(M.thinkingEl, M.outputDiv.nextSibling);
  };

  M.stopSpinner = function() {
    if (Board.debugLog) Board.debugLog('stopSpinner', {
      thinkingEl: !!M.thinkingEl, termStatus: Board.state.termStatus,
    });
    if (M.thinkingEl) {
      if (M.thinkingEl._rotator) {
        clearTimeout(M.thinkingEl._rotator);
        M.thinkingEl._rotator = null;
      }
      if (M.thinkingEl.parentNode) {
        M.thinkingEl.parentNode.removeChild(M.thinkingEl);
      }
    }
    M.thinkingEl = null;
  };

  // ── Input Management ──

  // ── Image Attachment ──

  var ALLOWED_MIME = ["image/png", "image/jpeg", "image/gif", "image/webp"];

  var MAX_IMAGE_SIZE = 20 * 1024 * 1024; // 20MB

  M.renderImagePreview = function() {
    var container = document.getElementById("terminal-image-preview");
    if (!container) return;
    container.innerHTML = "";
    M.attachedImages.forEach(function (img, idx) {
      var thumb = document.createElement("div");
      thumb.className = "terminal-image-thumb";

      var imgEl = document.createElement("img");
      imgEl.src = "data:" + img.media_type + ";base64," + img.data;
      imgEl.alt = img.name || "image";

      var removeBtn = document.createElement("button");
      removeBtn.className = "terminal-image-remove";
      removeBtn.title = "About Us";
      removeBtn.innerHTML = "\u00D7";
      removeBtn.addEventListener("click", function () { M.removeImage(idx); });

      thumb.appendChild(imgEl);
      thumb.appendChild(removeBtn);
      container.appendChild(thumb);
    });
  };

  M.attachImage = function(file) {
    if (!file) return;
    if (ALLOWED_MIME.indexOf(file.type) === -1) {
      M.appendErrorMessage("[Additional Error] Not supported format (PNG/JPG/GIF/WebP only available)");
      return;
    }
    if (file.size > MAX_IMAGE_SIZE) {
      M.appendErrorMessage("[Adder Error] File size exceeds 20MB");
      return;
    }
    var reader = new FileReader();
    reader.onload = function (e) {
      var dataUrl = e.target.result;
      // data:image/png;base64,XXXX to base64
      var base64 = dataUrl.split(",")[1];
      M.attachedImages.push({ data: base64, media_type: file.type, name: file.name });
      M.renderImagePreview();
    };
    reader.readAsDataURL(file);
  };

  M.removeImage = function(index) {
    M.attachedImages.splice(index, 1);
    M.renderImagePreview();
  };

  M.clearImages = function() {
    M.attachedImages = [];
    M.renderImagePreview();
    var fileInput = document.getElementById("terminal-attach-input");
    if (fileInput) fileInput.value = "";
  };

  /**
   * The number of bytes is returned by converting to readable units (B, KB, MB).
   */
  M.formatFileSize = function(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  /**
   * Render asynchronous file preview card to terminal-image-preview container.
   * Sharing the same container with the existing image thumbnail (M.renderImagePreview)
   * Manage one view strip.
   */
  M.renderFilePreview = function() {
    var container = document.getElementById("terminal-image-preview");
    if (!container) return;

    // M.renderImagePreview()
    var existingCards = container.querySelectorAll(".terminal-file-card");
    existingCards.forEach(function (card) { card.parentNode.removeChild(card); });

    M.attachedFiles.forEach(function (info, idx) {
      var card = document.createElement("div");
      card.className = "terminal-file-card";
      card.setAttribute("data-file-idx", idx);

      // Scots Gaelic
      var ext = info.name.split(".").pop().toUpperCase().slice(0, 6) || "FILE";
      var extLabel = document.createElement("div");
      extLabel.className = "terminal-file-card-ext";
      extLabel.textContent = ext;

      // ellipsis
      var nameLabel = document.createElement("div");
      nameLabel.className = "terminal-file-card-name";
      nameLabel.textContent = info.name;
      nameLabel.title = info.name;

      // File Size
      var sizeLabel = document.createElement("div");
      sizeLabel.className = "terminal-file-card-size";
      sizeLabel.textContent = M.formatFileSize(info.size);

      // Remove button
      var removeBtn = document.createElement("button");
      removeBtn.className = "terminal-image-remove";
      removeBtn.title = "About Us";
      removeBtn.innerHTML = "\u00D7";
      removeBtn.addEventListener("click", (function (capturedIdx) {
        return function () { M.removeFile(capturedIdx); };
      })(idx));

      card.appendChild(extLabel);
      card.appendChild(nameLabel);
      card.appendChild(sizeLabel);
      card.appendChild(removeBtn);
      container.appendChild(card);
    });
  };

  M.removeFile = function(index) {
    var removed = M.attachedFiles.splice(index, 1);
    // Remove filename from textarea
    var targetInput = document.getElementById("terminal-input");
    if (targetInput && removed.length > 0) {
      var name = removed[0].name;
      var re = new RegExp("(?:^|\\n)" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?=\\n|$)", "g");
      targetInput.value = targetInput.value.replace(re, "").replace(/^\n/, "").replace(/\n\n+/g, "\n");
      var evt = document.createEvent("Event");
      evt.initEvent("input", true, true);
      targetInput.dispatchEvent(evt);
    }
    M.renderFilePreview();
  };

  M.clearFiles = function() {
    M.attachedFiles = [];
    M.renderFilePreview();
  };

  // ── Ticket Attachment ──

  /**
   * #terminal-image-preview
   * Share the same container with the image/file card to manage it with one line attachment strip.
   * Only the existing ticket card (`[data-ticket-idx]`), the image/file card is maintained.
   *
   * The Card DOM body is a single truth source helper of-card.js
   * (Board. term.attachmentCard.create)
   * add the data-ticket-idx property and remove button to the wrapper pattern.
   * This will always match the message renderer card and the look&fill of the input side card.
   */
  M.renderTicketPreview = function() {
    var container = document.getElementById("terminal-image-preview");
    if (!container) return;

    var existingCards = container.querySelectorAll("[data-ticket-idx]");
    existingCards.forEach(function (card) { card.parentNode.removeChild(card); });

    if (!M.attachedTickets) return;

    var helper = M.attachmentCard;
    if (!helper || typeof helper.create !== "function") return;

    M.attachedTickets.forEach(function (ticket, idx) {
      var card = helper.create(ticket);
      card.setAttribute("data-ticket-idx", idx);

      var removeBtn = document.createElement("button");
      removeBtn.className = "terminal-image-remove";
      removeBtn.title = "About Us";
      removeBtn.innerHTML = "×";
      removeBtn.addEventListener("click", (function (capturedIdx) {
        return function () { M.removeTicket(capturedIdx); };
      })(idx));

      card.appendChild(removeBtn);
      container.appendChild(card);
    });
  };

  /**
   * Add ticket attachment.
   * If the same ticket number is already attached, ignore + appendSystemMessage.
   *
   * @param {{number, title, command, prompt, result}} payload
   * @param {string null} reportText - report.html
   */
  M.attachTicket = function(payload, reportText) {
    if (!payload || !payload.number) return;
    if (!M.attachedTickets) M.attachedTickets = [];

    var dup = M.attachedTickets.some(function (t) { return t.number === payload.number; });
    if (dup) {
      if (M.appendSystemMessage) {
        M.appendSystemMessage("NEWS" + payload.number + "{{ data.filesizeHumanReadable }}");
      }
      return;
    }

    M.attachedTickets.push({
      number: payload.number,
      title: payload.title || "",
      command: payload.command || "",
      prompt: payload.prompt || "",
      result: payload.result || null,
      report: reportText || null,
      addedAt: Date.now()
    });
    M.renderTicketPreview();
  };

  M.removeTicket = function(index) {
    if (!M.attachedTickets) return;
    M.attachedTickets.splice(index, 1);
    M.renderTicketPreview();
  };

  M.clearTickets = function() {
    M.attachedTickets = [];
    M.renderTicketPreview();
  };

  // ── Memory
  // Memory attachments do not inline the body to context (user-determined: path only → astont read),
  // How to attach a path token to prefix block before the user text at the sendInput point.
  // So do not send backends field and do not print sidecar.
  M.attachedMemories = M.attachedMemories || [];

  M.renderMemoryPreview = function() {
    var container = document.getElementById("terminal-image-preview");
    if (!container) return;

    var existingCards = container.querySelectorAll("[data-memory-idx]");
    existingCards.forEach(function (card) { card.parentNode.removeChild(card); });

    if (!M.attachedMemories) return;

    var helper = M.attachmentCard;
    if (!helper || typeof helper.create !== "function") return;

    M.attachedMemories.forEach(function (mem, idx) {
      var card = helper.create({
        type: "memory",
        name: mem.name,
        category: mem.category,
        title: mem.description || mem.name,
        subtitle: mem.name
      });
      card.setAttribute("data-memory-idx", idx);

      var removeBtn = document.createElement("button");
      removeBtn.className = "terminal-image-remove";
      removeBtn.title = "About Us";
      removeBtn.innerHTML = "×";
      removeBtn.addEventListener("click", (function (capturedIdx) {
        return function () { M.removeMemory(capturedIdx); };
      })(idx));

      card.appendChild(removeBtn);
      container.appendChild(card);
    });
  };

  /**
   * Add memory attachment (drop handler calls).
   * If the same name is already attached, ignore + appendSystemMessage.
   * description reinforcement after asynchronous fetch (if there is no file or the frontmatter is not graceful fallback).
   *
   * @param {{name: string, category?: string}} payload
   */
  M.attachMemory = function(payload) {
    if (!payload || !payload.name) return;
    if (!M.attachedMemories) M.attachedMemories = [];

    var dup = M.attachedMemories.some(function (m) { return m.name === payload.name; });
    if (dup) {
      if (M.appendSystemMessage) {
        M.appendSystemMessage("[Additional] Memory" + payload.name + "{{ data.filesizeHumanReadable }}");
      }
      return;
    }

    var entry = {
      name: payload.name,
      category: payload.category || "",
      description: "",
      addedAt: Date.now()
    };
    M.attachedMemories.push(entry);
    M.renderMemoryPreview();

    // Reinforce asynchronous description (frontmatter parse). Failure/never graceful — fallback with the chip label filename.
    var fetchFn = Board.fetch && Board.fetch.fetchMemoryFile;
    var parseFn = Board.fetch && Board.fetch.parseMemoryFrontmatter;
    if (typeof fetchFn === "function") {
      fetchFn(payload.name).then(function (data) {
        if (!data || !data.content) return;
        var meta = typeof parseFn === "function" ? parseFn(data.content) : {};
        var found = M.attachedMemories.find(function (m) { return m.name === payload.name; });
        if (found) {
          found.description = meta.description || meta.name || "";
          M.renderMemoryPreview();
        }
      });
    }
  };

  M.removeMemory = function(index) {
    if (!M.attachedMemories) return;
    M.attachedMemories.splice(index, 1);
    M.renderMemoryPreview();
  };

  M.clearMemories = function() {
    M.attachedMemories = [];
    M.renderMemoryPreview();
  };

  /**
   * Convert the attached ticket arrangement to the payload structure for backend transmission.
   * Text prepend policy pulmonary (T-427 → T-429) — User message text only,
   * SDK Encoding content
   * Combines the user role in the array with additional text blocks.
   *
   * null return null return (payload tos attachment field not insert).
   *
   * @param {Array<{number,title,command,prompt,result,report,addedAt}>|undefined} tickets
   * @returns {Array<{number,command,title,prompt,report,fetched_at}>|null}
   */
  function _buildAttachmentsPayload(tickets) {
    if (!tickets || tickets.length === 0) return null;
    return tickets.map(function (t) {
      return {
        number: t.number || "",
        command: t.command || "",
        title: t.title || "",
        prompt: t.prompt || "",
        report: t.report || "",
        // When attaching(=DnD after client is fetched the ticket payload + report.html)
        // Backend / sidecar is easy to identify with the same message string.
        fetched_at: t.addedAt || null
      };
    });
  }

  /**
   * Specifies that the string is a file path pattern.
   * - Unix absolute path: / start, // except (Protocol relative URL)
   * - Windows absolute path: C:\ drive letter
   * - Multiple line paths: if each line is a path pattern
   * - URL (http://, https://) excluded
   */
  M.isFilePath = function(text) {
    if (!text) return false;
    // URL
    if (/^https?:\/\//i.test(text.trim())) return false;
    // If multiple lines check each line and all path patterns are true
    var lines = text.trim().split(/\r?\n/);
    var pathLine = /^\/[^\/\s]+\/|^[A-Za-z]:\\/;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (line && !pathLine.test(line)) return false;
    }
    return pathLine.test(lines[0].trim());
  };

  /**
   * Insert text in the current cursor position of textarea(selectionStart/End).
   */
  M.insertTextAtCursor = function(textarea, text) {
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    var before = textarea.value.substring(0, start);
    var after = textarea.value.substring(end);
    textarea.value = before + text + after;
    var pos = start + text.length;
    textarea.selectionStart = pos;
    textarea.selectionEnd = pos;
    textarea.focus();
    // Automatic height adjustment trigger by generating input event
    var evt = document.createEvent("Event");
    evt.initEvent("input", true, true);
    textarea.dispatchEvent(evt);
  };

  /**
   * . terminal-input-card
   */
  M.showFileBadge = function(card, names) {
    // Home
    var prev = card.querySelector(".terminal-file-badge");
    if (prev) prev.parentNode.removeChild(prev);

    var badge = document.createElement("div");
    badge.className = "terminal-file-badge";
    badge.textContent = names.join(", ");
    card.appendChild(badge);

    setTimeout(function () {
      if (badge.parentNode) badge.parentNode.removeChild(badge);
    }, 3000);
  };

  M.setInputLocked = function(locked) {
    M.inputLocked = locked;
    var input = document.getElementById("terminal-input");
    var sendBtn = document.getElementById("terminal-send-btn");
    // In a busy state, the input window is active (allows to queue input). idle/busy only inputtable.
    // stopped/starting/archived/missing silver input inert.
    // exception: ESC autoResume Windows ( inAutoResume) stopped/starting is short
    // It does not maintain input.disabled even exposed — input window flashes.
    var inAutoResume = !!Board.state._inAutoResume;
    var inputtable = Board.util.TERM_STATUS_INPUTTABLE.has(Board.state.termStatus)
        || inAutoResume;
    var shouldDisable = !inputtable;
    var prevDisabled = input ? input.disabled : null;
    if (Board.debugLog) Board.debugLog('setInputLocked', {
      locked: locked,
      termStatus: Board.state.termStatus,
      inAutoResume: inAutoResume,
      inputtable: inputtable,
      shouldDisable: shouldDisable,
      prevDisabled: prevDisabled,
      willChange: prevDisabled !== shouldDisable,
    });
    if (input) {
      input.disabled = shouldDisable;
      if (!shouldDisable) {
        input.focus();
      }
    }
    if (sendBtn) {
      sendBtn.disabled = shouldDisable;
    }
    var attachBtn = document.getElementById("terminal-attach-btn");
    if (attachBtn) {
      attachBtn.disabled = shouldDisable;
    }
  };

  M.sendInput = function() {
    if (M.isWorkflowMode) return;
    var input = document.getElementById("terminal-input");
    if (!input) return;
    var text = input.value.trim();
    var hasImages = M.attachedImages.length > 0;
    var hasTickets = M.attachedTickets && M.attachedTickets.length > 0;
    var hasMemories = M.attachedMemories && M.attachedMemories.length > 0;
    if (Board.debugLog) Board.debugLog('sendInput.entry', {
      termStatus: Board.state.termStatus,
      textLen: text.length,
      hasImages: hasImages,
      hasTickets: hasTickets,
      hasMemories: hasMemories,
      queueSize: M.inputQueue ? M.inputQueue.length : 0,
      willQueue: Board.state.termStatus === "busy",
    });
    if (!text && !hasImages && !hasTickets && !hasMemories) return;
    var inputtable = Board.util.TERM_STATUS_INPUTTABLE;
    // inAutoResume Allows stop/starting even send during Windows — after process new spawn
    // Instant idle arrives so you can try to send user even in short races.
    // (for server-side send input guard processing at race)
    if (!inputtable.has(Board.state.termStatus) && !Board.state._inAutoResume) return;

    input.value = "";
    input.style.height = "auto";

    // Route slash commands (to process immediately without putting on the order) — Slash commands for the future if images/Tickets/Memory
    // M.isFilePath() check: /home/... The file path is not routed as a slash command
    if (!hasImages && !hasTickets && !hasMemories && text.charAt(0) === "/" && !M.isFilePath(text)) {
      Board.slashCommands.handle(text, {
        isWorkflowMode: M.isWorkflowMode,
        appendSystemMessage: M.appendSystemMessage,
        appendHtmlBlock: M.appendHtmlBlock,
        appendErrorMessage: M.appendErrorMessage,
        clearOutput: M.clearOutput,
        postJson: Board.session.postJson
      });
      return;
    }

    // T-429: Attachment body prepend policy closure — sendText is user text intact.
    // Attached ticket body sends to separates payload field (backend is SDK)
    // When the user role content array is combined with additional text blocks.
    //
    // memory attachments inline the body with the path only prefix block (user crystal: body fetch
    // Without a Assistant Read). so does not add to backends field.
    var sendText = text;
    if (hasMemories) {
      var memoryLines = M.attachedMemories.map(function (m) {
        var label = m.description || m.name;
        return "- " + label + ": memory/" + m.name;
      });
      var prefixBlock = "[Note Memory]\\n" + memoryLines.join("\n");
      sendText = text ? prefixBlock + "\n\n" + text : prefixBlock;
    }
    var attachmentsPayload = hasTickets ? _buildAttachmentsPayload(M.attachedTickets) : null;
    // meta snapshot for outputDiv card renderer (preserved before ticket/memory clear)
    var ticketsSnapshot = hasTickets ? M.attachedTickets.slice() : null;
    var memoriesSnapshot = hasMemories ? M.attachedMemories.slice() : null;

    // If you have a busy status (with response wait), you can route it to enqueueInput (with image/ticket).
    // cue entry is not pre-echo in outputDiv, and only exposure to cue stack cards.
    if (Board.state.termStatus === "busy") {
      var imagesSnapshot = hasImages
        ? M.attachedImages.map(function (img) { return { data: img.data, media_type: img.media_type, name: img.name }; })
        : null;
      // CommitQueueue is the same as the commitQueueue to the idle transition.
      M.enqueueInput(sendText, imagesSnapshot, attachmentsPayload);
      if (hasImages) {
        M.clearImages();
        M.clearFiles();
      }
      if (hasTickets) {
        M.clearTickets();
      }
      if (hasMemories) {
        M.clearMemories();
      }
      return;
    }

    var div = document.createElement("div");
    div.className = "term-message term-user";
    if (sendText) div.textContent = sendText;
    if (hasImages) {
      var thumbRow = document.createElement("div");
      thumbRow.style.cssText = "display:flex;gap:4px;flex-wrap:wrap;margin-top:4px;";
      M.attachedImages.forEach(function (img) {
        var t = document.createElement("img");
        t.src = "data:" + img.media_type + ";base64," + img.data;
        t.style.cssText = "width:48px;height:48px;object-fit:cover;border-radius:6px;border:1px solid #3a3a3a;";
        thumbRow.appendChild(t);
      });
      div.appendChild(thumbRow);
    }
    M.appendToOutput(div);

    // T-429: Added echo to .term-message-attachments container with div and alias.
    // Attach-card.js reuses a single true source heaper to match the input side card and the look&pilot.
    // echo by type="memory" in the same container as memory attachment.
    var hasAttachmentEcho = (ticketsSnapshot && ticketsSnapshot.length > 0)
      || (memoriesSnapshot && memoriesSnapshot.length > 0);
    if (hasAttachmentEcho && M.attachmentCard && typeof M.attachmentCard.create === "function") {
      var attachContainer = document.createElement("div");
      attachContainer.className = "term-message-attachments";
      if (ticketsSnapshot) {
        ticketsSnapshot.forEach(function (att) {
          attachContainer.appendChild(M.attachmentCard.create(att));
        });
      }
      if (memoriesSnapshot) {
        memoriesSnapshot.forEach(function (mem) {
          attachContainer.appendChild(M.attachmentCard.create({
            type: "memory",
            name: mem.name,
            category: mem.category,
            title: mem.description || mem.name,
            subtitle: mem.name
          }));
        });
      }
      M.appendToOutput(attachContainer);
    }

    // Transfer payload configuration — text is user free input, attachments are attached to the attachments field.
    var payload = { text: sendText };
    if (hasImages) {
      payload.images = M.attachedImages.map(function (img) {
        return { data: img.data, media_type: img.media_type };
      });
    }
    if (attachmentsPayload && attachmentsPayload.length > 0) {
      payload.attachments = attachmentsPayload;
    }
    M.clearImages();
    M.clearFiles();
    if (hasTickets) M.clearTickets();
    if (hasMemories) M.clearMemories();

    // Mark sendText as locally sent so the user_input SSE echo is skipped.
    // sendText = text = user free input → SSE user input.text matches exactly.
    if (sendText && Board.session && Board.session._markSent) {
      Board.session._markSent(sendText);
    }

    // ESC INTERFLOW SHIELD SHIELD SHIELD SHIELD
    // Restoration target is only a user-friendly input area — no means that the attachment card itself disappears.
    M._lastSentText = text || "";
    // Since we sent a new message, localStorage's ESC restore text is clear.
    try { localStorage.removeItem("board.term.lastSentText"); } catch (e) {}

    M.setInputLocked(true);
    M.startSpinner();
    Board.state.setTermStatus("busy");
    M.updateControlBar();
    // "I want to see the latest response"
    // isNearBottom static and unparalleled user messages + go to the bottom to see the spinner.
    if (M.outputDiv) M.outputDiv.scrollTop = M.outputDiv.scrollHeight;

    var ep = M.endpoints();
    Board.session.postJson(ep.input, ep.inputBody(payload)).catch(function (err) {
      M.stopSpinner();
      M.appendErrorMessage("[Error] " + err.message);
      M.setInputLocked(false);
      Board.state.setTermStatus("idle");
      M.updateControlBar();
    });
  };

  // drainQueueue is the old API (string push method). In the 1:1 model, commitQueue.
  // session.js fallback can be called in the path, so preserved by alias.
  M.drainQueue = function() {
    if (M.isWorkflowMode) return;
    M.commitQueue();
  };

  M.interruptSession = function() {
    if (M.isWorkflowMode) return;
    if (Board.state.termStatus !== "busy") return;
    if (M._interruptInFlight) return;
    M._interruptInFlight = true;
    // [ESC Automatic Guard] The flag to recognize the process exit that arrives immediately after ESC.
    // exit code will cover the possibility not 130 due to SDK graceful shutdown.
    // Auto clear after 5 seconds (the user has another action after ESC).
    M._recentInterrupt = true;
    if (M._recentInterruptTimer) clearTimeout(M._recentInterruptTimer);
    M._recentInterruptTimer = setTimeout(function () {
      M._recentInterrupt = false;
      M._recentInterruptTimer = null;
    }, 5000);
    M.updateControlBar();

    Board.session.postJson("/terminal/interrupt").then(function () {
      M.stopSpinner();
      if (M.textBuffer) {
        if (Board.WfTicketRenderer && Board.WfTicketRenderer.detect(M.textBuffer)) {
          Board.WfTicketRenderer.render(M.textBuffer);
        } else {
          var html = M.renderMarkdownToHtml(M.textBuffer);
          M.appendHtmlBlock(html, "term-message term-assistant");
        }
      }
      M.textBuffer = "";
      // Remove empty toolboxes that did not arrive — check all items in toolBoxMap.
      // If the result is already entered the box, removeEmptyToolBox is not empty and preserved.
      Object.keys(M.toolBoxMap).forEach(function (tuid) {
        M.removeEmptyToolBox(tuid);
      });
      M.toolBoxMap = {};
      M.currentToolBox = null;
      M.toolInputBuffer = "";
      M.currentToolName = null;
      // [Quantity Preservation Policy] ESC is currently stopped response(A) and waited cue(B, C...)
      // Notice idle transition after advanceTurn will send the following items automatically
      // (the same action as the Claude CLI). The queue is determined by the user directly with the queue card × button.
      // [ESC Restoration] Automatically restore user messages sent to the input window
      // The user can edit or send it back.
      // In the input window, if the user already typing a new text, it can be blank before preserving
      // prepend (not over). Save localStorage even and keep after a new one.
      if (M._lastSentText) {
        var inputEl = document.getElementById("terminal-input");
        if (inputEl) {
          inputEl.value = inputEl.value
            ? M._lastSentText + " " + inputEl.value
            : M._lastSentText;
          inputEl.style.height = "auto";
          inputEl.style.height = inputEl.scrollHeight + "px";
        }
        try { localStorage.setItem("board.term.lastSentText", M._lastSentText); } catch (e) {}
        M._lastSentText = "";
      }
      M.updateControlBar();
      // Change the status and unlock the result SSE event handler.
      // The Claude CLI after SIGINT must be issued a result event, so it does not change directly here.
      // (When the server is still running, the client switched to idle and 409 occurrences)
      // interruptInFlight  onResult
    }).catch(function (err) {
      M.appendErrorMessage("[Error] Failed to interrupt: " + err.message);
      M._interruptInFlight = false;
      M.updateControlBar();
    });
  };

  // ── Queue Model ──

  /**
   * Add the input text to the queue (1:1 turn model).
   *
   * - Push the extra input during busy to the flat queue.
   * - Cue entry is not pre-echo in message flow.
   * - Perform only hint count update (updateControlBar call).
   * - idle commit timer / turn-id generation / nextTurn field no object.
   *
   * @param {string} text - Add text
   */
  /**
   * Add the entry card to the queue stack.
   * The container is hidden. × Deleted connection with entry click handler.
   * Image attachment entry: "[Emiji N]" label, if text + end "[+N]" notation.
   */
  function _renderQueueCard(entry) {
    var container = document.getElementById("terminal-input-queue");
    if (!container) return;

    var imageCount = entry.images ? entry.images.length : 0;
    var attachCount = entry.attachments ? entry.attachments.length : 0;
    var labels = [];
    if (imageCount > 0) labels.push("NEWS" + imageCount + "News");
    if (attachCount > 0) labels.push("NEWS" + attachCount + "Notice");
    var labelStr = labels.join(" ");
    var displayText = entry.text || "";
    if (displayText && labelStr) {
      displayText = displayText + " " + labelStr;
    } else if (!displayText && labelStr) {
      displayText = labelStr;
    }

    var item = document.createElement("div");
    item.className = "terminal-queue-item";
    item.setAttribute("data-entry-id", entry.id);
    item.title = displayText; // Full text exposure to hover (one line ellipsis complement)

    var textSpan = document.createElement("span");
    textSpan.className = "terminal-queue-text";
    textSpan.textContent = displayText;

    var removeBtn = document.createElement("button");
    removeBtn.className = "terminal-queue-remove";
    removeBtn.type = "button";
    removeBtn.title = "Remove from queue";
    removeBtn.innerHTML = "&times;";
    (function (eid) {
      removeBtn.addEventListener("click", function (ev) {
        ev.stopPropagation();
        if (typeof M.removePendingEntry === "function") M.removePendingEntry(eid);
      });
    })(entry.id);

    item.appendChild(textSpan);
    item.appendChild(removeBtn);
    container.appendChild(item);

    if (container.hasAttribute("hidden")) container.removeAttribute("hidden");
  }

  /**
   * Removes certain entry cards from cue stack. Default Container hidden.
   */
  function _removeQueueCard(entryId) {
    var container = document.getElementById("terminal-input-queue");
    if (!container) return;
    var item = container.querySelector('[data-entry-id="' + entryId + '"]');
    if (item && item.parentNode) item.parentNode.removeChild(item);
    if (!container.children.length) container.setAttribute("hidden", "");
  }

  M.enqueueInput = function(text, images, attachments) {
    text = text || "";
    images = images || null;
    // T-429: Retention to attachments — echo + separating transmission equally when commitQueueue.
    var attachList = (attachments && attachments.length > 0) ? attachments : null;
    var hasImages = images && images.length > 0;
    var hasAttachments = !!attachList;
    if (Board.debugLog) Board.debugLog('enqueueInput.entry', {
      termStatus: Board.state.termStatus,
      textLen: text.length,
      hasImages: hasImages,
      hasAttachments: hasAttachments,
      queueSizeBefore: M.inputQueue ? M.inputQueue.length : 0,
    });
    if (!text && !hasImages && !hasAttachments) return;

    var entry = {
      id: "entry-" + Date.now() + "-" + Math.floor(Math.random() * 0x10000).toString(16),
      text: text,
      images: hasImages ? images : null,
      attachments: attachList,
      ts: Date.now(),
      status: "pending"
    };

    M.inputQueue.push(entry);

    // Add card to queue stack (input right alignment area above).
    _renderQueueCard(entry);

    // hint area count also update.
    M.updateControlBar();
  };

  /**
   * dequeue → outputDiv
   *
   * Tag:
   * (a) Enter new in idle condition (terminal.js keydown handler)
   * (b) busy → idle transition during advanceTurn this residual queue processing
   *
   * ignored when calling busy (processed as an advanceTurn path).
   */
  M.commitQueue = function() {
    if (Board.debugLog) Board.debugLog('commitQueue.entry', {
      termStatus: Board.state.termStatus,
      queueSize: M.inputQueue ? M.inputQueue.length : 0,
    });
    // If you are busy, commit ignore — advanceTurn will be handled after arrival
    if (Board.state.termStatus === "busy") return;

    // getting fucked
    if (M.inputQueue.length === 0) return;

    // First entry 1 dequeue (1 turn = 1 message)
    var entry = M.inputQueue.shift();

    // Remove the corresponding card from queue stack (dequeue → process start time signal)
    _removeQueueCard(entry.id);

    // echo in message flow (term-message term-user — text + image thumbnail)
    var div = document.createElement("div");
    div.className = "term-message term-user";
    if (entry.text) div.textContent = entry.text;
    if (entry.images && entry.images.length > 0) {
      var thumbRow = document.createElement("div");
      thumbRow.style.cssText = "display:flex;gap:4px;flex-wrap:wrap;margin-top:4px;";
      entry.images.forEach(function (img) {
        var t = document.createElement("img");
        t.src = "data:" + img.media_type + ";base64," + img.data;
        t.style.cssText = "width:48px;height:48px;object-fit:cover;border-radius:6px;border:1px solid #3a3a3a;";
        thumbRow.appendChild(t);
      });
      div.appendChild(thumbRow);
    }
    if (M.appendToOutput) M.appendToOutput(div);

    // T-429: Add an attachment card to a separate container echo (sendInput direct route same separating wrender).
    if (entry.attachments && entry.attachments.length > 0 && M.attachmentCard && typeof M.attachmentCard.create === "function") {
      var attachContainer = document.createElement("div");
      attachContainer.className = "term-message-attachments";
      entry.attachments.forEach(function (att) {
        attachContainer.appendChild(M.attachmentCard.create(att));
      });
      if (M.appendToOutput) M.appendToOutput(attachContainer);
    }

    // SSE user input echo anti-duplication with sent marking (text only — image/perfect echo is indispensable)
    if (entry.text && Board.session && Board.session._markSent) {
      Board.session._markSent(entry.text);
    }

    // ESC INTERFLOW SHIELD SHIELD SHIELD SHIELD
    M._lastSentText = entry.text || "";
    // Since we sent a new message, localStorage's ESC restore text is clear.
    try { localStorage.removeItem("board.term.lastSentText"); } catch (e) {}

    M.startSpinner();
    Board.state.setTermStatus("busy");
    M.setInputLocked(true);
    if (M.outputDiv) M.outputDiv.scrollTop = M.outputDiv.scrollHeight;
    M.updateControlBar();

    // payload configuration — text + image + attachment (each separated field)
    var payload = { text: entry.text || "" };
    if (entry.images && entry.images.length > 0) {
      payload.images = entry.images.map(function (img) {
        return { data: img.data, media_type: img.media_type };
      });
    }
    if (entry.attachments && entry.attachments.length > 0) {
      payload.attachments = entry.attachments;
    }

    var ep = M.endpoints();
    Board.session.postJson(ep.input, ep.inputBody(payload)).catch(function (err) {
      M.stopSpinner();
      M.appendErrorMessage("[Error] " + err.message);
      M.setInputLocked(false);
      Board.state.setTermStatus("idle");
      M.updateControlBar();
    });
  };

  /**
   * Remove pending entry from the queue (click on the hint panel × button).
   *
   * - Remove the inputQueue only.
   * - Since outputDiv DOM is not pre-echo, DOM operation is unnecessary.
   * - hint panel rerender is entrusted to updateControlBar.
   *
   * @param {string} entryId - Removed entry id
   */
  M.removePendingEntry = function(entryId) {
    M.inputQueue = M.inputQueue.filter(function (e) { return e.id !== entryId; });
    // Remove the card from the queue stack (× button click reflect)
    _removeQueueCard(entryId);
    // hint panel rerender
    M.updateControlBar();
  };

  /**
   * Turn result SSE session.js  onResult is called upon arrival.
   *
   * 1:1 turn model:
   * - If there is a residual queue entry, then turn to commitQueue() immediately
   * - Without idle clearance (spinner stop / unlock)
   *
   * commitQueueue executes spinner stop + idle status conversion before calling.
   * CommitQueue will switch back to busy inside.
   */
  M.advanceTurn = function() {
    M.stopSpinner();
    M.setInputLocked(false);
    Board.state.setTermStatus("idle");

    if (M.inputQueue.length > 0) {
      // If you have a residual queue entry, please immediately send the following entry
      M.commitQueue();
    } else {
      // Curriculum — idle Clearance
      M.updateControlBar();
    }
  };

})();
