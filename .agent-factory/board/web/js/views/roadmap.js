/**
 * @module roadmap
 *
 * Roadmap subtab of the Contexts tab (formerly the Prompt tab).
 *
 * Displays `.agent-factory/roadmap/ROADMAP.yaml` (response as JSON from server).
 * Left side (Phase + Milestone tree, status badge) + Right side body (select Phase of
 * Markdown body + Milestone card grid). Mermaid code blocks in Markdown are automatically converted to SVG.
 *
 * The subtab entry point is exposed as `Board.render.renderRoadmapSubtab(container)`,
 * Called by the subtab dispatcher of memory-core.js.
 *
 * Depends on: common.js (Board.state, Board.util, Board.render — renderMd / initMermaid)
 */
"use strict";

(function () {
  var esc = Board.util.esc;
  var saveUI = Board.util.saveUI;

  // ── State ──
  // common.js initializes Board.state.roadmap (sideWidth / activePhaseId / expandedCardIds).
  // In this module, if you mutate the object in property units, saveUI automatically persists it.
  var state = Board.state.roadmap;

  // Data cache — Store fetch results, refresh on SSE roadmap events
  var data = null;
  var fetching = false;

  // Last rendered container — Re-render target when SSE refresh.
  // If null, the current subtab is not active → re-render is omitted.
  var activeContainer = null;

  // ── Markdown helper ──
  // Board.render.renderMd converts a mermaid code block into a .mermaid-block placeholder.
  // After rendering, initMermaid replaces placeholder with SVG.
  function md(text) {
    if (!text) return '';
    if (Board.render && Board.render.renderMd) {
      try { return Board.render.renderMd(text, ''); } catch (_) {}
    }
    if (typeof marked !== 'undefined' && marked.parse) {
      try { return marked.parse(text); } catch (_) {}
    }
    return '<pre>' + esc(text) + '</pre>';
  }

  // ── Status helpers ──
  function badge(status) {
    if (!status) return '';
    return '<span class="roadmap-badge status-' + esc(status) + '">' + esc(status) + '</span>';
  }

  function dot(status) {
    if (!status) return '';
    return '<span class="roadmap-side-dot status-' + esc(status) + '" aria-hidden="true"></span>';
  }

  function phaseProgress(phase) {
    var ms = phase.milestones || [];
    if (ms.length === 0) return '';
    var done = 0;
    for (var i = 0; i < ms.length; i++) {
      if (ms[i].status === 'done') done++;
    }
    return done + '/' + ms.length;
  }

  // ── Side ──
  function renderSide() {
    var w = state.sideWidth || 240;
    return '<aside class="roadmap-side" style="width:' + w + 'px">'
      + '<div class="roadmap-side-list">' + renderPhasesTree() + '</div>'
      + '</aside>'
      + '<div class="roadmap-resize-handle" id="roadmap-resize-handle"></div>';
  }

  function renderPhasesTree() {
    var phases = (data && data.phases) || [];
    var h = '';
    for (var i = 0; i < phases.length; i++) {
      var p = phases[i];
      var isActive = state.activePhaseId === p.id;
      var prog = phaseProgress(p);
      h += '<div class="roadmap-side-phase">';
      h += '<div class="roadmap-side-phase-title' + (isActive ? ' active' : '') + '" data-phase-id="' + esc(p.id) + '">';
      h += '<span>' + esc(p.title || p.id) + '</span>';
      if (prog) h += '<span class="roadmap-side-phase-progress">' + prog + '</span>';
      h += '</div>';
      var ms = p.milestones || [];
      if (ms.length > 0) {
        h += '<ul class="roadmap-side-milestones">';
        for (var j = 0; j < ms.length; j++) {
          var m = ms[j];
          h += '<li class="roadmap-side-milestone" data-phase-id="' + esc(p.id) + '" data-milestone-id="' + esc(m.id) + '">';
          h += dot(m.status || 'planned');
          h += '<span>' + esc(m.title || m.id) + '</span>';
          h += '</li>';
        }
        h += '</ul>';
      }
      h += '</div>';
    }
    return h;
  }

  // ── Body ──
  function renderBodyContent(phase) {
    if (!phase) {
      return '<div class="roadmap-empty">'
        + '<div class="roadmap-empty-icon" aria-hidden="true">'
        + '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        + '<path d="M3 3h18v18H3z"/><path d="M3 9h18M9 3v18"/>'
        + '</svg></div>'
        + '<div class="roadmap-empty-title">Select a phase</div>'
        + '<div class="roadmap-empty-desc">Select Phase on the left side to see the prose body and milestone cards.</div>'
        + '</div>';
    }

    var prog = phaseProgress(phase);
    var h = '';

    h += '<h2 class="roadmap-body-title">';
    h += '<span>' + esc(phase.title || phase.id) + '</span>';
    if (prog) h += '<span class="roadmap-body-title-progress">milestones ' + prog + '</span>';
    h += '</h2>';

    h += '<div class="roadmap-body-md">' + md(phase.body || '') + '</div>';

    var ms = phase.milestones || [];
    if (ms.length > 0) {
      h += '<div class="roadmap-milestones-section">';
      h += '<div class="roadmap-milestones-heading">Milestones</div>';
      h += '<div class="roadmap-cards">';
      for (var i = 0; i < ms.length; i++) {
        var m = ms[i];
        var expanded = state.expandedCardIds.indexOf(phase.id + '/' + m.id) !== -1;
        h += '<div class="roadmap-card' + (expanded ? ' expanded' : '') + '" '
          + 'data-phase-id="' + esc(phase.id) + '" data-milestone-id="' + esc(m.id) + '">';
        h += '<div class="roadmap-card-header">';
        h += '<div class="roadmap-card-title">' + esc(m.title || m.id) + '</div>';
        h += badge(m.status || 'planned');
        h += '</div>';
        var tickets = m.tickets || [];
        if (tickets.length > 0) {
          h += '<div class="roadmap-card-tickets">';
          for (var k = 0; k < tickets.length; k++) {
            h += '<span class="roadmap-card-ticket-chip" data-ticket="' + esc(tickets[k]) + '">'
              + esc(tickets[k]) + '</span>';
          }
          h += '</div>';
        }
        if (m.body) {
          h += '<div class="roadmap-card-body roadmap-body-md">' + md(m.body) + '</div>';
        }
        h += '</div>';
      }
      h += '</div>';
      h += '</div>';
    }

    return h;
  }

  // ── Main render ──
  // Container = #prompt-content (flex row, overflow:hidden) in Prompt tab.
  // Insert side / resize-handle / body directly as children (no separate layout wrapper).
  function renderInto(container) {
    if (!container) return;
    activeContainer = container;

    if (!data) {
      container.innerHTML = renderSide()
        + '<div class="roadmap-body">'
        + '<div class="roadmap-loading">'
        + '<div class="roadmap-loading-spinner"></div>'
        + '<span>Loading roadmap...</span>'
        + '</div>'
        + '</div>';
      wireEventHandlers(container);
      return;
    }

    var phases = data.phases || [];
    if (phases.length === 0) {
      container.innerHTML = renderSide()
        + '<div class="roadmap-body">'
        + '<div class="roadmap-empty">'
        + '<div class="roadmap-empty-icon" aria-hidden="true">'
        + '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        + '<path d="M3 3h18v18H3z"/><path d="M3 9h18M9 3v18"/>'
        + '</svg></div>'
        + '<div class="roadmap-empty-title">No roadmap yet</div>'
        + '<div class="roadmap-empty-desc">If you write .agent-factory/roadmap/ROADMAP.yaml it will appear here</div>'
        + '</div>'
        + '</div>';
      wireEventHandlers(container);
      return;
    }

    // Determine active phase — fallback to first phase if stored value is invalid
    var active = null;
    if (state.activePhaseId) {
      for (var i = 0; i < phases.length; i++) {
        if (phases[i].id === state.activePhaseId) { active = phases[i]; break; }
      }
    }
    if (!active) {
      active = phases[0];
      state.activePhaseId = active.id;
      if (saveUI) saveUI();
    }

    container.innerHTML = renderSide()
      + '<div class="roadmap-body">' + renderBodyContent(active) + '</div>';

    wireEventHandlers(container);
    if (Board.render.initMermaid) Board.render.initMermaid();
    if (Board.render.initHighlight) Board.render.initHighlight();
  }

  // ── Resize handle ──
  function bindResizeHandle(container) {
    var handle = container.querySelector('#roadmap-resize-handle');
    if (!handle) return;
    var sidebar = container.querySelector('.roadmap-side');
    if (!sidebar) return;

    handle.addEventListener('mousedown', function (e) {
      e.preventDefault();
      handle.classList.add('dragging');
      var startX = e.clientX;
      var startW = sidebar.offsetWidth;

      function onMove(ev) {
        var w = startW + (ev.clientX - startX);
        if (w < 140) w = 140;
        if (w > 600) w = 600;
        sidebar.style.width = w + 'px';
      }
      function onUp() {
        handle.classList.remove('dragging');
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        var w = sidebar.offsetWidth;
        if (w >= 140 && w <= 600 && w !== state.sideWidth) {
          state.sideWidth = w;
          if (saveUI) saveUI();
        }
      }
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });
  }

  // ── Event handlers ──
  function wireEventHandlers(container) {
    bindResizeHandle(container);

    // Phase title click → change activePhaseId
    var phaseTitles = container.querySelectorAll('.roadmap-side-phase-title');
    phaseTitles.forEach(function (el) {
      el.addEventListener('click', function () {
        var pid = el.getAttribute('data-phase-id');
        if (pid && pid !== state.activePhaseId) {
          state.activePhaseId = pid;
          if (saveUI) saveUI();
          renderInto(container);
        }
      });
    });

    // Milestone in side → Activate corresponding phase + Expand card + Scroll to card
    var sideMilestones = container.querySelectorAll('.roadmap-side-milestone');
    sideMilestones.forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.stopPropagation();
        var pid = el.getAttribute('data-phase-id');
        var mid = el.getAttribute('data-milestone-id');
        var key = pid + '/' + mid;
        var changed = false;
        if (pid !== state.activePhaseId) {
          state.activePhaseId = pid;
          changed = true;
        }
        if (state.expandedCardIds.indexOf(key) === -1) {
          state.expandedCardIds.push(key);
          changed = true;
        }
        if (changed) {
          if (saveUI) saveUI();
          renderInto(container);
        }
        requestAnimationFrame(function () {
          var card = container.querySelector(
            '.roadmap-card[data-phase-id="' + pid + '"][data-milestone-id="' + mid + '"]'
          );
          if (card && card.scrollIntoView) {
            card.scrollIntoView({ behavior: 'smooth', block: 'start', inline: 'nearest' });
          }
        });
      });
    });

    // Card click → expand/collapse
    var cards = container.querySelectorAll('.roadmap-card');
    cards.forEach(function (card) {
      card.addEventListener('click', function (e) {
        if (e.target && e.target.classList && e.target.classList.contains('roadmap-card-ticket-chip')) {
          return;
        }
        var pid = card.getAttribute('data-phase-id');
        var mid = card.getAttribute('data-milestone-id');
        var key = pid + '/' + mid;
        var idx = state.expandedCardIds.indexOf(key);
        if (idx === -1) state.expandedCardIds.push(key);
        else state.expandedCardIds.splice(idx, 1);
        card.classList.toggle('expanded');
        if (saveUI) saveUI();
      });
    });

    // Ticket chip → move to viewer tab
    var chips = container.querySelectorAll('.roadmap-card-ticket-chip');
    chips.forEach(function (chip) {
      chip.addEventListener('click', function (e) {
        e.stopPropagation();
        var tid = chip.getAttribute('data-ticket');
        if (!tid) return;
        var ticket = (Board.state.TICKETS || []).find(function (t) { return t.number === tid; });
        if (ticket && Board.render.openViewer) {
          Board.render.openViewer(ticket);
          if (Board.util.switchTab) Board.util.switchTab('viewer');
        }
      });
    });
  }

  // ── Fetch + render ──
  function fetchAndRender() {
    if (fetching) return;
    fetching = true;
    fetch('/api/roadmap', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (json) {
        data = json;
        fetching = false;
        if (activeContainer && activeContainer.isConnected) {
          renderInto(activeContainer);
        }
      })
      .catch(function () {
        fetching = false;
      });
  }

  // ── Subtab entry point ──
  // Called by the subtab dispatcher of memory-core.js. The container is #prompt-content.
  Board.render.renderRoadmapSubtab = function (container) {
    if (!container) return;
    activeContainer = container;
    renderInto(container);
    if (!data) fetchAndRender();
  };

  // SSE roadmap event/update entry point called from an external trigger.
  // Automatically re-render if there is an active container, otherwise just update the data.
  Board.render.refreshRoadmap = fetchAndRender;
})();
