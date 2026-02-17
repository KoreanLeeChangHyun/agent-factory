---
name: skill-auto-integrator
description: "Automated skill integration pipeline that searches, downloads, converts, and installs external AI skills from SkillsMP marketplace into .claude/skills/ directory. Use for skill discovery and integration: finding external skills, importing marketplace skills, auto-installing agent skills. Triggers: 'skill search', 'skill install', 'find skill', '스킬 찾기', '스킬 설치', '스킬 통합', 'auto integrate'."
---

# Skill Auto Integrator

외부 AI 스킬 마켓플레이스(SkillsMP)에서 스킬을 자동으로 검색, 다운로드, 변환, 설치하는 7단계 자동화 파이프라인.

## Overview

7단계 파이프라인을 통해 사용자의 자연어 프롬프트에서 적합한 외부 스킬을 찾아 `.claude/skills/` 디렉토리에 통합한다.

| 단계 | 이름 | 설명 |
|------|------|------|
| 1 | 프롬프트 분석 | 자연어 프롬프트에서 검색 키워드, 도메인, 작업 유형 추출 |
| 2 | 스킬 검색 | SkillsMP API를 호출하여 후보 스킬 목록 조회 |
| 3 | 후보 선정 | 키워드 매칭, description 유사도, 최신성, 라이선스 가중치 기반 랭킹 |
| 4 | 다운로드 | 상위 후보를 git clone 또는 HTTP 다운로드 (실패 시 다음 후보 재시도) |
| 5 | 포맷 변환 | 다운로드된 패키지를 Agent Skills 표준 구조로 변환 |
| 6 | 통합 설치 | `.claude/skills/{name}/`에 설치, 충돌 감지 처리 |
| 7 | 검증 | frontmatter 유효성, 파일 참조 무결성 등 7개 항목 검증 |

## Usage

### CLI 실행

```bash
# 기본 실행 - 검색 프롬프트로 스킬 검색 및 설치
python .claude/skills/skill-auto-integrator/scripts/skill_auto_integrate.py "PDF 처리 스킬"

# 검색+변환만 수행 (설치 미실행)
python .claude/skills/skill-auto-integrator/scripts/skill_auto_integrate.py --dry-run "코드 리뷰 스킬"

# 설치 경로 변경
python .claude/skills/skill-auto-integrator/scripts/skill_auto_integrate.py --target /path/to/skills "데이터 분석 스킬"
```

### 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `prompt` (위치 인자) | 검색 프롬프트 (자연어) | 필수 |
| `--dry-run` | 검색+변환만 수행, 설치 미실행 | `false` |
| `--target` | 스킬 설치 대상 디렉토리 | `.claude/skills/` |

## Pipeline Details

### 1. 프롬프트 분석 (`prompt_analyzer.py`)

순수 Python 정규식 기반 키워드 추출. 한글/영문 이중 언어 지원. spaCy 등 외부 NLP 의존성 없이 동작.

- 불용어 필터링으로 노이즈 키워드 제거
- 한글 명사 패턴(`-기`, `-화`, `-스킬` 등) 인식
- `SearchQuery` dataclass로 키워드, 도메인, 작업 유형 구조화

### 2-3. 스킬 검색 및 후보 선정 (`skill_search.py`)

SkillsMP API 호출 후 가중치 기반 랭킹으로 상위 3개 후보 선정.

- 랭킹 가중치: 키워드 매칭(0.4) + description 유사도(0.3) + 최신성(0.2) + 라이선스 호환성(0.1)
- 다운로드 실패 시 다음 후보로 자동 재시도 (최대 3회)

### 4. 포맷 변환 (`format_converter.py`)

다운로드된 스킬 패키지를 Agent Skills 표준 디렉토리 구조로 변환.

- 포맷 타입 자동 감지: Agent Skills / MCP 서버 / npm 패키지
- 디렉토리 매핑: `src/`/`lib/` -> `scripts/`, `docs/` -> `references/`, `assets/` 유지
- Frontmatter 생성/보정, name 정규화(`^[a-z0-9]+(-[a-z0-9]+)*$`)

### 5-6. 통합 및 검증 (`validator.py`)

7개 검증 항목 실행 후 `.claude/skills/`에 설치.

- 검증 항목: frontmatter 유효성, name 정규식, description 품질, 파일 참조 무결성, 충돌 검사, Progressive Disclosure 준수, 라이선스 호환성
- 기존 스킬 충돌 시 `conflict` 상태 반환

### 7. 메인 오케스트레이터 (`skill_auto_integrate.py`)

7단계 순차 실행을 관리하는 엔트리포인트. 설치 완료 후 command-skill-map 등록 키워드 제안 출력.

## Scripts Reference

모든 Python 모듈은 `scripts/` 디렉토리에 위치한다.

| 모듈 | 역할 |
|------|------|
| `prompt_analyzer.py` | 프롬프트에서 검색 키워드 추출 |
| `skill_search.py` | SkillsMP 검색 및 다운로드 |
| `format_converter.py` | 포맷 변환 (Agent Skills 표준) |
| `validator.py` | 유효성 검증 및 설치 |
| `skill_auto_integrate.py` | 메인 파이프라인 오케스트레이터 (CLI 엔트리포인트) |
