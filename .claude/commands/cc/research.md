---
description: "웹 검색 기반 연구/조사 및 내부 자산 분석 수행. 외부 정보 수집, 기술 비교 분석, 내부 코드베이스/DB/데이터 분석을 통해 리포트를 제공합니다. Use when: 기술 조사, 비교 분석, 웹 리서치, 데이터 분석, 코드베이스 분석, DB 분석 / Do not use when: 코드 수정이 목적일 때 (cc:implement 사용)"
argument-hint: "조사 주제 또는 분석 대상"
---

> **워크플로우 스킬 로드**: 이 명령어는 워크플로우 오케스트레이션 스킬을 사용합니다. 실행 시작 전 `.claude/skills/workflow-orchestration/SKILL.md`를 Read로 로드하세요.

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

