/**
 * @module memory/memory-quick-prompts
 * Contexts > Quick Prompts sub-tab.
 *
 * The user sends prompt phrases from the UI trigger such as the memory button of the terminal header
 * Direct editing/replacement management interface. About Us
 * . agent-factory/board/config/quick-prompts.json
 */
"use strict";

(function () {
  var esc = Board.util.esc;
  var M = (Board._memory = Board._memory || {});

  M.renderSubQuickPrompts = function () {
    var content = document.getElementById("prompt-content");
    if (!content) return;

    content.innerHTML =
      '<div class="quick-prompts-container">' +
        '<div class="quick-prompts-header">' +
          '<div class="quick-prompts-title">Quick Prompts</div>' +
          '<div class="quick-prompts-subtitle">You can edit messages sent by UI triggers (Memory buttons, etc.). News /div>' +
        '</div>' +
        '<div class="quick-prompts-list" id="quick-prompts-list">' +
          '<div class="quick-prompts-loading">Loading…</div>' +
        '</div>' +
      '</div>';

    M.fetchQuickPrompts().then(function (data) {
      var items = (data && data.items) || [];
      Board.state.promptQuickItems = items.slice();
      Board.state.promptQuickDirtyById = {};
      Board.state.promptQuickOriginalById = {};
      for (var i = 0; i < items.length; i++) {
        var it = items[i];
        if (it && it.id) {
          Board.state.promptQuickOriginalById[it.id] = it.prompt || "";
        }
      }
      M.renderQuickPromptsList();
    });
  };

  M.renderQuickPromptsList = function () {
    var listEl = document.getElementById("quick-prompts-list");
    if (!listEl) return;

    var items = Board.state.promptQuickItems || [];
    if (items.length === 0) {
      listEl.innerHTML =
        '<div class="quick-prompts-empty">' +
          '<div class="quick-prompts-empty-text">No quick prompts defined.</div>' +
          '<div class="quick-prompts-empty-sub">.agent-factory/board/config/quick-prompts.json</div>' +
        '</div>';
      return;
    }

    var html = "";
    for (var i = 0; i < items.length; i++) {
      html += M.renderQuickPromptCard(items[i]);
    }
    listEl.innerHTML = html;

    M.bindQuickPromptCards(listEl);
  };

  M.renderQuickPromptCard = function (item) {
    if (!item || !item.id) return "";
    var id = item.id;
    var label = item.label || id;
    var prompt = item.prompt || "";
    var bindTo = item.bindTo || "";
    var description = item.description || "";

    return (
      '<div class="quick-prompt-card" data-quick-id="' + esc(id) + '">' +
        '<div class="quick-prompt-card-head">' +
          '<div class="quick-prompt-card-meta">' +
            '<span class="quick-prompt-card-label">' + esc(label) + '</span>' +
            '<code class="quick-prompt-card-id">' + esc(id) + '</code>' +
            (bindTo
              ? '<span class="quick-prompt-card-bind" title="bindTo">' + esc(bindTo) + '</span>'
              : '') +
          '</div>' +
          '<div class="quick-prompt-card-actions">' +
            '<span class="quick-prompt-card-dirty">Unsaved</span>' +
            '<button class="quick-prompt-card-save" data-action="save" disabled>Save</button>' +
            '<button class="quick-prompt-card-revert" data-action="revert" disabled>Revert</button>' +
          '</div>' +
        '</div>' +
        (description
          ? '<div class="quick-prompt-card-desc">' + esc(description) + '</div>'
          : '') +
        '<textarea class="quick-prompt-card-textarea" data-quick-input rows="4">' +
          esc(prompt) +
        '</textarea>' +
      '</div>'
    );
  };

  M.bindQuickPromptCards = function (root) {
    var cards = root.querySelectorAll(".quick-prompt-card");
    for (var i = 0; i < cards.length; i++) {
      (function (card) {
        var id = card.getAttribute("data-quick-id");
        var textarea = card.querySelector("[data-quick-input]");
        var saveBtn = card.querySelector('[data-action="save"]');
        var revertBtn = card.querySelector('[data-action="revert"]');

        if (textarea) {
          textarea.addEventListener("input", function () {
            var orig = Board.state.promptQuickOriginalById[id] || "";
            var dirty = textarea.value !== orig;
            M.setQuickPromptDirty(id, dirty);
          });
          textarea.addEventListener("keydown", function (e) {
            if ((e.ctrlKey || e.metaKey) && e.key === "s") {
              e.preventDefault();
              if (Board.state.promptQuickDirtyById[id]) {
                M.doQuickPromptSave(id);
              }
            }
          });
        }

        if (saveBtn) {
          saveBtn.addEventListener("click", function () {
            M.doQuickPromptSave(id);
          });
        }

        if (revertBtn) {
          revertBtn.addEventListener("click", function () {
            if (textarea) {
              textarea.value = Board.state.promptQuickOriginalById[id] || "";
            }
            M.setQuickPromptDirty(id, false);
          });
        }
      })(cards[i]);
    }
  };

  M.setQuickPromptDirty = function (id, isDirty) {
    Board.state.promptQuickDirtyById[id] = !!isDirty;
    var card = document.querySelector('.quick-prompt-card[data-quick-id="' + cssEsc(id) + '"]');
    if (!card) return;
    var saveBtn = card.querySelector('[data-action="save"]');
    var revertBtn = card.querySelector('[data-action="revert"]');
    var dirtyEl = card.querySelector(".quick-prompt-card-dirty");
    if (saveBtn) saveBtn.disabled = !isDirty;
    if (revertBtn) revertBtn.disabled = !isDirty;
    if (dirtyEl) dirtyEl.classList.toggle("visible", !!isDirty);
  };

  M.doQuickPromptSave = function (id) {
    var card = document.querySelector('.quick-prompt-card[data-quick-id="' + cssEsc(id) + '"]');
    if (!card) return;
    var textarea = card.querySelector("[data-quick-input]");
    if (!textarea) return;

    var saveBtn = card.querySelector('[data-action="save"]');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }

    var newPrompt = textarea.value;

    // to maintain different metafields (label, bindTo, description) of existing items
    // promptQuickItems from lookup. If not, it is considered new.
    var meta = null;
    var items = Board.state.promptQuickItems || [];
    for (var i = 0; i < items.length; i++) {
      if (items[i] && items[i].id === id) { meta = items[i]; break; }
    }

    var payload = { id: id, prompt: newPrompt };
    if (meta) {
      if (meta.label != null) payload.label = meta.label;
      if (meta.bindTo != null) payload.bindTo = meta.bindTo;
      if (meta.description != null) payload.description = meta.description;
    }

    M.saveQuickPrompt(payload).then(function (result) {
      if (saveBtn) saveBtn.textContent = "Save";
      if (result && result.ok) {
        Board.state.promptQuickOriginalById[id] = newPrompt;
        if (meta) meta.prompt = newPrompt;
        M.setQuickPromptDirty(id, false);
      } else {
        if (saveBtn) saveBtn.disabled = false;
        Board.util.showInfoModal("Store failure", "Failed to save quick prompt: " + id, { severity: "error" });
      }
    });
  };

  // id  escape — the default values are alphabet/numeric/.-
  // It is enough to handle simple, but it is safe to follow and escape.
  function cssEsc(s) {
    if (typeof s !== "string") return "";
    return s.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  }
})();
