# LWC 라이프사이클 훅

> 출처: [Salesforce LWC Developer Guide](https://developer.salesforce.com/docs/platform/lwc/guide/create-lifecycle-hooks-dom.html)

## 라이프사이클 순서

```
constructor()
    ↓
connectedCallback()
    ↓
render() (자동 호출)
    ↓
renderedCallback()
    ↓
[컴포넌트 사용 중...]
    ↓
disconnectedCallback()
```

## constructor()

컴포넌트 인스턴스 생성 시 호출.

```javascript
export default class MyComponent extends LightningElement {
    items = [];

    constructor() {
        super();  // 반드시 첫 줄에서 호출

        // ✅ 가능한 작업
        this.items = [];
        console.log('Component created');

        // ❌ 불가능한 작업
        // - this.template 접근 (아직 없음)
        // - @api property 접근 (아직 할당 안 됨)
        // - 자식 요소 접근 (아직 없음)
    }
}
```

### 주의사항
- `super()` 반드시 첫 줄에서 호출
- DOM 접근 불가
- `@api` 속성 접근 불가 (아직 할당 안 됨)

## connectedCallback()

컴포넌트가 DOM에 삽입될 때 호출.

```javascript
export default class MyComponent extends LightningElement {
    @api recordId;
    isInitialized = false;

    connectedCallback() {
        // ✅ @api 속성 사용 가능
        console.log('Record ID:', this.recordId);

        // ✅ 초기 데이터 로드
        this.loadData();

        // ✅ 이벤트 리스너 등록
        window.addEventListener('resize', this.handleResize);

        // ✅ 초기화 플래그
        this.isInitialized = true;
    }

    handleResize = () => {
        // resize 처리
    }
}
```

### 주요 용도
- 초기 데이터 로드
- 이벤트 리스너 등록
- 타이머 설정
- 외부 라이브러리 초기화

### 주의사항
- **여러 번 호출될 수 있음** (DOM에서 제거 후 재삽입 시)
- 한 번만 실행해야 하는 코드는 플래그로 제어

```javascript
isFirstRender = true;

connectedCallback() {
    if (this.isFirstRender) {
        this.isFirstRender = false;
        this.oneTimeSetup();
    }
}
```

## renderedCallback()

컴포넌트 렌더링 완료 후 호출.

```javascript
export default class MyComponent extends LightningElement {
    isRendered = false;

    renderedCallback() {
        // ✅ DOM 요소 접근 가능
        const element = this.template.querySelector('.my-element');

        // ✅ 외부 라이브러리 초기화 (차트 등)
        if (!this.isRendered) {
            this.isRendered = true;
            this.initializeChart();
        }

        // ❌ 무한 루프 주의!
        // this.someReactiveProperty = 'new value';
    }

    initializeChart() {
        const canvas = this.template.querySelector('canvas');
        // 차트 초기화...
    }
}
```

### 주요 용도
- DOM 조작
- 외부 라이브러리 초기화 (Chart.js 등)
- 스크롤 위치 조정
- 포커스 설정

### 주의사항
- **매 렌더링마다 호출** → 플래그로 제어
- 반응형 속성 변경 시 **무한 루프** 주의!

```javascript
// ❌ 무한 루프!
renderedCallback() {
    this.count = this.count + 1;  // 렌더링 → 변경 → 렌더링...
}

// ✅ 조건부 실행
renderedCallback() {
    if (!this.isInitialized) {
        this.isInitialized = true;
        this.count = 10;
    }
}
```

## disconnectedCallback()

컴포넌트가 DOM에서 제거될 때 호출.

```javascript
export default class MyComponent extends LightningElement {
    intervalId;

    connectedCallback() {
        // 타이머 설정
        this.intervalId = setInterval(() => {
            this.refreshData();
        }, 5000);

        // 이벤트 리스너 등록
        window.addEventListener('resize', this.handleResize);
    }

    disconnectedCallback() {
        // ✅ 타이머 정리
        if (this.intervalId) {
            clearInterval(this.intervalId);
        }

        // ✅ 이벤트 리스너 제거
        window.removeEventListener('resize', this.handleResize);

        // ✅ 외부 리소스 해제
        this.cleanup();
    }

    handleResize = () => {
        // ...
    }
}
```

### 주요 용도
- 이벤트 리스너 제거
- 타이머/인터벌 정리
- 캐시 정리
- 외부 연결 해제

## errorCallback(error, stack)

자식 컴포넌트에서 발생한 에러 처리.

```javascript
export default class ParentComponent extends LightningElement {
    error;
    stack;

    errorCallback(error, stack) {
        this.error = error;
        this.stack = stack;

        // 에러 로깅
        console.error('Error:', error.message);
        console.error('Stack:', stack);

        // 에러 리포팅 서비스로 전송
        this.reportError(error, stack);
    }

    reportError(error, stack) {
        // 에러 리포팅 로직
    }
}
```

```html
<template>
    <template lwc:if={error}>
        <div class="error-boundary">
            <p>오류가 발생했습니다: {error.message}</p>
            <button onclick={handleRetry}>다시 시도</button>
        </div>
    </template>
    <template lwc:else>
        <c-child-component></c-child-component>
    </template>
</template>
```

### Error Boundary 패턴

```javascript
export default class ErrorBoundary extends LightningElement {
    hasError = false;
    errorMessage = '';

    errorCallback(error, stack) {
        this.hasError = true;
        this.errorMessage = error.message;
    }

    handleReset() {
        this.hasError = false;
        this.errorMessage = '';
    }
}
```

## 라이프사이클 요약

| 훅 | 호출 시점 | DOM 접근 | 용도 |
|----|----------|---------|------|
| `constructor` | 인스턴스 생성 | ❌ | 초기 상태 설정 |
| `connectedCallback` | DOM 삽입 | ❌ (자식) | 데이터 로드, 이벤트 등록 |
| `renderedCallback` | 렌더링 완료 | ✅ | DOM 조작, 라이브러리 초기화 |
| `disconnectedCallback` | DOM 제거 | ❌ | 정리 작업 |
| `errorCallback` | 자식 에러 | - | 에러 처리 |

## 부모-자식 호출 순서

```
Parent constructor()
    ↓
Parent connectedCallback()
    ↓
Child constructor()
    ↓
Child connectedCallback()
    ↓
Child renderedCallback()
    ↓
Parent renderedCallback()
```

자식의 렌더링이 완료된 후 부모의 `renderedCallback()`이 호출됨.
