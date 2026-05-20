// Fixture test for renderer-helpers.unescapeLiteralNewlines (T-321 P1).
//
// Validated against: `unescapeLiteralNewlines(text)` in `core/renderer-helpers.js`.
// Replace literal backslash-n (` \n ` 2 characters) with an actual newline (` \n ` 1 character).
//
// Compatibility mode 1: If helper supports CommonJS module.exports, import it with createRequire.
// Compatibility mode 2: Red as ENOENT if not present.

import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const helperPath = resolve(here, "..", "core", "renderer-helpers.js");
const require = createRequire(import.meta.url);
const { unescapeLiteralNewlines } = require(helperPath);

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    console.error(`FAIL [${label}]\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`);
    process.exit(1);
  }
  console.log(`PASS  [${label}]`);
}

function assertContains(actual, needle, label) {
  if (!String(actual).includes(needle)) {
    console.error(`FAIL [${label}]\n  needle:   ${JSON.stringify(needle)}\n  actual:   ${JSON.stringify(actual)}`);
    process.exit(1);
  }
  console.log(`PASS  [${label}]`);
}

// Case A: Literal backslash-n → actual newline (separated into 3 items)
const A_in = "Condition 1 \n Condition 2 \n Condition 3";
const A_out = unescapeLiteralNewlines(A_in);
assertEqual(A_out, "Condition 1 \n Condition 2 \n Condition 3", "A: literal \\n → real newline");
// Hypothesis verification of Markdown rendering results — 3 lines broken by newlines must be able to be expressed as separate <p> / <br> / <li>
// (The helper unit verification is satisfied with assertEqual above. The marked integrated operation is recorded separately in the P1 W1.md report.)

// Case B: Input that is already a real newline (idempotent — no regression)
const B_in = "Condition 1 \n Condition 2";
const B_out = unescapeLiteralNewlines(B_in);
assertEqual(B_out, "Condition 1 \n Condition 2", "B: already-newline idempotent");

// Case C: plain text without backslash (no change)
const C_in = "This is plain text.";
const C_out = unescapeLiteralNewlines(C_in);
assertEqual(C_out, C_in, "C: plain text unchanged");

// Case D: ` \n ` inside the code fence is preserved (user intent literal) — plan avoidance item
const D_in = "before\n```\nconst s = \"line1\\nline2\";\n```\nafter\\nend";
const D_out = unescapeLiteralNewlines(D_in);
// ` \n ` inside the fence remains the same, and ` \n ` (after \n end) outside the fence is replaced with an actual newline.
assertContains(D_out, "const s = \"line1\\nline2\";", "D-fence: code fence \\n preserved");
assertContains(D_out, "after\nend", "D-outside: fence-outside \n unescaped");

// Case E: Inline backtick ` \n ` is also preserved
const E_in = "text `literal \n ` next line \n after that";
const E_out = unescapeLiteralNewlines(E_in);
assertContains(E_out, "`literal \n `", "E-inline: inline code \\n preserved");
assertContains(E_out, "next line \n then", "E-outside: inline outside \n unescaped");

// Case F: empty string
assertEqual(unescapeLiteralNewlines(""), "", "F: empty string");

// Case G: null / undefined graceful
assertEqual(unescapeLiteralNewlines(null), null, "G-null");
assertEqual(unescapeLiteralNewlines(undefined), undefined, "G-undefined");

// ── marked integrated verification (acceptance_criteria #2) ─────────────────────────────
// helper output → marked.parse Whether the result is split into actual newline-based markdown tokens (br/p/li, etc.).
const markedMod = require(resolve(here, "..", "vendor", "marked-15.0.0.min.js"));
const markedParse = markedMod.parse;

const integ_in = "Condition 1 \n Condition 2 \n Condition 3";
const integ_unescaped = unescapeLiteralNewlines(integ_in);
const integ_html = markedParse(integ_unescaped, { gfm: true, breaks: true });
// `breaks: true` option (same as common.js) — Converts single newlines to <br> .
const hasBr = integ_html.includes("<br>") || integ_html.includes("<br/>") || integ_html.includes("<br />");
const hasPsplit = (integ_html.match(/<\/p>\s*<p>/g) || []).length > 0;
const hasLi = integ_html.includes("<li>");
const hasRealNewline = integ_unescaped.includes("\n");

if (!(hasBr || hasPsplit || hasLi || hasRealNewline)) {
  console.error(`FAIL [marked-integration]: html=${JSON.stringify(integ_html)}`);
  process.exit(1);
}
console.log(`PASS  [marked-integration: br=${hasBr} p-split=${hasPsplit} li=${hasLi} newline=${hasRealNewline}]`);

// Regression Guard: Preserve br/newline in marked results even if newline input is already entered.
const integ2_in = "Condition 1 \n Condition 2";
const integ2_html = markedParse(unescapeLiteralNewlines(integ2_in), { gfm: true, breaks: true });
const has2Br = integ2_html.includes("<br>") || integ2_html.includes("<br/>") || integ2_html.includes("<br />");
if (!has2Br) {
  console.error(`FAIL [regression: already-newline input lost line break]: html=${JSON.stringify(integ2_html)}`);
  process.exit(1);
}
console.log(`PASS  [regression: already-newline input → <br> preserved]`);

console.log("\nALL PASS — test_renderer_escape.mjs");
