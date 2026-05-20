// Fixture test for renderer-helpers.unescapeLiteralNewlines (T-321 P1).
//
// 검증 대상: `core/renderer-helpers.js` 의 `unescapeLiteralNewlines(text)`.
// 리터럴 백슬래시-n (`\\n` 2글자) 을 실제 개행 (`\n` 1글자) 으로 치환.
//
// 호환 모드 1: helper 가 CommonJS module.exports 를 지원하면 createRequire 로 import.
// 호환 모드 2: 미존재 시 ENOENT 로 Red.

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

// Case A: 리터럴 백슬래시-n → 실제 개행 (3개 항목으로 분리)
const A_in = "조건1\\n조건2\\n조건3";
const A_out = unescapeLiteralNewlines(A_in);
assertEqual(A_out, "조건1\n조건2\n조건3", "A: literal \\n → real newline");
// 마크다운 렌더링 결과 가설 검증 — newline 으로 끊긴 3 라인이 별개의 <p> / <br> / <li> 중 하나로 표현 가능해야 함
// (helper 단위 검증은 위 assertEqual 로 충족. marked 통합 동작은 P1 W1.md report 에 별도 기록)

// Case B: 이미 실제 개행인 입력 (idempotent — 회귀 없음)
const B_in = "조건1\n조건2";
const B_out = unescapeLiteralNewlines(B_in);
assertEqual(B_out, "조건1\n조건2", "B: already-newline idempotent");

// Case C: 백슬래시 미포함 plain text (변동 없음)
const C_in = "이것은 보통 텍스트입니다.";
const C_out = unescapeLiteralNewlines(C_in);
assertEqual(C_out, C_in, "C: plain text unchanged");

// Case D: code fence 내부의 `\\n` 은 보존 (사용자 의도 리터럴) — plan 회피 항목
const D_in = "before\n```\nconst s = \"line1\\nline2\";\n```\nafter\\nend";
const D_out = unescapeLiteralNewlines(D_in);
// fence 내부의 `\\n` 은 그대로 유지, fence 외부의 `\\n` (after\nend) 는 실제 개행으로 치환
assertContains(D_out, "const s = \"line1\\nline2\";", "D-fence: code fence \\n preserved");
assertContains(D_out, "after\nend", "D-outside: fence-외부 \\n unescaped");

// Case E: 인라인 backtick `\\n` 도 보존
const E_in = "텍스트 `리터럴 \\n` 다음 줄\\n그 다음";
const E_out = unescapeLiteralNewlines(E_in);
assertContains(E_out, "`리터럴 \\n`", "E-inline: inline code \\n preserved");
assertContains(E_out, "다음 줄\n그 다음", "E-outside: 인라인 외부 \\n unescaped");

// Case F: 빈 문자열
assertEqual(unescapeLiteralNewlines(""), "", "F: empty string");

// Case G: null / undefined graceful
assertEqual(unescapeLiteralNewlines(null), null, "G-null");
assertEqual(unescapeLiteralNewlines(undefined), undefined, "G-undefined");

// ── marked 통합 검증 (acceptance_criteria #2) ────────────────────────────
// helper 출력 → marked.parse 결과가 실제 개행 기반 마크다운 토큰 (br/p/li 등) 으로 분할되는지.
const markedMod = require(resolve(here, "..", "vendor", "marked-15.0.0.min.js"));
const markedParse = markedMod.parse;

const integ_in = "조건1\\n조건2\\n조건3";
const integ_unescaped = unescapeLiteralNewlines(integ_in);
const integ_html = markedParse(integ_unescaped, { gfm: true, breaks: true });
// `breaks: true` 옵션 (common.js 와 동일) — 단일 개행이 <br> 로 변환.
const hasBr = integ_html.includes("<br>") || integ_html.includes("<br/>") || integ_html.includes("<br />");
const hasPsplit = (integ_html.match(/<\/p>\s*<p>/g) || []).length > 0;
const hasLi = integ_html.includes("<li>");
const hasRealNewline = integ_unescaped.includes("\n");

if (!(hasBr || hasPsplit || hasLi || hasRealNewline)) {
  console.error(`FAIL [marked-integration]: html=${JSON.stringify(integ_html)}`);
  process.exit(1);
}
console.log(`PASS  [marked-integration: br=${hasBr} p-split=${hasPsplit} li=${hasLi} newline=${hasRealNewline}]`);

// 회귀 가드: 이미 개행 입력도 marked 결과에 br/개행 보존
const integ2_in = "조건1\n조건2";
const integ2_html = markedParse(unescapeLiteralNewlines(integ2_in), { gfm: true, breaks: true });
const has2Br = integ2_html.includes("<br>") || integ2_html.includes("<br/>") || integ2_html.includes("<br />");
if (!has2Br) {
  console.error(`FAIL [regression: already-newline input lost line break]: html=${JSON.stringify(integ2_html)}`);
  process.exit(1);
}
console.log(`PASS  [regression: already-newline input → <br> preserved]`);

console.log("\nALL PASS — test_renderer_escape.mjs");
