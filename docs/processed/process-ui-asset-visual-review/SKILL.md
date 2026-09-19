---
name: ui-asset-visual-review
description: 공통 에셋 직접 캡처 검토 — 2026-09-09을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/ui-asset-visual-review.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# 공통 에셋 직접 캡처 검토 — 2026-09-09

- 아래 `artifacts/ui-review` 링크 16건은 이번 병합 전부터 대상 파일이 없었습니다. 과거 검수 기록의 출처 문자열로 보존하며, 현재 열람 가능하거나 이번에 검증된 증거를 뜻하지 않습니다.

- 판정: 캡처 검토에서 8개 시각/사용성 문제를 확인하여 수정했다. 탐색 트리는 VS Code 탐색기의 밀도와 키보드 조작을 기준으로 프로젝트 소유 native 에셋을 추가했다. 전체 제품 전환이나 모든 브라우저 접근성 검증이 완료됐다는 판정은 아니다.

- [전체 수정 전후 캡처 비교](../../artifacts/ui-review/index.html) · [탐색 트리](../../artifacts/ui-review/after/section-03-1440.png) · [180px 탐색기](../../artifacts/ui-review/after/tree-180.png)

- 후속 사용자 참고 이미지에 맞춰 계층 안내선·채워진 유형별 폴더 아이콘·회색 선택 행과 파란 포커스 테두리를 적용했다. [참고 이미지 기준 캡처](../../artifacts/ui-review/after/tree-reference.png). 슈퍼 관리자 영역의 가짜 탭 헤더는 제거하고 제목과 새 탭 열기 액션을 한 줄에 배치했다. 카탈로그의 72vh 고정 높이를 제거하여 남은 높이를 채운다. [화면 캡처](../../artifacts/ui-review/admin-layout-1440-1000.png). 1440×1000, 1440×700, 390×900에서 iframe 하단과 작업 영역 사이가 25px 이하인지 검증했다. 후속 밀도 검토에서는 카탈로그 바깥 여백을 12px로 줄이고, 임베드된 중복 소개를 숨겼다. 상단 검토 영역은 높이가 독립적인 두 개의 명시적 컬럼으로 구성하고 모바일에서는 한 줄로 내려간다. 목록·상세 패널의 높이 계산과 제어 버튼 겹침도 수정했다.

- Material Icon Theme 후속 적용: 공식 npm 5.38.1의 SVG 1,251개와 MIT 라이선스, 공식 파일/폴더 매핑을 내려받았다. 임시 자체 폴더 glyph는 원본으로 교체했다. 현재 카탈로그는 26개 SVG를 로컬 레지스트리로 묶어 사용하며, tests/benchmarks/contracts/integration, 기본 폴더와 열림 상태의 공식 아이콘 이름을 브라우저에서 검증했다. 원본 출처 및 SHA-512/SHA-256은 `assets/ui-kit/vendor/material-icon-theme/provenance.json`에 있다.

<a id="확인-및-수정"></a>

## 1. 확인 및 수정

- [중간] 카탈로그 밀도와 소스 구조 — 관리자 화면에 제목이 중복되고, 1100px 최대 폭과 24px 섹션 여백 및 행 단위 2열 배치 때문에 검토 화면에 큰 빈 공간이 생겼다. Fix: 임베드 상태에서는 카탈로그 소개를 숨기고, 최대 폭을 1280px로 늘리며 12px 여백과 명시적인 두 컬럼 컨테이너를 적용했다. 760px 이하에서는 한 컬럼으로 바뀐다. 에셋 루트에 섞여 있던 컴포넌트·카탈로그· 스타일·문서·빌드·테스트는 `src/components/`, `catalog/`, `styles/`, `docs/`, `scripts/`, `tests/`로 분리했다. 패키징 전에 이전 카탈로그 대상 디렉터리를 비워 낡은 평면 파일이 wheel에 남지 않게 했다. Verification: [관리자 1440px](../../artifacts/ui-review/admin-layout-1440-1000.png), [관리자 390px](../../artifacts/ui-review/admin-layout-390-900.png), 2열/1열·중복 소개 숨김· 가로 overflow·패널 겹침 assertion과 wheel 파일 목록 검사 통과.

- [중간] 탐색 트리 기준 — 기존 예제는 파일/폴더 아이콘 없이 일반 트리로 표시됐다. Evidence: [수정 전](../../artifacts/ui-review/before/section-03-1440.png). Fix: `explorer-tree.js`가 기존 native renderer/keyboard/selection 계산을 조합한다. 22px 행, 12px 들여쓰기, 파일/폴더 아이콘, 긴 이름 말줄임, 색상 외 선택선과 포커스 테두리를 적용했다. 제품 문서 편집기 전체를 이 생성 함수로 교체하지는 않았다. Verification: Shift 범위 선택, 비활성 항목, 방향키 접기/펼치기/자식 이동, Enter, 단일 Tab 진입점, 180/268/520px 폭. 파일 열기는 호출자 콜백이며 실제 데이터/API를 변경하지 않는다.

- [중간] 다이얼로그/Drawer 테마 — 존재하지 않는 `::part(panel)`에 스타일을 적용했다. Evidence: upstream 실제 part는 dialog이며 [기존 캡처](../../artifacts/ui-review/before/confirm.png)에 큰 기본 모서리가 남았다. Fix: 실제 `::part(dialog)`에 공통 테두리/모서리를 연결했다. Verification: [다이얼로그](../../artifacts/ui-review/after/confirm.png), [Drawer](../../artifacts/ui-review/after/drawer.png), 열기/닫기/Escape/포커스 복귀 회귀 검증. 최종 오버레이 캡처는 애니메이션 종료를 기다렸다.

- [중간] 스위치 시각 표현 — role=switch만 지정하여 일반 체크박스와 똑같이 보였다. Evidence: [기본 컨트롤 수정 전](../../artifacts/ui-review/before/section-08-1440.png). Fix: native checkbox와 role을 유지하며 트랙/손잡이 및 checked 표현을 추가했다. Verification: [수정 후](../../artifacts/ui-review/after/section-08-390.png), 기존 native switch 동작 검사 통과.

- [낮음] 아이콘 버튼 비율 — 카탈로그 grid의 행 높이로 늘어나 세로로 긴 버튼이 됐다. Evidence: [수정 전 아이콘 영역](../../artifacts/ui-review/before/section-10-1440.png). Fix: 공통 iconButton에 전용 클래스를 붙이고 공통 control 높이와 align-self를 지정했다. Verification: [수정 후](../../artifacts/ui-review/after/section-10-1440.png), 폭=높이 assertion.

- [중간] 검색 실패/빈 결과 구분 — 비동기 요청이 실패해도 드롭다운에는 영어 ‘No results found’가 표시됐다. Evidence: `assets/ui-kit/src/components/components.js`는 실패 시 빈 callback만 호출하고 기본 빈 결과 렌더러를 사용했다. Fix: 현재 요청의 실패 여부를 구분하여 ‘검색하지 못했습니다.’와 ‘검색 결과가 없습니다.’를 다르게 표시한다. Verification: 드롭다운 오류 문구 assertion, [오류 캡처](../../artifacts/ui-review/after/remote-error.png), 비동기 성공/빈 결과/오류/경합/취소 회귀 검증.

<a id="검증과-한계"></a>

## 2. 검증과 한계

- 캡처: Chromium 1440/390px의 17개 영역과 다이얼로그/Drawer/메뉴,
  설정 오류·검색 오류·업로드 실패/완료, 탐색기 180/268/520px.
- `AF_CAPTURE_DIR=artifacts/ui-review/after NODE_PATH=assets/ui-kit/node_modules node tests/browser/admin-assets.cjs` 통과.
  실제 앱 HTTP 라우트와 CSP를 사용하되 인증은 테스트 프로세스의 합성 principal이다.
- 운영 사용자의 로그인 세션을 사용한 캡처는 아니다.
- `node assets/ui-kit/scripts/verify-all.mjs` 10종 통과. 별도 ui-components/ui-boundaries 회귀와 제품 번들 동기화 검증 통과.
- 데모의 의도적 업로드 실패 로그 1건은 실패 UI와 함께 검증한다. 예상 밖 콘솔 오류/CSP 차단은 실패 처리한다.
- 운영에서는 읽기 전용 카탈로그 mount와 static mount가 이 파일들을 사용한다.
  이번 검토는 제품 전체 화면, Firefox/Safari, 실제 화면 낭독기, DB 영속성의 증거를 대신하지 않는다.
- 앞선 Caddy 수정은 실행 설정에 반영됐지만 `/etc/caddy/Caddyfile` 원본 저장에는 sudo 권한이 필요하다.
  재시작 시 복구되지 않도록 `deploy/caddy-factory-headers.patch` 영구 적용이 남아 있다.
