---
name: workflow-cc-implement
description: "Workflow command skill for cc:implement. Handles code implementation, modification, refactoring, architecture design, and asset management (agent/skill/command). Auto-loads keyword-based skills for refactoring, architecture, and manager operations."
disable-model-invocation: true
---

# Implement Command

코드 구현, 수정, 리팩토링을 수행하는 워크플로우 커맨드 스킬.

## 실행 옵션

| 옵션 | 모드명 | 설명 | Phase Order |
|------|--------|------|-------------|
| `-np` | noplan | PLAN 단계 스킵 | INIT -> WORK -> REPORT -> DONE |
| `-nr` | noreport | REPORT 단계 스킵 | INIT -> PLAN -> WORK -> DONE |
| `-np -nr` | noplan+noreport | 둘 다 스킵 | INIT -> WORK -> DONE |

## 리팩토링 지원

implement 명령어는 리팩토링 작업을 포함한다. 대상이 불명확한 경우 최근 리뷰 대상(`.workflow/<최신작업디렉토리>/report.md`)을 참조한다.

### 키워드 기반 스킬 로드

리팩토링 키워드(`리팩토링`, `refactor`, `코드 개선`, `추출`, `extract`) 포함 시 `review-code-quality` 스킬 자동 로드.

## 아키텍처/다이어그램 지원

아키텍처 키워드(`아키텍처`, `architecture`, `설계`, `architect`, `시스템 구조`, `컴포넌트`) 포함 시 `design-architect` + `design-mermaid-diagrams` 스킬 자동 로드.

### 지원 기능

| 기능 | 설명 |
|------|------|
| 다이어그램 유형 선택 | 클래스, 시퀀스, ER, 컴포넌트, 상태, 플로우차트 6종 |
| Mermaid 코드 생성 | `.md` 파일로 Mermaid 코드 저장 |
| PNG 변환 | `mmdc -i <file>.md -o <file>.png` |

## 에셋 관리 (에이전트/스킬/커맨드)

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
| 커맨드 | `.claude/commands/cc/*.md` |

## 프로젝트 플로우 연동

워크플로우가 `.kanbanboard` 컨텍스트 내에서 실행될 때, REPORT 완료 후 칸반보드를 자동 갱신한다.

### 후처리 조건

1. 프로젝트 루트에서 `.kanbanboard` 파일 존재 여부 확인
2. 존재하지 않으면 후처리 스킵
3. 존재하면 아래 갱신 절차 실행

### 갱신 절차

```bash
bash .claude/skills/design-strategy/scripts/update-kanban.sh <kanbanboard_path> <workflow_id> <status>
```

| 인자 | 값 |
|------|-----|
| `kanbanboard_path` | 프로젝트 루트의 `.kanbanboard` 파일 경로 |
| `workflow_id` | 현재 워크플로우 ID |
| `status` | `completed` 또는 `failed` |
