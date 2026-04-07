/**
 * @module workflow-bar
 *
 * WorkflowRenderer (banner parser + state machine) and phaseTimeline (DOM renderer).
 *
 * Parses Bash tool_use_result text for workflow banner patterns emitted by
 * flow-claude, flow-init, flow-step, flow-phase, and flow-finish scripts.
 * phaseTimeline renders the timeline bar DOM below .terminal-session-bar.
 *
 * Depends on: common.js (Board namespace)
 * Registers:  Board.WorkflowRenderer, Board.phaseTimeline
 */
"use strict";

(function () {

  // ── ANSI strip utility ──

  var ANSI_STRIP_RE = /\x1b\[[0-9;]*m/g;
  function stripAnsi(text) {
    return (text || "").replace(ANSI_STRIP_RE, "");
  }

  // ── WorkflowRenderer namespace ──

  var WorkflowRenderer = (function () {

    // ── Pattern constants ──

    var P = {
      workflowBoxTop:    /╔[═]+╗/,
      workflowStartCmd:  /║\s+▶\s+(\S+)/,
      workflowEnd:       /║\s+\[OK\]\s+(\S+)\s+·\s+(.+?)(?:\s+\((\w+)\))?$/,
      endBorder:         /^[═]{10,}$/,
      init:              /║\s+INIT:\s+(.+)$/,
      initWorkDir:       /║\s+(\.claude\.workflow\/workflow\/[^\s]+)$/,
      stepStart:         /║\s+\[●[^\]]*\]\s+(PLAN|WORK|REPORT|DONE)/,
      stepEnd:           /║\s+\[●[^\]]*\]\s+(PLAN|WORK|REPORT|DONE)\s+-\s+(.+)$/,
      artifactLine:      /║\s+(\.claude\.workflow\/workflow\/[^\s]+)$/,
      stepOk:            /║\s+\[OK\]\s+(\S+)$/,
      stepAsk:           /║\s+\[ASK\]\s+(\S+)$/,
      phase:             /║\s+STATE:\s+Phase\s+(\d+)\s+(sequential|parallel)/,
      phaseAgents:       /║\s+>>\s+([^\[]+?)(?:\s+\[([^\]]+)\])?$/,
      finishDone:        /║\s+DONE:\s+워크플로우\s+(완료|실패)/,
      finishKey:         /║\s+(\d{8}-\d{6})$/,
      fail:              /^FAIL$/
    };

    // ── Step Panel constants ──

    var STEP_COLORS = {
      unknown: "#858585",
      init:    "#858585",
      plan:    "#569cd6",
      work:    "#D97757",
      report:  "#c586c0",
      done:    "#4ec9b0",
      failed:  "#f48771"
    };

    var STEP_STATUS_LABELS = {
      active: "\uC9C4\uD589 \uC911",
      done:   "\uC644\uB8CC"
    };

    // ── Default state ──

    var DEFAULT_STATE = {
      command:      "",
      workId:       "",
      title:        "",
      workDir:      "",
      currentStep:  "init",
      currentPhase: -1,
      phases:       [],
      artifacts:    [],
      status:       "running",
      error:        undefined
    };

    // ── Internal mutable state ──

    var _state = {};

    /** @type {HTMLElement|null} Current active step panel DOM element */
    var _activeStepPanel = null;

    /** @type {Object<string, HTMLElement>} Map of step name -> panel DOM */
    var _stepPanels = {};

    var _pendingInit = false;
    var _pendingInitTitle = "";
    var _pendingStepEnd = false;
    var _pendingStepEndName = "";
    var _pendingStepEndTs = "";
    var _pendingPhase = false;
    var _pendingPhaseN = -1;
    var _pendingPhaseMode = "";
    var _inBox = false;
    var _boxHasCmd = false;
    var _pendingFinish = false;
    var _pendingFinishResult = "";

    function _reset(command) {
      _state = {
        command:      command || "",
        workId:       "",
        title:        "",
        workDir:      "",
        currentStep:  "init",
        currentPhase: -1,
        phases:       [],
        artifacts:    [],
        status:       "running",
        error:        undefined
      };
      _activeStepPanel = null;
      _stepPanels = {};
      _clearParserFlags();
    }

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

    function _setInit(title, workDir) {
      _state.title = title;
      _state.workDir = workDir;
      _state.currentStep = "init";
    }

    function _setStep(stepName) {
      var prevStep = _state.currentStep;
      _state.currentStep = stepName.toLowerCase();

      // Mark previous step panel as done
      if (prevStep && prevStep !== _state.currentStep && _stepPanels[prevStep]) {
        var prevPanel = _stepPanels[prevStep];
        prevPanel.setAttribute("data-status", "done");
        var prevStatusEl = prevPanel.querySelector(".wf-step-panel-status");
        if (prevStatusEl) {
          prevStatusEl.setAttribute("data-status", "done");
          prevStatusEl.textContent = STEP_STATUS_LABELS.done;
        }
        var prevIcon = prevPanel.querySelector(".wf-step-panel-icon");
        if (prevIcon) prevIcon.textContent = "\u2713";
      }

      // Create or activate panel for new step
      _activeStepPanel = _getOrCreateStepPanel(_state.currentStep);
    }

    function _setPhase(n, mode, agents, taskIds) {
      _state.phases.push({
        n:       n,
        agents:  agents  || [],
        taskIds: taskIds || [],
        mode:    mode
      });
      _state.currentPhase = n;
    }

    // ── Step Panel DOM management ──

    function _getOrCreateStepPanel(stepName) {
      if (_stepPanels[stepName]) return _stepPanels[stepName];

      var outputDiv = document.getElementById("terminal-output");
      if (!outputDiv) return null;

      var panel = document.createElement("div");
      panel.className = "wf-step-panel";
      panel.setAttribute("data-step", stepName);
      panel.setAttribute("data-status", "active");

      var color = STEP_COLORS[stepName] || STEP_COLORS.unknown;

      var header = document.createElement("div");
      header.className = "wf-step-panel-header";
      header.style.borderLeftColor = color;

      var icon = document.createElement("span");
      icon.className = "wf-step-panel-icon";
      icon.textContent = "\u25CF";
      icon.style.color = color;
      header.appendChild(icon);

      var name = document.createElement("span");
      name.className = "wf-step-panel-name";
      name.textContent = stepName.toUpperCase();
      header.appendChild(name);

      var status = document.createElement("span");
      status.className = "wf-step-panel-status";
      status.setAttribute("data-status", "active");
      status.textContent = STEP_STATUS_LABELS.active;
      header.appendChild(status);

      panel.appendChild(header);

      var body = document.createElement("div");
      body.className = "wf-step-panel-body";
      panel.appendChild(body);

      // Append to output with scroll
      var follow = Board._term && Board._term.isNearBottom ? Board._term.isNearBottom(outputDiv) : true;
      outputDiv.appendChild(panel);
      if (Board._term && Board._term.scrollToBottomIfFollowing) {
        Board._term.scrollToBottomIfFollowing(outputDiv, follow);
      }

      _stepPanels[stepName] = panel;
      return panel;
    }

    function _insertToCurrentPanel(html) {
      var panel = _activeStepPanel;
      if (!panel) {
        // Fallback: create panel for current step if needed
        panel = _getOrCreateStepPanel(_state.currentStep || "init");
        _activeStepPanel = panel;
      }
      if (!panel) return null;

      var body = panel.querySelector(".wf-step-panel-body");
      if (!body) return null;

      var outputDiv = document.getElementById("terminal-output");
      var follow = Board._term && Board._term.isNearBottom ? Board._term.isNearBottom(outputDiv) : true;

      // MAX_OUTPUT_NODES guard for panel body
      while (body.childNodes.length >= 500) {
        body.removeChild(body.firstChild);
      }

      var container = document.createElement("div");
      container.innerHTML = html;
      body.appendChild(container);

      if (outputDiv && Board._term && Board._term.scrollToBottomIfFollowing) {
        Board._term.scrollToBottomIfFollowing(outputDiv, follow);
      }

      return container;
    }

    function _appendDomToCurrentPanel(domEl) {
      var panel = _activeStepPanel;
      if (!panel) {
        panel = _getOrCreateStepPanel(_state.currentStep || "init");
        _activeStepPanel = panel;
      }
      if (!panel) return;

      var body = panel.querySelector(".wf-step-panel-body");
      if (!body) return;

      var outputDiv = document.getElementById("terminal-output");
      var follow = Board._term && Board._term.isNearBottom ? Board._term.isNearBottom(outputDiv) : true;

      while (body.childNodes.length >= 500) {
        body.removeChild(body.firstChild);
      }

      body.appendChild(domEl);

      if (outputDiv && Board._term && Board._term.scrollToBottomIfFollowing) {
        Board._term.scrollToBottomIfFollowing(outputDiv, follow);
      }
    }

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

    function _setWorkflowEnd(workId, title) {
      if (workId) _state.workId = workId;
      if (title)  _state.title  = title;
    }

    function _complete() {
      _state.status      = "done";
      _state.currentStep = "done";
    }

    function _fail(msg) {
      _state.status      = "failed";
      _state.currentStep = "failed";
      _state.error       = msg || "FAIL";
    }

    // ── Per-line pattern matching ──

    function _parseLine(line) {
      var m;

      if (P.workflowBoxTop.test(line)) {
        _inBox    = true;
        _boxHasCmd = false;
        return true;
      }

      if (P.endBorder.test(line)) {
        _pendingStepEnd = false;
        return true;
      }

      if (_inBox && (m = P.workflowStartCmd.exec(line))) {
        _boxHasCmd = true;
        _inBox     = false;
        _reset(m[1]);
        return true;
      }

      if (_inBox && !_boxHasCmd && (m = P.stepStart.exec(line))) {
        _inBox = false;
        _setStep(m[1]);
        return true;
      }

      if (/╚[═]+╝/.test(line)) {
        _inBox     = false;
        _boxHasCmd = false;
        return true;
      }

      if ((m = P.workflowEnd.exec(line))) {
        _setWorkflowEnd(m[1], m[2].trim());
        return true;
      }

      if ((m = P.init.exec(line))) {
        _pendingInit      = true;
        _pendingInitTitle = m[1].trim();
        _pendingStepEnd = false;
        _pendingPhase   = false;
        return true;
      }

      if (_pendingInit && (m = P.initWorkDir.exec(line))) {
        _setInit(_pendingInitTitle, m[1].trim());
        _pendingInit      = false;
        _pendingInitTitle = "";
        return true;
      }

      if ((m = P.stepEnd.exec(line))) {
        _pendingStepEnd     = true;
        _pendingStepEndName = m[1];
        _pendingStepEndTs   = m[2].trim();
        _setStep(m[1]);
        return true;
      }

      if ((m = P.artifactLine.exec(line))) {
        _addArtifact(m[1].trim());
        return true;
      }

      if (_pendingStepEnd && (P.stepOk.test(line) || P.stepAsk.test(line))) {
        _pendingStepEnd = false;
        return true;
      }

      if ((m = P.phase.exec(line))) {
        _pendingPhase    = true;
        _pendingPhaseN   = parseInt(m[1], 10);
        _pendingPhaseMode = m[2];
        return true;
      }

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

      if ((m = P.finishDone.exec(line))) {
        _pendingFinish       = true;
        _pendingFinishResult = m[1];
        return true;
      }

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

      if (P.fail.test(line)) {
        _fail("FAIL");
        return true;
      }

      return false;
    }

    // ── Public API ──

    return {
      get state() { return _state; },
      patterns: P,

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

      reset: function () {
        _reset();
      },

      /**
       * Get or create a step panel DOM for the given step name.
       * @param {string} stepName
       * @returns {HTMLElement|null}
       */
      getOrCreateStepPanel: function (stepName) {
        return _getOrCreateStepPanel(stepName);
      },

      /**
       * Insert HTML content into the current active step panel's body.
       * @param {string} html
       * @returns {HTMLElement|null} the container element or null
       */
      insertToCurrentPanel: function (html) {
        return _insertToCurrentPanel(html);
      },

      /**
       * Append a DOM element into the current active step panel's body.
       * @param {HTMLElement} domEl
       */
      appendDomToCurrentPanel: function (domEl) {
        _appendDomToCurrentPanel(domEl);
      },

      /**
       * Returns the current active step panel DOM element.
       * @returns {HTMLElement|null}
       */
      getActiveStepPanel: function () {
        return _activeStepPanel;
      }
    };
  })();

  // ── phaseTimeline DOM Renderer ──

  var phaseTimeline = (function () {

    function _getOrCreateBar() {
      var existing = document.getElementById("wf-timeline-bar");
      if (existing) return existing;

      var sessionBar = document.querySelector(".terminal-session-bar");
      if (!sessionBar) return null;

      var bar = document.createElement("div");
      bar.className = "wf-timeline-bar";
      bar.id = "wf-timeline-bar";

      var parent = sessionBar.parentNode;
      if (parent) {
        parent.insertBefore(bar, sessionBar.nextSibling);
      }
      return bar;
    }

    function _esc(s) {
      return String(s || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function _buildStepsRowHtml(st) {
      var labels = { init: "INIT", plan: "PLAN", work: "WORK", report: "REPORT", done: "DONE", failed: "FAIL" };
      var current = st.currentStep || "init";

      var orderedSteps = ["init", "plan", "work", "report", "done"];
      if (current === "failed") {
        orderedSteps.push("failed");
      }

      var stepOrder = {};
      orderedSteps.forEach(function (s, i) { stepOrder[s] = i; });
      var currentIdx = stepOrder[current];

      var html = '<div class="wf-steps-row">';
      orderedSteps.forEach(function (step, idx) {
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

        if (step === "work" && st.currentPhase >= 0) {
          html += '<span class="wf-phase-badge">Phase ' + _esc(String(st.currentPhase)) + '</span>';
        }

        html += '</div>';

        if (idx < orderedSteps.length - 1) {
          html += '<div class="wf-timeline-sep">&rarr;</div>';
        }
      });
      html += '</div>';
      return html;
    }

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

      renderTimelineBar: function () {
        // Guard: requires isWorkflowMode and outputDiv from terminal.js core
        // These are checked via Board.state
        var outputDiv = document.getElementById("terminal-output");
        if (!outputDiv) return;

        var bar = _getOrCreateBar();
        if (!bar) return;

        var st = WorkflowRenderer.state;

        var html = "";
        html += _buildMetaRowHtml(st);
        html += _buildStepsRowHtml(st);
        html += _buildArtifactsRowHtml(st.artifacts);

        bar.innerHTML = html;

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

      renderArtifactLinks: function () {
        var outputDiv = document.getElementById("terminal-output");
        if (!outputDiv) return;

        var bar = document.getElementById("wf-timeline-bar");
        if (!bar) {
          phaseTimeline.renderTimelineBar();
          return;
        }

        var st = WorkflowRenderer.state;

        var existingRow = bar.querySelector(".wf-artifacts-row");
        var newHtml = _buildArtifactsRowHtml(st.artifacts);

        if (newHtml) {
          if (existingRow) {
            existingRow.outerHTML = newHtml;
          } else {
            bar.insertAdjacentHTML("beforeend", newHtml);
          }
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

      renderStatusBadge: function (status, msg) {
        var outputDiv = document.getElementById("terminal-output");
        if (!outputDiv) return;

        var follow = Board._term && Board._term.isNearBottom ? Board._term.isNearBottom(outputDiv) : true;

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
        if (Board._term && Board._term.scrollToBottomIfFollowing) {
          Board._term.scrollToBottomIfFollowing(outputDiv, follow);
        }
      },

      render: function () {
        phaseTimeline.renderTimelineBar();

        var st = WorkflowRenderer.state;
        if (st.status === "done") {
          phaseTimeline.renderStatusBadge("ok");
        } else if (st.status === "failed") {
          phaseTimeline.renderStatusBadge("fail", st.error);
        }
      },

      openArtifact: function (path) {
        var url = "/api/workflow/artifact?path=" + encodeURIComponent(path);
        window.open(url, "_blank");
      },

      insertPlaceholder: function () {
        _getOrCreateBar();
      }

    };
  })();

  // ── Register on Board namespace ──
  Board.WorkflowRenderer = WorkflowRenderer;
  Board.phaseTimeline = phaseTimeline;
})();
