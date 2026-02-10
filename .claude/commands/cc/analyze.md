---
description: 내부 자산 분석 수행. 요구사항, 코드베이스, 데이터베이스, 데이터를 분석합니다. 키워드 기반으로 분석 유형을 자동 판단합니다.
---

# Analyze

## -np 플래그 (No-Plan 모드)

`$ARGUMENTS`에 `-np` 플래그가 포함된 경우 Tier 2 (no-plan) 모드로 실행합니다.

- `-np` 감지 시: init 에이전트 호출에 `mode: no-plan` 전달
- `-np` 미감지 시: 기존과 동일 (mode: full)

```
# -np 플래그 감지 예시
cc:analyze -np "간단한 코드베이스 분석"
→ Task(subagent_type="init", prompt="command: analyze\nmode: no-plan")
```

## 분석 유형

| 유형 | 스킬 | 키워드 |
|------|------|--------|
| 요구사항 분석 | command-analyze-srs | 요구사항, 명세서, 스펙, SRS, 기능 정의, requirement, spec |
| 코드베이스 분석 | command-analyze-codebase | 코드베이스, 아키텍처, 코드 구조, 의존성, 모듈, codebase, architecture |
| 데이터베이스 분석 | command-analyze-database | 데이터베이스, DB, 스키마, 테이블, ERD, 인덱스, database, schema |
| 데이터 분석 | command-analyze-data | 데이터 분석, 통계, 데이터셋, EDA, 시각화, data analysis, statistics |
| 기본값 | command-analyze-srs | (키워드 없음) |

## 분석 유형 판단

사용자 요청에서 키워드를 기반으로 분석 유형을 자동 판단합니다. 상단 "분석 유형" 테이블을 참조하세요.

**판단 로직:**
1. 요청 문자열을 소문자로 변환
2. 각 유형의 키워드를 순서대로 확인
3. 첫 번째 매칭된 키워드의 유형 선택
4. 키워드 없으면 기본값: 요구사항 분석 (command-analyze-srs)

**예시:**
- "로그인 기능 요구사항 분석" → command-analyze-srs
- "프로젝트 코드베이스 구조 분석" → command-analyze-codebase
- "사용자 테이블 스키마 분석" → command-analyze-database
- "매출 데이터 통계 분석" → command-analyze-data

## 스킬 로드

판단된 유형에 따라 해당 스킬을 로드합니다:
- command-analyze-srs: `.claude/skills/command-analyze-srs/SKILL.md`
- command-analyze-codebase: `.claude/skills/command-analyze-codebase/SKILL.md`
- command-analyze-database: `.claude/skills/command-analyze-database/SKILL.md`
- command-analyze-data: `.claude/skills/command-analyze-data/SKILL.md`

## 상세 절차 및 템플릿

요구사항 분석의 상세 절차(워크플로우, 재질의 가이드, 구조화 항목)와 명세서 템플릿은 command-analyze-srs 스킬을 참조하세요: `.claude/skills/command-analyze-srs/SKILL.md`
