# LWC HTML 템플릿 디렉티브

> 출처: [Salesforce LWC Developer Guide](https://developer.salesforce.com/docs/platform/lwc/guide/reference-directives.html)

## 조건부 렌더링

### lwc:if / lwc:elseif / lwc:else (권장)

```html
<template>
    <template lwc:if={condition1}>
        <!-- condition1이 truthy일 때 -->
    </template>
    <template lwc:elseif={condition2}>
        <!-- condition2가 truthy일 때 -->
    </template>
    <template lwc:else>
        <!-- 위 조건 모두 falsy일 때 -->
    </template>
</template>
```

**규칙:**
- `lwc:elseif`와 `lwc:else`는 반드시 `lwc:if` 또는 `lwc:elseif` 바로 다음에 위치
- `lwc:else`는 값을 가질 수 없음
- 복잡한 표현식(`!condition`, `a && b`)은 지원 안 됨 → getter 사용

```javascript
// 복잡한 조건은 getter로
get isReady() {
    return this.isLoaded && !this.hasError;
}
```

## ⚠️ 템플릿 표현식 제한사항 (LWC1060 에러)

LWC 템플릿에서는 **단순 프로퍼티 참조만 허용**됩니다. JavaScript 표현식은 사용할 수 없습니다.

### UnaryExpression 금지

```html
<!-- ❌ 에러: LWC1060 - Template expression doesn't allow UnaryExpression -->
<template lwc:if={!hasData}>
    <p>No data</p>
</template>

<!-- ✅ 해결: getter 사용 -->
<template lwc:if={hasNoData}>
    <p>No data</p>
</template>
```

```javascript
// JS에서 getter 정의
get hasNoData() {
    return !this.hasData;
}
```

### ConditionalExpression (삼항연산자) 금지

```html
<!-- ❌ 에러: LWC1060 - Template expression doesn't allow ConditionalExpression -->
<span>{isActive ? 'Active' : 'Inactive'}</span>
<span class={isError ? 'error' : 'normal'}></span>
<span>{sortField === 'name' ? sortIndicator : ''}</span>

<!-- ✅ 해결: getter 사용 -->
<span>{statusText}</span>
<span class={statusClass}></span>
<span>{nameSortIcon}</span>
```

```javascript
// JS에서 getter 정의
get statusText() {
    return this.isActive ? 'Active' : 'Inactive';
}

get statusClass() {
    return this.isError ? 'error' : 'normal';
}

get nameSortIcon() {
    return this.sortField === 'name' ? this.sortIndicator : '';
}
```

### BinaryExpression 금지

```html
<!-- ❌ 에러: LWC1060 - Template expression doesn't allow BinaryExpression -->
<template lwc:if={count > 0}>...</template>
<template lwc:if={status === 'active'}>...</template>
<template lwc:if={a && b}>...</template>

<!-- ✅ 해결: getter 사용 -->
<template lwc:if={hasItems}>...</template>
<template lwc:if={isActive}>...</template>
<template lwc:if={isReady}>...</template>
```

```javascript
get hasItems() {
    return this.count > 0;
}

get isActive() {
    return this.status === 'active';
}

get isReady() {
    return this.a && this.b;
}
```

### 허용되는 표현식

```html
<!-- ✅ 단순 프로퍼티 참조 -->
{propertyName}
{object.property}

<!-- ✅ Getter 참조 -->
{computedProperty}
```

### 정리: 금지되는 표현식 목록

| 표현식 유형 | 예시 | 해결 방법 |
|------------|------|----------|
| UnaryExpression | `{!value}` | `get notValue()` |
| ConditionalExpression | `{a ? b : c}` | `get computedValue()` |
| BinaryExpression | `{a > b}`, `{a === b}`, `{a && b}` | `get isGreater()` |
| CallExpression | `{method()}` | `get result()` |
| MemberExpression (계산된) | `{arr[index]}` | `get item()` |

### if:true / if:false (비권장, deprecated)

```html
<!-- 사용하지 마세요 -->
<template if:true={condition}>...</template>
<template if:false={condition}>...</template>
```

## 리스트 렌더링

### for:each

```html
<template>
    <ul>
        <template for:each={items} for:item="item" for:index="idx">
            <li key={item.id}>
                Index: {idx}, Name: {item.name}
            </li>
        </template>
    </ul>
</template>
```

| 속성 | 설명 |
|------|------|
| `for:each={array}` | 반복할 배열 |
| `for:item="name"` | 현재 항목 변수명 |
| `for:index="idx"` | 현재 인덱스 (선택) |
| `key={uniqueId}` | 고유 키 (필수) |

### iterator

첫/마지막 항목 특별 처리:

```html
<template>
    <ul>
        <template iterator:it={items}>
            <li key={it.value.id}>
                <template lwc:if={it.first}>
                    <span class="first-badge">First</span>
                </template>

                {it.value.name} (Index: {it.index})

                <template lwc:if={it.last}>
                    <span class="last-badge">Last</span>
                </template>
            </li>
        </template>
    </ul>
</template>
```

| 속성 | 타입 | 설명 |
|------|------|------|
| `it.value` | Object | 현재 항목 값 |
| `it.index` | Number | 현재 인덱스 |
| `it.first` | Boolean | 첫 번째 항목 여부 |
| `it.last` | Boolean | 마지막 항목 여부 |

## key 디렉티브

리스트의 각 항목에 고유 키 필수:

```html
<!-- 올바른 사용 -->
<template for:each={items} for:item="item">
    <li key={item.id}>{item.name}</li>
</template>

<!-- ❌ 객체를 key로 사용 불가 -->
<li key={item}>{item.name}</li>
```

## lwc:ref

DOM 요소 참조:

```html
<template>
    <input type="text" lwc:ref="myInput">
    <button onclick={focusInput}>Focus</button>
</template>
```

```javascript
focusInput() {
    this.refs.myInput.focus();
}
```

## lwc:spread

객체 속성 펼치기:

```html
<template>
    <c-child lwc:spread={childProps}></c-child>
</template>
```

```javascript
get childProps() {
    return {
        title: this.title,
        description: this.description,
        onchange: this.handleChange
    };
}
```

## 슬롯 (Slot)

### 기본 슬롯

```html
<!-- 자식 컴포넌트 -->
<template>
    <div class="card">
        <slot></slot>
    </div>
</template>

<!-- 부모 컴포넌트 -->
<c-card>
    <p>이 내용이 슬롯에 들어갑니다</p>
</c-card>
```

### 명명된 슬롯

```html
<!-- 자식 컴포넌트 -->
<template>
    <div class="card">
        <header><slot name="header"></slot></header>
        <main><slot></slot></main>
        <footer><slot name="footer"></slot></footer>
    </div>
</template>

<!-- 부모 컴포넌트 -->
<c-card>
    <span slot="header">제목</span>
    <p>본문 내용</p>
    <span slot="footer">하단</span>
</c-card>
```

## 중첩 템플릿 규칙

중첩된 `<template>` 태그는 반드시 다음 디렉티브 중 하나를 포함해야 함:
- `for:each`
- `iterator:*`
- `lwc:if`
- `lwc:elseif`
- `lwc:else`

```html
<!-- ✅ 올바른 사용 -->
<template lwc:if={condition}>
    <p>Content</p>
</template>

<!-- ❌ 잘못된 사용 - 디렉티브 없음 -->
<template>
    <p>Content</p>
</template>
```
