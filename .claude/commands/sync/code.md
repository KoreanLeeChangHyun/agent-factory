---
description: "원격 리파지토리에서 .claude 디렉토리를 가져와 현재 프로젝트에 동기화합니다."
disable-model-invocation: true
---

# Sync .claude from Remote Repository

원격 리파지토리(`https://github.com/KoreanLeeChangHyun/claude-workflow.git`)에서 `.claude` 디렉토리를 가져와 현재 프로젝트에 덮어쓰기합니다.

> **주의:** 프로젝트 자체의 git과 `.claude` 원격 리파지토리는 별개입니다. 이 명령어는 `.claude` 설정 전용 리파지토리에서 최신 설정을 가져옵니다.

## 입력: $ARGUMENTS

| 인자 | 설명 | 기본값 |
|------|------|--------|
| `--dry-run` | 실제 동기화 없이 변경 사항만 미리보기 | 비활성 |
| `-h`, `--help` | 사용법 출력 | - |

## 스크립트

`.claude/scripts/sync/code_sync.py` - 옵션: `[--dry-run | -h | --help]`

## 오케스트레이션 흐름

이 명령어는 대화형 부분이 없으므로 스크립트를 직접 실행하고 결과만 출력합니다.

### Step 1. 동기화 실행

Bash 도구로 실행:

```bash
python3 .claude/scripts/sync/code_sync.py $ARGUMENTS
```

### Step 2. 결과 출력

스크립트의 stdout 출력을 그대로 사용자에게 표시합니다.

스크립트가 다음 내용을 자동 처리합니다:
- `.claude.env` 파일 자동 백업 및 복원
- 원격 리포지토리 shallow clone
- rsync --delete로 `.claude/` 디렉토리 동기화
- 임시 파일 자동 정리

---

## 주의사항

- `.claude.env` 파일은 **절대** 덮어쓰지 않습니다 (비밀 정보 보호)
- `.claude/.env` 파일은 rsync `--exclude='/.env'`에 의해 동기화 대상에서 제외됩니다 (settings 레벨 환경변수 보호)
- 원격 리파지토리에서 삭제된 파일은 로컬에서도 삭제됩니다 (`--delete` 옵션)
- 동기화 후 `/init:workflow`로 워크플로우를 재초기화해야 변경사항이 반영됩니다
- 이 명령어는 `disable-model-invocation: true`로 사용자만 직접 호출할 수 있습니다
- 동시 실행 시 각 세션은 PID 기반으로 격리된 임시 디렉토리를 사용하므로 경합은 발생하지 않습니다. 단, 동시에 `.claude/` 디렉토리를 덮어쓰므로 결과가 비결정적일 수 있어 순차 실행을 권장합니다

## 오류 처리

| 오류 상황 | 대응 |
|----------|------|
| git clone 실패 | 에러 메시지 출력, 네트워크/URL 확인 안내 |
| rsync 실패 | 에러 메시지 출력, 디스크 공간/권한 확인 안내 |
| .env 복원 실패 | WARNING 출력, TEMP_DIR 내 sync-backup/.env에서 수동 복원 안내 |
| 원격에 .claude 디렉토리 없음 | 에러 메시지 출력, 원격 리포지토리 구조 확인 안내 |
| 알 수 없는 옵션 입력 | 에러 메시지 출력, 사용법(`--dry-run`, `-h`) 안내 |

## 관련 명령어

| 명령어 | 설명 |
|--------|------|
| `/init:workflow` | 워크플로우 재초기화 (동기화 후 실행 권장) |
| `/sync:history` | .workflow/ 작업 내역을 history.md에 동기화 |
| `/sync:registry` | 워크플로우 레지스트리 조회 및 정리 |
| `/sync:catalog` | 스킬 카탈로그(skill-catalog.md) 재생성 |
| `/sync:context` | 코드베이스 분석 후 CLAUDE.md 갱신 |
| `/git:config` | Git 설정 (인증 문제 시) |
