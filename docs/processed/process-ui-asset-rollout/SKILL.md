---
name: ui-asset-rollout
description: 공통 UI 에셋 제품 적용을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/ui-asset-rollout.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# 공통 UI 에셋 제품 적용

<a id="슈퍼-관리자-공통-에셋-검토-화면"></a>

## 1. 슈퍼 관리자 공통 에셋 검토 화면

- 기존 플랫폼 관리 영역의 표시 이름을 ‘슈퍼 관리자’로 변경하고 ‘공통 에셋’ 메뉴 추가.
  원본 카탈로그를 iframe으로 연결하며 새 탭에서도 검토할 수 있다.
- `/admin/assets/`와 JS/CSS/문서/라이선스 파일은 모두 `require_platform_admin`을
  통과해야 한다. 일반 사용자·조직 관리자에게 별도 권한을 부여하지 않는다.
- 실제 운영 계정의 권한 목록 변경이나 본인만 권한을 보유하는지의 DB 감사는 수행하지 않았다.
- 카탈로그 응답은 no-store. 인증된 카탈로그 응답에 한해서 같은 출처 iframe,
  컴포넌트의 동적 스타일과 data URL 아이콘 로드를 허용한다. 다른 화면의 보안 정책은 유지한다.
- 검토 파일만 wheel/Docker에 포함하며 node_modules·빌드 도구·릴리스 압축본은 제공하지 않는다.
  화면을 떠나거나 다른 메뉴를 열면 iframe을 제거한다.
- 검증: `tests/test_admin.py`의 GET/HEAD 401·403·200 및 경로 제한,
  `tests/browser/ui-screens.cjs`의 메뉴 진입·이탈,
- `tests/browser/admin-assets.cjs`의 실제 HTTP 보안 헤더·iframe·다이얼로그·알림, 1440/390px 레이아웃.
- 404 후속 수정: 실행 중인 Compose API는 app/static/template만 bind mount했고
  재시작 전 워커에는 신규 라우트가 없었다. ui-kit 읽기 전용 mount를 추가하고
- API 컨테이너를 재생성했다. 실서버 `/factory/admin/assets/`가 비로그인 요청에 401을 반환하고 health가 정상임을 확인했다. 기존 작업자·스케줄러는 재배포하지 않았다.
- iframe 차단 후속 수정: 호스트 Caddy의 전역 CSP/X-Frame-Options가 앱 응답에
  추가되어 카탈로그도 DENY로 차단됐다. `/factory/*`에서는 앱의 CSP/frame 정책만
- 사용하도록 Caddy 관리 API로 실서비스 설정을 reload했다. 외부 HTTPS 응답의 중복 정책 제거와 다른 사이트의 DENY 유지를 확인했다. `/etc/caddy/Caddyfile` 쓰기는 sudo 암호가 필요하여 아직 저장하지 못했다. 재시작 후에도 유지하려면 저장소 루트에서 `sudo patch /etc/caddy/Caddyfile < deploy/caddy-factory-headers.patch`를 실행한다. 이 패치는 원본에 dry-run 검증했으며 현재 실행 중인 설정과 같은 변경이다.

<a id="현재-판정--최근-통합-게이트"></a>

## 2. 현재 판정 — 최근 통합 게이트

- 아래는 현재 소스와 재실행 결과를 대조한 상태다. 뒤쪽의 날짜별 기록은 당시의 증거이므로 ‘아직 미적용’이라는 과거 문장은 이후 적용 기록과 함께 읽는다. 독립 에셋 키트의 완성과 전체 제품 전환 완료는 별도다. **전체 제품 전환은 미완료다.**

| 영역 | 현재 연결된 공통 요소 | 남은 적용/검증 경계 |
|---|---|---|
| 조직 | 버튼·필드·탭·확인·표·grid·메타데이터·상태 | 전체 상태별 시각 비교, 실제 조직 DB 게이트 |
| Workspace | 생성 필드·native dialog·이름/프로필/Activity 메뉴·픽셀 리사이저 | 기타 popup·중복 chrome 스타일·전체 lifecycle 검증 |
| 연동 | 필드·탭·확인·상태·메타데이터 | 폴더 비동기 응답/폴링의 전체 scope 전환 검증, 나머지 목록 배치 |
| MCP | 버튼·배지·아이콘·선택 필드·코드 작업 영역·연결 toast | 기타 상태/메타데이터의 잔여 개별 구현 |
| 일정 | 버튼·편집 필드·공통 상태·시각 토큰 | 보기/필터·목록/표 조합·dialog lifecycle 어댑터 |
| Reporting | 버튼·상태·배지·메타데이터 | 계층/이력 목록 조합 및 상태별 전면 시각 확인 |
| 계정/관리자 | 헤더·메타데이터·표와 셀 스타일·상태·응답 버전 검사 | 전체 조회 오류/권한 경계 및 전면 시각 검증 |
| 문서 | 도구·아이콘·메뉴·재귀 split·native tree 렌더러/키보드/선택 계산 | 탭 이동 어댑터와 나머지 특화 아이콘·스타일 |
| 인증 | 경량 필드·상태·테마 | Workspace 고급 번들 미로딩 유지, 전체 인증 방식 실환경 검증 |

- 대표적인 미완료 소스 근거:

- `static/js/document-editor.js`의 renderTree는 경로/행 액션 어댑터다. 계층 DOM과
  키보드는 범용 공통 탐색 트리에 연결한다.
- `static/js/workspace.js`의 sidebarResizer는 공통 픽셀 어댑터에 연결했다.
  문서의 비율 split과 구분하여 기존 180–520px·16px 키보드 간격 계약을 보존한다.
- `static/css/workspace.css`의 workspace-actions__popup/workspace-dialog,
  뒤쪽 shell/editor-header 규칙에 개별 시각 값이 남아 있다.
- 모든 픽셀을 삭제하는 대신 실제 계약·공통 토큰·기능별 예외를 나누어 정리해야 한다.

- 최근 같은 worktree에서 다시 실행한 제품 게이트:

- `NODE_PATH=assets/ui-kit/node_modules node tests/browser/<suite>.cjs`:
  organizations, workspace-start, ui-screens, mcp-handoff, planning, document-editor,
- ui-components, auth-assets, ui-boundaries **9종 통과**.
- `.venv/bin/python -m pytest tests/test_workspace_ui.py tests/test_organization_management.py tests/browser/reporting.py -q`:
  **13 passed, 1 skipped**. skip은 조직 전용 DB 미설정이며 DB 영속성 검증 증거가 아니다.
- 위 결과는 각 스위트가 실제 포함하는 viewport/상태/흐름에 한정한다. 전체 화면의
  시각 동일성, Firefox/Safari/보조기술, 운영 배포 또는 미구현 화면 완료를 뜻하지 않는다.

<a id="범위와-원칙"></a>

## 3. 범위와 원칙

- 공통 에셋을 실제 화면의 표현·상호작용 구현으로 사용한다. 인증, 권한, API payload, 서버 상태 해석, 저장/재조회, 작업공간 전환 생명주기는 보존한다. 기존 사용자 변경은 덮어쓰지 않는다. 데모 composition의 문서/연동 필터나 단일 필드 설정 폼을 제품 기능으로 대체하지 않는다.

<a id="적용-순서와-남은-범위"></a>

## 4. 적용 순서와 남은 범위

1. 기반: `/static/ui/core.js` 동기 브리지와 공유 테마 연결. 기본 컴포넌트는
   외부 라이브러리 없이 번들링. 고급 컴포넌트의 필요 시 로딩·해제는 후속 적용.
2. 조직: 버튼, 기존 native control을 보존하는 필드, 로딩 상태 적용.
   구성원/초대 탭, 기존 confirm 작업, 액션 행·기술 메타데이터도 공통화.
- 조직의 나머지 리소스 레이아웃과 상태별 검증은 남음.
3. Workspace: 아이콘, 헤더, 목록, 생성 폼, 메뉴. Activity 의미·순서 보존.
4. 연동/MCP: 목록·상세, 상태, 폴더 선택, 확인 창, 코드·복사 액션.
   OAuth, 폴링, 페이지 커서, 토큰 삭제·비밀 값 초기화 보존.
5. Reporting/관리자/계정: 목록·메타데이터·상태·표 주변 UI.
6. Planning: 필드·다이얼로그·탭·필터. Kanban/날짜/충돌 처리 보존.
7. 문서: 아이콘·메뉴·도구부터 적용. 재귀 split과 tree는 제품 어댑터가 필요하며
   기존 탭 이동·선택·렌더러·살아 있는 DOM 이동을 보존한다.
8. 로그인/초대: 최소 기본 컴포넌트만 적용. 인증·Google 브랜딩·리다이렉트 보존.

- 업로더는 제품/API 요구 없이 추가하지 않는다. Tabulator/PDF/차트의 내부 구현은 교체 대상이 아니다.

<a id="빌드와-검증"></a>

## 5. 빌드와 검증

- 원본: `assets/ui-kit/`; 제품 산출물: `static/ui/` (직접 수정하지 않음).
- 빌드: `node assets/ui-kit/scripts/build-product.mjs` (설치된 esbuild 필요).
- 동기화 검증: `node assets/ui-kit/scripts/build-product.mjs --check`.
- 제품 회귀: `NODE_PATH=assets/ui-kit/node_modules node tests/browser/organizations.cjs`
  및 `tests/browser/workspace-start.cjs`.
- 에셋 회귀: `node assets/ui-kit/scripts/verify-all.mjs`.

- 각 단계는 해당 화면의 키보드·좁은 폭·긴 한국어, 정상/로딩/오류/권한/빈 상태, 중복 제출, scope 전환 후 정리, 기존 요청 payload, 실제 저장 재조회를 확인한다. 브라우저 mock API 테스트는 DB 영속성의 증거로 간주하지 않는다. 전체 제품 적용은 진행 중이며 첫 화면의 통과로 완료 처리하지 않는다.

<a id="2026-09-09-기반조직-기본-요소-적용-검증"></a>

## 6. 2026-09-09 기반/조직 기본 요소 적용 검증

- 제품 빌드 및 `--check` 통과. 기본 JS 4,399 bytes, 공유 theme 11,074 bytes.
- 조직 브라우저 시나리오 통과: 기존 관리 흐름, 1400/390px 개요 overflow,
  native control 동일성·FormData·required/maxLength·이벤트·label 연결·설명 보존.
- Workspace 시작 브라우저 시나리오 통과: 생성/실패/반복 생성, 전환, 오래된 응답,
  모바일, 재시도, `/factory` 경로 접두사와 CSRF.
- 에셋 `verify-all.mjs` 전체 통과.
- `.venv/bin/python -m pytest tests/test_workspace_ui.py tests/test_organization_management.py -q`:
  12 passed, 1 skipped. 전용 `ORGANIZATION_TEST_DATABASE_URL`이 없어 DB 통합 테스트는
- 실행되지 않음. 실제 DB 저장 검증 완료를 뜻하지 않음.
- `git diff --check` 통과.

- 조직의 모든 상태와 후속 제품 화면에 대한 전체 시각/접근성 검증은 아직 남아 있다.

<a id="조직-탭확인-창레이아웃-후속-적용"></a>

## 7. 조직 탭·확인 창·레이아웃 후속 적용

- 구성원/초대는 공통 `tabs` 사용: 연결된 tab/tabpanel, 방향키·Home/End,
  선택 상태 및 roving tabindex. 설정 페이지 전환은 기존 navigation 의미 보존.
- 팀/역할 삭제, 구성원 상태 변경/제거, 소유권 이전의 기존 confirm을
  `createNativeConfirm`으로 연결. 조직 이름을 직접 입력하는 삭제 절차는 그대로 유지.
- Escape/취소는 mutation 없이 원래 액션에 focus 복귀. 조직 전환/reset은
  대기 Promise를 false로 종료하고 dialog 제거. 응답 뒤에도 generation 검사.
- 공통 `inline`/`metadataList`를 사용하고 대체된 feature CSS 제거.
- 조직 브라우저 테스트에 팀 삭제 취소/승인/화면 reset, 탭 키보드 검증 추가.
- 경량 native dialog는 소유한 어댑터이며 기존 Web Awesome dialog/drawer
  에셋을 제거하거나 모든 고급 overlay 적용을 완료했다는 뜻이 아님.

<a id="연동-화면-1차-적용"></a>

## 8. 연동 화면 1차 적용

- `bindTabs`를 에셋에 추가하고 생성형 `tabs`도 같은 바인더를 사용하도록 통합.
  연동의 기존 버튼/패널/data 속성을 유지하면서 aria-controls/labelledby,
- roving tabindex, 방향키/Home/End를 공유한다. 초기 바인딩은 API를 호출하지 않는다.
- Drive 폴더 선택·열기·더 보기 버튼과 범위 이름 필드를 공통 컴포넌트로 전환.
  입력 요소의 name/required/maxLength 및 기존 제출 핸들러 보존.
- 수집 중지와 인증 해제는 공통 확인 창 사용. 취소/Escape는 요청하지 않고,
  승인 시 캡처한 조직/작업공간/대상 경로에 기존 PATCH/DELETE 요청만 전송.
- generation/context/선택 대상 검사로 오래된 승인·응답의 UI 반영을 차단한다.
- open/reset/연결 선택/카탈로그 이동 시 확인 창 해제.
- 연동의 정적 액션 버튼·리소스 행·상태·메타데이터 및 비동기 폴더/폴링 전체
  생명주기 검증은 후속 범위로 남음. OAuth·폴링 로직 자체는 이번 단계에서 교체하지 않음.

<a id="상태메타데이터--reporting관리자-기본-요소"></a>

## 9. 상태·메타데이터 / Reporting·관리자 기본 요소

- 연동의 로딩/빈 폴더/조회 오류/명시적 연결 검사 성공은 `setStatus`로 표시.
  기존 live region 참조와 선택자를 유지하고, 빈 메시지는 숨기며 loading 이후
- aria-busy를 제거한다. 서버 상태의 의미와 OAuth/갱신 로직은 바꾸지 않는다.
- 연동 메타데이터는 `af-metadata-grid` 사용. feature의 중복 3열 스타일 제거,
  1440px 3열 / 390px 1열 및 긴 문자열 overflow 검증 추가.
- Reporting의 위임 이벤트용 버튼 HTML은 공통 button DOM에서 직렬화한다.
  action/id 데이터와 텍스트 escaping, 기존 이벤트 위임·보고 freshness 계산 보존.
- 상세/전체 조회의 로딩·오류는 공통 status 사용.
- 관리자 빈 표와 조회 오류도 공통 status 사용. 표 데이터·권한·API 처리는 유지.
- 검증: 연동/account/admin 브라우저, 에셋 전체 검증, Workspace Python 10개 통과.
  Reporting 실브라우저 테스트 1개 통과. 전체 제품 리팩터링 완료는 아님.

<a id="일정-기본-요소-적용"></a>

## 10. 일정 기본 요소 적용

- 위임 액션 버튼의 스타일·종류는 공통 button이 생성한다. 기존 escape된
  label/속성 조각과 소유한 SVG는 제품 어댑터에서 보존한다.
- 작업 편집 및 출시 목표일 native dialog의 입력/select/textarea를 fieldFor로
  연결. name/value/required/maxLength/임시 저장·제출 이벤트는 기존 요소에 유지.
- 필수 표시의 텍스트·별표가 한 줄에 남도록 처리한다.
- Kanban/타임라인 날짜 계산·기간 충돌·revision·가져오기 API는 변경하지 않는다.
  계획 특화 아이콘·헤더·탭·상태 및 dialog 전체 생명주기 공통화는 아직 남음.

<a id="mcp-기본-요소--제품-svg-연결"></a>

## 11. MCP 기본 요소 / 제품 SVG 연결

- 토큰 폐기·영구 삭제 버튼은 공통 button 사용. 토큰 상태는 공통 badge 사용하되
  진단 클라이언트의 서버 통신 확인과 실제 MCP 연결 증거를 구분하는 기존 계산 유지.
- 제품 core에 준비된 Tabler SVG icon/iconButton을 노출. 토큰 목록 새로고침에
  적용하며 기존 버튼 자체, 이벤트, aria-label/title을 보존한다.
- `static/ui/tabler-LICENSE`, `icons.provenance.json`을 빌드에 포함하고 --check로
  확인한다. 출처 URL·원본 해시와 배포된 라이선스의 실제 상대 경로를 유지한다.
- 토큰 발급/조회/폐기/삭제 API, 비밀 값 초기화, 다운로드·복사 fallback은 그대로다.
  MCP 나머지 필드·레이아웃·코드 액션과 전 화면 SVG 통합은 남음.

<a id="문서-도구-기본-요소"></a>

## 12. 문서 도구 기본 요소

- 문서 도구/탭 닫기/PDF 조작 버튼은 공통 button에서 생성하고 기존 de-button
  도구 배치·접근성 이름·이벤트 전파 중단을 보존한다. 재시도 버튼도 공통화.
- 닫기/아래·오른쪽 펼침/추가/더보기는 준비된 SVG 에셋을 사용하고 중복 path 제거.
  파일·폴더·고정·분할 등 아직 에셋 매핑이 없는 특화 아이콘은 보존.
- 문서 브라우저 시나리오 통과. 별도 DOCUMENT_HEADERS_ONLY=1 검증에서
  180–520px 사이드바의 도구 배치·검색·접기·키보드 검증 통과.
- tree 다중 선택·탭 drag/drop·재귀 split·렌더러·메뉴 생명주기 구현은 아직
  공통 어댑터로 교체하지 않았다. 첫 도구 요소 적용으로 문서 전체 완료 처리하지 않음.

<a id="인증-화면"></a>

## 13. 인증 화면

- 로그인/초대는 `/static/ui/auth.js` (3,098 bytes)만 사용. SVG·Workspace 동작·
  vendor 런타임은 포함하지 않는다. build-product의 생성/동기화 검사에 포함.
- 로그인 이메일/비밀번호는 fieldFor 사용. name/autocomplete/minlength/required,
  FormData payload, 중복 제출 방지, 로그인 후 이동, Google 브랜드 버튼 보존.
- 초대 화면에 공유 테마·카드 배치를 연결하고 오류는 공통 setStatus 사용.
  초대 validation/sessionStorage/history/redirect 동작은 기존대로 유지.
- ui-components 브라우저 통과: 로그인 실패·중복 제출·390px overflow 포함.
- auth-assets 브라우저 통과: 잘못된 링크, 저장소 차단, 정상 임시 보관/redirect,
  `/factory` 접두사, 390px, Workspace core 미로딩 확인.

<a id="작업공간-생성--메뉴-키보드"></a>

## 14. 작업공간 생성 / 메뉴 키보드

- 작업공간 생성 이름 필드를 fieldFor로 연결. 동일 input의 id/name 및 form.reset,
  생성 payload·중복 제출·생성 후 재조회/선택 흐름 유지.
- 준비된 popover의 메뉴 키보드를 menuKeyboard 모듈로 분리. 카탈로그 popover와
  제품 문서 메뉴가 같은 방향키/Home/End/Escape/Tab/문자 검색 동작을 사용한다.
- 항목의 disabled/aria-disabled/hidden을 고려한다.
- 문서 메뉴의 위치 계산·포인터 닫기·scope reset은 기존 소유자에 남아 있다.
  Floating UI 위치/관찰자 정리와 Workspace의 다른 메뉴 통합은 후속 작업이다.

<a id="문서-메뉴-위치-계산"></a>

## 15. 문서 메뉴 위치 계산

- Floating UI dom/core/utils만 포함하는 독립 positioning.js (45,753 bytes)를
  Workspace에 연결. 인증 페이지는 이 번들을 로드하지 않는다.
- 문서 메뉴는 마우스 가상 좌표 또는 키보드 실행 요소를 기준으로 flip/shift 적용.
  좁은 창에서는 메뉴 자체의 최대 크기와 스크롤을 제한한다.
- close/reset에서 autoUpdate 해제. disposed/revision 검사로 닫힌 메뉴에
  비동기 결과가 반영되지 않도록 한다. 기존 메뉴 액션/포커스 동작 보존.
- 배포 산출물에 세 패키지의 라이선스와 고정 버전·resolved/integrity 기록 포함.
  build-product --check가 번들 및 출처 기록의 동기화를 검사한다.
- 문서 브라우저 회귀 통과. 화면 가장자리 배치와 해제 후 resize 무반영 테스트 추가.
  다른 Workspace 메뉴 및 카탈로그 popover의 위치 어댑터 통합은 아직 남음.

<a id="제품-적용-중간-통합-검증"></a>

## 16. 제품 적용 중간 통합 검증

- 같은 현재 worktree에서 organizations/workspace-start/mcp-handoff/planning/
  document-editor/ui-components/ui-screens/auth-assets 브라우저 스위트 8종 통과.
- 에셋 verify-all 전체 통과. 제품 build-product --check 통과.
- Python workspace UI/조직/Reporting 브라우저 묶음: 13 passed, 1 skipped.
  skip은 전용 조직 DB 미설정이며 실제 DB 영속성 완료 증거가 아니다.
- 배포 아카이브를 현재 에셋 소스로 갱신하고 독립 추출 후 해시·모듈·CSS·SVG·
  390px 카탈로그·확인 창 검증 통과. 제품 적용 기록도 아카이브에 포함한다.
- 초기 에셋 ACCEPTANCE/SCOPE는 과거 단계의 범위로 명확히 표시했다.
  전체 제품 적용 완료, 운영 서버 배포, Firefox/Safari/보조기술 인증은 주장하지 않는다.

<a id="작업공간-이름-변경-메뉴"></a>

## 17. 작업공간 이름 변경 메뉴

- 작업공간/그룹 이름 변경 메뉴는 공통 button/menuKeyboard/positionMenu 사용.
  개별 화면 좌표 clamp 제거. 기존 인라인 이름 편집과 API·권한 오류 처리는 유지.
- 메뉴 닫기, 목록 재렌더링, 작업공간 진입/목록 로딩에서 위치 관찰자 해제.
  Escape/Tab은 원래 실행 요소로 포커스 복귀.
- 그룹 메뉴 Escape 복귀 및 Home 이동 검증을 workspace-start에 추가.
  Activity 표시 설정 메뉴는 별도 의미(menuitemcheckbox)가 있어 아직 미전환.

<a id="공통-native-table"></a>

## 18. 공통 native table

- 조직/관리자의 중복 table 생성 코드를 resourceTable로 통합.
  scope=col, 빈 행 colspan, null 표시 및 DOM 액션 셀을 보존한다.
- 조직의 중복 table CSS는 공통 af-table/af-table-scroll로 대체.
  관리자 표의 넓은 데이터 열 표현은 기존 admin-table-shell 규칙을 유지한다.
- 조직/관리자 브라우저 통과. HTML 유사 문자열의 text 처리, DOM 셀 동일성·
  이벤트 보존, 빈 행 colspan과 열 제목 scope 검증 추가.

<a id="조직-목록-레이아웃"></a>

## 19. 조직 목록 레이아웃

- 개요/작업공간 목록의 컨테이너를 에셋 grid로 전환하고 중복 grid CSS 제거.
  1400px 3열 / 390px 1열, 긴 한국어 식별자의 컨테이너 내부 줄바꿈 검증 추가.
- 조직 화면의 gap/margin/padding 중 비표준 5/6/7/10/14/18/20/26px 값을
  공유 간격 토큰으로 정리. 도메인 폭 제한과 아이콘/아바타 크기는 별도 유지.
- 기존 목록의 개수 제한·열기 액션·상태·권한·API는 변경하지 않음.

<a id="조직-권한빈-상태"></a>

## 20. 조직 권한·빈 상태

- 구성원/팀/역할/감사 로그/초대의 권한 없음과 미선택/빈 작업공간 상태를
  공통 status의 permission/empty로 통합. 서버 permissions/is_owner 판단은 보존.
- 조직 브라우저에 권한 없는 구성원·팀·역할의 상태 표시 및 목록 API 미호출,
  접근 가능한 작업공간이 없는 경우의 empty 표시를 추가 검증한다.

<a id="공통-탭-경계-상태-수정"></a>

## 21. 공통 탭 경계 상태 수정

- [P1] 비활성 상태 — 모든 탭이 disabled이면 선택되지 않은 패널도 모두 노출됨. Evidence: ui-boundaries.cjs의 수정 전 실행에서 visible panels=2, tabindex=[0,0]. Fix: bindTabs 초기화에서 모든 panel을 숨기고 aria-selected=false/tabindex=-1을 설정한 뒤 유효한 시작 탭만 선택한다. 잘못된 initial 값은 첫 enabled 탭으로 보정. Verification: 모든 탭 disabled, 이후 enable/select, destroy 뒤 클릭·select 콜백 무반응을 제품 번들에서 검증. 공통 컴포넌트 경계 테스트를 추가함.

<a id="재귀-분할-적용-준비-아래-제품-적용-기록-이전-단계"></a>

## 22. 재귀 분할 적용 준비 (아래 제품 적용 기록 이전 단계)

- 기존 createSplitPane을 독립 splitter.js로 분리하고 components.js에서 재노출.
  제품 전용 bundle은 Zag vanilla/splitter 의존성만 포함하며 아직 템플릿에 로드하지 않음.
- setSizes와 소유자가 지정하는 접근성 label 옵션 추가. 종전 카탈로그 동작은 유지.
- 제품용 splitter.js 128,758 bytes. 실제 포함된 패키지를 빌드 입력에서 찾아
  라이선스와 출처 기록을 배포 산출물에 포함하며 --check로 확인.
- 중첩 패널의 독립 비율 25/75·60/40과 ID 고유성을 실제 Chromium에서 검증.
  레이아웃이 정착한 뒤 크기를 변경하는 시나리오다.
- 기존 문서 그룹 DOM을 직접 부모 Zag panel로 삼으면 자식 root의 id/data 속성이
  부모 panel 속성과 충돌할 수 있다. 각 분기용 고정 panel 래퍼와 normalize/reset
- 해제 연결이 필요하며 실제 문서 분할 전환은 아직 완료하지 않음.

<a id="재귀-문서-분할-제품-적용-및-검증"></a>

## 23. 재귀 문서 분할 제품 적용 및 검증

- Workspace에서 독립 splitter 번들을 로드하고 각 재귀 분기에 고정 panel 래퍼를
  두어 부모 panel과 자식 split root의 ID/data 속성 충돌을 방지한다.
- 기존 그룹 DOM 이동, 탭 이동, 분할 비율, 최대화/복원은 문서 소유자가 유지한다.
  normalize에서 제거된 분기의 어댑터를 해제하고 reset에서 전체 바인딩을 해제한다.
- 제품 CSP는 완화하지 않는다. 제품 전용 vendor 어댑터는 style 문자열의
  setAttribute 대신 CSSOM 속성 쓰기를 사용한다. 전역 resize cursor는 정적 CSS와
- 소유자별 data 속성으로 표시하고 해제한다.
- 기존 방향키 5% 이동 간격을 옵션으로 유지한다. 라이브러리의 flex:0 0 auto가
  기존 flex-basis 두께를 덮어쓰므로 가로 width/세로 height를 각각 5px로 명시한다.
- 수정 전 실제 포인터 resize assertion이 실패했고 수정 후 통과했다.
- document-editor 브라우저 시나리오 통과: 가로/세로 분할선 실제 두께, 키보드와
  포인터 조절, 최대화/복원, 중첩 그룹 제거, 탭 이동, 문서 렌더링 및 CSP 오류 검사.
- ui-boundaries 통과: 중첩 비율 25/75·60/40, ID 고유성, 드래그 중 destroy 후
  전역 커서 제거. 에셋 verify-all 전체 통과.
- 이 결과는 문서 tree 공통화, 전체 제품 시각 검증 또는 운영 배포 완료를 뜻하지 않는다.

<a id="mcp-필드코드-작업-영역-적용"></a>

## 24. MCP 필드·코드 작업 영역 적용

- 클라이언트/사용 환경/토큰 선택 및 AI 지침 복사 fallback을 fieldFor로 연결한다.
  기존 native control과 선택값·이벤트를 유지하며 컨테이너의 data 속성과 hidden을
- 보존해 환경별 표시 및 fallback의 보안 초기화 흐름을 유지한다.
- 공통 bindCodeOperation을 추가해 명령·설정·선택 토큰 영역의 헤더/액션,
  코드 글꼴·overflow·도움말 배치를 공유한다. 기존 label·control·button DOM은
- 복제하지 않는다. 도움말을 aria-describedby에 연결하고 기존 설명 ID를 보존한다.
- 중복 코드 영역/토큰 영역 CSS를 제거한다. 명령 줄바꿈·설정 행수·AI fallback
  높이 등 제품별 표시 정책은 기존 feature 스타일에 남긴다.
- ui-boundaries: 입력 동일성, readonly, 값 보존, 기존 버튼 이벤트, 반복 적용 시
  설명 ID 중복 방지, 비밀 값의 HTML 미복제를 검증한다.
- MCP 브라우저: 공통 필드/코드 클래스, label/help 연결, password 유지 및
  13개 클라이언트/전체 환경 변형, 다운로드·복사 fallback·오류·오래된 응답·
- 390px 기존 시나리오 통과. API와 연결 증거 판단은 변경하지 않는다.

<a id="계정관리자-콘텐츠-레이아웃"></a>

## 25. 계정·관리자 콘텐츠 레이아웃

- 공통 metadataGrid 생성기를 추가하고 관리자 개요의 개별 metric 카드를
  정의 목록으로 전환한다. API 키·값·순서는 유지하고 텍스트 노드로 출력한다.
- 계정의 기존 조직/작업공간 dd와 data 참조를 유지하며 같은 메타데이터 grid를
  적용한다. 계정과 관리자 헤더·콘텐츠 여백은 af-page-header/af-page-content를
- 사용하고 장식용 영문 eyebrow와 중복 카드/메타데이터/제목 CSS를 제거한다.
- 계정 이메일은 긴 식별자를 내부에서 줄바꿈하고 700px 이하에서 아바타와
  상세 내용을 순서대로 쌓는다. 계정/관리자 API 및 정보 갱신 로직은 변경하지 않는다.
- ui-screens에서 1440/390px 계정·관리자 metadata 열 수, 데이터 보존,
  긴 이메일 overflow와 기존 연동·오류·권한 시나리오 통과.
- workspace-start, 에셋 verify-all 통과. Python workspace UI 10개 통과.
  관리자 비동기 응답 경합 및 전 화면 시각 검증은 이 결과의 검증 범위가 아니다.

<a id="프로필-메뉴-공통-동작"></a>

## 26. 프로필 메뉴 공통 동작

- 프로필 메뉴는 공통 af-popover 스타일과 positionMenu/menuKeyboard를 사용한다.
  기존 사용자 정보와 로그아웃 버튼·API 핸들러는 유지한다.
- 버튼과 메뉴의 aria-controls/labelledby를 연결하고 클릭 또는 위/아래 방향키로
  열면 첫 메뉴 항목에 focus를 둔다. Escape는 실행 버튼으로 복귀하고 Tab은
- 메뉴를 닫은 뒤 기본 탭 이동을 허용한다. 바깥 클릭은 focus를 강제로 옮기지 않는다.
- 닫기/다시 열기/pagehide에서 위치 관찰자를 해제한다. 고정 위치와 viewport
  flip/shift는 공통 모듈이 소유하며 개별 absolute 좌표·그림자·반경은 제거한다.
- workspace-start에서 1440/390px 가장자리 배치, 키보드 열기/Home/Escape/Tab,
  aria-expanded와 포커스 복귀, 바깥 클릭 닫기 통과. ui-screens 회귀 통과.
- Activity 체크 메뉴는 별도 의미를 유지하며 아직 공통화 후속 범위다.

<a id="activity-체크-메뉴-후속-적용"></a>

## 27. Activity 체크 메뉴 후속 적용

- 표시 설정 메뉴는 공통 button/Tabler check, af-popover, positionMenu 및
  menuKeyboard를 사용한다. menuitemcheckbox/aria-checked 의미와 기존 사용자별
- 저장·권한 필터·Activity 순서·전체 숨김 후 복구 동작은 유지한다.
- 체크 시 메뉴를 재생성하지 않고 해당 버튼의 aria-checked와 아이콘만 갱신해
  키보드 포커스를 유지한다. 위치 관찰자는 닫기/다시 열기/pagehide에서 해제한다.
- Escape/Tab은 실행 요소로 복귀한다. 실행 Activity가 숨겨졌다면 사용 가능한
  Activity 또는 전체 숨김 상태의 설정 버튼으로 복귀한다.
- 작업공간 이름 변경 메뉴에도 같은 overlay 클래스를 적용하여 기존 공통
  positionMenu와 스타일 계약을 맞춘다. 개별 그림자·반경·고정 좌표 CSS 제거.
- workspace-start: Home/End/방향키, Space 반복 체크와 포커스 보존, 390px
  viewport 재배치, 전체 숨김 후 설정 버튼 focus, 표시 설정 저장/복구 통과.
- ui-screens 회귀 통과. 전체 셸 공통화 및 문서 tree 전환 완료를 뜻하지 않는다.

<a id="일정-타임라인-시각-토큰"></a>

## 28. 일정 타임라인 시각 토큰

- 일정 CSS에 남은 직접 색상값을 공통 텍스트/표면/테두리/상태 토큰으로 연결한다.
  ui.css에 차트 격자·주말/현재일 밴드와 상태 배경 토큰을 추가하며 의미 색상에서
- 파생한다. 날짜 위치·기간 길이·상태 계산과 기존 텍스트/아이콘은 유지한다.
- 행의 3px 세로 여백은 4px 변경 시 기존 compact row 높이 검사에서 실패하여
  기능 치수로 유지한다. 공통 간격 정리를 이유로 행 밀도 계약을 변경하지 않는다.
- planning 브라우저 통과: CRUD/임시 입력/기간 조정/타임라인 fit·주·월·출시일,
  모바일·재조회·오류·읽기 전용·조직 전환·CSRF·경로 접두사.
- 실제 브라우저에서 공통 link 토큰을 임시 변경하여 오늘 표시선·캡션 테두리가
  함께 바뀌는 것을 확인하고 원래 값으로 복원한다. 전체 일정 컴포넌트 전환이나
- 색 대비에 대한 전면 접근성 인증을 의미하지 않는다.

<a id="일정-작업-결과오류-상태"></a>

## 29. 일정 작업 결과·오류 상태

- 저장 결과, import 검토 경고/오류, 기간 검증 및 mutation 오류를 공통
  setStatus에 연결한다. 폼/예약 메시지는 af-status--inline 변형으로 외곽 박스
- 없이 표시한다. 조회 실패는 공통 error 상태를 사용하고 기존 재시도를 유지한다.
- 긴 dashboard 메시지는 한 줄 예약 공간보다 커질 수 있게 해 겹침을 방지한다.
  성공은 status, 오류는 alert로 표시하며 메시지 종류별 색상을 공통 모듈이 소유한다.
- 저장 후 재조회가 실패하면 성공 메시지를 추가하지 않는다. 서버 저장과 화면
  재조회는 별개이며 기존 실패 안내와 재시도 경로를 유지한다.
- planning 브라우저에 잘못된 기간 입력의 공통 alert·입력값 보존·mutation
  미전송과 조회 실패 공통 상태 검증을 추가한다. 날짜 계산/API payload는 그대로다.

<a id="reporting-배지메타데이터"></a>

## 30. Reporting 배지·메타데이터

- 작업 목록과 상세의 상태를 공통 badge로 표시한다. completed/failed/
  input_required만 success/error/warning에 매핑하고 그 외 상태는 중립 배지로
- 표시한다. 상태 한국어 이름과 freshness 계산·폴링·마지막 snapshot 보존은 유지한다.
- 에이전트 역할/책임/범위/수정/소유자/보고 시각과 작업 시작/종료/수정은 공통
  metadataGrid로 출력한다. plain text 날짜와 HTML용 escaping을 구분하여
- 메타데이터를 중복 escape하지 않는다. 작업이 없는 목록은 공통 empty 상태다.
- 기존 보고 이력/진행률/문서·일정·로그 액션과 이벤트 위임을 보존하고 개별 배지
  CSS를 제거한다. 트리 들여쓰기와 모바일 여백은 공통 간격 토큰을 사용한다.
- Reporting 브라우저에 metadata 필드 순서, 공통 배지, 600px 단일 열과
  내부 overflow 검증을 추가한다. 응답을 기다린 후 DOM을 검사한다.

<a id="관리자-공통-상태와-응답-순서"></a>

## 31. 관리자 공통 상태와 응답 순서

- 헤더 조회 상태를 setStatus/af-status--inline으로 연결한다. loading 때만
  aria-busy를 표시하고 성공/실패 때 제거한다. 단발 조회를 실시간이라고 부르지
- 않고 ‘조회 완료’로 표시한다.
- 메뉴 전환 시 요청 버전을 증가시키고 fetch와 JSON 파싱 이후, 오류 처리에서
  현재 요청 여부를 확인한다. 계정 프로필 이동도 대기 중인 관리자 응답을 무효화한다.
- ui-screens에 개요 응답을 보류한 뒤 사용자 조회 오류를 먼저 표시하는 재현을
  추가했다. 수정 전 오류 영역이 사라져 실패했고 수정 후 새 화면의 제목·오류·
- 상태가 유지되어 통과했다. loading/success/error의 busy 해제도 검증한다.
- ui-screens/workspace-start 및 Python workspace UI 10개 통과.
  기존 관리자 권한/조회 경로와 401 리다이렉트 계약은 유지한다.

<a id="관리자-표-스타일-정리"></a>

## 32. 관리자 표 스타일 정리

- admin-table-shell의 중복 셀 여백·테두리·색상·행 hover 및 empty/error 박스
  스타일을 제거한다. 공통 af-table/af-status가 표현을 소유한다.
- 데이터 열의 최소 표 폭 680px, 줄바꿈 금지와 긴 값의 생략 처리는 제품 정책으로
  유지한다. 스크롤은 공통 af-table-scroll 영역 안에 한정한다.
- ui-screens에 실제 관리자 jobs 응답 표를 추가하여 1440/390px 페이지 overflow,
  390px 내부 가로 스크롤, 공통 셀 padding 토큰, payload/rules 제외,
- HTML 유사 문자열의 text 출력 및 빈 organizations 상태를 검증한다.
- ui-screens와 조직 표 회귀 통과. 표 정렬/페이지 구분 등 새 기능은 추가하지 않는다.

<a id="mcp-공통-토스트-제품-연결"></a>

## 33. MCP 공통 토스트 제품 연결

- 준비된 Zag toast manager를 독립 제품 번들 static/ui/toasts.js로 빌드하고
  Workspace에만 로드한다. 현재 출력 97,844 bytes. 인증 경량 번들에는 포함하지 않는다.
- 분할용 CSSOM 속성 어댑터를 product-style-props로 분리하여 toast도 같은 CSP
  대응을 사용한다. 기존 style-src 정책은 완화하지 않는다. 빌드 입력에서 실제
- 의존성을 수집해 notices/provenance를 생성하고 --check로 검사한다.
- MCP의 서버 검증·진단 클라이언트 구분과 사용자/조직/작업공간/토큰별 확인 기록은
  유지한다. 연결 확인 때 공통 success toast를 표시하고 기존 4.5초 기간을 유지한다.
- 명시적 닫기 기능을 제공하며 reset에서 manager를 destroy하여 오래된 알림을 제거한다.
- 토스트 render 재적용 전에 이전 속성 바인딩을 정리한다. 개별 MCP toast DOM/CSS와
  수동 타이머는 제거한다. 앱이 알림을 처음 필요로 할 때 manager를 만든다.
- MCP 브라우저에 공통 success 토스트·중복 방지·닫은 뒤 재알림 방지 및 모든
  navigation에 걸친 CSP 위반 수집을 연결한다. document-editor와 에셋 verify-all
- 회귀 통과. 알림 관련 소유 데이터나 API는 변경하지 않는다.

<a id="폼-다이얼로그-기반-연결"></a>

## 34. 폼 다이얼로그 기반 연결

- bindNativeDialog를 추가해 작업공간 생성과 일정 편집의 기존 dialog를 공통
  컨테이너로 연결한다. 별도의 focus trap을 중복 구현하지 않고 native 모달·Escape·
- 포커스 복귀를 사용한다. 기존 폼/컨트롤/리스너 및 기간 편집 초기 focus는 유지한다.
- af-dialog와 af-confirm은 공통 외곽 스타일을 공유한다. 작업공간의 개별
  20px 여백·6px 반경·제목/입력/footer CSS를 제거하고 공통 토큰을 소비한다.
- 일정 편집의 540px 폭은 기능별 확장으로 유지한다.
- ui-boundaries에서 실제 modal, 초기 focus, close 후 복귀, destroy 후 재개 차단,
  동일 input과 값 보존을 검증한다. planning/workspace-start 및 verify-all 통과.
- 일정의 저장/취소/reset과 임시 입력 정책은 소유자에 남긴다. 이 단계는 모든
  dialog 비동기 경계 검증이나 Web Awesome dialog로의 일괄 교체를 뜻하지 않는다.

<a id="셸-픽셀-리사이저-공통화"></a>

## 35. 셸 픽셀 리사이저 공통화

- 기존 native resize 동작을 bindResizeHandle 에셋으로 분리한다. 포인터 캡처,
  방향키, pointercancel/lostpointercapture, 드래그 상태와 destroy를 공유한다.
- Workspace는 getValue/setSidebarWidth와 body의 드래그 class만 연결한다.
  기존 viewport 폭 보정과 ARIA 값·180–520px 제한·16px 키보드 이동을 유지한다.
- pagehide는 cancel을 호출해 드래그 상태를 해제한다. Activity 구성은 변경하지 않는다.
- Workspace 스킬은 안내된 경로에서 읽을 수 없어 저장소 디자인 시스템과 실제
  코드 계약을 기준으로 작업했다. 읽지 못한 스킬 내용을 적용했다고 주장하지 않는다.
- workspace-start, DOCUMENT_HEADERS_ONLY 180–520px 및 document-editor 통과.
  ui-boundaries에서 실제 포인터 이동/해제, 16px 방향키와 드래그 중 destroy 후
- 포인터·키보드 무반응 및 드래그 class 해제를 검증했다.

<a id="문서-native-tree-키보드-어댑터"></a>

## 36. 문서 native tree 키보드 어댑터

- bindTreeKeyboard를 공통 에셋에 추가하고 제품 treeKey의 키 매핑을 제거한다.
  depth-first visible row를 소유자가 제공하고 펼침/열기/선택/메뉴/Shift 이동
- 콜백으로 문서 동작을 유지한다. native tree와 Web Awesome tree를 중복 실행하지 않는다.
- 오른쪽 방향키는 펼쳐진 폴더의 실제 자식에게만 이동하며 빈 폴더의 다음 형제로
  넘어가지 않는다. IME 조합 중 키와 defaultPrevented 이벤트는 처리하지 않는다.
- 문서 DOM·다중 선택·drag/drop·preview·탭 이동 상태는 기존 소유자에 남긴다.
  따라서 이 단계로 전체 tree 컴포넌트 전환 완료를 주장하지 않는다.
- document-editor 및 180–520px header 검사 통과. ui-boundaries에서
  자식/부모 이동, 빈 폴더, Ctrl+Enter/Space/Ctrl+A 전달, destroy 후 무반응 검증.

<a id="문서-native-tree-렌더러"></a>

## 37. 문서 native tree 렌더러

- renderNativeTree로 재귀 계층 DOM, treeitem/group ARIA, level/posinset/setsize,
  roving tabindex와 focus key 복원을 공통 에셋으로 옮긴다.
- 문서 경로 구성·폴더 우선 정렬·검색·아이콘·열기/선택/메뉴/drag는 제품의
  childrenOf/isExpanded/renderRow 어댑터로 유지한다. 살아 있는 문서 에디터 DOM과
- 트리 표시 DOM은 별개이며 에디터 렌더러를 교체하지 않는다.
- 중복 key는 fragment 구성 중 거부해 기존 tree DOM을 보존한다. 중첩 자식
  click/dblclick/contextmenu가 부모 폴더의 액션을 실행하지 않게 한다.
- document-editor 회귀 통과. ui-boundaries에서 계층 level, 자식 이벤트 분리,
  단일 Tab 진입점, 재렌더링 후 focus, 중복 key 거부/기존 DOM 보존,
- 접힌 폴더의 자식 미렌더링 및 HTML 유사 label 안전 출력을 검증한다.

<a id="문서-다중-선택-계산"></a>

## 38. 문서 다중 선택 계산

- selectKeys 공통 함수가 단일 선택·Ctrl/Meta 토글·Shift 범위 선택을 계산한다.
  문서 소유자가 현재 보이는 파일 key 순서를 제공하며 폴더/열기/드래그 정책은 유지한다.
- 검색 결과에서 anchor가 사라진 경우 기존 -1 인덱스가 범위의 시작 0으로
  보정되어 관계없는 앞쪽 파일까지 선택될 수 있었다. 이제 클릭한 파일만 새 기준으로
- 선택한다. 일반 순방향/역방향 범위와 토글 동작은 보존한다.
- ui-boundaries에서 원본 Set 불변성, 양방향 범위, 토글 해제, 보이지 않는 기준,
  없는 대상의 선택 보존을 검증한다. 제품 브라우저에 c.json 선택 → .md 검색 →
- b.md Shift 클릭 시 b만 선택되는 실제 문서 흐름을 추가한다.

<a id="연동-폴더-범위와-오래된-응답"></a>

## 39. 연동 폴더 범위와 오래된 응답

- 폴더 조회는 요청 번호·context·연결 객체·generation을 캡처하고 성공/실패
  양쪽에서 현재 범위인지 검사한다. 빠르게 폴더를 이동해도 이전 응답은 목록과
- 공통 상태를 덮어쓰지 않는다.
- 새 경로 조회를 시작하면 해당 경로/상위 버튼을 즉시 갱신하고 이전 목록을
  지운다. 더 보기 요청 중에는 중복 추가를 막고 실패 시 재시도할 수 있게 복원한다.
- 새 연결/작업공간 및 reset에서 폴더 목록·cursor·선택 폴더·제출 가능 상태를
  함께 초기화한다. API 경로·페이지 cursor 계약과 폴더 선택 의미는 변경하지 않는다.
- ui-screens에서 하위 폴더 응답을 보류하고 상위 경로를 먼저 로드한 후 늦은 응답을
  해제해도 오래된 행이 나타나지 않는 것을 검증한다. reset 후 목록 비움·선택 해제·
- 제출 disabled도 검증한다. OAuth/수집 폴링의 모든 경계를 검증했다는 뜻은 아니다.
