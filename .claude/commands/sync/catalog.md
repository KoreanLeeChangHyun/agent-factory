---
description: "스킬 카탈로그 갱신. .claude/skills/ 디렉터리를 전수 스캔하여 skill-catalog.md를 재생성합니다."
---

# Sync Skill Catalog

`.claude/skills/*/SKILL.md`를 전수 스캔하여 `.claude/skills/skill-catalog.md`를 재생성합니다.

스킬이 추가/삭제/수정된 후 카탈로그를 최신 상태로 동기화할 때 사용합니다.

## 스크립트

`.claude/scripts/sync/catalog_sync.py` - 옵션: `[--dry-run]`

## 오케스트레이션 흐름

### Step 1. 현황 미리보기

Bash 도구로 실행:

```bash
python3 .claude/scripts/sync/catalog_sync.py --dry-run
```

활성 스킬 수, 제외 스킬 수, 예상 파일 크기를 출력합니다.
출력 결과를 사용자에게 표시합니다.

### Step 2. 카탈로그 재생성

Bash 도구로 실행:

```bash
python3 .claude/scripts/sync/catalog_sync.py
```

`.claude/skills/skill-catalog.md`를 재생성합니다. 기존 파일이 있으면 덮어씁니다.

### Step 3. 결과 출력

스크립트의 stdout 출력을 사용자에게 표시합니다.

출력 내용:
- 활성 스킬 수
- 제외 스킬 수
- 파일 크기 (bytes)
- 저장 위치

---

## 오류 처리

| 오류 상황 | 대응 |
|----------|------|
| skills 디렉터리 없음 | 에러 메시지 출력, 디렉터리 확인 안내 |
| command-skill-map.md 없음 | 해당 섹션을 "(파일 없음)"으로 대체하여 생성 |
| 파일 쓰기 실패 | 에러 메시지 출력, 권한 확인 안내 |

## 관련 명령어

| 명령어 | 설명 |
|--------|------|
| `/sync:registry` | 워크플로우 레지스트리 조회 및 정리 |
| `/sync:history` | .workflow/ 작업 내역을 history.md에 동기화 |
| `/sync:code` | 원격 리포지토리에서 .claude 동기화 |
| `/sync:context` | 코드베이스 분석 후 CLAUDE.md 갱신 |
