---
name: ui-kit-acceptance
description: 에셋 제작 단계 검증 기록을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/ui-kit-acceptance.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
---


# 에셋 제작 단계 검증 기록

- 이 문서는 초기 독립 공통 에셋 키트의 검증 기록이며 전사 화면 통합은 제외한다. 확인 환경: Node 22.23.2, Playwright 1.55.0 Chromium, 1280/768/390px. 운영 배포·실제 제품 API·화면 낭독기 인증·Firefox/Safari 호환성 인증은 이 기록의 주장에 포함하지 않는다. 이후 시작된 제품 연결 작업은 `ui-asset-rollout.md`의 별도 증거를 따른다.

<a id="요구사항별-증거"></a>

## 1. 요구사항별 증거

| 요구 | 구현 | 직접 검증 |
|---|---|---|
| 외부 소스 확보·재사용 고지 | package/lock, src/vendors, generated/licenses, provenance | clean install/build, verify-provenance |
| 우리 테마 | ui.css 소비, theme.css, 외부 native/reset 미수입 | verify-layouts 30px 컨트롤·반응형, 렌더링 확인 |
| 확장 가능한 SVG | Tabler 16개, icons.js, 원본/생성 해시 | verify-inputs, verify-provenance |
| 레이아웃·배치 | layouts.js, Zag Splitter | verify-layouts/states/compositions |
| 기본 컨트롤·상태 | primitives.js, badge/status/skeleton, busy, Group | verify-layouts/states/inputs |
| 고급 입력 | Tom Select 어댑터 | verify-inputs/states: 선택·다중·오류·빈 결과·경합·취소·제거·IME |
| 탐색·트리 | navigation.js, explorerTree | verify-navigation/layouts/admin-assets |
| 메뉴·팝오버·모달·툴팁 | popovers/overlays/web-components | verify-navigation/interactions/web-components/layouts |
| 알림 | Zag Toast 어댑터 | verify-interactions: 중복·닫기·타이머·제거 |
| 반복 화면 조합 | compositions.js | verify-compositions: 검색·필터·상세·저장/실패/취소 |
| 업로드 | Uppy 큐, 주입형 전송, xhrTransport | verify-uploads/http: 제한·드롭·multipart·실패·재시도·취소 |
| 상대/절대 시각 | GitHub relative-time + time | verify-states |
| 사용 문서·미리보기 | `.codex/skills/rule-ui/references/ui-kit-api.md`, index.html/catalog.js | 전체 검증 카탈로그 로딩·각 실제 동작 |
| 독립 전달 묶음 | package.mjs, release archive/manifest | verify-package: 추출 후 해시·독립 서버·CSS/JS/SVG·모바일·확인창 |
| 초기 에셋 단계의 운영 미적용 | 당시 변경은 assets/ui-kit와 기존 조사 키트 안에 한정 | 초기 단계의 쓰기 대상 확인; 후속 제품 연결은 별도 진행 |

<a id="감사에서-수정한-사항"></a>

## 2. 감사에서 수정한 사항

- [중요] 외부 런타임 요청 — Web Awesome의 fallback 아이콘이 외부 CDN에 요청됨. 수정: 기본 아이콘 공급원을 로컬 Tabler로 등록하고 menu-2 SVG 추가. 검증: verify-web-components의 HTTP(S) 외부 요청 배열이 비어 있음.

- [보통] 입력 기본값 — value가 생략된 Select에 빈 문자열을 강제로 넣어 초기 선택이 사라짐. 수정: 명시한 값만 대입. 검증: 카탈로그 렌더링과 조합 테스트.

- [보통] 요청 경합 — 비동기 콜백이 공유 request의 최신 신호를 읽을 가능성. 수정: 요청별 signal 캡처. 검증: verify-states의 오래된 결과 폐기·취소 신호 확인.

- [보통] 상태 구별 — busy와 disabled 계약, 접힌 패널의 상호작용 구분 필요. 수정: setBusy 및 collapse/expand API, 접힌 패널 inert/내용 숨김. 검증: verify-layouts와 카탈로그 예제.

<a id="후속-전사-적용-시"></a>

## 3. 후속 전사 적용 시

- 실제 화면의 권한·인증·저장 계약, 화면 교체 생명주기, 제품 브라우저 지원 범위와 보조기술 테스트를 연결한다. 카탈로그의 예제 데이터·시뮬레이션 전송·저장 콜백을 제품 동작으로 사용하지 않는다. 외부 저작권은 원 저작자에게 남는다.
