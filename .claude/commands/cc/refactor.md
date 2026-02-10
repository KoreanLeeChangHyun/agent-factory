---
description: 코드 리팩토링 수행. /cc:review 이후에 진행 권장.
---
# Refactor

## -np 플래그 (No-Plan 모드)

`$ARGUMENTS`에 `-np` 플래그가 포함된 경우 Tier 2 (no-plan) 모드로 실행합니다.

- `-np` 감지 시: init 에이전트 호출에 `mode: no-plan` 전달
- `-np` 미감지 시: 기존과 동일 (mode: full)

```
# -np 플래그 감지 예시
cc:refactor -np "함수 추출 리팩토링"
→ Task(subagent_type="init", prompt="command: refactor\nmode: no-plan")
```

## 대상 결정

1. 요청에 대상이 명시된 경우 → 해당 대상
2. 요청에 대상이 불명확한 경우 → 최근 리뷰 대상 (`.workflow/<최신작업디렉토리>/report.md` 참조)
