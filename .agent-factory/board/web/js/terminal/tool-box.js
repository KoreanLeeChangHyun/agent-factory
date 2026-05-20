/**
 * @module terminal/tool-box
 * Split from terminal.js. Functions attach to Board._term (M) namespace.
 */
"use strict";

(function () {
  var esc = Board.util.esc;
  var M = (Board._term = Board._term || {});

  // ── Tool Box Toggle Delegation ──
  //
  // session-switcher is outputDiv charitable cloneNode(true) to save/restore
  // To do, cloneNode does not copy addEventListener listener. When creating a box
  // If you hold the click listener in the individual element, the toggles will die after one tap return.
  //
  // outputDiv is a stable node that does not revert to session conversions, so once deliguetion
  // Free from clone impact.

  M.setupToolBoxDelegation = function() {
    if (M._toolBoxDelegationBound) return;
    if (!M.outputDiv) return;
    M.outputDiv.addEventListener("click", function(e) {
      var toggle = e.target.closest && e.target.closest(".term-toggle-icon, .wf-tool-card-toggle");
      if (!toggle) return;
      var container;
      if (toggle.classList.contains("term-toggle-icon")) {
        container = toggle.closest(".term-tool-box");
      } else {
        container = toggle.closest(".wf-tool-card");
      }
      if (!container) return;
      var isOpen = container.classList.toggle("open");
      toggle.classList.toggle("rotated", isOpen);
    });
    M._toolBoxDelegationBound = true;
  };

  // ── Tool Box Renderer ──

  M.createToolBox = function(toolName, toolUseId) {
    // If the previous toolbox is still running, switch to done
    if (M.currentToolBox) {
      var prevStatus = M.currentToolBox.querySelector(".term-tool-status");
      if (prevStatus && prevStatus.classList.contains("running")) {
        prevStatus.className = "term-tool-status done";
        prevStatus.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#3fb950" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
      }
      // If the output of the previous box is empty, remove the premise from the DOM
      var prevFull = M.currentToolBox.querySelector(".term-tool-output-full");
      if (prevFull && prevFull.children.length === 0 && !prevFull.textContent.trim()) {
        M.currentToolBox.remove();
        M.currentToolBox = null;
      }
    }

    var box = document.createElement("div");
    box.className = "term-tool-box";
    if (toolName) {
      box.setAttribute("data-tool-name", toolName);
    }
    if (toolUseId) {
      box.setAttribute("data-tool-use-id", toolUseId);
      M.toolBoxMap[toolUseId] = box;
    }

    var header = document.createElement("div");
    header.className = "term-tool-header";

    var toggleSpan = document.createElement("span");
    toggleSpan.className = "term-toggle-icon";
    toggleSpan.innerHTML = '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 2.5L7.5 6 4 9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    header.appendChild(toggleSpan);

    var labelSpan = document.createElement("span");
    labelSpan.className = "term-tool-label";
    labelSpan.textContent = toolName;
    header.appendChild(labelSpan);

    var statusSpan = document.createElement("span");
    statusSpan.className = "term-tool-status running";
    statusSpan.innerHTML = '<span class="term-tool-status-dot"></span>';
    header.appendChild(statusSpan);

    box.appendChild(header);

    var inputDiv = document.createElement("div");
    inputDiv.className = "term-tool-input";
    box.appendChild(inputDiv);

    var outputArea = document.createElement("div");
    outputArea.className = "term-tool-output";

    var previewDiv = document.createElement("div");
    previewDiv.className = "term-tool-output-preview";
    outputArea.appendChild(previewDiv);

    var fullDiv = document.createElement("div");
    fullDiv.className = "term-tool-output-full";
    outputArea.appendChild(fullDiv);

    box.appendChild(outputArea);

    // Toggle handler is responsible for the outputDiv delegation of M.setupToolBoxDelegation.
    // inline addEventListener when converting session with cloneNode(true)
    // Regression response (T-390 follow-up).

    M.appendToOutput(box);
    M.currentToolBox = box;

    return box;
  };

  M.removeEmptyToolBox = function(targetToolUseId) {
    // If specified a specific toolUseId, only the corresponding box is cleaned
    if (targetToolUseId && M.toolBoxMap[targetToolUseId]) {
      var targetBox = M.toolBoxMap[targetToolUseId];
      var targetFull = targetBox.querySelector(".term-tool-output-full");
      if (targetFull && targetFull.children.length === 0 && !targetFull.textContent.trim()) {
        if (targetBox.parentNode) {
          targetBox.parentNode.removeChild(targetBox);
        }
        delete M.toolBoxMap[targetToolUseId];
        if (M.currentToolBox === targetBox) {
          M.currentToolBox = null;
        }
      }
    }

    // M.currentToolBox Cleanup (Compatible)
    if (M.currentToolBox) {
      var fullDiv = M.currentToolBox.querySelector(".term-tool-output-full");
      if (fullDiv && fullDiv.children.length === 0 && !fullDiv.textContent.trim()) {
        if (M.currentToolBox.parentNode) {
          M.currentToolBox.parentNode.removeChild(M.currentToolBox);
        }
        M.currentToolBox = null;
      }
    }

    // M.toolBoxMap
    var mapKeys = Object.keys(M.toolBoxMap);
    for (var mi = 0; mi < mapKeys.length; mi++) {
      var mapBox = M.toolBoxMap[mapKeys[mi]];
      var mapFull = mapBox.querySelector(".term-tool-output-full");
      if (mapFull && mapFull.children.length === 0 && !mapFull.textContent.trim()) {
        if (mapBox.parentNode) {
          mapBox.parentNode.removeChild(mapBox);
        }
        delete M.toolBoxMap[mapKeys[mi]];
      }
    }

    // DOM direct congratulation: Unregistered residual empty boxes in toolBoxMap
    if (M.outputDiv) {
      var domBoxes = M.outputDiv.querySelectorAll(".term-tool-box");
      for (var di = 0; di < domBoxes.length; di++) {
        var domBox = domBoxes[di];
        var domFull = domBox.querySelector(".term-tool-output-full");
        if (domFull && domFull.children.length === 0 && !domFull.textContent.trim()) {
          var domToolUseId = domBox.getAttribute("data-tool-use-id");
          if (domBox.parentNode) {
            domBox.parentNode.removeChild(domBox);
          }
          if (domToolUseId && M.toolBoxMap[domToolUseId]) {
            delete M.toolBoxMap[domToolUseId];
          }
          if (M.currentToolBox === domBox) {
            M.currentToolBox = null;
          }
        }
      }
    }

    // Workflow Mode Card
    M.removeEmptyWorkflowToolCard();
  };

  M.removeEmptyWorkflowToolCard = function() {
    if (!M.currentWorkflowToolCard) return;
    var cardBody = M.currentWorkflowToolCard.querySelector(".wf-tool-card-body");
    if (cardBody && cardBody.children.length === 0 && !cardBody.textContent.trim()) {
      if (M.currentWorkflowToolCard.parentNode) {
        M.currentWorkflowToolCard.parentNode.removeChild(M.currentWorkflowToolCard);
      }
      M.currentWorkflowToolCard = null;
    }
  };

  // ── Path Compression Helpers ──
  //
  // compressPathLike: removes the directory prefix of the path string and returns only basename.
  // lastIndexOf-type adoption — regular global replace when each segment is concatenate
  // Prevent bugs (W01-hotfix). One-word filename contains random characters normal processing.
  // returns empty strings if the input is non-string/falsy.
  M._compressPathLike = function(str) {
    if (typeof str !== "string" || !str) return "";
    // lastIndexOf Method: Preventing bugs that are concatenate when global replace.
    // greedy match
    // One-word filename (e.g. tool-card-path-compression) also handles the normal.
    var idx = str.lastIndexOf("/");
    return idx >= 0 ? str.substring(idx + 1) : str;
  };

  // buildToolInputSummary: insertToolResult / insertWorkflowResult Both Share
  // input summary builder. If/else ladders of each existing function are extracted into a single helper.
  // return value: { summary, title, isFlow, flowCommand }
  //   summary - short description that will be exposed to textContent on the card
  //   title - title/aria-label
  //   isFlow - Bash flow-
  //   flowCommand - flowCommand original (for M. formatFlowCommand input)
  M._buildToolInputSummary = function(toolName, parsedInput) {
    var summary = "";
    var title = "";
    var isFlow = false;
    var flowCommand = "";

    if (toolName === "Bash" && parsedInput.command) {
      summary = "$ " + parsedInput.command;
      title = summary;
      if (M.isFlowCommand(parsedInput.command)) {
        isFlow = true;
        flowCommand = parsedInput.command;
      }
    } else if ((toolName === "Read" || toolName === "Write" || toolName === "Edit") && parsedInput.file_path) {
      summary = M._compressPathLike(parsedInput.file_path);
      title = parsedInput.file_path;
    } else if (toolName === "Grep" && parsedInput.pattern) {
      // pattern for compression (glob pattern `**/*.js` prevents damage)
      // Apply compression only for path arguments
      var rawPath = parsedInput.path || "";
      var compressedPath = rawPath ? M._compressPathLike(rawPath) : "";
      summary = parsedInput.pattern + (compressedPath ? "  " + compressedPath : "");
      title = parsedInput.pattern + (rawPath ? "  " + rawPath : "");
    } else if (toolName === "Glob" && parsedInput.pattern) {
      // Because the entire pattern is a glob pattern, it is prohibited to compress
      summary = parsedInput.pattern;
      title = parsedInput.pattern;
    } else {
      var pairs = [];
      var keys = Object.keys(parsedInput);
      for (var ki = 0; ki < keys.length && ki < 3; ki++) {
        var v = parsedInput[keys[ki]];
        if (typeof v === "string") {
          pairs.push(keys[ki] + ": " + (v.length > 40 ? v.slice(0, 40) + "…" : v));
        }
      }
      summary = pairs.join("  ");
      title = summary;
    }

    return { summary: summary, title: title, isFlow: isFlow, flowCommand: flowCommand };
  };

  M.isFlowCommand = function(commandStr) {
    return /^flow-/.test((commandStr || '').trim());
  };

  M._formatFlowCommand = function(cmdStr) {
    var raw = (cmdStr || '').replace(/^\$\s*/, '');
    // Split into base command and --args, respecting quoted strings
    var parts = [];
    var base = '';
    var re = /(--\S+)\s+("(?:[^"\\]|\\.)*"|\S+)/g;
    var firstArgIdx = raw.search(/\s--/);
    if (firstArgIdx > 0) {
      base = raw.substring(0, firstArgIdx).trim();
    } else {
      base = raw;
    }
    var m;
    while ((m = re.exec(raw)) !== null) {
      var key = m[1];
      var val = m[2].replace(/^"|"$/g, '');
      parts.push({ key: key, val: val });
    }
    if (!parts.length) {
      return '<span class="flow-cmd-base">' + esc(raw) + '</span>';
    }
    var html = '<span class="flow-cmd-base">' + esc(base) + '</span>';
    for (var i = 0; i < parts.length; i++) {
      var displayVal = parts[i].val.length > 80
        ? parts[i].val.substring(0, 80) + '\u2026'
        : parts[i].val;
      html += '<div class="flow-cmd-arg">'
        + '<span class="flow-cmd-key">' + esc(parts[i].key) + '</span> '
        + '<span class="flow-cmd-val">' + esc(displayVal) + '</span>'
        + '</div>';
    }
    return html;
  };

  M.insertToolResult = function(text, isError, toolName, toolUseId) {
    // M.currentToolBox fallback if you have toolUseId
    var targetBox = (toolUseId && M.toolBoxMap[toolUseId]) ? M.toolBoxMap[toolUseId] : M.currentToolBox;
    if (!targetBox) return;
    if (!text && !isError) { M.removeEmptyToolBox(toolUseId); return; }
    var fullDiv = targetBox.querySelector(".term-tool-output-full");
    if (!fullDiv) return;

    var resolvedToolName = toolName;
    if (!resolvedToolName && targetBox.getAttribute) {
      resolvedToolName = targetBox.getAttribute("data-tool-name") || undefined;
    }

    var inputDiv = targetBox.querySelector(".term-tool-input");
    var isFlow = false;
    var flowCommand = "";
    if (M.toolInputBuffer && inputDiv) {
      var inputSummary = "";
      var inputTitle = "";
      try {
        var parsedInput = JSON.parse(M.toolInputBuffer);
        var effectiveToolName = resolvedToolName || M.currentToolName;
        var built = M._buildToolInputSummary(effectiveToolName, parsedInput);
        inputSummary = built.summary;
        inputTitle = built.title;
        isFlow = built.isFlow;
        flowCommand = built.flowCommand;
      } catch (_e) {
        inputSummary = "";
        inputTitle = "";
      }
      if (isFlow && flowCommand) {
        inputDiv.innerHTML = M._formatFlowCommand(flowCommand);
      } else {
        inputDiv.textContent = inputSummary;
      }
      // Disable OS native hover tooltip (user request 2026-05-09).
      // Long Command Full View Replaces Box Toggle Unload. aria-label is maintained for accessibility.
      inputDiv.setAttribute("aria-label", inputTitle || inputSummary);
      M.toolInputBuffer = "";
    } else if (M.toolInputBuffer) {
      M.toolInputBuffer = "";
    }

    if (isFlow) {
      targetBox.setAttribute("data-flow-cmd", "true");
      var labelEl = targetBox.querySelector(".term-tool-label");
      if (labelEl) {
        labelEl.textContent = "Flow";
      }
    }

    var html;
    try {
      html = Board.ToolResultRenderer.dispatch(resolvedToolName, text, { isError: !!isError });
    } catch (e) {
      html = '<pre class="term-plain">' + esc(text || '') + '</pre>';
    }

    var container = document.createElement("div");
    container.className = isError ? "term-tool-error" : "term-tool-result-rendered";
    container.innerHTML = html;
    fullDiv.appendChild(container);

    var effectiveTool = resolvedToolName || M.currentToolName;
    var toggleIcon = targetBox.querySelector(".term-toggle-icon");
    var isFlowBox = targetBox.getAttribute("data-flow-cmd") === "true";
    if (isFlowBox) {
      targetBox.classList.add("open");
      if (toggleIcon) toggleIcon.classList.add("rotated");
    } else {
      targetBox.classList.remove("open");
      if (toggleIcon) toggleIcon.classList.remove("rotated");
    }

    var statusEl = targetBox.querySelector(".term-tool-status");
    if (statusEl) {
      statusEl.className = isError ? "term-tool-status error" : "term-tool-status done";
      statusEl.innerHTML = isError
        ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#f85149" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
        : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#3fb950" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    }

    if (!isError) {
      var previewDiv = targetBox.querySelector(".term-tool-output-preview");
      if (previewDiv) {
        var lines = (text || "").split("\n");
        var previewLines = lines.slice(0, 4);
        previewDiv.textContent = previewLines.join("\n");
      }
    }

    // Remove the corresponding item from toolBoxMap after completion of the result insert (Memory leak prevention)
    if (toolUseId && M.toolBoxMap[toolUseId]) {
      delete M.toolBoxMap[toolUseId];
    }
  };

  // ── Workflow Tool Card Renderer ──

  /**
   * Formats elapsed milliseconds into a human-readable duration string.
   * < 1000ms  → "< 1s"
   * 1s–59s    → "X.Xs"  (one decimal place)
   * 60s–59m   → "Xm Ys"
   * ≥ 60min   → "Xh Ym"
   * @param {number} ms - elapsed time in milliseconds
   * @returns {string}
   */
  M.formatDuration = function(ms) {
    if (ms < 1000) return "< 1s";
    var totalSec = ms / 1000;
    if (totalSec < 60) return totalSec.toFixed(1) + "s";
    var totalMin = Math.floor(totalSec / 60);
    var remSec = Math.floor(totalSec % 60);
    if (totalMin < 60) return totalMin + "m " + remSec + "s";
    var hours = Math.floor(totalMin / 60);
    var remMin = totalMin % 60;
    return hours + "h " + remMin + "m";
  };

  /**
   * Creates a compact tool card for workflow step panels.
   * Unlike the full 3-row M.createToolBox(), this renders:
   *   tool name + input summary (1 line) + collapsible output
   * @param {string} toolName
   * @returns {HTMLElement} the card element
   */
  M.createWorkflowToolCard = function(toolName) {
    var panel = Board.WorkflowRenderer.getActiveStepPanel();
    if (!panel) {
      // Fallback: ensure step panel exists
      Board.WorkflowRenderer.getOrCreateStepPanel(
        Board.WorkflowRenderer.state.currentStep || "init"
      );
    }

    var card = document.createElement("div");
    card.className = "wf-tool-card";
    if (toolName) {
      card.setAttribute("data-tool-name", toolName);
    }

    var cardHeader = document.createElement("div");
    cardHeader.className = "wf-tool-card-header";

    var toggleIcon = document.createElement("span");
    toggleIcon.className = "wf-tool-card-toggle";
    toggleIcon.innerHTML = '<svg width="10" height="10" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 2.5L7.5 6 4 9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    cardHeader.appendChild(toggleIcon);

    var toolLabel = document.createElement("span");
    toolLabel.className = "wf-tool-card-name";
    toolLabel.textContent = toolName || "";
    cardHeader.appendChild(toolLabel);

    var inputSpan = document.createElement("span");
    inputSpan.className = "wf-tool-card-input";
    cardHeader.appendChild(inputSpan);

    var timeSpan = document.createElement("span");
    timeSpan.className = "wf-tool-card-time";
    cardHeader.appendChild(timeSpan);

    card.appendChild(cardHeader);
    card.setAttribute("data-start-time", String(Date.now()));
    card.setAttribute("data-running", "true");

    var cardBody = document.createElement("div");
    cardBody.className = "wf-tool-card-body";
    card.appendChild(cardBody);

    // Toggle handler is responsible for M.setupToolBoxDelegation delegation

    // Append to current step panel
    Board.WorkflowRenderer.appendDomToCurrentPanel(card);

    // Track as current tool card for workflow mode
    M.currentWorkflowToolCard = card;
    return card;
  };

  /**
   * Insert tool result into current workflow step panel via compact card.
   * Reuses Board.ToolResultRenderer.dispatch() for HTML generation.
   * @param {string} text - raw output text
   * @param {boolean} isError - error flag
   * @param {string} [toolName] - optional tool name override
   */
  M.insertWorkflowResult = function(text, isError, toolName) {
    if (!text && !isError) return;

    var card = M.currentWorkflowToolCard;
    if (!card) return;

    var cardBody = card.querySelector(".wf-tool-card-body");
    if (!cardBody) return;

    var resolvedToolName = toolName;
    if (!resolvedToolName && card.getAttribute) {
      resolvedToolName = card.getAttribute("data-tool-name") || undefined;
    }

    // Populate input summary on the card header
    var inputSpan = card.querySelector(".wf-tool-card-input");
    var isFlowWf = false;
    var flowCommandWf = "";
    if (M.toolInputBuffer && inputSpan && !inputSpan.textContent) {
      var inputSummary = "";
      var inputTitle = "";
      try {
        var parsedInput = JSON.parse(M.toolInputBuffer);
        var effectiveToolName = resolvedToolName || M.currentToolName;
        var built = M._buildToolInputSummary(effectiveToolName, parsedInput);
        inputSummary = built.summary;
        inputTitle = built.title;
        isFlowWf = built.isFlow;
        flowCommandWf = built.flowCommand;
      } catch (_e) {
        inputSummary = "";
        inputTitle = "";
      }
      inputSpan.textContent = inputSummary;
      // Disable OS native hover tooltip (user request 2026-05-09). Only aria-label is maintained.
      inputSpan.setAttribute("aria-label", inputTitle || inputSummary);
      M.toolInputBuffer = "";
    } else if (M.toolInputBuffer) {
      M.toolInputBuffer = "";
    }

    if (isFlowWf) {
      card.setAttribute("data-flow-cmd", "true");
      var cardNameEl = card.querySelector(".wf-tool-card-name");
      if (cardNameEl) {
        cardNameEl.textContent = "Flow";
      }
      var cardToggle = card.querySelector(".wf-tool-card-toggle");
      card.classList.add("open");
      if (cardToggle) cardToggle.classList.add("rotated");
    }

    var html;
    try {
      html = Board.ToolResultRenderer.dispatch(resolvedToolName, text, { isError: !!isError });
    } catch (e) {
      html = '<pre class="term-plain">' + esc(text || '') + '</pre>';
    }

    var container = document.createElement("div");
    container.className = isError ? "wf-tool-error" : "wf-tool-result";
    container.innerHTML = html;
    cardBody.appendChild(container);

    // Record elapsed time on the card header
    var startTimeAttr = card.getAttribute("data-start-time");
    if (startTimeAttr) {
      var startTime = parseInt(startTimeAttr, 10);
      if (!isNaN(startTime)) {
        var elapsed = Date.now() - startTime;
        var timeEl = card.querySelector(".wf-tool-card-time");
        if (timeEl) {
          timeEl.textContent = M.formatDuration(elapsed);
        }
      }
    }

    // Result arrival = Complete tool execution. During the process, the pulse animation is sticking.
    card.removeAttribute("data-running");

    // Complete status display: success / failure. Attach the SVG icon next to the header right time.
    card.setAttribute("data-status", isError ? "fail" : "success");
    var headerEl = card.querySelector(".wf-tool-card-header");
    if (headerEl && !headerEl.querySelector(".wf-tool-card-status-icon")) {
      var statusIcon = document.createElement("span");
      statusIcon.className = "wf-tool-card-status-icon";
      if (isError) {
        statusIcon.innerHTML = '<svg width="10" height="10" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
      } else {
        statusIcon.innerHTML = '<svg width="10" height="10" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2.5 6.5l2.5 2.5 4.5-5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
      }
      headerEl.appendChild(statusIcon);
    }
  };

  /** @type {HTMLElement|null} Current workflow tool card in step panel */
  M.currentWorkflowToolCard = null;

})();
