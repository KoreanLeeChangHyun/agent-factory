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

  GC.state = { status: null, busy: false, expanded: false };

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

  function fmtLastRun(lr) {
    if (!lr || !lr.finished_at) return "n/a";
    return lr.finished_at.replace("T", " ");
  }

  function summaryText(s) {
    if (!s || !s.counts) return "loading…";
    var c = s.counts;
    var ac = s.archive_counts || {};
    var totalArch = (ac.merged || 0) + (ac.synthesized || 0) + (ac.stale || 0);
    return "total=" + (c.total || 0)
      + "  user=" + (c.user || 0)
      + "  feedback=" + (c.feedback || 0)
      + "  project=" + (c.project || 0)
      + "  reference=" + (c.reference || 0)
      + (c.flat ? ("  flat=" + c.flat) : "")
      + "  archive=" + totalArch
      + (s.archive_pending_prune ? ("  pending_prune=" + s.archive_pending_prune) : "");
  }

  function render(container) {
    var s = GC.state.status;
    var busy = GC.state.busy;
    var expanded = GC.state.expanded;
    var hot = (s && s.hot_limit) ? s.hot_limit : 30;
    var pendingPrune = (s && s.archive_pending_prune) || 0;
    var lastRunStr = s ? fmtLastRun(s.last_run) : "loading…";
    container.innerHTML =
      '<div class="memory-gc-bar" role="region" aria-label="Memory GC status">' +
        '<button class="memory-gc-toggle" id="memory-gc-toggle" title="Show details">' +
          '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="' + (expanded ? "6 9 12 15 18 9" : "9 6 15 12 9 18") + '"/></svg>' +
        '</button>' +
        '<span class="memory-gc-summary">' + Board.util.esc(summaryText(s)) + '</span>' +
        '<span class="memory-gc-meta">last_run: ' + Board.util.esc(lastRunStr) + '  hot_limit=' + hot + '</span>' +
        '<div class="memory-gc-actions">' +
          '<button class="memory-gc-btn" id="memory-gc-run-btn"' + (busy ? ' disabled' : '') + '>' + (busy ? 'Running…' : 'Run GC') + '</button>' +
          '<button class="memory-gc-btn" id="memory-gc-dry-btn"' + (busy ? ' disabled' : '') + '>Dry-run</button>' +
          '<button class="memory-gc-btn danger" id="memory-gc-prune-btn"' + (busy || pendingPrune === 0 ? ' disabled' : '') + ' title="Permanently delete archive entries past TTL">' +
            'Prune Archive (' + pendingPrune + ')' +
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
    var lr = s.last_run || {};
    return (
      '<dl class="memory-gc-detail-list">' +
        '<dt>memory_dir</dt><dd>' + Board.util.esc(s.memory_dir || '') + '</dd>' +
        '<dt>auto_triggers</dt><dd>' + Board.util.esc((s.auto_triggers || []).join(', ') || '(none)') + '</dd>' +
        '<dt>reflection_threshold</dt><dd>' + Board.util.esc(String(s.reflection_threshold || '')) + '</dd>' +
        '<dt>archive_ttl_days</dt><dd>' + Board.util.esc(String(s.archive_ttl_days || '')) + '</dd>' +
        '<dt>last_run.summary</dt><dd>' +
          (lr.summary || ('total=' + (lr.total_memories || 0) + ' hot=' + (lr.hot_count || 0)
            + ' dedup=' + (lr.dedup_applied || 0) + '/' + (lr.dedup_candidates || 0)
            + ' synth=' + (lr.reflection_synthesized || 0) + '/' + (lr.reflection_clusters || 0))) +
        '</dd>' +
      '</dl>'
    );
  }

  function runCycle(container, dryRun) {
    GC.state.busy = true;
    render(container);
    postRun({ dry_run: dryRun, with_reflection: false }).then(function (res) {
      GC.state.busy = false;
      GC.refresh(container);
      if (res && res.error) {
        alert("GC " + (dryRun ? "dry-run" : "run") + " error: " + res.error);
      }
    });
  }

  function runPrune(container) {
    GC.state.busy = true;
    render(container);
    postPrune(true).then(function (res) {
      GC.state.busy = false;
      GC.refresh(container);
      if (res && res.error) alert("Prune error: " + res.error);
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
