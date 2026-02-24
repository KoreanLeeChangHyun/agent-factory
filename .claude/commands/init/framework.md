---
description: 특정 프레임워크로 프로젝트를 초기화합니다. 프레임워크별 베스트 프랙티스와 구조를 적용합니다. (프로젝트당 1회)
---

# Initialize Framework

> **실행 시점:** 새 프로젝트에서 프레임워크 초기화 시 사용합니다. (프로젝트당 1회)

프레임워크 프로젝트를 초기화합니다. 사용자가 지정한 프레임워크에 맞는 프로젝트 구조, 설정 파일, 베스트 프랙티스를 적용합니다.

## 지원 프레임워크

| 프레임워크 | 스킬 | 설명 |
|------------|------|------|
| fastapi | framework-fastapi | Python FastAPI 웹 프레임워크 |
| django | (framework-django 미구현) | Python Django 웹 프레임워크 (향후 스킬 생성 예정) |
| react | framework-react | React 프론트엔드 프레임워크 |

## 스킬 매핑

프레임워크에 따라 적절한 스킬을 로드합니다:

```
fastapi -> framework-fastapi 스킬
django  -> framework-django 스킬 (미구현, 향후 생성 예정)
react   -> framework-react 스킬
```

**주의**: Django는 현재 전용 스킬이 없습니다. `init:framework django` 실행 시 framework-django 스킬이 필요하며, 미구현 상태임을 사용자에게 안내합니다.

## 실행 방식

프레임워크 프로젝트를 다음 순서로 초기화합니다:

### Step 1: 프레임워크 파싱

사용자 입력에서 프레임워크 이름과 프로젝트 이름을 추출합니다.

```
입력: "fastapi myproject"
-> framework: fastapi
-> project_name: myproject (optional)
```

### Step 2: 스킬 로드 및 실행

해당 프레임워크 스킬을 읽고 프로젝트 구조를 생성합니다.

- **fastapi/django**: `.claude/skills/framework-fastapi/SKILL.md` 참조
- **react**: `.claude/skills/framework-react/SKILL.md` 참조

### Step 3: 프로젝트 초기화

스킬에 정의된 구조대로 파일과 디렉토리를 생성합니다.

## 예시 출력

```
## 프로젝트 초기화 완료

**프레임워크**: FastAPI
**프로젝트명**: myproject

### 생성된 구조
myproject/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   └── database.py
├── tests/
├── requirements/
└── README.md

### 다음 단계
1. `cd myproject`
2. `pip install -r requirements/dev.txt`
3. `uvicorn src.main:app --reload`
```

## 관련 스킬

- `framework-fastapi` - FastAPI 프로젝트 구조 및 베스트 프랙티스
- `framework-react` - React 프로젝트 구조 및 베스트 프랙티스

---

## 오류 처리

| 오류 상황 | 대응 |
|----------|------|
| 지원하지 않는 프레임워크 지정 | 지원 프레임워크 목록 안내 |
| 스킬 파일 미존재 (django 등) | 미구현 상태 안내, 수동 설정 가이드 제공 |
| 프로젝트 디렉토리 이미 존재 | 덮어쓰기 여부 확인 |

---

## 관련 명령어

| 명령어 | 설명 |
|--------|------|
| `/init:build` | 빌드/실행 스크립트 생성 |
| `/init:workflow` | 워크플로우 로드 |
