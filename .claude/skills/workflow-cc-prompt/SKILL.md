---
name: workflow-cc-prompt
description: "Workflow command skill for cc:prompt. Refines .prompt/prompt.txt content through interactive Q&A. Standalone command independent of workflow FSM/guards/sub-agents."
disable-model-invocation: true
skills:
  - research-prompt-engineering
---

# Prompt Command (Prompt Refinement)

`.prompt/prompt.txt`의 프롬프트를 대화형 질의응답으로 정제하는 워크플로우 커맨드 스킬. 워크플로우(FSM/가드/서브에이전트)와 무관한 독립 명령어.

## 스킬 참조

이 명령어는 `research-prompt-engineering` 스킬을 사용한다. 분석 시작 전 `.claude/skills/research-prompt-engineering/SKILL.md`를 로드하고, 필요 시 하위 references도 참조한다.

## 실행 흐름

### 1. prompt.txt 읽기

`.prompt/prompt.txt`를 읽는다. 빈 파일/공백만 있는 경우 안내 메시지 후 종료.

### 1.5. 스킬 로드

`research-prompt-engineering` 스킬에서 모호성 분석 체크리스트, 프롬프트 구조화 5요소, 핵심 원칙을 로드한다.

용도 판별:

| 용도 키워드 | 추가 로드 대상 |
|------------|---------------|
| 구현, 기능, 함수, 모듈 | `references/prompt-templates.md` (기능 구현 템플릿) |
| 버그, 오류, 에러, 수정 | `references/prompt-templates.md` (버그 수정 템플릿) |
| 리팩토링, 정리, 분리 | `references/prompt-templates.md` (리팩토링 템플릿) |
| 리뷰, 검토 | `references/prompt-templates.md` (코드 리뷰 템플릿) |
| 조사, 비교, 연구 | `references/prompt-templates.md` (연구 조사 템플릿) |
| 설계, 아키텍처, 시스템 | `references/prompt-templates.md` (아키텍처 설계 템플릿) |
| 에이전트, 서브에이전트, 도구 | `references/claude-code-patterns.md` (Claude Code 특화 패턴) |

### 2. 현재 내용 표시 및 분석

스킬의 모호성 분석 체크리스트(5대 모호성 유형)와 자가 점검 체크리스트(7개 항목)를 기준으로 분석.

| # | 모호성 유형 | 판단 기준 |
|---|------------|----------|
| 1 | 대상 불명확 | 작업 대상 파일/컴포넌트/모듈이 특정되지 않음 |
| 2 | 요구사항 불완전 | 원하는 동작/결과가 구체적으로 기술되지 않음 |
| 3 | 컨텍스트 부족 | 배경 정보, 제약 조건, 기술 스택 등이 누락됨 |
| 4 | 범위 미정의 | 여러 해석이 가능한 요청, 무제한적 범위 표현 |
| 5 | 제약 조건 누락 | 형용사형 목표, 측정 불가 기준 |

### 3. AskUserQuestion 반복 루프

분석된 모호성 항목 기반으로 질문을 제시. 사용자가 "완료"를 선택할 때까지 반복.

### 4. 프롬프트 구조화 및 저장

프롬프트 구조화 5요소(명확한 목표, 구체적 대상, 제약 조건, 검증 기준, 참조 컨텍스트)에 맞춰 정리 후 `.prompt/prompt.txt`에 저장.

### 5. 완료 메시지

`prompt.txt가 업데이트되었습니다. 이제 cc:implement, cc:research 등을 실행하세요.`

## 주의사항

1. **Task 도구 호출 금지** - 비워크플로우 독립 명령어이므로 서브에이전트 호출 불가
2. **Bash 도구 호출 금지** - 가드 스크립트 비간섭 보장
3. **사용 가능 도구** - Read, Write, AskUserQuestion만 사용
4. **워크플로우 무관** - FSM 상태 전이, 배너 출력, workDir 생성, status.json/registry.json 조작 불가
