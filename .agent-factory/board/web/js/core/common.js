/**
 * @module common
 *
 * Board SPA shared foundation module.
 *
 * Initializes the window.Board namespace and registers shared constants,
 * utility functions, state objects, XML/directory parsers, Highlight.js
 * and Markdown helpers, UI persistence, and tab switching logic.
 *
 * This module must be loaded before all other Board modules.
 */
"use strict";

// ── Namespace Initialization ──
window.Board = window.Board || {};
const Board = window.Board;

Board.state = Board.state || {};
Board.util = Board.util || {};
Board.render = Board.render || {};
Board.fetch = Board.fetch || {};

// ── Debug Logger (server-gated) ──
//
// The measurement is based on the entire code and determines the activation of the server side flag file.
// control .agent-factory/runs/bg/debug.enabled file by touch/rm.
// Cla is always POST — server checks flag files to the file
// You should decide to write. The usual overhead is only fetch once (ms).
//
// Tag:
//   1. Claude: touch .../runs/bg/debug.enabled (+ existing log empty)
//   2. User: Reproduction of problem
//   3. FAQs Claude: Analysis by cat .../runs/bg/debug.log
//   4. Claude: rm .../runs/bg/debug.enabled (active)

Board.debugLog = function (tag, data) {
  var entry = {
    ts: new Date().toISOString(),
    tag: String(tag || ''),
    data: data === undefined ? null : data,
  };
  try {
    fetch('/api/debug-log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(entry),
      keepalive: true,
    }).catch(function () {});
  } catch (e) { /* Network Errors */ }
};

// ── Terminal Status State Machine ──
//
// enum and former helper expressing the life cycle of the main terminal session.
//
//   Stop: No Claude CLI process. Start Wait.
//   starting : before receiving system/init event from spawn request. Input inert.
//   idle: Claude ready. No response. Type
//   busy: result/process exit after sending user input. Spinner display.
//   archived: the past session restored exclusively for reading. Reservation
//   missing: Find the server doesn't have a session (404). No input.
//
// Price:
//   stopped -> starting -> idle -> busy -> idle -> ... -> stopped
//
// Price:
//   starting -> stop (spawn failure)
//   busy     -> stopped      (process_exit)
//   * -> archived (archived load)
//   *        -> missing      (fetchStatus 404)
//
// Label:
//   stopped=subscribed, starting=subject, idle=subject, busy=subject,
//   archived= read only, missing=no action
//
Board.util.TERM_STATUSES = Object.freeze({
  STOPPED: 'stopped',
  STARTING: 'starting',
  IDLE: 'idle',
  BUSY: 'busy',
  ARCHIVED: 'archived',
  MISSING: 'missing',
});

Board.util.TERM_STATUS_LABELS = Object.freeze({
  stopped: 'Stopped',
  starting: 'Starting',
  idle: 'Idle',
  busy: 'Busy',
  archived: 'Archived',
  missing: 'Missing',
});

/** Kill button can end session */
Board.util.TERM_STATUS_KILLABLE = Object.freeze(
  new Set(['starting', 'idle', 'busy'])
);

/** Claude is currently working (speaker display) */
Board.util.TERM_STATUS_SPINNING = Object.freeze(new Set(['busy']));

/** User can send new input */
Board.util.TERM_STATUS_INPUTTABLE = Object.freeze(
  new Set(['idle', 'busy'])
);

/** The server (`/terminal/status`) is authoritatively judged — the clad extension is managed */
var _SERVER_AUTHORITATIVE = Object.freeze(new Set(['stopped']));
var _CLIENT_EXTENDED = Object.freeze(
  new Set(['starting', 'idle', 'busy', 'archived', 'missing'])
);

/**
 * Sets Board.state.termStatus. We use cookies to ensure that we give you the best experience on our website.
 * @param {string} next new state (TERM STATUSES one of the values)
 */
Board.state.setTermStatus = function (next) {
  if (typeof next !== 'string') return;
  Board.state.termStatus = next;
};

// ESC autoResume Windows — process exit + willAutoResume from entry to startSession.setIdle.
// This window will automatically close when termStatus is stopped → starting, but setInputLocked
// does not make input.disabled true. Input window flicker (~500ms) for avoidance.
Board.state._inAutoResume = false;

/**
 * merge server /terminal/status response (stopped/running) to the climatic machine.
 * - When the server returns a stop, the climax stops to the full (recommended).
 * - Server returns running and crawls to startting/idle/busy/archived/missing
 *   Keeping the climatic state if it is. Other than others considered idle.
 * archived/missing enters fetchStatus 404 or archived end
 * You do not have to set it directly here.
 *
 * @param {string} serverStatus server reported status string
 */
Board.state.reconcileTermStatus = function (serverStatus) {
  var current = Board.state.termStatus;
  var result;
  if (!serverStatus) {
    Board.state.setTermStatus('stopped');
    result = 'stopped(empty)';
  } else if (serverStatus === 'stopped') {
    Board.state.setTermStatus('stopped');
    result = 'stopped';
  } else if (serverStatus === 'running') {
    if (current === 'starting') {
      // Θ client-only transient state. server has reported 'running'
      // Since the server side process is a clear signal that lives, it should be corrected by idle.
      // (After awaiting response treatment can be added as busy)
      Board.state.setTermStatus('idle');
      result = 'idle(from-starting)';
    } else if (_CLIENT_EXTENDED.has(current)) {
      result = 'keep(' + current + ')';
    } else {
      // If the server is running, the server is running:
      // Awaiting response is authoritative.
      // where idle is only corrected, and the busy shooting of fetchStatus
      // 'if (data.awaiting response)' branch is solely responsible.
      // 'busy(from-stopped)' rule refreshes awaiting response=false
      // Infinite spinning revolving spinner — 2026-05-13 fix)
      Board.state.setTermStatus('idle');
      result = 'idle(from-' + current + ')';
    }
  } else {
    Board.state.setTermStatus(serverStatus);
    result = 'passthrough(' + serverStatus + ')';
  }
  if (Board.debugLog) Board.debugLog('reconcileTermStatus', {
    server: serverStatus, before: current, after: Board.state.termStatus, result: result,
  });
};

// ── Constants ──
const PRODUCT_LABELS = {
  appTitle: "Agent Factory Console",
  work_request: "Work Item",
  workRequests: "Conveyor",
  run: "Run",
  runs: "Runs",
  verification: "Verification",
  reports: "Reports",
  settings: "Settings",
};

const STATUS_LABELS = {
  "Draft": "Draft",
  Accepted: "Accepted",
  "Executing": "Executing",
  Verifying: "Verifying",
  Complete: "Complete",
};

const STEP_LABELS = {
  INIT: "Initialize",
  PLAN: "Plan",
  WORK: "Execute",
  VALIDATE: "Verify",
  REPORT: "Report",
  DONE: "Complete",
  FAILED: "Failed",
  NONE: "None",
};

const COMMAND_LABELS = {
  implement: "Execute",
  research: "Research",
  review: "Verifying",
  prompt: "Prompt",
};

const COLUMNS = [
  { key: "Draft", label: STATUS_LABELS["Draft"], dot: "dot-todo" },
  { key: "Accepted", label: STATUS_LABELS.Accepted, dot: "dot-open" },
  { key: "Executing", label: STATUS_LABELS["Executing"], dot: "dot-progress" },
  { key: "Verifying", label: STATUS_LABELS.Verifying, dot: "dot-review" },
  { key: "Complete", label: STATUS_LABELS.Complete, dot: "dot-done" },
];

const CMD_COLORS = {
  implement: { bg: "rgba(86,156,214,0.22)", fg: "#9CDCFE" },
  review: { bg: "rgba(197,134,192,0.22)", fg: "#C586C0" },
  research: { bg: "rgba(220,220,170,0.22)", fg: "#DCDCAA" },
  prompt: { bg: "rgba(160,160,160,0.16)", fg: "#A0A0A0" },
};

const STATUS_COLORS = {
  "Draft": { bg: "rgba(156,220,254,0.14)", fg: "#9CDCFE" },
  Accepted: { bg: "rgba(78,201,176,0.14)", fg: "#4EC9B0" },
  "Executing": { bg: "rgba(220,220,170,0.14)", fg: "#DCDCAA" },
  Verifying: { bg: "rgba(197,134,192,0.14)", fg: "#C586C0" },
  Complete: { bg: "rgba(133,133,133,0.15)", fg: "#858585" },
};

const LS_KEY = "claude-board-ui";
const CONVEYOR_SORT_LS_KEY = "claude-board-conveyor-sort";

// Register constants on Board.util for cross-module access
Board.util.COLUMNS = COLUMNS;
Board.util.CMD_COLORS = CMD_COLORS;
Board.util.STATUS_COLORS = STATUS_COLORS;
Board.util.PRODUCT_LABELS = PRODUCT_LABELS;
Board.util.STATUS_LABELS = STATUS_LABELS;
Board.util.STEP_LABELS = STEP_LABELS;
Board.util.COMMAND_LABELS = COMMAND_LABELS;
Board.util.LS_KEY = LS_KEY;
Board.util.CONVEYOR_SORT_LS_KEY = CONVEYOR_SORT_LS_KEY;

// ── Utility Functions ──

/** Escapes HTML entities in text. */
function esc(text) {
  const d = document.createElement("div");
  d.textContent = text || "";
  return d.innerHTML;
}

/** Extracts text content from an XML element's child tag. */
function xmlText(el, tag) {
  const c = el && el.querySelector(tag);
  return c ? (c.textContent || "").trim() : "";
}

/** Formats a datetime string to YYYY-MM-DD HH:MM. */
function formatTime(dt) {
  return dt ? dt.substring(0, 16) : "";
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status || "";
}

function stepLabel(step) {
  var key = String(step || "NONE").toUpperCase();
  return STEP_LABELS[key] || key;
}

function commandLabel(command) {
  return COMMAND_LABELS[command] || command || "";
}

/** Command name → 3-letter abbreviation map. */
var CMD_ABBR = {
  implement: "IMP",
  research: "RSC",
  review: "REV",
  prompt: "PRM",
  refactor: "REF",
  test: "TST",
  deploy: "DEP",
  design: "DES",
  plan: "PLN",
  fix: "FIX",
  debug: "DBG",
  analyze: "ANL",
  document: "DOC",
};
Board.util.CMD_ABBR = CMD_ABBR;

/** Renders a colored badge span with 3-letter abbreviation. */
function badge(text, colors, extraStyle) {
  if (!text || !colors) return "";
  var label = CMD_ABBR[text] || text.substring(0, 3).toUpperCase();
  return '<span class="badge" style="background:' + colors.bg + ";color:" + colors.fg + ";" + (extraStyle || '') + '">' + label + "</span>";
}

Board.util.esc = esc;
Board.util.xmlText = xmlText;
Board.util.formatTime = formatTime;
Board.util.statusLabel = statusLabel;
Board.util.stepLabel = stepLabel;
Board.util.commandLabel = commandLabel;
Board.util.badge = badge;

// ── XML WorkRequest Parsing ──

/** Parses a workRequest XML string into a workRequest data object. */
function parseWorkRequest(text) {
  const doc = new DOMParser().parseFromString(text, "text/xml");
  const root = doc.querySelector("work_request");
  if (!root) return null;

  const meta = root.querySelector("metadata");
  const workRequest = {
    number: "", title: "", created: "", updated: "", status: "Accepted",
    command: "", prompt: null, result: null,
    relations: [],
  };

  if (meta) {
    ["number", "title", "created", "updated", "status"].forEach(function (f) {
      const el = meta.querySelector(f);
      if (el && el.textContent) workRequest[f] = el.textContent.trim();
    });
    // <datetime>
    if (!workRequest.created || !workRequest.updated) {
      var dtEl = meta.querySelector("datetime");
      if (dtEl && dtEl.textContent) {
        var dtVal = dtEl.textContent.trim();
        if (!workRequest.created) workRequest.created = dtVal;
        if (!workRequest.updated) workRequest.updated = dtVal;
      }
    }
    const cmdEl = meta.querySelector("command");
    if (cmdEl) workRequest.command = (cmdEl.textContent || "").trim();
  }

  // Flat structure: <prompt> directly under <workRequest>
  var promptEls = root.getElementsByTagName("prompt");
  var promptEl = null;
  for (var pi = 0; pi < promptEls.length; pi++) {
    if (promptEls[pi].parentNode === root) { promptEl = promptEls[pi]; break; }
  }
  if (promptEl) {
    var prompt = {};
    for (var fi = 0; fi < promptEl.children.length; fi++) {
      var fc = promptEl.children[fi];
      var ft = (fc.textContent || "").trim();
      ft = ft.split("\n").map(function (l) { return l.trim(); }).filter(function (l) { return l; }).join("\n");
      if (ft) prompt[fc.tagName] = ft;
    }
    if (Object.keys(prompt).length > 0) workRequest.prompt = prompt;
  }

  // Flat structure: <result> directly under <workRequest>
  var resultEls = root.getElementsByTagName("result");
  var resultEl = null;
  for (var rsi = 0; rsi < resultEls.length; rsi++) {
    if (resultEls[rsi].parentNode === root) { resultEl = resultEls[rsi]; break; }
  }
  if (resultEl) {
    var rObj = {};
    for (var ri = 0; ri < resultEl.children.length; ri++) {
      var rc = resultEl.children[ri];
      var rt = (rc.textContent || "").trim();
      if (rt) rObj[rc.tagName.toLowerCase()] = rt;
    }
    if (Object.keys(rObj).length > 0) workRequest.result = rObj;
  }

  // Legacy done workRequest fallback (read-only): <submit>/<subnumber> structure
  // WR-399: Submit transient step is removed from the system. This block is only compatible with the past done workRequest display.
  if (!workRequest.prompt && !workRequest.command) {
    var submitEl = root.querySelector("submit");
    if (submitEl) {
      var subs = submitEl.querySelectorAll("subnumber");
      var activeSub = null;
      for (var si = 0; si < subs.length; si++) {
        if (subs[si].getAttribute("active") === "true") { activeSub = subs[si]; break; }
      }
      if (!activeSub && subs.length > 0) activeSub = subs[subs.length - 1];
      if (activeSub) {
        var legacyCmd = (activeSub.querySelector("command") || {}).textContent || "";
        if (legacyCmd) workRequest.command = legacyCmd.trim();
        var legacyPromptEl = activeSub.querySelector("prompt");
        if (legacyPromptEl) {
          var lp = {};
          for (var lpi = 0; lpi < legacyPromptEl.children.length; lpi++) {
            var lc = legacyPromptEl.children[lpi];
            var lt = (lc.textContent || "").trim();
            if (lt) lp[lc.tagName] = lt;
          }
          if (Object.keys(lp).length > 0) workRequest.prompt = lp;
        }
        var legacyResultEl = activeSub.querySelector("result");
        if (legacyResultEl) {
          var lr = {};
          for (var lri = 0; lri < legacyResultEl.children.length; lri++) {
            var lrc = legacyResultEl.children[lri];
            var lrt = (lrc.textContent || "").trim();
            if (lrt) lr[lrc.tagName.toLowerCase()] = lrt;
          }
          if (Object.keys(lr).length > 0) workRequest.result = lr;
        }
      }
    }
  }

  const relationsEl = root.querySelector("relations");
  if (relationsEl) {
    const rels = relationsEl.querySelectorAll("relation");
    for (let k = 0; k < rels.length; k++) {
      const type = rels[k].getAttribute("type") || "";
      const relWorkRequest = rels[k].getAttribute("work_request") || "";
      if (type && relWorkRequest) workRequest.relations.push({ type: type, work_request: relWorkRequest });
    }
  }

  return workRequest;
}

Board.util.parseWorkRequest = parseWorkRequest;

// ── Directory / Path Utilities ──

/** Parses an HTML directory listing into dirs and files arrays. */
function parseDirLinks(html) {
  const dirs = [];
  const files = [];
  const re = /href="([^"]+)"/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    const href = m[1];
    if (href === "../") continue;
    if (href.endsWith("/")) dirs.push(href);
    else files.push(href);
  }
  return { dirs: dirs, files: files };
}

/** Returns the last URL path segment, decoded. */
function lastSegment(href) {
  const parts = href.replace(/\/$/, "").split("/");
  return decodeURIComponent(parts[parts.length - 1]);
}

/**
 * Resolves a result path to its actual location, handling archived workflows.
 * When a workflow is archived to .history/, workRequest XML still holds the original
 * workflow/YYYYMMDD-HHMMSS/ path. This function rewrites the path using the
 * actual basePath from the WORKFLOWS array.
 */
function resolveResultPath(path) {
  const m = path.match(/\.workflow\/(\d{8}-\d{6})\//);
  if (!m) return path;
  const regKey = m[1];

  for (let i = 0; i < Board.state.WORKFLOWS.length; i++) {
    if (Board.state.WORKFLOWS[i].entry === regKey) {
      const bp = Board.state.WORKFLOWS[i].basePath || "";
      if (bp.indexOf(".history/") !== -1) {
        return path.replace(
          "workflow/" + regKey + "/",
          "workflow/.history/" + regKey + "/"
        );
      }
      return path;
    }
  }
  return path;
}

/** Returns the directory portion of a URL (up to and including the last '/'). */
function urlDir(url) {
  if (!url) return "";
  return url.substring(0, url.lastIndexOf("/") + 1);
}

function projectRoot() {
  var path = window.location.pathname;
  var idx = path.indexOf(".agent-factory/board/");
  if (idx !== -1) return path.substring(0, idx);
  return "/";
}

/**
 * Builds a full URL path from a .agent-factory/ relative path.
 * @param {string} wfPath - Path starting with .agent-factory/ or workflow/
 * @returns {string} Absolute URL path from project root
 */
function resolveToRoot(wfPath) {
  return projectRoot() + resolveResultPath(wfPath);
}

Board.util.parseDirLinks = parseDirLinks;
Board.util.lastSegment = lastSegment;
Board.util.resolveResultPath = resolveResultPath;
Board.util.resolveToRoot = resolveToRoot;
Board.util.projectRoot = projectRoot;
Board.util.urlDir = urlDir;

// ── Highlight.js Language Mapping ──

/** Maps file extension to highlight.js language identifier. */
function getHighlightLang(url) {
  const LANG_MAP = {
    ".py":   "python",
    ".js":   "javascript",
    ".ts":   "typescript",
    ".jsx":  "javascript",
    ".tsx":  "typescript",
    ".md":   "markdown",
    ".xml":  "xml",
    ".sh":   "bash",
    ".json": "json",
    ".css":  "css",
    ".html": "html",
    ".yml":  "yaml",
    ".yaml": "yaml",
  };
  const m = url && url.match(/(\.[^./?#]+)(?:[?#].*)?$/);
  if (!m) return "plaintext";
  return LANG_MAP[m[1].toLowerCase()] || "plaintext";
}

/** Applies highlight.js to pending code blocks. */
function initHighlight() {
  const blocks = document.querySelectorAll(".code-viewer code.hljs-pending, .md-body code.hljs-pending");
  blocks.forEach(function (block) {
    if (block.dataset.highlighted) return;
    block.dataset.highlighted = "true";
    block.classList.remove("hljs-pending");
    if (typeof hljs === "undefined") return;
    let lang = null;
    const classes = block.className.split(/\s+/);
    for (let i = 0; i < classes.length; i++) {
      const m = classes[i].match(/^language-(.+)$/);
      if (m) {
        lang = m[1];
        break;
      }
    }
    if (lang && lang !== "plaintext" && hljs.getLanguage(lang)) {
      hljs.highlightElement(block);
    }
  });
}

Board.util.getHighlightLang = getHighlightLang;
Board.render.initHighlight = initHighlight;

// ── Markdown Rendering ──
let mermaidCounter = 0;

/** Renders markdown text to HTML, with Mermaid and code highlighting support. */
function renderMd(text, baseUrl) {
  if (typeof marked === "undefined") return '<pre class="wf-file-content">' + esc(text) + '</pre>';

  // WR-321 P1 — flow-conveyor XML field (-constraints "Condition1\n condition2")
  // Litreal backslash-n 2 letters to the actual opening (code fence/inline backtick inside preserved).
  if (Board.util && Board.util.unescapeLiteralNewlines) {
    text = Board.util.unescapeLiteralNewlines(text);
  }

  const renderer = new marked.Renderer();
  renderer.code = function (opts) {
    const code = typeof opts === "object" ? opts.text : opts;
    const lang = typeof opts === "object" ? opts.lang : arguments[1];
    if (lang === "mermaid") {
      const id = "mermaid-" + (++mermaidCounter);
      return '<div class="mermaid-block" data-mermaid-id="' + id + '">' + esc(code) + '</div>';
    }
    const langClass = lang ? lang : "plaintext";
    return '<pre class="md-code"><code class="hljs-pending language-' + esc(langClass) + '">' + esc(code) + '</code></pre>';
  };

  renderer.link = function (opts) {
    const href = typeof opts === "object" ? opts.href : opts;
    const title = typeof opts === "object" ? opts.title : arguments[1];
    const text = typeof opts === "object" ? opts.text : arguments[2];
    if (!href) return text || "";
    if (href.indexOf("http://") === 0 || href.indexOf("https://") === 0) {
      const titleAttr = title ? ' title="' + esc(title) + '"' : "";
      return '<a href="' + esc(href) + '"' + titleAttr + ' target="_blank" rel="noopener noreferrer">' + (text || esc(href)) + '</a>';
    }
    let resolvedUrl;
    if (href.indexOf("workflow/") === 0 || href.indexOf(".claude/") === 0) {
      resolvedUrl = resolveToRoot(href);
    } else {
      resolvedUrl = urlDir(baseUrl) + href;
    }
    return '<span class="md-file-link" data-filepath="' + esc(href) + '" data-url="' + esc(resolvedUrl) + '">' + (text || esc(href)) + '</span>';
  };

  let html = marked.parse(text, { renderer: renderer, gfm: true, breaks: true });

  // WR-321 P2 — Merged into a single <ol> block (if text short circuit is not attached).
  // In a single ol output with a non-pure/0-start number (e.g. 5.6.7. / 1.2.0.) is already in a parent,
  // idempotent after-treatment to ensure the same indentation in the user input strain (the case with a rare marker).
  if (Board.util && Board.util.mergeAdjacentOrderedLists) {
    html = Board.util.mergeAdjacentOrderedLists(html);
  }

  const FILE_EXT_RE = /\.(md|js|ts|jsx|tsx|css|html|json|py|txt|log|xml|sh|yml|yaml|toml|env|csv)$/i;
  html = html.replace(/<code>([^<]+)<\/code>/g, function (match, inner) {
    const decoded = inner.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&#39;/g, "'").replace(/&quot;/g, '"');
    const isFilePath = decoded.indexOf("/") !== -1 || FILE_EXT_RE.test(decoded.trim());
    if (isFilePath) {
      const escaped = esc(decoded.trim());
      return '<code class="md-file-link" data-filepath="' + escaped + '">' + inner + '</code>';
    }
    return match;
  });

  return html;
}

/** Removes orphan SVG elements inserted by Mermaid into document.body during failed renders. */
function cleanupMermaidOrphans(id) {
  // Mermaid v11 may insert a temporary element with id="d<N>" or the render id into body
  var orphan = document.getElementById(id);
  if (orphan && orphan !== document.body && !orphan.closest('.mermaid-block')) {
    orphan.remove();
  }
  // Also sweep for any SVG elements directly under body with id starting with "d" followed by digits
  document.querySelectorAll('body > svg[id], body > div[id]').forEach(function (el) {
    if (/^d\d+$/.test(el.id)) {
      el.remove();
    }
  });
}

/** Renders pending Mermaid diagram blocks. */
function initMermaid() {
  var defined = typeof mermaid !== "undefined";
  var blocks = document.querySelectorAll(".mermaid-block");
  if (Board.debugLog) Board.debugLog('initMermaid.call', {
    defined: defined, blockCount: blocks.length,
  });
  if (!defined) return;
  blocks.forEach(function (block) {
    if (block.dataset.rendered) return;
    block.dataset.rendered = "true";
    var id = block.dataset.mermaidId;
    var code = block.textContent;
    if (Board.debugLog) Board.debugLog('initMermaid.render', {
      id: id, codeHead: code.slice(0, 80),
    });
    mermaid.render(id, code).then(function (result) {
      block.innerHTML = result.svg;
      if (Board.debugLog) Board.debugLog('initMermaid.success', { id: id });
    }).catch(function (err) {
      console.warn('[initMermaid] Mermaid render failed for id=' + id + ':', err);
      if (Board.debugLog) Board.debugLog('initMermaid.fail', {
        id: id, err: String(err && err.message || err),
      });
      cleanupMermaidOrphans(id);
      block.innerHTML = '<pre class="wf-file-content">' + esc(code) + '</pre>';
    });
  });
}

// async script loading once more scans at the end of the race window replacement.
function _mermaidRescanWhenReady() {
  if (typeof mermaid !== "undefined") { initMermaid(); return; }
  var script = document.querySelector('script[src*="mermaid"]');
  if (script) script.addEventListener('load', function () { initMermaid(); }, { once: true });
}
_mermaidRescanWhenReady();

Board.render.renderMd = renderMd;
Board.render.initMermaid = initMermaid;

// ── Dashboard Parsers ──

/**
 * Parses a token string like "1621k" to a number.
 * @param {string} val
 * @returns {number}
 */
function parseToken(val) {
  if (!val || val === "-") return 0;
  const cleaned = val.replace(/,/g, "").trim();
  if (cleaned.endsWith("k")) return parseFloat(cleaned) * 1000;
  return parseFloat(cleaned) || 0;
}

/**
 * Parses markdown table rows (skipping header and separator rows).
 * @param {string} text
 * @returns {Array<Array<string>>}
 */
function parseMdTableRows(text) {
  const rows = [];
  const lines = (text || "").split("\n");
  let inTable = false;
  let headerSeen = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line.startsWith("|")) {
      if (inTable) break;
      continue;
    }
    if (!inTable) { inTable = true; headerSeen = false; continue; }
    if (!headerSeen) { headerSeen = true; continue; }
    const cells = line.split("|").slice(1, -1).map(function (c) { return c.trim(); });
    rows.push(cells);
  }
  return rows;
}

/**
 * Extracts header cells from first markdown table in text.
 * @param {string} text
 * @returns {Array<string>}
 */
function parseMdTableHeader(text) {
  const lines = (text || "").split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith("|")) {
      return line.split("|").slice(1, -1).map(function (c) { return c.trim(); });
    }
  }
  return [];
}

/**
 * Formats token count to human-readable string (e.g. 1.6M, 500k).
 * @param {number} n
 * @returns {string}
 */
function formatTokens(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return Math.round(n / 1000) + "k";
  return String(Math.round(n));
}

Board.util.parseToken = parseToken;
Board.util.parseMdTableRows = parseMdTableRows;
Board.util.parseMdTableHeader = parseMdTableHeader;
Board.util.formatTokens = formatTokens;

// ── State Objects ──

/** Loads persisted UI state from localStorage. */
function loadUI() {
  try { return JSON.parse(localStorage.getItem(LS_KEY)) || {}; } catch (e) { return {}; }
}

const savedState = loadUI();

/** Migrates legacy tab history entries to object format. */
function migrateTabHistory(history) {
  return history.map(function (entry) {
    if (typeof entry === "string") return { tab: entry, viewerTab: null };
    return entry;
  });
}

// Initialize shared state
Board.state.WORK_REQUESTS = [];
Board.state.WORKFLOWS = [];
Board.state.COLUMNS = COLUMNS;
Board.state.viewerTabs = [];
Board.state.activeViewerTab = savedState.activeViewerTab || null;
Board.state.activeTab = (savedState.tab === "metrics" ? "dashboard" : (savedState.tab || "dashboard"));
Board.state.tabHistory = migrateTabHistory(savedState.tabHistory || []);
Board.state.forwardHistory = migrateTabHistory(savedState.forwardHistory || []);
Board.state.codeViewerStore = {};
Board.state.codeViewerIdCounter = 0;

// Workflow shared state (used by workflow.js and sse.js)
Board.state.wfEntryHrefs = [];
Board.state.wfLoadedIndex = 0;
Board.state.wfInitialized = false;
Board.state.wfSearchQuery = "";
Board.state.wfSortKey = "updated_at";
Board.state.wfSortDir = "desc";
Board.state.wfLoading = false;

// Dashboard shared state
Board.state.dashData = {};
Board.state.dashFetched = false;
Board.state.dashChartInstances = {};

// Conveyor sort state
Board.state.conveyorSort = null; // initialized by conveyor.js

// Roadmap subtab state — saveUI/loadUI by sequencing (active phase + unfolded card + side width).
// Contexts Tab (Former Prompt Tab) is used by Roadmap Sub tab — not a separate panel, so no panel Accepted.
Board.state.roadmap = (savedState.roadmap && typeof savedState.roadmap === "object")
  ? {
      activePhaseId: typeof savedState.roadmap.activePhaseId === "string"
        ? savedState.roadmap.activePhaseId
        : null,
      expandedCardIds: Array.isArray(savedState.roadmap.expandedCardIds)
        ? savedState.roadmap.expandedCardIds.slice()
        : [],
      sideWidth: typeof savedState.roadmap.sideWidth === "number"
        && savedState.roadmap.sideWidth >= 140 && savedState.roadmap.sideWidth <= 600
        ? savedState.roadmap.sideWidth
        : 240,
    }
  : {
      activePhaseId: null,
      expandedCardIds: [],
      sideWidth: 240,
    };

// Contexts tab integration status — saveUI/loadUI to zero.
// User Event (Swap Tab Switch, File Selection, Sidebar Width Adjustment, GC bar Toggle) is all updated
// The policy that should be restored after. Each subtab module reads here instead of the default hardcode.
(function () {
  var rawCx = (savedState.contexts && typeof savedState.contexts === "object")
    ? savedState.contexts : {};
  var ALLOWED_SUBTABS = { roadmap: 1, rules: 1, memory: 1, prompt: 1 };
  var sub = (typeof rawCx.subTab === "string" && ALLOWED_SUBTABS[rawCx.subTab])
    ? rawCx.subTab : "roadmap";
  function _ws(v, def) {
    if (typeof v === "number" && v >= 140 && v <= 600) return v;
    return def;
  }
  function _sub(o) {
    o = (o && typeof o === "object") ? o : {};
    return {
      activeFile: typeof o.activeFile === "string" ? o.activeFile : null,
      sidebarWidth: _ws(o.sidebarWidth, 280),
    };
  }
  var memorySub = _sub(rawCx.memory);
  memorySub.gcExpanded = !!(rawCx.memory && rawCx.memory.gcExpanded);
  memorySub.archiveCollapsed = (rawCx.memory && rawCx.memory.archiveCollapsed != null)
    ? !!rawCx.memory.archiveCollapsed
    : true;
  Board.state.contexts = {
    subTab: sub,
    memory: memorySub,
    rules: _sub(rawCx.rules),
    prompt: _sub(rawCx.prompt),
  };
})();

// Relations panel state — saveUI/loadUI by sequencing (open/close + filter)
Board.state.relations = (savedState.relations && typeof savedState.relations === "object")
  ? {
      filter: {
        statuses: Array.isArray(savedState.relations.filter && savedState.relations.filter.statuses)
          ? savedState.relations.filter.statuses
          : ["open", "progress", "review", "done"],
        direction: (savedState.relations.filter && savedState.relations.filter.direction) || "TD",
        showIsolated: !!(savedState.relations.filter && savedState.relations.filter.showIsolated),
      },
      panelAccepted: !!savedState.relations.panelAccepted,
    }
  : {
      filter: { statuses: ["open", "progress", "review", "done"], direction: "TD", showIsolated: false },
      panelAccepted: false,
    };

// ── UI State Persistence ──

/** Saves current UI state to localStorage. */
function saveUI() {
  const openNums = Board.state.viewerTabs.map(function (t) { return t.number; });
  const state = {
    tab: Board.state.activeTab,
    viewerTabs: openNums,
    activeViewerTab: Board.state.activeViewerTab,
    tabHistory: Board.state.tabHistory,
    forwardHistory: Board.state.forwardHistory,
    relations: Board.state.relations,
    roadmap: Board.state.roadmap,
    contexts: Board.state.contexts,
  };
  try { localStorage.setItem(LS_KEY, JSON.stringify(state)); } catch (e) {}
}

Board.util.saveUI = saveUI;
Board.util.loadUI = loadUI;

// ── Tab Switching ──

const tabs = document.querySelectorAll(".tab");
const views = document.querySelectorAll(".view");

/** Switches the active tab and triggers rendering for the target view. */
function switchTab(target, skipPush) {
  if (!skipPush && Board.state.activeTab) {
    Board.state.tabHistory.push({
      tab: Board.state.activeTab,
      viewerTab: Board.state.activeTab === "viewer" ? Board.state.activeViewerTab : null,
    });
    if (Board.state.tabHistory.length > 100) Board.state.tabHistory.shift();
    Board.state.forwardHistory.length = 0;
  }
  Board.state.activeTab = target;
  tabs.forEach(function (t) { t.classList.toggle("active", t.dataset.view === target); });
  views.forEach(function (v) { v.classList.toggle("active", v.id === "view-" + target); });
  if (target === "dashboard" && Board.render.renderDashboard) Board.render.renderDashboard();
  if (target === "conveyor" && Board.render.renderConveyor) Board.render.renderConveyor();
  if (target === "workflow" && Board.render.renderWorkflow) Board.render.renderWorkflow();
  if (target === "viewer" && Board.render.renderViewer) Board.render.renderViewer();
  if (target === "memory" && Board.render.renderMemory) Board.render.renderMemory();
  saveUI();
  if (Board.util.updateQueryString) Board.util.updateQueryString();
}

tabs.forEach(function (t) {
  t.addEventListener("click", function () { switchTab(t.dataset.view); });
});

Board.util.switchTab = switchTab;

// ── Query String Helpers ──

/** Updates URL query string to reflect current viewer state. */
function updateQueryString() {
  var params = new URLSearchParams(window.location.search);
  if (Board.state.activeTab === "viewer" && Board.state.activeViewerTab) {
    params.set("tab", "viewer");
    params.set("work_request", Board.state.activeViewerTab);
  } else {
    params.delete("tab");
    params.delete("work_request");
  }
  var qs = params.toString();
  var url = window.location.pathname + (qs ? "?" + qs : "");
  history.replaceState(null, "", url);
}
Board.util.updateQueryString = updateQueryString;

// ── Fetch Utilities ──

/**
 * Fetches a directory URL and returns .xml file names.
 * @param {string} dirUrl
 * @returns {Promise<string[]>}
 */
function fetchXmlList(dirUrl) {
  return fetch(dirUrl, { cache: "no-store" }).then(function (res) {
    if (!res.ok) return [];
    return res.text().then(function (html) {
      return parseDirLinks(html).files.filter(function (f) { return f.endsWith(".xml") && !f.includes("../") && !f.startsWith("/"); });
    });
  }).catch(function () { return []; });
}

Board.util.fetchXmlList = fetchXmlList;

// ── Branch Status Bar Helper ──
//
// git brand name and icon SVG on the status bar (`#terminal-sl-branch`).
// both terminal/workflow pages, page load point·SSE git branch event·
// /api/branch fetch update to a single helper anywhere.
//
// No-op on the status bar element page (conveyor/dashboard, etc.).
var BRANCH_ICON_SVG =
  '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
  + 'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
  + 'stroke-linejoin="round" style="vertical-align:-1px;margin-right:3px">'
  + '<circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>'
  + '<path d="M6 15V9a6 6 0 0 0 6-6h0a6 6 0 0 0 6 6"/></svg>';

function setBranchStatusBar(branchName) {
  if (!branchName) return;
  var el = document.getElementById("terminal-sl-branch");
  if (!el) return;
  el.innerHTML = BRANCH_ICON_SVG + branchName;
}

Board.util.setBranchStatusBar = setBranchStatusBar;
Board.util.BRANCH_ICON_SVG = BRANCH_ICON_SVG;

// ── Info Modal Helper ──
//
// Single-confirm-button informational modal.
// Replaces native alert() calls throughout the Board UI with an accessible,
// theme-consistent overlay.
//
// Usage:
//   Board.util.showInfoModal("Title", "Body text", { severity: "warning", onClose: fn });
//
// SVG icons per severity:
//   info    — circle with 'i' indicator (Lucide circle-info style)
//   warning — triangle alert (Lucide triangle-alert style)
//   error   — circle with 'x' (Lucide circle-x style)

var _infoModalCounter = 0;

var _INFO_MODAL_ICONS = {
  info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" '
    + 'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" '
    + 'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    + '<circle cx="12" cy="12" r="10"/>'
    + '<line x1="12" y1="16" x2="12" y2="12"/>'
    + '<line x1="12" y1="8" x2="12.01" y2="8"/>'
    + '</svg>',
  warning: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" '
    + 'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" '
    + 'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    + '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
    + '<line x1="12" y1="9" x2="12" y2="13"/>'
    + '<line x1="12" y1="17" x2="12.01" y2="17"/>'
    + '</svg>',
  error: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" '
    + 'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" '
    + 'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    + '<circle cx="12" cy="12" r="10"/>'
    + '<line x1="15" y1="9" x2="9" y2="15"/>'
    + '<line x1="9" y1="9" x2="15" y2="15"/>'
    + '</svg>',
};

/**
 * Displays an informational modal dialog with a single confirm button.
 *
 * Replaces native alert() calls throughout the Board UI with an accessible,
 * theme-consistent overlay. Supports three severity levels (info / warning / error)
 * with distinct SVG icons. Keyboard (ESC) and overlay-click dismissal are both
 * supported.
 *
 * @param {string} title - Dialog title text (required).
 * @param {string} body  - Dialog body text (required). Rendered as textContent — no HTML injection.
 * @param {Object} [options]
 * @param {Function} [options.onClose]     - Called when the modal is dismissed by any method.
 * @param {'info'|'warning'|'error'} [options.severity='info'] - Determines icon and modifier class.
 * @param {string} [options.confirmText='About Us'] - Label for the confirm button.
 */
function showInfoModal(title, body, options) {
  var opts = options || {};
  var severity = (opts.severity === 'warning' || opts.severity === 'error') ? opts.severity : 'info';
  var confirmText = opts.confirmText || 'About Us';
  var onClose = typeof opts.onClose === 'function' ? opts.onClose : null;

  var uid = 'info-modal-title-' + (++_infoModalCounter);

  // ── Build overlay ──
  var overlay = document.createElement('div');
  overlay.className = 'info-modal-overlay';

  // ── Build dialog ──
  var dialog = document.createElement('div');
  dialog.className = 'info-modal-dialog is-' + severity;
  dialog.setAttribute('role', 'dialog');
  dialog.setAttribute('aria-modal', 'true');
  dialog.setAttribute('aria-labelledby', uid);

  // ── Icon (static trusted SVG string — no user data interpolated) ──
  var iconEl = document.createElement('div');
  iconEl.className = 'info-modal-icon';
  iconEl.innerHTML = _INFO_MODAL_ICONS[severity];

  // ── Title ──
  var titleEl = document.createElement('h3');
  titleEl.className = 'info-modal-title';
  titleEl.id = uid;
  titleEl.textContent = title;

  // ── Body ──
  var bodyEl = document.createElement('p');
  bodyEl.className = 'info-modal-body';
  bodyEl.textContent = body;

  // ── Actions ──
  var actionsEl = document.createElement('div');
  actionsEl.className = 'info-modal-actions';

  var confirmBtn = document.createElement('button');
  confirmBtn.className = 'info-modal-btn is-' + severity;
  confirmBtn.textContent = confirmText;

  actionsEl.appendChild(confirmBtn);

  // ── Assemble dialog ──
  dialog.appendChild(iconEl);
  dialog.appendChild(titleEl);
  dialog.appendChild(bodyEl);
  dialog.appendChild(actionsEl);

  overlay.appendChild(dialog);

  // ── Cleanup function ──
  function closeModal() {
    document.removeEventListener('keydown', onKeyDown);
    if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    if (onClose) onClose();
  }

  // ── Event: ESC key ──
  function onKeyDown(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      closeModal();
    }
  }
  document.addEventListener('keydown', onKeyDown);

  // ── Event: overlay backdrop click (not dialog interior) ──
  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) closeModal();
  });

  // ── Event: confirm button click ──
  confirmBtn.addEventListener('click', closeModal);

  // ── Mount + auto-focus confirm button ──
  document.body.appendChild(overlay);
  confirmBtn.focus();
}

Board.util.showInfoModal = showInfoModal;
