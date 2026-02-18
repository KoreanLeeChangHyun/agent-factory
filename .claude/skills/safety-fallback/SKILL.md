---
name: safety-fallback
description: "Agent system safety guard, limitation reference, and error recovery strategy guide. For hook-based safety, refer to hooks-guide skill. Use for error recovery and safety tasks: (1) agent limitation reference, (2) Task failure/error recovery strategy, (3) self-verification criteria understanding, (4) iteration limits/resource protection policies. Triggers: '안전장치', 'fallback', '에러 복구', 'Task 실패', '제한 사항'."
license: "Apache-2.0"
---

# 안전장치 및 Fallback 가이드

## 설명
에이전트 시스템의 안전장치, 제한 사항, 오류 복구 전략을 설명합니다.

## 사용 시기
- 에이전트 제한 사항을 확인하고 싶을 때
- Task 실패나 에이전트 에러 발생 시 복구 방법을 알고 싶을 때
- 에이전트 자체 검증 기준을 이해하고 싶을 때

---

## 안전장치 (v1.2.0)

### Iteration Limits (권장 설계 가이드라인)

에이전트 시스템 설계 시 권장하는 반복 제한 기준:

| 항목 | 권장값 | 설명 |
|------|--------|------|
| 쿼리당 최대 Task 호출 | 10회 | 무한 루프 방지 |
| 최대 재작업 요청 | 3회 | 반복 실패 시 에스컬레이션 |
| 부모당 최대 서브 에이전트 | 5개 | 리소스 과다 사용 방지 |
| 최대 깊이 | 3 | XX-XX-XX 형식까지 |
| 작업 타임아웃 | 30분 | 장기 작업 방지 |

> 이 값들은 `.claude/settings.json`에 별도 설정 섹션이 없으며, 에이전트/스킬 구현 시 자체적으로 준수해야 하는 가이드라인입니다.

### Fallback 전략 (권장 동작 방식)

에이전트 에러 발생 시 권장하는 복구 전략:

#### Task 실패 시
1. 자동 재시도 (최대 1회)
2. 실패 시 오케스트레이터에 에스컬레이션
3. 사용자에게 알림

#### 에이전트 에러 시
1. 자동 복구 시도
2. 복구 실패 시 옵션 제시
3. 사용자에게 알림

> 워크플로우 내에서는 Worker가 에러를 작업 내역에 기록하고 오케스트레이터에게 보고합니다.

### Self-Verification (권장 검증 체크리스트)

에이전트 역할별 자체 검증 항목:

| 역할 | 필수 검증 | 권장 검증 |
|------|----------|----------|
| **Coder** | 문법 검증, 구문 오류 없음 | 테스트 통과, 린트 오류 없음 |
| **Tester** | 테스트 실행됨, 커버리지 보고 | 커버리지 80% 이상 |
| **Researcher** | 출처 명시, 요약 포함 | 복수 출처 비교 |
| **Documenter** | 포맷 정확, 내용 완전 | 예시 포함 |

> 이 검증 항목들은 각 에이전트/스킬이 작업 완료 전 자체적으로 확인해야 하는 가이드라인입니다.

### 컨텍스트 압축

긴 작업 세션에서 컨텍스트 관리:

- `/compact` - 대화 요약 (Claude Code 내장 기능)
- `/clear` - 컨텍스트 초기화 (Claude Code 내장 기능)

> 대규모 코드베이스 탐색 시 `deep-research` 스킬의 `context:fork`를 활용하면 메인 컨텍스트 오염 없이 심층 조사가 가능합니다.

---

## 참고
- `.claude/settings.json` - Hook 설정 (안전장치 트리거)
- `.claude/hooks/` - Hook thin wrapper 디렉터리, `.claude/scripts/` - 실제 로직 스크립트 디렉터리
- `hooks-guide` 스킬 - Hook 시스템 상세 가이드
