---
name: workflow-wf-implement
description: "Workflow command skill for wf implement. Handles code implementation, modification, refactoring, architecture design, and asset management (agent/skill/command). Auto-loads keyword-based skills for refactoring, architecture, and manager operations."
disable-model-invocation: true
---

# Implement Command

> **워크플로우 스킬 로드**: 이 스킬은 워크플로우 오케스트레이션 스킬을 사용합니다. 실행 시작 전 `.claude/skills/workflow-orchestration/SKILL.md`를 Read로 로드하세요.

코드 구현, 수정, 리팩토링을 수행하는 워크플로우 커맨드 스킬. PLAN→WORK→REPORT→DONE FSM은 `workflow-orchestration/SKILL.md`를 따른다.

## 리팩토링 지원

implement 커맨드는 리팩토링 작업을 포함합니다.

### 대상 결정

1. 요청에 리팩토링 대상이 명시된 경우 → 해당 대상
2. 요청에 대상이 불명확한 경우 → 최근 리뷰 대상 (`.workflow/<최신작업디렉토리>/report.md` 참조)

### 키워드 기반 스킬 로드

작업 내용에 리팩토링 관련 키워드(`리팩토링`, `refactor`, `코드 개선`, `추출`, `extract`)가 포함되면 `review-code-quality` 스킬이 자동 로드되어 코드 품질 검사를 병행합니다.

## 아키텍처/다이어그램 지원

아키텍처 설계 및 다이어그램 생성 작업은 키워드 기반으로 접근할 수 있습니다.

### 키워드 기반 스킬 로드

작업 내용에 아키텍처 관련 키워드(`아키텍처`, `architecture`, `설계`, `architect`, `시스템 구조`, `컴포넌트`)가 포함되면 `design-architect` + `design-mermaid-diagrams` 스킬이 자동 로드됩니다.

### 지원 기능

| 기능 | 설명 |
|------|------|
| 다이어그램 유형 선택 | 클래스, 시퀀스, ER, 컴포넌트, 상태, 플로우차트 6종 |
| Mermaid 코드 생성 | `.md` 파일로 Mermaid 코드 저장 |
| PNG 변환 | `mmdc -i <file>.md -o <file>.png` (mmdc CLI 사용) |

## 에셋 관리 (에이전트/스킬/커맨드)

사용자 요청에 에이전트, 스킬, 커맨드 관리가 포함된 경우 아래 키워드 매핑에 따라 적절한 Manager 스킬을 실행합니다.

### 키워드 매핑

| 키워드 | 대상 | 실행할 스킬 |
|--------|------|-------------|
| 에이전트, agent | 에이전트 | management-agent |
| 스킬, skill | 스킬 | management-skill |
| 커맨드, command, 명령어 | 커맨드 | management-command |

### 에셋 경로

| 에셋 | 경로 |
|------|------|
| 에이전트 | `.claude/agents/*.md` |
| 스킬 | `.claude/skills/<skill-name>/` |
| 커맨드 | `.claude/commands/wf.md` |

## 구현 완료 검증

`workflow-system-verification` 스킬 연동. 구현 완료 후 아래 4단계 검증을 순서대로 수행한다.

1. **빌드/컴파일 확인**: 변경 파일 대상으로 빌드 또는 컴파일 오류가 없는지 확인
2. **테스트 실행**: 관련 테스트를 실행하여 모두 통과하는지 확인
3. **타입 체크**: 타입스크립트 등 정적 타입 언어의 경우 타입 체크 통과 확인
4. **재검증 루프**: 검증 실패 시 즉시 수정 후 해당 단계부터 재검증. 모든 단계 통과 후 완료 선언

## 동적 컨텍스트

구현 시작 시 현재 작업 상태를 자동 파악하여 컨텍스트에 포함한다.

```
!git diff --name-only
!git status
```

## 프로젝트 플로우 연동

REPORT 단계 완료 후 티켓 상태를 자동 전이한다.

### 전이 절차

```bash
flow-kanban move T-NNN review
```

티켓 번호는 `wf.md` Steps 3-1~3-4에서 파싱된 `#N` 인자를 사용한다. 티켓 파일 경로는 `.kanban/T-NNN.xml`이다.

### 동작 요약

- 구현이 완료된 티켓을 Review 상태로 전이한다
- `wf -s implement #N` 실행 시 `wf.md`가 이미 티켓 XML 내용을 파싱하여 전달하므로 별도 파싱은 불필요하다
