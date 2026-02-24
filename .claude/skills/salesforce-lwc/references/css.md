# LWC CSS 스타일링 가이드

> 출처: [Salesforce LWC Developer Guide](https://developer.salesforce.com/docs/platform/lwc/guide/create-components-css.html)

## 기본 원칙

### Shadow DOM 스코핑
- 스타일은 자동으로 컴포넌트에 스코프됨
- 외부 스타일이 침범하지 않음
- 내부 스타일이 외부로 누출되지 않음

### 파일 규칙
- CSS 파일명은 컴포넌트명과 동일해야 함
- 컴포넌트당 하나의 CSS 파일만 가능
- `myComponent.css` → `myComponent.js`와 자동 연결

## :host 선택자

컴포넌트 자체(루트 요소)를 스타일링.

```css
/* 기본 호스트 스타일 */
:host {
    display: block;
    padding: 1rem;
    border: 1px solid #d8dde6;
    border-radius: 4px;
}

/* 조건부 호스트 스타일 */
:host(.compact) {
    padding: 0.5rem;
}

:host(.highlighted) {
    border-color: #0070d2;
    box-shadow: 0 0 0 3px rgba(0, 112, 210, 0.15);
}

:host([disabled]) {
    opacity: 0.5;
    pointer-events: none;
}
```

## CSS 변수 (Custom Properties)

### 정의 및 사용

```css
:host {
    /* 변수 정의 */
    --primary-color: #0070d2;
    --secondary-color: #706e6b;
    --danger-color: #c23934;
    --success-color: #2e844a;

    --font-size-sm: 12px;
    --font-size-md: 14px;
    --font-size-lg: 16px;

    --spacing-xs: 0.25rem;
    --spacing-sm: 0.5rem;
    --spacing-md: 1rem;
    --spacing-lg: 1.5rem;
    --spacing-xl: 2rem;

    --border-radius: 4px;
    --transition-duration: 0.2s;
}

/* 변수 사용 */
.button {
    background-color: var(--primary-color);
    font-size: var(--font-size-md);
    padding: var(--spacing-sm) var(--spacing-md);
    border-radius: var(--border-radius);
    transition: background-color var(--transition-duration) ease;
}

/* 기본값 지정 */
.text {
    color: var(--text-color, #333);
}
```

### 부모에서 변수 오버라이드

```css
/* 부모 컴포넌트 CSS */
c-child-component {
    --primary-color: #ff5722;
    --spacing-md: 2rem;
}
```

## 커스텀 UI 컴포넌트 스타일

### 버튼

```css
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.75rem 1.5rem;
    font-size: 14px;
    font-weight: 500;
    line-height: 1;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-primary {
    background-color: #0070d2;
    color: white;
}

.btn-primary:hover {
    background-color: #005fb2;
}

.btn-primary:active {
    background-color: #004e96;
}

.btn-secondary {
    background-color: white;
    color: #0070d2;
    border: 1px solid #0070d2;
}

.btn-secondary:hover {
    background-color: #f4f6f9;
}

.btn-danger {
    background-color: #c23934;
    color: white;
}

.btn:disabled {
    background-color: #c9c9c9;
    cursor: not-allowed;
}

.btn-sm {
    padding: 0.5rem 1rem;
    font-size: 12px;
}

.btn-lg {
    padding: 1rem 2rem;
    font-size: 16px;
}
```

### 입력 필드

```css
.input {
    width: 100%;
    padding: 0.75rem 1rem;
    font-size: 14px;
    line-height: 1.5;
    color: #333;
    background-color: white;
    border: 1px solid #d8dde6;
    border-radius: 4px;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.input:focus {
    outline: none;
    border-color: #0070d2;
    box-shadow: 0 0 0 3px rgba(0, 112, 210, 0.15);
}

.input:disabled {
    background-color: #f4f6f9;
    cursor: not-allowed;
}

.input-error {
    border-color: #c23934;
}

.input-error:focus {
    box-shadow: 0 0 0 3px rgba(194, 57, 52, 0.15);
}

/* 입력 그룹 */
.input-group {
    margin-bottom: 1rem;
}

.input-label {
    display: block;
    margin-bottom: 0.5rem;
    font-size: 14px;
    font-weight: 500;
    color: #333;
}

.input-help {
    margin-top: 0.25rem;
    font-size: 12px;
    color: #706e6b;
}

.input-error-message {
    margin-top: 0.25rem;
    font-size: 12px;
    color: #c23934;
}
```

### 카드

```css
.card {
    background-color: white;
    border: 1px solid #d8dde6;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    overflow: hidden;
}

.card-header {
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #d8dde6;
    background-color: #f4f6f9;
}

.card-title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #333;
}

.card-body {
    padding: 1.5rem;
}

.card-footer {
    padding: 1rem 1.5rem;
    border-top: 1px solid #d8dde6;
    background-color: #f4f6f9;
}
```

### 테이블

```css
.table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}

.table th,
.table td {
    padding: 0.75rem 1rem;
    text-align: left;
    border-bottom: 1px solid #d8dde6;
}

.table th {
    font-weight: 600;
    color: #706e6b;
    background-color: #f4f6f9;
}

.table tr:hover {
    background-color: #f4f6f9;
}

.table-striped tr:nth-child(even) {
    background-color: #fafafa;
}
```

### 모달

```css
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
}

.modal {
    background-color: white;
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    max-width: 600px;
    width: 90%;
    max-height: 90vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

.modal-header {
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #d8dde6;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.modal-title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
}

.modal-close {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #706e6b;
    padding: 0;
    line-height: 1;
}

.modal-body {
    padding: 1.5rem;
    overflow-y: auto;
    flex: 1;
}

.modal-footer {
    padding: 1rem 1.5rem;
    border-top: 1px solid #d8dde6;
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
}
```

## 유틸리티 클래스

```css
/* 텍스트 */
.text-center { text-align: center; }
.text-right { text-align: right; }
.text-muted { color: #706e6b; }
.text-danger { color: #c23934; }
.text-success { color: #2e844a; }

/* 여백 */
.m-0 { margin: 0; }
.mt-1 { margin-top: 0.5rem; }
.mt-2 { margin-top: 1rem; }
.mb-1 { margin-bottom: 0.5rem; }
.mb-2 { margin-bottom: 1rem; }

.p-0 { padding: 0; }
.p-1 { padding: 0.5rem; }
.p-2 { padding: 1rem; }

/* Flexbox */
.d-flex { display: flex; }
.flex-column { flex-direction: column; }
.align-center { align-items: center; }
.justify-center { justify-content: center; }
.justify-between { justify-content: space-between; }
.gap-1 { gap: 0.5rem; }
.gap-2 { gap: 1rem; }

/* 표시 */
.hidden { display: none; }
.invisible { visibility: hidden; }
```

## 제한사항

1. **지원하지 않는 선택자**
   - `:host-context()`
   - `::part`
   - ID 선택자 (`#id`) - 런타임에 변환됨

2. **대안**
   ```css
   /* ❌ ID 선택자 사용 금지 */
   #myElement { ... }

   /* ✅ class 또는 data 속성 사용 */
   .my-element { ... }
   [data-id="myElement"] { ... }
   ```

3. **외부 스타일시트**
   - 컴포넌트 폴더 내 CSS만 사용 가능
   - 전역 CSS 직접 import 불가
   - Static Resource로 로드 필요
