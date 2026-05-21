---
name: grill-me
description: "사용자 요구사항이 모호하거나 새 티켓을 생성하기 직전 의도를 캐물어 명확화해야 할 때 호출. Ouroboros 5단계 (DRAFT → CLARIFY → CRITIQUE → REWRITE → ACCEPT) 루프로 WorkRequest 를 실행 전 계약 수준까지 다듬는다. 트리거: '티켓 만들어줘', '/wf -o', '티켓 생성해줘', 'grill me', '캐물어줘', '제대로 물어봐', '인터뷰해줘', 작업 범위·산출물·제약·우선순위가 모호한 요구사항 발화. 도구로 답할 수 있는 것은 사용자에게 묻지 않는다."
license: "MIT (derived)"
---

# grill-me (Ouroboros WorkRequest 루프)

새 티켓을 생성하기 직전, 사용자의 모호한 요구사항을 **Ouroboros 5단계 루프 (DRAFT → CLARIFY → CRITIQUE → REWRITE → ACCEPT)** 로 다듬어 실행 전 계약을 고정하는 스킬입니다. 옛 grill-me (1~2개 인터뷰) 컨셉은 CLARIFY 단계 안으로 흡수되었습니다. 외부 `grill-me` (MIT, Matt Pocock 2026) 어휘를 본 프로젝트 Ouroboros 모델 (`.agent-factory/engine/core/work_requests/ouroboros.py`) 위에 매핑한 형태입니다.

> **룰 정의의 단일 진실 공급원**: 인터뷰 룰의 정의는 `.claude/rules/workflow/workflow.md` (티켓 생성 규칙 + DO Ouroboros 루프 룰)가 보유합니다. 본 스킬은 정의를 복붙하지 않고 트리거·5단계 흐름·예시·반례만 보유합니다.

## 1. 사용 시기

- 사용자가 "티켓 만들어줘", "/wf -o", "티켓 생성해줘", "grill me", "캐물어줘", "제대로 물어봐", "인터뷰해줘" 등으로 명시 호출한 경우.
- 사용자가 코드 수정·조사·검토를 요청했으나 작업 범위·산출물 형태·제약·우선순위 가운데 하나라도 모호한 경우.
- 기존 티켓을 편집(`/wf -e N`)하기 직전 요구사항이 흐릿한 경우.
- Board WorkRequest API (`create` / `refine` / `accept`) 의 의미적 흐름이 필요한 경우.

## 2. Ouroboros 5단계 (DRAFT → CLARIFY → CRITIQUE → REWRITE → ACCEPT)

5단계 FSM 의 합법 전이는 `.agent-factory/engine/core/work_requests/ouroboros.py` (`_NEXT_PHASE`) 에 정의됩니다. 본 스킬은 그 위에서 동작합니다.

| 단계 | 책임 | 본 스킬 동작 |
|------|------|--------------|
| **DRAFT** | 사용자 요청 raw 채집 | 사용자 발화·제목 후보·command (`implement`/`research`/`review`) 초안을 있는 그대로 기록. `flow-kanban create "" --command init --status todo` 로 빈 티켓 채번 |
| **CLARIFY** | 누락 필드 식별·자연어 질문 | `goal`/`target`/`constraints`/`criteria`/`context` 5필드 중 도구로 답할 수 없는 항목만 한 번에 1~2개 자연어로 질문. 메뉴 (1=A/2=B) 형태 금지 |
| **CRITIQUE** | 모호·검증불가·범위확장 위험 점검 | 모호한 대상, 검증 불가능한 기준, 범위 확장 위험, 숨은 의존성을 어시스턴트가 명시 짚음. 사용자 회의 신호 (`?`, `~ 아님`, 단답 의문) 감지 시 즉시 자세 낮춤 |
| **REWRITE** | 실행 가능한 prompt 갱신 | `flow-kanban update-prompt T-NNN --command ... --goal "..." --target "..." --constraints "..." --criteria "..." --context "..."` 호출. 추론한 제약·가정·위험은 `context` 또는 `constraints` 에 명시 |
| **ACCEPT** | 실행·검증에 충분 시 종결 | `goal`/`target`/`constraints`/`criteria` 4 태그가 각 10자 이상 + `TODO:` 미시작 충족 시 (품질 점수 ≥ 0.6) 사용자에게 확인 받고 ACCEPT 전이. 이후 `/wf -s N` 으로 v2 driver 발사 |

### 전이 규칙 (ouroboros.py `_NEXT_PHASE`)

- `DRAFT → CLARIFY` (필수)
- `CLARIFY → CRITIQUE` (필수)
- `CRITIQUE → REWRITE` 또는 `CRITIQUE → ACCEPT` (CRITIQUE 결과에 따라 분기)
- `REWRITE → CLARIFY` (재인터뷰 필요 시) 또는 `REWRITE → ACCEPT` (충분 시)
- `ACCEPT → (terminal)`

가능한 경우 티켓 XML `<ouroboros_history>` 에 각 단계 진입 시각·텍스트를 누적 기록합니다 (`OuroborosEntry` 형태).

## 3. 호출 흐름

1. **도구 우선 조회 (DRAFT 전 사전 작업)** — 답을 사용자에게 묻기 전, 본 프로젝트 도구로 알 수 있는지 먼저 확인합니다 (아래 6절).
2. **DRAFT** — 사용자 발화에서 추출 가능한 정보로 초안 채집, 빈 티켓 채번.
3. **CLARIFY** — 도구로 답이 안 나오는 결정점만 한 번에 1~2개씩 자연어로 질문. 답을 받은 뒤 다음 질문으로 진행.
4. **CRITIQUE** — 모은 답을 어시스턴트가 다시 짚어 모호·검증불가·범위확장 위험을 명시. 추천 1안 우선 제시 (옵션 나열 회피).
5. **REWRITE** — `flow-kanban update-prompt` 로 prompt 필드 갱신.
6. **ACCEPT** — 품질 점수 ≥ 0.6 + 사용자 합의 시 ACCEPT 전이. 후속 명령 안내 (`/wf -s N`).

CRITIQUE 결과 모호함이 잔존하면 `REWRITE → CLARIFY` 로 다시 한 사이클 더 돌립니다.

## 4. 묻는 대상

상세 정의는 `.claude/rules/workflow/workflow.md` (DO Ouroboros 루프 룰)을 참조하세요. 본 스킬에서는 CLARIFY 단계에서 다음 결정점만 자연어로 묻습니다.

- **작업 범위** — 어디까지가 이 티켓의 안쪽이고 바깥쪽인가.
- **산출물 형태** — 코드 패치/조사 보고서/리뷰 코멘트 중 무엇으로 마무리되어야 하는가.
- **제약** — 손대지 말아야 할 영역, 호환성, 성능 한계 등.
- **우선순위** — 시급성, 다른 작업 대비 비중.
- **연구·구현 방향에 결정적인 모호 포인트** — 위 4가지로 분류되지 않지만 방향을 가르는 결정점.

## 5. 묻지 않는 대상

- **티켓 상태** — 무조건 `--status todo` 자동 생성. 사용자가 즉시 집중하려면 칸반 DnD 한 번이면 충분합니다.
- **기본 생성 옵션** — 명시되지 않은 옵션은 기본값을 사용합니다.
- **메뉴 형태 질의 (1=A/2=B)** — MUST NOT. 자연어 한 줄 질문만 사용합니다.

## 6. 도구 우선 (외부 원본 "explore the codebase instead" 의 본 프로젝트 매핑)

DRAFT 직전 또는 CLARIFY 진입 전에 다음 도구로 답할 수 있는 사실은 사용자에게 묻지 말고 직접 조회합니다.

| 알고 싶은 것 | 도구 |
|------|------|
| 칸반 현재 상태, 티켓 목록 | `flow-kanban board`, `flow-kanban list`, `flow-kanban show <T-NNN>` |
| 진행 중인 워크트리 | `git worktree list` |
| 과거 결정·규약 | auto memory (`MEMORY.md` + 본문) |
| 백엔드 라이브 상태 | board live 조회 (`/api/...`) |
| 최근 파일 변경 시각 | `.pyc` / `.board.url` mtime, `git log` |
| 코드 위치·구조 | Glob / Grep / Read |
| 이전 Ouroboros 이력 | 티켓 XML `<ouroboros_history>` |

## 7. 반례 (절대 하지 말 것)

- DRAFT/CLARIFY/CRITIQUE 단계 건너뛰고 바로 ACCEPT 로 직행하기 — 5단계 루프의 의미가 사라짐.
- 한 번에 여러 질문을 묶어서 던지기 (CLARIFY 단계에서) — 답이 흩어지고 사용자 부담만 커집니다.
- 메뉴 형태 (1=A/2=B/3=C) 질의 — 자연어 인터뷰만 허용됩니다.
- CRITIQUE 단계를 어시스턴트가 사용자에게 떠넘기기 — 약점 분석은 어시스턴트의 책임 (workflow.md "사용자가 어때요 묻기 전에 즉시 약점" 룰).
- 사용자 명시 동의 없이 자동 강제 정책·가드·FSM 룰·status 강제 전이를 도입하기 — auto memory `feedback_no_speculative_guards_2026-05-08` 규약으로 명시 금지된 패턴.
- 합법 전이 (`_NEXT_PHASE`) 를 어기고 `DRAFT → ACCEPT` 같은 점프를 시도하기.
- workflow.md 의 Ouroboros 루프 룰 정의를 본 SKILL.md 로 복붙해 단일 진실 공급원을 깨뜨리기.
- 도구로 답할 수 있는 것을 사용자에게 묻기.

## 8. 출처

- 외부 원본: `/home/deus/workspace/claude/repo/skills/skills/productivity/grill-me/SKILL.md` — MIT (Matt Pocock, 2026).
- 본 프로젝트 Ouroboros 모델: `.agent-factory/engine/core/work_requests/ouroboros.py` (5단계 FSM + `_NEXT_PHASE` 합법 전이).
- 변경 요약: 한국어/존댓말로 재작성 / 옛 grill-me 의 "한 번에 1~2개 질문" 룰을 Ouroboros CLARIFY 단계 안으로 흡수 / DRAFT·CRITIQUE·REWRITE·ACCEPT 단계 신설 / 외부의 "explore the codebase instead" 권고를 본 프로젝트 도구(`flow-kanban`·`git worktree`·auto memory·board live)로 매핑 / `.claude/rules/workflow/workflow.md` Ouroboros 루프 룰을 단일 진실 공급원으로 cross-reference / 추천 1안 우선·자동 강제 금지·메뉴 질의 금지 등 본 프로젝트 규약 반영 / 티켓 생성 단계(`flow-kanban create --status todo`)를 DRAFT 의 일부로 통합.

## 9. 시스템 스킬 분류

본 스킬은 `my-*` 접두사가 아니므로 **시스템 스킬**(`.claude/` 갱신 정책상 갱신 대상)로 분류됩니다. `disable-model-invocation` 키를 설정하지 않아 자동 호출이 가능합니다.
