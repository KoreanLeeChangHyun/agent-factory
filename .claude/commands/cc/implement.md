---
description: 코드 구현, 수정, 리팩토링. 기능 구현, 버그 수정, 코드 변경, 리팩토링을 수행합니다. 에이전트/스킬/커맨드 관리 포함.
argument-hint: "[-np] [-nr]"
---

# Implement

## 리팩토링 지원

implement 명령어는 리팩토링 작업을 포함합니다. 기존 `cc:refactor` 명령어의 기능이 여기에 통합되었습니다.

### 대상 결정

1. 요청에 리팩토링 대상이 명시된 경우 → 해당 대상
2. 요청에 대상이 불명확한 경우 → 최근 리뷰 대상 (`.workflow/<최신작업디렉토리>/report.md` 참조)

### 키워드 기반 스킬 로드

작업 내용에 리팩토링 관련 키워드(`리팩토링`, `refactor`, `코드 개선`, `추출`, `extract`)가 포함되면 `review-code-quality` 스킬이 자동 로드되어 코드 품질 검사를 병행합니다.

## 아키텍처/다이어그램 지원

아키텍처 설계 및 다이어그램 생성 작업은 키워드 기반으로 접근할 수 있습니다. 기존 `cc:architect` 명령어의 기능이 키워드 라우팅을 통해 여기서 사용 가능합니다.

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

### Manager 스킬 실행

요청 유형에 따라 적절한 manager 스킬을 실행합니다.

- **management-agent**: `.claude/skills/management-agent/` 참조
- **management-skill**: `.claude/skills/management-skill/` 참조
- **management-command**: `.claude/skills/management-command/` 참조

### 지원 작업

각 manager 스킬은 다음 작업을 지원합니다:

| 작업 | 설명 |
|------|------|
| 생성 (create) | 새로운 에셋 생성 |
| 수정 (update) | 기존 에셋 수정 |
| 삭제 (delete) | 에셋 삭제 |
| 조회 (list/show) | 에셋 목록 또는 상세 조회 |

### 에셋 경로

| 에셋 | 경로 |
|------|------|
| 에이전트 | `.claude/agents/*.md` |
| 스킬 | `.claude/skills/<skill-name>/` |
| 커맨드 | `.claude/commands/cc/*.md` |

## 실행 옵션

| 옵션 | 모드명 | 설명 | Phase Order |
|------|--------|------|-------------|
| `-np` | noplan | PLAN 단계를 스킵하고 즉시 WORK로 진행 | INIT -> WORK -> REPORT -> DONE |
| `-nr` | noreport | REPORT 단계를 스킵하고 WORK 완료 후 즉시 DONE으로 진행 | INIT -> PLAN -> WORK -> DONE |
| `-np -nr` | noplan+noreport | PLAN과 REPORT 모두 스킵 | INIT -> WORK -> DONE |

## 프로젝트 플로우 연동

워크플로우가 프로젝트 플로우(`.kanbanboard`) 컨텍스트 내에서 실행될 때, REPORT 단계 완료 후 칸반보드를 자동 갱신한다.

### 후처리 조건

1. 프로젝트 루트 디렉토리에서 `.kanbanboard` 파일을 검색한다
2. `.kanbanboard` 파일이 존재하지 않으면 후처리를 스킵한다
3. `.kanbanboard` 파일이 존재하면 아래 갱신 절차를 실행한다

### 갱신 절차

REPORT 단계가 완료(DONE 상태 전이)된 후 다음을 수행한다:

```bash
bash .claude/skills/design-strategy/scripts/update-kanban.sh <kanbanboard_path> <workflow_id> <status>
```

| 인자 | 값 |
|------|-----|
| `kanbanboard_path` | 프로젝트 루트의 `.kanbanboard` 파일 경로 |
| `workflow_id` | 현재 워크플로우 ID (예: WF-1) |
| `status` | `completed` (정상 완료 시) 또는 `failed` (실패 시) |

### 동작 요약

- 완료된 워크플로우의 체크박스를 `[x]`로 전환
- 해당 마일스톤의 상태 카운터(N/M 완료)를 자동 갱신
- 모든 워크플로우가 완료된 마일스톤을 Done 컬럼으로 이동

