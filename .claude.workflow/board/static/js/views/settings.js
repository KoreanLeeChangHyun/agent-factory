(function () {
  var panel = document.getElementById('settings-panel');
  var overlay = document.getElementById('settings-overlay');
  var body = document.getElementById('settings-body');

  document.getElementById('settings-toggle').addEventListener('click', open);
  document.getElementById('settings-close').addEventListener('click', close);
  overlay.addEventListener('click', close);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && panel.classList.contains('open')) close();
  });

  function open() {
    panel.classList.add('open');
    overlay.classList.add('open');
    load();
  }

  function close() {
    panel.classList.remove('open');
    overlay.classList.remove('open');
  }

  function load() {
    body.innerHTML = '<div style="text-align:center;padding:2rem;color:#666">Loading...</div>';
    fetch('/api/env')
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function () {
        body.innerHTML = '<div style="text-align:center;padding:2rem;color:#f44747">Failed to load</div>';
      });
  }

  function render(sections) {
    body.innerHTML = '';

    // Actions section (맨 위)
    var actions = document.createElement('div');
    actions.className = 'settings-section';
    actions.innerHTML = '<div class="settings-section-title">Actions</div>';
    var syncItem = document.createElement('div');
    syncItem.className = 'settings-item';
    syncItem.innerHTML =
      '<div class="settings-item-info">' +
        '<div class="settings-item-title">Sync Latest Workflow</div>' +
        '<div class="settings-item-label">.claude/ 및 .claude.workflow/를 최신 버전으로 동기화합니다</div>' +
      '</div>' +
      '<div class="settings-item-control">' +
        '<button class="settings-action-btn" id="settings-sync-btn">Sync</button>' +
      '</div>';

    var syncContainer = document.createElement('div');
    syncContainer.className = 'settings-sync-container';
    syncContainer.innerHTML =
      '<div class="settings-sync-status" id="settings-sync-status" style="display:none"></div>' +
      '<div class="settings-sync-log" id="settings-sync-log" style="display:none"></div>';

    actions.appendChild(syncItem);
    actions.appendChild(syncContainer);

    var restartItem = document.createElement('div');
    restartItem.className = 'settings-item';
    restartItem.innerHTML =
      '<div class="settings-item-info">' +
        '<div class="settings-item-key">Restart Server</div>' +
        '<div class="settings-item-label">Board HTTP 서버를 재시작합니다</div>' +
      '</div>' +
      '<div class="settings-item-control">' +
        '<button class="settings-action-btn" id="settings-restart-btn">Restart</button>' +
      '</div>';
    actions.appendChild(restartItem);
    body.appendChild(actions);

    var restartBtn = document.getElementById('settings-restart-btn');
    if (restartBtn) {
      restartBtn.addEventListener('click', function () {
        restartBtn.disabled = true;
        restartBtn.textContent = 'Restarting...';
        fetch('/api/restart', { method: 'POST' })
          .then(function () {
            setTimeout(function () { location.reload(); }, 1500);
          })
          .catch(function () {
            setTimeout(function () { location.reload(); }, 2000);
          });
      });
    }

    var syncBtn = document.getElementById('settings-sync-btn');
    if (syncBtn) {
      syncBtn.addEventListener('click', function () {
        if (!confirm('현재 프로젝트의 .claude/ 및 .claude.workflow/를 최신 버전으로 덮어씁니다. 계속할까요?')) {
          return;
        }

        var statusEl = document.getElementById('settings-sync-status');
        var logEl = document.getElementById('settings-sync-log');

        syncBtn.disabled = true;
        syncBtn.textContent = 'Syncing...';
        syncContainer.classList.add('active');
        statusEl.style.display = '';
        logEl.style.display = '';
        statusEl.className = 'settings-sync-status starting';
        statusEl.textContent = '시작';
        logEl.innerHTML = '';

        function parseSseBuffer(buffer) {
          var events = [];
          var blocks = buffer.split('\n\n');
          var remaining = blocks.pop();
          blocks.forEach(function (block) {
            if (!block.trim()) return;
            var lines = block.split('\n');
            var evt = {};
            lines.forEach(function (line) {
              if (line.indexOf('event: ') === 0) {
                evt.type = line.slice(7).trim();
              } else if (line.indexOf('data: ') === 0) {
                try { evt.data = JSON.parse(line.slice(6)); } catch (e) { evt.data = {}; }
              }
            });
            if (evt.type) events.push(evt);
          });
          return { events: events, remaining: remaining };
        }

        fetch('/api/workflow/sync', { method: 'POST' })
          .then(function (response) {
            if (response.status === 409) {
              statusEl.className = 'settings-sync-status failed';
              statusEl.textContent = '이미 동기화가 진행 중입니다.';
              syncBtn.disabled = false;
              syncBtn.textContent = 'Sync';
              return;
            }

            var reader = response.body.getReader();
            var decoder = new TextDecoder();
            var buffer = '';

            function read() {
              return reader.read().then(function (chunk) {
                if (chunk.done) return;
                buffer += decoder.decode(chunk.value, { stream: true });
                var parsed = parseSseBuffer(buffer);
                buffer = parsed.remaining;
                parsed.events.forEach(function (evt) {
                  if (evt.type === 'start') {
                    statusEl.className = 'settings-sync-status running';
                    statusEl.textContent = '진행 중';
                  } else if (evt.type === 'log') {
                    var line = document.createElement('div');
                    line.className = 'settings-sync-log-line';
                    line.innerHTML = esc((evt.data && evt.data.line) || '');
                    logEl.appendChild(line);
                    logEl.scrollTop = logEl.scrollHeight;
                  } else if (evt.type === 'done') {
                    statusEl.className = 'settings-sync-status done';
                    statusEl.textContent = '완료 — 서버 재시작 필요';
                    if (restartBtn) {
                      restartBtn.classList.add('pulse');
                      setTimeout(function () { restartBtn.classList.remove('pulse'); }, 3000);
                    }
                  } else if (evt.type === 'error') {
                    statusEl.className = 'settings-sync-status failed';
                    statusEl.textContent = '실패';
                    var errLine = document.createElement('div');
                    errLine.className = 'settings-sync-log-line error';
                    errLine.innerHTML = esc((evt.data && evt.data.message) || '오류가 발생했습니다.');
                    logEl.appendChild(errLine);
                    logEl.scrollTop = logEl.scrollHeight;
                  }
                });
                return read();
              });
            }

            return read().finally(function () {
              syncBtn.disabled = false;
              syncBtn.textContent = 'Sync';
            });
          })
          .catch(function (err) {
            statusEl.className = 'settings-sync-status failed';
            statusEl.textContent = '실패';
            var errLine = document.createElement('div');
            errLine.className = 'settings-sync-log-line error';
            errLine.innerHTML = esc(err && err.message ? err.message : '네트워크 오류가 발생했습니다.');
            logEl.appendChild(errLine);
            syncBtn.disabled = false;
            syncBtn.textContent = 'Sync';
          });
      });
    }

    // Settings sections
    sections.forEach(function (sec) {
      var el = document.createElement('div');
      el.className = 'settings-section';
      el.innerHTML = '<div class="settings-section-title">' + esc(sec.section) + '</div>';
      sec.vars.forEach(function (v) { el.appendChild(createItem(v)); });
      body.appendChild(el);
    });
  }

  function createItem(v) {
    var item = document.createElement('div');
    item.className = 'settings-item';

    var info = document.createElement('div');
    info.className = 'settings-item-info';
    info.innerHTML = '<div class="settings-item-key">' + esc(v.key) + '</div>' +
      (v.label ? '<div class="settings-item-label">' + esc(v.label) + '</div>' : '');

    var ctrl = document.createElement('div');
    ctrl.className = 'settings-item-control';

    if (v.type === 'bool') {
      ctrl.innerHTML =
        '<label class="toggle">' +
          '<input type="checkbox"' + (v.value === 'true' ? ' checked' : '') + '>' +
          '<span class="toggle-track"></span>' +
          '<span class="toggle-thumb"></span>' +
        '</label>';
      var cb = ctrl.querySelector('input');
      cb.addEventListener('change', function () {
        save(v.key, cb.checked ? 'true' : 'false');
      });
    } else {
      var inp = document.createElement('input');
      inp.className = 'settings-input';
      inp.type = (v.type === 'int' || v.type === 'float') ? 'number' : 'text';
      if (v.type === 'float') inp.step = '0.1';
      inp.value = v.value;
      var timer;
      inp.addEventListener('input', function () {
        clearTimeout(timer);
        timer = setTimeout(function () { save(v.key, inp.value, inp); }, 800);
      });
      inp.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { clearTimeout(timer); save(v.key, inp.value, inp); }
      });
      ctrl.appendChild(inp);
    }

    item.appendChild(info);
    item.appendChild(ctrl);
    return item;
  }

  function save(key, value, inputEl) {
    fetch('/api/env', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: key, value: value }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok && inputEl) flash(inputEl, 'saved');
      })
      .catch(function () {
        if (inputEl) flash(inputEl, 'error');
      });
  }

  function flash(el, cls) {
    el.classList.add(cls);
    setTimeout(function () { el.classList.remove(cls); }, 1200);
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }
})();
