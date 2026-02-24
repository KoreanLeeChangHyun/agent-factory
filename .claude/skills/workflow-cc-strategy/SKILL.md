---
name: workflow-cc-strategy
description: "Workflow command skill for cc:strategy. Establishes multi-workflow strategy with milestones, workflow chains, and roadmap. Operates in Planner mode (new strategy) or Judge mode (progress evaluation) based on .kanbanboard existence."
disable-model-invocation: true
---

# Strategy Command

다중 워크플로우 전략 수립을 수행하는 워크플로우 커맨드 스킬.

## 실행 흐름

strategy 명령어는 INIT -> STRATEGY -> DONE 흐름으로 실행된다. PLAN, WORK, REPORT 단계를 거치지 않으며, STRATEGY Phase에서 오케스트레이터가 직접 작업을 수행한다.

## 실행 모드 분기

`.kanbanboard` 파일 존재 여부로 모드를 판별한다.

| 조건 | 모드 | 역할 |
|------|------|------|
| `.kanbanboard` 없음 | Planner 모드 | 최초 전략 수립. 4단계 절차로 roadmap.md + .kanbanboard 생성 |
| `.kanbanboard` 존재 | Judge 모드 | 진행 상황 평가. 마일스톤 진행률 확인 및 완료 판단 |

## 전략 수립 절차 (Planner 모드)

### 1단계: 현황 분석

- 코드베이스 구조 및 프로젝트 상태 파악
- 기존 워크플로우 이력(`.workflow/`) 검토
- 기술 스택, 의존성, 제약 사항 식별

### 2단계: 목표 정의

- 최종 목표(End Goal) 명확화
- 중간 마일스톤(Milestone) 설정
- 각 마일스톤의 완료 기준(Definition of Done) 정의

### 3단계: 워크플로우 분해

- 마일스톤별 필요한 워크플로우 식별
- 워크플로우 간 종속성 그래프 설계
- 워크플로우별 명령어 유형 결정 (implement, research, review 등)
- 워크플로우별 예상 복잡도(T1/T2/T3) 산정

### 4단계: 로드맵 생성

- 우선순위 기반 실행 순서 결정
- 종속성을 고려한 병렬/순차 실행 계획
- 리스크 및 완화 전략 식별
- `roadmap.md` 최종 작성
- `.kanbanboard` 파일 자동 생성

## Judge 모드 절차

### 1단계: 현황 로드

- `.kanbanboard` 읽어 현재 프로젝트 상태 파악
- frontmatter에서 `roadmap` 경로 추출하여 `roadmap.md` 로드

### 2단계: 마일스톤 진행률 계산

- 마일스톤별 진행률 산출 (완료 워크플로우 수 / 전체 워크플로우 수)
- 전체 프로젝트 진행률 계산

### 3단계: roadmap.md 정합성 검증

- 마일스톤 ID / 워크플로우 ID 교차 검증
- 불일치 발견 시 경고 및 수정 방안 제안

### 4단계: 완료 마일스톤 아카이빙

- 완료된 마일스톤을 Done 컬럼으로 이동
- roadmap.md에 완료일/상태 기록

### 5단계: 다음 액션 결정

- 모든 마일스톤 Done -> 프로젝트 완료 선언
- 미완료 마일스톤 -> 다음 실행할 마일스톤/워크플로우 추천

## 핵심 산출물

| 산출물 | 설명 |
|--------|------|
| `roadmap.md` | 마일스톤, 워크플로우 체인, 종속성 그래프, 리스크 평가 |
| `.kanbanboard` | 마일스톤별 진행 상태 추적 (Backlog / In Progress / Done) |

## 관련 스킬

- `design-strategy` - 전략 수립 상세 가이드 (복잡도 산정, 종속성 그래프, 로드맵 템플릿)

## vs cc:research

| 관점 | cc:research | cc:strategy |
|------|-------------|-------------|
| 목적 | 정보 수집 및 분석 | 의사결정 및 계획 수립 |
| 입력 | 조사 주제, 질문 | 대규모 목표, 프로젝트 비전 |
| 산출물 | 리포트 (report.md) | 로드맵 (roadmap.md) |
| 핵심 활동 | 웹 검색, 코드 탐색, 비교 분석 | 목표 분해, 워크플로우 설계, 우선순위 결정 |
