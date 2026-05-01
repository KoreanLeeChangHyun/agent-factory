/**
 * @module memory/memory-core
 * Split from memory.js. Functions on Board._memory (M) namespace.
 * Contains: state init, APIs, helpers, CLAUDE.md sub-tab, Memory sub-tab, main entry.
 */
"use strict";

(function () {
  var esc = Board.util.esc;
  var M = (Board._memory = Board._memory || {});

  // ── State: Contexts tab (shared) ──
  // 서브탭: roadmap | rules | memory | prompt
  // CLAUDE.md 는 Rules 서브탭의 "Project Meta" 카테고리에 편입되어 별도 서브탭이 아니다.
  // 사용자 선택은 Board.state.contexts (common.js, localStorage 영속) 가 단일 진실 공급원.
  // 아래 변수들은 영속 상태에서 read-only 미러 — 변경 시 M.persistContexts() 호출 필수.
  var _cx = Board.state.contexts || { subTab: "roadmap", memory: {}, rules: {}, prompt: {} };
  Board.state.promptSubTab = _cx.subTab || "roadmap";

  // ── State: Rules sub-tab ──
  Board.state.promptRulesFiles = [];
  Board.state.promptRulesActiveFile = (_cx.rules && _cx.rules.activeFile) || null;
  Board.state.promptRulesDirty = false;
  Board.state.promptRulesPreview = false;
  Board.state.promptRulesOriginalContent = "";

  // ── State: Prompt sub-tab ──
  Board.state.promptPromptFiles = [];
  Board.state.promptPromptActiveFile = (_cx.prompt && _cx.prompt.activeFile) || null;
  Board.state.promptPromptDirty = false;
  Board.state.promptPromptPreview = false;
  Board.state.promptPromptOriginalContent = "";

  // ── State: Quick Prompts sub-tab ──
  Board.state.promptQuickItems = [];
  Board.state.promptQuickDirtyById = {};
  Board.state.promptQuickOriginalById = {};

  // ── State: CLAUDE.md sub-tab ──
  Board.state.promptClaudeMdContent = "";
  Board.state.promptClaudeMdDirty = false;
  Board.state.promptClaudeMdPreview = false;
  Board.state.promptClaudeMdOriginalContent = "";

  // ── State: Memory sub-tab (existing) ──
  Board.state.memoryFiles = [];
  Board.state.memoryActiveFile = (_cx.memory && _cx.memory.activeFile) || null;
  Board.state.memoryDirty = false;
  Board.state.memoryPreview = false;
  Board.state.memoryOriginalContent = "";

  // 영속 상태 동기화 — 모든 사용자 이벤트(서브탭 전환·파일 선택·sidebar resize·GC bar 토글)
  // 후 호출. Board.state 의 휘발 변수들을 contexts 객체에 반영하고 saveUI() 로 commit.
  M.persistContexts = function () {
    var cx = Board.state.contexts;
    if (!cx) return;
    cx.subTab = Board.state.promptSubTab;
    if (cx.memory) cx.memory.activeFile = Board.state.memoryActiveFile;
    if (cx.rules) cx.rules.activeFile = Board.state.promptRulesActiveFile;
    if (cx.prompt) cx.prompt.activeFile = Board.state.promptPromptActiveFile;
    if (Board.util && Board.util.saveUI) Board.util.saveUI();
  };

  // ═══════════════════════════════════════════════════════════════════
  // Fetch Functions
  // ═══════════════════════════════════════════════════════════════════

  // ── Memory API ──

  M.fetchMemoryList = function() {
    return fetch("/api/memory", { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : []; })
      .catch(function () { return []; });
  };

  M.fetchMemoryFile = function(name) {
    return fetch("/api/memory/file?name=" + encodeURIComponent(name), { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; });
  };

  M.saveMemoryFile = function(name, content) {
    return fetch("/api/memory/file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, content: content }),
    }).then(function (res) { return res.json(); })
      .catch(function () { return null; });
  };

  M.deleteMemoryFile = function(name) {
    return fetch("/api/memory/file?name=" + encodeURIComponent(name), { method: "DELETE" })
      .then(function (res) { return res.json(); })
      .catch(function () { return null; });
  };

  Board.fetch.fetchMemoryList = M.fetchMemoryList;
  Board.fetch.fetchMemoryFile = M.fetchMemoryFile;

  // ── Rules API ──

  M.fetchRulesList = function() {
    return fetch("/api/prompt/rules", { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : []; })
      .catch(function () { return []; });
  };

  // CLAUDE.md 가 Rules 사이드바 "Project Meta" 카테고리에 편입되었으므로,
  // path === "CLAUDE.md" 인 special case 를 fetch/save/delete 시 분기 처리한다.
  M.fetchRulesFile = function(path) {
    if (path === "CLAUDE.md") return M.fetchClaudeMd();
    return fetch("/api/prompt/rules/file?path=" + encodeURIComponent(path), { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; });
  };

  M.saveRulesFile = function(path, content) {
    if (path === "CLAUDE.md") return M.saveClaudeMd(content);
    return fetch("/api/prompt/rules/file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path, content: content }),
    }).then(function (res) { return res.json(); })
      .catch(function () { return null; });
  };

  M.deleteRulesFile = function(path) {
    if (path === "CLAUDE.md") {
      return Promise.resolve({ ok: false, error: "CLAUDE.md cannot be deleted." });
    }
    return fetch("/api/prompt/rules/file?path=" + encodeURIComponent(path), { method: "DELETE" })
      .then(function (res) { return res.json(); })
      .catch(function () { return null; });
  };

  // ── Prompt Files API ──

  M.fetchPromptList = function() {
    return fetch("/api/prompt/prompt-files", { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : []; })
      .catch(function () { return []; });
  };

  M.fetchPromptFile = function(name) {
    return fetch("/api/prompt/prompt-files/file?name=" + encodeURIComponent(name), { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; });
  };

  M.savePromptFile = function(name, content) {
    return fetch("/api/prompt/prompt-files/file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, content: content }),
    }).then(function (res) { return res.json(); })
      .catch(function () { return null; });
  };

  M.deletePromptFile = function(name) {
    return fetch("/api/prompt/prompt-files/file?name=" + encodeURIComponent(name), { method: "DELETE" })
      .then(function (res) { return res.json(); })
      .catch(function () { return null; });
  };

  // ── Quick Prompts API ──

  M.fetchQuickPrompts = function() {
    return fetch("/api/quick-prompts", { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : { version: 1, items: [] }; })
      .catch(function () { return { version: 1, items: [] }; });
  };

  M.saveQuickPrompt = function(item) {
    return fetch("/api/quick-prompts/item", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(item),
    }).then(function (res) { return res.json(); })
      .catch(function () { return null; });
  };

  M.deleteQuickPrompt = function(id) {
    return fetch("/api/quick-prompts/item?id=" + encodeURIComponent(id), { method: "DELETE" })
      .then(function (res) { return res.json(); })
      .catch(function () { return null; });
  };

  // 메모리 버튼/단축 명령에서 사용하는 lookup 헬퍼.
  // 매번 fetch 해서 사용자가 방금 편집한 문구가 즉시 반영되도록 한다.
  M.getQuickPromptText = function(id, fallback) {
    return M.fetchQuickPrompts().then(function (data) {
      var items = (data && data.items) || [];
      for (var i = 0; i < items.length; i++) {
        if (items[i] && items[i].id === id && typeof items[i].prompt === "string") {
          return items[i].prompt;
        }
      }
      return fallback;
    }).catch(function () { return fallback; });
  };

  Board.fetch.fetchQuickPrompts = M.fetchQuickPrompts;
  Board.fetch.getQuickPromptText = M.getQuickPromptText;

  // ── CLAUDE.md API ──

  M.fetchClaudeMd = function() {
    return fetch("/api/prompt/claude-md", { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; });
  };

  M.saveClaudeMd = function(content) {
    return fetch("/api/prompt/claude-md", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: content }),
    }).then(function (res) { return res.json(); })
      .catch(function () { return null; });
  };

  // ═══════════════════════════════════════════════════════════════════
  // Shared Helpers
  // ═══════════════════════════════════════════════════════════════════

  M.formatFileSize = function(bytes) {
    if (bytes == null) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  /**
   * Returns true if the currently active sub-tab has unsaved changes.
   */
  M.isCurrentSubTabDirty = function() {
    var sub = Board.state.promptSubTab;
    if (sub === "rules") return Board.state.promptRulesDirty;
    if (sub === "prompt") return Board.state.promptPromptDirty;
    if (sub === "memory") return Board.state.memoryDirty;
    if (sub === "quick-prompts") {
      var dirty = Board.state.promptQuickDirtyById || {};
      for (var k in dirty) { if (dirty[k]) return true; }
      return false;
    }
    return false;
  };

  // ═══════════════════════════════════════════════════════════════════
  // Main Render: M.renderPrompt (replaces renderMemory)
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Renders the complete Prompt tab UI.
   * Builds the sub-tab bar and delegates to the active sub-tab renderer.
   */
  M.renderPrompt = function() {
    var container = document.getElementById("view-memory");
    if (!container) return;

    // Build wrapper -> sub-tab bar + content area
    // Uses .prompt-view-wrapper (flex column) inside #view-memory (flex row)
    container.innerHTML =
      '<div class="prompt-view-wrapper">' +
        '<div class="prompt-subtab-bar">' +
          M.renderSubTabButton("roadmap", "Roadmap") +
          M.renderSubTabButton("rules", "Rules") +
          M.renderSubTabButton("memory", "Memory") +
          M.renderSubTabButton("quick-prompts", "Quick Prompts") +
          M.renderSubTabButton("prompt", "Prompt") +
        '</div>' +
        '<div class="prompt-subtab-content" id="prompt-content"></div>' +
      '</div>';

    // Bind sub-tab click handlers
    var btns = container.querySelectorAll(".prompt-subtab");
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener("click", M.onSubTabClick);
    }

    // Render active sub-tab content
    M.renderActiveSubTab();
  };

  M.renderSubTabButton = function(key, label) {
    var active = Board.state.promptSubTab === key ? " active" : "";
    return '<button class="prompt-subtab' + active + '" data-subtab="' + key + '">' + esc(label) + '</button>';
  };

  M.onSubTabClick = function(e) {
    var target = e.currentTarget.dataset.subtab;
    if (!target || target === Board.state.promptSubTab) return;

    // Dirty check before switching
    if (M.isCurrentSubTabDirty()) {
      if (!confirm("Unsaved changes will be lost. Continue?")) return;
      // Reset dirty state of the tab being left
      M.resetDirtyState(Board.state.promptSubTab);
    }

    Board.state.promptSubTab = target;
    M.persistContexts();

    // Update sub-tab bar active state
    var bar = document.querySelector(".prompt-subtab-bar");
    if (bar) {
      var btns = bar.querySelectorAll(".prompt-subtab");
      for (var i = 0; i < btns.length; i++) {
        btns[i].classList.toggle("active", btns[i].dataset.subtab === target);
      }
    }

    M.renderActiveSubTab();
  };

  M.resetDirtyState = function(subTab) {
    if (subTab === "rules") Board.state.promptRulesDirty = false;
    else if (subTab === "prompt") Board.state.promptPromptDirty = false;
    else if (subTab === "memory") Board.state.memoryDirty = false;
    else if (subTab === "quick-prompts") Board.state.promptQuickDirtyById = {};
  };

  M.renderActiveSubTab = function() {
    var sub = Board.state.promptSubTab;
    if (sub === "roadmap") M.renderSubRoadmap();
    else if (sub === "rules") M.renderSubRules();
    else if (sub === "memory") M.renderSubMemory();
    else if (sub === "quick-prompts") M.renderSubQuickPrompts();
    else if (sub === "prompt") M.renderSubPromptFiles();
  };

  // Roadmap 서브탭 — views/roadmap.js 가 등록한 진입점에 위임.
  M.renderSubRoadmap = function() {
    var content = document.getElementById("prompt-content");
    if (!content) return;
    if (Board.render.renderRoadmapSubtab) {
      Board.render.renderRoadmapSubtab(content);
    } else {
      content.innerHTML = '<div class="memory-empty-icon" aria-hidden="true">'
        + '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        + '<path d="M12 2v20M2 12h20"/></svg></div>'
        + '<p>Roadmap module not loaded.</p>';
    }
  };

  // Compatibility: Board.render.renderMemory = M.renderPrompt
  Board.render.renderMemory = M.renderPrompt;

  // ═══════════════════════════════════════════════════════════════════
  // Resize Handle
  // ═══════════════════════════════════════════════════════════════════

  M.bindResizeHandle = function(container, kind) {
    var handle = container.querySelector(".memory-resize-handle");
    if (!handle) return;
    var sidebar = container.querySelector(".memory-sidebar");
    if (!sidebar) return;

    // 저장된 width 즉시 적용 (kind = "memory" | "rules" | "prompt")
    var cx = Board.state.contexts;
    var bucket = (cx && kind && cx[kind]) ? cx[kind] : null;
    if (bucket && typeof bucket.sidebarWidth === "number"
        && bucket.sidebarWidth >= 140 && bucket.sidebarWidth <= 600) {
      sidebar.style.width = bucket.sidebarWidth + "px";
      sidebar.style.minWidth = bucket.sidebarWidth + "px";
    }

    handle.addEventListener("mousedown", function (e) {
      e.preventDefault();
      handle.classList.add("dragging");
      var startX = e.clientX;
      var startW = sidebar.offsetWidth;
      var lastW = startW;

      function onMove(ev) {
        var w = startW + (ev.clientX - startX);
        if (w < 140) w = 140;
        if (w > 600) w = 600;
        sidebar.style.width = w + "px";
        sidebar.style.minWidth = w + "px";
        lastW = w;
      }
      function onUp() {
        handle.classList.remove("dragging");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        if (bucket) {
          bucket.sidebarWidth = lastW;
          if (Board.util && Board.util.saveUI) Board.util.saveUI();
        }
      }
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  };

  // ═══════════════════════════════════════════════════════════════════
  // Sub-tab: Rules
  // ═══════════════════════════════════════════════════════════════════



  M.renderSubClaudeMd = function() {
    var content = document.getElementById("prompt-content");
    if (!content) return;

    M.fetchClaudeMd().then(function (data) {
      if (!data) {
        content.innerHTML =
          '<div class="memory-empty">' +
            '<div class="memory-empty-icon">&#128221;</div>' +
            '<div class="memory-empty-text">CLAUDE.md not found</div>' +
            '<div class="memory-empty-sub">No CLAUDE.md file in project root.</div>' +
          '</div>';
        return;
      }

      Board.state.promptClaudeMdContent = data.content;
      Board.state.promptClaudeMdOriginalContent = data.content;
      Board.state.promptClaudeMdDirty = false;
      Board.state.promptClaudeMdPreview = true;

      content.innerHTML = M.renderClaudeMdLayout();
      M.bindClaudeMdToolbar();
      M.bindClaudeMdKeyboard();

      var textarea = document.getElementById("claudemd-textarea");
      if (textarea) {
        textarea.value = data.content;
        textarea.disabled = false;
        textarea.classList.add("hidden");
      }
      var previewEl = document.getElementById("claudemd-preview");
      if (previewEl) {
        previewEl.innerHTML = Board.render.renderMd(data.content);
        previewEl.classList.add("visible");
        Board.render.initHighlight();
        Board.render.initMermaid();
      }
      var previewBtn = document.getElementById("claudemd-btn-preview");
      if (previewBtn) { previewBtn.textContent = "Edit"; previewBtn.classList.remove("active"); }
      var filenameEl = document.getElementById("claudemd-toolbar-filename");
      if (filenameEl) filenameEl.textContent = "CLAUDE.md (" + M.formatFileSize(data.size) + ")";
    });
  };

  M.renderClaudeMdLayout = function() {
    return (
      '<div class="prompt-full-editor">' +
        '<div class="memory-toolbar" id="claudemd-toolbar">' +
          '<span class="memory-toolbar-filename" id="claudemd-toolbar-filename">CLAUDE.md</span>' +
          '<span class="memory-toolbar-dirty" id="claudemd-toolbar-dirty">Unsaved</span>' +
          '<button class="memory-toolbar-btn" id="claudemd-btn-preview" title="Edit mode">Edit</button>' +
          '<button class="memory-toolbar-btn" id="claudemd-btn-save" title="Save (Ctrl+S)" disabled>Save</button>' +
        '</div>' +
        '<div class="memory-edit-area" id="claudemd-edit-area">' +
          '<textarea class="memory-textarea" id="claudemd-textarea" placeholder="Loading CLAUDE.md..." disabled></textarea>' +
          '<div class="memory-preview md-body" id="claudemd-preview"></div>' +
        '</div>' +
      '</div>'
    );
  };

  M.bindClaudeMdToolbar = function() {
    var textarea = document.getElementById("claudemd-textarea");
    var saveBtn = document.getElementById("claudemd-btn-save");
    var previewBtn = document.getElementById("claudemd-btn-preview");

    if (textarea) {
      textarea.addEventListener("input", function () {
        var isDirty = textarea.value !== Board.state.promptClaudeMdOriginalContent;
        M.setClaudeMdDirty(isDirty);
      });
    }
    if (saveBtn) saveBtn.addEventListener("click", M.doClaudeMdSave);
    if (previewBtn) previewBtn.addEventListener("click", M.toggleClaudeMdPreview);
  };

  M.bindClaudeMdKeyboard = function() {
    var textarea = document.getElementById("claudemd-textarea");
    if (!textarea) return;
    textarea.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (Board.state.promptClaudeMdDirty) M.doClaudeMdSave();
      }
      if (e.key === "Tab") {
        e.preventDefault();
        var start = textarea.selectionStart;
        var end = textarea.selectionEnd;
        textarea.value = textarea.value.substring(0, start) + "  " + textarea.value.substring(end);
        textarea.selectionStart = textarea.selectionEnd = start + 2;
        textarea.dispatchEvent(new Event("input"));
      }
    });
  };

  M.setClaudeMdDirty = function(isDirty) {
    Board.state.promptClaudeMdDirty = isDirty;
    var saveBtn = document.getElementById("claudemd-btn-save");
    var dirtyEl = document.getElementById("claudemd-toolbar-dirty");
    if (saveBtn) saveBtn.disabled = !isDirty;
    if (dirtyEl) dirtyEl.classList.toggle("visible", isDirty);
  };

  M.doClaudeMdSave = function() {
    var textarea = document.getElementById("claudemd-textarea");
    if (!textarea) return;
    var content = textarea.value;
    var saveBtn = document.getElementById("claudemd-btn-save");
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }

    M.saveClaudeMd(content).then(function (result) {
      if (saveBtn) saveBtn.textContent = "Save";
      if (result && result.ok) {
        Board.state.promptClaudeMdOriginalContent = content;
        Board.state.promptClaudeMdContent = content;
        M.setClaudeMdDirty(false);
      } else {
        if (saveBtn) saveBtn.disabled = false;
        alert("Failed to save CLAUDE.md.");
      }
    });
  };

  M.toggleClaudeMdPreview = function() {
    Board.state.promptClaudeMdPreview = !Board.state.promptClaudeMdPreview;
    var preview = document.getElementById("claudemd-preview");
    var textarea = document.getElementById("claudemd-textarea");
    var previewBtn = document.getElementById("claudemd-btn-preview");

    if (Board.state.promptClaudeMdPreview) {
      // Preview mode: show preview, hide textarea, button says "Edit"
      var content = textarea ? textarea.value : "";
      if (preview) {
        preview.innerHTML = Board.render.renderMd(content);
        preview.classList.add("visible");
        Board.render.initHighlight();
        Board.render.initMermaid();
      }
      if (textarea) textarea.classList.add("hidden");
      if (previewBtn) { previewBtn.textContent = "Edit"; previewBtn.classList.remove("active"); }
    } else {
      // Edit mode: show textarea, hide preview, button says "Preview"
      if (preview) { preview.classList.remove("visible"); preview.innerHTML = ""; }
      if (textarea) { textarea.classList.remove("hidden"); textarea.focus(); }
      if (previewBtn) { previewBtn.textContent = "Preview"; previewBtn.classList.add("active"); }
    }
  };

  // ═══════════════════════════════════════════════════════════════════
  // Sub-tab: Memory (existing logic preserved)
  // ═══════════════════════════════════════════════════════════════════

  M.renderSubMemory = function() {
    var content = document.getElementById("prompt-content");
    if (!content) return;

    M.fetchMemoryList().then(function (files) {
      Board.state.memoryFiles = files;

      // GC bar + body 2단 column 분리.
      // prompt-subtab-content 는 row 라 wrapper 안에서 column 흐름을 잡아준다.
      content.innerHTML =
        '<div class="memory-vertical-wrap">' +
          '<div class="memory-gc-host" id="memory-gc-host"></div>' +
          '<div class="memory-body-host" id="memory-body-host"></div>' +
        '</div>';
      var bodyHost = document.getElementById("memory-body-host");
      var gcHost = document.getElementById("memory-gc-host");

      if (Board.render.renderMemoryGcBar) {
        Board.render.renderMemoryGcBar(gcHost);
      }

      if (!files || files.length === 0) {
        bodyHost.innerHTML = M.renderMemoryEmptyState();
        M.bindMemoryEmptyNewBtn(bodyHost);
        return;
      }

      bodyHost.innerHTML = M.renderMemoryLayout();
      M.bindResizeHandle(bodyHost, "memory");
      M.renderMemorySidebar();
      M.bindMemoryToolbar();
      M.bindMemoryKeyboard();

      // Auto-select: previously active file or first file
      var toSelect = null;
      if (Board.state.memoryActiveFile) {
        for (var i = 0; i < files.length; i++) {
          if (files[i].name === Board.state.memoryActiveFile) {
            toSelect = files[i].name;
            break;
          }
        }
      }
      if (!toSelect && files.length > 0) {
        toSelect = files[0].name;
      }
      if (toSelect) M.selectMemoryFile(toSelect);
    });
  };

  M.renderMemoryLayout = function() {
    return (
      '<div class="memory-sidebar">' +
        '<div class="memory-sidebar-header">' +
          '<span class="memory-sidebar-title">Memory Files</span>' +
          '<button class="memory-new-btn" id="memory-new-btn">+ New</button>' +
        '</div>' +
        '<div class="memory-file-list" id="memory-file-list"></div>' +
      '</div>' +
      '<div class="memory-resize-handle"></div>' +
      '<div class="memory-editor">' +
        '<div class="memory-toolbar" id="memory-toolbar">' +
          '<span class="memory-toolbar-filename" id="memory-toolbar-filename">No file selected</span>' +
          '<span class="memory-toolbar-dirty" id="memory-toolbar-dirty">Unsaved</span>' +
          '<button class="memory-toolbar-btn" id="memory-btn-preview" title="Edit mode">Edit</button>' +
          '<button class="memory-toolbar-btn" id="memory-btn-save" title="Save (Ctrl+S)" disabled>Save</button>' +
          '<button class="memory-toolbar-btn danger" id="memory-btn-delete" title="Delete file" disabled>Delete</button>' +
        '</div>' +
        '<div class="memory-edit-area" id="memory-edit-area">' +
          '<textarea class="memory-textarea" id="memory-textarea" placeholder="Select a file to edit..." disabled></textarea>' +
          '<div class="memory-preview md-body" id="memory-preview"></div>' +
        '</div>' +
      '</div>'
    );
  };

  M.renderMemoryEmptyState = function() {
    return (
      '<div class="memory-empty">' +
        '<div class="memory-empty-icon">&#128221;</div>' +
        '<div class="memory-empty-text">No memory files found</div>' +
        '<div class="memory-empty-sub">Memory directory is empty or does not exist yet.</div>' +
        '<button class="memory-new-btn" id="memory-empty-new-btn" style="margin-top:8px">+ Create First File</button>' +
      '</div>'
    );
  };

  // Memory GC 마이그레이션 후 type/archive 카테고리 그루핑.
  // MEMORY.md 는 별도 최상단, 그 외는 (user / feedback / project / reference / archive/*) 순.
  var MEMORY_CATEGORY_ORDER = [
    "flat",
    "user",
    "feedback",
    "project",
    "reference",
    "archive/merged",
    "archive/synthesized",
    "archive/stale",
  ];
  var MEMORY_CATEGORY_LABELS = {
    "flat": "Uncategorized",
    "user": "User",
    "feedback": "Feedback",
    "project": "Project",
    "reference": "Reference",
    "archive/merged": "Archive · Merged",
    "archive/synthesized": "Archive · Synthesized",
    "archive/stale": "Archive · Stale",
  };

  function _basename(p) {
    var idx = p.lastIndexOf("/");
    return idx >= 0 ? p.substring(idx + 1) : p;
  }

  function _renderMemoryItem(f) {
    var isActive = f.name === Board.state.memoryActiveFile;
    var classes = "memory-file-item";
    if (isActive) classes += " active";
    if (f.isIndex) classes += " is-index";
    var icon = f.isIndex ? "&#9733;" : "&#128196;";
    var sizeStr = M.formatFileSize(f.size);
    var displayName = f.isIndex ? f.name : _basename(f.name);
    return (
      '<div class="' + classes + '" data-name="' + esc(f.name) + '">' +
        '<span class="memory-file-item-icon">' + icon + '</span>' +
        '<div class="memory-file-item-info">' +
          '<div class="memory-file-item-name">' + esc(displayName) + '</div>' +
          '<div class="memory-file-item-meta">' + sizeStr + ' &middot; ' + esc(f.mtime || "") + '</div>' +
        '</div>' +
        '<span class="memory-file-item-dirty"></span>' +
      '</div>'
    );
  }

  M.renderMemorySidebar = function() {
    var list = document.getElementById("memory-file-list");
    if (!list) return;

    var files = Board.state.memoryFiles || [];
    var indexFile = null;
    var groups = {};
    for (var i = 0; i < files.length; i++) {
      var f = files[i];
      if (f.isIndex) { indexFile = f; continue; }
      var cat = f.category || "flat";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(f);
    }

    var html = "";
    if (indexFile) {
      // MEMORY.md 는 카테고리 헤더 없이 단독 노출
      html += '<div class="memory-cat-group is-index">' + _renderMemoryItem(indexFile) + '</div>';
    }

    var seen = {};
    for (var c = 0; c < MEMORY_CATEGORY_ORDER.length; c++) {
      var cat = MEMORY_CATEGORY_ORDER[c];
      seen[cat] = true;
      var catFiles = groups[cat];
      if (!catFiles || catFiles.length === 0) continue;
      html += _renderMemoryCategoryGroup(cat, catFiles);
    }
    // 예약 외 카테고리 (있으면)
    for (var ck in groups) {
      if (seen[ck]) continue;
      html += _renderMemoryCategoryGroup(ck, groups[ck]);
    }

    list.innerHTML = html;

    var items = list.querySelectorAll(".memory-file-item");
    for (var j = 0; j < items.length; j++) {
      items[j].addEventListener("click", M.onMemoryFileItemClick);
    }
  };

  function _renderMemoryCategoryGroup(cat, catFiles) {
    var label = MEMORY_CATEGORY_LABELS[cat] || cat;
    var inner = "";
    for (var k = 0; k < catFiles.length; k++) {
      inner += _renderMemoryItem(catFiles[k]);
    }
    return (
      '<div class="memory-cat-group" data-category="' + esc(cat) + '">' +
        '<div class="memory-cat-header">' +
          '<span class="memory-cat-label">' + esc(label) + '</span>' +
          '<span class="memory-cat-count">' + catFiles.length + '</span>' +
        '</div>' +
        inner +
      '</div>'
    );
  }

  M.onMemoryFileItemClick = function(e) {
    var item = e.currentTarget;
    var name = item.dataset.name;
    if (!name || name === Board.state.memoryActiveFile) return;

    if (Board.state.memoryDirty) {
      if (!confirm("Unsaved changes will be lost. Continue?")) return;
    }
    M.selectMemoryFile(name);
  };

  M.selectMemoryFile = function(name) {
    Board.state.memoryActiveFile = name;
    Board.state.memoryDirty = false;
    Board.state.memoryPreview = true;
    M.persistContexts();

    var list = document.getElementById("memory-file-list");
    if (list) {
      var items = list.querySelectorAll(".memory-file-item");
      for (var i = 0; i < items.length; i++) {
        items[i].classList.toggle("active", items[i].dataset.name === name);
      }
    }

    M.fetchMemoryFile(name).then(function (data) {
      if (!data) {
        M.showMemoryEditorError("Failed to load file: " + name);
        return;
      }

      Board.state.memoryOriginalContent = data.content;

      var textarea = document.getElementById("memory-textarea");
      var preview = document.getElementById("memory-preview");
      var filenameEl = document.getElementById("memory-toolbar-filename");
      var saveBtn = document.getElementById("memory-btn-save");
      var deleteBtn = document.getElementById("memory-btn-delete");
      var previewBtn = document.getElementById("memory-btn-preview");
      var dirtyEl = document.getElementById("memory-toolbar-dirty");

      if (textarea) { textarea.value = data.content; textarea.disabled = false; textarea.classList.add("hidden"); }
      if (preview) {
        preview.innerHTML = Board.render.renderMd(data.content);
        preview.classList.add("visible");
        Board.render.initHighlight();
        Board.render.initMermaid();
      }
      if (filenameEl) filenameEl.textContent = data.name;
      if (saveBtn) saveBtn.disabled = true;
      if (deleteBtn) {
        var isIndex = false;
        for (var i = 0; i < Board.state.memoryFiles.length; i++) {
          if (Board.state.memoryFiles[i].name === name && Board.state.memoryFiles[i].isIndex) {
            isIndex = true;
            break;
          }
        }
        deleteBtn.disabled = isIndex;
        deleteBtn.title = isIndex ? "Cannot delete index file" : "Delete file";
      }
      if (previewBtn) { previewBtn.textContent = "Edit"; previewBtn.classList.remove("active"); }
      if (dirtyEl) dirtyEl.classList.remove("visible");
    });
  };

  M.showMemoryEditorError = function(msg) {
    var textarea = document.getElementById("memory-textarea");
    if (textarea) { textarea.value = msg; textarea.disabled = true; }
  };

  M.bindMemoryToolbar = function() {
    var textarea = document.getElementById("memory-textarea");
    var saveBtn = document.getElementById("memory-btn-save");
    var deleteBtn = document.getElementById("memory-btn-delete");
    var previewBtn = document.getElementById("memory-btn-preview");
    var newBtn = document.getElementById("memory-new-btn");

    if (textarea) {
      textarea.addEventListener("input", function () {
        var isDirty = textarea.value !== Board.state.memoryOriginalContent;
        M.setMemoryDirty(isDirty);
      });
    }
    if (saveBtn) saveBtn.addEventListener("click", M.doMemorySave);
    if (deleteBtn) deleteBtn.addEventListener("click", M.doMemoryDelete);
    if (previewBtn) previewBtn.addEventListener("click", M.toggleMemoryPreview);
    if (newBtn) newBtn.addEventListener("click", M.doMemoryNewFile);
  };

  M.bindMemoryEmptyNewBtn = function(container) {
    var btn = container.querySelector("#memory-empty-new-btn");
    if (btn) btn.addEventListener("click", M.doMemoryNewFile);
  };

  M.bindMemoryKeyboard = function() {
    var textarea = document.getElementById("memory-textarea");
    if (!textarea) return;

    textarea.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (Board.state.memoryDirty) M.doMemorySave();
      }
      if (e.key === "Tab") {
        e.preventDefault();
        var start = textarea.selectionStart;
        var end = textarea.selectionEnd;
        textarea.value = textarea.value.substring(0, start) + "  " + textarea.value.substring(end);
        textarea.selectionStart = textarea.selectionEnd = start + 2;
        textarea.dispatchEvent(new Event("input"));
      }
    });
  };

  M.setMemoryDirty = function(isDirty) {
    Board.state.memoryDirty = isDirty;
    var saveBtn = document.getElementById("memory-btn-save");
    var dirtyEl = document.getElementById("memory-toolbar-dirty");
    if (saveBtn) saveBtn.disabled = !isDirty;
    if (dirtyEl) dirtyEl.classList.toggle("visible", isDirty);
  };

  M.doMemorySave = function() {
    var name = Board.state.memoryActiveFile;
    if (!name) return;

    var textarea = document.getElementById("memory-textarea");
    if (!textarea) return;

    var content = textarea.value;
    var saveBtn = document.getElementById("memory-btn-save");
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }

    M.saveMemoryFile(name, content).then(function (result) {
      if (saveBtn) saveBtn.textContent = "Save";
      if (result && result.ok) {
        Board.state.memoryOriginalContent = content;
        M.setMemoryDirty(false);
        M.refreshMemoryFileList();
      } else {
        if (saveBtn) saveBtn.disabled = false;
        alert("Failed to save file.");
      }
    });
  };

  M.doMemoryDelete = function() {
    var name = Board.state.memoryActiveFile;
    if (!name) return;
    if (!confirm('Delete "' + name + '"? This cannot be undone.')) return;

    M.deleteMemoryFile(name).then(function (result) {
      if (result && result.ok) {
        Board.state.memoryActiveFile = null;
        Board.state.memoryDirty = false;
        M.persistContexts();
        M.renderSubMemory();
      } else {
        alert("Failed to delete file.");
      }
    });
  };

  M.doMemoryNewFile = function() {
    var filename = prompt("Enter new file name (without .md extension):");
    if (!filename) return;
    filename = filename.trim().replace(/\s+/g, "-");
    if (!filename) return;
    if (!filename.endsWith(".md")) filename += ".md";

    for (var i = 0; i < Board.state.memoryFiles.length; i++) {
      if (Board.state.memoryFiles[i].name === filename) {
        alert('File "' + filename + '" already exists.');
        return;
      }
    }

    M.saveMemoryFile(filename, "# " + filename.replace(/\.md$/, "") + "\n\n").then(function (result) {
      if (result && result.ok) {
        Board.state.memoryActiveFile = result.name;
        Board.state.memoryDirty = false;
        M.persistContexts();
        M.renderSubMemory();
      } else {
        alert("Failed to create file.");
      }
    });
  };

  M.toggleMemoryPreview = function() {
    Board.state.memoryPreview = !Board.state.memoryPreview;
    var preview = document.getElementById("memory-preview");
    var textarea = document.getElementById("memory-textarea");
    var previewBtn = document.getElementById("memory-btn-preview");

    if (Board.state.memoryPreview) {
      // Preview mode: show preview, hide textarea, button says "Edit"
      var content = textarea ? textarea.value : "";
      if (preview) {
        preview.innerHTML = Board.render.renderMd(content);
        preview.classList.add("visible");
        Board.render.initHighlight();
        Board.render.initMermaid();
      }
      if (textarea) textarea.classList.add("hidden");
      if (previewBtn) { previewBtn.textContent = "Edit"; previewBtn.classList.remove("active"); }
    } else {
      // Edit mode: show textarea, hide preview, button says "Preview"
      if (preview) { preview.classList.remove("visible"); preview.innerHTML = ""; }
      if (textarea) { textarea.classList.remove("hidden"); textarea.focus(); }
      if (previewBtn) { previewBtn.textContent = "Preview"; previewBtn.classList.add("active"); }
    }
  };

  M.refreshMemoryFileList = function() {
    M.fetchMemoryList().then(function (files) {
      Board.state.memoryFiles = files;
      M.renderMemorySidebar();
    });
  };

  // ═══════════════════════════════════════════════════════════════════
  // SSE Refresh (called from sse.js)
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Refreshes memory data on external changes.
   * Called by SSE event listener when memory files change externally.
   * Only refreshes if Memory sub-tab is active within the Prompt tab.
   */
  M.refreshMemory = function() {
    if (Board.state.activeTab !== "memory") return;

    // Only auto-refresh Memory sub-tab content
    if (Board.state.promptSubTab !== "memory") return;

    M.fetchMemoryList().then(function (files) {
      Board.state.memoryFiles = files;
      M.renderMemorySidebar();

      if (Board.state.memoryActiveFile) {
        var found = false;
        for (var i = 0; i < files.length; i++) {
          if (files[i].name === Board.state.memoryActiveFile) {
            found = true;
            break;
          }
        }
        if (!found) {
          Board.state.memoryActiveFile = null;
          Board.state.memoryDirty = false;
          M.persistContexts();
          M.renderSubMemory();
          return;
        }

        if (!Board.state.memoryDirty) {
          M.fetchMemoryFile(Board.state.memoryActiveFile).then(function (data) {
            if (!data) return;
            Board.state.memoryOriginalContent = data.content;
            var textarea = document.getElementById("memory-textarea");
            if (textarea && !Board.state.memoryDirty) {
              textarea.value = data.content;
            }
            if (Board.state.memoryPreview) {
              var preview = document.getElementById("memory-preview");
              if (preview) {
                preview.innerHTML = Board.render.renderMd(data.content);
                Board.render.initHighlight();
                Board.render.initMermaid();
              }
            }
          });
        }
      }
    });
  };

  Board.render.refreshMemory = M.refreshMemory;

})();
