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

  // ── Markdown Renderer ──

  function renderMarkdown(text) {
    var lines = text.split("\n");
    var out = [];
    var inCodeBlock = false;
    var codeBlockLang = "";
    var i = 0;

    while (i < lines.length) {
      var line = lines[i];

      // Code block toggle
      if (line.match(/^```/)) {
        if (!inCodeBlock) {
          inCodeBlock = true;
          codeBlockLang = line.slice(3).trim();
          out.push("\x1b[90m" + (codeBlockLang ? "  " + codeBlockLang : "  code") + "\x1b[0m");
          out.push("\x1b[90m" + repeat("─", 40) + "\x1b[0m");
        } else {
          inCodeBlock = false;
          out.push("\x1b[90m" + repeat("─", 40) + "\x1b[0m");
        }
        i++;
        continue;
      }

      if (inCodeBlock) {
        out.push("\x1b[36m  " + line + "\x1b[0m");
        i++;
        continue;
      }

      // Markdown table detection
      if (isTableRow(line) && i + 1 < lines.length && isTableSep(lines[i + 1])) {
        var tableLines = [];
        while (i < lines.length && (isTableRow(lines[i]) || isTableSep(lines[i]))) {
          tableLines.push(lines[i]);
          i++;
        }
        out.push(renderTable(tableLines));
        continue;
      }

      // Headers
      var hMatch = line.match(/^(#{1,3})\s+(.*)/);
      if (hMatch) {
        out.push("\x1b[1m\x1b[36m" + hMatch[2] + "\x1b[0m");
        i++;
        continue;
      }

      // List items
      if (line.match(/^\s*[-*]\s/)) {
        out.push(line.replace(/^(\s*)[-*]\s/, "$1• "));
        i++;
        continue;
      }

      // Inline formatting
      out.push(formatInline(line));
      i++;
    }

    return out.join("\r\n");
  }

  function formatInline(line) {
    // Bold **text**
    line = line.replace(/\*\*([^*]+)\*\*/g, "\x1b[1m$1\x1b[22m");
    // Italic *text*
    line = line.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "\x1b[3m$1\x1b[23m");
    // Inline code `text`
    line = line.replace(/`([^`]+)`/g, "\x1b[46m\x1b[30m $1 \x1b[0m");
    return line;
  }

  function isTableRow(line) {
    return line && line.trim().charAt(0) === "|" && line.trim().slice(-1) === "|";
  }

  function isTableSep(line) {
    return line && /^\|[\s:?-]+\|/.test(line.trim());
  }

  function repeat(ch, n) {
    var s = "";
    for (var j = 0; j < n; j++) s += ch;
    return s;
  }

  function renderTable(tableLines) {
    // Parse cells
    var rows = [];
    var sepIdx = -1;
    for (var i = 0; i < tableLines.length; i++) {
      if (isTableSep(tableLines[i])) {
        sepIdx = i;
        continue;
      }
      var cells = tableLines[i].split("|").slice(1, -1);
      for (var c = 0; c < cells.length; c++) cells[c] = cells[c].trim();
      rows.push(cells);
    }

    if (rows.length === 0) return "";

    // Calculate column widths
    var cols = rows[0].length;
    var widths = [];
    for (var c = 0; c < cols; c++) widths[c] = 0;
    for (var r = 0; r < rows.length; r++) {
      for (var c = 0; c < cols && c < rows[r].length; c++) {
        var w = stripAnsi(rows[r][c]).length;
        if (w > widths[c]) widths[c] = w;
      }
    }

    // Render with box-drawing
    var out = [];
    // Top border
    out.push("\x1b[90m┌" + widths.map(function (w) { return repeat("─", w + 2); }).join("┬") + "┐\x1b[0m");

    for (var r = 0; r < rows.length; r++) {
      var row = [];
      for (var c = 0; c < cols; c++) {
        var cell = (rows[r][c] || "");
        var pad = widths[c] - stripAnsi(cell).length;
        row.push(" " + cell + repeat(" ", pad) + " ");
      }
      if (r === 0) {
        // Header row — bold
        out.push("\x1b[90m│\x1b[0m\x1b[1m" + row.join("\x1b[0m\x1b[90m│\x1b[0m\x1b[1m") + "\x1b[0m\x1b[90m│\x1b[0m");
        out.push("\x1b[90m├" + widths.map(function (w) { return repeat("─", w + 2); }).join("┼") + "┤\x1b[0m");
      } else {
        out.push("\x1b[90m│\x1b[0m" + row.join("\x1b[90m│\x1b[0m") + "\x1b[90m│\x1b[0m");
      }
    }

    // Bottom border
    out.push("\x1b[90m└" + widths.map(function (w) { return repeat("─", w + 2); }).join("┴") + "┘\x1b[0m");

    return out.join("\r\n");
  }

  function stripAnsi(s) {
    return s.replace(/\x1b\[[0-9;]*m/g, "");
  }

  // ── Constants ──
  var SSE_RECONNECT_INTERVAL = 3000;  // SSE reconnect delay (ms)
  var XTERM_CDN_CHECK_INTERVAL = 200; // xterm.js CDN load check interval (ms)
  var XTERM_CDN_MAX_WAIT = 10000;     // max wait for xterm.js CDN (ms)

  var TOOL_ICONS = {
    Bash: "\u2699",       // ⚙
    Read: "\u25b6",       // ▶
    Edit: "\u270e",       // ✎
    Write: "\u270d",      // ✍
    Grep: "\u2315",       // ⌕
    Glob: "\u2605",       // ★
    Agent: "\u2726",      // ✦
    WebSearch: "\u2301",  // ⌁
    WebFetch: "\u21e9",   // ⇩
    Skill: "\u269b",      // ⚛
    TodoWrite: "\u2611",  // ☑
    NotebookEdit: "\u2630" // ☰
  };
  // Default icon for unknown tools
  var DEFAULT_TOOL_ICON = "\u25c8"; // ◈

  // ── State ──
  Board.state.termConnected = false;
  Board.state.termSessionId = null;
  Board.state.termStatus = "stopped"; // running | idle | stopped

  /** @type {Terminal|null} xterm.js instance */
  var term = null;
  /** @type {FitAddon|null} xterm.js fit addon */
  var fitAddon = null;
  /** @type {EventSource|null} SSE connection */
  var termEventSource = null;
  /** @type {number|null} SSE reconnect timer */
  var reconnectTimerId = null;
  /** @type {boolean} whether terminal tab has been rendered at least once */
  var termInitialized = false;
  /** @type {boolean} whether input is currently disabled (waiting for result) */
  var inputLocked = false;
  /** @type {boolean} whether streaming chunks were received for current response */
  var receivedChunks = false;
  /** @type {string} buffer for streaming text to render markdown on completion */
  var textBuffer = "";
  /** @type {number} accumulated cost for session */
  var sessionCost = 0;
  /** @type {number} total tokens used */
  var sessionTokens = { input: 0, output: 0 };
  /** @type {string} model display name */
  var sessionModel = '--';
  /** @type {number} context window size */
  var contextWindow = 1000000;
  /** @type {number|null} loading spinner interval */
  var spinnerInterval = null;
  var spinnerFrames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
  var spinnerIdx = 0;

  function startSpinner() {
    if (spinnerInterval) return;
    if (!term) return;
    spinnerIdx = 0;
    term.write("\r\n\x1b[33m✻ Thinking...\x1b[0m");
    spinnerInterval = setInterval(function () {
      if (!term) return;
      var frame = spinnerFrames[spinnerIdx % spinnerFrames.length];
      // 커서를 줄 맨 앞으로 → 덮어쓰기
      term.write("\r\x1b[33m" + frame + " Thinking...\x1b[0m\x1b[K");
      spinnerIdx++;
    }, 80);
  }

  function stopSpinner() {
    if (spinnerInterval) {
      clearInterval(spinnerInterval);
      spinnerInterval = null;
      // Thinking 줄 지우기
      if (term) {
        term.write("\r\x1b[K");
      }
    }
  }

  // ── Copy Panel ──

  /** @type {string} plain text log of all terminal output */
  var plainLog = "";
  /** @type {boolean} whether textarea view is active */
  var textViewActive = false;

  function appendPlainLog(text) {
    plainLog += text;
    var ta = document.getElementById("terminal-text-output");
    if (ta && textViewActive) {
      ta.value = plainLog;
      ta.scrollTop = ta.scrollHeight;
    }
  }

  function toggleTextView() {
    textViewActive = !textViewActive;
    var xtermEl = document.getElementById("terminal-output");
    var textEl = document.getElementById("terminal-text-output");
    var btn = document.getElementById("terminal-copy-btn");
    if (!xtermEl || !textEl) return;

    if (textViewActive) {
      xtermEl.style.display = "none";
      textEl.style.display = "block";
      textEl.value = plainLog;
      textEl.scrollTop = textEl.scrollHeight;
      if (btn) btn.textContent = "Terminal";
    } else {
      xtermEl.style.display = "";
      textEl.style.display = "none";
      if (btn) btn.textContent = "Text";
      if (fitAddon) { try { fitAddon.fit(); } catch (e) {} }
    }
  }

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
      if (data.model) {
        var raw = data.model;
        var ctxMatch = raw.match(/\[(\d+)([mk])\]/i);
        if (ctxMatch) {
          contextWindow = ctxMatch[2].toLowerCase() === "m" ? parseInt(ctxMatch[1]) * 1000000 : parseInt(ctxMatch[1]) * 1000;
        }
        var clean = raw.replace(/\[.*\]/, "").replace(/^claude-/, "");
        clean = clean.replace(/-(\d+)-(\d+)/, " $1.$2").replace(/-/g, " ");
        sessionModel = clean.charAt(0).toUpperCase() + clean.slice(1);
      }
      if (data.permission_mode) {
        var modeEl = document.getElementById("terminal-sl-mode");
        if (modeEl) modeEl.textContent = data.permission_mode;
      }
      if (data.branch) {
        var branchEl = document.getElementById("terminal-sl-branch");
        if (branchEl) branchEl.textContent = data.branch;
      }
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

      // Fit addon: resize terminal columns to match container width
      if (typeof FitAddon !== "undefined" && FitAddon.FitAddon) {
        fitAddon = new FitAddon.FitAddon();
        term.loadAddon(fitAddon);
        fitAddon.fit();
        window.addEventListener("resize", function () {
          if (fitAddon) { try { fitAddon.fit(); } catch (e) {} }
        });
      }

      // Auto-copy selection to clipboard
      term.onSelectionChange(function () {
        var sel = term.getSelection();
        if (sel && navigator.clipboard) {
          navigator.clipboard.writeText(sel).catch(function () {});
        }
      });

      // Keyboard shortcuts (document-level, skip when input focused)
      document.addEventListener("keydown", function (e) {
        if (!term) return;
        if (document.activeElement && document.activeElement.tagName === "TEXTAREA") return;
        // F2 or Ctrl+Shift+C: toggle text view
        if (e.key === "F2" || (e.ctrlKey && e.shiftKey && (e.key === "C" || e.key === "c"))) {
          e.preventDefault();
          toggleTextView();
        }
      });

      term.writeln("\x1b[90mClaude Code Terminal\x1b[0m");
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
   * Returns a Promise that resolves when the SSE connection is open.
   * If the connection is already open, resolves immediately.
   * Otherwise calls connectSSE() and waits for the open event (timeout: 5s).
   * @returns {Promise<void>}
   */
  function connectSSEReady() {
    return new Promise(function (resolve, reject) {
      if (
        termEventSource &&
        termEventSource.readyState === EventSource.OPEN
      ) {
        resolve();
        return;
      }

      // connectSSE() 내부에서 open 이벤트 리스너가 등록되므로,
      // 여기서는 open 이벤트를 한 번만 감지하는 일회성 리스너를 사전 등록한다
      var timer = setTimeout(function () {
        reject(new Error("SSE connection timeout"));
      }, 5000);

      // connectSSE()를 호출하기 전에 임시 EventSource를 열어 open을 감지한다
      // connectSSE()가 내부적으로 disconnectSSE()를 호출하여 기존 연결을 교체하므로
      // 새로운 EventSource 참조를 가져와야 한다
      connectSSE();

      // connectSSE() 완료 후 생성된 termEventSource에 open 리스너 추가
      var source = termEventSource;
      if (!source) {
        clearTimeout(timer);
        reject(new Error("SSE source not created"));
        return;
      }

      if (source.readyState === EventSource.OPEN) {
        clearTimeout(timer);
        resolve();
        return;
      }

      function onOpen() {
        clearTimeout(timer);
        source.removeEventListener("open", onOpen);
        resolve();
      }

      function onError() {
        clearTimeout(timer);
        source.removeEventListener("open", onOpen);
        source.removeEventListener("error", onError);
        reject(new Error("SSE connection failed"));
      }

      source.addEventListener("open", onOpen);
      source.addEventListener("error", onError);
    });
  }

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
        if (term) {
          if (data.chunk && data.kind === "text_delta") {
            receivedChunks = true;
            textBuffer += data.chunk;
          } else if (data.text && data.kind === "assistant" && !receivedChunks) {
            textBuffer += data.text;
          } else if (data.kind === "content_block_start" && data.raw) {
            var block = data.raw.content_block || {};
            if (block.type === "tool_use" && block.name) {
              var icon = TOOL_ICONS[block.name] || DEFAULT_TOOL_ICON;
              term.writeln("");
              term.writeln("\x1b[33m" + icon + " " + block.name + "\x1b[0m");
              appendPlainLog("\n" + icon + " " + block.name + "\n");
            }
          } else if (data.kind === "user" && data.raw) {
            var tr = data.raw.tool_use_result;
            var mc = data.raw.message && data.raw.message.content;
            var resultText = "";

            if (tr) {
              if (tr.stdout) resultText = tr.stdout;
              else if (tr.file && tr.file.content) resultText = tr.file.content;
              else if (typeof tr.content === "string") resultText = tr.content;
            }
            if (!resultText && mc && mc[0] && typeof mc[0].content === "string") {
              resultText = mc[0].content;
            }

            if (resultText) {
              term.writeln("\x1b[90m" + resultText + "\x1b[0m");
              appendPlainLog(resultText + "\n");
            }
            if (tr && tr.stderr) {
              term.writeln("\x1b[31m" + tr.stderr + "\x1b[0m");
              appendPlainLog("[stderr] " + tr.stderr + "\n");
            }
            if (mc && mc[0] && mc[0].is_error) {
              term.writeln("\x1b[31m[Tool Error]\x1b[0m");
              appendPlainLog("[Tool Error]\n");
            }
          }
        }
      } catch (err) {
        // Ignore parse errors
      }
    });

    termEventSource.addEventListener("result", function (e) {
      try {
        var data = JSON.parse(e.data);
        if (data.done) {
          stopSpinner();
          if (data.cost_usd) sessionCost += data.cost_usd;
          if (data.input_tokens) sessionTokens.input += data.input_tokens;
          if (data.output_tokens) sessionTokens.output += data.output_tokens;
          if (term && textBuffer) {
            term.writeln("");
            term.write(renderMarkdown(textBuffer));
            term.writeln("");
            appendPlainLog("\n" + textBuffer + "\n");
          }
          textBuffer = "";
          if (term) {
            term.writeln("\x1b[90mResponse complete\x1b[0m");
          }
          Board.state.termStatus = "idle";
          receivedChunks = false;
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
          sessionCost = 0;
          sessionTokens = { input: 0, output: 0 };
          // Extract model and context window from raw init data
          if (data.raw && data.raw.model) {
            var rawModel = data.raw.model;
            // "claude-opus-4-6[1m]" → "Opus 4.6", contextWindow=1000000
            var ctxMatch = rawModel.match(/\[(\d+)([mk])\]/i);
            if (ctxMatch) {
              var ctxNum = parseInt(ctxMatch[1]);
              contextWindow = ctxMatch[2].toLowerCase() === "m" ? ctxNum * 1000000 : ctxNum * 1000;
            }
            // Pretty model name
            var clean = rawModel.replace(/\[.*\]/, "").replace(/^claude-/, "");
            // "opus-4-6" → "Opus 4.6"
            clean = clean.replace(/-(\d+)-(\d+)/, " $1.$2").replace(/-/g, " ");
            clean = clean.charAt(0).toUpperCase() + clean.slice(1);
            sessionModel = clean;
          }
          // Permission mode
          if (data.raw && data.raw.permissionMode) {
            var modeEl = document.getElementById("terminal-sl-mode");
            if (modeEl) modeEl.textContent = data.raw.permissionMode;
          }
          if (term) {
            term.writeln("\x1b[32mSession started\x1b[0m");
          }
          setInputLocked(false);
          updateControlBar();
        } else if (data.subtype === "process_exit") {
          Board.state.termStatus = "stopped";
          Board.state.termSessionId = null;
          stopSpinner();
          // 143=SIGTERM (Kill 버튼), 0=정상종료 → 무시
          var exitCode = data.exit_code;
          if (exitCode !== 0 && exitCode !== 143 && exitCode !== undefined) {
            if (term) {
              term.writeln("\x1b[31mProcess exited with code " + exitCode + "\x1b[0m");
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
        // Kill(143) / 정상종료(0) 에러 무시
        if (data.exit_code === 143 || data.exit_code === 0) return;
        stopSpinner();
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
    appendPlainLog("\n> " + text + "\n");

    setInputLocked(true);
    startSpinner();
    Board.state.termStatus = "running";
    updateControlBar();
    input.value = "";
    input.style.height = "auto";

    postJson("/terminal/input", { text: text }).catch(function (err) {
      stopSpinner();
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
   * Ensures SSE connection is ready before calling /terminal/start so that
   * the system/init event is never missed.
   */
  function startSession() {
    if (Board.state.termStatus === "running") return;

    if (term) {
      term.clear();
      term.writeln("\x1b[90mStarting session...\x1b[0m");
    }

    Board.state.termStatus = "running";
    updateControlBar();

    // SSE 연결이 준비된 후에만 /terminal/start를 호출한다.
    // connectSSEReady()는 이미 연결되어 있으면 즉시 resolve한다.
    connectSSEReady().then(function () {
      return postJson("/terminal/start");
    }).then(function (data) {
      if (data.session_id) {
        Board.state.termSessionId = data.session_id;
        Board.state.termStatus = "idle";
        updateControlBar();
      }
      // init 대기 없이 바로 전송 — stdin 버퍼에 쌓임
      startSpinner();
      setInputLocked(true);
      postJson("/terminal/input", { text: "첫 메시지입니다. '세션이 초기화 되었습니다.' 라고만 답하세요." }).catch(function () {});
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
        term.writeln("\x1b[33mSession terminated\x1b[0m");
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
    if (startBtn) {
      startBtn.disabled = Board.state.termStatus === "running";
    }
    if (killBtn) {
      killBtn.disabled = Board.state.termStatus === "stopped";
    }
    if (statusDot) {
      statusDot.className = "terminal-status-dot terminal-status-" + Board.state.termStatus;
    }
    var statusContainer = document.querySelector(".terminal-status");
    if (statusContainer) {
      statusContainer.setAttribute("data-state", Board.state.termStatus);
    }
    if (statusText) {
      statusText.textContent = Board.state.termStatus;
    }
    var sessionIdEl = document.getElementById("terminal-session-id");
    if (sessionIdEl) {
      sessionIdEl.textContent = Board.state.termSessionId || '';
    }

    // Update status line
    updateStatusLine();

    // Update input field state
    setInputLocked(inputLocked);
  }

  function updateStatusLine() {
    var slModel = document.getElementById("terminal-sl-model");
    var slBar = document.getElementById("terminal-sl-bar");
    var slTokens = document.getElementById("terminal-sl-tokens");
    var slCost = document.getElementById("terminal-sl-cost");

    if (slModel) slModel.textContent = sessionModel;

    // Branch: add git icon prefix if element has content
    var slBranch = document.getElementById("terminal-sl-branch");
    if (slBranch) {
      var branchText = slBranch.textContent.replace(/^\ue0a0\s*/, "").trim();
      if (branchText && branchText !== "--") {
        slBranch.textContent = "\ue0a0 " + branchText;
      }
    }

    // Context progress bar
    var totalTokens = sessionTokens.input + sessionTokens.output;
    var pct = contextWindow > 0 ? Math.min(totalTokens / contextWindow * 100, 100) : 0;
    var barFill = document.getElementById("terminal-sl-bar-fill");
    var barPct = document.getElementById("terminal-sl-bar-pct");
    if (barFill) barFill.style.width = pct.toFixed(1) + "%";
    if (barPct) barPct.textContent = pct.toFixed(1) + "%";

    // Token display
    if (slTokens) {
      var fmtTotal = totalTokens >= 1000 ? Math.round(totalTokens / 1000) + "k" : totalTokens;
      var fmtCtx = contextWindow >= 1000000 ? (contextWindow / 1000000) + "M" : Math.round(contextWindow / 1000) + "k";
      slTokens.textContent = "(" + fmtTotal + "/" + fmtCtx + ")";
    }

    if (slCost) slCost.textContent = "$" + sessionCost.toFixed(4);
  }

  // ── Main Render ──

  /**
   * Detects whether running in SPA mode (index.html) or standalone mode (terminal.html).
   * SPA mode:        document.getElementById("view-terminal") exists
   * Standalone mode: document.getElementById("terminal-standalone") or <body> fallback
   * @returns {HTMLElement|null} container element, or null if not available
   */
  function getContainer() {
    var spaEl = document.getElementById("view-terminal");
    if (spaEl) return spaEl;
    var standaloneEl = document.getElementById("terminal-standalone");
    if (standaloneEl) return standaloneEl;
    return null;
  }

  /**
   * Main Terminal tab render entry point.
   * On first call, builds the full terminal UI layout, initializes xterm.js
   * and SSE connection. On subsequent calls (tab re-activation), only updates
   * the control bar state without destroying/rebuilding the DOM, so that
   * xterm.js output history is preserved across tab switches.
   *
   * Supports dual mode:
   *  - SPA mode (index.html): renders into #view-terminal
   *  - Standalone mode (terminal.html): renders into #terminal-standalone
   */
  function renderTerminal() {
    var el = getContainer();
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
    h += '<div class="terminal-session-left">';
    h += '<div class="terminal-status" data-state="' + esc(Board.state.termStatus) + '">';
    h += '<span class="terminal-status-dot terminal-status-' + esc(Board.state.termStatus) + '" id="terminal-status-dot"></span>';
    h += '<span class="terminal-status-text" id="terminal-status-text">' + esc(Board.state.termStatus) + '</span>';
    h += '</div>';
    h += '<span class="terminal-session-id" id="terminal-session-id">'
      + esc(Board.state.termSessionId || '')
      + '</span>';
    h += '</div>';
    h += '<div class="terminal-session-controls">';
    h += '<button class="terminal-btn terminal-btn-start" id="terminal-start-btn">Start</button>';
    h += '<button class="terminal-btn terminal-btn-kill" id="terminal-kill-btn">Kill</button>';
    h += '<button class="terminal-btn terminal-btn-copy" id="terminal-copy-btn" title="Toggle text view (F2)">Text</button>';
    h += '<span class="terminal-controls-divider"></span>';
    h += '<button class="terminal-btn terminal-btn-settings" id="terminal-settings-btn" title="Settings">';
    h += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">';
    h += '<circle cx="12" cy="12" r="3"/>';
    h += '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>';
    h += '</svg></button>';
    h += '</div>';
    // Settings dropdown (hidden by default)
    h += '<div class="terminal-settings-dropdown" id="terminal-settings-dropdown">';
    h += '<button class="terminal-settings-item" id="terminal-restart-server">Restart Server</button>';
    h += '<button class="terminal-settings-item" id="terminal-clear-output">Clear Output</button>';
    h += '</div>';
    h += '</div>';

    // xterm.js output area
    h += '<div class="terminal-output" id="terminal-output"></div>';
    h += '<textarea class="terminal-text-output" id="terminal-text-output" readonly spellcheck="false" style="display:none"></textarea>';

    // Input card (Claude-style)
    h += '<div class="terminal-input-card">';
    h += '<textarea class="terminal-input" id="terminal-input"'
      + ' placeholder="메시지를 입력하세요..." rows="1"'
      + ' autocomplete="off" spellcheck="false"'
      + (Board.state.termStatus === "stopped" ? " disabled" : "")
      + '></textarea>';
    h += '<div class="terminal-input-bottom">';
    h += '<div class="terminal-input-bottom-left"></div>';
    h += '<div class="terminal-input-bottom-right">';
    h += '<span class="terminal-input-hint">Enter 전송 · Shift+Enter 줄바꿈</span>';
    h += '<button class="terminal-send-btn" id="terminal-send-btn"'
      + (Board.state.termStatus === "stopped" ? " disabled" : "")
      + '><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg></button>';
    h += '</div>';
    h += '</div>';
    h += '</div>';

    // Status line
    h += '<div class="terminal-statusline" id="terminal-statusline">';
    h += '<span class="terminal-sl-model" id="terminal-sl-model">--</span>';
    h += '<span class="terminal-sl-branch" id="terminal-sl-branch">--</span>';
    h += '<span class="terminal-sl-bar" id="terminal-sl-bar"><span class="terminal-sl-bar-track"><span class="terminal-sl-bar-fill" id="terminal-sl-bar-fill" style="width:0%"></span></span><span id="terminal-sl-bar-pct">0%</span></span>';
    h += '<span class="terminal-sl-tokens" id="terminal-sl-tokens">(0/0)</span>';
    h += '<span class="terminal-sl-right">';
    h += '<span class="terminal-sl-mode" id="terminal-sl-mode"></span>';
    h += '<span id="terminal-sl-cost">$0.00</span>';
    h += '<span id="terminal-sl-port">port:' + location.port + '</span>';
    h += '</span>';
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

    // Settings dropdown
    var settingsBtn = document.getElementById("terminal-settings-btn");
    var settingsDropdown = document.getElementById("terminal-settings-dropdown");
    if (settingsBtn && settingsDropdown) {
      settingsBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        settingsDropdown.classList.toggle("visible");
      });
      document.addEventListener("click", function () {
        settingsDropdown.classList.remove("visible");
      });
    }
    var restartBtn = document.getElementById("terminal-restart-server");
    if (restartBtn) {
      restartBtn.addEventListener("click", function () {
        settingsDropdown.classList.remove("visible");
        postJson("/api/restart").then(function () {
          // Server will restart via execv — reload page after short delay
          setTimeout(function () { location.reload(); }, 1500);
        }).catch(function () {
          // Server may already be restarting
          setTimeout(function () { location.reload(); }, 2000);
        });
      });
    }
    var clearBtn = document.getElementById("terminal-clear-output");
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        settingsDropdown.classList.remove("visible");
        if (term) { term.clear(); }
      });
    }
    var copyBtn = document.getElementById("terminal-copy-btn");
    if (copyBtn) {
      copyBtn.addEventListener("click", toggleTextView);
    }
    if (inputEl) {
      inputEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendInput();
          return;
        }
        // Enter 외 모든 키는 textarea 네이티브 동작 보장 (xterm 가로채기 방지)
        e.stopPropagation();
      });
      // Auto-resize textarea
      inputEl.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 120) + "px";
      });
    }

    // ResizeObserver for fit addon
    var outputEl2 = document.getElementById("terminal-output");
    if (outputEl2 && typeof ResizeObserver !== "undefined") {
      new ResizeObserver(function () {
        if (fitAddon) { try { fitAddon.fit(); } catch (e) {} }
      }).observe(outputEl2);
    }

    termInitialized = true;

    // Fetch branch on load
    fetch("/api/branch").then(function (r) { return r.json(); }).then(function (d) {
      if (d.branch) {
        var el = document.getElementById("terminal-sl-branch");
        if (el) el.textContent = d.branch;
      }
    }).catch(function () {});
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

  // ── Hook into switchTab (SPA mode only) ──
  // Extend switchTab to trigger renderTerminal when Terminal tab is selected.
  // In standalone mode (terminal.html), Board.util.switchTab is defined by common.js
  // but there are no tab buttons — the hook is still safe since querySelectorAll
  // returns an empty NodeList and switchTab is never called externally.
  if (Board.util.switchTab) {
    var originalSwitchTab = Board.util.switchTab;
    Board.util.switchTab = function (target, skipPush) {
      originalSwitchTab(target, skipPush);
      if (target === "terminal" && Board.render.renderTerminal) {
        Board.render.renderTerminal();
      }
    };
  }

  // Also re-bind existing tab click listeners (since common.js binds them before this override)
  // querySelectorAll returns empty NodeList in standalone mode — forEach is a no-op.
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
