---
name: workflow-cc-research
description: "Workflow command skill for cc:research. Performs web-search-based research and internal asset analysis. Auto-loads analysis skills based on keywords: SRS, codebase, database, data analysis."
disable-model-invocation: true
---

# Research Command

웹 검색 기반 연구/조사 및 내부 자산 분석을 수행하는 워크플로우 커맨드 스킬.

## 실행 옵션

| 옵션 | 모드명 | 설명 | Phase Order |
|------|--------|------|-------------|
| `-np` | noplan | PLAN 단계 스킵 | INIT -> WORK -> REPORT -> DONE |
| `-nr` | noreport | REPORT 단계 스킵 | INIT -> PLAN -> WORK -> DONE |
| `-np -nr` | noplan+noreport | 둘 다 스킵 | INIT -> WORK -> DONE |

## 연구 절차

1. **주제 파악 및 범위 정의** - 연구 주제 파악, 조사 깊이/범위/시간 범위 정의, 비교 대상 확인
2. **정보 수집** - WebSearch, WebFetch, Grep, Glob, Read 활용
3. **분석 및 정리** - 핵심 개념 추출, 장단점 분석, 비교 분석, 적용 가능성 평가
4. **리포트 작성** - 구조화된 문서 생성, 출처 명시

리포트 템플릿, 주의사항 등 상세 절차는 `research-general` 스킬(`.claude/skills/research-general/SKILL.md`)을 참조.

## 분석 지원

요청에 분석 관련 키워드가 포함되면 해당 분석 유형의 스킬이 자동 로드된다.

### 분석 유형

| 유형 | 스킬 | 키워드 |
|------|------|--------|
| 요구사항 분석 | analyze-srs | 요구사항, 명세서, 스펙, SRS, 기능 정의, requirement, spec |
| 코드베이스 분석 | analyze-codebase | 코드베이스, 아키텍처, 코드 구조, 의존성, 모듈, codebase, architecture |
| 데이터베이스 분석 | analyze-database | 데이터베이스, DB, 스키마, 테이블, ERD, 인덱스, database, schema |
| 데이터 분석 | analyze-data | 데이터 분석, 통계, 데이터셋, EDA, 시각화, data analysis, statistics |
| 기본값 | analyze-srs | (분석 키워드 있으나 유형 불명 시) |

### 분석 유형 판단 로직

1. 요청 문자열을 소문자로 변환
2. 각 유형의 키워드를 순서대로 확인
3. 첫 번째 매칭된 키워드의 유형 선택
4. 분석 키워드는 있으나 유형 불명이면 기본값: analyze-srs

### 관련 스킬 경로

- `.claude/skills/research-general/SKILL.md` - 연구/조사 워크플로우 상세 정의
- `.claude/skills/analyze-srs/SKILL.md` - 요구사항 분석 절차
- `.claude/skills/analyze-codebase/SKILL.md` - 코드베이스 분석 절차
- `.claude/skills/analyze-database/SKILL.md` - 데이터베이스 분석 절차
- `.claude/skills/analyze-data/SKILL.md` - 데이터 분석 절차

### 분석 절차

1. **대상 파악 및 범위 정의** - 분석 대상과 범위 정의
2. **데이터 수집** - Grep, Glob, Read, Bash 등으로 내부 자산 탐색
3. **분석 수행** - 분석 유형별 스킬의 체크리스트/프레임워크 적용
4. **리포트 작성** - 분석 결과를 구조화된 문서로 정리
