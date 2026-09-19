---
name: organization-implementation
description: 조직·구성원·세부 권한 구현 추적을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/organization-implementation.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# 조직·구성원·세부 권한 구현 추적

- 사용자 요청의 1–12번 전체가 범위다. 로컬 구현과 집중 검증을 추적한다. 운영 DB 적용과 배포는 이 작업에 포함되지 않는다.

- [x] 1. 권한 카탈로그, 범위, 기본 역할표
- [x] 2. 조직 사이드바와 구성원·팀·역할·설정 화면
- [x] 3. 조직 생성·수정·소유권 이전·마지막 소유자 보호
- [x] 4. 구성원 목록·검색·상세·상태·역할 관리
- [x] 5. 초대·수락·만료·재전송·취소
- [x] 6. 작업공간 배정·제외·역할 지정
- [x] 7. 대상별 세부 스코프 및 실제 작업별 검사
- [x] 8. 사용자 지정 역할 CRUD·부여
- [x] 9. 평면 팀 CRUD·팀원·작업공간 배정
- [x] 10. 최종 권한과 직접·팀 부여 경로
- [x] 11. 서버 검증·위임 제한·정지 차단·토큰 교집합
- [x] 12. 변경 이력 및 focused integration/browser tests

<a id="구현-정책"></a>

## 1. 구현 정책

- 조직 권한은 조직 관리에만 적용하고, 작업공간 콘텐츠는 직접 또는 팀 멤버십으로 접근한다. 소유자는 조직의 역할·배정을 관리할 수 있지만 콘텐츠 접근에는 공간 멤버십이 필요하다. 일반 관리자는 자신의 보유 권한 범위에서만 위임하며, 작업공간 역할 위임은 해당 공간 권한으로 검증한다. 여러 경로는 허용 권한의 합집합이다. 정지·제거된 조직 멤버십은 모든 공간 접근을 차단한다. 플랫폼 관리자는 기존의 별도 관리 권한을 유지한다. 소유권 변경·멤버십 변경은 조직 행 잠금으로 직렬화한다. 기존 broad grant는 마이그레이션으로 명시적 권한으로 변환한다.

- 리소스 단위 ACL, 외부 게스트, 공개/가입 요청 정책은 후속 확장 범위다. 스코프 선택 UI는 현재 지원하는 조직·작업공간만 제공하며 개별 문서 ACL을 약속하지 않는다.

<a id="항목별-검증-근거"></a>

## 2. 항목별 검증 근거

| 항목 | 구현 | 확인한 행동 |
|---|---|---|
| 1 | `app/modules/organization/permissions.py`, `.codex/skills/design-platform/references/organization-management.md` | 범위가 섞인 역할·알 수 없는 키·소유자 전용 권한 거부, 기본 역할표와 개별 설명 |
| 2 | `template/workspace/index.html`, `static/js/organizations.js`, `static/js/workspace.js` | 조직 메뉴, 네 관리 화면, 조직 이름·ID 표시와 조직 전환 시 갱신 |
| 3 | `OrganizationService.update/transfer/delete_organization` | 생성·이름 변경, 오래된 revision 거부, 이전 후 기존 소유자 권한 하향, 삭제 후 검색·접근 차단 |
| 4 | `OrganizationService.members/detail/update_member` | 이메일 검색, 역할·상태 변경, 제거 후 재초대 필요, 마지막 소유자 정지·제거 방지 |
| 5 | `OrganizationService.invite/accept_invitation/cancel_invitation` | 수락·재사용 거부·만료·재전송 토큰 교체·취소·재초대, 초대 역할 삭제 보호 |
| 6 | `OrganizationService.set_workspace_member` | 직접 배정·제외, 공간별 역할 적용, 마지막 활성 공간 소유자 보호 |
| 7 | 각 도메인 router/service 및 MCP | 문서 읽기와 쓰기 분리, 일정 수정·활성화·삭제, 에이전트·저장소 삭제, 로그 내보내기의 실제 권한 검사 |
| 8 | `OrganizationService.write_role/delete_role` | 역할 생성·수정·삭제·부여, 사용 중 삭제 거부, 브라우저에서 선택한 개별 권한만 저장 |
| 9 | `OrganizationService.write_team/set_team_member/set_team_workspace/delete_team` | 팀 생성·수정·삭제와 팀원·공간 연결, 높은 팀 역할을 통한 자기 권한 상승 거부 |
| 10 | `AuthorizationRepository.permission_sources`, 구성원 상세 | 직접·팀 권한 합집합 및 부여 경로, 직접 배정 제거 후 팀 권한 유지 |
| 11 | authorization, MCP verifier/transport, worker authority | 타 조직 ID 혼용 거부, 보유 권한 이상 위임·강등 거부, 정지 차단, 문서 조회 토큰의 정확한 상한, 일정 실행자 현재 권한 검사 |
| 12 | `tests/test_organization_management.py`, browser, 검증 scripts | 조직 audit 이벤트, 비관리자 강제 RLS, 마이그레이션 왕복, 실제 동시 소유자 정지, 화면 전환·역할 저장·초대·삭제 |

<a id="실행-증거-2026-09-06"></a>

## 3. 실행 증거 (2026-09-06)

- `scripts/verify-organizations.sh`: 새 pgvector/PostgreSQL 16 DB, `0022 → 0021 → 0022` 왕복,
  superuser/bypassrls가 아닌 DB 역할로 실제 HTTP 요청을 검증한다. 최종 5개 통과. 구성원,
- 초대, 팀, 역할, 소유권, 위임 제한, 토큰, 동시 변경의 여러 시나리오가 포함된다.
- `NODE_PATH=/tmp/af-pw/node_modules node tests/browser/organizations.cjs`:
  브라우저 흐름 통과. 실제 정적 화면을 사용하고 API 응답은 mock이다. 서버의 실제 권한·DB
- 동작은 위 HTTP/RLS 검증으로 별도 확인한다. 조직 ID 전환, 역할 설명·선택 저장, 구성원 상세 유지, 초대, 삭제 이름 검증, 삭제 후 남은 조직으로 복귀를 확인한다.
- `pytest -q tests/test_scheduling.py tests/test_workspace_ui.py`: 11개 통과.
- `pytest -q tests/test_mcp_server.py`: 1개 통과.
- `NODE_PATH=/tmp/af-pw/node_modules CLOUD_VERIFY_PYTHON=/tmp/organization-build-env/bin/python bash scripts/verify-cloud-platform.sh`:
  18개 통합·패키징, 22개 인증·인터페이스, 175개 도메인 검증 통과. 실제 HTTP 문서 브라우저,
- worker, 패키지 자산 검증을 포함한다. 프로젝트 venv에 없는 빌드 도구는 임시 venv로 제공했다. 기록: `/tmp/af-cloud-platform-verify-1788669763-664120.log`.
- 독립 검토는 권한 상승, 삭제된 조직의 일정, 일정 수정자의 실행 권한을 확인했다.
  발견 사항을 수정하고 거부 경로·실행자·조직 삭제 검증을 추가했다.
- 비활성 작업공간 제외 변경과 실제 DB 회귀 검증도 통과했다. 독립 검토자가 조직 검증 5개와 브라우저를 다시 실행해 통과했으며 1–12 로컬 구현 완료에 동의했다. 독립 기록: `/tmp/organization-independent-final.log`.

<a id="제한-및-적용"></a>

## 4. 제한 및 적용

- 테스트 실행 엔진은 기존에 존재하지 않는다. `test.execute`는 준비 중·선택 불가이며
  MCP 상태는 미구현을 명시한다. 테스트 실행 엔진 개발을 이 권한 관리 작업으로 가장하지 않는다.
- 화면에서 쓰는 조직 식별자는 고유한 `slug`다. UUID는 설정의 기술 정보와 기존 API
  경계에서 유지한다. slug는 가입 코드가 아니며 코드만으로 참여하는 기능은 없다.
- 감사 로그 내보내기는 최신 200건이며 전체 이력 내보내기로 표시하지 않는다.
- SMTP 발송은 설정된 메일 서버가 필요하다. 자동 검증은 발송 adapter를 대체하고
  저장·재전송·토큰 수락 동작을 검사한다.
- 변경은 현재 작업트리에 있다. 실제 서비스 사용 전 마이그레이션 `0022` 적용과 서비스
  재시작이 필요하며, 이 검증은 운영 환경에 변경을 가하지 않는다.

<a id="github-스타일-화면-정리"></a>

## 5. GitHub 스타일 화면 정리

- 개발자용 사이트라는 사용자 방향에 따라 조직의 기본 화면을 개요로 바꾸고 접근 가능한 작업공간을 먼저 표시한다. 사이드바는 개요·작업공간·구성원·팀·설정 순서다. 구성원과 대기 초대를 구분하고 역할·상태 필터를 제공한다. 역할 및 권한과 감사 로그는 설정 하위에 두며, 소유권 이전과 삭제는 위험 작업 영역에 둔다. 사용자 지정 역할은 기본 역할에서 시작해 세부 스코프를 조정할 수 있다. 자세한 근거와 검증은 `docs/processed/organization-github-alignment.md`에 기록한다.
