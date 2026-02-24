---
description: 코드베이스를 분석하여 CLAUDE.md를 생성/갱신합니다. 코드 변경 후 CLAUDE.md를 최신화할 때 수시로 실행하세요.
---

# Update Project Context (CLAUDE.md)

> **실행 시점:** 필요할 때 수시로 실행하세요. 코드베이스가 변경된 후 CLAUDE.md를 최신 상태로 유지할 때 사용합니다.
>
> **멱등성:** 반복 실행해도 안전합니다. 기존 CLAUDE.md의 Recent Changes, Known Issues, Next Steps 섹션은 자동 보존됩니다.
>
프로젝트 코드베이스를 분석하고 CLAUDE.md를 생성 또는 갱신합니다.

## 스크립트

`.claude/scripts/init/init_project.py` - 서브커맨드: analyze, generate-claude-md

## 오케스트레이션 흐름

아래 순서대로 실행합니다. 각 단계에서 Bash 도구로 스크립트를 호출하고, 결과 JSON을 파싱하여 다음 단계를 결정합니다.

### Step 1. 프로젝트 분석

Bash 도구로 실행:

```bash
python3 .claude/scripts/init/init_project.py analyze
```

**결과 JSON 예시:**
```json
{
  "project_name": "my-project",
  "project_description": "...",
  "project_type": "Configuration",
  "detected_languages": "Markdown, Shell",
  "detected_frameworks": "None",
  "runtime": "None",
  "package_manager": "None",
  "key_dependencies": "None",
  "existing_directories": ".claude, .github",
  "git_initialized": true,
  "git_repository": "git@github.com:user/repo.git",
  "git_current_branch": "main",
  "git_main_branch": "main",
  "git_branch_strategy": "GitHub Flow"
}
```

분석 결과를 사용자에게 요약 표시:

```
[분석 결과]
- 언어: (detected_languages)
- 프레임워크: (detected_frameworks)
- 프로젝트 유형: (project_type)
- Git: (git_initialized) ((git_branch_strategy))
```

**analyze 결과 JSON을 변수에 보존** -> Step 2~3에서 사용.

### Step 2. CLAUDE.md 덮어쓰기 확인 (대화형)

기존 CLAUDE.md 파일 존재 여부를 Read 도구로 확인합니다.

**분기:**
- 파일이 없으면 -> Step 3 (바로 생성)
- 파일이 있으면 -> **AskUserQuestion** 으로 사용자에게 확인:
  - 질문: "기존 CLAUDE.md 파일이 있습니다. 분석 결과로 갱신하시겠습니까? (기존 Recent Changes, Known Issues, Next Steps는 보존됩니다) [yes/no]"
  - `yes` -> Step 3
  - `no` -> Step 4 (CLAUDE.md 갱신 건너뜀)

### Step 3. CLAUDE.md 생성/갱신

Step 1의 analyze 결과 JSON을 stdin으로 전달하여 실행:

```bash
echo '<analyze_json>' | python3 .claude/scripts/init/init_project.py generate-claude-md
```

스크립트가 기존 CLAUDE.md의 Recent Changes, Known Issues, Next Steps를 자동 보존합니다.

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
| `/sync:registry` | 워크플로우 레지스트리 조회 및 정리 |
| `/sync:code` | 원격 리포지토리에서 .claude 동기화 |
