---
description: 레지스트리 관리. 워크플로우 레지스트리 조회, 정리, 초기화를 수행합니다.
---
# Registry Management

워크플로우 레지스트리(`.workflow/registry.json`)의 엔트리를 조회하고 선택적으로 정리합니다.

## 스크립트

`.claude/hooks/workflow/registry.sh` - 서브커맨드: list, clean, remove, help

## 오케스트레이션 흐름

### Step 1. 현황 조회

Bash 도구로 실행:

```bash
wf-registry list
```

모든 레지스트리 엔트리를 컬러 테이블로 출력합니다. KEY, TITLE, PHASE, COMMAND 컬럼이 표시되며, phase별 색상이 적용됩니다.

**phase 색상:**
- INIT = 빨강, PLAN = 파랑, WORK = 초록, REPORT = 보라
- COMPLETED / STALE / CANCELLED = 회색, FAILED = 노랑

출력 결과를 사용자에게 표시합니다.

### Step 2. 정리 대상 미리보기 (선택적)

정리 전에 대상을 확인하려면:

```bash
wf-registry clean --dry-run
```

제거 대상 엔트리 목록과 사유를 출력하되, 실제 삭제는 수행하지 않습니다.

**정리 대상 기준:**
- COMPLETED / FAILED / STALE / CANCELLED phase 엔트리
- status.json이 없는 고아 엔트리
- registry phase와 status.json phase가 불일치하는 엔트리
- REPORT phase인데 1시간 이상 경과한 잔류 엔트리

### Step 3. 선택적 정리 실행

Bash 도구로 실행:

```bash
wf-registry clean
```

정리 대상 엔트리만 제거합니다. 진행 중인 워크플로우(INIT, PLAN, WORK, REPORT)는 보존됩니다.

### Step 4. 전체 초기화 (필요 시)

모든 엔트리를 제거하고 레지스트리를 비우려면:

```bash
wf-registry clean --force
```

registry.json을 `{}`로 초기화합니다. 확인 없이 즉시 실행되므로 주의가 필요합니다.

> **주의**: `--force`는 진행 중인 워크플로우 엔트리도 모두 제거합니다. `.workflow/` 하위 디렉토리의 물리 파일은 삭제하지 않습니다.

### Step 5. 단건 제거 (필요 시)

특정 엔트리만 제거하려면:

```bash
wf-registry remove <YYYYMMDD-HHMMSS>
```

해당 키의 엔트리를 registry에서 단건 제거합니다. 존재하지 않는 키에 대해서는 경고만 출력합니다.

---

## init:clear와의 역할 구분

| 항목 | init:registry (이 명령어) | init:clear |
|------|--------------------------|------------|
| 대상 | registry.json 엔트리만 | .workflow/ 디렉토리 + .prompt/ 파일 전체 |
| 방식 | 선택적 정리 (조건 기반) | 전체 삭제 (nuclear) |
| 물리 파일 | 삭제하지 않음 | 삭제함 |
| 용도 | 좀비 엔트리 정리, 레지스트리 정돈 | 작업 내역 완전 초기화 |

## 관련 명령어

- `/init:clear` - 작업 내역 전체 삭제 (.workflow/ + .prompt/)
- `/init:project` - 프로젝트 초기화
