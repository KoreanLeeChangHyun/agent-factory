---
name: execution-contracts
description: 실행 흐름과 API·데이터 계약 초안을 확인할 때 사용합니다.
document-type: processed
category: analyze
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/design-execution-contracts/index.html
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# 실행 흐름과 API·데이터 계약 초안

- Processed · design-execution-contracts · 초안 1 · 2026-09-15.

- 단계 1 상세 설계 자료. **검수 전 제안이며 구현 완료 명세가 아니다.**

- [서비스 경계 초안](../analyze-service-boundary-design/SKILL.md) · [확정 결정의 인터뷰 기록](../interview-service-boundaries/SKILL.md) · [현재 목표 디렉터리 구조](../../skills/rule-workbench-structure/SKILL.md#target-structure)

<a id="scope"></a>

<a id="범위와-결정-상태"></a>

## 1. 범위와 결정 상태

- **확정 입력**: [인터뷰 Q1–Q7](../interview-service-boundaries/SKILL.md)을 따른다. 원문 선택 기록을 대체하지 않는다.

- **이 문서의 계약명·필드·경로·상태 상세는 검토 제안**이다. 구현하거나 명세로 승격한 것이 아니다.

- 대상: 요청 접수, 권한, 작업공간 상태, 실행, 사용권, 감사 전달.

- 제외: 에이전트 실행 엔진 선정, 고객 코드 서버 실행, 결제, 채팅 자동 기동.

- S1·S2·S3·S7·S8은 [서비스 경계 초안 2](../analyze-service-boundary-design/SKILL.md)의 식별자다. 최종 서비스 수를 확정하지 않는다.

- 외부 에이전트의 결과 보고는 수신 기능이다. 보고 수신을 실행 요청으로 바꾸지 않는다.

<a id="owners"></a>

<a id="소유권과-호출-방향"></a>

## 2. 소유권과 호출 방향

| 소유자 | 판정·저장 책임 | 금지하는 접근 |
| --- | --- | --- |
| S1 접근 관리 | 현재 사용자·토큰·멤버십·권한 판정 | 다른 서비스 DB 직접 조회 |
| S2 작업공간 | 작업공간 소유 참조·상태·작업 활성화 | S3를 동기 호출하여 상태 응답 완성 |
| S3 실행·일정 | Run·Job·실행 이벤트·접수 중복 방지·작업 점유 | S7의 사용권을 자체 발급 |
| S7 사용량 | 한도 판정·용량 예약·갱신·해제·사용량 수신 | 사용권을 사용자 권한 증명으로 취급 |
| S8 감사 | 감사 수신·중복 방지·추가 전용 이력 | 업무 DB 수정으로 누락을 보정 |

- API·MCP 진입점은 소유 서비스로 전달한다. MCP가 API 앱의 Python 모듈을 가져오지 않는다.

- S3가 S2의 상태와 S1의 권한을 검사한다. S1은 모든 업무를 통과시키는 게이트웨이가 아니다.

- 각 서비스의 사용자 요청은 자체 경계에서 검증한다. 브라우저·큐의 actor/tenant 필드를 신뢰하지 않는다.

- 내부 호출은 호출 서비스와 위임된 사용자 권한을 구분한다. 호출 대상·행위·자원 범위를 제한한다.

- 다른 서비스 호출 중 로컬 DB 트랜잭션을 길게 유지하지 않는다.

- 독립 DB 사이의 검사와 저장은 하나의 원자적 동작이 아니다. 실행 직전과 안전 지점에서 재검사한다.

<a id="flow"></a>

<a id="실행-접수와-실제-시작"></a>

## 3. 실행 접수와 실제 시작

- **입력 확인**: 인증, 작업공간 바인딩, 입력 형식·크기, 요청 중복 키를 검사한다.

- **현재 상태 확인**: S2의 작업공간 상태와 S1의 실행 권한을 조회한다.

- **접수 가능 여부 확인**: S7 장애·한도 초과 시 새 요청을 거절한다. 이 검사는 실행 용량 예약이 아니다.

- **접수 트랜잭션**: S3가 Run, Job, 중복 키, 최초 이벤트, 전달 대기 기록을 함께 저장한다.

- **접수 응답**: 커밋 확인 후 queued와 run_id를 반환한다. 브로커 전달 성공을 기다리지 않는다.

- **작업 점유**: 전달된 job_id로 원본을 조회한다. 현재 실행 시도와 점유 세대를 검증한다.

- **시작 재검사**: 취소·권한·작업공간 상태를 다시 검사하고 S7에서 실행 용량을 원자적으로 확보한다.

- **시작 확정**: S3가 점유와 사용권 참조를 확인한 뒤 running을 저장한다. 성공 전 외부 작업을 시작하지 않는다.

- **실행과 종료**: 안전 지점마다 재검사한다. 결과 저장 후 점유 해제·사용권 해제를 재시도 가능한 방식으로 처리한다.

- *제안*: 대기 시간 동안 실행 슬롯을 점유하지 않도록 접수 검사와 실행 사용권을 분리한다.

- 접수 후 한도가 바뀌면 시작이 지연될 수 있다. 대기 상한·재검사 간격·최종 실패 정책은 미정이다.

- S7 예약 성공 후 S3 저장 실패 시 같은 예약 ID로 조회·해제를 재시도한다. 응답 유실만으로 새 예약을 만들지 않는다.

- 시작 전 예약은 자동 만료 가능해야 한다. 실행 가능성이 있는 예약은 중단 확인 없이 재사용하지 않는다.

- 접수 감사도 중요 변경으로 취급하는 안이다. 최종 중요 작업 목록은 별도 승인 대상이다.

<a id="api"></a>

<a id="api와-내부-계약-초안"></a>

## 4. API와 내부 계약 초안

- HTTP 경로는 제안이다. 기존 공개 API·MCP 도구의 호환성 조사를 마친 뒤 확정한다.

- 공개 요청은 인증된 사용자 기준으로 처리한다. 내부 서비스 자격증명을 브라우저에 전달하지 않는다.

| 계약 | 입력 | 출력·효과 |
| --- | --- | --- |
| POST /api/v1/workspaces/{id}/runs | agent_version_id, input_refs, idempotency_key | 202: run_id, queued, revision. 외부 실행 완료를 뜻하지 않음. |
| GET /api/v1/workspaces/{id}/runs/{run_id} | 경로 ID·현재 조회 권한 | 200: 상태, revision, reason_code, 결과 참조 |
| POST …/runs/{run_id}/cancel | idempotency_key, expected_revision | 대기 취소는 200. 실행 중 취소 요청은 202. |
| POST …/runs/{run_id}/retry | idempotency_key, expected_revision | 202: 새로운 run_id와 retry_of. 기존 이력 보존. |
| GET …/runs/{run_id}/events | 불투명 커서·페이지 크기 | 순서 있는 이벤트·다음 커서. 페이지마다 재인가. |
| S1 Authorize | 검증된 actor, action, resource, token 제한, S2 상태 근거 | allow/deny, decision_id, policy_revision, checked_at |
| S2 ResolveWorkspace | workspace_id, 호출 서비스 신원 | 소유 참조·상태·revision. 원본 토큰·자격증명 제외. |
| S7 CheckAdmission / AcquireCapacity | 범위·metric·수량·고정 예약 ID·실행 시도 | 접수 판정 / lease_id, epoch, expires_at, limit_revision |
| S7 Renew / Release / InspectLease | lease_id, epoch, 점유자·명령 중복 키 | 같은 사용권의 상태. 갱신 응답 유실은 유효기간 연장 근거가 아님. |
| S8 AppendAuditBatch | 인증된 producer, 버전별 감사 이벤트 | 항목별 저장·중복·거절 결과. 일괄 수신만으로 전체 완료 처리 금지. |

- HTTP와 MCP는 같은 업무 명령·결과 의미를 사용한다. HTTP 상태 코드를 MCP 결과 형식에 그대로 강제하지 않는다.

- 계약 버전, nullable 여부, enum, 최대 크기, 시간 형식, 오류 필드는 후속 스키마에 명시한다.

- S1의 과거 allow 응답은 영구 허가증이 아니다. safe point에서는 현재 판정을 다시 받는다.

- 외부 결과 보고의 입력 계약은 실행 Submit 계약과 별도로 유지한다.

<a id="data"></a>

<a id="데이터와-트랜잭션-경계"></a>

## 5. 데이터와 트랜잭션 경계

| 레코드·소유자 | 핵심 필드 제안 | 일관성 조건 |
| --- | --- | --- |
| Run · S3 | id, workspace_id, requested_by, agent_version_id, status, revision, retry_of | 불변 버전을 고정. 다른 DB의 ID는 외부 참조. |
| Job · S3 | id, run_id, task_type, status, attempt, claim_epoch, cancel_requested_at | Run과 로컬 FK. 실행 세대별 단일 점유. |
| IdempotencyRecord · S3 | workspace_id, operation, key, actor_id, request_digest, result_ref | (workspace_id, operation, key) 유일. 주체·입력 일치 확인. |
| RunEvent · S3 | event_id, run_id, sequence, type, occurred_at, 최소 payload | (run_id, sequence) 유일. 상태 변경과 같은 트랜잭션. |
| Outbox · 각 업무 서비스 | event_id, schema_version, producer, workspace_id, aggregate_id, sequence, payload | 업무 변경과 원자적 저장. 재전송에도 event_id 유지. |
| DeliveryState · 발신 서비스 | event_id, destination, attempts, next_attempt_at, acknowledged_at | 감사 원문과 가변 전달 상태를 분리. |
| CapacityLease · S7 | lease_id, reservation_id, scope, metric, quantity, holder, epoch, expires_at, state | 용량 검사·예약이 원자적이어야 함. 저장소 복구 후 옛 lease 부활 금지. |
| AuditEvent · S8 | producer, event_id, actor, action, resource_ref, outcome, occurred_at, request_id | (producer, event_id) 유일. 저장과 수신 중복 판정을 같은 트랜잭션으로 처리. |

- 식별자는 기존 정책의 UUID를 따른다. 시간은 시간대 의미를 보존한다.

- workspace_id는 개인·조직 작업공간 모두의 격리 기준이다. 개인 플랜의 내부 조직 표현은 아직 정하지 않는다.

- 원격 소유권 참조를 PostgreSQL 외래 키로 표기하지 않는다. 로컬 참조·RLS 적용 방식은 기존 DB 명세와 정합화한다.

- Run·Job·초기 이벤트·중복 방지·outbox 중 하나라도 로컬 저장에 실패하면 접수 전체를 롤백한다.

- 사용권 예약과 S3 저장은 교차 DB 원자성을 보장하지 않는다. 고아 예약 조회·해제 절차가 필요하다.

- 감사 payload에는 본문·토큰·자격증명·문서 내용을 넣지 않는다. 전송 대기 기록에도 같은 제한을 적용한다.

<a id="states"></a>

<a id="상태취소안전-지점"></a>

## 6. 상태·취소·안전 지점

| 현재 상태 | 허용 변화 | 조건 |
| --- | --- | --- |
| queued | running / cancelled / failed | 실행 자격 확보 / 시작 전 취소 / 영구적 접수 후 실패 |
| running | succeeded / failed / cancel_requested | 결과 확정 / 복구 불가 실패 / 취소·권한 회수·사용권 만료 중단 |
| cancel_requested | cancelled | 실행 중단과 진행 중 부작용 상태를 확인한 후 확정 |
| succeeded / failed / cancelled | 변경 없음 | 실패·취소 재시도는 새 Run. 과거 결과를 덮어쓰지 않음. |

- **경합 제안**: 결과 저장과 취소 요청은 S3 revision 검사로 직렬화한다.

- 성공이 먼저 커밋되면 취소는 terminal 응답을 반환한다. 취소가 먼저 커밋되면 늦은 결과로 성공 상태를 덮어쓰지 않는다.

- 중단 확인 전에는 cancelled로 표시하지 않는다. 외부 효과가 불명확하면 cancel_requested와 조정 필요 사유를 유지한다.

- 안전 지점: 점유 후, 외부 호출 전, 재시도 전, 업무 데이터 저장 전.

- 안전 지점마다 취소·현재 권한·작업공간 상태·점유 세대·사용권을 검사한다.

- 권한 검사 장애는 허가로 간주하지 않는다. 새 업무 동작을 보류하고 중단·조정 경로만 허용하는 안이다.

- 권한 회수 뒤에도 최소 상태·오류·감사 증빙은 내부 복구 권한으로 남길 수 있어야 한다. 사용자 콘텐츠 변경 권한과 구분한다.

- Job의 retry·dead 상태와 Run의 사용자 상태를 동일 enum으로 합치지 않는다. Job 시도 소진은 Run 실패로 연결한다.

- 사용권 만료 뒤 새 작업을 시작하지 않는다. 이미 진행 중인 외부 요청의 자동 롤백은 보장하지 않는다.

<a id="failures"></a>

<a id="중복장애사용권-복구"></a>

## 7. 중복·장애·사용권 복구

| 상황 | 응답·처리 제안 | 금지 |
| --- | --- | --- |
| 같은 요청 키·같은 입력 | 현재 권한 재확인 후 기존 run_id 반환 | 새 Run·새 용량 예약 생성 |
| 같은 키·다른 입력 또는 주체 | 409 충돌. 타인 요청의 존재·내용은 노출하지 않음. | 키만 맞으면 과거 결과 반환 |
| DB 커밋 응답 유실 | 503 REQUEST_OUTCOME_UNKNOWN. 같은 키로 재조회·재요청. | 실패 확정·자동 새 키 생성 |
| 브로커 장애·중복 전달 | outbox 재전송. Job 원본과 현재 점유를 확인. | 메시지 수만큼 실행 |
| S7 접수 검사 장애 | 503 USAGE_UNAVAILABLE. 새 접수 차단. | 한도 검사 우회 |
| S7 용량 초과 | 접수 단계 429 CAPACITY_EXCEEDED. 접수 후 시작 단계는 제한된 대기 제안. | 가격·초과 요금 자동 적용 |
| 갱신 응답 유실 | 마지막 확인된 만료 시각까지만 사용. 같은 갱신 명령 조회·재전송. | 클라이언트가 자체 TTL 연장 |
| 워커 연결 단절·lease 만료 | 중단 확인 또는 효과 차단 확인 후 용량 재사용 | 만료만 보고 기존 실행이 끝났다고 판정 |
| 사용권 저장소 유실·복구 | 신규 실행 차단. 활성 실행 재조정 후 새 epoch 발급. | 카운터를 0으로 초기화하여 즉시 재개 |
| 중앙 감사 장애 | 로컬 outbox 유지·재전송·적체 경보 | 중앙 미수신만으로 이미 커밋한 업무 롤백 |
| 중요 변경의 로컬 감사 저장 실패 | 업무 트랜잭션 롤백·실패 응답 | 감사 누락 상태로 성공 응답 |
| 외부 호출 타임아웃 | 외부 중복 키·상태 조회로 조정. 지원이 없으면 수동 확인. | 외부 효과가 없었다고 가정한 맹목적 재실행 |

- lease epoch를 보내는 것만으로 fencing이 완성되지 않는다. 효과를 받는 쪽에서 오래된 세대를 거절해야 한다.

- 외부 제공자가 이를 지원하지 않으면 실행 격리·종료 확인 또는 보수적인 용량 보류가 필요하다.

- 만료 판정에는 시계 오차·통신 지연의 안전 여유를 설계한다. TTL·갱신 주기·여유 수치는 아직 정하지 않는다.

- 동일 감사 ID의 다른 payload는 덮어쓰지 않고 거절·경보 처리한다.

- outbox 용량이 고갈되면 중요 변경도 실패할 수 있다. 적체 한도·보존·운영 대응은 배포 설계에 포함한다.

<a id="placement"></a>

<a id="디렉터리파일-계약에-연결할-구현-단위"></a>

## 8. 디렉터리·파일 계약에 연결할 구현 단위

- 아래는 **책임 매핑**이다. 실제 파일 생성·이동이나 전체 파일 명세 완료를 뜻하지 않는다.

- 원격 서비스 묶음 승인 뒤 정확한 파일명·공개 함수·의존성·오류·이전 소스를 확정한다.

| 기존 목표 소유자 | 이번 설계로 필요한 구현 책임 | 후속 검증 소유자 |
| --- | --- | --- |
| apps/api · apps/mcp | Run 접수·조회·취소·재시도 계약 변환. 소유 서비스 호출. | tests/api · tests/mcp |
| apps/jobs | Job 점유·안전 지점·중단 확인·outbox 전달·고아 예약 조정 | tests/jobs |
| packages/core/identity · organizations | 현재 권한 판정·위임 범위·권한 회수 규칙 | tests/packages |
| packages/core/workspaces | 작업공간 상태·소유 참조의 최소 조회 계약 | tests/packages |
| packages/core/agents · scheduling · reporting | Run/Job 상태·중복 접수·결과 수신·재시도 연결 | tests/packages |
| packages/core/usage · audit | 용량 정책·사용권 포트·감사 불변 데이터 규칙 | tests/packages |
| packages/adapters | 서비스별 DB·원격 호출·원자적 lease·outbox 저장 구현 | tests/packages · tests/integration |
| packages/contracts/schemas | 접근·작업공간·실행·사용량·감사 메시지 원본 | tests/contracts |
| packages/contracts/py · ts | 원본 스키마 기반 생성 코드. 수작업 이중 정의 금지. | tests/contracts |
| migrations · deploy/local | DB별 제약·역할·복구 이력, 서비스 기동·안전 상한·복원 절차 | tests/integration 및 단계 9 운영 검증 |

<a id="review"></a>

<a id="검수-항목과-다음-작업"></a>

## 9. 검수 항목과 다음 작업

- **작성 완료**: 핵심 흐름, 소유권, 계약 입출력, 데이터 제약, 경합·실패 대응의 초안.

- **미확정**: 서비스 묶음, 실행 엔진, 접수 후 대기 정책, 중요 감사 작업 범위.

- **기술 설계 잔여**: 서비스 인증 방식, lease/fencing 구현, 중복 키 보존, 오류 공개 범위, 메시지 크기·호환성.

- 기존 감사 실패 정책은 Q5와 정합화해야 한다. 이 문서가 기존 명세를 조용히 대체하지 않는다.

- 기존 조직 하위 팀·교차 DB FK·워커 권한 표현도 [충돌 목록](../analyze-service-boundary-design/SKILL.md#conflicts)을 따라 수정해야 한다.

- RTO 4시간·RPO 5분은 목표다. 실행 상태·외부 효과·감사 기록의 복구 검증 전에는 달성을 주장하지 않는다.

- 위 미확정 사항 중 파일 배치를 바꾸는 서비스 묶음·실행 책임을 먼저 검수한다.

- 승인된 경계에 맞춰 정확한 계약 스키마와 파일별 구현 기록을 작성한다.

- 목표 전체 트리와 기존 파일 이전 대응표를 갱신한다.

- 명세 영문 Skill·한국어 HTML을 정합화한 뒤 단계 1 구현 계약을 확정한다.

- 제품 테스트는 단계 8까지 보류한다. 위 검증 소유자 표는 향후 계획이다.

- 이 문서 작업에서는 제품 코드·DB·배포·사용자 설정을 변경하지 않는다.

- 근거: 현재 사용자 대화, 인터뷰 기록, 서비스 경계 초안, 저장소의 실행·사용량·문서 정책.

- 새 외부 조사 결과나 구현 성능을 주장하는 문서는 아니다.
