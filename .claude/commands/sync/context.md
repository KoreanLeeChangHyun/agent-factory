---
description: 코드베이스를 분석하여 CLAUDE.md를 생성/갱신합니다. 코드 변경 후 CLAUDE.md를 최신화할 때 수시로 실행하세요.
---

# Update Project Context (CLAUDE.md)

> **실행 시점:** 필요할 때 수시로 실행하세요. 코드베이스가 변경된 후 CLAUDE.md를 최신 상태로 유지할 때 사용합니다.
>
> **멱등성:** 반복 실행해도 안전합니다. 기존 CLAUDE.md의 Recent Changes, Known Issues, Next Steps 섹션은 자동 보존됩니다.
>
프로젝트 코드베이스를 분석하고 CLAUDE.md를 생성 또는 갱신합니다.

## 오케스트레이션 흐름

아래 순서대로 실행합니다. 도구(Glob, Read, Bash)로 프로젝트를 직접 분석하고 결과를 바탕으로 CLAUDE.md를 생성/갱신합니다.

### Step 1. 프로젝트 분석

Glob, Read, Bash 도구를 사용하여 프로젝트를 직접 분석합니다:

- **언어 감지**: 파일 확장자 분포 확인 (Glob `**/*.py`, `**/*.ts` 등)
- **프레임워크 감지**: package.json, requirements.txt, Cargo.toml 등 의존성 파일 Read
- **프로젝트 구조**: 디렉터리 레이아웃 확인 (Bash `ls`)
- **Git 정보**: Bash `git remote -v`, `git branch --show-current`

분석 결과를 사용자에게 요약 표시:

```
[분석 결과]
- 언어: (감지된 언어)
- 프레임워크: (감지된 프레임워크)
- 프로젝트 유형: (유형)
- Git: (초기화 여부) (브랜치 전략)
```

### Step 2. CLAUDE.md 덮어쓰기 확인 (대화형)

기존 CLAUDE.md 파일 존재 여부를 Read 도구로 확인합니다.

**분기:**
- 파일이 없으면 -> Step 3 (바로 생성)
- 파일이 있으면 -> **AskUserQuestion** 으로 사용자에게 확인:
  - 질문: "기존 CLAUDE.md 파일이 있습니다. 분석 결과로 갱신하시겠습니까? (기존 Recent Changes, Known Issues, Next Steps는 보존됩니다) [yes/no]"
  - `yes` -> Step 3
  - `no` -> Step 4 (CLAUDE.md 갱신 건너뜀)

### Step 3. CLAUDE.md 생성/갱신

Step 1의 분석 결과를 바탕으로 Write 도구를 사용하여 CLAUDE.md를 직접 생성/갱신합니다.

기존 CLAUDE.md가 있는 경우 Recent Changes, Known Issues, Next Steps 섹션을 보존합니다.

### Step 4. 완료 메시지

최종 결과를 출력합니다:

```
=== CLAUDE.md 갱신 완료 ===

[분석 결과]
- 언어: (detected_languages)
- 프레임워크: (detected_frameworks)
- 프로젝트 유형: (project_type)
- Git: (git_initialized) ((git_branch_strategy))

[결과]
[v] CLAUDE.md 갱신 완료 (또는 "기존 파일 유지" 또는 "신규 생성")

다음 단계:
- CLAUDE.md를 확인하고 필요한 부분을 수동으로 보완하세요
- Known Issues, Next Steps 섹션을 업데이트하세요
```

---

## 사용자 재질의 원칙

**이 명령어는 대부분 자동화된 작업이므로 사용자 입력이 거의 필요하지 않습니다.**

| 상황 | AskUserQuestion 사용 |
|------|---------------------|
| 기존 CLAUDE.md 덮어쓰기 확인 | 기존 파일 존재 시 |
| 기타 예외 상황 | 사용자 판단 필요 시 |

---

## 오류 처리

| 오류 상황 | 대응 |
|----------|------|
| 프레임워크 감지 실패 | "Unknown"으로 설정, 수동 편집 안내 |
| 의존성 파일 파싱 실패 | 해당 항목 건너뛰기, 경고 메시지 출력 |
| Git 명령어 실행 실패 | `initialized: false`로 설정 |
| CLAUDE.md 쓰기 실패 | 에러 메시지 출력, 권한 확인 안내 |

---

## 관련 명령어

| 명령어 | 설명 |
|--------|------|
| `/init:workflow` | 워크플로우 로드 (CLAUDE.md, orchestration 스킬) |
| `/sync:history` | .workflow/ 작업 내역을 history.md에 동기화 |
| `/sync:catalog` | 스킬 카탈로그(skill-catalog.md) 재생성 |
