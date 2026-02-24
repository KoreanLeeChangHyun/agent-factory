# LWC 데코레이터

> 출처: [Salesforce LWC Developer Guide](https://developer.salesforce.com/docs/platform/lwc/guide/reference-decorators.html)

## @api

부모 컴포넌트에서 접근 가능한 public property/method 정의.

### Public Property

```javascript
import { LightningElement, api } from 'lwc';

export default class MyComponent extends LightningElement {
    // 기본값 설정 가능
    @api title = 'Default Title';

    // 읽기 전용 (getter만)
    @api
    get formattedTitle() {
        return this.title.toUpperCase();
    }

    // 읽기/쓰기 (getter + setter)
    _count = 0;
    @api
    get count() {
        return this._count;
    }
    set count(value) {
        this._count = parseInt(value, 10) || 0;
    }
}
```

### Public Method

```javascript
export default class MyComponent extends LightningElement {
    @api
    focus() {
        this.template.querySelector('input').focus();
    }

    @api
    reset() {
        this.value = '';
    }
}
```

```html
<!-- 부모에서 사용 -->
<c-my-component title="Hello" count="5"></c-my-component>

<script>
// 메서드 호출
this.template.querySelector('c-my-component').focus();
</script>
```

### 주의사항
- Public property는 부모에서 변경 가능 → 컴포넌트 내부에서 직접 변경 금지
- 변경이 필요하면 private 복사본 사용

```javascript
@api title;

// ❌ 잘못된 사용
handleClick() {
    this.title = 'New Title'; // 에러!
}

// ✅ 올바른 사용
_internalTitle;

connectedCallback() {
    this._internalTitle = this.title;
}

handleClick() {
    this._internalTitle = 'New Title';
}
```

## @track

객체/배열 내부 변경을 감지하여 리렌더링.

### 언제 필요한가?

Spring '20부터 모든 필드는 기본적으로 반응형이지만, **객체/배열 내부** 변경은 감지 안 됨.

```javascript
export default class MyComponent extends LightningElement {
    // 기본 반응형 (재할당 시 리렌더링)
    name = 'John';           // 문자열
    count = 0;               // 숫자
    items = [];              // 배열 (재할당만 감지)

    // @track 필요 (내부 변경 감지)
    @track user = {};        // 객체 내부 변경
    @track products = [];    // 배열 내부 변경
}
```

### 예시

```javascript
import { LightningElement, track } from 'lwc';

export default class Example extends LightningElement {
    // @track 없음 - 재할당만 감지
    items = ['a', 'b', 'c'];

    addItemWrong() {
        this.items.push('d');  // ❌ UI 업데이트 안 됨
    }

    addItemCorrect() {
        this.items = [...this.items, 'd'];  // ✅ 재할당으로 감지
    }

    // @track 있음 - 내부 변경도 감지
    @track trackedItems = ['a', 'b', 'c'];

    addTrackedItem() {
        this.trackedItems.push('d');  // ✅ UI 업데이트 됨
    }
}
```

### 객체 내부 변경

```javascript
@track user = {
    name: 'John',
    address: {
        city: 'Seoul'
    }
};

updateCity() {
    this.user.address.city = 'Busan';  // ✅ @track으로 감지됨
}
```

## @wire

Salesforce 데이터를 반응형으로 가져오기.

### Apex 메서드 연결

```javascript
import { LightningElement, wire } from 'lwc';
import getAccounts from '@salesforce/apex/AccountController.getAccounts';

export default class AccountList extends LightningElement {
    // 방법 1: Property에 할당
    @wire(getAccounts)
    accounts;

    // 방법 2: Function으로 처리
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

### 파라미터 전달

```javascript
import { LightningElement, wire, api } from 'lwc';
import getAccount from '@salesforce/apex/AccountController.getAccount';

export default class AccountDetail extends LightningElement {
    @api recordId;

    // $recordId - 반응형 파라미터 (값 변경 시 자동 재호출)
    @wire(getAccount, { accountId: '$recordId' })
    account;
}
```

### UI API 사용

```javascript
import { LightningElement, wire, api } from 'lwc';
import { getRecord, getFieldValue } from 'lightning/uiRecordApi';
import NAME_FIELD from '@salesforce/schema/Account.Name';

export default class AccountName extends LightningElement {
    @api recordId;

    @wire(getRecord, { recordId: '$recordId', fields: [NAME_FIELD] })
    account;

    get accountName() {
        return getFieldValue(this.account.data, NAME_FIELD);
    }
}
```

### Wire vs Imperative

| Wire | Imperative |
|------|-----------|
| 선언적 | 명령적 |
| 자동 캐싱 | 수동 호출 |
| 파라미터 변경 시 자동 재호출 | 직접 호출 필요 |
| 읽기 전용 | CRUD 모두 가능 |

```javascript
// Imperative Call (DML 작업 등)
import { LightningElement } from 'lwc';
import createAccount from '@salesforce/apex/AccountController.createAccount';

export default class CreateAccount extends LightningElement {
    async handleCreate() {
        try {
            const result = await createAccount({ name: 'New Account' });
            console.log('Created:', result);
        } catch (error) {
            console.error('Error:', error);
        }
    }
}
```

## 데코레이터 요약

| 데코레이터 | 용도 | 반응형 |
|-----------|------|--------|
| `@api` | Public property/method | 부모에서 변경 시 |
| `@track` | 객체/배열 내부 변경 감지 | 내부 변경 시 |
| `@wire` | Salesforce 데이터 연결 | 파라미터 변경 시 |
| (없음) | Private reactive field | 재할당 시 |
