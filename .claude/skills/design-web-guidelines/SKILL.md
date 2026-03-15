---
name: design-web-guidelines
description: Provides web accessibility and standards compliance checklists for implementation tasks. Use when building or reviewing web interfaces that must meet WCAG 2.1 Level AA, ARIA requirements, keyboard navigation, form accessibility, color contrast, screen reader compatibility, semantic HTML structure, dark mode support, or internationalization readiness.
license: "Apache-2.0"
---

# 웹 디자인 가이드라인

웹 구현을 위한 접근성 및 표준 준수 기술 체크리스트입니다. 이 스킬은 **기술적 정확성과 표준 준수**에 집중합니다 -- 시각적 디자인 품질과 미학적 판단은 `design-frontend`를 참고하세요.

## 역할 분리

| 스킬 | 범위 |
|-------|-------|
| `design-frontend` | 디자인 품질, 미학, 타이포그래피, 색상, 모션, 공간 구성 |
| `design-web-guidelines` | 접근성 준수, 표준 체크리스트, 기술적 정확성 |

사용자 대면 웹 인터페이스를 구축할 때 두 스킬을 모두 적용하세요: `design-frontend`는 시각적 외관, 이 스킬은 모든 사용자에게 어떻게 작동하는지를 담당합니다.

## WCAG 2.1 Level AA 체크리스트

### 인식 가능성 (Perceivable)

1. **텍스트 대안**: 모든 비텍스트 콘텐츠에 `alt` 텍스트가 있어야 합니다. 장식용 이미지는 `alt=""` 또는 `role="presentation"` 사용.
2. **자막/스크립트**: 사전 녹음된 오디오/비디오에는 자막이 있어야 합니다. 실시간 오디오에는 가능한 경우 자막 제공.
3. **색상 대비**: 일반 텍스트 >= 4.5:1 비율. 큰 텍스트 (18px 굵게 / 24px 일반) >= 3:1 비율. UI 컴포넌트와 그래픽 객체 >= 3:1 비율.
4. **확대**: 1280px 뷰포트에서 가로 스크롤 없이 200% 확대 시 콘텐츠 읽기 가능.
5. **텍스트 간격**: line-height 1.5배, 단락 간격 2배, letter-spacing 0.12em, word-spacing 0.16em일 때 콘텐츠 손실 없음.
6. **이미지 내 텍스트**: 사용하지 마세요. CSS 스타일링으로 실제 텍스트를 사용하세요.

### 운용 가능성 (Operable)

7. **키보드 접근성**: 모든 기능은 키보드로 사용 가능. 키보드 트랩 없음. 단축키 비활성화 또는 재매핑 가능.
8. **포커스 순서**: 시각적 레이아웃과 일치하는 논리적 탭 순서. 양수 `tabindex` 값은 사용하지 마세요.
9. **포커스 가시성**: >= 3:1 대비의 커스텀 포커스 표시기. 최소 2px 외곽선. 대체 없이 `outline: none`은 사용하지 마세요.
10. **내비게이션 건너뛰기**: 첫 번째 포커스 요소로 "메인 콘텐츠로 건너뛰기" 링크 제공.
11. **페이지 제목**: 페이지별 고유하고 설명적인 `<title>`.
12. **링크 목적**: 링크 텍스트는 컨텍스트 내에서 의미 있어야 합니다. 컨텍스트 없이 "여기를 클릭" 또는 "더 읽기"는 피하세요.
13. **타이밍**: 시간 제한이 있는 경우, 사용자가 끄거나 조정하거나 연장(최소 10배)할 수 있어야 합니다.
14. **모션/애니메이션**: `prefers-reduced-motion`을 존중하세요. 자동 재생 콘텐츠에 일시 정지/중지 컨트롤 제공.

### 이해 가능성 (Understandable)

15. **언어**: `<html>`에 `lang` 속성 설정. 다른 언어 구절에 `lang` 속성 설정.
16. **예측 가능한 내비게이션**: 페이지 전반에 걸쳐 일관된 내비게이션. 포커스나 입력 시 예상치 못한 컨텍스트 변경 없음.
17. **오류 식별**: 오류는 텍스트로 설명(색상만 사용하지 않음). 오류 메시지는 `aria-describedby` 또는 `aria-errormessage`로 필드와 연결.
18. **레이블/지침**: 폼 입력에 보이는 레이블 제공. 필수 필드는 텍스트로 표시(`*`만 사용하지 않음).
19. **오류 방지**: 법적/금융 제출의 경우, 검토, 확인, 취소 작업 허용.

### 견고성 (Robust)

20. **유효한 HTML**: 중복 ID 없음. 올바른 중첩. 완전한 시작/종료 태그.
21. **이름/역할/값**: 커스텀 컨트롤은 올바른 ARIA 역할, 상태, 속성을 노출해야 합니다.
22. **상태 메시지**: 동적 콘텐츠 업데이트는 `aria-live` 영역 사용. 오류에는 `role="alert"`, 정보 업데이트에는 `role="status"` 사용.

## ARIA 패턴

### 컴포넌트별 필수 ARIA 속성

```
Button:        role="button" (implicit for <button>)
               aria-pressed (toggle), aria-expanded (menu trigger)

Dialog/Modal:  role="dialog", aria-modal="true"
               aria-labelledby (title), aria-describedby (description)
               Focus trap: tab cycles within modal

Tabs:          role="tablist" > role="tab" + role="tabpanel"
               aria-selected, aria-controls, aria-labelledby

Menu:          role="menu" > role="menuitem"
               aria-haspopup, aria-expanded
               Arrow key navigation

Combobox:      role="combobox", aria-expanded, aria-controls
               aria-activedescendant for active option
               role="listbox" > role="option"

Alert:         role="alert" (assertive) or role="status" (polite)
               aria-live="assertive" or "polite"

Progress:      role="progressbar"
               aria-valuenow, aria-valuemin, aria-valuemax, aria-label

Breadcrumb:    <nav aria-label="Breadcrumb">
               aria-current="page" on current item

Accordion:     <button aria-expanded="true/false" aria-controls="panel-id">
               role="region" on panel, aria-labelledby pointing to button
```

### ARIA 규칙

1. ARIA보다 네이티브 HTML 요소를 선호하세요: `<div role="button">` 대신 `<button>` 사용.
2. 네이티브 시맨틱을 변경하지 마세요: `<h2 role="tab">` 사용 금지.
3. 모든 인터랙티브 ARIA 컨트롤은 키보드로 조작 가능해야 합니다.
4. 포커스 가능한 요소에 `aria-hidden="true"`를 사용하지 마세요.
5. 모든 인터랙티브 요소에는 접근 가능한 이름이 있어야 합니다 (콘텐츠, `aria-label`, 또는 `aria-labelledby`를 통해).

## 키보드 내비게이션

### 예상 키 동작

| 패턴 | 키 | 동작 |
|---------|------|----------|
| 버튼 | Enter, Space | 활성화 |
| 링크 | Enter | 이동 |
| 탭 패널 | 왼쪽/오른쪽 화살표 | 탭 전환 |
| 메뉴 항목 | 위/아래 화살표 | 항목 이동 |
| 드롭다운 | Escape | 닫기 |
| 모달 | Escape | 닫기, 트리거로 포커스 반환 |
| 라디오 그룹 | 화살표 키 | 선택 이동 |
| 체크박스 | Space | 토글 |
| 슬라이더 | 화살표 키 | 증가/감소 |

### 포커스 관리

- 모달 내부에 포커스를 가두세요 (첫 번째와 마지막 포커스 요소 사이에서 Tab 순환).
- 모달이 닫힐 때, 모달을 열었던 요소로 포커스를 반환하세요.
- SPA에서 경로가 변경될 때, 포커스를 메인 콘텐츠로 이동하거나 `aria-live`로 알리세요.
- 모달이 열려 있을 때 배경 콘텐츠에 `inert` 속성을 사용하세요.
- 복합 위젯(listbox, combobox, grid)의 경우 `aria-activedescendant`를 관리하세요.

## 폼 접근성

### 입력 패턴

```html
<!-- 올바른 레이블 연결 -->
<label for="email">Email address</label>
<input id="email" type="email" required aria-required="true"
       aria-describedby="email-hint email-error">
<p id="email-hint" class="hint">We will never share your email.</p>
<p id="email-error" class="error" role="alert" aria-live="assertive"></p>

<!-- 관련 입력 그룹화 -->
<fieldset>
  <legend>Shipping address</legend>
  <!-- address fields -->
</fieldset>

<!-- 필수 필드 표시 -->
<p class="form-note">Fields marked with <span aria-hidden="true">*</span>
<span class="sr-only">asterisk</span> are required.</p>
```

### 유효성 검사 패턴

1. **인라인 유효성 검사**: blur 시 유효성 검사 (모든 키 입력 시마다 하지 않음). 필드 옆에 오류 표시.
2. **제출 시 요약**: 폼 상단에 각 필드로 연결되는 링크와 함께 모든 오류 목록 표시. 요약으로 포커스 이동.
3. **유효하지 않은 폼 제출 방지**: `aria-live` 영역으로 오류 수를 알리세요.
4. **오류 메시지**: 구체적으로 ("이메일에 @가 포함되어야 합니다") 일반적이지 않게 ("유효하지 않은 입력").
5. **성공 확인**: `role="status"`로 알리거나 확인 페이지로 리다이렉트하세요.

### 자동 완성

일반 필드에 `autocomplete` 속성을 사용하세요:

```
name, email, tel, street-address, postal-code,
country, cc-number, cc-exp, cc-csc,
username, current-password, new-password
```

## 색상과 대비

### 대비 비율 확인

| 요소 | 최소 비율 (AA) | 향상된 기준 (AAA) |
|---------|-------------------|----------------|
| 일반 텍스트 (< 18px / < 14px 굵게) | 4.5:1 | 7:1 |
| 큰 텍스트 (>= 18px / >= 14px 굵게) | 3:1 | 4.5:1 |
| UI 컴포넌트 (테두리, 아이콘) | 3:1 | 해당 없음 |
| 비텍스트 대비 (차트, 그래프) | 3:1 | 해당 없음 |

### 색상 독립성

- 색상만으로 정보를 전달하지 마세요. 텍스트 레이블, 아이콘, 또는 패턴을 추가하세요.
- 폼 오류: 빨간 테두리 + 오류 아이콘 + 텍스트 메시지.
- 차트: 색상 외에도 패턴/도형 사용.
- 텍스트 내 링크: 밑줄 또는 주변 텍스트와 3:1 대비 + 호버/포커스 시 비색상 표시기.

## 다크 모드 구현

### CSS 전략

```css
/* 시스템 설정 감지 */
@media (prefers-color-scheme: dark) {
  :root { /* dark tokens */ }
}

/* 수동 토글 지원 */
[data-theme="dark"] { /* dark tokens */ }
[data-theme="light"] { /* light tokens */ }
```

### 다크 모드 규칙

1. **토큰 기반**: 모든 색상은 CSS 커스텀 속성으로. 컴포넌트에 색상을 하드코딩하지 마세요.
2. **대비 유지**: 다크 모드에서 모든 대비 비율을 다시 확인하세요. 어두운 배경에는 동일한 AA 비율의 밝은 텍스트가 필요합니다.
3. **상승된 표면**: 다크 모드에서 높이감을 위해 투명도 대신 더 밝은 음영을 사용하세요.
4. **이미지**: 다크 모드에서 이미지에 `filter: brightness(0.85)` 적용 고려. 로고/일러스트레이션은 가능한 경우 다크 변형을 제공하세요.
5. **그림자**: 다크 모드에서 box-shadow를 미묘한 테두리나 밝은 오버레이로 교체하세요.
6. **지속성**: `localStorage`에 설정을 저장하세요. 플래시를 방지하기 위해 첫 렌더링 전에 초기화하세요.
7. **전환**: 부드러운 전환을 위해 `transition: background-color 0.2s, color 0.2s` 사용. 초기 로드 시 전환을 제외하세요.

## 애니메이션 접근성

### 모션 설정

```css
/* 기본값: 애니메이션 포함 */
.element {
  animation: fadeIn 0.3s ease;
  transition: transform 0.2s ease;
}

/* 사용자 설정 존중 */
@media (prefers-reduced-motion: reduce) {
  .element {
    animation: none;
    transition: none;
  }
  /* 또는 미묘한 대안 제공 */
  .element {
    animation-duration: 0.01ms;
    transition-duration: 0.01ms;
  }
}
```

### 모션 규칙

1. 일시 정지 컨트롤 없이 5초 이상 애니메이션을 자동 재생하지 마세요.
2. 모션만으로 전달되는 콘텐츠는 없어야 합니다.
3. 패럴랙스 스크롤을 피하거나 모션 없는 대안을 제공하세요.
4. 깜박이는 콘텐츠: 초당 3회를 초과하지 마세요.
5. 전정 트리거: `prefers-reduced-motion` 가드 뒤에 있지 않는 한 대규모 모션, 확대/축소 애니메이션, 회전 효과는 피하세요.

## 국제화 준비

### 텍스트 방향

```css
/* RTL 지원을 위한 논리적 속성 */
margin-inline-start: 1rem;  /* not margin-left */
padding-inline-end: 1rem;   /* not padding-right */
inset-inline-start: 0;      /* not left: 0 */
border-inline-end: 1px solid;
text-align: start;           /* not text-align: left */
```

### i18n 패턴

1. **하드코딩된 문자열 없음**: 모든 사용자 대면 텍스트를 번역 파일로 추출하세요.
2. **유연한 레이아웃**: 텍스트 확장을 위해 설계하세요 (독일어는 영어보다 ~30% 더 길 수 있습니다). 텍스트에 고정 너비 컨테이너를 사용하지 마세요.
3. **날짜/숫자 형식**: `Intl.DateTimeFormat`과 `Intl.NumberFormat`을 사용하세요.
4. **복수형 처리**: 0/1/많음의 경우를 처리하세요. ICU MessageFormat 또는 동등한 것을 사용하세요.
5. **이미지 내 텍스트**: 피하세요. 불가피하다면 번역된 변형을 제공하세요.
6. **폰트 스택**: 전체 스타일에 CJK와 아랍어 폰트 폴백을 포함하세요.
7. **`lang` 속성**: `<html>`에 설정하고 인라인 외국어 콘텐츠에서 재정의하세요.

## 시맨틱 HTML 참조

### 랜드마크 영역

```html
<header>       <!-- 배너 랜드마크: 사이트 헤더 -->
<nav>          <!-- 내비게이션 랜드마크 -->
<main>         <!-- 메인 랜드마크: 주요 콘텐츠 (페이지당 하나) -->
<aside>        <!-- 보완 랜드마크: 사이드바 -->
<footer>       <!-- 콘텐츠 정보 랜드마크: 사이트 푸터 -->
<section>      <!-- aria-label이 있으면 영역 랜드마크가 됨 -->
<form>         <!-- 접근 가능한 이름이 있을 때 폼 랜드마크 -->
<search>       <!-- 검색 랜드마크 (HTML5.2+) -->
```

### 헤딩 계층

- 페이지당 하나의 `<h1>`.
- 레벨을 건너뛰지 마세요 (h2 없이 h1 -> h3 금지).
- 헤딩은 그 아래의 콘텐츠를 설명합니다.
- 시각적 크기 조정이 아닌 구조를 위해 헤딩을 사용하세요 (크기는 CSS 사용).

### 목록

- 내비게이션 메뉴: `<nav>` 안에 `<li>`가 있는 `<ul>`.
- 순서가 있는 단계: `<ol>`.
- 키-값 쌍: `<dl>`, `<dt>`, `<dd>`.

## 반응형 디자인

### 브레이크포인트 전략

```css
/* 모바일 우선 접근법 */
.container { /* 모바일 스타일 */ }

@media (min-width: 640px)  { /* sm: 태블릿 */ }
@media (min-width: 768px)  { /* md: 태블릿 가로 */ }
@media (min-width: 1024px) { /* lg: 데스크톱 */ }
@media (min-width: 1280px) { /* xl: 와이드 데스크톱 */ }
```

### 터치 타겟

- 인터랙티브 요소의 최소 44x44 CSS 픽셀 (WCAG 2.5.8).
- 인접한 터치 타겟 사이 최소 8px 간격.
- 블록 대안이 있는 경우 텍스트 내 인라인 링크는 예외.

### 반응형 규칙

1. >= 320px 뷰포트에서 가로 스크롤 없이 콘텐츠 읽기 가능.
2. 크기 조정에 상대 단위 (`rem`, `em`, `%`, `vw`) 사용. 컨테이너에 고정 픽셀 너비 사용 금지.
3. 뷰포트에 따라 콘텐츠 표시/숨기기: `display: none` (접근성 트리에서 제거) 또는 `visibility: hidden` + `position: absolute` (시각적으로 숨기되 트리에 유지) 사용.
4. 400% 화면 확대에서 테스트하세요.

## 테스트 체크리스트

접근 가능한 구현 완료 표시 전:

- [ ] axe-core 또는 Lighthouse 접근성 감사 실행. 점수 >= 90.
- [ ] 모든 인터랙티브 플로우를 키보드만으로 내비게이션.
- [ ] 주요 사용자 플로우에서 스크린 리더 테스트 (VoiceOver/NVDA).
- [ ] 라이트 및 다크 테마 모두에서 모든 텍스트와 UI 요소의 색상 대비 확인.
- [ ] `prefers-reduced-motion` 동작 확인.
- [ ] HTML 유효성 검사: 중복 ID 없음, 올바른 중첩.
- [ ] 모든 인터랙티브 요소에서 포커스 표시기 가시성 확인.
- [ ] 보조 기술로 폼 오류 처리 테스트.
- [ ] 200% 및 400% 확대 시 콘텐츠 손실 없음 확인.
- [ ] 모바일에서 터치 타겟이 최소 44x44px 충족 확인.
