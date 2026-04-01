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
