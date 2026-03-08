---
description: "코드 구현, 수정, 리팩토링. 기능 구현, 버그 수정, 코드 변경, 리팩토링을 수행합니다. 에이전트/스킬/커맨드 관리 포함. Use when: 기능 구현, 코드 수정, 버그 수정, 리팩토링, 아키텍처 설계, 에이전트/스킬/커맨드 관리 / Do not use when: 코드 리뷰가 목적일 때 (cc:review 사용)"
argument-hint: "[-n] 구현할 기능, 수정할 파일, 또는 리팩토링 대상"
---

> **워크플로우 스킬 로드**: 이 명령어는 워크플로우 오케스트레이션 스킬을 사용합니다. 실행 시작 전 `.claude/skills/workflow-orchestration/SKILL.md`를 Read로 로드하세요.

## `-n` 강제 승인 요청 플래그

기본 동작은 자동 승인입니다. 오케스트레이터는 별도 플래그 없이 `autoApprove=true`로 설정하여 PLAN 완료 후 자동으로 WORK 단계로 진행합니다.

`$ARGUMENTS`에 `-n` 플래그가 포함되면 오케스트레이터가 `autoApprove=false`로 설정합니다. planner는 정상 실행하되, PLAN Step 2b에서 사용자 승인(AskUserQuestion 3옵션: 승인/수정 요청/중지)을 요청합니다.

- `-n` 미포함: 기본 동작 → planner 완료 후 자동 승인, WORK 즉시 진행
- `-n` 포함: planner 완료 후 AskUserQuestion 3옵션 제시 (승인/수정 요청/중지)

`plan_validator.py`가 계획서 검증 중 경고를 발생시키면, `-n` 플래그 여부와 무관하게 자동 승인이 차단되고 사용자 확인을 요청합니다.

## `<command>` 태그 검증

워크플로우 오케스트레이션 시 `user_prompt.txt` 파일에 명시된 커맨드와 실제 실행 커맨드의 일치를 검증합니다.

### 검증 절차

1. **INIT Step 완료 후 파싱**: 오케스트레이터가 INIT Step에서 `user_prompt.txt`를 생성한 후, PLAN Step 진입 전에 `user_prompt.txt`의 첫 번째 줄을 파싱하여 `<command>XXX</command>` 패턴을 추출합니다.

2. **검증 로직**:
   - `<command>` 태그가 존재하고 값이 `implement`가 **아닌** 경우: AskUserQuestion으로 경고 메시지를 표시합니다.
     - 메시지: `"prompt.txt에 <command>{값}</command>으로 지정되어 있지만 cc:implement를 실행했습니다."`
     - 선택지: `"계속 진행"` (현재 커맨드로 진행) / `"중단"` (워크플로우 종료)
   - `<command>` 태그가 존재하지 않는 경우: 경고 없이 정상 진행합니다. (하위 호환)
   - `<command>implement</command>`인 경우: 정상 진행합니다.

3. **검증 시점**: 이 검증은 워크플로우 오케스트레이션 스킬의 Step 1(INIT) 완료 후, Step 2(PLAN) 시작 전에 수행됩니다.

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

## 구현 완료 검증

`workflow-system-verification` 스킬 연동. 구현 완료 후 아래 4단계 검증을 순서대로 수행한다.

1. **빌드/컴파일 확인**: 변경 파일 대상으로 빌드 또는 컴파일 오류가 없는지 확인
2. **테스트 실행**: 관련 테스트를 실행하여 모두 통과하는지 확인
3. **타입 체크**: 타입스크립트 등 정적 타입 언어의 경우 타입 체크 통과 확인
4. **재검증 루프**: 검증 실패 시 즉시 수정 후 해당 단계부터 재검증. 모든 단계 통과 후 완료 선언

## 동적 컨텍스트

구현 시작 시 현재 작업 상태를 자동 파악하여 컨텍스트에 포함한다. 아래 명령어를 주입하여 변경 현황을 실시간으로 확인한다.

```
!git diff --name-only
!git status
```

| 명령어 | 용도 |
|--------|------|
| `!git diff --name-only` | 현재 수정된 파일 목록 파악 |
| `!git status` | 스테이징 상태 및 미추적 파일 파악 |

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

