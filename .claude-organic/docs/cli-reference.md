# flow-* CLI 레퍼런스

<!-- SUMMARY_START: 시스템 프롬프트용 요약 섹션 (alias-reference.xml 갱신 기반) -->
<!-- 이 주석 이후 ## Quick Reference 섹션까지가 시스템 프롬프트용 압축 버전입니다. -->

## Quick Reference (시스템 프롬프트용 압축 버전)

| alias | 핵심 사용법 | 필수 인자 |
|-------|------------|---------|
| `flow-claude` | `flow-claude start <command>` / `flow-claude end <registryKey>` | start/end 서브커맨드 |
| `flow-step` | `flow-step start <registryKey> [phase]` / `flow-step end <registryKey> [label]` | start/end 서브커맨드, registryKey |
| `flow-phase` | `flow-phase <registryKey> <N>` | registryKey, 페이즈 번호 |
| `flow-init` | `flow-init <command> <title> [mode] [#N]` | command(implement/review/research), title |
| `flow-finish` | `flow-finish <registryKey> <status>` | registryKey, status(완료/실패) |
| `flow-reload` | `flow-reload <workDir>` | workDir 상대경로 |
| `flow-update` | `flow-update <subcommand> <registryKey> ...` | 서브커맨드, registryKey |
| `flow-skillmap` | `flow-skillmap <registryKey>` | registryKey |
| `flow-skill` | `flow-skill archive/activate/list <skill_name>` | 서브커맨드 |
| `flow-validate` | `flow-validate <plan_path>` | plan.md 경로 |
| `flow-validate-p` | `flow-validate-p <prompt_file_path>` | 티켓 XML 경로 |
| `flow-recommend` | `flow-recommend <task_description>` | 태스크 설명 문자열 |
| `flow-gc` | `flow-gc [project_root]` | 없음 (선택적) |
| `flow-kanban` | `flow-kanban <subcommand> ...` (create/move/done/delete 등) | 서브커맨드 |

<!-- SUMMARY_END -->

---

## 상세 레퍼런스

### flow-claude

- **alias**: `flow-claude`
- **스크립트**: `.claude-organic/engine/banners/flow_claude_banner.sh`
- **설명**: 워크플로우 시작/종료 배너를 출력하는 셸 스크립트

#### 서브커맨드

| 서브커맨드 | 사용법 | 설명 |
|-----------|-------|------|
| `start` | `flow-claude start <command>` | 워크플로우 시작 배너 출력 |
| `end` | `flow-claude end <registryKey>` | 워크플로우 종료 배너 + 로그 기록 + Slack 알림 |

#### 인자

**start**
| 인자 | 필수 | 설명 |
|------|------|------|
| `command` | 필수 | 실행 명령어 문자열 (implement, review, research 등) |

**end**
| 인자 | 필수 | 설명 |
|------|------|------|
| `registryKey` | 필수 | YYYYMMDD-HHMMSS 형식 워크플로우 식별자 |

#### 사용 예시

```bash
flow-claude start implement
flow-claude end 20260325-004729
```

---

### flow-step

- **alias**: `flow-step`
- **스크립트**: `.claude-organic/engine/banners/flow_step_banner.sh`
- **설명**: PLAN/WORK/REPORT 단계 배너를 출력하는 셸 스크립트

#### 서브커맨드

| 서브커맨드 | 사용법 | 설명 |
|-----------|-------|------|
| `start` | `flow-step start <registryKey> [phase]` | 단계 시작 배너 출력 |
| `end` | `flow-step end <registryKey> [label]` | 단계 종료 배너 출력 |

#### 인자

**start**
| 인자 | 필수 | 설명 |
|------|------|------|
| `registryKey` | 필수 | YYYYMMDD-HHMMSS 형식 워크플로우 식별자 |
| `phase` | 선택 | 페이즈 이름 (PLAN/WORK/REPORT). 미지정 시 status.json에서 자동 조회 |

**end**
| 인자 | 필수 | 설명 |
|------|------|------|
| `registryKey` | 필수 | YYYYMMDD-HHMMSS 형식 워크플로우 식별자 |
| `label` | 선택 | 완료 레이블. 미지정 시 `[ASK]` 출력, 지정 시 `[OK] <label>` 출력 |

#### 사용 예시

```bash
flow-step start 20260325-004729
flow-step start 20260325-004729 PLAN
flow-step end   20260325-004729
flow-step end   20260325-004729 planSubmit
```

---

### flow-phase

- **alias**: `flow-phase`
- **스크립트**: `.claude-organic/engine/banners/flow_phase_banner.sh`
- **설명**: WORK 단계의 Phase 서브배너를 출력하는 셸 스크립트

#### 사용법

```
flow-phase <registryKey> <N>
```

#### 인자

| 인자 | 필수 | 설명 |
|------|------|------|
| `registryKey` | 필수 | YYYYMMDD-HHMMSS 형식 워크플로우 식별자 |
| `N` | 필수 | Phase 번호 (0 = skill-mapper 고정, 1 이상 = plan.md에서 파싱) |

#### 사용 예시

```bash
flow-phase 20260325-004729 0
flow-phase 20260325-004729 1
flow-phase 20260325-004729 2
```

---

### flow-init

- **alias**: `flow-init`
- **스크립트**: `.claude-organic/engine/flow/initialization.py`
- **설명**: 워크플로우 디렉터리 구조와 메타데이터를 초기화하는 스크립트

#### 사용법

```
flow-init <command> <title> [mode] [#N]
```

#### 인자

| 인자 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `command` | 필수 | string | 실행 명령어. `implement`, `review`, `research` 또는 체인 (`implement>review`) |
| `title` | 필수 | string | 20자 이내 워크플로우 제목 |
| `mode` | 선택 | string | 워크플로우 모드. 현재 `full`만 지원 (기본값: `full`) |
| `#N` / `T-NNN` | 선택 | string | 티켓 번호. 지정 시 해당 티켓을 사용 |

#### 환경변수

| 변수 | 설명 |
|------|------|
| `TICKET_NUMBER` | 티켓 번호 (T-NNN 또는 NNN 형식). 미지정 시 .claude-organic/tickets/active/에서 자동 선택 |

#### 출력 (stdout)

- init-result JSON: `workDir`, `registryKey`, `workId`, `workName`, `ticketNumber`, `chainCommand`

#### 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | 티켓 파일 없음 또는 비어있음 |
| 2 | 인자 오류 |
| 4 | 워크플로우 초기화 실패 |

#### 사용 예시

```bash
flow-init implement "로그인 버그 수정"
flow-init implement "인증 시스템 개선" full T-012
flow-init "implement>review" "결제 모듈 구현"
```

---

### flow-finish

- **alias**: `flow-finish`
- **스크립트**: `.claude-organic/engine/flow/finalization.py`
- **설명**: 워크플로우 마무리 6단계 처리 (상태 전이, 사용량 확정, 아카이빙, 티켓 갱신, 체인 발사, 세션 정리)

#### 사용법

```
flow-finish <registryKey> <status> [--ticket-number <T-NNN>]
```

#### 인자

| 인자 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `registryKey` | 필수 | string | YYYYMMDD-HHMMSS 형식 워크플로우 식별자 |
| `status` | 필수 | string | 완료 결과. `완료` 또는 `실패` |
| `--ticket-number` | 선택 | string | T-NNN 형식 티켓 번호. 지정 시 kanban 상태 갱신 |

#### 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | status.json 상태 전이 실패 (critical) |

#### 사용 예시

```bash
flow-finish 20260325-004729 완료
flow-finish 20260325-004729 완료 --ticket-number T-169
flow-finish 20260325-004729 실패 --ticket-number T-169
```

---

### flow-reload

- **alias**: `flow-reload`
- **스크립트**: `.claude-organic/engine/flow/reload_prompt.py`
- **설명**: 티켓 XML 피드백을 현재 워크플로우의 user_prompt.txt에 append하는 스크립트

#### 사용법

```
flow-reload <workDir>
```

#### 인자

| 인자 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `workDir` | 필수 | string | 작업 디렉터리 상대 경로 (예: `.claude-organic/runs/20260325-004729/작업명/implement`) |

#### 환경변수

| 변수 | 설명 |
|------|------|
| `TICKET_NUMBER` | 티켓 번호 (T-NNN 또는 NNN). 미지정 시 .context.json 또는 .claude-organic/tickets/active/ 스캔으로 자동 탐색 |

#### 출력 (stdout)

- 티켓 XML 피드백 전문

#### 사용 예시

```bash
flow-reload .claude-organic/runs/20260325-004729/로그인-버그-수정/implement
```

---

### flow-update

- **alias**: `flow-update`
- **스크립트**: `.claude-organic/engine/flow/update_state.py`
- **설명**: 워크플로우 상태 일괄 업데이트 라우터 (상태 전이, 사용량 추적, 태스크 관리, 환경변수 관리)

#### 서브커맨드

| 서브커맨드 | 사용법 | 설명 |
|-----------|-------|------|
| `context` | `flow-update context <registryKey> <agent>` | .context.json agent 필드 갱신 |
| `status` | `flow-update status <registryKey> <toPhase>` | status.json FSM 상태 전이 |
| `both` | `flow-update both <registryKey> <agent> <toPhase>` | context 갱신 + status 전이 동시 수행 |
| `link-session` | `flow-update link-session <registryKey> <sessionId>` | status.json에 세션 ID 등록 |
| `usage-pending` | `flow-update usage-pending <registryKey> <id1> [id2] ...` | 사용량 추적 대상 등록 |
| `usage` | `flow-update usage <registryKey> <agent_name> <input_tokens> <output_tokens> [cache_creation] [cache_read] [task_id]` | 에이전트 토큰 데이터 기록 |
| `usage-finalize` | `flow-update usage-finalize <registryKey>` | totals 계산 및 .usage.md 갱신 |
| `usage-regenerate` | `flow-update usage-regenerate` | .usage.md 전체 재생성 |
| `env` | `flow-update env <registryKey> set\|unset <KEY> [VALUE]` | .claude-organic/.env 환경변수 관리 |
| `task-status` | `flow-update task-status <registryKey> <status> <id1> [id2] ...` | 태스크 상태 일괄 변경 |
| `task-start` | `flow-update task-start <registryKey> <id1> [id2] ...` | 태스크를 running으로 설정 |

#### 주요 인자

**status 전이 대상 (`toPhase`)**
- `PLAN`, `WORK`, `REPORT`, `DONE`, `FAILED`, `STALE`

#### 종료 코드

- 항상 0 (비차단 원칙)

#### 사용 예시

```bash
flow-update status 20260325-004729 PLAN
flow-update both 20260325-004729 orchestrator WORK
flow-update task-start 20260325-004729 W01 W02
flow-update task-status 20260325-004729 done W01
flow-update usage 20260325-004729 orchestrator 1500 800 200 100
flow-update env 20260325-004729 set ENFORCE_SELF_REVIEW true
```

---

### flow-skillmap

- **alias**: `flow-skillmap`
- **스크립트**: `.claude-organic/engine/flow/skill_mapper.py`
- **설명**: plan.md 태스크의 skills 컬럼을 분석하여 skill-map.md와 태스크별 컨텍스트 슬라이스를 생성하는 Phase 0 스크립트

#### 사용법

```
flow-skillmap <registryKey>
```

#### 인자

| 인자 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `registryKey` | 필수 | string | YYYYMMDD-HHMMSS 형식 워크플로우 식별자 (workDir, plan.md 경로, command 자동 해석) |

#### 출력 파일

- `<workDir>/work/skill-map.md`
- `<workDir>/work/context/WXX-context.md` (태스크별)

#### 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 1 | 오류 (인자 누락, command 미발견 등) |
| 2 | 검증 실패 (스킬 미배정 또는 존재하지 않는 스킬명) |

#### 사용 예시

```bash
flow-skillmap 20260325-004729
```

---

### flow-skill

- **alias**: `flow-skill`
- **스크립트**: `.claude-organic/engine/flow/skill_state_manager.py`
- **설명**: 스킬의 활성(active)/아카이브(archived) 상태를 관리하는 CLI

#### 서브커맨드

| 서브커맨드 | 사용법 | 설명 |
|-----------|-------|------|
| `archive` | `flow-skill archive <skill_name>` | 스킬을 archived 상태로 전환 |
| `activate` | `flow-skill activate <skill_name>` | 스킬을 active 상태로 전환 |
| `list` | `flow-skill list [--archived \| --active]` | 스킬 상태 목록 조회 |

#### 인자

| 인자 | 필수 | 설명 |
|------|------|------|
| `skill_name` | archive/activate에 필수 | 스킬 이름 (skill-catalog.md에 등록된 이름) |
| `--archived` | list에서 선택 | archived 상태 스킬만 표시 |
| `--active` | list에서 선택 | active 상태 스킬만 표시 |

#### 종료 코드

- 0: 성공, 1: 실패

#### 사용 예시

```bash
flow-skill archive convention-python
flow-skill activate convention-python
flow-skill list
flow-skill list --archived
```

---

### flow-validate

- **alias**: `flow-validate`
- **스크립트**: `.claude-organic/engine/flow/plan_validator.py`
- **설명**: plan.md 구조를 검증하여 Phase 편차, 워커 분배, 스킬 배정, WHAT/HOW 분리를 점검하는 스크립트

#### 사용법

```
flow-validate <plan_path>
```

#### 인자

| 인자 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `plan_path` | 필수 | string | plan.md 파일 경로 |

#### 검증 항목

1. Mermaid 서브그래프에서 Phase별 워커 수 추출, 최대/최소 비율 3배 이상 시 경고
2. 작업 목록 테이블에서 워커별 작업 항목 수 파싱, 편차 2 초과 시 경고
3. T2(10+) 태스크에서 스킬 1개인 경우 경고
4. WHAT/HOW 분리 검증: criteria/goal/context 재서술 탐지 (advisory, 비차단)

#### 사용 예시

```bash
flow-validate .claude-organic/runs/20260325-004729/로그인-버그-수정/implement/plan.md
```

---

### flow-validate-p

- **alias**: `flow-validate-p`
- **스크립트**: `.claude-organic/engine/flow/prompt_validator.py`
- **설명**: 티켓 XML 파일의 계약 스펙을 검증하고 품질 점수를 산출하는 스크립트

#### 사용법

```
flow-validate-p <prompt_file_path>
```

#### 인자

| 인자 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `prompt_file_path` | 필수 | string | 티켓 XML 파일 경로 (.claude-organic/tickets/active/T-NNN.xml) |

#### 검증 항목

1. 필수 태그 4개 (`<goal>`, `<target>`, `<constraints>`, `<criteria>`) 존재 확인
2. 빈 섹션 감지 (내용 없음 또는 TODO 패턴만 존재, 최소 10자 미만)
3. 품질 점수 산출: `(존재 필수 태그 수 / 4) * 0.6 + (유효 내용 태그 수 / 4) * 0.4`
4. 선택 태그 (`<context>`, `<approach>`, `<scope>`, `<reference>`) 존재 여부 기재

#### 출력 (stdout)

JSON: `quality_score`, `has_tags`, `missing_tags`, `empty_tags`, `optional_tags`, `feedback`

#### 종료 코드

| 코드 | 의미 |
|------|------|
| 0 | 검증 완료 |
| 1 | 파일 읽기 실패 |
| 2 | 인자 오류 |

#### 사용 예시

```bash
flow-validate-p .claude-organic/tickets/active/T-169.xml
```

---

### flow-recommend

- **alias**: `flow-recommend`
- **스크립트**: `.claude-organic/engine/flow/skill_recommender.py`
- **설명**: 태스크 설명을 입력받아 TF-IDF 유사도 기반으로 상위 3개 스킬을 추천하는 스크립트

#### 사용법

```
flow-recommend <task_description>
```

#### 인자

| 인자 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `task_description` | 필수 | string | 스킬을 추천받을 태스크 설명 (자유 텍스트, 다중 단어 가능) |

#### 출력 (stdout)

- 추천 스킬 3개 (이름 + 유사도 점수)
- 추천 불가 시 "추천 가능한 스킬이 없습니다."

#### 사용 예시

```bash
flow-recommend "보안 리뷰 및 OWASP 취약점 분석"
flow-recommend "React 컴포넌트 성능 최적화"
flow-recommend "GitHub Actions CI 빌드 실패 디버깅"
```

---

### flow-gc

- **alias**: `flow-gc`
- **스크립트**: `.claude-organic/engine/flow/garbage_collect.py`
- **설명**: TTL(24시간) 만료된 미완료 워크플로우를 STALE 상태로 전환하는 좀비 정리 스크립트

#### 사용법

```
flow-gc [project_root]
```

#### 인자

| 인자 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `project_root` | 선택 | string | 프로젝트 루트 경로. 미지정 시 스크립트 위치 기준으로 자동 탐지 |

#### 동작

- `.claude-organic/runs/` 하위에서 TTL 만료 + 미완료(DONE/FAILED/STALE 미해당) status.json을 STALE로 전환
- flow-init 실행 시 자동으로 호출됨

#### 사용 예시

```bash
flow-gc
flow-gc /home/user/project
```

---

### flow-kanban

- **alias**: `flow-kanban`
- **스크립트**: `.claude-organic/engine/flow/kanban.py`
- **설명**: 칸반 보드 상태 관리 CLI. XML 티켓 파일(.claude-organic/tickets/active/T-NNN.xml)을 SSoT로 사용

#### 서브커맨드

| 서브커맨드 | 사용법 | 설명 |
|-----------|-------|------|
| `create` | `flow-kanban create "<title>" [--command <cmd>]` | 새 티켓 생성 (.claude-organic/tickets/active/T-NNN.xml) |
| `move` | `flow-kanban move <ticket> <target> [--force]` | 티켓을 지정 컬럼으로 이동 |
| `done` | `flow-kanban done <ticket>` | 티켓을 Done으로 이동 + .claude-organic/tickets/done/으로 파일 이동 |
| `delete` | `flow-kanban delete <ticket>` | 티켓 삭제 |
| `update-title` | `flow-kanban update-title <ticket> <title>` | 티켓 제목 갱신 |
| `update` | `flow-kanban update <ticket> [options]` | 티켓 메타데이터 갱신 |
| `update-prompt` | `flow-kanban update-prompt <ticket> [options]` | 티켓 prompt 필드(goal/target/constraints/criteria/context) 갱신 |
| `update-result` | `flow-kanban update-result <ticket> [options]` | 티켓 result 필드(registrykey/workdir/plan/report) 갱신 |
| `link` | `flow-kanban link <ticket> [--depends-on T-MMM] [--derived-from T-MMM] [--blocks T-MMM]` | 티켓 간 관계 양방향 기록 |
| `unlink` | `flow-kanban unlink <ticket> [--depends-on T-MMM] [--derived-from T-MMM] [--blocks T-MMM]` | 티켓 간 관계 양방향 제거 |
| `list` | `flow-kanban list [--status <open\|progress\|review\|done>]` | 티켓 목록 한 줄 요약 조회 |
| `board` | `flow-kanban board` | 칸반 보드 전체 현황 마크다운 테이블 출력 |
| `show` | `flow-kanban show <ticket>` | 특정 티켓 상세 정보 조회 |

#### 컬럼 키 (`move` 서브커맨드의 `target`)

| 키 | 상태명 |
|----|--------|
| `open` | Open |
| `progress` | In Progress |
| `review` | In Review |
| `done` | Done |

#### `update-prompt` 인자

| 인자 | 필수 | 설명 |
|------|------|------|
| `ticket` | 필수 | 티켓 번호 (T-NNN, NNN, #N 형식) |
| `--command` | 선택 | 워크플로우 커맨드 (implement, review, research 등) |
| `--goal` | 선택 | 목표 |
| `--target` | 선택 | 작업 대상 |
| `--constraints` | 선택 | 제약사항 |
| `--criteria` | 선택 | 완료 기준 |
| `--context` | 선택 | 맥락 정보 |
| `--skip-validation` | 선택 | 품질 검증 우회 (긴급 시 사용) |

#### `update-result` 인자

| 인자 | 필수 | 설명 |
|------|------|------|
| `ticket` | 필수 | 티켓 번호 |
| `--registrykey` | 선택 | YYYYMMDD-HHMMSS 형식 registryKey |
| `--plan` | 선택 | plan.md 상대 경로 |
| `--report` | 선택 | report.md 상대 경로 |
| `--workdir` | 선택 | 워크플로우 산출물 디렉터리 상대 경로 |

#### 사용 예시

```bash
flow-kanban create "로그인 버그 수정" --command implement
flow-kanban move T-169 progress
flow-kanban move T-169 review
flow-kanban done T-169

flow-kanban update-prompt T-169 \
  --goal "flow-* 스크립트 사용 가이드 통합" \
  --target ".claude-organic/docs/cli-reference.md 갱신"

flow-kanban update-result T-169 \
  --registrykey 20260325-004729 \
  --plan ".claude-organic/runs/20260325-004729/.../plan.md" \
  --report ".claude-organic/runs/20260325-004729/.../report.md" \
  --workdir ".claude-organic/runs/20260325-004729/.../implement"

flow-kanban link T-169 --depends-on T-165
flow-kanban link T-169 --derived-from T-168
```

---

## 환경변수 의존성 요약

| 환경변수 | 사용 스크립트 | 용도 |
|---------|------------|------|
| `TICKET_NUMBER` | flow-init, flow-reload | 티켓 번호 직접 지정 |
| `TMUX_PANE` | flow-finish | 세션 kill 여부 판단 (하위호환 폴백) |
| `WORKFLOW_WORKTREE_PATH` | flow-launcher | worktree cwd 설정 |
| `CLAUDE_SESSION_ID` | flow-init | 초기 세션 ID 등록 |

---

## 실행 컨텍스트 요구사항

모든 `flow-*` alias는 **프로젝트 루트** 디렉터리에서 실행해야 합니다.
Python 스크립트는 `sys.path` 자동 설정 가드를 포함하므로 `PYTHONPATH` 환경변수 없이 직접 실행 가능합니다.
