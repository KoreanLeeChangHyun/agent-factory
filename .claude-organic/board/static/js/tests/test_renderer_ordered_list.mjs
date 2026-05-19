// Fixture test for renderer-helpers.mergeAdjacentOrderedLists + marked integration (T-321 P2).
//
// 검증 대상:
//   1) helper 단위 (mergeAdjacentOrderedLists) — 인접 <ol> 병합 / start 보존 / 비-인접 보존.
//   2) marked 통합 — `1. A\n2. B\n0. C` 와 비순차 시작 (`5. 6. 7.`) 이 단일 <ol> 부모 안 동일 depth.
//   3) marked 출력에서 텍스트 단락 끼인 분리 케이스 → helper 후처리로 인접 ol 병합.
//
// acceptance_criteria #1: 단일 ol 안 3 li 의 들여쓰기 일치 — 동일 부모 + 동일 CSS rule (.md-body ol).
// acceptance_criteria #2: 표준 1.2.3. 회귀 없음.
// acceptance_criteria #3: 비순차 (5.6.7., 0 시작) 도 단일 ol 동일 들여쓰기.

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
  // common.js renderMd 와 동일한 순서: unescape → marked → merge.
  const text = unescapeLiteralNewlines(md);
  const html = markedParse(text, { gfm: true, breaks: true });
  return mergeAdjacentOrderedLists(html);
}

// ── helper 단위 검증 ─────────────────────────────────────────────────────

// H-1: 인접 ol 병합
{
  const html = "<ol><li>A</li></ol>\n<ol start=\"2\"><li>B</li></ol>";
  const merged = mergeAdjacentOrderedLists(html);
  ok(countMatches(merged, /<ol\b/g) === 1, "H-1: adjacent ol merged into single ol",
     `merged=${JSON.stringify(merged)}`);
  ok(merged.includes("<li>A</li>") && merged.includes("<li>B</li>"),
     "H-1b: both li preserved");
}

// H-2: 비-인접 ol 은 보존 (사이에 텍스트 단락)
{
  const html = "<ol><li>A</li></ol>\n<p>text</p>\n<ol><li>B</li></ol>";
  const merged = mergeAdjacentOrderedLists(html);
  ok(countMatches(merged, /<ol\b/g) === 2, "H-2: ol separated by <p> kept separate");
}

// H-3: 3+ 연속 ol 모두 흡수
{
  const html = "<ol><li>A</li></ol><ol><li>B</li></ol><ol><li>C</li></ol>";
  const merged = mergeAdjacentOrderedLists(html);
  ok(countMatches(merged, /<ol\b/g) === 1, "H-3: 3 adjacent ol → single ol");
  ok(countMatches(merged, /<li>/g) === 3, "H-3b: 3 li preserved");
}

// H-4: idempotent (이미 단일 ol)
{
  const html = "<ol><li>A</li><li>B</li><li>C</li></ol>";
  const merged = mergeAdjacentOrderedLists(html);
  ok(merged === html, "H-4: idempotent");
}

// H-5: null/undefined graceful
ok(mergeAdjacentOrderedLists(null) === null, "H-5-null");
ok(mergeAdjacentOrderedLists(undefined) === undefined, "H-5-undefined");

// ── marked 통합 검증 (acceptance_criteria) ───────────────────────────────

// A: 입력 '1. A\n2. B\n0. C' — 단일 ol 안 3 li 동일 부모 (동일 들여쓰기)
{
  const html = render("1. A\n2. B\n0. C");
  ok(countMatches(html, /<ol\b/g) === 1, "A-1: 1.2.0. → 단일 ol",
     `html=${JSON.stringify(html)}`);
  ok(countMatches(html, /<li>/g) === 3, "A-2: 3 li 보존");
  // 단일 ol 부모 안 같은 depth 확인: 모든 li 가 단일 ol close 전에 등장
  const olOpen = html.indexOf("<ol");
  const olClose = html.indexOf("</ol>");
  const liPositions = [];
  let idx = 0;
  while ((idx = html.indexOf("<li>", idx)) !== -1) { liPositions.push(idx); idx += 4; }
  ok(liPositions.every(p => p > olOpen && p < olClose),
     "A-3: 모든 li 가 단일 ol 부모 안 (동일 depth)",
     `olOpen=${olOpen} olClose=${olClose} li=${liPositions}`);
}

// B: 표준 1. 2. 3. 회귀 없음
{
  const html = render("1. A\n2. B\n3. C");
  ok(countMatches(html, /<ol\b/g) === 1, "B-1: 1.2.3. → 단일 ol");
  ok(countMatches(html, /<li>/g) === 3, "B-2: 3 li");
  // 표준 입력은 start attribute 없음 (default 1)
  ok(!html.match(/<ol\s+start=/), "B-3: 표준 입력 start attribute 부재", `html=${html}`);
}

// C: 비순차 시작 5. 6. 7.
{
  const html = render("5. A\n6. B\n7. C");
  ok(countMatches(html, /<ol\b/g) === 1, "C-1: 5.6.7. → 단일 ol");
  ok(countMatches(html, /<li>/g) === 3, "C-2: 3 li");
  // start=5 보존 (시작 번호 유지)
  ok(/<ol\s+start="5"/.test(html), "C-3: start=\"5\" 보존", `html=${html}`);
}

// D: 0 시작
{
  const html = render("0. A\n0. B\n0. C");
  ok(countMatches(html, /<ol\b/g) === 1, "D-1: 0.0.0. → 단일 ol");
  ok(countMatches(html, /<li>/g) === 3, "D-2: 3 li");
  ok(/<ol\s+start="0"/.test(html), "D-3: start=\"0\" 보존");
}

// E: 텍스트 단락이 끼었지만 helper 병합으로 단일 ol 으로 흡수되는 케이스
//    — marked 가 두 ol 로 분리한 뒤 helper 가 인접한 (텍스트 비포함) ol 만 병합. 이 케이스는 helper 가 병합하지 않음.
{
  const html = render("1. A\n2. B\n\ntext between\n\n3. C\n4. D");
  // 텍스트 단락 사이에 끼었으므로 2 ol 유지 — 사용자 의도 보존 (별개 list).
  ok(countMatches(html, /<ol\b/g) === 2, "E-1: 텍스트 단락 사이 ol 은 분리 유지");
  ok(html.includes("<p>text between</p>"), "E-2: 텍스트 단락 보존");
}

// F: 리터럴 \n 입력 (P1 연계) — flow-kanban XML 필드 시뮬레이션
{
  const html = render("1. A\\n2. B\\n0. C");
  ok(countMatches(html, /<ol\b/g) === 1, "F-1: 리터럴 \\n 입력도 단일 ol",
     `html=${JSON.stringify(html)}`);
  ok(countMatches(html, /<li>/g) === 3, "F-2: 3 li (P1 unescape + ol 단일화 연계)");
}

console.log("\nALL PASS — test_renderer_ordered_list.mjs");
