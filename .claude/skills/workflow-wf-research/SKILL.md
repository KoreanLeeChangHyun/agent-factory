---
name: workflow-wf-research
description: "Workflow command skill for wf research. Performs web-search-based research and internal asset analysis. Auto-loads analysis skills based on keywords: SRS, codebase, database, data analysis."
disable-model-invocation: true
license: "Apache-2.0"
---

# Research Command

> **워크플로우 스킬 로드**: 이 스킬은 워크플로우 오케스트레이션 스킬을 사용합니다. 실행 시작 전 `.claude/skills/workflow-orchestration/SKILL.md`를 Read로 로드하세요.

웹 검색 기반 연구/조사 및 내부 자산 분석을 수행하는 워크플로우 커맨드 스킬. PLAN→WORK→REPORT→DONE FSM은 `workflow-orchestration/SKILL.md`를 따른다.

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

리포트 템플릿, 주의사항 등 상세 절차는 research-general 스킬(`.claude/skills/research-general/SKILL.md`)을 참조한다.

## 출처 검증 기준

| 등급 | 출처 유형 | 날짜 기준 |
|------|----------|----------|
| S | 공식 문서, RFC, 표준 규격 | 최신 버전 확인 필수 |
| A | 주요 오픈소스 저장소, 공인 기관 발행물 | 최근 1년 이내 권장 |
| B | 기술 블로그(검증된 저자), 컨퍼런스 발표 자료 | 최근 2년 이내 |
| C | 일반 블로그, 포럼, Q&A 사이트 | 교차 검증 필수 |
| D | 출처 불명, 비공개 자료 | 사용 자제, 사용 시 명시적 경고 |

## 분석 지원

연구/조사 외에 내부 자산 분석도 이 커맨드에서 수행한다.

### 분석 유형

| 유형 | 스킬 | 키워드 |
|------|------|--------|
| 요구사항 분석 | analyze-srs | 요구사항, 명세서, 스펙, SRS, 기능 정의, requirement, spec |
| 코드베이스 분석 | analyze-codebase | 코드베이스, 아키텍처, 코드 구조, 의존성, 모듈, codebase, architecture |
| 데이터베이스 분석 | analyze-database | 데이터베이스, DB, 스키마, 테이블, ERD, 인덱스, database, schema |
| 데이터 분석 | analyze-data | 데이터 분석, 통계, 데이터셋, EDA, 시각화, data analysis, statistics |
| 기본값 | analyze-srs | (분석 키워드 있으나 유형 불명 시) |

### 분석 유형 판단

1. 요청 문자열을 소문자로 변환
2. 각 유형의 키워드를 순서대로 확인
3. 첫 번째 매칭된 키워드의 유형 선택
4. 분석 키워드는 있으나 유형 불명이면 기본값: 요구사항 분석 (analyze-srs)

### 스킬 로드

- analyze-srs: `.claude/skills/analyze-srs/SKILL.md`
- analyze-codebase: `.claude/skills/analyze-codebase/SKILL.md`
- analyze-database: `.claude/skills/analyze-database/SKILL.md`
- analyze-data: `.claude/skills/analyze-data/SKILL.md`

### 분석 절차

1. **대상 파악 및 범위 정의** - 분석 대상과 범위를 정의
2. **데이터 수집** - Grep, Glob, Read, Bash 등으로 내부 자산 탐색
3. **분석 수행** - 분석 유형별 스킬의 체크리스트와 프레임워크 적용
4. **리포트 작성** - 분석 결과를 구조화된 문서로 정리

## 관련 스킬

- `.claude/skills/research-general/SKILL.md` - 연구/조사 워크플로우 상세 정의, 리포트 템플릿
- `.claude/skills/research-integrated/SKILL.md` - 웹+코드 통합 조사
- `.claude/skills/analyze-srs/SKILL.md` - 요구사항 분석 절차
- `.claude/skills/analyze-codebase/SKILL.md` - 코드베이스 분석 절차
- `.claude/skills/analyze-database/SKILL.md` - 데이터베이스 분석 절차
- `.claude/skills/analyze-data/SKILL.md` - 데이터 분석 절차

## 동적 컨텍스트

```
!git log --oneline -10
```

## 프로젝트 플로우 연동

REPORT 단계 완료 후 티켓 상태를 자동 전이한다.

### 전이 절차

```bash
flow-kanban move T-NNN review
```

티켓 번호는 `wf.md` Steps 3-1~3-4에서 파싱된 `#N` 인자를 사용한다. 티켓 파일 경로는 `.kanban/T-NNN.xml`이다.

### 동작 요약

- 연구/분석이 완료된 티켓을 Review 상태로 전이한다
- `wf -s research #N` 실행 시 `wf.md`가 이미 티켓 XML 내용을 파싱하여 전달하므로 별도 파싱은 불필요하다

### cleanup 절차

워크플로우 완료 시 tmux 윈도우 자동 종료가 이중 안전장치로 동작한다:

- **1차 (finalization.py Step 5)**: `flow-finish` 실행 시 3초 지연 후 tmux 윈도우를 백그라운드(nohup+sleep)로 kill. `flow-claude end` 배너 출력이 보장된 후 종료
- **2차 (PostToolUse hook)**: `flow-claude end` Bash 호출 감지 시 5초 지연 후 tmux 윈도우를 추가로 kill. 1차 안전장치 실패 시 보완
- **비tmux 환경**: `TMUX_PANE` 미설정 시 양쪽 모두 자동 스킵 (멱등성 보장)
