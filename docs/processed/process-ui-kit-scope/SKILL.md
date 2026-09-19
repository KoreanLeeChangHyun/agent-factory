---
name: ui-kit-scope
description: UI kit 제작 범위와 당시 검증 기록을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/specification/design-platform/ui-kit-scope.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# UI kit 제작 범위와 당시 검증 기록

- 초기 단계 목표(완료): 조사한 외부 소스를 확보하고 기존 ui.css 테마로 가공하여 전사 적용의 기준이 될 독립 공통 에셋 키트를 완성한다. 이 단계에서는 제품 화면 연결을 하지 않았다.

- 후속 제품 적용은 현재 진행 중이다. 최신 범위와 증거는 `../../processed/ui-asset-rollout.md`에 기록한다.

<a id="완료-게이트"></a>

## 1. 완료 게이트

- 아래 항목은 구현과 실제 검증 증거가 함께 있어야 완료다. 가져오기만 한 소스, 화면만 있는 데모, 작동하지 않는 컨트롤은 완료로 취급하지 않는다.

| 범위 | 산출물 | 상태 |
|---|---|---|
| 소스 확보 | 고정 버전, lockfile, 재현 빌드, 원문 라이선스, 출처·해시 | 검증 완료 — verify-provenance, Node22 clean build, 독립 archive 검증 |
| 아이콘 | 확장 가능한 Tabler 레지스트리, 14/16px 테마, 이름·접근성 계약 | 원본 16개·라이선스·레지스트리·버튼 구현 및 규격/해시 검증; 기본 외부 CDN 공급원을 로컬 SVG로 변경 |
| 레이아웃 | PageLayout/Header/Content, SplitPane, ListDetail, Collection, Settings | 제작·검증 완료 — layouts/Splitter, verify-layouts/states/compositions |
| 배치 | Stack, Inline, Grid, Divider, SectionHeader | 제작·검증 완료 — stack/inline/grid/divider/sectionHeader, verify-layouts |
| 기본 컨트롤 | Button/IconButton/Group, Field/Input/Textarea/Select, Checkbox/Radio/Switch | 제작·검증 완료 — primitives/Group/busy, verify-layouts/states/inputs |
| 고급 입력 | 검색형 선택, 다중 선택, 비동기 옵션, 한국어 입력 | 비동기 성공/오류/빈 결과/경합/취소, 검색 IME, 다중 선택/제거, 비활성/오류/제거 검증 통과 |
| 탐색 | Tabs, Breadcrumb, Pagination, ExplorerTree | 제작·검증 완료 — 탭/경로/페이지/공통 계층 트리, verify-navigation/layouts/admin-assets |
| 오버레이 | Menu, Popover, Tooltip, Dialog, ConfirmDialog, Drawer | 제작·검증 완료 — 메뉴/팝오버/확인/Drawer/Tooltip, 관련 동작·제거 검증 |
| 상태 | Badge, Alert, Empty, Loading, Skeleton, Toast manager | 제작·검증 완료 — badge/status/skeleton/toast, verify-states/interactions |
| 조합 | SearchField, FilterBar, ResourceRow, MetadataList, 저장/취소 영역 | 제작·검증 완료 — 검색/필터/목록상세/설정 저장, verify-compositions |
| 업로드 | 파일 선택/드롭, 제한, 큐, 진행, 취소, 실패, 재시도; 주입형 transport | 실패/재시도/성공/취소/크기제한/제거, 드롭·실제 loopback HTTP multipart 전송/서버 오류/취소 검증 통과 |
| 시간 | 상대 시각과 절대 시각 병기 | relative-time shadow 렌더링과 동일 ISO 절대 시각 병기 검증 통과 |
| 카탈로그 | 전 항목·상태별 살아있는 예제, 사용 API와 소유권 문서 | 제작·검증 완료 — 전체 분류 예제와 `.codex/skills/rule-ui/references/ui-kit-api.md`, ACCEPTANCE.md |
| 검증 | 데스크톱/좁은 폭, 키보드/포커스, 긴 한글, 생명주기, 오프라인 에셋, 라이선스/해시 | 에셋 단계 검증 완료 — npm run verify 및 verify:package; 범위·한계는 ACCEPTANCE.md |

<a id="구현-경계"></a>

## 2. 구현 경계

- Web Awesome Page/Tree/Drawer/Dialog/Tooltip 등은 개별 소스로 확보하고 공통 테마 어댑터를 제공한다.
- Zag Splitter/Toast와 Vanilla adapter는 동작 레이어로 가공한다. 같은 기능의 대체 구현을 전역으로 중복 실행하지 않는다.
- Tom Select는 검색형/다중 선택, Uppy는 업로드 엔진, GitHub relative-time은 시간 표현을 담당한다.
- 기존 Tabler/Floating UI 소스도 새 에셋의 출처 추적에 포함한다.
- 기본 레이아웃/컨트롤/조합은 ui.css 토큰을 소비한다. 외부 테마가 제품 토큰을 덮어쓰지 않는다.
- 예제 데이터는 예제임을 표시한다. 연결·성공·업로드 상태를 실제 서버 상태처럼 꾸미지 않는다.
- 전사 적용, 백엔드 변경, 배포는 후속 작업이다.
