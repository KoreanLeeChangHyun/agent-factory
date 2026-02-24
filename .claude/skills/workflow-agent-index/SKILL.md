---
name: workflow-agent-index
description: "Internal skill for workflow WORK Phase 0 (skill mapping preparation). Reads skill-catalog.md once to acquire all skill metadata, then maps plan tasks to appropriate skills using a 4-level matching priority. Produces skill-map.md for subsequent Worker phases. Internally invoked by orchestrator via indexer agent; not intended for direct user invocation."
disable-model-invocation: true
---

# Index

스킬 카탈로그 기반 스킬 매핑을 위한 인덱서 에이전트 전용 워크플로우 스킬.

> 이 스킬은 workflow-agent-orchestration 스킬이 관리하는 워크플로우의 WORK Phase 0 단계입니다.

**workflow-agent-index의 역할:**
- 오케스트레이터(workflow-agent-orchestration)가 Task 도구로 indexer 에이전트를 호출
- 스킬 카탈로그를 1회 Read하여 전체 스킬 메타데이터를 획득
- 계획서 태스크에 적합한 스킬을 4단계 매칭 우선순위로 매핑
- 결과를 skill-map.md로 생성하여 오케스트레이터에 반환

## 입력

오케스트레이터로부터 다음 정보를 전달받습니다:

| 파라미터 | 설명 | 비고 |
|----------|------|------|
| `command` | 실행 명령어 (implement, review, research 등) | 필수 |
| `workId` | 작업 ID | 필수 |
| `taskId` | `phase0` 고정 | 필수 |
| `planPath` | 계획서 경로 | full 모드 |
| `userPromptPath` | 사용자 프롬프트 경로 | noplan 모드 (planPath 대체) |
| `workDir` | 작업 디렉터리 경로 | 필수 |

## 실행 절차

### 1. work 디렉터리 생성

```bash
mkdir -p <workDir>/work
```

### 2. 계획서 읽기

`planPath`(full 모드) 또는 `userPromptPath`(noplan 모드)에서 다음 정보를 추출한다:

- `command`: 실행 명령어
- 태스크 목록: 각 태스크의 ID, 작업명, 종속성, 작업 내용
- `skills`: 사용자가 명시한 스킬 목록 (있는 경우)

### 3. 스킬 카탈로그 읽기

`.claude/skills/skill-catalog.md`를 **1회 Read**로 전체 내용을 로드한다.

카탈로그에는 3개 섹션이 포함되어 있다:
- **Command Default Mapping**: 명령어별 기본 스킬 매핑 테이블
- **Keyword Index**: 키워드별 추가 스킬 매핑 테이블
- **Skill Descriptions**: 모든 활성 스킬의 이름과 description

이 1회 Read로 매핑에 필요한 모든 정보가 획득된다. 개별 SKILL.md 파일을 추가로 읽을 필요가 없다.

### 4. 스킬 매핑 (4단계 매칭 우선순위)

각 태스크에 대해 다음 우선순위로 스킬을 결정한다. 상위 단계에서 적합한 스킬을 찾으면 하위 단계는 실행하지 않는다.

| 우선순위 | 매칭 방식 | 소스 | 설명 |
|---------|----------|------|------|
| 1순위 | **skills 파라미터** | 입력 파라미터 | 사용자가 명시적으로 전달한 스킬. 무조건 사용 |
| 2순위 | **명령어 기본 매핑** | 카탈로그 Command Default Mapping 섹션 | 명령어(implement, review 등)에 따른 기본 스킬 |
| 3순위 | **키워드 매칭** | 카탈로그 Keyword Index 섹션 | 태스크 작업 내용의 키워드가 인덱스와 일치하는 경우 |
| 4순위 | **description 폴백** | 카탈로그 Skill Descriptions 섹션 | description 필드와 태스크 내용의 의미론적 매칭 |

**매핑 규칙:**

- 2순위(명령어 기본 매핑)는 모든 태스크에 공통 적용된다
- 3순위(키워드 매칭)는 2순위 결과에 **추가**로 적용된다 (대체가 아님)
- 4순위(description 폴백)는 2~3순위에서 태스크 특화 스킬을 찾지 못한 경우에만 시도한다
- `workflow-agent-*`, `workflow-cc-*` 접두사 스킬과 `disable-model-invocation: true` 스킬은 매핑 대상에서 제외한다

### 5. skill-map.md 생성

`<workDir>/work/skill-map.md` 파일을 다음 형식으로 생성한다:

```markdown
# Skill Map

| 태스크 ID | 태스크 설명 | 추천 스킬 | 판단 근거 |
|-----------|------------|----------|----------|
| W01 | [태스크 설명] | skill-a, skill-b | [매칭 방식과 근거] |
| W02 | [태스크 설명] | skill-c | [매칭 방식과 근거] |
```

**테이블 컬럼 설명:**

| 컬럼 | 내용 |
|------|------|
| 태스크 ID | 계획서의 태스크 ID (W01, W02, ...) |
| 태스크 설명 | 계획서의 태스크 작업명 |
| 추천 스킬 | 매핑 결과 스킬명 (쉼표 구분). 해당 스킬이 없으면 "(없음)" |
| 판단 근거 | 매칭 방식(skills 파라미터/명령어 기본/키워드 매칭/description 폴백)과 구체적 근거 |

---

## 반환 형식

```
상태: 성공 | 실패
스킬맵: <workDir>/work/skill-map.md
매핑 스킬: N개
```

- **매핑 스킬 N개**: 중복 제거된 고유 스킬 수

---

## Frontmatter 플래그 설명

`disable-model-invocation: true`: Claude의 자동 스킬 호출을 차단하여 오케스트레이터가 indexer 에이전트를 통해서만 이 스킬을 사용하도록 보장합니다. 이 플래그는 제거하지 마세요.
