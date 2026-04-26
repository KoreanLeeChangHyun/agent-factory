/* Memory GC bar — Memory 서브탭 상단에 GC 상태 + 액션 버튼.
 *
 * 백엔드: GET /api/memory/gc/status, POST /api/memory/gc/run, POST /api/memory/gc/prune-archive
 * 디자인: 단일 줄 status + 우측 액션 버튼. 상세 토글로 archive/카테고리 카운트 노출.
 */
(function () {
  if (!window.Board) return;
  var Board = window.Board;
  var R = (Board.render = Board.render || {});
  var GC = (Board._memoryGc = Board._memoryGc || {});

  // expanded 는 사용자 토글이라 영속화 — Board.state.contexts.memory.gcExpanded 가 진실.
  function _initialExpanded() {
    var cx = Board.state && Board.state.contexts;
    return !!(cx && cx.memory && cx.memory.gcExpanded);
  }

  GC.state = {
    status: null,
    busy: false,
    expanded: _initialExpanded(),
    flash: null,    // 직전 GC 결과 한줄 요약 (2.5s 노출 후 자동 해제)
    flashTimer: null,
  };

  function setFlash(container, text, kind) {
    if (GC.state.flashTimer) clearTimeout(GC.state.flashTimer);
    GC.state.flash = { text: text, kind: kind || "ok" };
    render(container);
    GC.state.flashTimer = setTimeout(function () {
      GC.state.flash = null;
      GC.state.flashTimer = null;
      render(container);
    }, 2500);
  }

  function fetchStatus() {
    return fetch("/api/memory/gc/status", { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; });
  }

  function postRun(opts) {
    return fetch("/api/memory/gc/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts || {}),
    }).then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; });
  }

  function postPrune(apply) {
    return fetch("/api/memory/gc/prune-archive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ apply: !!apply }),
    }).then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; });
  }

  function fmtRelative(isoStr) {
    // YYYY-MM-DDTHH:MM:SS → 시각만 + (m/h ago) 표기
    if (!isoStr) return "n/a";
    var d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    var diffMs = Date.now() - d.getTime();
    var sec = Math.max(0, Math.floor(diffMs / 1000));
    if (sec < 5) return "just now";
    if (sec < 60) return sec + "s ago";
    var min = Math.floor(sec / 60);
    if (min < 60) return min + "m ago";
    var hr = Math.floor(min / 60);
    if (hr < 24) return hr + "h ago";
    var day = Math.floor(hr / 24);
    return day + "d ago";
  }

  function summaryText(s) {
    if (!s || !s.counts) return "loading…";
    var total = (s.counts && s.counts.total) || 0;
    var lr = s.last_run;
    var rel = lr && lr.finished_at ? fmtRelative(lr.finished_at) : "never";
    return total + " memories  ·  last GC " + rel;
  }

  function render(container) {
    var s = GC.state.status;
    var busy = GC.state.busy;
    var expanded = GC.state.expanded;
    var pendingPrune = (s && s.archive_pending_prune) || 0;
    var flash = GC.state.flash;
    var flashHtml = flash
      ? '<span class="memory-gc-flash ' + (flash.kind === 'err' ? 'err' : 'ok') + '">' +
          (flash.kind === 'err' ? '✕ ' : '✓ ') + Board.util.esc(flash.text) +
        '</span>'
      : '';
    container.innerHTML =
      '<div class="memory-gc-bar' + (busy ? ' busy' : '') + '" role="region" aria-label="Memory GC status">' +
        '<button class="memory-gc-toggle" id="memory-gc-toggle" title="Show details">' +
          '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="' + (expanded ? "6 9 12 15 18 9" : "9 6 15 12 9 18") + '"/></svg>' +
        '</button>' +
        '<span class="memory-gc-summary">' + Board.util.esc(summaryText(s)) + '</span>' +
        flashHtml +
        '<div class="memory-gc-actions">' +
          '<button class="memory-gc-btn" id="memory-gc-run-btn"' + (busy ? ' disabled' : '') + ' title="Run dedup + index regen (no LLM)">' + (busy ? 'Running…' : 'Run') + '</button>' +
          '<button class="memory-gc-btn" id="memory-gc-dry-btn"' + (busy ? ' disabled' : '') + ' title="Dry-run (no changes)">Dry</button>' +
          '<button class="memory-gc-btn danger" id="memory-gc-prune-btn"' + (busy || pendingPrune === 0 ? ' disabled' : '') + ' title="Permanently delete archive entries past TTL">' +
            'Prune (' + pendingPrune + ')' +
          '</button>' +
        '</div>' +
      '</div>' +
      (expanded
        ? '<div class="memory-gc-details">' + renderDetails(s) + '</div>'
        : '');

    var toggleBtn = document.getElementById("memory-gc-toggle");
    var runBtn = document.getElementById("memory-gc-run-btn");
    var dryBtn = document.getElementById("memory-gc-dry-btn");
    var pruneBtn = document.getElementById("memory-gc-prune-btn");

    if (toggleBtn) toggleBtn.onclick = function () {
      GC.state.expanded = !GC.state.expanded;
      var cx = Board.state && Board.state.contexts;
      if (cx && cx.memory) {
        cx.memory.gcExpanded = GC.state.expanded;
        if (Board.util && Board.util.saveUI) Board.util.saveUI();
      }
      render(container);
    };
    if (runBtn) runBtn.onclick = function () { runCycle(container, false); };
    if (dryBtn) dryBtn.onclick = function () { runCycle(container, true); };
    if (pruneBtn) pruneBtn.onclick = function () {
      if (!confirm("Permanently delete " + pendingPrune + " archive entries past TTL?")) return;
      runPrune(container);
    };
  }

  function renderDetails(s) {
    if (!s) return '<div class="memory-gc-detail-empty">no status</div>';
    var c = s.counts || {};
    var ac = s.archive_counts || {};
    var lr = s.last_run || {};
    var counts = [
      'user=' + (c.user || 0),
      'feedback=' + (c.feedback || 0),
      'project=' + (c.project || 0),
      'reference=' + (c.reference || 0),
    ];
    if (c.flat) counts.push('flat=' + c.flat);
    var archiveCounts = (ac.merged || 0) + ' merged · ' + (ac.synthesized || 0) + ' synthesized · ' + (ac.stale || 0) + ' stale';
    var lastRunSummary = 'total=' + (lr.total_memories || 0)
      + ' hot=' + (lr.hot_count || 0)
      + ' dedup=' + (lr.dedup_applied || 0) + '/' + (lr.dedup_candidates || 0)
      + ' synth=' + (lr.reflection_synthesized || 0) + '/' + (lr.reflection_clusters || 0);
    return (
      '<dl class="memory-gc-detail-list">' +
        '<dt>counts</dt><dd>' + Board.util.esc(counts.join('  ·  ')) + '</dd>' +
        '<dt>archive</dt><dd>' + Board.util.esc(archiveCounts) +
          (s.archive_pending_prune ? ('  ·  pending prune ' + s.archive_pending_prune) : '') +
        '</dd>' +
        '<dt>hot_limit</dt><dd>' + (s.hot_limit || 0) + '</dd>' +
        '<dt>auto_triggers</dt><dd>' + Board.util.esc((s.auto_triggers || []).join(', ') || '(none)') + '</dd>' +
        '<dt>reflection_threshold</dt><dd>' + (s.reflection_threshold || 0) + '</dd>' +
        '<dt>archive_ttl_days</dt><dd>' + (s.archive_ttl_days || 0) + '</dd>' +
        '<dt>last_run</dt><dd>' + Board.util.esc(lr.finished_at || 'never') + '  ·  ' + Board.util.esc(lastRunSummary) + '</dd>' +
        '<dt>memory_dir</dt><dd>' + Board.util.esc(s.memory_dir || '') + '</dd>' +
      '</dl>'
    );
  }

  function runCycle(container, dryRun) {
    GC.state.busy = true;
    render(container);
    // Reflect (LLM 자동 합성) 는 "never auto-modified" 원칙으로 폐기.
    // 이 사이클은 dedup + 인덱스 재생성만. LLM 호출 없음.
    postRun({ dry_run: dryRun, with_reflection: false }).then(function (res) {
      GC.state.busy = false;
      var label = dryRun ? "Dry-run" : "Run GC";
      if (!res || res.error || res.ok === false) {
        setFlash(container, label + " failed: " + ((res && res.error) || "no response"), "err");
        GC.refresh(container);
        return;
      }
      var summary = "total=" + (res.total_memories || 0)
        + " hot=" + (res.hot_count || 0)
        + " dedup=" + (res.dedup_applied || 0) + "/" + (res.dedup_candidates || 0);
      setFlash(container, label + " · " + summary, "ok");
      GC.refresh(container);
    });
  }

  function runPrune(container) {
    GC.state.busy = true;
    render(container);
    postPrune(true).then(function (res) {
      GC.state.busy = false;
      if (!res || res.error || res.ok === false) {
        setFlash(container, "Prune failed: " + ((res && res.error) || "no response"), "err");
      } else {
        setFlash(container, "Prune archive · " + ((res.raw_stdout || "ok").split("\n")[0]), "ok");
      }
      GC.refresh(container);
    });
  }

  GC.refresh = function (container) {
    fetchStatus().then(function (s) {
      GC.state.status = s;
      render(container);
    });
  };

  R.renderMemoryGcBar = function (container) {
    if (!container) return;
    GC.refresh(container);
  };
})();
