/**
 * @module memory
 *
 * Board SPA Memory tab module.
 *
 * Provides CRUD operations for Claude Code auto memory files
 * (~/.claude/projects/.../memory/) via Board API endpoints.
 *
 * Features:
 *   - File list sidebar with MEMORY.md index highlight
 *   - Markdown editor with syntax-aware textarea
 *   - Markdown preview toggle (using Board.render.renderMd)
 *   - Ctrl+S save shortcut
 *   - Unsaved change detection with confirmation prompts
 *   - File create / delete operations
 *
 * Depends on: common.js (Board.state, Board.util, Board.render, Board.fetch)
 */
"use strict";

(function () {
  var esc = Board.util.esc;

  // ── State ──
  Board.state.memoryFiles = [];
  Board.state.memoryActiveFile = null;
  Board.state.memoryDirty = false;
  Board.state.memoryPreview = false;
  Board.state.memoryOriginalContent = "";

  // ── Fetch Functions ──

  /**
   * Fetches memory file list from server.
   * @returns {Promise<Array>} file list
   */
  function fetchMemoryList() {
    return fetch("/api/memory", { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) return [];
        return res.json();
      })
      .catch(function () { return []; });
  }

  /**
   * Fetches a single memory file content.
   * @param {string} name - filename
   * @returns {Promise<Object|null>} file data {name, content, size}
   */
  function fetchMemoryFile(name) {
    return fetch("/api/memory/file?name=" + encodeURIComponent(name), { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) return null;
        return res.json();
      })
      .catch(function () { return null; });
  }

  /**
   * Saves a memory file to server.
   * @param {string} name - filename
   * @param {string} content - file content
   * @returns {Promise<Object|null>} result {ok, name}
   */
  function saveMemoryFile(name, content) {
    return fetch("/api/memory/file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, content: content }),
    })
      .then(function (res) { return res.json(); })
      .catch(function () { return null; });
  }

  /**
   * Deletes a memory file from server.
   * @param {string} name - filename
   * @returns {Promise<Object|null>} result {ok}
   */
  function deleteMemoryFile(name) {
    return fetch("/api/memory/file?name=" + encodeURIComponent(name), {
      method: "DELETE",
    })
      .then(function (res) { return res.json(); })
      .catch(function () { return null; });
  }

  Board.fetch.fetchMemoryList = fetchMemoryList;
  Board.fetch.fetchMemoryFile = fetchMemoryFile;

  // ── Render ──

  /**
   * Renders the complete Memory tab UI.
   * Fetches file list and builds sidebar + editor layout.
   */
  function renderMemory() {
    var container = document.getElementById("view-memory");
    if (!container) return;

    fetchMemoryList().then(function (files) {
      Board.state.memoryFiles = files;

      // If no files, show empty state
      if (!files || files.length === 0) {
        container.innerHTML = renderEmptyState();
        bindEmptyNewBtn(container);
        return;
      }

      container.innerHTML = renderLayout();
      renderSidebar();
      bindToolbar();
      bindKeyboard();

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
      if (toSelect) {
        selectFile(toSelect);
      }
    });
  }

  Board.render.renderMemory = renderMemory;

  // ── Layout Templates ──

  function renderLayout() {
    return (
      '<div class="memory-sidebar">' +
        '<div class="memory-sidebar-header">' +
          '<span class="memory-sidebar-title">Memory Files</span>' +
          '<button class="memory-new-btn" id="memory-new-btn">+ New</button>' +
        '</div>' +
        '<div class="memory-file-list" id="memory-file-list"></div>' +
      '</div>' +
      '<div class="memory-editor">' +
        '<div class="memory-toolbar" id="memory-toolbar">' +
          '<span class="memory-toolbar-filename" id="memory-toolbar-filename">No file selected</span>' +
          '<span class="memory-toolbar-dirty" id="memory-toolbar-dirty">Unsaved</span>' +
          '<button class="memory-toolbar-btn" id="memory-btn-preview" title="Toggle Preview">Preview</button>' +
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

  function renderEmptyState() {
    return (
      '<div class="memory-empty">' +
        '<div class="memory-empty-icon">&#128221;</div>' +
        '<div class="memory-empty-text">No memory files found</div>' +
        '<div class="memory-empty-sub">Memory directory is empty or does not exist yet.</div>' +
        '<button class="memory-new-btn" id="memory-empty-new-btn" style="margin-top:8px">+ Create First File</button>' +
      '</div>'
    );
  }

  // ── Sidebar Rendering ──

  function renderSidebar() {
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

    // Bind click events
    var items = list.querySelectorAll(".memory-file-item");
    for (var j = 0; j < items.length; j++) {
      items[j].addEventListener("click", onFileItemClick);
    }
  }

  function onFileItemClick(e) {
    var item = e.currentTarget;
    var name = item.dataset.name;
    if (!name || name === Board.state.memoryActiveFile) return;

    if (Board.state.memoryDirty) {
      if (!confirm("Unsaved changes will be lost. Continue?")) return;
    }

    selectFile(name);
  }

  // ── File Selection ──

  function selectFile(name) {
    Board.state.memoryActiveFile = name;
    Board.state.memoryDirty = false;
    Board.state.memoryPreview = false;

    // Update sidebar active state
    var list = document.getElementById("memory-file-list");
    if (list) {
      var items = list.querySelectorAll(".memory-file-item");
      for (var i = 0; i < items.length; i++) {
        items[i].classList.toggle("active", items[i].dataset.name === name);
      }
    }

    // Fetch file content
    fetchMemoryFile(name).then(function (data) {
      if (!data) {
        showEditorError("Failed to load file: " + name);
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

      if (textarea) {
        textarea.value = data.content;
        textarea.disabled = false;
      }
      if (preview) {
        preview.innerHTML = "";
        preview.classList.remove("visible");
      }
      if (textarea) {
        textarea.classList.remove("hidden");
      }
      if (filenameEl) filenameEl.textContent = data.name;
      if (saveBtn) saveBtn.disabled = true;
      if (deleteBtn) {
        // Protect MEMORY.md from deletion
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
      if (previewBtn) previewBtn.classList.remove("active");
      if (dirtyEl) dirtyEl.classList.remove("visible");

      Board.state.memoryPreview = false;
    });
  }

  function showEditorError(msg) {
    var textarea = document.getElementById("memory-textarea");
    if (textarea) {
      textarea.value = msg;
      textarea.disabled = true;
    }
  }

  // ── Toolbar Bindings ──

  function bindToolbar() {
    var textarea = document.getElementById("memory-textarea");
    var saveBtn = document.getElementById("memory-btn-save");
    var deleteBtn = document.getElementById("memory-btn-delete");
    var previewBtn = document.getElementById("memory-btn-preview");
    var newBtn = document.getElementById("memory-new-btn");

    // Textarea input -> dirty detection
    if (textarea) {
      textarea.addEventListener("input", function () {
        var isDirty = textarea.value !== Board.state.memoryOriginalContent;
        setDirty(isDirty);
      });
    }

    // Save button
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        doSave();
      });
    }

    // Delete button
    if (deleteBtn) {
      deleteBtn.addEventListener("click", function () {
        doDelete();
      });
    }

    // Preview toggle
    if (previewBtn) {
      previewBtn.addEventListener("click", function () {
        togglePreview();
      });
    }

    // New file button
    if (newBtn) {
      newBtn.addEventListener("click", function () {
        doNewFile();
      });
    }
  }

  function bindEmptyNewBtn(container) {
    var btn = container.querySelector("#memory-empty-new-btn");
    if (btn) {
      btn.addEventListener("click", function () {
        doNewFile();
      });
    }
  }

  // ── Keyboard Shortcuts ──

  function bindKeyboard() {
    var textarea = document.getElementById("memory-textarea");
    if (!textarea) return;

    textarea.addEventListener("keydown", function (e) {
      // Ctrl+S / Cmd+S -> Save
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (Board.state.memoryDirty) doSave();
      }
      // Tab -> insert spaces
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

  // ── Actions ──

  function setDirty(isDirty) {
    Board.state.memoryDirty = isDirty;
    var saveBtn = document.getElementById("memory-btn-save");
    var dirtyEl = document.getElementById("memory-toolbar-dirty");
    if (saveBtn) saveBtn.disabled = !isDirty;
    if (dirtyEl) dirtyEl.classList.toggle("visible", isDirty);
  }

  function doSave() {
    var name = Board.state.memoryActiveFile;
    if (!name) return;

    var textarea = document.getElementById("memory-textarea");
    if (!textarea) return;

    var content = textarea.value;
    var saveBtn = document.getElementById("memory-btn-save");
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.textContent = "Saving...";
    }

    saveMemoryFile(name, content).then(function (result) {
      if (saveBtn) {
        saveBtn.textContent = "Save";
      }
      if (result && result.ok) {
        Board.state.memoryOriginalContent = content;
        setDirty(false);
        // Refresh file list to update size/mtime
        refreshFileList();
      } else {
        if (saveBtn) saveBtn.disabled = false;
        alert("Failed to save file.");
      }
    });
  }

  function doDelete() {
    var name = Board.state.memoryActiveFile;
    if (!name) return;

    if (!confirm('Delete "' + name + '"? This cannot be undone.')) return;

    deleteMemoryFile(name).then(function (result) {
      if (result && result.ok) {
        Board.state.memoryActiveFile = null;
        Board.state.memoryDirty = false;
        renderMemory();
      } else {
        alert("Failed to delete file.");
      }
    });
  }

  function doNewFile() {
    var filename = prompt("Enter new file name (without .md extension):");
    if (!filename) return;

    // Sanitize: trim, replace spaces with dashes
    filename = filename.trim().replace(/\s+/g, "-");
    if (!filename) return;

    // Ensure .md extension
    if (!filename.endsWith(".md")) filename += ".md";

    // Check for duplicate
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
        renderMemory();
      } else {
        alert("Failed to create file.");
      }
    });
  }

  function togglePreview() {
    Board.state.memoryPreview = !Board.state.memoryPreview;
    var preview = document.getElementById("memory-preview");
    var textarea = document.getElementById("memory-textarea");
    var previewBtn = document.getElementById("memory-btn-preview");

    if (Board.state.memoryPreview) {
      // Show preview
      var content = textarea ? textarea.value : "";
      if (preview) {
        preview.innerHTML = Board.render.renderMd(content);
        preview.classList.add("visible");
        Board.render.initHighlight();
        Board.render.initMermaid();
      }
      if (textarea) textarea.classList.add("hidden");
      if (previewBtn) previewBtn.classList.add("active");
    } else {
      // Show editor
      if (preview) {
        preview.classList.remove("visible");
        preview.innerHTML = "";
      }
      if (textarea) {
        textarea.classList.remove("hidden");
        textarea.focus();
      }
      if (previewBtn) previewBtn.classList.remove("active");
    }
  }

  // ── Helpers ──

  function refreshFileList() {
    fetchMemoryList().then(function (files) {
      Board.state.memoryFiles = files;
      renderSidebar();
    });
  }

  function formatFileSize(bytes) {
    if (bytes == null) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  // ── SSE Refresh (called from sse.js) ──

  /**
   * Refreshes memory data on external changes.
   * Called by SSE event listener when memory files change externally.
   */
  function refreshMemory() {
    // Only refresh if Memory tab is active
    if (Board.state.activeTab !== "memory") return;

    // If user has dirty changes, don't auto-refresh editor content
    fetchMemoryList().then(function (files) {
      Board.state.memoryFiles = files;
      renderSidebar();

      // If current file was deleted externally, clear editor
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
          renderMemory();
          return;
        }

        // If not dirty, refresh content too
        if (!Board.state.memoryDirty) {
          fetchMemoryFile(Board.state.memoryActiveFile).then(function (data) {
            if (!data) return;
            Board.state.memoryOriginalContent = data.content;
            var textarea = document.getElementById("memory-textarea");
            if (textarea && !Board.state.memoryDirty) {
              textarea.value = data.content;
            }
            // If preview is showing, refresh it
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
