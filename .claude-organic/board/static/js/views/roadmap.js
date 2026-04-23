/**
 * @module roadmap
 *
 * Board SPA roadmap tab module.
 *
 * Builds a dependency graph from ticket relations and renders it as a
 * Mermaid flowchart. Provides status filters, layout direction toggle,
 * isolated node toggle, statistics cards, and legend. Clicking a node
 * opens the ticket in the Viewer tab.
 *
 * Depends on: common.js (Board.state, Board.util, Board.render)
 */
"use strict";

(function () {
  // ── Shared references ──
  var esc = Board.util.esc;
  var COLUMNS = Board.util.COLUMNS;
  var STATUS_COLORS = Board.util.STATUS_COLORS;

  // ── Module State ──
  var filterState = {
    // To Do 기본 숨김: 초기 활성 상태를 명시 (empty = all 규칙 대신 명시적 4개 사용)
    statuses: ["open", "progress", "review", "done"],
    direction: "TD",
    showIsolated: false,
  };

  // Status key normalization for CSS and Mermaid class names
  var STATUS_CLASS_MAP = {
    "To Do": "todo",
    "Open": "open",
    "Submit": "open",
    "In Progress": "progress",
    "Review": "review",
    "Done": "done",
  };

  // ── Utility: Escape title for Mermaid ──

  /**
   * Escapes special characters in ticket titles for safe Mermaid embedding.
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
   * Converts a ticket number like "T-001" to a Mermaid-safe node ID "T_001".
   * @param {string} num
   * @returns {string}
   */
  function toNodeId(num) {
    return num.replace(/-/g, "_");
  }

  // ── A. Graph Build Function ──

  /**
   * Builds a dependency graph from ticket data.
   * @param {Array} tickets - Board.state.TICKETS array
   * @param {Object} opts - { statuses: string[], showIsolated: boolean }
   * @returns {{ nodes: Object, edges: Array, relatedNumbers: Set }}
   */
  function buildDependencyGraph(tickets, opts) {
    var statuses = (opts && opts.statuses && opts.statuses.length > 0) ? opts.statuses : null;
    var showIsolated = (opts && opts.showIsolated) || false;

    // Build node map for all tickets (we need targets of relations too)
    var allNodes = {};
    for (var i = 0; i < tickets.length; i++) {
      var t = tickets[i];
      allNodes[t.number] = {
        number: t.number,
        title: t.title || "",
        status: t.status || "Open",
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
        var targetNum = rel.ticket;
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
    lines.push("  classDef todo fill:#1e1e1e,stroke:#6a9fb5,stroke-width:2px,color:#e0e0e0");
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
   * Computes statistics for the roadmap view.
   * @param {Array} tickets
   * @param {Set} relatedNumbers
   * @returns {Object}
   */
  function computeStats(tickets, relatedNumbers) {
    var total = tickets.length;
    var related = relatedNumbers.size;
    var byStatus = { todo: 0, open: 0, progress: 0, review: 0, done: 0 };
    var byRelType = { "depends-on": 0, "derived-from": 0, "blocks": 0 };

    for (var i = 0; i < tickets.length; i++) {
      var t = tickets[i];
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
      { label: "Total Tickets", value: stats.total, cls: "stat-total", sub: "all tickets" },
      { label: "With Relations", value: stats.related, cls: "stat-relations", sub: "linked tickets" },
      { label: "To Do", value: stats.byStatus.todo, cls: "stat-todo", sub: "backlog" },
      { label: "Open", value: stats.byStatus.open, cls: "stat-open", sub: "open / submit" },
      { label: "In Progress", value: stats.byStatus.progress, cls: "stat-progress", sub: "running" },
      { label: "Review", value: stats.byStatus.review, cls: "stat-review", sub: "awaiting review" },
      { label: "Done", value: stats.byStatus.done, cls: "stat-done", sub: "completed" },
    ];

    var h = '<div class="roadmap-stats">';
    for (var i = 0; i < cards.length; i++) {
      var c = cards[i];
      h += '<div class="roadmap-stat-card ' + c.cls + '">';
      h += '<div class="roadmap-stat-label">' + esc(c.label) + '</div>';
      h += '<div class="roadmap-stat-value">' + c.value + '</div>';
      h += '<div class="roadmap-stat-sub">' + esc(c.sub) + '</div>';
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
      { key: "todo", label: "To Do" },
      { key: "open", label: "Open" },
      { key: "progress", label: "In Progress" },
      { key: "review", label: "Review" },
      { key: "done", label: "Done" },
    ];

    var h = '<div class="roadmap-toolbar">';

    // Status filter label
    h += '<span class="roadmap-toolbar-label">Filter</span>';

    // Status filter buttons
    // 명시 배열 방식 (T3.2): filterState.statuses는 항상 활성 상태 목록을 담는다.
    for (var i = 0; i < statusFilters.length; i++) {
      var sf = statusFilters[i];
      var isActive = filterState.statuses.indexOf(sf.key) !== -1;
      h += '<button class="roadmap-filter-btn' + (isActive ? " active" : "") + '" data-status="' + sf.key + '">';
      h += esc(sf.label);
      h += '</button>';
    }

    // Separator
    h += '<span class="roadmap-toolbar-sep"></span>';

    // Layout direction toggle
    h += '<span class="roadmap-toolbar-label">Layout</span>';
    h += '<button class="roadmap-layout-btn' + (filterState.direction === "TD" ? " active" : "") + '" data-dir="TD">TD</button>';
    h += '<button class="roadmap-layout-btn' + (filterState.direction === "LR" ? " active" : "") + '" data-dir="LR">LR</button>';

    // Separator
    h += '<span class="roadmap-toolbar-sep"></span>';

    // Isolated nodes toggle
    h += '<label class="roadmap-isolated-toggle">';
    h += '<input type="checkbox"' + (filterState.showIsolated ? ' checked' : '') + '>';
    h += 'Show isolated nodes';
    h += '</label>';

    // Spacer + Collapse button
    h += '<span style="flex:1"></span>';
    h += '<button class="roadmap-collapse-btn" id="roadmap-collapse-btn" title="Collapse">';
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
    var h = '<div class="roadmap-legend">';
    h += '<span class="roadmap-legend-title">Legend</span>';

    // Edge types
    h += '<div class="roadmap-legend-item">';
    h += '<span class="roadmap-legend-edge edge-depends"></span>';
    h += '<span>depends-on</span>';
    h += '</div>';

    h += '<div class="roadmap-legend-item">';
    h += '<span class="roadmap-legend-edge edge-derived"></span>';
    h += '<span>derived-from</span>';
    h += '</div>';

    h += '<div class="roadmap-legend-item">';
    h += '<span class="roadmap-legend-edge edge-blocks"></span>';
    h += '<span>blocks</span>';
    h += '</div>';

    // Separator
    h += '<span class="roadmap-legend-sep"></span>';

    // Node statuses
    h += '<div class="roadmap-legend-item">';
    h += '<span class="roadmap-legend-dot dot-todo"></span>';
    h += '<span>To Do</span>';
    h += '</div>';

    h += '<div class="roadmap-legend-item">';
    h += '<span class="roadmap-legend-dot dot-open"></span>';
    h += '<span>Open</span>';
    h += '</div>';

    h += '<div class="roadmap-legend-item">';
    h += '<span class="roadmap-legend-dot dot-progress"></span>';
    h += '<span>In Progress</span>';
    h += '</div>';

    h += '<div class="roadmap-legend-item">';
    h += '<span class="roadmap-legend-dot dot-review"></span>';
    h += '<span>Review</span>';
    h += '</div>';

    h += '<div class="roadmap-legend-item">';
    h += '<span class="roadmap-legend-dot dot-done"></span>';
    h += '<span>Done</span>';
    h += '</div>';

    h += '</div>';
    return h;
  }

  /**
   * Renders the empty state when no relations exist.
   * @returns {string}
   */
  function renderEmptyState() {
    var h = '<div class="roadmap-empty">';
    h += '<div class="roadmap-empty-icon">&#128279;</div>';
    h += '<div class="roadmap-empty-title">No ticket relations found</div>';
    h += '<div class="roadmap-empty-desc">';
    h += 'The roadmap visualizes dependencies between tickets. ';
    h += 'Link tickets using the CLI to see them here.';
    h += '</div>';
    h += '<div class="roadmap-empty-hint">flow-kanban link T-001 --depends-on T-002</div>';
    h += '</div>';
    return h;
  }

  // ── C. Main Render Function ──

  /**
   * Main render entry point for the Roadmap panel.
   * Registered as Board.render.renderRoadmap.
   */
  function renderRoadmap() {
    var el = document.getElementById("roadmap-panel-content");
    if (!el) return;

    var tickets = Board.state.TICKETS || [];

    if (tickets.length === 0) {
      el.innerHTML = '<div class="roadmap-loading">' +
        '<div class="roadmap-loading-spinner"></div>' +
        '<span>Waiting for ticket data...</span>' +
        '</div>';
      return;
    }

    // Build full graph first (for stats, using all tickets regardless of filter)
    var fullGraph = buildDependencyGraph(tickets, { statuses: [], showIsolated: true });

    // Compute stats
    var stats = computeStats(tickets, fullGraph.relatedNumbers);

    // Build filtered graph for display
    var displayOpts = {
      statuses: filterState.statuses,
      showIsolated: filterState.showIsolated,
    };
    var graph = buildDependencyGraph(tickets, displayOpts);

    // Start building HTML
    var h = '';

    // 1. Filter toolbar
    h += renderToolbar();

    // 2. Graph container placeholder
    h += '<div class="roadmap-graph-container" id="roadmap-graph"></div>';

    // 3. Legend
    h += renderLegend();

    el.innerHTML = h;

    // 5. Wire up event handlers
    wireEventHandlers(el);

    // 6. Render Mermaid graph
    var graphEl = document.getElementById("roadmap-graph");
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

    var renderId = "roadmap-" + Date.now();

    mermaid.render(renderId, mermaidCode).then(function (result) {
      graphEl.innerHTML = result.svg;

      // Bind click events on nodes
      bindNodeClickEvents(graphEl, graph.nodes);
    }).catch(function (err) {
      console.warn("[roadmap] Mermaid render failed:", err);
      // Cleanup orphan SVG elements
      if (Board.render.initMermaid) {
        // Use common.js cleanup pattern
        var orphan = document.getElementById(renderId);
        if (orphan && orphan !== document.body) {
          orphan.remove();
        }
        document.querySelectorAll("body > svg[id], body > div[id]").forEach(function (el) {
          if (/^d\d+$/.test(el.id)) el.remove();
        });
      }
      graphEl.innerHTML = '<pre class="wf-file-content">' + esc(mermaidCode) + '</pre>';
    });
  }

  // ── D. Event Handling ──

  /**
   * Wires up filter, layout, and isolated toggle event handlers.
   * @param {HTMLElement} container
   */
  function wireEventHandlers(container) {
    // Status filter buttons
    var filterBtns = container.querySelectorAll(".roadmap-filter-btn");
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

        renderRoadmap();
      });
    });

    // Layout direction toggle
    var layoutBtns = container.querySelectorAll(".roadmap-layout-btn");
    layoutBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var dir = btn.getAttribute("data-dir");
        if (filterState.direction !== dir) {
          filterState.direction = dir;
          renderRoadmap();
        }
      });
    });

    // Isolated nodes toggle
    var isolatedToggle = container.querySelector(".roadmap-isolated-toggle input");
    if (isolatedToggle) {
      isolatedToggle.addEventListener("change", function () {
        filterState.showIsolated = isolatedToggle.checked;
        renderRoadmap();
      });
    }

    // Collapse button
    var collapseBtn = container.querySelector("#roadmap-collapse-btn");
    if (collapseBtn) {
      collapseBtn.addEventListener("click", function () {
        toggleRoadmapPanel();
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
      // Extract ticket number from node ID: "flowchart-T_NNN-N" -> "T_NNN"
      var match = nodeId.match(/flowchart-(T_\d+)/);
      if (!match) return;

      var ticketIdUnder = match[1]; // e.g. "T_001"
      var ticketNum = ticketIdUnder.replace(/_/g, "-"); // e.g. "T-001"

      if (!nodes[ticketNum]) return;

      svgNode.style.cursor = "pointer";
      svgNode.addEventListener("click", function () {
        var ticket = Board.state.TICKETS.find(function (t) {
          return t.number === ticketNum;
        });
        if (ticket && Board.render.openViewer) {
          Board.render.openViewer(ticket);
          Board.util.switchTab("viewer");
        }
      });
    });
  }

  // ── Panel Toggle ──

  /**
   * Updates the collapsed bar ticket count.
   */
  function updateBarCount() {
    var countEl = document.getElementById("roadmap-bar-count");
    if (!countEl) return;
    var tickets = Board.state.TICKETS || [];
    var fullGraph = buildDependencyGraph(tickets, { statuses: [], showIsolated: false });
    var linked = Object.keys(fullGraph.nodes).length;
    countEl.textContent = linked > 0 ? linked + " linked" : "";
  }

  /**
   * Toggles the roadmap panel open/closed.
   */
  function toggleRoadmapPanel() {
    var panel = document.getElementById("roadmap-panel");
    if (!panel) return;

    var isOpen = panel.classList.toggle("open");

    if (isOpen) {
      renderRoadmap();
    } else {
      updateBarCount();
    }
  }

  // Wire collapsed bar click
  var collapsedBar = document.getElementById("roadmap-collapsed-bar");
  if (collapsedBar) {
    collapsedBar.addEventListener("click", toggleRoadmapPanel);
  }

  // Update bar count periodically (tickets may load async)
  setTimeout(updateBarCount, 2000);

  // ── Register on Board namespace ──
  Board.render.renderRoadmap = renderRoadmap;
  Board.render.toggleRoadmapPanel = toggleRoadmapPanel;
})();
