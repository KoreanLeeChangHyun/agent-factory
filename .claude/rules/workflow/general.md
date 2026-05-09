# 일반 규칙

## 언어 및 톤
- 사용자 ↔ 어시스턴트 대화: 한국어 / 존댓말
- 코드 / 식별자 / 룰 / 문서: 영어 primary (한국어 번역은 향후 `translate/` 폴더 별도 트랙)
  - **Why**: LLM 의 동음이의어·의미 모호성 처리 정확도 ↑ (사용자 명시 2026-05-09: "클로드가 영어를 잘 읽기 때문이에요")
  - **How to apply**: 새 코드/필드/파일명/룰은 영어 default. 한국어 자산은 점진 마이그레이션 (별도 리팩토링 트랙)

## 설계 원칙 (메타)
- **모든 설계는 클로드(LLM)가 이해하기 쉬운 형태로 한다 — 그게 품질 최고** (사용자 명시 2026-05-09)
- **How to apply**:
  - 명명: action verb + explicit prefix (예: `phase_verify`, `ticket_validate` — 동의어 회피)
  - 동음이의어 제거: 같은 단어를 다른 계층/책임에 재사용 금지 (예: `phase` 단어를 워크플로우 6단계와 WORK 내부 sub-단계 양쪽에 쓰지 말 것 — 후자는 `step` 으로 분리)
  - 양언어 짝 어휘 분리: 영어 verb 다르고 한국어 어휘도 다르게 (예: verification/validation ↔ 검증/검수 — 동의어 짝 회피)
  - 데이터 구조: XML/JSON 등 단일 형식 일관, snake_case 통일
  - 흐름: Execute → Verify → Update 등 균일 패턴으로 phase 추가·디버깅 시 LLM 추론 부담 ↓

## 브랜치 정책
- 메인 브랜치(main/master)에 직접 커밋 절대 금지 (MUST NOT)
- 모든 변경은 피처 브랜치 생성 → PR 병합 (MUST)
- 브랜치 명명: feat/기능명, fix/버그명, refactor/대상명

## 메모리 정책
- CLAUDE.md: 프로젝트 규칙 전용. 세션 상태/메모를 저장하지 않는다 (MUST NOT)
- auto memory (~/.claude/projects/.../memory/): 세션 간 학습/상태 저장용
- 새 메모리 작성 시 **동일·연관 주제의 이전 메모리를 동시 점검·정리** (MUST):
  - 사실관계가 정정·반전된 경우 → 본문 update (오진단·오기록 발견 시 즉시)
  - 새 정보가 이전 정보를 완전히 대체 → 이전 파일 삭제 또는 본문 상단에 `> deprecated by <new_file>` 표시
  - 동일 주제로 분산 작성된 경우 → 통합 (원칙: 1주제 1파일, 또는 한 파일 안에 시계열 섹션)
  - MEMORY.md 인덱스 갱신 (자동 영역은 `flow-memory-gc run` 이 처리, 수동 영역은 직접 정리)
- 검토 누락 시 stale 메모리가 미래 세션에서 잘못된 단정·옵션 추천을 트리거 (실제 사례: 2026-05-07 T-400 오진단 메모리 — 사용자가 T-408 실행한 상황을 T-400 실행으로 기록)

## 추측 금지 (MUST)
- 사용자 의도·요청이 명확하지 않으면 **절대 추측으로 진행하지 않는다** (MUST NOT)
- 모르면 **다시 묻는다** (MUST)
- 헷갈리면 **다시 묻는다** (MUST)
- 사용자 명시 동의 없이 **자동 강제 정책·가드·FSM 룰·status 강제 전이·칸반 자동 회귀 등 안전장치 도입 절대 금지** (MUST NOT) — "사용자가 실수로 X 할 수 있으니 자동 차단" 같은 추측 기반 안전장치 삽입 금지
- 폐기 사례 (2026-05-08 commit 0c970fa, finalization.py +2/-73): T-409 산출물 정합성 검증 + T-411 워커 commit 누락 자동 검출 → status 강제 전이 → 칸반 Open 자동 회귀 정책 일괄 폐기. 사용자 명시 거부 ("내가 의도하지도 않았는데 클로드가 멋대로 추측해서 넣은 거지 같은 정책")

## 응답 스타일
- 커스텀 슬래시 명령어 제안 금지 — 사용자는 자연어로 요청, 내부적으로 워크플로우 변환
- bypassPermissions 세션에서는 재확인 없이 바로 실행 (파괴적 액션 제외)
- 새 기능 완료 시 사용자에게 즉시 안내
- 상태 보고 전 `flow-sessions` 조회 필수 — 기억 기반 보고 금지
- 티켓 관련 발화(티켓 번호 언급 / 티켓 생성·수정·이동·삭제 / 티켓 상태 보고 / "이거/저거/그거" 같은 지시어로 티켓 가리킴) 시 반드시 `flow-kanban show <T-NNN>` 또는 `flow-kanban board` 등으로 **현재 상태를 먼저 조회한 뒤 응답** (MUST). 기억·auto memory·jsonl 헤더(`_meta.ticket_id`)·세션 파일명·로그·이전 응답 결과 등 **칸반 외 보조 단서로 티켓 식별·상태 단정 금지** (MUST NOT) — 칸반이 single source of truth. 칸반은 다른 세션·UI(board DnD)에서도 변경되므로 stale 보조 정보로 사용자 혼선 유발 (실제 사고: 2026-05-07 사용자가 T-408 실행 중인 상황에서 어시스턴트가 03:55 옛 T-400 jsonl 만 보고 "사용자가 T-400 실행 시도"로 단정한 오진단 — 칸반 In Progress 컬럼이 진실. flow-sessions 도 보조용. 칸반 우선)
- 브랜치 그래프 차이 설명 시 **"앞선다/뒤처진다(ahead/behind)" 표현은 변경 내용(코드/파일)이 있을 때만** 사용 (MUST). PR `--merge` 방식의 자동 생성 merge commit 노드만 차이날 때는 명시적으로 "코드 동일, merge commit 노드만 차이"라고 쓴다 — 변경 내용 있는 것처럼 들려 사용자가 동기화 필요 여부를 오판하는 사례 차단
- 어시스턴트→사용자 출력에 "박제" 표현 사용 금지 (MUST NOT). 작업 진행 의향을 물을 때는 "티켓 생성 진행할까요" / "룰 추가할까요" / "메모리 등록할까요" 등 구체 작업 어휘로 대체. 단 사용자 발화 트리거 키워드(`박제해줘` 등)는 grill-me 호출 트리거로 그대로 보존 — 양방향 구분 (사용자→어시스턴트 트리거 어휘 보존 / 어시스턴트→사용자 출력 어휘 교체)

## 메인 세션 제약
- 서브에이전트(Agent 도구) 사용 금지 (MUST NOT) — 시간이 오래 걸리므로 티켓 생성 후 워크플로우로 처리
- `AskUserQuestion` 도구 사용 금지 (MUST NOT) — PreToolUse hook 의 `hookSpecificOutput` 신형 schema 와 SDK 측 구형 permission-callback schema(`{behavior, updatedInput, message}`) 불일치로 ZodError 발생, 도구 호출 자체 차단됨 (재현 확인 2026-05-08). 1~4지선다 질의는 텍스트 번호 매기기(1./2./3./4.)로 대체
- 세션 시작 시 `.claude-organic/.settings`에서 워크플로우 설정 확인 (MUST) — 특히 `WORKFLOW_WORKTREE` 값으로 워크트리 활성 여부 파악

## 워크플로우 실행
- `flow-launcher` timeout 에러 후 재시도 전에 반드시 `flow-sessions`로 세션 중복 확인 (MUST) — timeout이어도 세션이 생성되었을 수 있음

## 티켓 운영
- 티켓 과분리 금지 — 관련 항목은 스프린트/복잡도 단위로 묶기
- 적정 작업량: implement 4~7태스크/1~2페이즈, research 4~6/2, review 4~5/2
- 리뷰 선택지는 테이블 형식으로 출력

## 기본 컨벤션
- 아키텍처, 흐름, 구조 설명 시 Mermaid 다이어그램 활용 (MUST)
- ` ```mermaid` 코드 블록을 출력하기 **직전** 반드시 Skill 도구로 `design-mermaid-diagrams` 를 명시 호출 (MUST). "참조" 가 아니라 **명시 호출** — 출력 후 호출은 무효. 한 줄 예제도 예외 없음
- 라벨 안에 `/`, `<br/>`, `?`, `()`, `:` 등 특수문자 들어가면 반드시 `["..."]` 형태 큰따옴표로 감싸기 (MUST) — escape 누락 시 mermaid 11+ 파서가 raw `<pre>` 로 fallback 되어 사용자가 의도를 못 봄
- 터미널 출력에 이모지/아이콘 사용 금지 (MUST NOT)
- 터미널 외 UI에서 아이콘이 필요하면 반드시 SVG로 직접 생성 (MUST) — 외부 아이콘 라이브러리/폰트 사용 금지

## UI 디자인
- border-left 한쪽 색상 디자인 금지
- 테마 컬러: 테라코타 오렌지(#D97757)

## PreToolUse Hook 출력 schema (MUST)
- 통과 시 빈 stdout 금지 (MUST NOT) — `permissionDecision: allow` JSON 을 반드시 출력
  - 빈 stdout 일 때 SDK 가 외부 경로/WebFetch 등에서 별도 권한 평가를 시도하다 schema 위반 ZodError 발생 (`expected behavior: "allow"|"deny"`)
- allow JSON 의 `updatedInput` 필드는 **전체 tool_input 을 교체**한다
  - 입력을 변경하지 않을 거면 필드 자체를 생략 (MUST)
  - `"updatedInput": {}` 절대 금지 (MUST NOT) — command/file_path/pattern 등 모든 필드가 undefined 되어 모든 도구가 마비됨 (`H.replace undefined`, `Path must be a string`)
- deny JSON 에 `updatedInput` 넣지 말 것 (SHOULD NOT) — 무시되며 의미상 잘못된 코드
- 정상 통과 출력 형태:
  ```json
  {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "..."}}
  ```
- 참고: https://code.claude.com/docs/en/hooks

## .claude/ 편집 (MUST)
- `.claude/` 하위 파일의 생성·수정·삭제는 반드시 `flow-claude-edit` 경유 (MUST)
- `.claude-organic/` 하위 파일은 Edit/Write 직접 수정 가능 (claude_edit 불필요)
- Edit/Write 직접 수정 불가 — Claude Code hardcoded 보호로 차단됨
- 절차: `flow-claude-edit open <path>` → edit/ 에서 편집 → `flow-claude-edit save <path>`
- 삭제: `flow-claude-edit open <path>` 후 edit/ 파일 삭제 → Bash로 원본 rm
- 경로: `.claude/` 접두사 제외하고 전달 (예: `flow-claude-edit open rules/workflow/general.md`)

## .claude/ 갱신 정책
- **rules**: `workflow/` = 시스템 (갱신 대상), `project/` = 프로젝트 (보존)
- **skills**: `my-*` 접두사 = 프로젝트 (보존), 나머지 = 시스템 (갱신 대상)
- **agents, commands**: 전부 시스템 (갱신 대상)
- **settings.json**: 프로젝트 (보존)
