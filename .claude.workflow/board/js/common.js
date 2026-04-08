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

// ── Constants ──
const COLUMNS = [
  { key: "Open", label: "Open", dot: "dot-open" },
  { key: "In Progress", label: "In Progress", dot: "dot-progress" },
  { key: "Review", label: "Review", dot: "dot-review" },
  { key: "Done", label: "Done", dot: "dot-done" },
];

const CMD_COLORS = {
  implement: { bg: "rgba(86,156,214,0.3)", fg: "#7bb8e8" },
  review: { bg: "rgba(197,134,192,0.3)", fg: "#d9a0d6" },
  research: { bg: "rgba(220,220,170,0.3)", fg: "#e8e8b0" },
  prompt: { bg: "rgba(160,160,160,0.2)", fg: "#a0a0a0" },
};

const STATUS_COLORS = {
  Open: { bg: "rgba(78,201,176,0.15)", fg: "#4ec9b0" },
  Submit: { bg: "rgba(86,156,214,0.15)", fg: "#569cd6" },
  "In Progress": { bg: "rgba(220,220,170,0.15)", fg: "#dcdcaa" },
  Review: { bg: "rgba(197,134,192,0.15)", fg: "#c586c0" },
  Done: { bg: "rgba(133,133,133,0.15)", fg: "#858585" },
};

const LS_KEY = "claude-board-ui";
const KANBAN_SORT_LS_KEY = "claude-board-kanban-sort";

// Register constants on Board.util for cross-module access
Board.util.COLUMNS = COLUMNS;
Board.util.CMD_COLORS = CMD_COLORS;
Board.util.STATUS_COLORS = STATUS_COLORS;
Board.util.LS_KEY = LS_KEY;
Board.util.KANBAN_SORT_LS_KEY = KANBAN_SORT_LS_KEY;

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
Board.util.badge = badge;

// ── XML Ticket Parsing ──

/** Parses a ticket XML string into a ticket data object. */
function parseTicket(text) {
  const doc = new DOMParser().parseFromString(text, "text/xml");
  const root = doc.querySelector("ticket");
  if (!root) return null;

  const meta = root.querySelector("metadata");
  const ticket = {
    number: "", title: "", datetime: "", status: "Open",
    command: "", prompt: null, result: null,
    relations: [],
  };

  if (meta) {
    ["number", "title", "datetime", "status"].forEach(function (f) {
      const el = meta.querySelector(f);
      if (el && el.textContent) ticket[f] = el.textContent.trim();
    });
    const cmdEl = meta.querySelector("command");
    if (cmdEl) ticket.command = (cmdEl.textContent || "").trim();
  }

  // Flat structure: <prompt> directly under <ticket>
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
    if (Object.keys(prompt).length > 0) ticket.prompt = prompt;
  }

  // Flat structure: <result> directly under <ticket>
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
    if (Object.keys(rObj).length > 0) ticket.result = rObj;
  }

  // Legacy done ticket fallback (read-only): <submit>/<subnumber> structure
  if (!ticket.prompt && !ticket.command) {
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
        if (legacyCmd) ticket.command = legacyCmd.trim();
        var legacyPromptEl = activeSub.querySelector("prompt");
        if (legacyPromptEl) {
          var lp = {};
          for (var lpi = 0; lpi < legacyPromptEl.children.length; lpi++) {
            var lc = legacyPromptEl.children[lpi];
            var lt = (lc.textContent || "").trim();
            if (lt) lp[lc.tagName] = lt;
          }
          if (Object.keys(lp).length > 0) ticket.prompt = lp;
        }
        var legacyResultEl = activeSub.querySelector("result");
        if (legacyResultEl) {
          var lr = {};
          for (var lri = 0; lri < legacyResultEl.children.length; lri++) {
            var lrc = legacyResultEl.children[lri];
            var lrt = (lrc.textContent || "").trim();
            if (lrt) lr[lrc.tagName.toLowerCase()] = lrt;
          }
          if (Object.keys(lr).length > 0) ticket.result = lr;
        }
      }
    }
  }

  const relationsEl = root.querySelector("relations");
  if (relationsEl) {
    const rels = relationsEl.querySelectorAll("relation");
    for (let k = 0; k < rels.length; k++) {
      const type = rels[k].getAttribute("type") || "";
      const relTicket = rels[k].getAttribute("ticket") || "";
      if (type && relTicket) ticket.relations.push({ type: type, ticket: relTicket });
    }
  }

  return ticket;
}

Board.util.parseTicket = parseTicket;

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
 * When a workflow is archived to .history/, ticket XML still holds the original
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

/**
 * Returns the project root URL path.
 * Board page is at <root>/.claude.workflow/board/index.html.
 * Strips .claude.workflow/board/ from the current path to find the root.
 */
function projectRoot() {
  var path = window.location.pathname;
  var idx = path.indexOf(".claude.workflow/board/");
  if (idx !== -1) return path.substring(0, idx);
  // fallback
  return "../../";
}

/**
 * Builds a full URL path from a .claude.workflow/ relative path.
 * @param {string} wfPath - Path starting with .claude.workflow/ or workflow/
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
  const blocks = document.querySelectorAll(".mermaid-block");
  blocks.forEach(function (block) {
    const id = block.dataset.mermaidId;
    if (block.dataset.rendered) return;
    block.dataset.rendered = "true";
    const code = block.textContent;
    if (typeof mermaid !== "undefined") {
      mermaid.render(id, code).then(function (result) {
        block.innerHTML = result.svg;
      }).catch(function (err) {
        console.warn('[initMermaid] Mermaid render failed for id=' + id + ':', err);
        cleanupMermaidOrphans(id);
        block.innerHTML = '<pre class="wf-file-content">' + esc(code) + '</pre>';
      });
    }
  });
}

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
Board.state.TICKETS = [];
Board.state.WORKFLOWS = [];
Board.state.COLUMNS = COLUMNS;
Board.state.viewerTabs = [];
Board.state.activeViewerTab = savedState.activeViewerTab || null;
Board.state.activeTab = savedState.tab || "dashboard";
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

// Kanban sort state
Board.state.kanbanSort = null; // initialized by kanban.js

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
    params.set("ticket", Board.state.activeViewerTab);
  } else {
    params.delete("tab");
    params.delete("ticket");
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

