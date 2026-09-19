---
name: development-planning-20260905
description: 개발 일정 구현을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-05-development-planning.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-05-development-planning
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# 개발 일정 구현

- 사용자 승인 범위: 데이터 구조·API·사이드바·도메인/기능 상세·전체 타임라인·연동 검증 (1–6).

- 기능 도메인 → 세부 기능 → 개발 이슈. PostgreSQL plan_items에 kind와 parent_id로 구별하며 같은 Workspace 안에서만 계층을 연결한다.
- 기능의 목표 기간과 완료 조건은 직접 관리한다. 도메인 기간·상태는 기능에서 집계한다. 이슈 목표일은 선택이다. 담당자는 자유 텍스트 계획 표기이며 실행 지시가 아니다.
- Sidebar: 전체 일정, 접을 수 있는 도메인/기능 트리. Workspace area: 전체 타임라인, 도메인 기능 목록, 기능 상세/이슈 표, 행 펼침 편집.
- 주/달력 월, 오늘, 전체 맞춤, 출시 목표일, 기간 미정, 기한 초과, 막힌 이유, 기능 기간 밖 이슈 표시.
- API: tenant base /plan, GET snapshot; POST /items; PUT /items/{id} with revision; DELETE /items/{id}?revision=N; PUT /settings with launch_date and revision.
- workspace.read/workspace.manage, CSRF, RLS, 동일 Workspace 쓰기 잠금, optimistic revision. 부모 삭제는 하위 항목이 없을 때만 가능.
- 새 migration 0013. 기존 background schedules/jobs와 분리된다. 기존 작업표시줄 순서와 다른 탭은 유지한다.
- 소유 명세 동기화: sibling plugin skills/workspace/references/planning.md와 Human workspace/index.html 개발 일정 절. 일정 미결정 문구만 갱신한다.

- 검증 명령과 결과는 작업 완료 시 아래에 기록한다.

<a id="완료-검증-2026-09-05"></a>

## 1. 완료 검증 (2026-09-05)

- `.venv/bin/pytest -q tests/test_planning.py tests/test_workspace_ui.py tests/test_workspace_management.py tests/test_scheduling.py`: 18 passed.
- `tests/test_planning_integration.py`: 별도 PostgreSQL DB를 migration 0013까지 생성해 실행. 비-superuser `planning_verifier` 역할로 HTTP API CRUD·새 요청 재조회·잘못된 계층·기간·타 워크스페이스 부모·viewer 쓰기 거절·RBAC·CSRF·RLS·revision 충돌·동시 수정 200/409·출시 목표일을 검증했다. 감사 저장도 동일 테스트 DB로 격리했다.
- `NODE_PATH=/tmp/af-pw/node_modules node tests/browser/planning.cjs`: 브라우저 계층 생성·이슈 수정/초안 유지·기능 기간 조정·주/월·전체 맞춤·출시 목표·모바일·재조회·오류 복구·읽기 전용·공간 전환·CSRF·/factory 접두사 통과.
- 기존 `tests/browser/workspace-start.cjs` 통과. 기존 개인 워크스페이스 변경은 보존했다.
- 독립 Verification: 충돌 후 Cancel/Escape 복구, 접기 초점, 같은 공간의 오래된 응답 차단, 장기 일정 레이블 밀도와 좁은 화면 전체 맞춤을 별도 검증했다.
- 변경 대상 Ruff, planning Python Mypy, JavaScript 구문, 양 저장소 diff whitespace 검사 통과.
- 실행 중인 MCP DB에 migration 0013 적용, API 컨테이너 재시작 완료. /factory/health·신규 JS/CSS·OpenAPI 모두 HTTP 200; 제공 자산과 소스의 바이트 일치 및 계획 API 네 경로 등록 확인.

- 담당자는 현재 자유 텍스트 표기다. 항목 종류와 부모 이동, 드래그 일정 조정, 의존 관계선은 초기 구현 범위에 포함하지 않는다. 사용자 데이터 예시는 실제 Workspace에 생성하지 않았다.

- 새로고침과 기능 도메인 추가는 기본 사이드바 헤더 오른쪽의 SVG 아이콘 버튼으로 제공한다. 일정 선택 시에만 표시하며 추가는 편집 권한이 있을 때 제공한다. 본문에는 전체 일정과 도메인/기능 탐색 트리만 둔다.

- 공통 일정 관리 명칭 적용: 화면의 도메인·기능·이슈 호칭을 작업/하위 작업으로 통일했다. 헤더는 작업 추가, 부모 화면은 하위 작업 추가, 이름 필드와 열은 작업 이름이다. 기존 저장 구조·계층·집계/날짜 규칙은 유지한다.

<a id="최상위-선택-날짜와-필수-표시-2026-09-06"></a>

## 2. 최상위 선택 날짜와 필수 표시 (2026-09-06)

- 최상위 시작일·목표일은 각각 선택 입력이며 직접 값이 우선하고 비어 있는 쪽만 하위 작업에서 집계한다. 스냅샷의 표시 날짜와 configured_* 저장값·날짜 출처를 분리하여 이름만 저장해도 집계 날짜가 고정되지 않는다. 혼합 기간 역전과 부모 기간 이탈은 경고하며 날짜를 자동 조정하지 않는다. 최상위 상세와 전체 일정에 날짜별 출처를 표시하고, 이름만 *와 required를 표시한다. 선택 문구는 제거했다. MCP 규칙, 가져오기 검토 경고, 원문·패키지 안내, Human·AI 명세를 동기화했다.

- 검증: scripts/verify-planning-import.sh 20 passed (실제 PostgreSQL와 인증 MCP 포함), Chromium planning.cjs 통과 (최상위 날짜 생성·수정·비우기·집계 출처·필수 표시 포함). 현재 조직 권한 계약에 맞춰 테스트에 조직 멤버십을 추가했고, 테스트 DB 생성을 막던 organization_teams의 중복 유일 제약 이름만 migration 0022와 모델에서 구분했다.

<a id="타임라인-위치-겹침-수정-2026-09-06"></a>

## 3. 타임라인 위치 겹침 수정 (2026-09-06)

- 서버 style-src self CSP가 HTML inline style을 차단해 눈금·기준선·막대 위치와 차트 너비가 적용되지 않았다. 숫자 data 속성을 개별 CSSOM 위치·너비 속성에 적용하도록 변경했다. 오늘·출시 설명은 헤더의 독립 줄로 이동하고 작업 기간 정보에는 본문 기준선이 겹치지 않게 했다. 운영 동일 CSP를 브라우저 검사에 적용하여 눈금 간격·설명과 작업 행 분리·차트 및 막대 너비를 확인했다. 브라우저·독립 검사 통과, 실행 서버 JS/CSS 바이트 일치 및 CSP 유지 확인.

<a id="참고-디자인-반영-2026-09-06"></a>

## 4. 참고 디자인 반영 (2026-09-06)

- GitHub Projects 로드맵·Notion의 좌측 표·Jira 상하위 일정 막대를 참고해 작업 정보와 날짜 캔버스를 분리했다. 최상위도 요약 막대를 제공하며, 단일 날짜는 점·미정은 좌측 문구만 표시한다. 이름/기간 두 줄·하위 들여쓰기·출처 배지, 52px 헤더와 옅은 날짜 안내선으로 정리했다. 날짜 출처 상세는 작업 상세와 배지 title에 남긴다.

- CSP 브라우저 검사 및 데스크톱·모바일 이미지 확인 통과. 독립 검증에서 최상위 날짜 없음·시작일만·목표일만 세 경우와 접근성 설명을 추가 확인했다. 실행 서버 JS/CSS 바이트 일치 확인. 참고 링크는 소유 planning 명세에 기록했다.

<a id="타임라인-세로-공간-채움-2026-09-06"></a>

## 5. 타임라인 세로 공간 채움 (2026-09-06)

- 전체 일정의 타임라인을 작업 패널의 남은 높이를 채우는 flex 영역으로 변경했다. 제목·조작부·기간 요약은 고정되고 타임라인이 나머지 세로 스크롤을 소유한다. 캔버스와 날짜·오늘·출시 기준선은 하단까지 이어지며, 상세·가져오기 화면에서는 일반 문서 스크롤로 복귀한다. 브라우저 검사는 패널과 타임라인 하단 간격이 16px 이내이며 캔버스가 스크롤 viewport 전체 높이를 채우는지 확인한다.
