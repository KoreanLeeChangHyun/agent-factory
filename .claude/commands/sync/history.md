---
description: ".workflow/* 작업 내역을 .prompt/history.md에 동기화합니다."
---

# Sync Workflow History

`.workflow/` 디렉토리의 작업 내역을 스캔하여 `.prompt/history.md`에 누락 항목을 추가하고 상태를 업데이트합니다.

## 스크립트

`.claude/scripts/sync/history_sync.py` - 서브커맨드: sync, status

## 오케스트레이션 흐름

### Step 1. 현황 조회

Bash 도구로 실행:

```bash
python3 .claude/scripts/sync/history_sync.py status
```

`.workflow/` 디렉토리 수, history.md 행 수, 누락 수를 요약 출력합니다.
출력 결과를 사용자에게 표시합니다.

### Step 2. 동기화 미리보기 (선택적)

누락 항목이 있으면 변경 예정 사항을 먼저 확인합니다:

```bash
python3 .claude/scripts/sync/history_sync.py sync --dry-run
```

신규 추가 건수와 상태 업데이트 건수를 미리 출력합니다.

### Step 3. 동기화 실행

Bash 도구로 실행:

```bash
python3 .claude/scripts/sync/history_sync.py sync
```

누락 항목을 추가하고 상태 변경 항목을 업데이트합니다.

### Step 4. 결과 출력

스크립트의 stdout 출력을 사용자에게 표시합니다.

---

## 입력: $ARGUMENTS

| 인자 | 설명 | 기본값 |
|------|------|--------|
| `--dry-run` | 실제 동기화 없이 변경 사항만 미리보기 | 비활성 |
| `--all` | 중단 작업(INIT/PLAN 단계) 포함하여 동기화 | 비활성 |
| `--target PATH` | history.md 파일 경로 지정 | `.prompt/history.md` |
| `status` | 동기화 상태 요약만 출력 (sync 대신 사용) | - |

### $ARGUMENTS 분기

- `$ARGUMENTS`가 비어있거나 `sync` 관련 옵션만 포함 -> Step 1~4 순차 실행
- `$ARGUMENTS`에 `status`가 포함 -> Step 1만 실행

```bash
# status만 실행
python3 .claude/scripts/sync/history_sync.py status

# 옵션과 함께 sync 실행
python3 .claude/scripts/sync/history_sync.py sync $ARGUMENTS
```

---

## 오류 처리

| 오류 상황 | 대응 |
|----------|------|
| .workflow/ 디렉토리 없음 | "작업 이력이 없습니다" 메시지 출력 |
| history.md 파일 없음 | 자동 생성 (헤더 포함) |
| Python 스크립트 실행 실패 | 에러 메시지 출력, Python 환경 확인 안내 |
| status.json 파싱 실패 | 해당 항목 "불명" 상태로 처리 |

## 관련 명령어

| 명령어 | 설명 |
|--------|------|
| `/sync:registry` | 워크플로우 레지스트리 조회 및 정리 |
| `/sync:code` | 원격 리포지토리에서 .claude 동기화 |
| `/sync:context` | 코드베이스 분석 후 CLAUDE.md 갱신 |
| `/init:clear` | 작업 내역 전체 삭제 (.workflow/ + .prompt/) |
