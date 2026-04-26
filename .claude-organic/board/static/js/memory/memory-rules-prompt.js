/**
 * @module memory/memory-rules-prompt
 * Split from memory.js. Functions on Board._memory (M) namespace.
 * Contains: Rules sub-tab + Prompt Files sub-tab + modal logic.
 */
"use strict";

(function () {
  var esc = Board.util.esc;
  var M = (Board._memory = Board._memory || {});

  M.renderSubRules = function() {
    var content = document.getElementById("prompt-content");
    if (!content) return;

    M.fetchRulesList().then(function (files) {
      files = files || [];
      // CLAUDE.md 를 "project-meta" special 카테고리 첫 항목으로 prepend.
      // selectRulesFile / saveRulesFile / deleteRulesFile 가 path === "CLAUDE.md" 분기를 가지므로
      // 일반 rules 파일과 동일하게 처리된다.
      files.unshift({
        path: "CLAUDE.md",
        name: "CLAUDE.md",
        category: "project-meta",
        size: null,
        mtime: "",
      });
      Board.state.promptRulesFiles = files;

      // CLAUDE.md 만 있는 케이스(.claude/rules/ 비어있음)는 정상 — 빈 상태 표시 안 함.

      content.innerHTML = M.renderRulesLayout();
      M.bindResizeHandle(content, "rules");
      M.renderRulesSidebar();
      M.bindRulesToolbar();
      M.bindRulesKeyboard();

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
      if (toSelect) M.selectRulesFile(toSelect);
    });
  };

  M.renderRulesLayout = function() {
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
  };

  M.renderRulesEmptyState = function() {
    return (
      '<div class="memory-empty">' +
        '<div class="memory-empty-icon">&#128220;</div>' +
        '<div class="memory-empty-text">No rules files found</div>' +
        '<div class="memory-empty-sub">.claude/rules/ directory is empty.</div>' +
        '<button class="memory-new-btn" id="rules-empty-new-btn" style="margin-top:8px">+ Create First Rule</button>' +
      '</div>'
    );
  };

  M.renderRulesSidebar = function() {
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
    var catOrder = ["project-meta", "workflow", "project"];
    var catLabels = {
      "project-meta": "Project Meta",
      "workflow": "Workflow",
      "project": "Project",
    };
    // Add any remaining categories not in the order
    for (var c in categories) {
      if (catOrder.indexOf(c) === -1) catOrder.push(c);
    }

    for (var ci = 0; ci < catOrder.length; ci++) {
      var catKey = catOrder[ci];
      var catFiles = categories[catKey];
      if (!catFiles || catFiles.length === 0) continue;

      var catLabel = catLabels[catKey] || (catKey.charAt(0).toUpperCase() + catKey.slice(1));
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
        var sizeStr = M.formatFileSize(file.size);

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
        M.selectRulesFile(path);
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
  };

  M.selectRulesFile = function(path) {
    Board.state.promptRulesActiveFile = path;
    Board.state.promptRulesDirty = false;
    Board.state.promptRulesPreview = true;
    if (M.persistContexts) M.persistContexts();

    // Update sidebar active state
    var list = document.getElementById("rules-file-list");
    if (list) {
      var items = list.querySelectorAll(".memory-file-item");
      for (var i = 0; i < items.length; i++) {
        items[i].classList.toggle("active", items[i].dataset.path === path);
      }
    }

    M.fetchRulesFile(path).then(function (data) {
      if (!data) {
        M.showRulesEditorError("Failed to load file: " + path);
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
      // CLAUDE.md 는 시스템 진입점 파일이라 삭제 차단 — Project Meta 편입 후에도 불변.
      if (deleteBtn) deleteBtn.disabled = (path === "CLAUDE.md");
      if (previewBtn) { previewBtn.textContent = "Edit"; previewBtn.classList.remove("active"); }
      if (dirtyEl) dirtyEl.classList.remove("visible");
    });
  };

  M.showRulesEditorError = function(msg) {
    var textarea = document.getElementById("rules-textarea");
    if (textarea) { textarea.value = msg; textarea.disabled = true; }
  };

  M.bindRulesToolbar = function() {
    var textarea = document.getElementById("rules-textarea");
    var saveBtn = document.getElementById("rules-btn-save");
    var deleteBtn = document.getElementById("rules-btn-delete");
    var previewBtn = document.getElementById("rules-btn-preview");
    var newBtn = document.getElementById("rules-new-btn");

    if (textarea) {
      textarea.addEventListener("input", function () {
        var isDirty = textarea.value !== Board.state.promptRulesOriginalContent;
        M.setRulesDirty(isDirty);
      });
    }
    if (saveBtn) saveBtn.addEventListener("click", M.doRulesSave);
    if (deleteBtn) deleteBtn.addEventListener("click", M.doRulesDelete);
    if (previewBtn) previewBtn.addEventListener("click", M.toggleRulesPreview);
    if (newBtn) newBtn.addEventListener("click", M.doRulesNewFile);
  };

  M.bindRulesEmptyNewBtn = function(container) {
    var btn = container.querySelector("#rules-empty-new-btn");
    if (btn) btn.addEventListener("click", M.doRulesNewFile);
  };

  M.bindRulesKeyboard = function() {
    var textarea = document.getElementById("rules-textarea");
    if (!textarea) return;
    textarea.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (Board.state.promptRulesDirty) M.doRulesSave();
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

  M.setRulesDirty = function(isDirty) {
    Board.state.promptRulesDirty = isDirty;
    var saveBtn = document.getElementById("rules-btn-save");
    var dirtyEl = document.getElementById("rules-toolbar-dirty");
    if (saveBtn) saveBtn.disabled = !isDirty;
    if (dirtyEl) dirtyEl.classList.toggle("visible", isDirty);
  };

  M.doRulesSave = function() {
    var path = Board.state.promptRulesActiveFile;
    if (!path) return;
    var textarea = document.getElementById("rules-textarea");
    if (!textarea) return;
    var content = textarea.value;
    var saveBtn = document.getElementById("rules-btn-save");
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }

    M.saveRulesFile(path, content).then(function (result) {
      if (saveBtn) saveBtn.textContent = "Save";
      if (result && result.ok) {
        Board.state.promptRulesOriginalContent = content;
        M.setRulesDirty(false);
        M.refreshRulesFileList();
      } else {
        if (saveBtn) saveBtn.disabled = false;
        alert("Failed to save file." + (result && result.error ? " " + result.error : ""));
      }
    });
  };

  M.doRulesDelete = function() {
    var path = Board.state.promptRulesActiveFile;
    if (!path) return;
    if (!confirm('Delete "' + path + '"? This cannot be undone.')) return;

    M.deleteRulesFile(path).then(function (result) {
      if (result && result.ok) {
        Board.state.promptRulesActiveFile = null;
        Board.state.promptRulesDirty = false;
        if (M.persistContexts) M.persistContexts();
        M.renderSubRules();
      } else {
        alert("Failed to delete file." + (result && result.error ? " " + result.error : ""));
      }
    });
  };

  M.doRulesNewFile = function() {
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

    M.saveRulesFile(relPath, "# " + filename.replace(/\.md$/, "") + "\n\n").then(function (result) {
      if (result && result.ok) {
        Board.state.promptRulesActiveFile = relPath;
        Board.state.promptRulesDirty = false;
        if (M.persistContexts) M.persistContexts();
        M.renderSubRules();
      } else {
        alert("Failed to create file." + (result && result.error ? " " + result.error : ""));
      }
    });
  };

  M.toggleRulesPreview = function() {
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
  };

  M.refreshRulesFileList = function() {
    M.fetchRulesList().then(function (files) {
      Board.state.promptRulesFiles = files;
      M.renderRulesSidebar();
    });
  };

  // ═══════════════════════════════════════════════════════════════════
  // Sub-tab: Prompt Files
  // ═══════════════════════════════════════════════════════════════════


  M.renderSubPromptFiles = function() {
    var content = document.getElementById("prompt-content");
    if (!content) return;

    M.fetchPromptList().then(function (files) {
      Board.state.promptPromptFiles = files;

      if (!files || files.length === 0) {
        content.innerHTML = M.renderPromptFilesEmptyState();
        M.bindPromptFilesEmptyNewBtn(content);
        return;
      }

      content.innerHTML = M.renderPromptFilesLayout();
      M.bindResizeHandle(content, "prompt");
      M.renderPromptFilesSidebar();
      M.bindPromptFilesToolbar();
      M.bindPromptFilesKeyboard();

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
      if (toSelect) M.selectPromptFile(toSelect);
    });
  };

  M.renderPromptFilesLayout = function() {
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
  };

  M.renderPromptFilesEmptyState = function() {
    return (
      '<div class="memory-empty">' +
        '<div class="memory-empty-icon">&#128196;</div>' +
        '<div class="memory-empty-text">No prompt files found</div>' +
        '<div class="memory-empty-sub">.claude-organic/prompts/ directory is empty.</div>' +
        '<button class="memory-new-btn" id="prompt-empty-new-btn" style="margin-top:8px">+ Create First File</button>' +
      '</div>'
    );
  };

  M.renderPromptFilesSidebar = function() {
    var list = document.getElementById("prompt-file-list");
    if (!list) return;

    var html = "";
    var files = Board.state.promptPromptFiles;
    for (var i = 0; i < files.length; i++) {
      var f = files[i];
      var isActive = f.name === Board.state.promptPromptActiveFile;
      var classes = "memory-file-item";
      if (isActive) classes += " active";
      var sizeStr = M.formatFileSize(f.size);

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
        M.selectPromptFile(name);
      });
    }
  };

  M.selectPromptFile = function(name) {
    Board.state.promptPromptActiveFile = name;
    Board.state.promptPromptDirty = false;
    Board.state.promptPromptPreview = true;
    if (M.persistContexts) M.persistContexts();

    var list = document.getElementById("prompt-file-list");
    if (list) {
      var items = list.querySelectorAll(".memory-file-item");
      for (var i = 0; i < items.length; i++) {
        items[i].classList.toggle("active", items[i].dataset.name === name);
      }
    }

    M.fetchPromptFile(name).then(function (data) {
      if (!data) {
        M.showPromptFilesEditorError("Failed to load file: " + name);
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
          preview.innerHTML = M.buildPromptCodeViewer(name, data.content);
          M.bindPromptCodeViewer(preview);
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
  };

  M.showPromptFilesEditorError = function(msg) {
    var textarea = document.getElementById("prompt-textarea");
    if (textarea) { textarea.value = msg; textarea.disabled = true; }
  };

  M.bindPromptFilesToolbar = function() {
    var textarea = document.getElementById("prompt-textarea");
    var saveBtn = document.getElementById("prompt-btn-save");
    var deleteBtn = document.getElementById("prompt-btn-delete");
    var previewBtn = document.getElementById("prompt-btn-preview");
    var newBtn = document.getElementById("prompt-new-btn");

    if (textarea) {
      textarea.addEventListener("input", function () {
        var isDirty = textarea.value !== Board.state.promptPromptOriginalContent;
        M.setPromptFilesDirty(isDirty);
      });
    }
    if (saveBtn) saveBtn.addEventListener("click", M.doPromptFilesSave);
    if (deleteBtn) deleteBtn.addEventListener("click", M.doPromptFilesDelete);
    if (previewBtn) previewBtn.addEventListener("click", M.togglePromptFilesPreview);
    if (newBtn) newBtn.addEventListener("click", M.doPromptFilesNewFile);
  };

  M.bindPromptFilesEmptyNewBtn = function(container) {
    var btn = container.querySelector("#prompt-empty-new-btn");
    if (btn) btn.addEventListener("click", M.doPromptFilesNewFile);
  };

  M.bindPromptFilesKeyboard = function() {
    var textarea = document.getElementById("prompt-textarea");
    if (!textarea) return;
    textarea.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (Board.state.promptPromptDirty) M.doPromptFilesSave();
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

  M.setPromptFilesDirty = function(isDirty) {
    Board.state.promptPromptDirty = isDirty;
    var saveBtn = document.getElementById("prompt-btn-save");
    var dirtyEl = document.getElementById("prompt-toolbar-dirty");
    if (saveBtn) saveBtn.disabled = !isDirty;
    if (dirtyEl) dirtyEl.classList.toggle("visible", isDirty);
  };

  M.doPromptFilesSave = function() {
    var name = Board.state.promptPromptActiveFile;
    if (!name) return;
    var textarea = document.getElementById("prompt-textarea");
    if (!textarea) return;
    var content = textarea.value;
    var saveBtn = document.getElementById("prompt-btn-save");
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }

    M.savePromptFile(name, content).then(function (result) {
      if (saveBtn) saveBtn.textContent = "Save";
      if (result && result.ok) {
        Board.state.promptPromptOriginalContent = content;
        M.setPromptFilesDirty(false);
        M.refreshPromptFilesList();
      } else {
        if (saveBtn) saveBtn.disabled = false;
        alert("Failed to save file.");
      }
    });
  };

  M.doPromptFilesDelete = function() {
    var name = Board.state.promptPromptActiveFile;
    if (!name) return;
    if (!confirm('Delete "' + name + '"? This cannot be undone.')) return;

    M.deletePromptFile(name).then(function (result) {
      if (result && result.ok) {
        Board.state.promptPromptActiveFile = null;
        Board.state.promptPromptDirty = false;
        if (M.persistContexts) M.persistContexts();
        M.renderSubPromptFiles();
      } else {
        alert("Failed to delete file.");
      }
    });
  };

  M.doPromptFilesNewFile = function() {
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

    M.savePromptFile(filename, "").then(function (result) {
      if (result && result.ok) {
        Board.state.promptPromptActiveFile = result.name || filename;
        Board.state.promptPromptDirty = false;
        if (M.persistContexts) M.persistContexts();
        M.renderSubPromptFiles();
      } else {
        alert("Failed to create file.");
      }
    });
  };

  M.togglePromptFilesPreview = function() {
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
          preview.innerHTML = M.buildPromptCodeViewer(activeFile, content);
          M.bindPromptCodeViewer(preview);
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
  };

  // ── Prompt code-viewer helpers ──

  M.buildPromptCodeViewer = function(filename, content) {
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
  };

  M.bindPromptCodeViewer = function(container) {
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
  };

  M.refreshPromptFilesList = function() {
    M.fetchPromptList().then(function (files) {
      Board.state.promptPromptFiles = files;
      M.renderPromptFilesSidebar();
    });
  };

  // ═══════════════════════════════════════════════════════════════════
  // Sub-tab: CLAUDE.md
  // ═══════════════════════════════════════════════════════════════════
})();
