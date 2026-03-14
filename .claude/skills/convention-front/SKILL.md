---
name: convention-front
description: "Enforces frontend coding conventions for HTML, CSS, JavaScript, and TypeScript files. Use when writing or reviewing HTML for semantic markup and accessibility, applying CSS BEM methodology and property ordering, enforcing camelCase naming and type annotations in JS/TS, or ensuring TSDoc documentation standards across .html/.css/.js/.ts/.jsx/.tsx files."
license: "Apache-2.0"
user-invocable: false
---

# 프론트엔드 통합 코딩 컨벤션

HTML, CSS, JavaScript, TypeScript 코드 작성 시 일관된 스타일과 구조를 유지하기 위한 통합 컨벤션 가이드입니다. 이 스킬은 `.html`, `.css`, `.js`, `.ts`, `.jsx`, `.tsx` 파일 읽기/쓰기 시 자동으로 트리거되며, 규칙 위반 시 자동 수정을 수행합니다.

---

## 1. HTML 컨벤션

### 1.1 소문자/큰따옴표 규칙

- 태그명과 속성명은 항상 소문자로 작성
- 속성값은 항상 큰따옴표(`"`)로 감싸기

```html
<!-- 좋은 예 -->
<div class="container" id="main-content">
  <input type="text" placeholder="검색어 입력" />
</div>

<!-- 나쁜 예 -->
<DIV Class='container' ID='main-content'>
  <INPUT TYPE='text' placeholder='검색어 입력' />
</DIV>
```

### 1.2 속성 순서 규칙

HTML 요소의 속성은 다음 순서로 작성한다:

1. `class`
2. `id`, `name`
3. `data-*`
4. `src`, `for`, `type`, `href`, `value`
5. `title`, `alt`
6. `role`, `aria-*`

```html
<!-- 좋은 예 -->
<a class="nav-link" id="home-link" data-section="home" href="/home" title="홈으로 이동" role="navigation">
  홈
</a>

<img class="profile-img" data-user-id="123" src="/img/avatar.png" alt="사용자 프로필 사진" />

<!-- 나쁜 예 (순서 불일치) -->
<a href="/home" id="home-link" class="nav-link" role="navigation" title="홈으로 이동" data-section="home">
  홈
</a>
```

### 1.3 시맨틱 태그 우선 규칙

의미를 가진 시맨틱 태그를 우선 사용하고, `<div>`/`<span>` 남용을 금지한다.

| 용도 | 시맨틱 태그 | 금지 (남용) |
|------|-------------|-------------|
| 페이지 헤더 | `<header>` | `<div class="header">` |
| 내비게이션 | `<nav>` | `<div class="nav">` |
| 주요 콘텐츠 | `<main>` | `<div class="main">` |
| 독립 콘텐츠 단위 | `<article>` | `<div class="article">` |
| 구획 구분 | `<section>` | `<div class="section">` |
| 보조 콘텐츠 | `<aside>` | `<div class="sidebar">` |
| 페이지 푸터 | `<footer>` | `<div class="footer">` |

```html
<!-- 좋은 예 -->
<header>
  <nav>
    <ul>
      <li><a href="/home">홈</a></li>
    </ul>
  </nav>
</header>
<main>
  <article>
    <h2>제목</h2>
    <p>본문</p>
  </article>
  <aside>관련 링크</aside>
</main>
<footer>저작권 정보</footer>

<!-- 나쁜 예 -->
<div class="header">
  <div class="nav">
    <ul>
      <li><a href="/home">홈</a></li>
    </ul>
  </div>
</div>
<div class="main">
  <div class="article">
    <h2>제목</h2>
    <p>본문</p>
  </div>
  <div class="sidebar">관련 링크</div>
</div>
<div class="footer">저작권 정보</div>
```

### 1.4 접근성 규칙

- `<img>` 태그에 `alt` 속성 필수
- 인터랙티브 요소에 `aria-label` 또는 `aria-labelledby` 적절히 사용
- `role` 속성으로 역할 명시 (커스텀 위젯일 경우)
- `tabindex` 관리: `0`(자연 순서) 또는 `-1`(프로그래밍 포커스)만 사용, 양수 금지

```html
<!-- 좋은 예 -->
<img class="logo" src="/img/logo.png" alt="회사 로고" />

<button class="close-btn" aria-label="모달 닫기">
  <span aria-hidden="true">&times;</span>
</button>

<div class="tab-panel" role="tabpanel" aria-labelledby="tab-1" tabindex="0">
  패널 내용
</div>

<!-- 나쁜 예 -->
<img src="/img/logo.png" />

<button class="close-btn">
  <span>&times;</span>
</button>

<div class="tab-panel">
  패널 내용
</div>
```

### 1.5 kebab-case 네이밍

`id`, `class`, `data-*` 속성값에는 kebab-case를 적용한다.

```html
<!-- 좋은 예 -->
<div class="user-profile" id="main-content" data-user-role="admin"></div>

<!-- 나쁜 예 -->
<div class="userProfile" id="mainContent" data-userRole="admin"></div>
```

### 1.6 불린 속성 규칙

`disabled`, `checked`, `readonly`, `required`, `hidden`, `autofocus` 등 불린 속성은 값을 생략한다.

```html
<!-- 좋은 예 -->
<input type="text" disabled />
<input type="checkbox" checked />
<textarea readonly></textarea>
<input type="email" required />

<!-- 나쁜 예 -->
<input type="text" disabled="disabled" />
<input type="checkbox" checked="checked" />
<textarea readonly="readonly"></textarea>
<input type="email" required="true" />
```

---

## 2. CSS 컨벤션

### 2.1 프로퍼티 순서 규칙 (5단계)

CSS 프로퍼티는 다음 5단계 순서로 작성한다:

1. **Positioning**: `position`, `top`, `right`, `bottom`, `left`, `z-index`
2. **Box Model**: `display`, `flex`, `grid`, `width`, `height`, `margin`, `padding`, `overflow`
3. **Typography**: `font`, `font-size`, `font-weight`, `line-height`, `color`, `text-align`, `text-decoration`, `letter-spacing`
4. **Visual**: `background`, `border`, `border-radius`, `opacity`, `box-shadow`
5. **Misc**: `transition`, `animation`, `transform`, `cursor`, `pointer-events`

```css
/* 좋은 예 */
.card {
  /* Positioning */
  position: relative;
  z-index: 10;

  /* Box Model */
  display: flex;
  width: 100%;
  max-width: 40rem;
  margin: 0 auto;
  padding: 1.5rem;

  /* Typography */
  font-size: 1rem;
  line-height: 1.5;
  color: oklch(0.3 0.02 260);

  /* Visual */
  background: oklch(0.98 0.005 260);
  border: 1px solid oklch(0.8 0.02 260);
  border-radius: 0.5rem;
  box-shadow: 0 2px 4px oklch(0 0 0 / 0.1);

  /* Misc */
  transition: box-shadow 0.2s ease;
  cursor: pointer;
}

/* 나쁜 예 (순서 불일치) */
.card {
  cursor: pointer;
  font-size: 1rem;
  position: relative;
  background: #fafafa;
  display: flex;
  border: 1px solid #ccc;
  margin: 0 auto;
  z-index: 10;
}
```

### 2.2 BEM 네이밍 규칙

Block__Element--Modifier 패턴으로 CSS 클래스를 작성한다.

```css
/* Block */
.card { }

/* Element (Block 내부 요소) */
.card__title { }
.card__body { }
.card__footer { }

/* Modifier (변형) */
.card--featured { }
.card--compact { }
.card__title--large { }
```

```html
<!-- 좋은 예 -->
<div class="card card--featured">
  <h2 class="card__title card__title--large">제목</h2>
  <div class="card__body">본문</div>
  <div class="card__footer">푸터</div>
</div>

<!-- 나쁜 예 -->
<div class="featured-card">
  <h2 class="title large">제목</h2>
  <div class="body">본문</div>
  <div class="footer">푸터</div>
</div>
```

### 2.3 class 우선 규칙

스타일링에는 `id` 셀렉터 대신 `class` 셀렉터를 사용한다. `id`는 JS 접근/앵커 용도로만 사용.

```css
/* 좋은 예 */
.navigation { }
.header { }
.main-content { }

/* 나쁜 예 */
#navigation { }
#header { }
#main-content { }
```

### 2.4 0값 단위 생략

값이 `0`일 때 단위를 생략한다.

```css
/* 좋은 예 */
.element {
  margin: 0;
  padding: 0;
  border: 0;
}

/* 나쁜 예 */
.element {
  margin: 0px;
  padding: 0rem;
  border: 0px;
}
```

### 2.5 축약형 사용

`margin`, `padding`, `border`, `font`, `background` 등은 가능하면 축약형을 사용한다.

```css
/* 좋은 예 */
.element {
  margin: 1rem 2rem;
  padding: 0.5rem 1rem 0.5rem 1rem;
  border: 1px solid oklch(0.7 0.02 260);
  font: bold 1rem/1.5 sans-serif;
}

/* 나쁜 예 */
.element {
  margin-top: 1rem;
  margin-right: 2rem;
  margin-bottom: 1rem;
  margin-left: 2rem;
  border-width: 1px;
  border-style: solid;
  border-color: #999;
}
```

### 2.6 모던 색상 표기

`oklch()` 또는 `hsl()`을 우선 사용한다. hex(`#rrggbb`)는 허용, `rgb()`는 구식으로 간주한다.

```css
/* 좋은 예 */
.element {
  color: oklch(0.5 0.15 260);
  background: hsl(220 60% 50%);
  border-color: #3366cc; /* hex 허용 */
}

/* 나쁜 예 */
.element {
  color: rgb(51, 102, 204);
  background: rgba(51, 102, 204, 0.5);
}
```

### 2.7 모던 미디어쿼리 표기

range syntax를 우선 사용한다.

```css
/* 좋은 예 */
@media (width >= 768px) {
  .container { max-width: 720px; }
}

@media (768px <= width <= 1024px) {
  .container { max-width: 960px; }
}

/* 나쁜 예 */
@media (min-width: 768px) {
  .container { max-width: 720px; }
}
```

### 2.8 !important 금지

`!important`는 사용하지 않는다. 특수성(specificity)을 올바르게 관리하여 해결한다.

```css
/* 좋은 예 */
.modal .close-button {
  display: block;
}

/* 나쁜 예 */
.close-button {
  display: block !important;
}
```

### 2.9 더블콜론 pseudo-element

pseudo-element에는 `::` (더블콜론)을 사용한다. 단일 콜론 `:before`, `:after`는 금지.

```css
/* 좋은 예 */
.element::before {
  content: "";
}
.element::after {
  content: "";
}
.element::first-line { }
.element::placeholder { }

/* 나쁜 예 */
.element:before {
  content: "";
}
.element:after {
  content: "";
}
```

### 2.10 상대 단위 우선

`rem`, `em`, `%`, `vw`, `vh`를 우선 사용하고 `px`은 최소화한다. `1px` 보더 등 물리 픽셀이 필요한 경우만 `px` 허용.

```css
/* 좋은 예 */
.element {
  font-size: 1rem;
  padding: 1.5em;
  width: 80%;
  max-width: 60rem;
  border: 1px solid oklch(0.8 0.02 260); /* px 허용: 물리 픽셀 보더 */
}

/* 나쁜 예 */
.element {
  font-size: 16px;
  padding: 24px;
  width: 800px;
  max-width: 960px;
}
```

### 2.11 모바일 퍼스트

`min-width` 기반 미디어쿼리로 모바일 퍼스트 접근법을 사용한다.

```css
/* 좋은 예: 모바일 퍼스트 (기본 -> 확장) */
.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

@media (width >= 768px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (width >= 1024px) {
  .grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* 나쁜 예: 데스크톱 퍼스트 (기본 -> 축소) */
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
}

@media (max-width: 1024px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
```

---

## 3. JS/TS 컨벤션

### 3.1 네이밍 규칙

JavaScript/TypeScript 코드에서는 일관된 네이밍 규칙을 적용하여 가독성과 유지보수성을 높인다.

#### 변수 및 함수: camelCase

- 소문자로 시작, 이후 각 단어의 첫 글자를 대문자로 표기
- 예: `userName`, `getUserData()`, `maxRetryCount`
- 금지: `user_name`, `get_user_data`, `UserName`

#### 클래스: PascalCase

- 각 단어의 첫 글자를 대문자로 표기
- 예: `UserService`, `DataProcessor`, `ApiClient`
- 금지: `user_service`, `dataProcessor`, `api_client`

#### 상수: UPPER_SNAKE_CASE

- 모든 글자를 대문자로, 단어는 언더스코어로 구분
- `const`로 선언된 원시값/불변 객체에 적용
- 예: `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT`, `API_BASE_URL`
- 금지: `maxRetryCount` (일반 변수), `MaxRetryCount`

#### Private 멤버: `#` private 필드(ES2022+) 또는 `_` 접두사(레거시)

- ES2022+ 환경: `#` private 필드 사용 (예: `#internalState`, `#validateInput()`)
- 레거시/호환성 필요 시: `_` 접두사 1개 (예: `_cache`, `_validateInput()`)

#### 파일명

- 일반 모듈/유틸리티: kebab-case.ts (예: `user-service.ts`, `data-processor.ts`)
- React 컴포넌트: PascalCase.tsx (예: `UserCard.tsx`, `DataTable.tsx`)
- 금지: `UserService.ts` (컴포넌트 외), `data_processor.ts`

#### 타입/인터페이스: PascalCase (`I` 접두사 금지)

- 예: `UserProps`, `ApiResponse`, `OrderStatus`
- 금지: `IUserProps`, `IApiResponse` (`I` 접두사 헝가리안 표기법 금지)

#### Enum: PascalCase (멤버도 PascalCase)

```typescript
// 좋은 예
enum Status {
  Active,
  Inactive,
  Pending,
}

enum HttpMethod {
  Get = "GET",
  Post = "POST",
  Put = "PUT",
}

// 나쁜 예
enum status {
  ACTIVE,
  INACTIVE,
}
```

### 3.2 타입 시스템 (이중 방식)

TypeScript 또는 JSDoc을 통해 타입 안전성을 확보한다.

#### TypeScript (권장): 전체 타입 어노테이션 필수

모든 함수 인자, 반환값, 변수에 타입 어노테이션을 명시한다.

```typescript
// 좋은 예
function getUser(userId: number): Record<string, string> {
  return { id: String(userId), name: "John" };
}

function calculateTotal(items: number[], taxRate: number): number {
  return items.reduce((sum, item) => sum + item, 0) * (1 + taxRate);
}

// 나쁜 예 (타입 어노테이션 누락)
function getUser(userId) {
  return { id: String(userId), name: "John" };
}
```

#### `type` vs `interface` 가이드

- `type`: 유니온, 교차, 튜플, 원시 타입 별칭에 사용

  ```typescript
  type Status = "active" | "inactive" | "pending";
  type ApiResult<T> = { data: T; error: string | null };
  type Coordinates = [number, number];
  ```

- `interface`: 객체 형상 정의, 클래스 계약, 선언 병합(declaration merging)에 사용

  ```typescript
  interface UserRepository {
    findById(id: number): Promise<User>;
    save(user: User): Promise<void>;
  }

  interface User {
    id: number;
    name: string;
    email: string;
  }
  ```

#### `any` 금지, `unknown` 우선

```typescript
// 나쁜 예
function parseInput(input: any): any {
  return JSON.parse(input);
}

// 좋은 예
function parseInput(input: unknown): Record<string, unknown> {
  if (typeof input !== "string") {
    throw new TypeError("입력값은 문자열이어야 합니다");
  }
  return JSON.parse(input) as Record<string, unknown>;
}
```

#### 제네릭 활용

```typescript
// 좋은 예
function identity<T>(value: T): T {
  return value;
}

function first<T>(arr: T[]): T | undefined {
  return arr[0];
}

class Repository<T extends { id: number }> {
  private items: T[] = [];

  findById(id: number): T | undefined {
    return this.items.find((item) => item.id === id);
  }
}
```

#### 클래스 속성 타입 어노테이션 필수

```typescript
class UserService {
  // 클래스 변수
  static readonly MAX_USERS: number = 1000;
  static defaultTimeout: number = 30.0;

  // 인스턴스 변수
  private readonly dbUrl: string;
  private cache: Map<string, string>;
  private userCount: number;

  constructor(dbUrl: string) {
    this.dbUrl = dbUrl;
    this.cache = new Map();
    this.userCount = 0;
  }
}
```

#### JavaScript (폴백): JSDoc 타입 주석으로 동등한 타입 안전성 확보

TypeScript를 사용할 수 없는 환경에서는 JSDoc으로 타입 안전성을 보장한다.

```javascript
/**
 * 사용자 정보를 반환합니다.
 * @param {number} userId - 사용자 ID
 * @returns {{ id: string, name: string }} 사용자 객체
 */
function getUser(userId) {
  return { id: String(userId), name: "John" };
}

/**
 * @typedef {Object} UserConfig
 * @property {string} name - 사용자 이름
 * @property {string} email - 이메일 주소
 * @property {number} [age] - 나이 (선택사항)
 */

/**
 * @param {UserConfig} config
 * @returns {void}
 */
function createUser(config) {
  // 구현
}
```

### 3.3 주석/문서화 규칙 (TSDoc/JSDoc 스타일)

명확하고 유지보수하기 쉬운 문서화를 위해 TSDoc/JSDoc 스타일을 사용한다.

#### 파일 최상단 모듈 설명 (필수)

```typescript
/**
 * @module user-service
 *
 * 사용자 관리 모듈.
 *
 * 이 모듈은 사용자 생성, 조회, 수정, 삭제 기능을 제공합니다.
 *
 * @remarks
 * 주요 클래스:
 * - {@link UserService}: 사용자 비즈니스 로직 처리
 * - {@link User}: 사용자 데이터 모델
 */
```

#### Public 함수/메서드: TSDoc 필수

```typescript
/**
 * 가격에 할인을 적용합니다.
 *
 * 회원 여부에 따라 추가 할인을 제공합니다.
 *
 * @param price - 원래 가격 (원화)
 * @param discountRate - 할인율 (0.0 ~ 1.0)
 * @param isMember - 회원 여부
 * @returns 할인이 적용된 최종 가격. 할인율이 유효하지 않으면 원래 가격.
 * @throws {RangeError} discountRate가 0.0 ~ 1.0 범위를 벗어난 경우
 * @example
 * ```typescript
 * const finalPrice = calculateDiscount(10000, 0.1, true);
 * // finalPrice === 8550
 * ```
 */
function calculateDiscount(
  price: number,
  discountRate: number,
  isMember: boolean
): number {
  if (discountRate < 0.0 || discountRate > 1.0) {
    throw new RangeError("할인율은 0.0 ~ 1.0 범위여야 합니다");
  }

  let finalPrice = price * (1 - discountRate);

  if (isMember) {
    finalPrice *= 0.95; // 추가 5% 할인
  }

  return finalPrice;
}
```

#### 클래스 TSDoc

```typescript
/**
 * 사용자 관리 서비스.
 *
 * 데이터베이스에서 사용자 정보를 조회, 생성, 수정, 삭제합니다.
 *
 * @remarks
 * 캐싱을 통해 반복 조회 성능을 최적화합니다.
 */
class UserManager {
  private cache: Map<number, User>;

  /**
   * UserManager를 초기화합니다.
   *
   * @param dbUrl - 데이터베이스 연결 URL
   */
  constructor(private readonly dbUrl: string) {
    this.cache = new Map();
  }
}
```

#### 인라인 주석: 복잡한 로직/비즈니스 규칙에 필수

```typescript
function processOrder(order: Order): void {
  // 배송료 계산: 기본 배송료 3,000원 + 지역별 추가 요금
  let shippingCost = 3000;
  if (order.region === "jeju") {
    shippingCost += 5000; // 제주도 추가료
  }

  // 상품 수 5개 이상 시 배송료 면제 (정책 변경 시 여기서 수정)
  if (order.items.length >= 5) {
    shippingCost = 0;
  }

  order.shippingCost = shippingCost;
}
```

#### Private 함수/메서드: 최소 한 줄 `/** ... */` 권장

```typescript
/** 이메일 형식을 검증합니다. */
function validateEmailFormat(email: string): boolean {
  return email.includes("@") && email.split("@")[1].includes(".");
}

/** SHA-256 해시를 계산합니다. */
async function computeHash(data: string): Promise<string> {
  const encoder = new TextEncoder();
  const buffer = await crypto.subtle.digest("SHA-256", encoder.encode(data));
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
```

### 3.4 모던 JS 베스트 프랙티스

#### const 기본 / let 최소 / var 금지

```typescript
// 좋은 예
const MAX_SIZE = 100;
const user = { name: "Alice" };
let count = 0; // 재할당이 필요한 경우에만 let

// 나쁜 예
var MAX_SIZE = 100;
var user = { name: "Alice" };
var count = 0;
```

#### Arrow Function 선호

콜백이나 간단한 함수에는 arrow function을 사용한다. 메서드 정의는 축약 메서드 구문 사용.

```typescript
// 좋은 예
const double = (n: number): number => n * 2;
const users = items.map((item) => item.name);
const filtered = data.filter((d) => d.active);

// 나쁜 예
const double = function(n) { return n * 2; };
const users = items.map(function(item) { return item.name; });
```

#### Template Literal

문자열 결합에는 template literal을 사용한다.

```typescript
// 좋은 예
const greeting = `안녕하세요, ${userName}님. ${itemCount}개의 상품이 있습니다.`;
const url = `${API_BASE_URL}/users/${userId}`;

// 나쁜 예
const greeting = "안녕하세요, " + userName + "님. " + itemCount + "개의 상품이 있습니다.";
const url = API_BASE_URL + "/users/" + userId;
```

#### Destructuring

객체/배열 비구조화 할당을 적극 활용한다.

```typescript
// 좋은 예
const { name, email, age } = user;
const [first, second, ...rest] = items;
const { data, error } = await fetchUser(userId);

// 나쁜 예
const name = user.name;
const email = user.email;
const age = user.age;
const first = items[0];
const second = items[1];
```

#### Spread Operator

배열/객체 복사 및 병합에 spread operator를 사용한다.

```typescript
// 좋은 예
const merged = { ...defaults, ...overrides };
const newItems = [...existingItems, newItem];

// 나쁜 예
const merged = Object.assign({}, defaults, overrides);
const newItems = existingItems.concat([newItem]);
```

#### Trailing Comma

여러 줄에 걸친 배열, 객체, 함수 매개변수에 trailing comma를 사용한다.

```typescript
// 좋은 예
const config = {
  host: "localhost",
  port: 3000,
  debug: true,
};

function createUser(
  name: string,
  email: string,
  role: string,
): User {
  // ...
}

// 나쁜 예
const config = {
  host: "localhost",
  port: 3000,
  debug: true
};
```

#### Named Export 우선

`default export` 대신 `named export`를 사용한다.

```typescript
// 좋은 예
export function getUser(id: number): User { ... }
export class UserService { ... }
export type UserProps = { ... };

// 나쁜 예
export default function getUser(id: number): User { ... }
export default class UserService { ... }
```

#### 중괄호 필수 (if/for/while)

단일 문장이더라도 중괄호를 생략하지 않는다.

```typescript
// 좋은 예
if (isValid) {
  process();
}

for (const item of items) {
  console.log(item);
}

// 나쁜 예
if (isValid) process();
for (const item of items) console.log(item);
```

#### async/await 선호

Promise `.then()` 체인 대신 `async/await`를 사용한다.

```typescript
// 좋은 예
async function fetchUserData(userId: number): Promise<UserData> {
  const response = await fetch(`/api/users/${userId}`);
  const data = await response.json();
  return data as UserData;
}

// 나쁜 예
function fetchUserData(userId: number): Promise<UserData> {
  return fetch(`/api/users/${userId}`)
    .then((response) => response.json())
    .then((data) => data as UserData);
}
```

---

## 4. 위반 시 자동 수정 동작

HTML/CSS/JS/TS 파일 읽기/쓰기 시 컨벤션 위반을 감지하고 자동으로 수정한다.

### 4.1 HTML 자동 수정

#### 속성 순서 재정렬

- **문제**: 속성이 규정 순서(class -> id -> data-* -> src/href -> title/alt -> role/aria-*)에 맞지 않음
- **수정**: 규정 순서에 맞게 속성 재정렬
- **예**:
  ```html
  <!-- 수정 전 -->
  <a href="/home" id="nav-home" class="nav-link">홈</a>

  <!-- 수정 후 -->
  <a class="nav-link" id="nav-home" href="/home">홈</a>
  ```

#### 시맨틱 태그 전환 권고

- **문제**: `<div class="header">` 등 시맨틱 태그로 대체 가능한 패턴 발견
- **수정**: 해당 시맨틱 태그로 전환 권고 (확인 후 수행)
- **예**:
  ```html
  <!-- 수정 전 -->
  <div class="header">제목</div>

  <!-- 수정 후 -->
  <header>제목</header>
  ```

#### 불린 속성 값 제거

- **문제**: `disabled="disabled"`, `checked="checked"` 등 불필요한 값 지정
- **수정**: 값 부분 자동 제거
- **예**:
  ```html
  <!-- 수정 전 -->
  <input type="checkbox" checked="checked" disabled="disabled" />

  <!-- 수정 후 -->
  <input type="checkbox" checked disabled />
  ```

#### 소문자/큰따옴표 변환

- **문제**: 대문자 태그명/속성명 또는 작은따옴표 사용
- **수정**: 소문자 + 큰따옴표로 자동 변환
- **예**:
  ```html
  <!-- 수정 전 -->
  <DIV Class='container'>내용</DIV>

  <!-- 수정 후 -->
  <div class="container">내용</div>
  ```

### 4.2 CSS 자동 수정

#### 프로퍼티 순서 재정렬

- **문제**: CSS 프로퍼티가 5단계 순서(Positioning -> Box Model -> Typography -> Visual -> Misc)에 맞지 않음
- **수정**: 규정 순서에 맞게 프로퍼티 재정렬

#### 0값 단위 제거

- **문제**: `margin: 0px`, `padding: 0rem` 등 불필요한 단위
- **수정**: `0`으로 자동 변환
- **예**:
  ```css
  /* 수정 전 */
  .element { margin: 0px; padding: 0rem; }

  /* 수정 후 */
  .element { margin: 0; padding: 0; }
  ```

#### 단일콜론 -> 더블콜론 변환

- **문제**: `:before`, `:after` 등 단일콜론 pseudo-element
- **수정**: `::before`, `::after`로 자동 변환
- **예**:
  ```css
  /* 수정 전 */
  .element:before { content: ""; }

  /* 수정 후 */
  .element::before { content: ""; }
  ```

#### !important 제거 권고

- **문제**: `!important` 사용 감지
- **수정**: 제거를 권고하고 특수성 관리 방안 제시 (확인 후 수행)

### 4.3 JS/TS 자동 수정

#### 타입 어노테이션 자동 추가 (TypeScript)

- **문제**: 함수 인자 또는 반환값에 타입 어노테이션 누락
- **수정**: 문맥상 타입 추론 후 `param: Type` 또는 `: ReturnType` 추가
- **예**:
  ```typescript
  // 수정 전
  function getUser(userId) {
    return { name: "John" };
  }

  // 수정 후
  function getUser(userId: number): Record<string, string> {
    return { name: "John" };
  }
  ```

#### TSDoc/JSDoc 자동 보완

- **문제**: public 함수/메서드에 TSDoc 누락 또는 불완전
- **수정**: TSDoc 블록 자동 생성 (`@param`, `@returns`, `@throws`, `@example`)
- **예**:
  ```typescript
  // 수정 전
  function calculateTax(amount: number, rate: number): number {
    return amount * rate;
  }

  // 수정 후
  /**
   * 세금을 계산합니다.
   *
   * @param amount - 금액
   * @param rate - 세율
   * @returns 계산된 세금
   */
  function calculateTax(amount: number, rate: number): number {
    return amount * rate;
  }
  ```

#### 네이밍 컨벤션 위반 수정

- **문제**: 변수/함수가 snake_case, 클래스가 camelCase 등 규칙 위반
- **수정**: 자동 변환 (변수/함수 -> camelCase, 클래스/타입 -> PascalCase, 상수 -> UPPER_SNAKE_CASE)
- **주의**: 문자열 내 하드코딩된 이름은 수정하지 않음

#### 모듈 설명 자동 추가

- **문제**: 파일 최상단에 모듈 JSDoc 누락
- **수정**: 파일명을 기반으로 기본 모듈 주석 생성
- **예**:
  ```typescript
  // 수정 전
  export function getUser(userId: number): User { ... }

  // 수정 후
  /**
   * @module user
   *
   * 사용자 관련 유틸리티 함수 모음.
   */

  export function getUser(userId: number): User { ... }
  ```

#### `any` 타입 수정

- **문제**: `any` 타입 사용
- **수정**: `unknown` 또는 적절한 타입으로 교체 권고 (문맥에 따라 자동 수정)
- **예**:
  ```typescript
  // 수정 전
  function parse(input: any): any { ... }

  // 수정 후
  function parse(input: unknown): Record<string, unknown> { ... }
  ```

#### var -> const/let 변환

- **문제**: `var` 키워드 사용
- **수정**: 재할당 여부를 분석하여 `const` 또는 `let`으로 자동 변환
- **예**:
  ```typescript
  // 수정 전
  var name = "Alice";
  var count = 0;
  count += 1;

  // 수정 후
  const name = "Alice";
  let count = 0;
  count += 1;
  ```

#### function -> arrow function 변환

- **문제**: 콜백 또는 간단한 함수에서 `function` 키워드 사용
- **수정**: arrow function으로 자동 변환 (메서드, 생성자, 제너레이터 제외)
- **예**:
  ```typescript
  // 수정 전
  const items = data.map(function(item) { return item.name; });

  // 수정 후
  const items = data.map((item) => item.name);
  ```

#### 문자열 연결 -> template literal 변환

- **문제**: `+` 연산자로 문자열 결합
- **수정**: template literal로 자동 변환
- **예**:
  ```typescript
  // 수정 전
  const msg = "Hello, " + name + "! You have " + count + " items.";

  // 수정 후
  const msg = `Hello, ${name}! You have ${count} items.`;
  ```

### 자동 수정 예외 사항

- **외부 라이브러리**: 서드파티 라이브러리 함수의 시그니처는 수정하지 않음
- **테스트 코드**: `*.test.ts`, `*.spec.ts` 파일의 describe/it 블록 네이밍은 유연하게 허용
- **생성 코드**: 자동 생성된 파일(예: `*.generated.ts`, `*.d.ts`)은 수정하지 않음
- **HTML 내 인라인 스크립트/스타일**: `<script>`, `<style>` 태그 내 코드는 별도 파일 분리 권고만 수행
- **CSS 프레임워크 클래스**: Tailwind CSS, Bootstrap 등 외부 프레임워크의 클래스명은 BEM 규칙을 적용하지 않음

---

## 5. 자동 수정 수준 3단계

### 5.1 필수 수정 (항상 수행)

- 네이밍 컨벤션 위반 (JS/TS: camelCase/PascalCase/UPPER_SNAKE_CASE, HTML: kebab-case)
- 타입 어노테이션 누락 (TypeScript, 명확한 경우)
- `any` 타입 사용
- `var` 사용 (const/let으로 변환)
- 소문자/큰따옴표 규칙 위반 (HTML)
- 불린 속성 값 제거 (HTML)

### 5.2 권장 수정 (경고 후 수행)

- TSDoc/JSDoc 문서화 누락
- 모듈 설명 주석 추가
- CSS 프로퍼티 순서 재정렬
- 시맨틱 태그 전환 (HTML)
- 0값 단위 생략 (CSS)
- 단일콜론 pseudo-element -> 더블콜론 변환 (CSS)
- Private 멤버 접두사 추가 (JS/TS)

### 5.3 검토 필수 (사용자 확인 후)

- 함수/클래스 구조 리팩토링
- BEM 네이밍 전면 적용
- 접근성 aria 속성 추가 (HTML)
- `!important` 제거 및 특수성 재설계 (CSS)
- `interface` <-> `type` 변환 (TS)
- 클래스 컴포넌트 -> 함수 컴포넌트 전환

---

## 6. ESLint / Prettier / Stylelint 연동

### ESLint 연동

프로젝트 루트에 `eslint.config.js`, `eslint.config.mjs`, `.eslintrc.js`, `.eslintrc.json`, `.eslintrc.yml` 중 하나가 존재하면:

- ESLint 규칙과 충돌하는 수정은 ESLint 설정을 우선 적용
- 자동 수정 후 `npx eslint --fix` 실행 권고
- `no-any`, `explicit-function-return-type`, `naming-convention` 규칙 확인

### Prettier 연동

프로젝트 루트에 `.prettierrc`, `.prettierrc.json`, `.prettierrc.js`, `prettier.config.js` 중 하나가 존재하면:

- 들여쓰기, 따옴표 스타일, 세미콜론 등 포맷팅은 Prettier 설정을 우선 적용
- 자동 수정 후 `npx prettier --write` 실행 권고

### Stylelint 연동

프로젝트 루트에 `.stylelintrc`, `.stylelintrc.json`, `.stylelintrc.js`, `stylelint.config.js` 중 하나가 존재하면:

- Stylelint 규칙과 충돌하는 CSS 수정은 Stylelint 설정을 우선 적용
- 자동 수정 후 `npx stylelint --fix "**/*.css"` 실행 권고
- `declaration-property-order`, `selector-class-pattern`, `unit-disallowed-list` 규칙 확인

---

**마지막 갱신**: 2026-03-13
