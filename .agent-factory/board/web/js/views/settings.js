(function () {
  var panel = document.getElementById('settings-panel');
  var overlay = document.getElementById('settings-overlay');
  var body = document.getElementById('settings-body');
  var resizeHandle = document.getElementById('settings-resize-handle');
  var SETTINGS_WIDTH_KEY = 'agentFactorySettingsWidth';
  var PROVIDER_SETTING_KEY = 'LLM_PROVIDER';
  var PROVIDER_LEGACY_SETTING_KEYS = ['AGENT_FACTORY_LLM_PROVIDER'];
  var SETTINGS_PANEL_OWNED_KEYS = {};
  SETTINGS_PANEL_OWNED_KEYS[PROVIDER_SETTING_KEY] = true;
  PROVIDER_LEGACY_SETTING_KEYS.forEach(function (key) { SETTINGS_PANEL_OWNED_KEYS[key] = true; });
  var SETTING_OPTIONS = {
    LLM_PROVIDER: [
      { value: 'claude', label: 'Claude' },
      { value: 'codex', label: 'Codex' },
      { value: 'fake', label: 'Fake' }
    ]
  };
  var ENV_DESCRIPTIONS = {
    LLM_PROVIDER: 'Brain provider for provider-neutral LLM adapter paths. Supported values: claude, codex, fake.',
    SLACK_BOT_TOKEN: 'Slack Bot OAuth token used to send task notifications. Leave empty to disable Slack notifications.',
    SLACK_CHANNEL_ID: 'Slack channel ID where Agent Factory notifications are posted.',
    SLACK_API_URL: 'Slack chat.postMessage endpoint. Change only when using a compatible proxy.',
    GIT_USER_NAME: 'Git author name used by Agent Factory automation.',
    GIT_USER_EMAIL: 'Git author email used by Agent Factory automation.',
    GITHUB_USERNAME: 'GitHub username used for repository and identity-related automation.',
    SSH_KEY_GITHUB: 'SSH private key path for GitHub operations, when a custom key is required.',
    HOOK_DANGEROUS_COMMAND: 'Blocks or warns on dangerous shell commands before tool execution.',
    HOOK_HOOKS_SELF_PROTECT: 'Protects Agent Factory hook files from accidental modification.',
    HOOK_SLACK_ASK: 'Routes selected approval/ask events through Slack integration.',
    HOOK_TASK_HISTORY_SYNC: 'Synchronizes task history during tool execution.',
    HOOK_AGENT_INVESTIGATION_GUARD: 'Requires stronger investigation before agent or sub-agent related changes.',
    HOOK_MAIN_BRANCH_GUARD: 'Prevents unsafe work directly on the main branch.',
    HOOK_MAIN_SESSION_GUARD: 'Guards actions that should only run from the main session.',
    HOOK_CONVEYOR_SUBCOMMAND_GUARD: 'Guards direct Conveyor subcommands that bypass the intended workflow.',
    HOOK_READONLY_SESSION_GUARD: 'Prevents writes from read-only or archived sessions.',
    HOOK_DIRECT_PATH_GUARD: 'Blocks direct script paths when the supported Agent Factory command should be used.',
    HOOK_COMPLETE_RELATION_GUARD: 'Checks WorkRequest relation consistency when moving work to Complete.',
    HOOK_RULES_AUTO_APPROVE: 'Allows rules-related operations to be auto-approved when safe.',
    HOOK_WORKTREE_REMOVE_GUARD: 'Protects workflow worktrees from unsafe removal.',
    HOOK_WORKTREE_PATH_GUARD: 'Ensures workflow worktree paths stay inside the expected Agent Factory area.',
    HOOK_HALLUCINATION_LOGGER: 'Records suspected hallucination or unsupported-claim events for review.',
    HOOKS_EDIT_ALLOWED: 'Optional allowlist for hook editing. Leave empty unless you need scoped hook changes.',
    HOOK_WORKFLOW_ORCHESTRATION: 'Enables Agent Factory workflow orchestration around WorkRequest execution.',
    HOOK_SESSION_SYSTEM_PROMPT: 'Injects the Agent Factory system prompt context at session start.',
    HOOK_WORKFLOW_AUTO_CONTINUE: 'Allows workflow automation to continue after stop events.',
    HOOK_USAGE_TRACKER: 'Tracks usage metadata after sub-agent sessions stop.',
    HOOK_HISTORY_SYNC_TRIGGER: 'Triggers history synchronization when sub-agent sessions stop.',
    HOOK_CATALOG_SYNC: 'Synchronizes catalog metadata after tool execution.',
    HOOK_USER_PROMPT_CONVEYOR: 'Injects Conveyor and session snapshot context into main user prompts.',
    HOOK_AUDITOR_T3: 'Enables the non-blocking LLM audit advisory layer.',
    AUDITOR_T3_MODEL: 'Optional model override used by the audit advisory layer. Leave empty to use the active provider default.',
    AUDITOR_T3_EFFORT: 'Reasoning effort used by the audit advisory layer.',
    ENFORCE_CSO_PRINCIPLE: 'Enforces skill trigger discipline based on skill descriptions.',
    ENFORCE_RATIONALIZATION_GUARD: 'Requires anti-rationalization checks in relevant workflow outputs.',
    ENFORCE_VRT: 'Requires Verification Result Table output where applicable.',
    ENFORCE_SELF_REVIEW: 'Requires self-review checklist output where applicable.',
    ENFORCE_TOKEN_EFFICIENCY: 'Enforces token-efficiency guidance in workflow behavior.',
    WORKFLOW_KEEP_COUNT: 'Maximum number of workflow run records retained under .agent-factory/runs.',
    CHAIN_MAX_RETRY: 'Maximum retry count when a chain stage fails.',
    WORKFLOW_WORKTREE: 'Enables isolated git worktrees for workflow execution.',
    QUALITY_THRESHOLD: 'Prompt quality threshold from 0.0 to 1.0 for workflow quality checks.',
    ERROR_THRESHOLD: 'Error count threshold before workflow health is considered degraded.',
    STALE_TTL_MINUTES: 'Minutes before a session or workflow is considered stale.',
    ZOMBIE_TTL_HOURS: 'Hours before an abandoned session is treated as zombie state.',
    REPORT_TTL_HOURS: 'Hours before generated report data is considered expired.',
    WORK_NAME_MAX_LEN: 'Maximum generated working directory name length.',
    WORKFLOW_RETRY_INIT: 'Retry count for the init phase.',
    WORKFLOW_RETRY_PLAN: 'Retry count for the plan phase.',
    WORKFLOW_RETRY_WORK: 'Retry count for the work phase.',
    WORKFLOW_RETRY_VALIDATE: 'Retry count for the validate phase.',
    WORKFLOW_RETRY_REPORT: 'Retry count for the report phase.',
    WORKFLOW_RETRY_PROMPT_N: 'Maximum retry-context hint history entries retained.',
    BANNER_WIDTH: 'Terminal banner width. Leave empty to auto-detect terminal width.',
    REPO_URL: 'Remote Agent Factory repository URL used by sync/bootstrap.',
    REQUIRED_PYTHON_MAJOR: 'Required Python major version checked by bootstrap.',
    REQUIRED_PYTHON_MINOR: 'Required Python minor version checked by bootstrap.',
    HOOK_WORKTREE_PATH: 'Current workflow worktree path, usually maintained by Agent Factory automatically.',
    CLAUDE_PERMISSION_MODE: 'Claude adapter permission mode for non-interactive runs.',
    CODEX_BIN: 'Codex executable name or path used by CodexAdapter.',
    CODEX_MODEL: 'Optional Codex model override. Leave empty to use Codex defaults.',
    CODEX_PROFILE: 'Optional Codex profile name from Codex config.',
    CODEX_SANDBOX: 'Codex sandbox mode, for example workspace-write.',
    CODEX_APPROVAL_POLICY: 'Codex approval policy, for example never.'
  };

  document.getElementById('settings-toggle').addEventListener('click', open);
  document.getElementById('settings-close').addEventListener('click', close);
  overlay.addEventListener('click', close);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && panel.classList.contains('open')) close();
  });

  function open() {
    applySavedWidth();
    panel.classList.add('open');
    overlay.classList.add('open');
    load();
  }

  function close() {
    panel.classList.remove('open');
    overlay.classList.remove('open');
  }

  function clampWidth(px) {
    var min = Math.min(420, window.innerWidth);
    var max = Math.max(min, Math.min(880, window.innerWidth));
    return Math.max(min, Math.min(max, px));
  }

  function applySavedWidth() {
    try {
      var saved = parseInt(localStorage.getItem(SETTINGS_WIDTH_KEY), 10);
      if (Number.isFinite(saved)) {
        panel.style.width = clampWidth(saved) + 'px';
      }
    } catch (e) {}
  }

  if (resizeHandle) {
    resizeHandle.addEventListener('pointerdown', function (e) {
      if (e.button !== 0) return;
      e.preventDefault();
      resizeHandle.setPointerCapture(e.pointerId);
      panel.classList.add('resizing');

      function move(ev) {
        var next = clampWidth(window.innerWidth - ev.clientX);
        panel.style.width = next + 'px';
      }

      function done(ev) {
        move(ev);
        panel.classList.remove('resizing');
        try { localStorage.setItem(SETTINGS_WIDTH_KEY, String(Math.round(panel.getBoundingClientRect().width))); } catch (err) {}
        resizeHandle.releasePointerCapture(ev.pointerId);
        resizeHandle.removeEventListener('pointermove', move);
        resizeHandle.removeEventListener('pointerup', done);
        resizeHandle.removeEventListener('pointercancel', done);
      }

      resizeHandle.addEventListener('pointermove', move);
      resizeHandle.addEventListener('pointerup', done);
      resizeHandle.addEventListener('pointercancel', done);
    });
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

    // Actions section
    var actions = document.createElement('div');
    actions.className = 'settings-section';
    actions.innerHTML = '<div class="settings-section-title">Actions</div>';
    var syncItem = document.createElement('div');
    syncItem.className = 'settings-item';
    syncItem.innerHTML =
      '<div class="settings-item-info">' +
        '<div class="settings-item-title">Sync Latest Workflow</div>' +
        '<div class="settings-item-label">.claude/ and .agent-factory/ synchronize with the latest version</div>' +
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
        '<div class="settings-item-label">Restart the Agent Factory Console server</div>' +
      '</div>' +
      '<div class="settings-item-control">' +
        '<button class="settings-action-btn" id="settings-restart-btn">Restart</button>' +
      '</div>';
    actions.appendChild(restartItem);

    var loginItem = document.createElement('div');
    loginItem.className = 'settings-item';
    loginItem.innerHTML =
      '<div class="settings-item-info">' +
        '<div class="settings-item-key">Login</div>' +
        '<div class="settings-item-label">Send /login to the active Console session.</div>' +
      '</div>' +
      '<div class="settings-item-control">' +
        '<button class="settings-action-btn" id="settings-login-btn">Login</button>' +
      '</div>';
    actions.appendChild(loginItem);

    var buildUrlItem = document.createElement('div');
    buildUrlItem.className = 'settings-item';
    buildUrlItem.innerHTML =
      '<div class="settings-item-info">' +
        '<div class="settings-item-key">Build URL</div>' +
        '<div class="settings-item-label">Copy the Agent Factory bootstrap command for other projects.</div>' +
      '</div>' +
      '<div class="settings-item-control">' +
        '<button class="settings-action-btn" id="settings-build-url-btn">Copy</button>' +
      '</div>';
    actions.appendChild(buildUrlItem);
    body.appendChild(actions);

    var provider = document.createElement('div');
    provider.className = 'settings-section settings-provider';
    var brain = getSettingValue(sections, PROVIDER_SETTING_KEY, PROVIDER_LEGACY_SETTING_KEYS) || (window.AgentFactoryBrain ? window.AgentFactoryBrain.getBrain() : 'claude');
    brain = normalizeBrain(brain);
    if (window.AgentFactoryBrain) {
      window.AgentFactoryBrain.setBrain(brain);
    }
    provider.innerHTML =
      '<div class="settings-section-title">Provider</div>' +
      '<div class="settings-item settings-provider-item">' +
        '<div class="settings-item-info">' +
          '<div class="settings-item-key">' + PROVIDER_SETTING_KEY + '</div>' +
          '<div class="settings-item-label">Controls the active LLM adapter, Console terminal process, and Board accent color.</div>' +
          '<div class="settings-provider-meta">' +
            '<span class="settings-provider-meta-label">Active adapter</span>' +
            '<span class="settings-provider-pill" id="settings-provider-pill">' + adapterLabel(brain) + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="settings-item-control">' +
          '<select class="settings-select" id="settings-brain-theme">' +
            '<option value="claude">Claude</option>' +
            '<option value="codex">Codex</option>' +
            '<option value="fake">Fake</option>' +
          '</select>' +
        '</div>' +
      '</div>' +
      '<div class="settings-item">' +
        '<div class="settings-item-info">' +
          '<div class="settings-item-key">Terminal capability</div>' +
          '<div class="settings-item-label" id="settings-terminal-capability-label">' + terminalCapabilityLabel(brain) + '</div>' +
        '</div>' +
        '<div class="settings-item-control"><span class="settings-capability-pill" id="settings-terminal-capability-pill">' + terminalCapabilityPill(brain) + '</span></div>' +
      '</div>' +
      '<details class="settings-adapter-details">' +
        '<summary id="settings-adapter-summary">' + adapterLabel(brain) + ' details</summary>' +
        '<div class="settings-adapter-body" id="settings-adapter-body">' + adapterDetails(brain) + '</div>' +
      '</details>';
    body.appendChild(provider);

    var brainSelect = document.getElementById('settings-brain-theme');
    if (brainSelect) {
      brainSelect.value = brain;
      brainSelect.addEventListener('change', function () {
        var selectedBrain = normalizeBrain(brainSelect.value);
        if (window.AgentFactoryBrain) {
          window.AgentFactoryBrain.setBrain(selectedBrain);
        }
        var pill = document.getElementById('settings-provider-pill');
        if (pill) pill.textContent = adapterLabel(selectedBrain);
        updateProviderCapability(selectedBrain);
        save(PROVIDER_SETTING_KEY, providerValue(selectedBrain), brainSelect);
      });
    }

    var buildUrlBtn = document.getElementById('settings-build-url-btn');
    if (buildUrlBtn) {
      buildUrlBtn.addEventListener('click', function () {
        if (buildUrlBtn.disabled) return;
        buildUrlBtn.disabled = true;
        var originalText = buildUrlBtn.textContent;
        fetch('/.agent-factory/build.url', { cache: 'no-store' })
          .then(function (r) {
            if (!r.ok) throw new Error('build.url not found');
            return r.text();
          })
          .then(function (text) {
            return navigator.clipboard.writeText(text.trim());
          })
          .then(function () {
            buildUrlBtn.textContent = 'Copied!';
            setTimeout(function () {
              buildUrlBtn.textContent = originalText;
              buildUrlBtn.disabled = false;
            }, 1200);
          })
          .catch(function () {
            buildUrlBtn.textContent = 'Failed';
            setTimeout(function () {
              buildUrlBtn.textContent = originalText;
              buildUrlBtn.disabled = false;
            }, 1500);
          });
      });
    }

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
        if (!confirm('.claude/ and .agent-factory/ of the current project is covered with the latest version. About Us')) {
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
        statusEl.textContent = 'Start';
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

        fetch('/api/settings/workflow-sync', { method: 'POST' })
          .then(function (response) {
            if (response.status === 409) {
              statusEl.className = 'settings-sync-status failed';
              statusEl.textContent = 'Sync is already in progress.';
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
                    statusEl.textContent = 'About Us';
                  } else if (evt.type === 'log') {
                    var line = document.createElement('div');
                    line.className = 'settings-sync-log-line';
                    line.innerHTML = esc((evt.data && evt.data.line) || '');
                    logEl.appendChild(line);
                    logEl.scrollTop = logEl.scrollHeight;
                  } else if (evt.type === 'done') {
                    statusEl.className = 'settings-sync-status done';
                    statusEl.textContent = '— server restart required';
                    if (restartBtn) {
                      restartBtn.classList.add('pulse');
                      setTimeout(function () { restartBtn.classList.remove('pulse'); }, 3000);
                    }
                  } else if (evt.type === 'error') {
                    statusEl.className = 'settings-sync-status failed';
                    statusEl.textContent = 'Failure';
                    var errLine = document.createElement('div');
                    errLine.className = 'settings-sync-log-line error';
                    errLine.innerHTML = esc((evt.data && evt.data.message) || 'I\'ve got a problem.');
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
            statusEl.textContent = 'Failure';
            var errLine = document.createElement('div');
            errLine.className = 'settings-sync-log-line error';
            errLine.innerHTML = esc(err && err.message ? err.message : 'I\'ve been using a network error.');
            logEl.appendChild(errLine);
            syncBtn.disabled = false;
            syncBtn.textContent = 'Sync';
          });
      });
    }

    var loginBtn = document.getElementById('settings-login-btn');
    if (loginBtn) {
      var loginBrain = getSettingValue(sections, PROVIDER_SETTING_KEY, PROVIDER_LEGACY_SETTING_KEYS) || (window.AgentFactoryBrain ? window.AgentFactoryBrain.getBrain() : 'claude');
      if (!supportsSlashCommands(normalizeBrain(loginBrain))) {
        loginBtn.disabled = true;
        loginBtn.title = 'Login command is not supported by this terminal provider';
      }
      loginBtn.addEventListener('click', function () {
        if (loginBtn.disabled) return;
        loginBtn.disabled = true;
        loginBtn.textContent = 'Sending...';
        fetch('/terminal/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: '/login' }),
        })
          .then(function (r) {
            if (!r.ok) throw new Error('Login command failed');
            loginBtn.textContent = 'Sent';
          })
          .catch(function () {
            loginBtn.textContent = 'Failed';
          })
          .finally(function () {
            setTimeout(function () {
              loginBtn.textContent = 'Login';
              loginBtn.disabled = false;
            }, 1200);
          });
      });
    }

    // Settings sections
    sections.forEach(function (sec) {
      var visibleVars = (sec.vars || []).filter(function (v) {
        return !SETTINGS_PANEL_OWNED_KEYS[v.key];
      });
      if (!visibleVars.length) return;
      var el = document.createElement('div');
      el.className = 'settings-section';
      el.innerHTML = '<div class="settings-section-title">' + esc(sec.section) + '</div>';
      visibleVars.forEach(function (v) { el.appendChild(createItem(v)); });
      body.appendChild(el);
    });
  }

  function createItem(v) {
    var item = document.createElement('div');
    item.className = 'settings-item';

    var info = document.createElement('div');
    info.className = 'settings-item-info';
    var label = ENV_DESCRIPTIONS[v.key] || v.label || 'No description available yet.';
    info.innerHTML = '<div class="settings-item-key">' + esc(v.key) + '</div>' +
      '<div class="settings-item-label">' + esc(label) + '</div>';

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
    } else if (SETTING_OPTIONS[v.key]) {
      var select = document.createElement('select');
      select.className = 'settings-select';
      select.setAttribute('data-setting-key', v.key);
      SETTING_OPTIONS[v.key].forEach(function (opt) {
        var option = document.createElement('option');
        option.value = opt.value;
        option.textContent = opt.label;
        select.appendChild(option);
      });
      select.value = providerValue(normalizeBrain(v.value));
      select.addEventListener('change', function () {
        var selected = normalizeBrain(select.value);
        select.value = providerValue(selected);
        if (v.key === PROVIDER_SETTING_KEY) {
          if (window.AgentFactoryBrain) {
            window.AgentFactoryBrain.setBrain(selected);
          }
          var pill = document.getElementById('settings-provider-pill');
          if (pill) pill.textContent = adapterLabel(selected);
          updateProviderCapability(selected);
        }
        save(v.key, select.value, select);
      });
      ctrl.appendChild(select);
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

  function getSettingValue(sections, key, legacyKeys) {
    var keys = [key].concat(legacyKeys || []);
    for (var k = 0; k < keys.length; k++) {
      var value = getExactSettingValue(sections, keys[k]);
      if (value) return value;
    }
    return '';
  }

  function getExactSettingValue(sections, key) {
    for (var i = 0; i < sections.length; i++) {
      var vars = sections[i].vars || [];
      for (var j = 0; j < vars.length; j++) {
        if (vars[j].key === key) return String(vars[j].value || '').trim();
      }
    }
    return '';
  }

  function normalizeBrain(value) {
    var brain = String(value || 'claude').toLowerCase();
    if (brain === 'openai') return 'codex';
    if (brain === 'fake') return 'fake';
    if (brain === 'codex') return 'codex';
    return 'claude';
  }

  function providerValue(brain) {
    return brain === 'fake' ? 'fake' : brain === 'codex' ? 'codex' : 'claude';
  }

  function adapterLabel(brain) {
    if (brain === 'codex') return 'CodexAdapter';
    if (brain === 'fake') return 'FakeAdapter';
    return 'ClaudeAdapter';
  }

  function terminalCapabilityPill(brain) {
    if (brain === 'codex') return 'Experimental';
    if (brain === 'fake') return 'No terminal';
    return 'Full';
  }

  function terminalCapabilityLabel(brain) {
    if (brain === 'codex') {
      return 'Codex terminal is experimental: current-thread follow-up uses codex exec resume when a session id is available; session list resume, attachments, and permission prompts are not supported yet.';
    }
    if (brain === 'fake') {
      return 'FakeAdapter is for tests and does not expose a live terminal process.';
    }
    return 'Claude terminal supports resume, attachments, slash commands, permission prompts, and interrupts.';
  }

  function adapterDetails(brain) {
    if (brain === 'codex') {
      return 'Console process integration uses codex exec --json - and codex exec resume --json to normalize stdout events into the Terminal stream.';
    }
    if (brain === 'fake') {
      return 'FakeAdapter is available for deterministic application tests; terminal start falls back to Claude until a fake process exists.';
    }
    return 'Console process integration uses local Claude Code hooks and .agent-factory runtime paths.';
  }

  function supportsSlashCommands(brain) {
    return brain === 'claude';
  }

  function updateProviderCapability(brain) {
    var capLabel = document.getElementById('settings-terminal-capability-label');
    if (capLabel) capLabel.textContent = terminalCapabilityLabel(brain);
    var capPill = document.getElementById('settings-terminal-capability-pill');
    if (capPill) capPill.textContent = terminalCapabilityPill(brain);
    var summary = document.getElementById('settings-adapter-summary');
    if (summary) summary.textContent = adapterLabel(brain) + ' details';
    var body = document.getElementById('settings-adapter-body');
    if (body) body.textContent = adapterDetails(brain);
    var loginBtn = document.getElementById('settings-login-btn');
    if (loginBtn) {
      var supported = supportsSlashCommands(brain);
      loginBtn.disabled = !supported;
      loginBtn.title = supported
        ? 'Send /login to the active Console session.'
        : 'Login command is not supported by this terminal provider';
    }
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
