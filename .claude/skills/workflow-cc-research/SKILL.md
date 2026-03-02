---
name: workflow-cc-research
description: "Workflow command skill for cc:research. Performs web-search-based research and internal asset analysis. Auto-loads analysis skills based on keywords: SRS, codebase, database, data analysis."
disable-model-invocation: true
---

# Research Command

웹 검색 기반 연구/조사 및 내부 자산 분석을 수행하는 워크플로우 커맨드 스킬.

상세 실행 절차는 `.claude/commands/cc/research.md`를 참조한다.

## 메타데이터

### 분석 유형 키워드 매핑

요청에 아래 키워드가 포함되면 해당 스킬이 자동 로드된다:

| 유형 | 스킬 | 키워드 |
|------|------|--------|
| 요구사항 분석 | analyze-srs | 요구사항, 명세서, 스펙, SRS, 기능 정의, requirement, spec |
| 코드베이스 분석 | analyze-codebase | 코드베이스, 아키텍처, 코드 구조, 의존성, 모듈, codebase, architecture |
| 데이터베이스 분석 | analyze-database | 데이터베이스, DB, 스키마, 테이블, ERD, 인덱스, database, schema |
| 데이터 분석 | analyze-data | 데이터 분석, 통계, 데이터셋, EDA, 시각화, data analysis, statistics |
| 기본값 | analyze-srs | (분석 키워드 있으나 유형 불명 시) |

### 관련 스킬 경로

- `.claude/skills/research-general/SKILL.md` - 연구/조사 워크플로우 상세 정의
- `.claude/skills/research-integrated/SKILL.md` - 웹+코드 통합 조사
- `.claude/skills/analyze-srs/SKILL.md` - 요구사항 분석 절차
- `.claude/skills/analyze-codebase/SKILL.md` - 코드베이스 분석 절차
- `.claude/skills/analyze-database/SKILL.md` - 데이터베이스 분석 절차
- `.claude/skills/analyze-data/SKILL.md` - 데이터 분석 절차

## 참조

이 스킬의 실행 절차는 대응 커맨드 파일(`.claude/commands/cc/research.md`)이 Single Source of Truth이다.
