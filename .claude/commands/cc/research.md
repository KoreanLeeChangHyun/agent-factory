---
description: "웹 검색 기반 연구/조사 및 내부 자산 분석 수행. 외부 정보 수집, 기술 비교 분석, 내부 코드베이스/DB/데이터 분석을 통해 리포트를 제공합니다. Use when: 기술 조사, 비교 분석, 웹 리서치, 데이터 분석, 코드베이스 분석, DB 분석 / Do not use when: 코드 수정이 목적일 때 (cc:implement 사용)"
argument-hint: "[-n] [#N] 조사 주제 또는 분석 대상"
---

> **워크플로우 스킬 로드**: 이 명령어는 워크플로우 오케스트레이션 스킬을 사용합니다. 실행 시작 전 `.claude/skills/workflow-orchestration/SKILL.md`를 Read로 로드하세요.

## `-n` 강제 승인 요청 플래그

기본 동작은 자동 승인입니다. 오케스트레이터는 별도 플래그 없이 `autoApprove=true`로 설정하여 PLAN 완료 후 자동으로 WORK 단계로 진행합니다.

`$ARGUMENTS`에 `-n` 플래그가 포함되면 오케스트레이터가 `autoApprove=false`로 설정합니다. planner는 정상 실행하되, PLAN Step 2b에서 사용자 승인(AskUserQuestion 3옵션: 승인/수정 요청/중지)을 요청합니다.

- `-n` 미포함: 기본 동작 → planner 완료 후 자동 승인, WORK 즉시 진행
- `-n` 포함: planner 완료 후 AskUserQuestion 3옵션 제시 (승인/수정 요청/중지)

`plan_validator.py`가 계획서 검증 중 경고를 발생시키면, `-n` 플래그 여부와 무관하게 자동 승인이 차단되고 사용자 확인을 요청합니다.

## `#N` 티켓 번호 인자

`$ARGUMENTS`에서 `#N` 패턴(예: `#1`, `#12`, `#123`)을 파싱하여 티켓 번호를 추출합니다. 추출된 번호는 3자리 zero-padding하여 `.kanban/*-T-NNN.txt` glob 패턴으로 현재 상태 파일을 자동 탐색합니다.

- `#N` 지정 시: `.kanban/*-T-NNN.txt` glob 패턴으로 탐색한 파일을 읽어 `user_prompt.txt`로 사용
- `#N` 미지정 시: `.kanban/board.md`에서 Open 상태 티켓을 자동 선택
  - Open 티켓 1개: 해당 티켓 자동 선택
  - Open 티켓 복수: 메뉴로 사용자에게 선택 요청
  - Open 티켓 0개: `$ARGUMENTS` 텍스트를 그대로 사용 (기존 동작 호환)

## `<command>` 태그 검증

이 검증은 워크플로우 오케스트레이션 스킬의 Step 1(INIT) 완료 후, Step 2(PLAN) 시작 전에 수행된다.

### 검증 절차

오케스트레이터가 INIT Step에서 `user_prompt.txt`를 생성한 후, PLAN Step 진입 전에 `user_prompt.txt` 첫 번째 줄을 파싱하여 `<command>XXX</command>` 패턴을 추출한다.

### 검증 규칙

- **`<command>` 태그가 존재하고 값이 `research`가 아닌 경우**: AskUserQuestion으로 경고 메시지를 표시한다.
  - 메시지: `"티켓 파일에 <command>{값}</command>으로 지정되어 있지만 cc:research를 실행했습니다."`
  - 선택지: `"계속 진행"` (현재 커맨드로 진행) / `"중단"` (워크플로우 종료)

- **`<command>` 태그가 존재하지 않는 경우**: 경고 없이 정상 진행 (하위 호환)

- **`<command>research</command>`인 경우**: 정상 진행

# Research

## 연구 절차

1. **주제 파악 및 범위 정의**
   - 연구 주제 파악 (기술 조사 / 개념 연구 / 비교 분석)
   - 조사 깊이, 범위, 시간 범위 정의
   - 비교 대상 확인 (해당 시)

2. **정보 수집**
   - WebSearch: 최신 정보, 문서, 블로그 등
   - WebFetch: 특정 페이지 상세 내용
   - Grep, Glob, Read: 코드베이스 탐색, 기존 사용 패턴

3. **분석 및 정리**
   - 핵심 개념 추출
   - 장단점 분석
   - 비교 분석 (해당 시)
   - 실제 적용 가능성 평가
   - 주의사항 및 제한사항

4. **리포트 작성**
   - 구조화된 문서 생성
   - 출처 명시
   - 리포트는 `.workflow/<YYYYMMDD-HHMMSS>/<작업명>/research/report.md`에 저장된다

리포트 템플릿, 주의사항 등 상세 절차는 research-general 스킬(`.claude/skills/research-general/SKILL.md`)을 참조합니다.

## 출처 검증 기준

수집된 정보는 아래 신뢰도 등급 기준으로 분류하고, 리포트에 등급을 명시합니다.

| 등급 | 출처 유형 | 날짜 기준 |
|------|----------|----------|
| S | 공식 문서, RFC, 표준 규격 | 최신 버전 확인 필수 |
| A | 주요 오픈소스 저장소, 공인 기관 발행물 | 최근 1년 이내 권장 |
| B | 기술 블로그(검증된 저자), 컨퍼런스 발표 자료 | 최근 2년 이내 |
| C | 일반 블로그, 포럼, Q&A 사이트 | 교차 검증 필수 |
| D | 출처 불명, 비공개 자료 | 사용 자제, 사용 시 명시적 경고 |

## 분석 지원

연구/조사 외에 내부 자산 분석도 이 명령어에서 수행합니다. 요청에 분석 관련 키워드가 포함되면 해당 분석 유형의 스킬이 자동 로드됩니다.

### 분석 유형

| 유형 | 스킬 | 키워드 |
|------|------|--------|
| 요구사항 분석 | analyze-srs | 요구사항, 명세서, 스펙, SRS, 기능 정의, requirement, spec |
| 코드베이스 분석 | analyze-codebase | 코드베이스, 아키텍처, 코드 구조, 의존성, 모듈, codebase, architecture |
| 데이터베이스 분석 | analyze-database | 데이터베이스, DB, 스키마, 테이블, ERD, 인덱스, database, schema |
| 데이터 분석 | analyze-data | 데이터 분석, 통계, 데이터셋, EDA, 시각화, data analysis, statistics |
| 기본값 | analyze-srs | (분석 키워드 있으나 유형 불명 시) |

### 분석 유형 판단

사용자 요청에서 키워드를 기반으로 분석 유형을 자동 판단합니다.

**판단 로직:**
1. 요청 문자열을 소문자로 변환
2. 각 유형의 키워드를 순서대로 확인
3. 첫 번째 매칭된 키워드의 유형 선택
4. 분석 키워드는 있으나 유형 불명이면 기본값: 요구사항 분석 (analyze-srs)

**예시:**
- "로그인 기능 요구사항 분석" -> analyze-srs
- "프로젝트 코드베이스 구조 분석" -> analyze-codebase
- "사용자 테이블 스키마 분석" -> analyze-database
- "매출 데이터 통계 분석" -> analyze-data

### 스킬 로드

판단된 유형에 따라 해당 스킬을 자동 로드합니다:
- analyze-srs: `.claude/skills/analyze-srs/SKILL.md`
- analyze-codebase: `.claude/skills/analyze-codebase/SKILL.md`
- analyze-database: `.claude/skills/analyze-database/SKILL.md`
- analyze-data: `.claude/skills/analyze-data/SKILL.md`

각 분석 유형의 상세 절차와 템플릿은 해당 스킬의 SKILL.md를 참조하세요.

### 분석 절차

분석 작업은 연구 절차와 유사하지만 내부 자산에 집중합니다:

1. **대상 파악 및 범위 정의** - 분석 대상(코드베이스, DB, 데이터 등)과 분석 범위를 정의
2. **데이터 수집** - Grep, Glob, Read, Bash 등으로 내부 자산 탐색
3. **분석 수행** - 분석 유형별 스킬의 체크리스트와 프레임워크 적용
4. **리포트 작성** - 분석 결과를 구조화된 문서로 정리

> 연구(외부 정보 수집)와 분석(내부 자산 분석)을 결합한 복합 작업도 가능합니다. 이 경우 연구 절차와 분석 절차를 순차적으로 수행합니다.

## 관련 스킬

- `.claude/skills/research-general/SKILL.md` - 연구/조사 워크플로우 상세 정의, 리포트 템플릿
- `.claude/skills/research-integrated/SKILL.md` - 웹+코드 통합 조사 (웹 검색 + 코드베이스 탐색 교차 대조)
- `.claude/skills/analyze-srs/SKILL.md` - 요구사항 분석 절차 및 명세서 템플릿
- `.claude/skills/analyze-codebase/SKILL.md` - 코드베이스 분석 절차
- `.claude/skills/analyze-database/SKILL.md` - 데이터베이스 분석 절차
- `.claude/skills/analyze-data/SKILL.md` - 데이터 분석 절차

## 동적 컨텍스트

연구 시작 시 최근 변경 이력을 자동 참조하여 컨텍스트에 포함합니다.

```
!git log --oneline -10
```

최근 10개 커밋 이력을 수집하여, 조사 대상과 연관된 최근 변경사항을 파악합니다.

## 프로젝트 플로우 연동

워크플로우가 프로젝트 플로우(`.kanban/board.md`) 컨텍스트 내에서 실행될 때, REPORT 단계 완료 후 티켓 상태를 자동 전이한다.

### 후처리 조건

1. 프로젝트 루트 디렉터리에서 `.kanban/board.md` 파일을 검색한다
2. `.kanban/board.md` 파일이 존재하지 않으면 후처리를 스킵한다
3. `.kanban/board.md` 파일이 존재하면 아래 전이 절차를 실행한다

### 전이 절차

REPORT 단계가 완료(DONE 상태 전이)된 후 다음을 수행한다:

```bash
python3 .claude/scripts/flow/kanban.py move T-NNN review
```

| 인자 | 값 |
|------|-----|
| `T-NNN` | 현재 워크플로우와 연결된 티켓 번호 (예: T-001) |
| `review` | 연구 완료 후 전이할 상태 |

### 동작 요약

- 연구/조사가 완료된 티켓을 Review 상태로 전이한다
- 티켓 번호는 워크플로우 초기화 시 파싱된 `#N` 인자 또는 자동 선택된 티켓에서 가져온다

