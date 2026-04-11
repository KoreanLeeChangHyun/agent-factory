/**
 * @module prompt
 *
 * Board SPA Prompt unified management tab module.
 *
 * Provides a 4-area sub-tab view (Rules | Prompt | CLAUDE.md | Memory)
 * for managing Claude Code configuration files via Board API endpoints.
 *
 * Sub-tabs:
 *   - Rules:    .claude/rules/ directory files (via flow-claude-edit)
 *   - Prompt:   .claude.workflow/prompt/ directory files
 *   - CLAUDE.md: single-file editor for project root CLAUDE.md
 *   - Memory:   ~/.claude/projects/.../memory/ files (original memory tab)
 *
 * Features:
 *   - File list sidebar with categorized grouping (Rules)
 *   - Markdown/code editor with syntax-aware textarea
 *   - Markdown preview toggle (using Board.render.renderMd)
 *   - Ctrl+S save shortcut
 *   - Unsaved change detection with confirmation prompts
 *   - File create / delete operations
 *   - Dirty check on sub-tab transitions
 *
 * Depends on: common.js (Board.state, Board.util, Board.render, Board.fetch)
 */
"use strict";

(function () {
  var esc = Board.util.esc;

  // ── State: Prompt tab (shared) ──
  Board.state.promptSubTab = "claudemd"; // "rules" | "prompt" | "claudemd" | "memory"

  // ── State: Rules sub-tab ──
  Board.state.promptRulesFiles = [];
  Board.state.promptRulesActiveFile = null;
  Board.state.promptRulesDirty = false;
  Board.state.promptRulesPreview = false;
  Board.state.promptRulesOriginalContent = "";

  // ── State: Prompt sub-tab ──
  Board.state.promptPromptFiles = [];
  Board.state.promptPromptActiveFile = null;
  Board.state.promptPromptDirty = false;
  Board.state.promptPromptPreview = false;
  Board.state.promptPromptOriginalContent = "";

  // ── State: CLAUDE.md sub-tab ──
  Board.state.promptClaudeMdContent = "";
  Board.state.promptClaudeMdDirty = false;
  Board.state.promptClaudeMdPreview = false;
  Board.state.promptClaudeMdOriginalContent = "";

  // ── State: Memory sub-tab (existing) ──
  Board.state.memoryFiles = [];
  Board.state.memoryActiveFile = null;
  Board.state.memoryDirty = false;
  Board.state.memoryPreview = false;
  Board.state.memoryOriginalContent = "";

  // ═══════════════════════════════════════════════════════════════════
  // Fetch Functions
  // ═══════════════════════════════════════════════════════════════════

  // ── Memory API ──

  function fetchMemoryList() {
    return fetch("/api/memory", { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : []; })
      .catch(function () { return []; });
  }

  function fetchMemoryFile(name) {
    return fetch("/api/memory/file?name=" + encodeURIComponent(name), { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; });
  }

  function saveMemoryFile(name, content) {
    return fetch("/api/memory/file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, content: content }),
    }).then(function (res) { return res.json(); })
      .catch(function () { return null; });
  }

  function deleteMemoryFile(name) {
    return fetch("/api/memory/file?name=" + encodeURIComponent(name), { method: "DELETE" })
      .then(function (res) { return res.json(); })
      .catch(function () { return null; });
  }

  Board.fetch.fetchMemoryList = fetchMemoryList;
  Board.fetch.fetchMemoryFile = fetchMemoryFile;

  // ── Rules API ──

  function fetchRulesList() {
    return fetch("/api/prompt/rules", { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : []; })
      .catch(function () { return []; });
  }

  function fetchRulesFile(path) {
    return fetch("/api/prompt/rules/file?path=" + encodeURIComponent(path), { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; });
  }

  function saveRulesFile(path, content) {
    return fetch("/api/prompt/rules/file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path, content: content }),
    }).then(function (res) { return res.json(); })
      .catch(function () { return null; });
  }

  function deleteRulesFile(path) {
    return fetch("/api/prompt/rules/file?path=" + encodeURIComponent(path), { method: "DELETE" })
      .then(function (res) { return res.json(); })
      .catch(function () { return null; });
  }

  // ── Prompt Files API ──

  function fetchPromptList() {
    return fetch("/api/prompt/prompt-files", { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : []; })
      .catch(function () { return []; });
  }

  function fetchPromptFile(name) {
    return fetch("/api/prompt/prompt-files/file?name=" + encodeURIComponent(name), { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; });
  }

  function savePromptFile(name, content) {
    return fetch("/api/prompt/prompt-files/file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, content: content }),
    }).then(function (res) { return res.json(); })
      .catch(function () { return null; });
  }

  function deletePromptFile(name) {
    return fetch("/api/prompt/prompt-files/file?name=" + encodeURIComponent(name), { method: "DELETE" })
      .then(function (res) { return res.json(); })
      .catch(function () { return null; });
  }

  // ── CLAUDE.md API ──

  function fetchClaudeMd() {
    return fetch("/api/prompt/claude-md", { cache: "no-store" })
      .then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; });
  }

  function saveClaudeMd(content) {
    return fetch("/api/prompt/claude-md", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: content }),
    }).then(function (res) { return res.json(); })
      .catch(function () { return null; });
  }

  // ═══════════════════════════════════════════════════════════════════
  // Shared Helpers
  // ═══════════════════════════════════════════════════════════════════

  function formatFileSize(bytes) {
    if (bytes == null) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  /**
   * Returns true if the currently active sub-tab has unsaved changes.
   */
  function isCurrentSubTabDirty() {
    var sub = Board.state.promptSubTab;
    if (sub === "rules") return Board.state.promptRulesDirty;
    if (sub === "prompt") return Board.state.promptPromptDirty;
    if (sub === "claudemd") return Board.state.promptClaudeMdDirty;
    if (sub === "memory") return Board.state.memoryDirty;
    return false;
  }

  // ═══════════════════════════════════════════════════════════════════
  // Main Render: renderPrompt (replaces renderMemory)
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Renders the complete Prompt tab UI.
   * Builds the sub-tab bar and delegates to the active sub-tab renderer.
   */
  function renderPrompt() {
    var container = document.getElementById("view-memory");
    if (!container) return;

    // Build wrapper -> sub-tab bar + content area
    // Uses .prompt-view-wrapper (flex column) inside #view-memory (flex row)
    container.innerHTML =
      '<div class="prompt-view-wrapper">' +
        '<div class="prompt-subtab-bar">' +
          renderSubTabButton("claudemd", "CLAUDE.md") +
          renderSubTabButton("rules", "Rules") +
          renderSubTabButton("memory", "Memory") +
          renderSubTabButton("prompt", "Prompt") +
        '</div>' +
        '<div class="prompt-subtab-content" id="prompt-content"></div>' +
      '</div>';

    // Bind sub-tab click handlers
    var btns = container.querySelectorAll(".prompt-subtab");
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener("click", onSubTabClick);
    }

    // Render active sub-tab content
    renderActiveSubTab();
  }

  function renderSubTabButton(key, label) {
    var active = Board.state.promptSubTab === key ? " active" : "";
    return '<button class="prompt-subtab' + active + '" data-subtab="' + key + '">' + esc(label) + '</button>';
  }

  function onSubTabClick(e) {
    var target = e.currentTarget.dataset.subtab;
    if (!target || target === Board.state.promptSubTab) return;

    // Dirty check before switching
    if (isCurrentSubTabDirty()) {
      if (!confirm("Unsaved changes will be lost. Continue?")) return;
      // Reset dirty state of the tab being left
      resetDirtyState(Board.state.promptSubTab);
    }

    Board.state.promptSubTab = target;

    // Update sub-tab bar active state
    var bar = document.querySelector(".prompt-subtab-bar");
    if (bar) {
      var btns = bar.querySelectorAll(".prompt-subtab");
      for (var i = 0; i < btns.length; i++) {
        btns[i].classList.toggle("active", btns[i].dataset.subtab === target);
      }
    }

    renderActiveSubTab();
  }

  function resetDirtyState(subTab) {
    if (subTab === "rules") Board.state.promptRulesDirty = false;
    else if (subTab === "prompt") Board.state.promptPromptDirty = false;
    else if (subTab === "claudemd") Board.state.promptClaudeMdDirty = false;
    else if (subTab === "memory") Board.state.memoryDirty = false;
  }

  function renderActiveSubTab() {
    var sub = Board.state.promptSubTab;
    if (sub === "rules") renderSubRules();
    else if (sub === "prompt") renderSubPromptFiles();
    else if (sub === "claudemd") renderSubClaudeMd();
    else if (sub === "memory") renderSubMemory();
  }

  // Compatibility: Board.render.renderMemory = renderPrompt
  Board.render.renderMemory = renderPrompt;

  // ═══════════════════════════════════════════════════════════════════
  // Resize Handle
  // ═══════════════════════════════════════════════════════════════════

  function bindResizeHandle(container) {
    var handle = container.querySelector(".memory-resize-handle");
    if (!handle) return;
    var sidebar = container.querySelector(".memory-sidebar");
    if (!sidebar) return;

    handle.addEventListener("mousedown", function (e) {
      e.preventDefault();
      handle.classList.add("dragging");
      var startX = e.clientX;
      var startW = sidebar.offsetWidth;

      function onMove(ev) {
        var w = startW + (ev.clientX - startX);
        if (w < 140) w = 140;
        if (w > 600) w = 600;
        sidebar.style.width = w + "px";
        sidebar.style.minWidth = w + "px";
      }
      function onUp() {
        handle.classList.remove("dragging");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      }
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  }

  // ═══════════════════════════════════════════════════════════════════
  // Sub-tab: Rules
  // ═══════════════════════════════════════════════════════════════════

  function renderSubRules() {
    var content = document.getElementById("prompt-content");
    if (!content) return;

    fetchRulesList().then(function (files) {
      Board.state.promptRulesFiles = files;

      if (!files || files.length === 0) {
        content.innerHTML = renderRulesEmptyState();
        bindRulesEmptyNewBtn(content);
        return;
      }

      content.innerHTML = renderRulesLayout();
      bindResizeHandle(content);
      renderRulesSidebar();
      bindRulesToolbar();
      bindRulesKeyboard();

      // Auto-select file
      var toSelect = null;
      if (Board.state.promptRulesActiveFile) {
        for (var i = 0; i < files.length; i++) {
          if (files[i].path === Board.state.promptRulesActiveFile) {
            toSelect = files[i].path;
            break;
          }
        }
      }
      if (!toSelect && files.length > 0) {
        toSelect = files[0].path;
      }
      if (toSelect) selectRulesFile(toSelect);
    });
  }

  function renderRulesLayout() {
    return (
      '<div class="memory-sidebar">' +
        '<div class="memory-sidebar-header">' +
          '<span class="memory-sidebar-title">Rules Files</span>' +
          '<button class="memory-new-btn" id="rules-new-btn">+ New</button>' +
        '</div>' +
        '<div class="memory-file-list" id="rules-file-list"></div>' +
      '</div>' +
      '<div class="memory-resize-handle"></div>' +
      '<div class="memory-editor">' +
        '<div class="memory-toolbar" id="rules-toolbar">' +
          '<span class="memory-toolbar-filename" id="rules-toolbar-filename">No file selected</span>' +
          '<span class="memory-toolbar-dirty" id="rules-toolbar-dirty">Unsaved</span>' +
          '<button class="memory-toolbar-btn" id="rules-btn-preview" title="Edit mode">Edit</button>' +
          '<button class="memory-toolbar-btn" id="rules-btn-save" title="Save (Ctrl+S)" disabled>Save</button>' +
          '<button class="memory-toolbar-btn danger" id="rules-btn-delete" title="Delete file" disabled>Delete</button>' +
        '</div>' +
        '<div class="memory-edit-area" id="rules-edit-area">' +
          '<textarea class="memory-textarea" id="rules-textarea" placeholder="Select a file to edit..." disabled></textarea>' +
          '<div class="memory-preview md-body" id="rules-preview"></div>' +
        '</div>' +
      '</div>'
    );
  }

  function renderRulesEmptyState() {
    return (
      '<div class="memory-empty">' +
        '<div class="memory-empty-icon">&#128220;</div>' +
        '<div class="memory-empty-text">No rules files found</div>' +
        '<div class="memory-empty-sub">.claude/rules/ directory is empty.</div>' +
        '<button class="memory-new-btn" id="rules-empty-new-btn" style="margin-top:8px">+ Create First Rule</button>' +
      '</div>'
    );
  }

  function renderRulesSidebar() {
    var list = document.getElementById("rules-file-list");
    if (!list) return;

    var files = Board.state.promptRulesFiles;

    // Group by category
    var categories = {};
    for (var i = 0; i < files.length; i++) {
      var f = files[i];
      var cat = f.category || "other";
      if (!categories[cat]) categories[cat] = [];
      categories[cat].push(f);
    }

    var html = "";
    var catOrder = ["workflow", "project"];
    // Add any remaining categories not in the order
    for (var c in categories) {
      if (catOrder.indexOf(c) === -1) catOrder.push(c);
    }

    for (var ci = 0; ci < catOrder.length; ci++) {
      var catKey = catOrder[ci];
      var catFiles = categories[catKey];
      if (!catFiles || catFiles.length === 0) continue;

      var catLabel = catKey.charAt(0).toUpperCase() + catKey.slice(1);
      html +=
        '<div class="prompt-category-group" data-category="' + esc(catKey) + '">' +
          '<div class="prompt-category-header">' +
            '<span class="prompt-category-icon">&#9660;</span>' +
            '<span class="prompt-category-label">' + esc(catLabel) + '</span>' +
            '<span class="prompt-category-count">' + catFiles.length + '</span>' +
          '</div>' +
          '<div class="prompt-category-files">';

      for (var fi = 0; fi < catFiles.length; fi++) {
        var file = catFiles[fi];
        var isActive = file.path === Board.state.promptRulesActiveFile;
        var classes = "memory-file-item";
        if (isActive) classes += " active";
        var sizeStr = formatFileSize(file.size);

        html +=
          '<div class="' + classes + '" data-path="' + esc(file.path) + '">' +
            '<span class="memory-file-item-icon">&#128196;</span>' +
            '<div class="memory-file-item-info">' +
              '<div class="memory-file-item-name">' + esc(file.name) + '</div>' +
              '<div class="memory-file-item-meta">' + sizeStr + ' &middot; ' + esc(file.mtime || "") + '</div>' +
            '</div>' +
            '<span class="memory-file-item-dirty"></span>' +
          '</div>';
      }

      html += '</div></div>';
    }

    list.innerHTML = html;

    // Bind file item clicks
    var items = list.querySelectorAll(".memory-file-item");
    for (var j = 0; j < items.length; j++) {
      items[j].addEventListener("click", function (e) {
        var item = e.currentTarget;
        var path = item.dataset.path;
        if (!path || path === Board.state.promptRulesActiveFile) return;
        if (Board.state.promptRulesDirty) {
          if (!confirm("Unsaved changes will be lost. Continue?")) return;
        }
        selectRulesFile(path);
      });
    }

    // Bind category header toggle
    var headers = list.querySelectorAll(".prompt-category-header");
    for (var h = 0; h < headers.length; h++) {
      headers[h].addEventListener("click", function (e) {
        var group = e.currentTarget.parentElement;
        if (group) group.classList.toggle("collapsed");
      });
    }
  }

  function selectRulesFile(path) {
    Board.state.promptRulesActiveFile = path;
    Board.state.promptRulesDirty = false;
    Board.state.promptRulesPreview = true;

    // Update sidebar active state
    var list = document.getElementById("rules-file-list");
    if (list) {
      var items = list.querySelectorAll(".memory-file-item");
      for (var i = 0; i < items.length; i++) {
        items[i].classList.toggle("active", items[i].dataset.path === path);
      }
    }

    fetchRulesFile(path).then(function (data) {
      if (!data) {
        showRulesEditorError("Failed to load file: " + path);
        return;
      }
      Board.state.promptRulesOriginalContent = data.content;

      var textarea = document.getElementById("rules-textarea");
      var preview = document.getElementById("rules-preview");
      var filenameEl = document.getElementById("rules-toolbar-filename");
      var saveBtn = document.getElementById("rules-btn-save");
      var deleteBtn = document.getElementById("rules-btn-delete");
      var previewBtn = document.getElementById("rules-btn-preview");
      var dirtyEl = document.getElementById("rules-toolbar-dirty");

      if (textarea) { textarea.value = data.content; textarea.disabled = false; textarea.classList.add("hidden"); }
      if (preview) {
        preview.innerHTML = Board.render.renderMd(data.content);
        preview.classList.add("visible");
        Board.render.initHighlight();
        Board.render.initMermaid();
      }
      if (filenameEl) filenameEl.textContent = data.path || data.name;
      if (saveBtn) saveBtn.disabled = true;
      if (deleteBtn) deleteBtn.disabled = false;
      if (previewBtn) { previewBtn.textContent = "Edit"; previewBtn.classList.remove("active"); }
      if (dirtyEl) dirtyEl.classList.remove("visible");
    });
  }

  function showRulesEditorError(msg) {
    var textarea = document.getElementById("rules-textarea");
    if (textarea) { textarea.value = msg; textarea.disabled = true; }
  }

  function bindRulesToolbar() {
    var textarea = document.getElementById("rules-textarea");
    var saveBtn = document.getElementById("rules-btn-save");
    var deleteBtn = document.getElementById("rules-btn-delete");
    var previewBtn = document.getElementById("rules-btn-preview");
    var newBtn = document.getElementById("rules-new-btn");

    if (textarea) {
      textarea.addEventListener("input", function () {
        var isDirty = textarea.value !== Board.state.promptRulesOriginalContent;
        setRulesDirty(isDirty);
      });
    }
    if (saveBtn) saveBtn.addEventListener("click", doRulesSave);
    if (deleteBtn) deleteBtn.addEventListener("click", doRulesDelete);
    if (previewBtn) previewBtn.addEventListener("click", toggleRulesPreview);
    if (newBtn) newBtn.addEventListener("click", doRulesNewFile);
  }

  function bindRulesEmptyNewBtn(container) {
    var btn = container.querySelector("#rules-empty-new-btn");
    if (btn) btn.addEventListener("click", doRulesNewFile);
  }

  function bindRulesKeyboard() {
    var textarea = document.getElementById("rules-textarea");
    if (!textarea) return;
    textarea.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (Board.state.promptRulesDirty) doRulesSave();
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
  }

  function setRulesDirty(isDirty) {
    Board.state.promptRulesDirty = isDirty;
    var saveBtn = document.getElementById("rules-btn-save");
    var dirtyEl = document.getElementById("rules-toolbar-dirty");
    if (saveBtn) saveBtn.disabled = !isDirty;
    if (dirtyEl) dirtyEl.classList.toggle("visible", isDirty);
  }

  function doRulesSave() {
    var path = Board.state.promptRulesActiveFile;
    if (!path) return;
    var textarea = document.getElementById("rules-textarea");
    if (!textarea) return;
    var content = textarea.value;
    var saveBtn = document.getElementById("rules-btn-save");
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }

    saveRulesFile(path, content).then(function (result) {
      if (saveBtn) saveBtn.textContent = "Save";
      if (result && result.ok) {
        Board.state.promptRulesOriginalContent = content;
        setRulesDirty(false);
        refreshRulesFileList();
      } else {
        if (saveBtn) saveBtn.disabled = false;
        alert("Failed to save file." + (result && result.error ? " " + result.error : ""));
      }
    });
  }

  function doRulesDelete() {
    var path = Board.state.promptRulesActiveFile;
    if (!path) return;
    if (!confirm('Delete "' + path + '"? This cannot be undone.')) return;

    deleteRulesFile(path).then(function (result) {
      if (result && result.ok) {
        Board.state.promptRulesActiveFile = null;
        Board.state.promptRulesDirty = false;
        renderSubRules();
      } else {
        alert("Failed to delete file." + (result && result.error ? " " + result.error : ""));
      }
    });
  }

  function doRulesNewFile() {
    // Category selection
    var category = prompt("Select category (type 'workflow' or 'project'):", "project");
    if (!category) return;
    category = category.trim().toLowerCase();
    if (category !== "workflow" && category !== "project") {
      alert("Category must be 'workflow' or 'project'.");
      return;
    }

    var filename = prompt("Enter new file name (without .md extension):");
    if (!filename) return;
    filename = filename.trim().replace(/\s+/g, "-");
    if (!filename) return;
    if (!filename.endsWith(".md")) filename += ".md";

    var relPath = category + "/" + filename;

    // Check for duplicate
    for (var i = 0; i < Board.state.promptRulesFiles.length; i++) {
      if (Board.state.promptRulesFiles[i].path === relPath) {
        alert('File "' + relPath + '" already exists.');
        return;
      }
    }

    saveRulesFile(relPath, "# " + filename.replace(/\.md$/, "") + "\n\n").then(function (result) {
      if (result && result.ok) {
        Board.state.promptRulesActiveFile = relPath;
        Board.state.promptRulesDirty = false;
        renderSubRules();
      } else {
        alert("Failed to create file." + (result && result.error ? " " + result.error : ""));
      }
    });
  }

  function toggleRulesPreview() {
    Board.state.promptRulesPreview = !Board.state.promptRulesPreview;
    var preview = document.getElementById("rules-preview");
    var textarea = document.getElementById("rules-textarea");
    var previewBtn = document.getElementById("rules-btn-preview");

    if (Board.state.promptRulesPreview) {
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
  }

  function refreshRulesFileList() {
    fetchRulesList().then(function (files) {
      Board.state.promptRulesFiles = files;
      renderRulesSidebar();
    });
  }

  // ═══════════════════════════════════════════════════════════════════
  // Sub-tab: Prompt Files
  // ═══════════════════════════════════════════════════════════════════

  function renderSubPromptFiles() {
    var content = document.getElementById("prompt-content");
    if (!content) return;

    fetchPromptList().then(function (files) {
      Board.state.promptPromptFiles = files;

      if (!files || files.length === 0) {
        content.innerHTML = renderPromptFilesEmptyState();
        bindPromptFilesEmptyNewBtn(content);
        return;
      }

      content.innerHTML = renderPromptFilesLayout();
      bindResizeHandle(content);
      renderPromptFilesSidebar();
      bindPromptFilesToolbar();
      bindPromptFilesKeyboard();

      // Auto-select file
      var toSelect = null;
      if (Board.state.promptPromptActiveFile) {
        for (var i = 0; i < files.length; i++) {
          if (files[i].name === Board.state.promptPromptActiveFile) {
            toSelect = files[i].name;
            break;
          }
        }
      }
      if (!toSelect && files.length > 0) {
        toSelect = files[0].name;
      }
      if (toSelect) selectPromptFile(toSelect);
    });
  }

  function renderPromptFilesLayout() {
    return (
      '<div class="memory-sidebar">' +
        '<div class="memory-sidebar-header">' +
          '<span class="memory-sidebar-title">Prompt Files</span>' +
          '<button class="memory-new-btn" id="prompt-new-btn">+ New</button>' +
        '</div>' +
        '<div class="memory-file-list" id="prompt-file-list"></div>' +
      '</div>' +
      '<div class="memory-resize-handle"></div>' +
      '<div class="memory-editor">' +
        '<div class="memory-toolbar" id="prompt-toolbar">' +
          '<span class="memory-toolbar-filename" id="prompt-toolbar-filename">No file selected</span>' +
          '<span class="memory-toolbar-dirty" id="prompt-toolbar-dirty">Unsaved</span>' +
          '<button class="memory-toolbar-btn" id="prompt-btn-preview" title="Edit mode">Edit</button>' +
          '<button class="memory-toolbar-btn" id="prompt-btn-save" title="Save (Ctrl+S)" disabled>Save</button>' +
          '<button class="memory-toolbar-btn danger" id="prompt-btn-delete" title="Delete file" disabled>Delete</button>' +
        '</div>' +
        '<div class="memory-edit-area" id="prompt-edit-area">' +
          '<textarea class="memory-textarea" id="prompt-textarea" placeholder="Select a file to edit..." disabled></textarea>' +
          '<div class="memory-preview md-body" id="prompt-preview"></div>' +
        '</div>' +
      '</div>'
    );
  }

  function renderPromptFilesEmptyState() {
    return (
      '<div class="memory-empty">' +
        '<div class="memory-empty-icon">&#128196;</div>' +
        '<div class="memory-empty-text">No prompt files found</div>' +
        '<div class="memory-empty-sub">.claude.workflow/prompt/ directory is empty.</div>' +
        '<button class="memory-new-btn" id="prompt-empty-new-btn" style="margin-top:8px">+ Create First File</button>' +
      '</div>'
    );
  }

  function renderPromptFilesSidebar() {
    var list = document.getElementById("prompt-file-list");
    if (!list) return;

    var html = "";
    var files = Board.state.promptPromptFiles;
    for (var i = 0; i < files.length; i++) {
      var f = files[i];
      var isActive = f.name === Board.state.promptPromptActiveFile;
      var classes = "memory-file-item";
      if (isActive) classes += " active";
      var sizeStr = formatFileSize(f.size);

      html +=
        '<div class="' + classes + '" data-name="' + esc(f.name) + '">' +
          '<span class="memory-file-item-icon">&#128196;</span>' +
          '<div class="memory-file-item-info">' +
            '<div class="memory-file-item-name">' + esc(f.name) + '</div>' +
            '<div class="memory-file-item-meta">' + sizeStr + ' &middot; ' + esc(f.mtime || "") + '</div>' +
          '</div>' +
          '<span class="memory-file-item-dirty"></span>' +
        '</div>';
    }

    list.innerHTML = html;

    var items = list.querySelectorAll(".memory-file-item");
    for (var j = 0; j < items.length; j++) {
      items[j].addEventListener("click", function (e) {
        var item = e.currentTarget;
        var name = item.dataset.name;
        if (!name || name === Board.state.promptPromptActiveFile) return;
        if (Board.state.promptPromptDirty) {
          if (!confirm("Unsaved changes will be lost. Continue?")) return;
        }
        selectPromptFile(name);
      });
    }
  }

  function selectPromptFile(name) {
    Board.state.promptPromptActiveFile = name;
    Board.state.promptPromptDirty = false;
    Board.state.promptPromptPreview = true;

    var list = document.getElementById("prompt-file-list");
    if (list) {
      var items = list.querySelectorAll(".memory-file-item");
      for (var i = 0; i < items.length; i++) {
        items[i].classList.toggle("active", items[i].dataset.name === name);
      }
    }

    fetchPromptFile(name).then(function (data) {
      if (!data) {
        showPromptFilesEditorError("Failed to load file: " + name);
        return;
      }
      Board.state.promptPromptOriginalContent = data.content;

      var textarea = document.getElementById("prompt-textarea");
      var preview = document.getElementById("prompt-preview");
      var filenameEl = document.getElementById("prompt-toolbar-filename");
      var saveBtn = document.getElementById("prompt-btn-save");
      var deleteBtn = document.getElementById("prompt-btn-delete");
      var previewBtn = document.getElementById("prompt-btn-preview");
      var dirtyEl = document.getElementById("prompt-toolbar-dirty");

      var isCodeFile = /\.(py|xml)$/i.test(name);
      if (textarea) { textarea.value = data.content; textarea.disabled = false; textarea.classList.add("hidden"); }
      if (preview) {
        if (isCodeFile) {
          preview.innerHTML = buildPromptCodeViewer(name, data.content);
          bindPromptCodeViewer(preview);
        } else {
          preview.innerHTML = Board.render.renderMd(data.content);
          Board.render.initHighlight();
          Board.render.initMermaid();
        }
        preview.classList.add("visible");
      }
      if (filenameEl) filenameEl.textContent = data.name;
      if (saveBtn) saveBtn.disabled = true;
      if (deleteBtn) deleteBtn.disabled = false;
      if (previewBtn) {
        previewBtn.textContent = "Edit";
        previewBtn.classList.remove("active");
        previewBtn.dataset.codeFile = isCodeFile ? "1" : "";
      }
      if (dirtyEl) dirtyEl.classList.remove("visible");
    });
  }

  function showPromptFilesEditorError(msg) {
    var textarea = document.getElementById("prompt-textarea");
    if (textarea) { textarea.value = msg; textarea.disabled = true; }
  }

  function bindPromptFilesToolbar() {
    var textarea = document.getElementById("prompt-textarea");
    var saveBtn = document.getElementById("prompt-btn-save");
    var deleteBtn = document.getElementById("prompt-btn-delete");
    var previewBtn = document.getElementById("prompt-btn-preview");
    var newBtn = document.getElementById("prompt-new-btn");

    if (textarea) {
      textarea.addEventListener("input", function () {
        var isDirty = textarea.value !== Board.state.promptPromptOriginalContent;
        setPromptFilesDirty(isDirty);
      });
    }
    if (saveBtn) saveBtn.addEventListener("click", doPromptFilesSave);
    if (deleteBtn) deleteBtn.addEventListener("click", doPromptFilesDelete);
    if (previewBtn) previewBtn.addEventListener("click", togglePromptFilesPreview);
    if (newBtn) newBtn.addEventListener("click", doPromptFilesNewFile);
  }

  function bindPromptFilesEmptyNewBtn(container) {
    var btn = container.querySelector("#prompt-empty-new-btn");
    if (btn) btn.addEventListener("click", doPromptFilesNewFile);
  }

  function bindPromptFilesKeyboard() {
    var textarea = document.getElementById("prompt-textarea");
    if (!textarea) return;
    textarea.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (Board.state.promptPromptDirty) doPromptFilesSave();
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
  }

  function setPromptFilesDirty(isDirty) {
    Board.state.promptPromptDirty = isDirty;
    var saveBtn = document.getElementById("prompt-btn-save");
    var dirtyEl = document.getElementById("prompt-toolbar-dirty");
    if (saveBtn) saveBtn.disabled = !isDirty;
    if (dirtyEl) dirtyEl.classList.toggle("visible", isDirty);
  }

  function doPromptFilesSave() {
    var name = Board.state.promptPromptActiveFile;
    if (!name) return;
    var textarea = document.getElementById("prompt-textarea");
    if (!textarea) return;
    var content = textarea.value;
    var saveBtn = document.getElementById("prompt-btn-save");
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }

    savePromptFile(name, content).then(function (result) {
      if (saveBtn) saveBtn.textContent = "Save";
      if (result && result.ok) {
        Board.state.promptPromptOriginalContent = content;
        setPromptFilesDirty(false);
        refreshPromptFilesList();
      } else {
        if (saveBtn) saveBtn.disabled = false;
        alert("Failed to save file.");
      }
    });
  }

  function doPromptFilesDelete() {
    var name = Board.state.promptPromptActiveFile;
    if (!name) return;
    if (!confirm('Delete "' + name + '"? This cannot be undone.')) return;

    deletePromptFile(name).then(function (result) {
      if (result && result.ok) {
        Board.state.promptPromptActiveFile = null;
        Board.state.promptPromptDirty = false;
        renderSubPromptFiles();
      } else {
        alert("Failed to delete file.");
      }
    });
  }

  function doPromptFilesNewFile() {
    var filename = prompt("Enter new file name (with extension, e.g. my-prompt.txt):");
    if (!filename) return;
    filename = filename.trim().replace(/\s+/g, "-");
    if (!filename) return;

    // Check for duplicate
    for (var i = 0; i < Board.state.promptPromptFiles.length; i++) {
      if (Board.state.promptPromptFiles[i].name === filename) {
        alert('File "' + filename + '" already exists.');
        return;
      }
    }

    savePromptFile(filename, "").then(function (result) {
      if (result && result.ok) {
        Board.state.promptPromptActiveFile = result.name || filename;
        Board.state.promptPromptDirty = false;
        renderSubPromptFiles();
      } else {
        alert("Failed to create file.");
      }
    });
  }

  function togglePromptFilesPreview() {
    Board.state.promptPromptPreview = !Board.state.promptPromptPreview;
    var preview = document.getElementById("prompt-preview");
    var textarea = document.getElementById("prompt-textarea");
    var previewBtn = document.getElementById("prompt-btn-preview");
    var activeFile = Board.state.promptPromptActiveFile || "";
    var isCodeFile = /\.(py|xml)$/i.test(activeFile);

    if (Board.state.promptPromptPreview) {
      // Preview mode: show preview, hide textarea, button says "Edit"
      var content = textarea ? textarea.value : "";
      if (preview) {
        if (isCodeFile) {
          preview.innerHTML = buildPromptCodeViewer(activeFile, content);
          bindPromptCodeViewer(preview);
        } else {
          preview.innerHTML = Board.render.renderMd(content);
          Board.render.initHighlight();
          Board.render.initMermaid();
        }
        preview.classList.add("visible");
      }
      if (textarea) textarea.classList.add("hidden");
      if (previewBtn) { previewBtn.textContent = "Edit"; previewBtn.classList.remove("active"); }
    } else {
      // Edit mode: show textarea, hide preview, button says "Preview"
      if (preview) { preview.classList.remove("visible"); preview.innerHTML = ""; }
      if (textarea) { textarea.classList.remove("hidden"); textarea.focus(); }
      if (previewBtn) { previewBtn.textContent = "Preview"; previewBtn.classList.add("active"); }
    }
  }

  // ── Prompt code-viewer helpers ──

  function buildPromptCodeViewer(filename, content) {
    var lang = Board.util.getHighlightLang(filename);
    var lines = content.split("\n");
    var lineCount = lines.length;
    if (lineCount > 0 && lines[lineCount - 1] === "") {
      lines = lines.slice(0, lineCount - 1);
      lineCount = lines.length;
    }
    var numWidth = String(lineCount).length;
    var rows = lines.map(function (line, i) {
      var num = String(i + 1);
      while (num.length < numWidth) num = " " + num;
      return '<span class="code-line-number">' + esc(num) + '</span><span class="code-line-content">' + esc(line) + '</span>';
    });
    var viewerId = "cv-" + (++Board.state.codeViewerIdCounter);
    Board.state.codeViewerStore[viewerId] = {
      pendingRows: [],
      allLines: lines,
      nextChunk: lineCount,
      searchMatches: [],
      searchIndex: -1,
      lang: lang,
    };
    var searchBarHtml = '<div class="code-search-bar" style="display:none">'
      + '<input class="code-search-input" type="text" placeholder="Search..." />'
      + '<span class="code-search-count"></span>'
      + '<button class="code-search-nav-btn" data-dir="prev">&#9650;</button>'
      + '<button class="code-search-nav-btn" data-dir="next">&#9660;</button>'
      + '<button class="code-search-close-btn">&times;</button>'
      + '</div>';
    return '<div class="code-viewer" data-viewer-id="' + viewerId + '">'
      + '<button class="code-copy-btn">Copy</button>'
      + searchBarHtml
      + '<pre><code class="hljs-pending language-' + esc(lang) + '">'
      + rows.join("\n")
      + '</code></pre></div>';
  }

  function bindPromptCodeViewer(container) {
    // Copy button
    container.querySelectorAll(".code-copy-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var viewer = btn.closest(".code-viewer");
        if (!viewer) return;
        var lineContents = viewer.querySelectorAll(".code-line-content");
        var text = Array.prototype.map.call(lineContents, function (span) {
          return span.textContent;
        }).join("\n");
        navigator.clipboard.writeText(text).then(function () {
          var original = btn.textContent;
          btn.textContent = "Copied!";
          setTimeout(function () { btn.textContent = original; }, 1500);
        }).catch(function () {
          btn.textContent = "Error";
          setTimeout(function () { btn.textContent = "Copy"; }, 1500);
        });
      });
    });
    Board.render.initHighlight();
  }

  function refreshPromptFilesList() {
    fetchPromptList().then(function (files) {
      Board.state.promptPromptFiles = files;
      renderPromptFilesSidebar();
    });
  }

  // ═══════════════════════════════════════════════════════════════════
  // Sub-tab: CLAUDE.md
  // ═══════════════════════════════════════════════════════════════════

  function renderSubClaudeMd() {
    var content = document.getElementById("prompt-content");
    if (!content) return;

    fetchClaudeMd().then(function (data) {
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

      content.innerHTML = renderClaudeMdLayout();
      bindClaudeMdToolbar();
      bindClaudeMdKeyboard();

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
      if (filenameEl) filenameEl.textContent = "CLAUDE.md (" + formatFileSize(data.size) + ")";
    });
  }

  function renderClaudeMdLayout() {
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
  }

  function bindClaudeMdToolbar() {
    var textarea = document.getElementById("claudemd-textarea");
    var saveBtn = document.getElementById("claudemd-btn-save");
    var previewBtn = document.getElementById("claudemd-btn-preview");

    if (textarea) {
      textarea.addEventListener("input", function () {
        var isDirty = textarea.value !== Board.state.promptClaudeMdOriginalContent;
        setClaudeMdDirty(isDirty);
      });
    }
    if (saveBtn) saveBtn.addEventListener("click", doClaudeMdSave);
    if (previewBtn) previewBtn.addEventListener("click", toggleClaudeMdPreview);
  }

  function bindClaudeMdKeyboard() {
    var textarea = document.getElementById("claudemd-textarea");
    if (!textarea) return;
    textarea.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (Board.state.promptClaudeMdDirty) doClaudeMdSave();
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
  }

  function setClaudeMdDirty(isDirty) {
    Board.state.promptClaudeMdDirty = isDirty;
    var saveBtn = document.getElementById("claudemd-btn-save");
    var dirtyEl = document.getElementById("claudemd-toolbar-dirty");
    if (saveBtn) saveBtn.disabled = !isDirty;
    if (dirtyEl) dirtyEl.classList.toggle("visible", isDirty);
  }

  function doClaudeMdSave() {
    var textarea = document.getElementById("claudemd-textarea");
    if (!textarea) return;
    var content = textarea.value;
    var saveBtn = document.getElementById("claudemd-btn-save");
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }

    saveClaudeMd(content).then(function (result) {
      if (saveBtn) saveBtn.textContent = "Save";
      if (result && result.ok) {
        Board.state.promptClaudeMdOriginalContent = content;
        Board.state.promptClaudeMdContent = content;
        setClaudeMdDirty(false);
      } else {
        if (saveBtn) saveBtn.disabled = false;
        alert("Failed to save CLAUDE.md.");
      }
    });
  }

  function toggleClaudeMdPreview() {
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
  }

  // ═══════════════════════════════════════════════════════════════════
  // Sub-tab: Memory (existing logic preserved)
  // ═══════════════════════════════════════════════════════════════════

  function renderSubMemory() {
    var content = document.getElementById("prompt-content");
    if (!content) return;

    fetchMemoryList().then(function (files) {
      Board.state.memoryFiles = files;

      if (!files || files.length === 0) {
        content.innerHTML = renderMemoryEmptyState();
        bindMemoryEmptyNewBtn(content);
        return;
      }

      content.innerHTML = renderMemoryLayout();
      bindResizeHandle(content);
      renderMemorySidebar();
      bindMemoryToolbar();
      bindMemoryKeyboard();

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
      if (toSelect) selectMemoryFile(toSelect);
    });
  }

  function renderMemoryLayout() {
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
  }

  function renderMemoryEmptyState() {
    return (
      '<div class="memory-empty">' +
        '<div class="memory-empty-icon">&#128221;</div>' +
        '<div class="memory-empty-text">No memory files found</div>' +
        '<div class="memory-empty-sub">Memory directory is empty or does not exist yet.</div>' +
        '<button class="memory-new-btn" id="memory-empty-new-btn" style="margin-top:8px">+ Create First File</button>' +
      '</div>'
    );
  }

  function renderMemorySidebar() {
    var list = document.getElementById("memory-file-list");
    if (!list) return;

    var html = "";
    var files = Board.state.memoryFiles;
    for (var i = 0; i < files.length; i++) {
      var f = files[i];
      var isActive = f.name === Board.state.memoryActiveFile;
      var classes = "memory-file-item";
      if (isActive) classes += " active";
      if (f.isIndex) classes += " is-index";

      var icon = f.isIndex ? "&#9733;" : "&#128196;";
      var sizeStr = formatFileSize(f.size);

      html +=
        '<div class="' + classes + '" data-name="' + esc(f.name) + '">' +
          '<span class="memory-file-item-icon">' + icon + '</span>' +
          '<div class="memory-file-item-info">' +
            '<div class="memory-file-item-name">' + esc(f.name) + '</div>' +
            '<div class="memory-file-item-meta">' + sizeStr + ' &middot; ' + esc(f.mtime || "") + '</div>' +
          '</div>' +
          '<span class="memory-file-item-dirty"></span>' +
        '</div>';
    }

    list.innerHTML = html;

    var items = list.querySelectorAll(".memory-file-item");
    for (var j = 0; j < items.length; j++) {
      items[j].addEventListener("click", onMemoryFileItemClick);
    }
  }

  function onMemoryFileItemClick(e) {
    var item = e.currentTarget;
    var name = item.dataset.name;
    if (!name || name === Board.state.memoryActiveFile) return;

    if (Board.state.memoryDirty) {
      if (!confirm("Unsaved changes will be lost. Continue?")) return;
    }
    selectMemoryFile(name);
  }

  function selectMemoryFile(name) {
    Board.state.memoryActiveFile = name;
    Board.state.memoryDirty = false;
    Board.state.memoryPreview = true;

    var list = document.getElementById("memory-file-list");
    if (list) {
      var items = list.querySelectorAll(".memory-file-item");
      for (var i = 0; i < items.length; i++) {
        items[i].classList.toggle("active", items[i].dataset.name === name);
      }
    }

    fetchMemoryFile(name).then(function (data) {
      if (!data) {
        showMemoryEditorError("Failed to load file: " + name);
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
  }

  function showMemoryEditorError(msg) {
    var textarea = document.getElementById("memory-textarea");
    if (textarea) { textarea.value = msg; textarea.disabled = true; }
  }

  function bindMemoryToolbar() {
    var textarea = document.getElementById("memory-textarea");
    var saveBtn = document.getElementById("memory-btn-save");
    var deleteBtn = document.getElementById("memory-btn-delete");
    var previewBtn = document.getElementById("memory-btn-preview");
    var newBtn = document.getElementById("memory-new-btn");

    if (textarea) {
      textarea.addEventListener("input", function () {
        var isDirty = textarea.value !== Board.state.memoryOriginalContent;
        setMemoryDirty(isDirty);
      });
    }
    if (saveBtn) saveBtn.addEventListener("click", doMemorySave);
    if (deleteBtn) deleteBtn.addEventListener("click", doMemoryDelete);
    if (previewBtn) previewBtn.addEventListener("click", toggleMemoryPreview);
    if (newBtn) newBtn.addEventListener("click", doMemoryNewFile);
  }

  function bindMemoryEmptyNewBtn(container) {
    var btn = container.querySelector("#memory-empty-new-btn");
    if (btn) btn.addEventListener("click", doMemoryNewFile);
  }

  function bindMemoryKeyboard() {
    var textarea = document.getElementById("memory-textarea");
    if (!textarea) return;

    textarea.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (Board.state.memoryDirty) doMemorySave();
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
  }

  function setMemoryDirty(isDirty) {
    Board.state.memoryDirty = isDirty;
    var saveBtn = document.getElementById("memory-btn-save");
    var dirtyEl = document.getElementById("memory-toolbar-dirty");
    if (saveBtn) saveBtn.disabled = !isDirty;
    if (dirtyEl) dirtyEl.classList.toggle("visible", isDirty);
  }

  function doMemorySave() {
    var name = Board.state.memoryActiveFile;
    if (!name) return;

    var textarea = document.getElementById("memory-textarea");
    if (!textarea) return;

    var content = textarea.value;
    var saveBtn = document.getElementById("memory-btn-save");
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }

    saveMemoryFile(name, content).then(function (result) {
      if (saveBtn) saveBtn.textContent = "Save";
      if (result && result.ok) {
        Board.state.memoryOriginalContent = content;
        setMemoryDirty(false);
        refreshMemoryFileList();
      } else {
        if (saveBtn) saveBtn.disabled = false;
        alert("Failed to save file.");
      }
    });
  }

  function doMemoryDelete() {
    var name = Board.state.memoryActiveFile;
    if (!name) return;
    if (!confirm('Delete "' + name + '"? This cannot be undone.')) return;

    deleteMemoryFile(name).then(function (result) {
      if (result && result.ok) {
        Board.state.memoryActiveFile = null;
        Board.state.memoryDirty = false;
        renderSubMemory();
      } else {
        alert("Failed to delete file.");
      }
    });
  }

  function doMemoryNewFile() {
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

    saveMemoryFile(filename, "# " + filename.replace(/\.md$/, "") + "\n\n").then(function (result) {
      if (result && result.ok) {
        Board.state.memoryActiveFile = result.name;
        Board.state.memoryDirty = false;
        renderSubMemory();
      } else {
        alert("Failed to create file.");
      }
    });
  }

  function toggleMemoryPreview() {
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
  }

  function refreshMemoryFileList() {
    fetchMemoryList().then(function (files) {
      Board.state.memoryFiles = files;
      renderMemorySidebar();
    });
  }

  // ═══════════════════════════════════════════════════════════════════
  // SSE Refresh (called from sse.js)
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Refreshes memory data on external changes.
   * Called by SSE event listener when memory files change externally.
   * Only refreshes if Memory sub-tab is active within the Prompt tab.
   */
  function refreshMemory() {
    if (Board.state.activeTab !== "memory") return;

    // Only auto-refresh Memory sub-tab content
    if (Board.state.promptSubTab !== "memory") return;

    fetchMemoryList().then(function (files) {
      Board.state.memoryFiles = files;
      renderMemorySidebar();

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
          renderSubMemory();
          return;
        }

        if (!Board.state.memoryDirty) {
          fetchMemoryFile(Board.state.memoryActiveFile).then(function (data) {
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
  }

  Board.render.refreshMemory = refreshMemory;

})();
