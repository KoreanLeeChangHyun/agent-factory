/**
 * @module terminal
 *
 * Board SPA terminal tab module.
 *
 * Provides a web-based terminal UI for interacting with Claude Code via
 * NDJSON stream-json protocol. Manages xterm.js terminal instance,
 * SSE event stream for real-time output, session lifecycle (start/kill),
 * and user input submission.
 *
 * Depends on: common.js (Board.state, Board.util, Board.render)
 */
"use strict";

(function () {
  var esc = Board.util.esc;

  // ── Constants ──
  var SSE_RECONNECT_INTERVAL = 3000;  // SSE reconnect delay (ms)
  var XTERM_CDN_CHECK_INTERVAL = 200; // xterm.js CDN load check interval (ms)
  var XTERM_CDN_MAX_WAIT = 10000;     // max wait for xterm.js CDN (ms)

  // ── State ──
  Board.state.termConnected = false;
  Board.state.termSessionId = null;
  Board.state.termStatus = "stopped"; // running | idle | stopped

  /** @type {Terminal|null} xterm.js instance */
  var term = null;
  /** @type {EventSource|null} SSE connection */
  var termEventSource = null;
  /** @type {number|null} SSE reconnect timer */
  var reconnectTimerId = null;
  /** @type {boolean} whether terminal tab has been rendered at least once */
  var termInitialized = false;
  /** @type {boolean} whether input is currently disabled (waiting for result) */
  var inputLocked = false;

  // ── Utility ──

  /**
   * Sends a POST request with JSON body to the given path.
   * @param {string} path - URL path (e.g. "/terminal/start")
   * @param {Object} [body] - JSON body to send
   * @returns {Promise<Object>} parsed JSON response
   */
  function postJson(path, body) {
    var opts = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    };
    if (body !== undefined) {
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (res) {
      if (!res.ok) {
        return res.json().then(function (err) {
          throw new Error(err.error || "Request failed: " + res.status);
        }).catch(function (parseErr) {
          if (parseErr.message && parseErr.message.indexOf("Request failed") === 0) throw parseErr;
          throw new Error("Request failed: " + res.status);
        });
      }
      return res.json();
    });
  }

  /**
   * Fetches current terminal status from the server.
   * @returns {Promise<void>}
   */
  function fetchStatus() {
    return fetch("/terminal/status", { cache: "no-store" }).then(function (res) {
      if (!res.ok) return;
      return res.json();
    }).then(function (data) {
      if (!data) return;
      Board.state.termStatus = data.status || "stopped";
      Board.state.termSessionId = data.session_id || null;
      updateControlBar();
    }).catch(function () {});
  }

  // ── xterm.js Management ──

  /**
   * Initializes the xterm.js terminal instance and attaches it to the DOM.
   * Waits for the CDN-loaded Terminal constructor if not yet available.
   * On re-render, disposes the old instance and creates a fresh one to avoid
   * stale DOM references from innerHTML replacement.
   * @param {HTMLElement} container - DOM element to attach the terminal to
   * @param {function} [callback] - called after terminal is ready
   */
  function initXterm(container, callback) {
    // Dispose previous instance since the container DOM was replaced by innerHTML
    if (term) {
      term.dispose();
      term = null;
    }

    function create() {
      term = new Terminal({
        convertEol: true,
        fontSize: 14,
        fontFamily: "'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace",
        theme: {
          background: "#1e1e1e",
          foreground: "#cccccc",
          cursor: "#569cd6",
          selectionBackground: "rgba(86,156,214,0.3)",
          black: "#1e1e1e",
          red: "#f44747",
          green: "#4ec9b0",
          yellow: "#dcdcaa",
          blue: "#569cd6",
          magenta: "#c586c0",
          cyan: "#9cdcfe",
          white: "#cccccc",
          brightBlack: "#858585",
          brightRed: "#f44747",
          brightGreen: "#4ec9b0",
          brightYellow: "#dcdcaa",
          brightBlue: "#569cd6",
          brightMagenta: "#c586c0",
          brightCyan: "#9cdcfe",
          brightWhite: "#ffffff",
        },
        cursorBlink: false,
        disableStdin: true,
        scrollback: 10000,
      });
      term.open(container);
      term.writeln("\x1b[90m-- Claude Code Terminal --\x1b[0m");
      term.writeln("\x1b[90mPress \"Start\" to begin a session.\x1b[0m");
      if (callback) callback();
    }

    // Wait for CDN-loaded Terminal constructor
    if (typeof Terminal !== "undefined") {
      create();
    } else {
      var elapsed = 0;
      var checkInterval = setInterval(function () {
        elapsed += XTERM_CDN_CHECK_INTERVAL;
        if (typeof Terminal !== "undefined") {
          clearInterval(checkInterval);
          create();
        } else if (elapsed >= XTERM_CDN_MAX_WAIT) {
          clearInterval(checkInterval);
          container.innerHTML = '<div class="empty" style="margin-top:32px;color:#f44747">'
            + 'Failed to load xterm.js from CDN. Check your network connection.</div>';
        }
      }, XTERM_CDN_CHECK_INTERVAL);
    }
  }

  /**
   * Disposes the xterm.js terminal instance and cleans up resources.
   */
  function disposeXterm() {
    if (term) {
      term.dispose();
      term = null;
    }
  }

  // ── SSE Connection ──

  /**
   * Connects to the terminal SSE event stream.
   * Handles stdout, result, system, and permission events.
   */
  function connectSSE() {
    disconnectSSE();

    termEventSource = new EventSource("/terminal/events");

    termEventSource.addEventListener("open", function () {
      Board.state.termConnected = true;
      updateControlBar();
    });

    termEventSource.addEventListener("stdout", function (e) {
      try {
        var data = JSON.parse(e.data);
        if (data.chunk && term) {
          term.write(data.chunk);
        }
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("result", function (e) {
      try {
        var data = JSON.parse(e.data);
        if (data.done) {
          if (term) {
            term.writeln("");
            term.writeln("\x1b[90m-- Response complete --\x1b[0m");
          }
          Board.state.termStatus = "idle";
          setInputLocked(false);
          updateControlBar();
        }
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("system", function (e) {
      try {
        var data = JSON.parse(e.data);
        if (data.subtype === "init" && data.session_id) {
          Board.state.termSessionId = data.session_id;
          Board.state.termStatus = "idle";
          if (term) {
            term.writeln("\x1b[32m-- Session started (ID: " + data.session_id.substring(0, 8) + "...) --\x1b[0m");
          }
          setInputLocked(false);
          updateControlBar();
        } else if (data.subtype === "process_exit") {
          Board.state.termStatus = "stopped";
          Board.state.termSessionId = null;
          if (term) {
            var exitCode = data.exit_code !== undefined ? data.exit_code : "unknown";
            if (exitCode === 0) {
              term.writeln("\x1b[90m-- Process exited normally --\x1b[0m");
            } else {
              term.writeln("\x1b[31m-- Process exited with code " + exitCode + " --\x1b[0m");
            }
          }
          setInputLocked(false);
          updateControlBar();
        }
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("permission", function (e) {
      try {
        var data = JSON.parse(e.data);
        if (term) {
          term.writeln("");
          term.writeln("\x1b[33m[Permission Request]\x1b[0m " + esc(data.description || "Tool use requested"));
        }
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("error", function (e) {
      try {
        var data = JSON.parse(e.data);
        if (term) {
          term.writeln("\x1b[31m[Error] " + esc(data.message || "Process error") + "\x1b[0m");
        }
        Board.state.termStatus = "stopped";
        Board.state.termSessionId = null;
        setInputLocked(false);
        updateControlBar();
      } catch (err) {
        // Ignore non-JSON error events
      }
    });

    termEventSource.onerror = function () {
      Board.state.termConnected = false;
      termEventSource.close();
      termEventSource = null;
      updateControlBar();

      // Schedule reconnection
      if (!reconnectTimerId) {
        reconnectTimerId = setTimeout(function () {
          reconnectTimerId = null;
          connectSSE();
        }, SSE_RECONNECT_INTERVAL);
      }
    };
  }

  /**
   * Disconnects the terminal SSE event stream.
   */
  function disconnectSSE() {
    if (reconnectTimerId) {
      clearTimeout(reconnectTimerId);
      reconnectTimerId = null;
    }
    if (termEventSource) {
      termEventSource.close();
      termEventSource = null;
    }
    Board.state.termConnected = false;
  }

  // ── Input Management ──

  /**
   * Sets the input locked state and updates the UI accordingly.
   * @param {boolean} locked - Whether input should be locked
   */
  function setInputLocked(locked) {
    inputLocked = locked;
    var input = document.getElementById("terminal-input");
    var sendBtn = document.getElementById("terminal-send-btn");
    if (input) {
      input.disabled = locked || Board.state.termStatus === "stopped";
      if (!locked && Board.state.termStatus !== "stopped") {
        input.focus();
      }
    }
    if (sendBtn) {
      sendBtn.disabled = locked || Board.state.termStatus === "stopped";
    }
  }

  /**
   * Sends user input text to the terminal server.
   */
  function sendInput() {
    var input = document.getElementById("terminal-input");
    if (!input) return;
    var text = input.value.trim();
    if (!text) return;
    if (inputLocked || Board.state.termStatus === "stopped") return;

    if (term) {
      term.writeln("");
      term.writeln("\x1b[36m> " + text + "\x1b[0m");
    }

    setInputLocked(true);
    Board.state.termStatus = "running";
    updateControlBar();
    input.value = "";

    postJson("/terminal/input", { text: text }).catch(function (err) {
      if (term) {
        term.writeln("\x1b[31m[Error] " + esc(err.message) + "\x1b[0m");
      }
      setInputLocked(false);
      Board.state.termStatus = "idle";
      updateControlBar();
    });
  }

  // ── Session Management ──

  /**
   * Starts a new Claude Code session.
   */
  function startSession() {
    if (Board.state.termStatus === "running") return;

    if (term) {
      term.clear();
      term.writeln("\x1b[90m-- Starting session... --\x1b[0m");
    }

    Board.state.termStatus = "running";
    updateControlBar();

    postJson("/terminal/start").then(function (data) {
      if (data.session_id) {
        Board.state.termSessionId = data.session_id;
      }
      // Actual status update will come via SSE system/init event
    }).catch(function (err) {
      if (term) {
        term.writeln("\x1b[31m[Error] Failed to start session: " + esc(err.message) + "\x1b[0m");
      }
      Board.state.termStatus = "stopped";
      updateControlBar();
    });
  }

  /**
   * Kills the current Claude Code session.
   */
  function killSession() {
    if (Board.state.termStatus === "stopped") return;

    postJson("/terminal/kill").then(function () {
      if (term) {
        term.writeln("\x1b[33m-- Session terminated --\x1b[0m");
      }
      Board.state.termStatus = "stopped";
      Board.state.termSessionId = null;
      setInputLocked(false);
      updateControlBar();
    }).catch(function (err) {
      if (term) {
        term.writeln("\x1b[31m[Error] Failed to kill session: " + esc(err.message) + "\x1b[0m");
      }
    });
  }

  // ── UI Update ──

  /**
   * Updates the control bar UI to reflect current session state.
   * Called whenever state changes occur.
   */
  function updateControlBar() {
    var startBtn = document.getElementById("terminal-start-btn");
    var killBtn = document.getElementById("terminal-kill-btn");
    var statusDot = document.getElementById("terminal-status-dot");
    var statusText = document.getElementById("terminal-status-text");
    var sessionIdEl = document.getElementById("terminal-session-id");

    if (startBtn) {
      startBtn.disabled = Board.state.termStatus === "running";
    }
    if (killBtn) {
      killBtn.disabled = Board.state.termStatus === "stopped";
    }
    if (statusDot) {
      statusDot.className = "terminal-status-dot terminal-status-" + Board.state.termStatus;
    }
    // Update data-state on parent .terminal-status for CSS selectors
    var statusContainer = document.querySelector(".terminal-status");
    if (statusContainer) {
      statusContainer.setAttribute("data-state", Board.state.termStatus);
    }
    if (statusText) {
      statusText.textContent = Board.state.termStatus;
    }
    if (sessionIdEl) {
      var sid = Board.state.termSessionId;
      sessionIdEl.textContent = sid ? sid.substring(0, 8) + "..." : "--";
    }

    // Update input field state
    setInputLocked(inputLocked);
  }

  // ── Main Render ──

  /**
   * Main Terminal tab render entry point.
   * On first call, builds the full terminal UI layout, initializes xterm.js
   * and SSE connection. On subsequent calls (tab re-activation), only updates
   * the control bar state without destroying/rebuilding the DOM, so that
   * xterm.js output history is preserved across tab switches.
   */
  function renderTerminal() {
    var el = document.getElementById("view-terminal");
    if (!el) return;

    // If already initialized and the DOM container still exists, just refresh state
    if (termInitialized && document.getElementById("terminal-output")) {
      updateControlBar();
      // Re-fit xterm if the container was hidden and is now visible
      if (term) {
        try { term.refresh(0, term.rows - 1); } catch (e) { /* ignore */ }
      }
      return;
    }

    var h = "";

    // Terminal container
    h += '<div class="terminal-container">';

    // Session control bar
    h += '<div class="terminal-session-bar">';
    h += '<div class="terminal-session-controls">';
    h += '<button class="terminal-btn terminal-btn-start" id="terminal-start-btn">Start</button>';
    h += '<button class="terminal-btn terminal-btn-kill" id="terminal-kill-btn">Kill</button>';
    h += '</div>';
    h += '<div class="terminal-status" data-state="' + esc(Board.state.termStatus) + '">';
    h += '<span class="terminal-status-dot terminal-status-' + esc(Board.state.termStatus) + '" id="terminal-status-dot"></span>';
    h += '<span class="terminal-status-text" id="terminal-status-text">' + esc(Board.state.termStatus) + '</span>';
    h += '</div>';
    h += '<div class="terminal-session-info">';
    h += '<span class="terminal-session-label">Session:</span>';
    h += '<span class="terminal-session-id" id="terminal-session-id">'
      + esc(Board.state.termSessionId ? Board.state.termSessionId.substring(0, 8) + "..." : "--")
      + '</span>';
    h += '</div>';
    h += '</div>';

    // xterm.js output area
    h += '<div class="terminal-output" id="terminal-output"></div>';

    // Input bar
    h += '<div class="terminal-input-bar">';
    h += '<input class="terminal-input" id="terminal-input" type="text"'
      + ' placeholder="Type a message..." autocomplete="off" spellcheck="false"'
      + (Board.state.termStatus === "stopped" ? " disabled" : "")
      + '>';
    h += '<button class="terminal-btn terminal-btn-send" id="terminal-send-btn"'
      + (Board.state.termStatus === "stopped" ? " disabled" : "")
      + '>Send</button>';
    h += '</div>';

    h += '</div>'; // .terminal-container

    el.innerHTML = h;

    // Initialize xterm.js in the output area
    var outputEl = document.getElementById("terminal-output");
    if (outputEl) {
      initXterm(outputEl, function () {
        // After xterm init, connect SSE if not already connected
        if (!termEventSource) {
          connectSSE();
        }
        // Fetch initial status
        fetchStatus();
      });
    }

    // Bind event handlers
    var startBtn = document.getElementById("terminal-start-btn");
    var killBtn = document.getElementById("terminal-kill-btn");
    var sendBtn = document.getElementById("terminal-send-btn");
    var inputEl = document.getElementById("terminal-input");

    if (startBtn) {
      startBtn.addEventListener("click", startSession);
    }
    if (killBtn) {
      killBtn.addEventListener("click", killSession);
    }
    if (sendBtn) {
      sendBtn.addEventListener("click", sendInput);
    }
    if (inputEl) {
      inputEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendInput();
        }
      });
    }

    termInitialized = true;
  }

  // ── Cleanup ──

  /**
   * Cleans up terminal resources when the tab is deactivated.
   * Called externally if needed.
   */
  function cleanupTerminal() {
    disconnectSSE();
    disposeXterm();
    termInitialized = false;
  }

  // ── Hook into switchTab ──
  // Extend switchTab to trigger renderTerminal when Terminal tab is selected
  var originalSwitchTab = Board.util.switchTab;
  Board.util.switchTab = function (target, skipPush) {
    originalSwitchTab(target, skipPush);
    if (target === "terminal" && Board.render.renderTerminal) {
      Board.render.renderTerminal();
    }
  };

  // Also re-bind existing tab click listeners (since common.js binds them before this override)
  document.querySelectorAll(".tab").forEach(function (t) {
    t.addEventListener("click", function () {
      if (t.dataset.view === "terminal" && Board.render.renderTerminal) {
        Board.render.renderTerminal();
      }
    });
  });

  // ── Register on Board namespace ──
  Board.render.renderTerminal = renderTerminal;
  Board.render.cleanupTerminal = cleanupTerminal;
})();
