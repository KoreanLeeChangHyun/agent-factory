---
description: 웹 검색 기반 연구/조사 및 내부 자산 분석 수행. 외부 정보 수집, 기술 비교 분석, 내부 코드베이스/DB/데이터 분석을 통해 리포트를 제공합니다.
---

# Research

## -np 플래그 (No-Plan 모드)

mode 결정은 오케스트레이터의 Mode Auto-Determination Rule에 의해 자동 수행됩니다. `-np` 플래그는 `$ARGUMENTS`를 통해 오케스트레이터에 전달됩니다.

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

리포트 템플릿, 주의사항 등 상세 절차는 command-research 스킬(`.claude/skills/command-research/SKILL.md`)을 참조합니다.

## 분석 지원

연구/조사 외에 내부 자산 분석도 이 명령어에서 수행합니다. 요청에 분석 관련 키워드가 포함되면 해당 분석 유형의 스킬이 자동 로드됩니다.

### 분석 유형

| 유형 | 스킬 | 키워드 |
|------|------|--------|
| 요구사항 분석 | command-analyze-srs | 요구사항, 명세서, 스펙, SRS, 기능 정의, requirement, spec |
| 코드베이스 분석 | command-analyze-codebase | 코드베이스, 아키텍처, 코드 구조, 의존성, 모듈, codebase, architecture |
| 데이터베이스 분석 | command-analyze-database | 데이터베이스, DB, 스키마, 테이블, ERD, 인덱스, database, schema |
| 데이터 분석 | command-analyze-data | 데이터 분석, 통계, 데이터셋, EDA, 시각화, data analysis, statistics |
| 기본값 | command-analyze-srs | (분석 키워드 있으나 유형 불명 시) |

### 분석 유형 판단

사용자 요청에서 키워드를 기반으로 분석 유형을 자동 판단합니다.

**판단 로직:**
1. 요청 문자열을 소문자로 변환
2. 각 유형의 키워드를 순서대로 확인
3. 첫 번째 매칭된 키워드의 유형 선택
4. 분석 키워드는 있으나 유형 불명이면 기본값: 요구사항 분석 (command-analyze-srs)

**예시:**
- "로그인 기능 요구사항 분석" -> command-analyze-srs
- "프로젝트 코드베이스 구조 분석" -> command-analyze-codebase
- "사용자 테이블 스키마 분석" -> command-analyze-database
- "매출 데이터 통계 분석" -> command-analyze-data

### 스킬 로드

판단된 유형에 따라 해당 스킬을 자동 로드합니다:
- command-analyze-srs: `.claude/skills/command-analyze-srs/SKILL.md`
- command-analyze-codebase: `.claude/skills/command-analyze-codebase/SKILL.md`
- command-analyze-database: `.claude/skills/command-analyze-database/SKILL.md`
- command-analyze-data: `.claude/skills/command-analyze-data/SKILL.md`

각 분석 유형의 상세 절차와 템플릿은 해당 스킬의 SKILL.md를 참조하세요.

### 분석 절차

분석 작업은 연구 절차와 유사하지만 내부 자산에 집중합니다:

1. **대상 파악 및 범위 정의** - 분석 대상(코드베이스, DB, 데이터 등)과 분석 범위를 정의
2. **데이터 수집** - Grep, Glob, Read, Bash 등으로 내부 자산 탐색
3. **분석 수행** - 분석 유형별 스킬의 체크리스트와 프레임워크 적용
4. **리포트 작성** - 분석 결과를 구조화된 문서로 정리

> 연구(외부 정보 수집)와 분석(내부 자산 분석)을 결합한 복합 작업도 가능합니다. 이 경우 연구 절차와 분석 절차를 순차적으로 수행합니다.

## 관련 스킬

- `.claude/skills/command-research/SKILL.md` - 연구/조사 워크플로우 상세 정의, 리포트 템플릿
- `.claude/skills/command-analyze-srs/SKILL.md` - 요구사항 분석 절차 및 명세서 템플릿
- `.claude/skills/command-analyze-codebase/SKILL.md` - 코드베이스 분석 절차
- `.claude/skills/command-analyze-database/SKILL.md` - 데이터베이스 분석 절차
- `.claude/skills/command-analyze-data/SKILL.md` - 데이터 분석 절차
