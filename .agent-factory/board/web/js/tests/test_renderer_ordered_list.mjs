// Fixture test for renderer-helpers.mergeAdjacentOrderedLists + marked integration (T-321 P2).
//
// Verified by:
//   1) helper unit (mergeAdjacentOrderedLists) — merge adjacent <ol> / preserve start / preserve non-adjacent.
//   2) marked integration — `1. A \n 2. B \n 0. C` and non-sequential start (`5.6.7.`) This single <ol> parent does not have the same depth.
//   3) Case of separation between text paragraphs in marked output → Merge adjacent ols with helper post-processing.
//
// acceptance_criteria #1: Indentation match of 3 li in single ol — same parent + same CSS rule (.md-body ol).
// acceptance_criteria #2: Standard 1.2.3. No regression.
// acceptance_criteria #3: Non-sequential (5.6.7., 0-start) also single ol same indentation.

import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const helperPath = resolve(here, "..", "core", "renderer-helpers.js");
const markedPath = resolve(here, "..", "vendor", "marked-15.0.0.min.js");
const require = createRequire(import.meta.url);
const { unescapeLiteralNewlines, mergeAdjacentOrderedLists } = require(helperPath);
const { parse: markedParse } = require(markedPath);

function ok(cond, label, detail) {
  if (!cond) {
    console.error(`FAIL [${label}]${detail ? "\n  " + detail : ""}`);
    process.exit(1);
  }
  console.log(`PASS  [${label}]`);
}

function countMatches(s, re) {
  return (s.match(re) || []).length;
}

function render(md) {
  // Same order as common.js renderMd: unescape → marked → merge.
  const text = unescapeLiteralNewlines(md);
  const html = markedParse(text, { gfm: true, breaks: true });
  return mergeAdjacentOrderedLists(html);
}

// ── helper unit verification ───────────────────────────────────────────────────────

// H-1: Merge adjacent ols
{
  const html = "<ol><li>A</li></ol>\n<ol start=\"2\"><li>B</li></ol>";
  const merged = mergeAdjacentOrderedLists(html);
  ok(countMatches(merged, /<ol\b/g) === 1, "H-1: adjacent ol merged into single ol",
     `merged=${JSON.stringify(merged)}`);
  ok(merged.includes("<li>A</li>") && merged.includes("<li>B</li>"),
     "H-1b: both li preserved");
}

// H-2: Non-adjacent OLs are preserved (text paragraphs between them)
{
  const html = "<ol><li>A</li></ol>\n<p>text</p>\n<ol><li>B</li></ol>";
  const merged = mergeAdjacentOrderedLists(html);
  ok(countMatches(merged, /<ol\b/g) === 2, "H-2: ol separated by <p> kept separate");
}

// H-3: Absorb all 3+ consecutive OLs
{
  const html = "<ol><li>A</li></ol><ol><li>B</li></ol><ol><li>C</li></ol>";
  const merged = mergeAdjacentOrderedLists(html);
  ok(countMatches(merged, /<ol\b/g) === 1, "H-3: 3 adjacent ol → single ol");
  ok(countMatches(merged, /<li>/g) === 3, "H-3b: 3 li preserved");
}

// H-4: idempotent (already single OL)
{
  const html = "<ol><li>A</li><li>B</li><li>C</li></ol>";
  const merged = mergeAdjacentOrderedLists(html);
  ok(merged === html, "H-4: idempotent");
}

// H-5: null/undefined graceful
ok(mergeAdjacentOrderedLists(null) === null, "H-5-null");
ok(mergeAdjacentOrderedLists(undefined) === undefined, "H-5-undefined");

// ── marked integrated verification (acceptance_criteria) ────────────────────────────────

// A: Input '1. A \n 2. B \n 0. C' — single ol not 3 li same parent (same indentation)
{
  const html = render("1. A\n2. B\n0. C");
  ok(countMatches(html, /<ol\b/g) === 1, "A-1: 1.2.0. → single ol",
     `html=${JSON.stringify(html)}`);
  ok(countMatches(html, /<li>/g) === 3, "A-2: 3 li conservation");
  // Checking the same depth within a single ol parent: all li appear before a single ol close
  const olOpen = html.indexOf("<ol");
  const olClose = html.indexOf("</ol>");
  const liPositions = [];
  let idx = 0;
  while ((idx = html.indexOf("<li>", idx)) !== -1) { liPositions.push(idx); idx += 4; }
  ok(liPositions.every(p => p > olOpen && p < olClose),
     "A-3: All li are in a single ol parent (same depth)",
     `olOpen=${olOpen} olClose=${olClose} li=${liPositions}`);
}

// B: Standard 1. 2. 3. No regression
{
  const html = render("1. A\n2. B\n3. C");
  ok(countMatches(html, /<ol\b/g) === 1, "B-1: 1.2.3. → single ol");
  ok(countMatches(html, /<li>/g) === 3, "B-2: 3 li");
  // Standard input has no start attribute (default 1)
  ok(!html.match(/<ol\s+start=/), "B-3: Absence of standard input start attribute", `html=${html}`);
}

// C: Out-of-order start 5. 6. 7.
{
  const html = render("5. A\n6. B\n7. C");
  ok(countMatches(html, /<ol\b/g) === 1, "C-1: 5.6.7. → single ol");
  ok(countMatches(html, /<li>/g) === 3, "C-2: 3 li");
  // keep start=5 (keep start number)
  ok(/<ol\s+start="5"/.test(html), "C-3: Preserve start=\\"5\\"", `html=${html}`);
}

// D: 0 start
{
  const html = render("0. A\n0. B\n0. C");
  ok(countMatches(html, /<ol\b/g) === 1, "D-1: 0.0.0. → single ol");
  ok(countMatches(html, /<li>/g) === 3, "D-2: 3 li");
  ok(/<ol\s+start="0"/.test(html), "D-3: Preserve start=\\"0\\"");
}

// E: Case where there is a text paragraph, but it is absorbed into a single ol by merging the helper.
//    — After marked is separated into two ols, helper merges only the adjacent ols (excluding text). This case is not merged by helper.
{
  const html = render("1. A\n2. B\n\ntext between\n\n3. C\n4. D");
  // It's sandwiched between paragraphs of text, so keep 2 ol — preserving user intent (separate list).
  ok(countMatches(html, /<ol\b/g) === 2, "E-1: Maintain ol separation between text paragraphs");
  ok(html.includes("<p>text between</p>"), "E-2: Preserve text paragraphs");
}

// F: Input literal \n (P1 association) — flow-kanban XML field simulation
{
  const html = render("1. A\\n2. B\\n0. C");
  ok(countMatches(html, /<ol\b/g) === 1, "F-1: Literal \n input is also a single ol",
     `html=${JSON.stringify(html)}`);
  ok(countMatches(html, /<li>/g) === 3, "F-2: 3 li (P1 unescape + ol unification linkage)");
}

console.log("\nALL PASS — test_renderer_ordered_list.mjs");
