---
description: 코드 리뷰 수행. 파일, 디렉토리, PR 등을 리뷰합니다.
---

# Review

## -np 플래그 (No-Plan 모드)

`$ARGUMENTS`에 `-np` 플래그가 포함된 경우 Tier 2 (no-plan) 모드로 실행합니다.

- `-np` 감지 시: init 에이전트 호출에 `mode: no-plan` 전달
- `-np` 미감지 시: 기존과 동일 (mode: full)

```
# -np 플래그 감지 예시
cc:review -np "빠른 리뷰 요청"
→ Task(subagent_type="init", prompt="command: review\nmode: no-plan")
```

**입력:**
- `command`: review

## 심각도 기준

| 심각도 | 기준 |
|--------|------|
| Critical | 즉시 수정 필요 (보안, 데이터 손실) |
| Warning | 수정 권장 (성능, 잠재적 버그) |
| Info | 개선 제안 (스타일, 리팩토링) |

## 관련 스킬

| 스킬 | 용도 | 경로 |
|------|------|------|
| command-requesting-code-review | 리뷰 체크리스트 및 사전 검증 | `.claude/skills/command-requesting-code-review/SKILL.md` |
| command-code-quality-checker | 린트/타입체크 자동 실행 | `.claude/skills/command-code-quality-checker/SKILL.md` |
