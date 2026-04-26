/**
 * @module roadmap
 *
 * Contexts 탭 (구 Prompt 탭) 의 Roadmap 서브탭.
 *
 * `.claude-organic/roadmap/ROADMAP.yaml` (서버에서 JSON 으로 응답) 을 표시한다.
 * 좌측 사이드 (Phase + Milestone 트리, 상태 뱃지) + 우측 본문 (선택 Phase 의
 * 마크다운 본문 + Milestone 카드 그리드). 마크다운 안 mermaid 코드블록은 자동 SVG 변환.
 *
 * 서브탭 진입점은 `Board.render.renderRoadmapSubtab(container)` 로 노출되며,
 * memory-core.js 의 서브탭 디스패처가 호출한다.
 *
 * Depends on: common.js (Board.state, Board.util, Board.render — renderMd / initMermaid)
 */
"use strict";

(function () {
  var esc = Board.util.esc;
  var saveUI = Board.util.saveUI;

  // ── State ──
  // common.js 가 Board.state.roadmap 을 초기화한다 (sideWidth / activePhaseId / expandedCardIds).
  // 본 모듈은 그 객체에 property 단위로 mutate 하면 saveUI 가 자동 영속화한다.
  var state = Board.state.roadmap;

  // 데이터 캐시 — fetch 결과 보관, SSE roadmap 이벤트 시 새로고침
  var data = null;
  var fetching = false;

  // 마지막으로 렌더한 컨테이너 — SSE refresh 시 재렌더 대상.
  // null 이면 현재 서브탭이 활성 상태가 아님 → 재렌더 생략.
  var activeContainer = null;

  // ── Markdown helper ──
  // Board.render.renderMd 는 mermaid 코드블록을 .mermaid-block placeholder 로 변환한다.
  // 렌더 후 initMermaid 가 placeholder 를 SVG 로 교체.
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
        + '<div class="roadmap-empty-desc">왼쪽 사이드에서 Phase 를 선택하면 산문 본문과 마일스톤 카드가 표시됩니다.</div>'
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
  // 컨테이너 = Prompt 탭의 #prompt-content (flex row, overflow:hidden).
  // 그 안에 side / resize-handle / body 를 직접 자식으로 박는다 (별도 layout wrapper 없음).
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
        + '<div class="roadmap-empty-desc">.claude-organic/roadmap/ROADMAP.yaml 을 작성하면 여기 표시됩니다.</div>'
        + '</div>'
        + '</div>';
      wireEventHandlers(container);
      return;
    }

    // 활성 phase 결정 — 저장값 무효 시 첫 phase 폴백
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

    // Phase title click → activePhaseId 변경
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

    // Milestone in side → 해당 phase 활성화 + 카드 펼침 + 카드로 스크롤
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

    // Ticket chip → viewer 탭 이동
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
  // memory-core.js 의 서브탭 디스패처가 호출. 컨테이너는 #prompt-content.
  Board.render.renderRoadmapSubtab = function (container) {
    if (!container) return;
    activeContainer = container;
    renderInto(container);
    if (!data) fetchAndRender();
  };

  // SSE roadmap 이벤트 / 외부 트리거에서 호출하는 갱신 진입점.
  // 활성 컨테이너가 있으면 자동 재렌더, 없으면 데이터만 갱신.
  Board.render.refreshRoadmap = fetchAndRender;
})();
