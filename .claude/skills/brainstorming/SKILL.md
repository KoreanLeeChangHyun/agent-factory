---
name: brainstorming
description: "신규 기능 컨셉을 티켓 생성 직전 단계까지 정리할 때 호출. grill-me 와 짝을 이뤄 컨셉 탐색에 집중. 트리거: '브레인스토밍', '아이디어 정리', '컨셉 잡아줘', '구상 도와줘', 모호한 신규 기능 발화."
license: "MIT (derived, partial)"
---

# Brainstorming (컨셉 정리)

신규 기능 아이디어가 명확한 티켓 생성 단계로 진입하기 전, 큰 그림을 사용자와 함께 정리하기 위한 스킬입니다. 무거운 디자인 강제 단계는 본 프로젝트 캐논과 충돌하므로 폐기하고, 컨셉 탐색·인터뷰 합류·근본 1안 추천 부분만 본 프로젝트 톤으로 재해석합니다.

## 1. 사용 시기

- 신규 기능 컨셉 탐색 (구체 요구사항 도출 직전 단계)
- `grill-me` 호출 전 큰 그림이 더 필요한 상태 (스코프·목적·성공 기준이 미정)
- 티켓 생성 직전 정리 — 한 줄 요약·산출물 형태·우선순위가 모호한 경우

## 2. grill-me 와의 관계

`grill-me` 는 인터뷰(질문)에 특화, `brainstorming` 은 컨셉 정리(큰 그림)에 특화합니다. 컨셉이 모이면 `grill-me` 또는 `flow-kanban create --status todo` 로 인계합니다.

## 3. 호출 흐름 (4단계 압축)

외부 원본의 9단계 체크리스트는 본 프로젝트에 과합니다. 다음 4단계로 압축합니다.

1. **도구 우선 컨텍스트 탐색** — `flow-kanban list/show/board`, `git worktree list`, `git log --oneline -20`, `MEMORY.md` (auto memory) 조회로 답할 수 있는 정보는 사용자에게 묻지 않습니다.
2. **1~2개 인터뷰** — 도구로 답을 알 수 없는 결정점만 자연어로 한 번에 1~2개 묻습니다 (메뉴 형태 금지).
3. **추천 1안 제시** — 옵션 나열 회피, 근본 1안 우선. 정말 필요할 때만 1~3개 단순화하고 추천 1안을 명시합니다.
4. **인계** — 합의되면 `grill-me` (세부 인터뷰 필요 시) 또는 `flow-kanban create --status todo` (바로 티켓 생성 가능 시) 로 넘깁니다.

## 4. 묻는 대상 / 묻지 않는 대상

룰 정의의 단일 진실 공급원은 `.claude/rules/workflow/workflow.md` (티켓 생성 규칙 + DO 인터뷰 룰) 입니다. 본 스킬에서 보충하는 컨셉 정리용 결정점은 다음과 같습니다.

- **묻는 대상** (workflow.md 인터뷰 룰 + 보충): 작업 범위 / 산출물 형태 / 제약 / 우선순위 / 목적 / 성공 기준
- **묻지 않는 대상** (workflow.md 동일): 티켓 상태(자동 To Do), 기본 생성 옵션(기본값), 1=A/2=B 메뉴 형태

## 5. 본 프로젝트에서 채택하지 않는 항목 (회귀 차단 티켓 생성)

외부 원본(`superpowers/skills/brainstorming/SKILL.md`, MIT, Jesse Vincent 2025)의 다음 항목은 본 프로젝트 캐논과 충돌하여 채택하지 않습니다. 미래 회귀 방지를 위해 명시 티켓 생성합니다.

1. **HARD-GATE 디자인 강제 단계** — 사용자 명시 동의 없는 자동 강제 정책 도입 금지 캐논과 충돌 (auto memory `feedback_no_speculative_guards_2026-05-08`).
2. **spec-document-reviewer 서브에이전트 호출** — 메인 세션 서브에이전트 사용 금지 캐논과 충돌 (`.claude/rules/workflow/general.md` 메인 세션 제약).
3. **자동 commit 디자인 문서** — destructive 행위는 사용자 명시 동의 필수 캐논과 충돌.
4. **9단계 체크리스트** — 본 프로젝트는 4단계 압축 (3절 참조). 무거운 강제 흐름 회피.
5. **"2-3 접근법 항상 제안" 강제** — 본 프로젝트는 근본 1안 우선 캐논 (auto memory `synthesis_user_interaction_canon` §3 Root Cause First).
6. **writing-plans 위임** — 본 프로젝트는 `flow-kanban create --status todo` → `/wf -s N` 워크플로우가 단일 진입점.

## 6. 출처

- 원본: `/home/deus/workspace/claude/.repo/superpowers/skills/brainstorming/SKILL.md` (MIT License, Jesse Vincent, 2025)
- 인용 형태: **부분 차용 (컨셉만), 무거운 부분 폐기**.
- 변경 요약: 한국어/존댓말로 재작성, 9단계 → 4단계 압축, HARD-GATE/spec-reviewer/자동 commit/2-3 접근법 강제/writing-plans 위임 폐기, 본 프로젝트 도구(`flow-kanban`, `git worktree`, auto memory)로 컨텍스트 탐색 매핑, `grill-me` 와의 dual-skill 관계 명시.

## 7. 시스템 스킬 분류

본 스킬은 `my-*` 접두사가 아니므로 **시스템 스킬**(`.claude/ 갱신 정책` 의 갱신 대상)에 해당합니다 (`CLAUDE.md` 참조). `disable-model-invocation` 키는 미설정 상태로 두어 자동 호출이 가능합니다.
