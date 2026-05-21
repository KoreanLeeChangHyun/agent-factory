/**
 * @module relations
 *
 * Board SPA relations tab module.
 *
 * Builds a dependency graph from workRequest relations and renders it as a
 * Mermaid flowchart. Provides status filters, layout direction toggle,
 * isolated node toggle, statistics cards, and legend. Clicking a node
 * opens the workRequest in the Viewer tab.
 *
 * Depends on: common.js (Board.state, Board.util, Board.render)
 */
"use strict";

(function () {
  // ── Shared references ──
  var esc = Board.util.esc;
  var COLUMNS = Board.util.COLUMNS;
  var STATUS_COLORS = Board.util.STATUS_COLORS;
  var saveUI = Board.util.saveUI;

  // ── Module State ──
  // Board.state.relations.filter property unit mutation/only
  // saveUI() is automatically subcontracted when calling.
  var filterState = Board.state.relations.filter;

  // Status key normalization for CSS and Mermaid class names
  var STATUS_CLASS_MAP = {
    "Draft": "todo",
    "Accepted": "open",
    "Submit": "open",
    "Executing": "progress",
    "Verifying": "review",
    "Complete": "done",
  };

  // ── Utility: Escape title for Mermaid ──

  /**
   * Escapes special characters in workRequest titles for safe Mermaid embedding.
   * Mermaid uses `"` wrapped labels, so we escape HTML entities.
   * @param {string} title
   * @returns {string}
   */
  function escapeMermaidTitle(title) {
    return title
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/\//g, "&#47;")
      .replace(/\(/g, "&#40;")
      .replace(/\)/g, "&#41;")
      .replace(/\[/g, "&#91;")
      .replace(/\]/g, "&#93;")
      .replace(/#/g, "&#35;");
  }

  /**
   * Truncates a string to maxLen characters with ellipsis.
   * @param {string} str
   * @param {number} maxLen
   * @returns {string}
   */
  function truncate(str, maxLen) {
    if (!str) return "";
    if (str.length <= maxLen) return str;
    return str.substring(0, maxLen) + "...";
  }

  /**
   * Converts a workRequest number like "WR-001" to a Mermaid-safe node ID "T_001".
   * @param {string} num
   * @returns {string}
   */
  function toNodeId(num) {
    return num.replace(/-/g, "_");
  }

  // ── A. Graph Build Function ──

  /**
   * Builds a dependency graph from workRequest data.
   * @param {Array} workRequests - Board.state.WORK_REQUESTS array
   * @param {Object} opts - { statuses: string[], showIsolated: boolean }
   * @returns {{ nodes: Object, edges: Array, relatedNumbers: Set }}
   */
  function buildDependencyGraph(workRequests, opts) {
    var statuses = (opts && opts.statuses && opts.statuses.length > 0) ? opts.statuses : null;
    var showIsolated = (opts && opts.showIsolated) || false;

    // Build node map for all workRequests (we need targets of relations too)
    var allNodes = {};
    for (var i = 0; i < workRequests.length; i++) {
      var t = workRequests[i];
      allNodes[t.number] = {
        number: t.number,
        title: t.title || "",
        status: t.status || "Accepted",
        command: t.command || "",
        relations: t.relations || [],
      };
    }

    // Build edges from relations
    var edges = [];
    var relatedNumbers = new Set();

    for (var num in allNodes) {
      var node = allNodes[num];
      var rels = node.relations;
      for (var ri = 0; ri < rels.length; ri++) {
        var rel = rels[ri];
        var targetNum = rel.workRequest;
        var type = rel.type;

        // Determine edge direction based on relation type
        var from, to;
        if (type === "depends-on") {
          // A depends-on B: edge from A to B
          from = num;
          to = targetNum;
        } else if (type === "derived-from") {
          // A derived-from B: edge from A to B
          from = num;
          to = targetNum;
        } else if (type === "blocks") {
          // A blocks B: edge from A to B
          from = num;
          to = targetNum;
        } else {
          continue;
        }

        edges.push({ from: from, to: to, type: type });
        relatedNumbers.add(from);
        relatedNumbers.add(to);
      }
    }

    // Deduplicate edges
    var edgeSet = {};
    var uniqueEdges = [];
    for (var ei = 0; ei < edges.length; ei++) {
      var e = edges[ei];
      var key = e.from + "|" + e.to + "|" + e.type;
      if (!edgeSet[key]) {
        edgeSet[key] = true;
        uniqueEdges.push(e);
      }
    }

    // Filter nodes based on status
    var filteredNodes = {};
    for (var n in allNodes) {
      var nd = allNodes[n];
      // Status filter
      if (statuses) {
        var statusClass = STATUS_CLASS_MAP[nd.status] || "open";
        var match = false;
        for (var si = 0; si < statuses.length; si++) {
          if (STATUS_CLASS_MAP[nd.status] === statuses[si] || nd.status === statuses[si]) {
            match = true;
            break;
          }
        }
        if (!match) continue;
      }
      // Isolated filter: only include if related or showIsolated is true
      if (!showIsolated && !relatedNumbers.has(n)) continue;
      filteredNodes[n] = nd;
    }

    // Filter edges to only include those where both nodes are in filtered set
    var filteredEdges = [];
    for (var fe = 0; fe < uniqueEdges.length; fe++) {
      var edge = uniqueEdges[fe];
      if (filteredNodes[edge.from] && filteredNodes[edge.to]) {
        filteredEdges.push(edge);
      }
    }

    return {
      nodes: filteredNodes,
      edges: filteredEdges,
      relatedNumbers: relatedNumbers,
    };
  }

  // ── B. Mermaid Code Generation ──

  /**
   * Generates Mermaid flowchart code from a dependency graph.
   * @param {{ nodes: Object, edges: Array }} graph
   * @param {string} direction - "TD" or "LR"
   * @returns {string} Mermaid flowchart code
   */
  function generateMermaidCode(graph, direction) {
    var lines = [];
    lines.push("flowchart " + (direction || "TD"));

    // Node definitions
    var nodeNums = Object.keys(graph.nodes);
    for (var i = 0; i < nodeNums.length; i++) {
      var num = nodeNums[i];
      var node = graph.nodes[num];
      var nodeId = toNodeId(num);
      var title = escapeMermaidTitle(truncate(node.title, 15));
      lines.push("  " + nodeId + "[\"" + num + "<br>" + title + "\"]");
    }

    // Edge definitions
    for (var ei = 0; ei < graph.edges.length; ei++) {
      var edge = graph.edges[ei];
      var fromId = toNodeId(edge.from);
      var toId = toNodeId(edge.to);

      if (edge.type === "depends-on") {
        lines.push("  " + fromId + " -.->|\"depends\"| " + toId);
      } else if (edge.type === "derived-from") {
        lines.push("  " + fromId + " -->|\"derived\"| " + toId);
      } else if (edge.type === "blocks") {
        lines.push("  " + fromId + " ==>|\"blocks\"| " + toId);
      }
    }

    // classDef for status colors
    lines.push("  classDef todo fill:#1e1e1e,stroke:#569cd6,stroke-width:2px,color:#e0e0e0");
    lines.push("  classDef open fill:#1e1e1e,stroke:#4ec9b0,stroke-width:2px,color:#e0e0e0");
    lines.push("  classDef progress fill:#1e1e1e,stroke:#dcdcaa,stroke-width:2px,color:#e0e0e0");
    lines.push("  classDef review fill:#1e1e1e,stroke:#c586c0,stroke-width:2px,color:#e0e0e0");
    lines.push("  classDef done fill:#1e1e1e,stroke:#858585,stroke-width:1px,color:#858585");

    // class assignments
    for (var ci = 0; ci < nodeNums.length; ci++) {
      var cNum = nodeNums[ci];
      var cNode = graph.nodes[cNum];
      var cId = toNodeId(cNum);
      var cls = STATUS_CLASS_MAP[cNode.status] || "open";
      lines.push("  class " + cId + " " + cls);
    }

    return lines.join("\n");
  }

  // ── Statistics Computation ──

  /**
   * Computes statistics for the relations view.
   * @param {Array} workRequests
   * @param {Set} relatedNumbers
   * @returns {Object}
   */
  function computeStats(workRequests, relatedNumbers) {
    var total = workRequests.length;
    var related = relatedNumbers.size;
    var byStatus = { todo: 0, open: 0, progress: 0, review: 0, done: 0 };
    var byRelType = { "depends-on": 0, "derived-from": 0, "blocks": 0 };

    for (var i = 0; i < workRequests.length; i++) {
      var t = workRequests[i];
      var cls = STATUS_CLASS_MAP[t.status] || "open";
      byStatus[cls] = (byStatus[cls] || 0) + 1;

      var rels = t.relations || [];
      for (var ri = 0; ri < rels.length; ri++) {
        var rtype = rels[ri].type;
        if (byRelType[rtype] !== undefined) {
          byRelType[rtype]++;
        }
      }
    }

    return {
      total: total,
      related: related,
      byStatus: byStatus,
      byRelType: byRelType,
    };
  }

  // ── Render Helpers ──

  /**
   * Renders statistics cards HTML.
   * @param {Object} stats
   * @returns {string}
   */
  function renderStatsCards(stats) {
    var cards = [
      { label: "Total WorkRequests", value: stats.total, cls: "stat-total", sub: "all workRequests" },
      { label: "With Relations", value: stats.related, cls: "stat-relations", sub: "linked workRequests" },
      { label: "Draft", value: stats.byStatus.todo, cls: "stat-todo", sub: "backlog" },
      { label: "Accepted", value: stats.byStatus.open, cls: "stat-open", sub: "open / submit" },
      { label: "Executing", value: stats.byStatus.progress, cls: "stat-progress", sub: "running" },
      { label: "Verifying", value: stats.byStatus.review, cls: "stat-review", sub: "awaiting review" },
      { label: "Complete", value: stats.byStatus.done, cls: "stat-done", sub: "completed" },
    ];

    var h = '<div class="relations-stats">';
    for (var i = 0; i < cards.length; i++) {
      var c = cards[i];
      h += '<div class="relations-stat-card ' + c.cls + '">';
      h += '<div class="relations-stat-label">' + esc(c.label) + '</div>';
      h += '<div class="relations-stat-value">' + c.value + '</div>';
      h += '<div class="relations-stat-sub">' + esc(c.sub) + '</div>';
      h += '</div>';
    }
    h += '</div>';
    return h;
  }

  /**
   * Renders the filter toolbar HTML.
   * @returns {string}
   */
  function renderToolbar() {
    var statusFilters = [
      { key: "todo", label: "Draft" },
      { key: "open", label: "Accepted" },
      { key: "progress", label: "Executing" },
      { key: "review", label: "Verifying" },
      { key: "done", label: "Complete" },
    ];

    var h = '<div class="relations-toolbar">';

    // Status filter label
    h += '<span class="relations-toolbar-label">Filter</span>';

    // Status filter buttons
    // Explicit Array Method (T3.2): filterState.statuses always lists active status.
    for (var i = 0; i < statusFilters.length; i++) {
      var sf = statusFilters[i];
      var isActive = filterState.statuses.indexOf(sf.key) !== -1;
      h += '<button class="relations-filter-btn' + (isActive ? " active" : "") + '" data-status="' + sf.key + '">';
      h += esc(sf.label);
      h += '</button>';
    }

    // Separator
    h += '<span class="relations-toolbar-sep"></span>';

    // Layout direction toggle
    h += '<span class="relations-toolbar-label">Layout</span>';
    h += '<button class="relations-layout-btn' + (filterState.direction === "TD" ? " active" : "") + '" data-dir="TD">TD</button>';
    h += '<button class="relations-layout-btn' + (filterState.direction === "LR" ? " active" : "") + '" data-dir="LR">LR</button>';

    // Separator
    h += '<span class="relations-toolbar-sep"></span>';

    // Isolated nodes toggle
    h += '<label class="relations-isolated-toggle">';
    h += '<input type="checkbox"' + (filterState.showIsolated ? ' checked' : '') + '>';
    h += 'Show isolated nodes';
    h += '</label>';

    // Spacer + Collapse button
    h += '<span style="flex:1"></span>';
    h += '<button class="relations-collapse-btn" id="relations-collapse-btn" title="Collapse">';
    h += '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"/></svg>';
    h += '</button>';

    h += '</div>';
    return h;
  }

  /**
   * Renders the legend HTML.
   * @returns {string}
   */
  function renderLegend() {
    var h = '<div class="relations-legend">';
    h += '<span class="relations-legend-title">Legend</span>';

    // Edge types — line + arrowhead. The color is injected with CSS currentColor.
    var depArrow = '<svg class="relations-legend-edge edge-depends" width="36" height="8" viewBox="0 0 36 8" fill="none" aria-hidden="true">'
      + '<line x1="0" y1="4" x2="26" y2="4" stroke="currentColor" stroke-width="2" stroke-dasharray="3 2"/>'
      + '<path d="M26 1 L34 4 L26 7 Z" fill="currentColor"/></svg>';
    var derArrow = '<svg class="relations-legend-edge edge-derived" width="36" height="8" viewBox="0 0 36 8" fill="none" aria-hidden="true">'
      + '<line x1="0" y1="4" x2="26" y2="4" stroke="currentColor" stroke-width="2"/>'
      + '<path d="M26 1 L34 4 L26 7 Z" fill="currentColor"/></svg>';
    var blkArrow = '<svg class="relations-legend-edge edge-blocks" width="36" height="9" viewBox="0 0 36 9" fill="none" aria-hidden="true">'
      + '<line x1="0" y1="4.5" x2="26" y2="4.5" stroke="currentColor" stroke-width="3"/>'
      + '<path d="M26 1 L35 4.5 L26 8 Z" fill="currentColor"/></svg>';

    h += '<div class="relations-legend-item">' + depArrow + '<span>depends-on</span></div>';
    h += '<div class="relations-legend-item">' + derArrow + '<span>derived-from</span></div>';
    h += '<div class="relations-legend-item">' + blkArrow + '<span>blocks</span></div>';

    // Separator
    h += '<span class="relations-legend-sep"></span>';

    // Node statuses
    h += '<div class="relations-legend-item">';
    h += '<span class="relations-legend-dot dot-todo"></span>';
    h += '<span>Draft</span>';
    h += '</div>';

    h += '<div class="relations-legend-item">';
    h += '<span class="relations-legend-dot dot-open"></span>';
    h += '<span>Accepted</span>';
    h += '</div>';

    h += '<div class="relations-legend-item">';
    h += '<span class="relations-legend-dot dot-progress"></span>';
    h += '<span>Executing</span>';
    h += '</div>';

    h += '<div class="relations-legend-item">';
    h += '<span class="relations-legend-dot dot-review"></span>';
    h += '<span>Verifying</span>';
    h += '</div>';

    h += '<div class="relations-legend-item">';
    h += '<span class="relations-legend-dot dot-done"></span>';
    h += '<span>Complete</span>';
    h += '</div>';

    h += '</div>';
    return h;
  }

  /**
   * Renders the empty state when no relations exist.
   * @returns {string}
   */
  function renderEmptyState() {
    var h = '<div class="relations-empty">';
    h += '<div class="relations-empty-icon" aria-hidden="true">'
      + '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
      + '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
      + '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'
      + '</svg></div>';
    h += '<div class="relations-empty-title">No workRequest relations found</div>';
    h += '<div class="relations-empty-desc">';
    h += 'The relations visualizes dependencies between workRequests. ';
    h += 'Link workRequests using the CLI to see them here.';
    h += '</div>';
    h += '<div class="relations-empty-hint">flow-conveyor link WR-001 --depends-on WR-002</div>';
    h += '</div>';
    return h;
  }

  // ── C. Main Render Function ──

  /**
   * Asynchronous paper filling only graph container.
   *
   * toolbar/legend is already invoked, only inside graph container
   * Add to cart Graph build + Mermaid renderer is unloaded, so it separates panel breakdown
   * User input → reduce delay between visual feedback.
   */
  function renderGraphBody() {
    var graphEl = document.getElementById("relations-graph");
    if (!graphEl) return;

    var workRequests = Board.state.WORK_REQUESTS || [];

    // If the workRequest data is still arrived, graph remains waiting spinner.
    // toolbar/legend is already drawn from Phase A, so it is preserved.
    if (workRequests.length === 0) {
      graphEl.innerHTML = '<div class="relations-loading">'
        + '<div class="relations-loading-spinner"></div>'
        + '<span>Waiting for workRequest data...</span>'
        + '</div>';
      return;
    }

    var displayOpts = {
      statuses: filterState.statuses,
      showIsolated: filterState.showIsolated,
    };
    var graph = buildDependencyGraph(workRequests, displayOpts);
    var nodeKeys = Object.keys(graph.nodes);

    if (nodeKeys.length === 0) {
      graphEl.innerHTML = renderEmptyState();
      return;
    }

    if (graph.edges.length === 0 && !filterState.showIsolated) {
      graphEl.innerHTML = renderEmptyState();
      return;
    }

    var mermaidCode = generateMermaidCode(graph, filterState.direction);

    if (typeof mermaid === "undefined") {
      graphEl.innerHTML = '<pre class="wf-file-content">' + esc(mermaidCode) + '</pre>';
      return;
    }

    var renderId = "relations-" + Date.now();

    mermaid.render(renderId, mermaidCode).then(function (result) {
      graphEl.innerHTML = result.svg;
      bindNodeClickEvents(graphEl, graph.nodes);
    }).catch(function (err) {
      console.warn("[relations] Mermaid render failed:", err);
      var orphan = document.getElementById(renderId);
      if (orphan && orphan !== document.body) orphan.remove();
      document.querySelectorAll("body > svg[id], body > div[id]").forEach(function (el) {
        if (/^d\d+$/.test(el.id)) el.remove();
      });
      graphEl.innerHTML = '<pre class="wf-file-content">' + esc(mermaidCode) + '</pre>';
    });
  }

  /**
   * Main render entry point for the Relations panel.
   * Registered as Board.render.renderRelations.
   *
   * It is divided into two papers NEWS
   *   Phase A — toolbar / legend with frequent graph container (static, light).
   *   Phase B — Graph container Animated with setTimeout (Mermaid wrench).
   * Toolbar/legend looks immediately with the panel unfolding, and only the middle of the spinner is money.
   */
  function renderRelations() {
    var el = document.getElementById("relations-panel-content");
    if (!el) return;

    // Phase A: static zone (toolbar + legend) instant synchronous renderer. Copyright (C) 2017. All Rights Reserved.
    // It is always exposed to whether or not you arrive. Graph is spinner.
    var h = '';
    h += renderToolbar();
    h += '<div class="relations-graph-container" id="relations-graph">'
      + '<div class="relations-loading">'
      + '<div class="relations-loading-spinner"></div>'
      + '<span>Loading graph...</span>'
      + '</div>'
      + '</div>';
    h += renderLegend();
    el.innerHTML = h;
    wireEventHandlers(el);

    // Phase B: Fill the graph body after the next paint.
    // 150ms — the balance of spinner blinking/replying. When shorter, it is back to Mermaid wrench cost
    // If the user feels the answer
    setTimeout(renderGraphBody, 150);
  }

  // ── D. Event Handling ──

  /**
   * Wires up filter, layout, and isolated toggle event handlers.
   * @param {HTMLElement} container
   */
  function wireEventHandlers(container) {
    // Status filter buttons
    var filterBtns = container.querySelectorAll(".relations-filter-btn");
    filterBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var status = btn.getAttribute("data-status");

        if (filterState.statuses.length === 0) {
          // Currently showing all: clicking one means "only show this one"
          filterState.statuses = [status];
        } else {
          var idx = filterState.statuses.indexOf(status);
          if (idx !== -1) {
            // Remove this status from filter
            filterState.statuses.splice(idx, 1);
            // If no statuses left, reset to all
            // (leave empty = show all)
          } else {
            // Add this status to filter
            filterState.statuses.push(status);
          }
          // If all 5 statuses are selected, reset to empty (= all)
          if (filterState.statuses.length >= 5) {
            filterState.statuses = [];
          }
        }

        if (saveUI) saveUI();
        renderRelations();
      });
    });

    // Layout direction toggle
    var layoutBtns = container.querySelectorAll(".relations-layout-btn");
    layoutBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var dir = btn.getAttribute("data-dir");
        if (filterState.direction !== dir) {
          filterState.direction = dir;
          if (saveUI) saveUI();
          renderRelations();
        }
      });
    });

    // Isolated nodes toggle
    var isolatedToggle = container.querySelector(".relations-isolated-toggle input");
    if (isolatedToggle) {
      isolatedToggle.addEventListener("change", function () {
        filterState.showIsolated = isolatedToggle.checked;
        if (saveUI) saveUI();
        renderRelations();
      });
    }

    // Collapse button
    var collapseBtn = container.querySelector("#relations-collapse-btn");
    if (collapseBtn) {
      collapseBtn.addEventListener("click", function () {
        toggleRelationsPanel();
      });
    }
  }

  /**
   * Binds click events on rendered Mermaid SVG nodes to open the Viewer tab.
   * @param {HTMLElement} graphEl - The graph container element
   * @param {Object} nodes - Graph nodes map
   */
  function bindNodeClickEvents(graphEl, nodes) {
    // Mermaid generates nodes with class "node" and id like "flowchart-T_NNN-N"
    var svgNodes = graphEl.querySelectorAll(".node");
    svgNodes.forEach(function (svgNode) {
      var nodeId = svgNode.id || "";
      // Extract workRequest number from node ID: "flowchart-T_NNN-N" -> "T_NNN"
      var match = nodeId.match(/flowchart-(T_\d+)/);
      if (!match) return;

      var workRequestIdUnder = match[1]; // e.g. "T_001"
      var workRequestNum = workRequestIdUnder.replace(/_/g, "-"); // e.g. "WR-001"

      if (!nodes[workRequestNum]) return;

      svgNode.style.cursor = "pointer";
      svgNode.addEventListener("click", function () {
        var workRequest = Board.state.WORK_REQUESTS.find(function (t) {
          return t.number === workRequestNum;
        });
        if (workRequest && Board.render.openViewer) {
          Board.render.openViewer(workRequest);
          Board.util.switchTab("viewer");
        }
      });
    });
  }

  // ── Panel Toggle ──

  /**
   * Updates the collapsed bar workRequest count.
   */
  function updateBarCount() {
    var countEl = document.getElementById("relations-bar-count");
    if (!countEl) return;
    var workRequests = Board.state.WORK_REQUESTS || [];
    var fullGraph = buildDependencyGraph(workRequests, { statuses: [], showIsolated: false });
    var linked = Object.keys(fullGraph.nodes).length;
    countEl.textContent = linked > 0 ? linked + " linked" : "";
  }

  /**
   * Toggles the relations panel open/closed.
   *
   * renderRelations
   * The graph body is filled with asynchronous in Phase B.
   */
  function toggleRelationsPanel() {
    var panel = document.getElementById("relations-panel");
    if (!panel) return;

    var isAccepted = panel.classList.toggle("open");
    Board.state.relations.panelAccepted = isAccepted;
    if (saveUI) saveUI();

    if (isAccepted) {
      renderRelations();
    } else {
      updateBarCount();
    }
  }

  // Wire collapsed bar click
  var collapsedBar = document.getElementById("relations-collapsed-bar");
  if (collapsedBar) {
    collapsedBar.addEventListener("click", toggleRelationsPanel);
  }

  // Restore the panelAccepted status of the previous session when loading the page.
  // Instantly apply panel classes and renderRelations also call immediately — workRequest data
  // If not yet, self waiting spinner is displayed, and data from the setTimeout flow below
  // After arrival, it will be reissued and converted to normal wrench.
  if (Board.state.relations.panelAccepted) {
    var initPanel = document.getElementById("relations-panel");
    if (initPanel) initPanel.classList.add("open");
    renderRelations();
  }

  // Update bar count periodically (workRequests may load async).
  // In case of panelAccepted, we trigger the renderer at the same point.
  setTimeout(function () {
    updateBarCount();
    if (Board.state.relations.panelAccepted) {
      renderRelations();
    }
  }, 2000);

  // ── Register on Board namespace ──
  Board.render.renderRelations = renderRelations;
  Board.render.toggleRelationsPanel = toggleRelationsPanel;
})();
