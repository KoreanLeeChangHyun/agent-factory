---
name: convention-javascript
description: ".js/.ts/.jsx/.tsx 파일 읽기/쓰기 시 트리거되는 JavaScript/TypeScript 코딩 컨벤션 강제 스킬. camelCase 네이밍, TypeScript 타입 어노테이션, TSDoc/JSDoc 문서화, OOP 설계 규칙을 강제한다. Triggers: '*.js', '*.ts', '*.jsx', '*.tsx', 'JavaScript', 'TypeScript', 'javascript', 'typescript'."
---

# JavaScript/TypeScript 코딩 컨벤션

JavaScript/TypeScript 코드 작성 시 일관된 스타일과 구조를 유지하기 위한 컨벤션 가이드입니다. 이 스킬은 .js/.ts/.jsx/.tsx 파일 읽기/쓰기 시 자동으로 트리거되며, 규칙 위반 시 자동 수정을 수행합니다.

## 1. 네이밍 규칙

JavaScript/TypeScript 코드에서는 일관된 네이밍 규칙을 적용하여 가독성과 유지보수성을 높입니다.

### 변수 및 함수: camelCase

- 소문자로 시작, 이후 각 단어의 첫 글자를 대문자로 표기
- 예: `userName`, `getUserData()`, `maxRetryCount`
- 금지: `user_name`, `get_user_data`, `UserName`

### 클래스: PascalCase

- 각 단어의 첫 글자를 대문자로 표기
- 예: `UserService`, `DataProcessor`, `ApiClient`
- 금지: `user_service`, `dataProcessor`, `api_client`

### 상수: UPPER_SNAKE_CASE

- 모든 글자를 대문자로, 단어는 언더스코어로 구분
- `const`로 선언된 원시값/불변 객체에 적용
- 예: `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT`, `API_BASE_URL`
- 금지: `maxRetryCount` (일반 변수), `MaxRetryCount`

### Private 멤버: `#` private 필드(ES2022+) 또는 `_` 접두사(레거시)

- ES2022+ 환경: `#` private 필드 사용 (예: `#internalState`, `#validateInput()`)
- 레거시/호환성 필요 시: `_` 접두사 1개 (예: `_cache`, `_validateInput()`)

### 파일명

- 일반 모듈/유틸리티: kebab-case.ts (예: `user-service.ts`, `data-processor.ts`)
- React 컴포넌트: PascalCase.tsx (예: `UserCard.tsx`, `DataTable.tsx`)
- 금지: `UserService.ts` (컴포넌트 외), `data_processor.ts`

### 타입/인터페이스: PascalCase (`I` 접두사 금지)

- 예: `UserProps`, `ApiResponse`, `OrderStatus`
- 금지: `IUserProps`, `IApiResponse` (`I` 접두사 헝가리안 표기법 금지)

### Enum: PascalCase (멤버도 PascalCase)

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

## 2. 타입 시스템 (이중 방식)

TypeScript 또는 JSDoc을 통해 타입 안전성을 확보합니다.

### TypeScript (권장): 전체 타입 어노테이션 필수

모든 함수 인자, 반환값, 변수에 타입 어노테이션을 명시합니다.

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

### JavaScript (폴백): JSDoc 타입 주석으로 동등한 타입 안전성 확보

TypeScript를 사용할 수 없는 환경에서는 JSDoc으로 타입 안전성을 보장합니다.

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

## 3. OOP/설계 규칙

### 기본 원칙

1. **클래스 기반 설계를 기본으로**: 비즈니스 로직, 상태 관리, 복잡한 연산은 클래스로 캡슐화
2. **단순 유틸리티 함수는 허용**: 순수 함수, 변환/계산 함수는 모듈 레벨 함수 가능
3. **React 프로젝트**: 함수 컴포넌트 + 훅 패턴 우선 (클래스 컴포넌트 지양)

### SOLID 원칙 준수 권장

- **S (Single Responsibility)**: 클래스/함수는 하나의 책임만 담당
- **O (Open/Closed)**: 확장에 열려있고 수정에 닫혀있음
- **L (Liskov Substitution)**: 하위 타입은 상위 타입으로 대체 가능
- **I (Interface Segregation)**: 클라이언트별 특화된 인터페이스
- **D (Dependency Inversion)**: 구체적인 구현이 아닌 추상화에 의존

### 추상 클래스 및 인터페이스 활용

TypeScript의 `abstract class`와 `interface`를 적극 활용합니다.

```typescript
interface DataRepository<T> {
  findById(id: number): Promise<T | undefined>;
  save(entity: T): Promise<void>;
  delete(id: number): Promise<void>;
}

abstract class BaseRepository<T extends { id: number }> implements DataRepository<T> {
  protected items: T[] = [];

  abstract findById(id: number): Promise<T | undefined>;
  abstract save(entity: T): Promise<void>;

  async delete(id: number): Promise<void> {
    this.items = this.items.filter((item) => item.id !== id);
  }
}

class UserRepository extends BaseRepository<User> {
  async findById(id: number): Promise<User | undefined> {
    return this.items.find((user) => user.id === id);
  }

  async save(user: User): Promise<void> {
    const index = this.items.findIndex((u) => u.id === user.id);
    if (index >= 0) {
      this.items[index] = user;
    } else {
      this.items.push(user);
    }
  }
}
```

### 상속보다 컴포지션 우선

```typescript
// 나쁜 예 (깊은 상속)
class BasicLogger {
  log(msg: string): void {}
}

class FileLogger extends BasicLogger {}

class EncryptedFileLogger extends FileLogger {}

// 좋은 예 (컴포지션)
interface Writer {
  write(content: string): void;
}

interface Formatter {
  format(msg: string): string;
}

class Logger {
  constructor(
    private readonly writer: Writer,
    private readonly formatter: Formatter
  ) {}

  log(msg: string): void {
    const formatted = this.formatter.format(msg);
    this.writer.write(formatted);
  }
}
```

### React 프로젝트: 함수 컴포넌트 + 훅 패턴

```typescript
// 좋은 예 (함수 컴포넌트 + 훅)
interface UserCardProps {
  userId: number;
  onSelect: (user: User) => void;
}

function UserCard({ userId, onSelect }: UserCardProps): JSX.Element {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    fetchUser(userId).then((data) => {
      setUser(data);
      setLoading(false);
    });
  }, [userId]);

  if (loading) return <div>로딩 중...</div>;
  if (!user) return <div>사용자를 찾을 수 없습니다</div>;

  return <div onClick={() => onSelect(user)}>{user.name}</div>;
}

// 나쁜 예 (클래스 컴포넌트 - 신규 개발 지양)
class UserCardClass extends React.Component<UserCardProps> {
  render() {
    return <div />;
  }
}
```

### 실제 예시 (결제 처리)

```typescript
interface PaymentProcessor {
  process(amount: number): Promise<boolean>;
}

class CreditCardProcessor implements PaymentProcessor {
  constructor(private readonly gatewayUrl: string) {}

  async process(amount: number): Promise<boolean> {
    if (amount <= 0) return false;
    // 게이트웨이 호출 로직
    return true;
  }
}

class Order {
  private _status: string = "pending";
  totalAmount: number = 0;

  constructor(
    readonly orderId: string,
    private readonly processor: PaymentProcessor
  ) {}

  async checkout(amount: number): Promise<boolean> {
    if (await this.processor.process(amount)) {
      this.totalAmount = amount;
      this._status = "completed";
      return true;
    }
    return false;
  }

  get status(): string {
    return this._status;
  }
}
```

## 4. 주석/문서화 규칙 (TSDoc/JSDoc 스타일)

명확하고 유지보수하기 쉬운 문서화를 위해 TSDoc/JSDoc 스타일을 사용합니다.

### 파일 최상단 모듈 설명 (필수)

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

### Public 함수/메서드: TSDoc 필수

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

### 클래스 TSDoc

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

### 인라인 주석: 복잡한 로직/비즈니스 규칙에 필수

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

### Private 함수/메서드: 최소 한 줄 `/** ... */` 권장

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

### TSDoc/JSDoc 완전 예시

```typescript
/**
 * @module data-transformer
 *
 * 데이터 변환 모듈.
 *
 * CSV, JSON 등 다양한 형식의 데이터를 읽고 변환합니다.
 */

/**
 * 파일에서 데이터를 읽고 변환합니다.
 *
 * 입력 파일을 지정된 형식으로 읽어 객체 배열로 변환합니다.
 * 선택적으로 특정 키로 필터링할 수 있습니다.
 *
 * @param inputFile - 입력 파일 경로
 * @param formatType - 파일 형식 ('csv' | 'json')
 * @param filterKey - 필터링할 키 (선택사항)
 * @returns 변환된 데이터 배열. filterKey가 지정되면 해당 키를 가진 항목만 반환.
 * @throws {Error} 입력 파일이 없는 경우
 * @throws {TypeError} 지정된 형식이 지원되지 않는 경우
 * @example
 * ```typescript
 * const data = await transformData("users.json", "json", "status");
 * console.log(data.length); // 100
 * ```
 */
async function transformData(
  inputFile: string,
  formatType: "csv" | "json",
  filterKey?: string
): Promise<Record<string, unknown>[]> {
  const fs = await import("fs/promises");
  const content = await fs.readFile(inputFile, "utf-8");

  let data: Record<string, unknown>[];

  if (formatType === "json") {
    data = JSON.parse(content) as Record<string, unknown>[];
  } else if (formatType === "csv") {
    data = parseCsv(content);
  } else {
    throw new TypeError(`지원되지 않는 형식: ${formatType}`);
  }

  // 필터링
  if (filterKey) {
    data = data.filter((item) => filterKey in item);
  }

  return data;
}
```

## 5. 위반 시 자동 수정 동작 + ESLint/Prettier 연동

.js/.ts/.jsx/.tsx 파일 읽기/쓰기 시 컨벤션 위반을 감지하고 자동으로 수정합니다.

### 자동 수정 동작 목록

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
- **수정**: 자동 변환 (변수/함수 → camelCase, 클래스/타입 → PascalCase, 상수 → UPPER_SNAKE_CASE)
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

### ESLint 연동

프로젝트 루트에 `eslint.config.js`, `eslint.config.mjs`, `.eslintrc.js`, `.eslintrc.json`, `.eslintrc.yml` 중 하나가 존재하면:

- ESLint 규칙과 충돌하는 수정은 ESLint 설정을 우선 적용
- 자동 수정 후 `npx eslint --fix` 실행 권고
- `no-any`, `explicit-function-return-type`, `naming-convention` 규칙 확인

### Prettier 연동

프로젝트 루트에 `.prettierrc`, `.prettierrc.json`, `.prettierrc.js`, `prettier.config.js` 중 하나가 존재하면:

- 들여쓰기, 따옴표 스타일, 세미콜론 등 포맷팅은 Prettier 설정을 우선 적용
- 자동 수정 후 `npx prettier --write` 실행 권고

### 자동 수정 예외 사항

- **외부 라이브러리**: 서드파티 라이브러리 함수의 시그니처는 수정하지 않음
- **테스트 코드**: `*.test.ts`, `*.spec.ts` 파일의 describe/it 블록 네이밍은 유연하게 허용
- **생성 코드**: 자동 생성된 파일(예: `*.generated.ts`, `*.d.ts`)은 수정하지 않음

### 자동 수정 수준 제어

.js/.ts/.jsx/.tsx 파일 작성 시 자동 수정 수준을 다음과 같이 적용:

1. **필수 수정** (항상 수행):
   - 네이밍 컨벤션 위반
   - 타입 어노테이션 누락 (TypeScript, 명확한 경우)
   - `any` 타입 사용

2. **권장 수정** (경고 후 수행):
   - TSDoc/JSDoc 문서화 누락
   - Private 멤버 접두사(`_`) 추가
   - 모듈 설명 주석 추가

3. **검토 필수** (사용자 확인 후):
   - 함수/클래스 구조 리팩토링
   - 클래스 컴포넌트 → 함수 컴포넌트 전환
   - `interface` ↔ `type` 변환

---

**마지막 갱신**: 2026-03-08
