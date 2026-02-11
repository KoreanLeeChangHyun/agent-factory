---
name: lwc-custom
description: Salesforce Lightning Web Components(LWC) 커스텀 컴포넌트 개발 스킬. 표준 lightning-* 컴포넌트를 사용하지 않고 순수 HTML, CSS, JavaScript로 LWC를 개발합니다. 사용 시점: LWC 컴포넌트 생성, Salesforce UI 개발, Lightning 앱 개발 요청 시. 키워드: LWC, Lightning Web Component, Salesforce, 세일즈포스.
disable-model-invocation: true
---

# LWC Custom Component Development

순수 HTML, CSS, JavaScript를 사용한 Salesforce Lightning Web Components 개발 가이드입니다.

## 핵심 원칙

### 표준 컴포넌트 사용 금지
```html
<!-- ❌ 사용 금지 - 표준 Lightning 컴포넌트 -->
<lightning-input label="Name" value={name}></lightning-input>
<lightning-button label="Submit" onclick={handleClick}></lightning-button>
<lightning-card title="My Card"></lightning-card>
<lightning-datatable></lightning-datatable>

<!-- ✅ 권장 - 순수 HTML -->
<input type="text" class="custom-input" value={name} onchange={handleChange}>
<button class="custom-btn" onclick={handleClick}>Submit</button>
<div class="custom-card">
    <h2 class="card-title">My Card</h2>
</div>
```

### 사용 금지 이유
1. **성능**: 표준 컴포넌트는 무겁고 렌더링이 느림
2. **제약사항**: 스타일링과 커스터마이징에 제한이 많음
3. **유연성**: 순수 HTML/CSS가 더 자유로운 UI 구현 가능

## LWC 컴포넌트 구조

### 필수 파일
```
myComponent/
├── myComponent.html          # 템플릿 (필수)
├── myComponent.js            # 컨트롤러 (필수)
├── myComponent.css           # 스타일 (선택)
└── myComponent.js-meta.xml   # 메타데이터 (필수)
```

### 네이밍 규칙
| 위치 | 규칙 | 예시 |
|------|------|------|
| 폴더/파일명 | camelCase | `myComponent` |
| JS 클래스명 | PascalCase | `MyComponent` |
| HTML 참조 | kebab-case | `<c-my-component>` |

## JavaScript 기본 구조

```javascript
import { LightningElement, api, track, wire } from 'lwc';

export default class MyComponent extends LightningElement {
    // Public property (부모에서 전달)
    @api recordId;
    @api title = 'Default Title';

    // Reactive property (객체/배열 내부 변경 감지)
    @track items = [];

    // Private reactive field (기본 반응형)
    name = '';
    isLoading = false;

    // Getter (계산된 속성)
    get hasItems() {
        return this.items.length > 0;
    }

    get itemCount() {
        return this.items.length;
    }

    // Lifecycle Hooks
    constructor() {
        super();
        // 초기화 (DOM 접근 불가)
    }

    connectedCallback() {
        // DOM에 삽입됨 (초기 데이터 로드)
    }

    renderedCallback() {
        // 렌더링 완료 (DOM 조작 가능)
    }

    disconnectedCallback() {
        // DOM에서 제거됨 (정리 작업)
    }

    // Event Handlers
    handleChange(event) {
        this.name = event.target.value;
    }

    handleClick() {
        // Custom Event 발생
        this.dispatchEvent(new CustomEvent('save', {
            detail: { name: this.name }
        }));
    }
}
```

## HTML 템플릿 문법

> ⚠️ **중요**: LWC 템플릿에서는 **단순 프로퍼티 참조만** 허용됩니다.
> `{!value}`, `{a ? b : c}`, `{a > b}` 같은 JavaScript 표현식은 **LWC1060 에러**를 발생시킵니다.
> 복잡한 로직은 반드시 **getter**로 처리하세요. 상세 내용은 [directives.md](references/directives.md) 참조.

### 데이터 바인딩
```html
<template>
    <!-- ✅ 텍스트 바인딩 (단순 프로퍼티) -->
    <p>{name}</p>

    <!-- ✅ 속성 바인딩 (단순 프로퍼티) -->
    <input type="text" value={name} class={inputClass}>
    <a href={url}>Link</a>

    <!-- ✅ Boolean 속성 -->
    <button disabled={isDisabled}>Submit</button>

    <!-- ❌ 금지: JavaScript 표현식 -->
    <!-- <p>{!hasData}</p>               UnaryExpression -->
    <!-- <p>{a > b}</p>                  BinaryExpression -->
    <!-- <p>{isActive ? 'Yes' : 'No'}</p> ConditionalExpression -->
</template>
```

### 조건부 렌더링 (lwc:if / lwc:elseif / lwc:else)
```html
<template>
    <!-- 권장: lwc:if 사용 -->
    <template lwc:if={isLoading}>
        <div class="spinner">Loading...</div>
    </template>
    <template lwc:elseif={hasError}>
        <div class="error">{errorMessage}</div>
    </template>
    <template lwc:else>
        <div class="content">{data}</div>
    </template>

    <!-- ❌ 비권장: if:true/if:false (deprecated) -->
</template>
```

### 리스트 렌더링 (for:each)
```html
<template>
    <!-- for:each 사용 -->
    <ul class="item-list">
        <template for:each={items} for:item="item" for:index="index">
            <li key={item.id} class="item">
                <span class="index">{index}</span>
                <span class="name">{item.name}</span>
            </li>
        </template>
    </ul>
</template>
```

### 리스트 렌더링 (iterator - 첫/마지막 항목 처리)
```html
<template>
    <ul class="item-list">
        <template iterator:it={items}>
            <li key={it.value.id} class="item">
                <template lwc:if={it.first}>
                    <span class="badge">First</span>
                </template>
                <span>{it.value.name}</span>
                <template lwc:if={it.last}>
                    <span class="badge">Last</span>
                </template>
            </li>
        </template>
    </ul>
</template>
```

### 이벤트 핸들링
```html
<template>
    <!-- 기본 이벤트 -->
    <input type="text" onchange={handleChange}>
    <button onclick={handleClick}>Click</button>

    <!-- 키보드 이벤트 -->
    <input onkeyup={handleKeyUp} onkeydown={handleKeyDown}>

    <!-- 폼 이벤트 -->
    <form onsubmit={handleSubmit}>
        <input type="text" name="email">
        <button type="submit">Submit</button>
    </form>
</template>
```

## CSS 스타일링

### 기본 스타일
```css
/* 호스트 요소 스타일 */
:host {
    display: block;
    padding: 1rem;
}

/* 조건부 호스트 스타일 */
:host(.compact) {
    padding: 0.5rem;
}

/* 컴포넌트 내부 스타일 */
.container {
    max-width: 1200px;
    margin: 0 auto;
}

.custom-input {
    width: 100%;
    padding: 0.75rem 1rem;
    border: 1px solid #d8dde6;
    border-radius: 4px;
    font-size: 14px;
    transition: border-color 0.2s ease;
}

.custom-input:focus {
    outline: none;
    border-color: #0070d2;
    box-shadow: 0 0 0 3px rgba(0, 112, 210, 0.15);
}

.custom-btn {
    padding: 0.75rem 1.5rem;
    background-color: #0070d2;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    transition: background-color 0.2s ease;
}

.custom-btn:hover {
    background-color: #005fb2;
}

.custom-btn:disabled {
    background-color: #c9c9c9;
    cursor: not-allowed;
}
```

### CSS 변수 활용
```css
:host {
    --primary-color: #0070d2;
    --secondary-color: #706e6b;
    --border-color: #d8dde6;
    --border-radius: 4px;
    --spacing-sm: 0.5rem;
    --spacing-md: 1rem;
    --spacing-lg: 1.5rem;
}

.custom-btn {
    background-color: var(--primary-color);
    border-radius: var(--border-radius);
    padding: var(--spacing-sm) var(--spacing-md);
}
```

## 메타데이터 설정

```xml
<?xml version="1.0" encoding="UTF-8"?>
<LightningComponentBundle xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>61.0</apiVersion>
    <isExposed>true</isExposed>
    <targets>
        <target>lightning__RecordPage</target>
        <target>lightning__AppPage</target>
        <target>lightning__HomePage</target>
        <target>lightning__Tab</target>
        <target>lightningCommunity__Page</target>
        <target>lightningCommunity__Default</target>
    </targets>
    <targetConfigs>
        <targetConfig targets="lightning__RecordPage,lightning__AppPage,lightning__HomePage">
            <property name="title" type="String" default="My Component"/>
        </targetConfig>
    </targetConfigs>
</LightningComponentBundle>
```

### ⚠️ targetConfig 제한사항

**`lightning__Tab` 타겟은 `<property>` 태그를 지원하지 않습니다!**

```xml
<!-- ❌ 에러: The 'property' tag isn't supported for lightning__Tab -->
<targetConfigs>
    <targetConfig targets="lightning__Tab">
        <property name="title" type="String"/>
    </targetConfig>
</targetConfigs>

<!-- ✅ 해결: lightning__Tab을 targetConfig에서 제외 -->
<targetConfigs>
    <targetConfig targets="lightning__RecordPage,lightning__AppPage,lightning__HomePage">
        <property name="title" type="String"/>
    </targetConfig>
</targetConfigs>
```

### property 지원 타겟

| 타겟 | property 지원 |
|------|--------------|
| `lightning__RecordPage` | ✅ |
| `lightning__AppPage` | ✅ |
| `lightning__HomePage` | ✅ |
| `lightning__Tab` | ❌ |
| `lightningCommunity__Page` | ✅ |
| `lightningCommunity__Default` | ✅ |

## Apex 연동

### Wire Service (권장)
```javascript
import { LightningElement, wire } from 'lwc';
import getAccounts from '@salesforce/apex/AccountController.getAccounts';

export default class AccountList extends LightningElement {
    @wire(getAccounts)
    wiredAccounts({ error, data }) {
        if (data) {
            this.accounts = data;
            this.error = undefined;
        } else if (error) {
            this.error = error;
            this.accounts = undefined;
        }
    }
}
```

### Imperative Call
```javascript
import { LightningElement } from 'lwc';
import getAccounts from '@salesforce/apex/AccountController.getAccounts';

export default class AccountList extends LightningElement {
    accounts = [];
    isLoading = false;

    async connectedCallback() {
        await this.loadAccounts();
    }

    async loadAccounts() {
        this.isLoading = true;
        try {
            this.accounts = await getAccounts();
        } catch (error) {
            console.error('Error:', error);
        } finally {
            this.isLoading = false;
        }
    }
}
```

## 커스텀 이벤트

### 자식 → 부모 통신
```javascript
// 자식 컴포넌트
handleSave() {
    const event = new CustomEvent('save', {
        detail: {
            id: this.recordId,
            name: this.name
        },
        bubbles: true,      // 이벤트 버블링
        composed: true      // Shadow DOM 경계 통과
    });
    this.dispatchEvent(event);
}
```

```html
<!-- 부모 컴포넌트 -->
<c-child-component onsave={handleChildSave}></c-child-component>
```

```javascript
// 부모 컴포넌트
handleChildSave(event) {
    const { id, name } = event.detail;
    console.log('Received:', id, name);
}
```

## 참조 문서

상세 정보는 다음 파일을 참조하세요:
- [디렉티브 상세](references/directives.md) - 템플릿 디렉티브 전체 목록
- [데코레이터 상세](references/decorators.md) - @api, @track, @wire 상세
- [라이프사이클](references/lifecycle.md) - 생명주기 훅 상세
- [CSS 가이드](references/css.md) - 스타일링 패턴

## 템플릿 사용

컴포넌트 템플릿은 `templates/` 폴더를 참조하세요:
- `templates/basic.md` - 기본 컴포넌트
- `templates/form.md` - 폼 컴포넌트
- `templates/list.md` - 리스트 컴포넌트
- `templates/modal.md` - 모달 컴포넌트
