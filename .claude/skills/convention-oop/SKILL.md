---
name: convention-oop
description: "Provides language-agnostic OOP principles and patterns guide covering SOLID, GRASP, GoF design patterns, and DDD tactical patterns with Python/JS/TS code examples. Use when writing or reviewing object-oriented code, applying design patterns, modeling domain logic with Entity/Value Object/Aggregate/Repository patterns, or handling Domain Events."
license: "Apache-2.0"
user-invocable: false
---

# OOP Conventions

언어 무관 객체지향 프로그래밍 원칙 가이드. SOLID, GRASP, GoF 디자인 패턴, DDD 전술 패턴을 Python과 JS/TS 코드 예시로 제공한다.

## 1. SOLID Principles

### 1.1 SRP - Single Responsibility Principle

클래스는 변경의 이유가 단 하나여야 한다. 하나의 책임만 캡슐화한다.

**Python - Bad:**

```python
class UserManager:
    def create_user(self, name: str, email: str) -> dict:
        # 사용자 생성 + 이메일 전송 + 로깅 = 3가지 책임
        user = {"name": name, "email": email}
        self._send_email(email, "Welcome!")
        self._log(f"User created: {name}")
        return user

    def _send_email(self, to: str, body: str) -> None: ...
    def _log(self, msg: str) -> None: ...
```

**Python - Good:**

```python
class UserService:
    def __init__(self, notifier: "Notifier", logger: "Logger"):
        self.notifier = notifier
        self.logger = logger

    def create_user(self, name: str, email: str) -> dict:
        user = {"name": name, "email": email}
        self.notifier.send(email, "Welcome!")
        self.logger.info(f"User created: {name}")
        return user
```

**TypeScript - Bad:**

```typescript
class UserManager {
  createUser(name: string, email: string): User {
    const user = { name, email };
    this.sendEmail(email, "Welcome!");
    this.log(`User created: ${name}`);
    return user;
  }
  private sendEmail(to: string, body: string): void { /* ... */ }
  private log(msg: string): void { /* ... */ }
}
```

**TypeScript - Good:**

```typescript
class UserService {
  constructor(
    private readonly notifier: Notifier,
    private readonly logger: Logger
  ) {}

  createUser(name: string, email: string): User {
    const user = { name, email };
    this.notifier.send(email, "Welcome!");
    this.logger.info(`User created: ${name}`);
    return user;
  }
}
```

### 1.2 OCP - Open/Closed Principle

확장에 열려 있고 수정에 닫혀 있어야 한다. 새 기능 추가 시 기존 코드를 변경하지 않는다.

**Python - Bad:**

```python
class DiscountCalculator:
    def calculate(self, customer_type: str, amount: float) -> float:
        if customer_type == "regular":
            return amount * 0.95
        elif customer_type == "premium":
            return amount * 0.90
        # 새 타입 추가 시 이 메서드를 수정해야 함
        return amount
```

**Python - Good:**

```python
from abc import ABC, abstractmethod

class DiscountStrategy(ABC):
    @abstractmethod
    def apply(self, amount: float) -> float: ...

class RegularDiscount(DiscountStrategy):
    def apply(self, amount: float) -> float:
        return amount * 0.95

class PremiumDiscount(DiscountStrategy):
    def apply(self, amount: float) -> float:
        return amount * 0.90

class DiscountCalculator:
    def calculate(self, strategy: DiscountStrategy, amount: float) -> float:
        return strategy.apply(amount)
```

**TypeScript - Bad:**

```typescript
class DiscountCalculator {
  calculate(customerType: string, amount: number): number {
    if (customerType === "regular") return amount * 0.95;
    if (customerType === "premium") return amount * 0.90;
    return amount;
  }
}
```

**TypeScript - Good:**

```typescript
interface DiscountStrategy {
  apply(amount: number): number;
}

class RegularDiscount implements DiscountStrategy {
  apply(amount: number): number { return amount * 0.95; }
}

class PremiumDiscount implements DiscountStrategy {
  apply(amount: number): number { return amount * 0.90; }
}

class DiscountCalculator {
  calculate(strategy: DiscountStrategy, amount: number): number {
    return strategy.apply(amount);
  }
}
```

### 1.3 LSP - Liskov Substitution Principle

하위 타입은 상위 타입으로 대체 가능해야 한다. 서브클래스가 부모 클래스의 계약을 깨지 않아야 한다.

**Python - Bad:**

```python
class Bird:
    def fly(self) -> str:
        return "flying"

class Penguin(Bird):
    def fly(self) -> str:
        raise NotImplementedError("Penguins can't fly")  # LSP 위반
```

**Python - Good:**

```python
from abc import ABC, abstractmethod

class Bird(ABC):
    @abstractmethod
    def move(self) -> str: ...

class Sparrow(Bird):
    def move(self) -> str:
        return "flying"

class Penguin(Bird):
    def move(self) -> str:
        return "swimming"
```

**TypeScript - Bad:**

```typescript
class Bird {
  fly(): string { return "flying"; }
}

class Penguin extends Bird {
  fly(): string { throw new Error("Penguins can't fly"); } // LSP 위반
}
```

**TypeScript - Good:**

```typescript
abstract class Bird {
  abstract move(): string;
}

class Sparrow extends Bird {
  move(): string { return "flying"; }
}

class Penguin extends Bird {
  move(): string { return "swimming"; }
}
```

### 1.4 ISP - Interface Segregation Principle

클라이언트는 사용하지 않는 메서드에 의존하지 않아야 한다. 범용 인터페이스보다 특화된 인터페이스를 선호한다.

**Python - Bad:**

```python
from abc import ABC, abstractmethod

class Worker(ABC):
    @abstractmethod
    def work(self) -> None: ...
    @abstractmethod
    def eat(self) -> None: ...
    @abstractmethod
    def sleep(self) -> None: ...

class Robot(Worker):
    def work(self) -> None: ...
    def eat(self) -> None: pass   # 불필요
    def sleep(self) -> None: pass  # 불필요
```

**Python - Good:**

```python
from abc import ABC, abstractmethod

class Workable(ABC):
    @abstractmethod
    def work(self) -> None: ...

class Feedable(ABC):
    @abstractmethod
    def eat(self) -> None: ...

class Human(Workable, Feedable):
    def work(self) -> None: ...
    def eat(self) -> None: ...

class Robot(Workable):
    def work(self) -> None: ...
```

**TypeScript - Bad:**

```typescript
interface Worker {
  work(): void;
  eat(): void;
  sleep(): void;
}

class Robot implements Worker {
  work(): void { /* ... */ }
  eat(): void { /* not applicable */ }
  sleep(): void { /* not applicable */ }
}
```

**TypeScript - Good:**

```typescript
interface Workable {
  work(): void;
}

interface Feedable {
  eat(): void;
}

class Human implements Workable, Feedable {
  work(): void { /* ... */ }
  eat(): void { /* ... */ }
}

class Robot implements Workable {
  work(): void { /* ... */ }
}
```

### 1.5 DIP - Dependency Inversion Principle

고수준 모듈은 저수준 모듈에 의존하지 않는다. 둘 다 추상화에 의존한다.

**Python - Bad:**

```python
class MySQLDatabase:
    def query(self, sql: str) -> list:
        return []

class UserRepository:
    def __init__(self):
        self.db = MySQLDatabase()  # 구체 구현에 직접 의존

    def find_all(self) -> list:
        return self.db.query("SELECT * FROM users")
```

**Python - Good:**

```python
from abc import ABC, abstractmethod

class Database(ABC):
    @abstractmethod
    def query(self, sql: str) -> list: ...

class MySQLDatabase(Database):
    def query(self, sql: str) -> list:
        return []

class UserRepository:
    def __init__(self, db: Database):  # 추상화에 의존
        self.db = db

    def find_all(self) -> list:
        return self.db.query("SELECT * FROM users")
```

**TypeScript - Bad:**

```typescript
class MySQLDatabase {
  query(sql: string): unknown[] { return []; }
}

class UserRepository {
  private db = new MySQLDatabase(); // 구체 구현에 직접 의존
  findAll(): unknown[] { return this.db.query("SELECT * FROM users"); }
}
```

**TypeScript - Good:**

```typescript
interface Database {
  query(sql: string): unknown[];
}

class MySQLDatabase implements Database {
  query(sql: string): unknown[] { return []; }
}

class UserRepository {
  constructor(private readonly db: Database) {} // 추상화에 의존
  findAll(): unknown[] { return this.db.query("SELECT * FROM users"); }
}
```

## 2. GRASP Patterns

### 2.1 Information Expert

책임을 수행하는 데 필요한 정보를 가장 많이 보유한 클래스에 책임을 할당한다.

**Python:**

```python
class Order:
    def __init__(self, items: list["OrderItem"]):
        self.items = items

    def total(self) -> float:
        # Order가 items를 알고 있으므로 total 계산 책임은 Order에
        return sum(item.subtotal() for item in self.items)

class OrderItem:
    def __init__(self, price: float, quantity: int):
        self.price = price
        self.quantity = quantity

    def subtotal(self) -> float:
        return self.price * self.quantity
```

**TypeScript:**

```typescript
class Order {
  constructor(private readonly items: OrderItem[]) {}

  total(): number {
    return this.items.reduce((sum, item) => sum + item.subtotal(), 0);
  }
}

class OrderItem {
  constructor(
    private readonly price: number,
    private readonly quantity: number
  ) {}

  subtotal(): number { return this.price * this.quantity; }
}
```

### 2.2 Creator

B가 A를 포함하거나 밀접하게 사용한다면, B가 A를 생성하는 책임을 진다.

**Python:**

```python
class Order:
    def __init__(self):
        self.items: list[OrderItem] = []

    def add_item(self, product: str, price: float, qty: int) -> None:
        # Order가 OrderItem을 포함하므로 생성 책임을 가짐
        self.items.append(OrderItem(product, price, qty))
```

**TypeScript:**

```typescript
class Order {
  private items: OrderItem[] = [];

  addItem(product: string, price: number, qty: number): void {
    this.items.push(new OrderItem(product, price, qty));
  }
}
```

### 2.3 Controller

UI 계층과 도메인 계층 사이의 시스템 이벤트를 처리하는 첫 번째 객체를 지정한다.

**Python:**

```python
class OrderController:
    def __init__(self, order_service: "OrderService"):
        self.order_service = order_service

    def place_order(self, request: dict) -> dict:
        # 시스템 이벤트를 받아 도메인 서비스에 위임
        order_id = self.order_service.create_order(
            customer_id=request["customer_id"],
            items=request["items"],
        )
        return {"order_id": order_id, "status": "created"}
```

**TypeScript:**

```typescript
class OrderController {
  constructor(private readonly orderService: OrderService) {}

  placeOrder(request: PlaceOrderRequest): OrderResponse {
    const orderId = this.orderService.createOrder(
      request.customerId,
      request.items
    );
    return { orderId, status: "created" };
  }
}
```

### 2.4 Low Coupling

클래스 간 의존성을 최소화한다. 변경의 영향 범위를 줄인다.

**Python - Bad:**

```python
class OrderService:
    def __init__(self):
        self.email = EmailService()      # 직접 생성
        self.inventory = InventoryDB()   # 직접 생성
        self.payment = StripeClient()    # 직접 생성
```

**Python - Good:**

```python
class OrderService:
    def __init__(
        self,
        notifier: "Notifier",           # 추상화에 의존
        inventory: "InventoryPort",
        payment: "PaymentPort",
    ):
        self.notifier = notifier
        self.inventory = inventory
        self.payment = payment
```

**TypeScript - Good:**

```typescript
class OrderService {
  constructor(
    private readonly notifier: Notifier,
    private readonly inventory: InventoryPort,
    private readonly payment: PaymentPort
  ) {}
}
```

### 2.5 High Cohesion

클래스 내부의 메서드들이 밀접하게 관련된 책임만 수행한다.

**Python - Bad:**

```python
class UserService:
    def create_user(self, data: dict) -> None: ...
    def generate_report(self, start: str) -> str: ...  # 관련 없는 책임
    def send_notification(self, msg: str) -> None: ...  # 관련 없는 책임
```

**Python - Good:**

```python
class UserService:
    def create_user(self, data: dict) -> None: ...
    def find_user(self, user_id: int) -> dict: ...
    def update_user(self, user_id: int, data: dict) -> None: ...
```

### 2.6 Polymorphism

타입에 따라 행동이 달라지는 경우, 조건문 대신 다형성(상속/인터페이스)을 사용한다.

**Python - Bad:**

```python
def calculate_area(shape: dict) -> float:
    if shape["type"] == "circle":
        return 3.14 * shape["radius"] ** 2
    elif shape["type"] == "rectangle":
        return shape["width"] * shape["height"]
```

**Python - Good:**

```python
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self) -> float: ...

class Circle(Shape):
    def __init__(self, radius: float):
        self.radius = radius
    def area(self) -> float:
        return 3.14 * self.radius ** 2

class Rectangle(Shape):
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height
    def area(self) -> float:
        return self.width * self.height
```

**TypeScript - Good:**

```typescript
interface Shape {
  area(): number;
}

class Circle implements Shape {
  constructor(private readonly radius: number) {}
  area(): number { return Math.PI * this.radius ** 2; }
}

class Rectangle implements Shape {
  constructor(
    private readonly width: number,
    private readonly height: number
  ) {}
  area(): number { return this.width * this.height; }
}
```

### 2.7 Pure Fabrication

도메인 모델에 자연스럽게 맞지 않지만 높은 응집도와 낮은 결합도를 달성하기 위한 인공 클래스를 만든다.

**Python:**

```python
class PersistenceService:
    """도메인 모델에는 없지만 기술적 책임 분리를 위한 인공 클래스"""
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    def save(self, entity: dict) -> None: ...
    def load(self, entity_id: str) -> dict: ...
```

**TypeScript:**

```typescript
class PersistenceService {
  constructor(private readonly connectionString: string) {}
  save(entity: Record<string, unknown>): void { /* ... */ }
  load(entityId: string): Record<string, unknown> { /* ... */ }
}
```

### 2.8 Indirection

두 구성 요소 사이에 중재자를 두어 직접 결합을 피한다.

**Python:**

```python
class PaymentGateway:
    """StripeClient와 OrderService 사이의 중재자"""
    def __init__(self, client: "StripeClient"):
        self.client = client

    def charge(self, amount: float) -> bool:
        return self.client.create_charge(int(amount * 100))
```

**TypeScript:**

```typescript
class PaymentGateway {
  constructor(private readonly client: StripeClient) {}
  charge(amount: number): boolean {
    return this.client.createCharge(Math.round(amount * 100));
  }
}
```

### 2.9 Protected Variations

변경이 예상되는 지점을 인터페이스 뒤에 숨겨 안정적인 인터페이스로 보호한다.

**Python:**

```python
from abc import ABC, abstractmethod

class TaxCalculator(ABC):
    """세금 계산 로직은 국가별로 자주 변경됨 -> 인터페이스로 보호"""
    @abstractmethod
    def calculate(self, amount: float) -> float: ...

class KoreaTax(TaxCalculator):
    def calculate(self, amount: float) -> float:
        return amount * 0.1

class USTax(TaxCalculator):
    def calculate(self, amount: float) -> float:
        return amount * 0.08
```

**TypeScript:**

```typescript
interface TaxCalculator {
  calculate(amount: number): number;
}

class KoreaTax implements TaxCalculator {
  calculate(amount: number): number { return amount * 0.1; }
}

class USTax implements TaxCalculator {
  calculate(amount: number): number { return amount * 0.08; }
}
```

## 3. Language-Specific OOP Conventions

언어별로 OOP를 구현할 때 따르는 관용적 패턴.

### 3.1 Python OOP Conventions

**추상 클래스(ABC)를 인터페이스로 활용:**

```python
from abc import ABC, abstractmethod

class DataRepository(ABC):
    @abstractmethod
    def get(self, key: str) -> dict: ...

    @abstractmethod
    def save(self, key: str, data: dict) -> None: ...
```

**@dataclass로 데이터 보관 클래스 작성:**

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    id: int
    name: str
    email: str
    phone: Optional[str] = None
```

**상속보다 컴포지션 우선:**

```python
class Logger:
    def __init__(self, writer: "Writer", formatter: "Formatter"):
        self.writer = writer
        self.formatter = formatter

    def log(self, msg: str) -> None:
        formatted = self.formatter.format(msg)
        self.writer.write(formatted)
```

**메서드 데코레이터 활용:**

```python
class UserService:
    class_variable: str = "shared"

    def __init__(self, name: str):
        self.name = name

    @staticmethod
    def validate_email(email: str) -> bool:
        return "@" in email

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "UserService":
        return cls(data["name"])

    @property
    def display_name(self) -> str:
        return self.name.upper()
```

### 3.2 JavaScript/TypeScript OOP Conventions

**abstract class와 interface 활용:**

```typescript
interface DataRepository<T> {
  findById(id: number): Promise<T | undefined>;
  save(entity: T): Promise<void>;
  delete(id: number): Promise<void>;
}

abstract class BaseRepository<T extends { id: number }>
  implements DataRepository<T> {
  protected items: T[] = [];
  abstract findById(id: number): Promise<T | undefined>;
  abstract save(entity: T): Promise<void>;
  async delete(id: number): Promise<void> {
    this.items = this.items.filter((item) => item.id !== id);
  }
}
```

**상속보다 컴포지션 우선:**

```typescript
interface Writer { write(content: string): void; }
interface Formatter { format(msg: string): string; }

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

**React 프로젝트 - 함수 컴포넌트 + 훅 패턴:**

```typescript
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

  if (loading) return <div>Loading...</div>;
  if (!user) return <div>Not found</div>;
  return <div onClick={() => onSelect(user)}>{user.name}</div>;
}
```

## 4. GoF Design Patterns - Quick Reference

### Creational Patterns (5)

| Pattern | Intent | When to Use |
|---------|--------|-------------|
| Factory Method | 서브클래스에 생성 위임 | 구체 타입을 미리 알 수 없을 때 |
| Abstract Factory | 관련 객체 제품군 일괄 생성 | 제품군 호환성 보장이 필요할 때 |
| Builder | 복잡한 객체 단계별 조립 | 생성자 파라미터가 4개 이상일 때 |
| Prototype | 기존 객체 복제로 생성 | 객체 생성 비용이 높을 때 |
| Singleton | 전역 단일 인스턴스 보장 | 공유 리소스 접근 제어 시 |

### Structural Patterns (7)

| Pattern | Intent | When to Use |
|---------|--------|-------------|
| Adapter | 호환되지 않는 인터페이스 연결 | 레거시/서드파티 통합 시 |
| Bridge | 추상화와 구현 독립 변경 | 두 차원의 변화가 독립적일 때 |
| Composite | 트리 구조 부분-전체 표현 | 재귀적 계층 구조 필요 시 |
| Decorator | 런타임 기능 동적 추가 | 서브클래싱 없이 기능 확장 시 |
| Facade | 복잡한 서브시스템 단순화 | 서브시스템 진입점 필요 시 |
| Flyweight | 대량 유사 객체 메모리 최적화 | 수천 개 유사 객체 관리 시 |
| Proxy | 객체 접근 제어 | 지연 로딩/캐싱/권한 제어 시 |

### Behavioral Patterns (11)

| Pattern | Intent | When to Use |
|---------|--------|-------------|
| Chain of Responsibility | 요청을 핸들러 체인으로 전달 | 처리자를 런타임에 결정할 때 |
| Command | 작업을 객체로 캡슐화 | Undo/Redo, 큐잉, 로깅 시 |
| Interpreter | 문법 규칙 해석 | DSL, 수식 파서 구현 시 |
| Iterator | 컬렉션 내부 구조 은닉하며 순회 | 커스텀 순회 로직 필요 시 |
| Mediator | 객체 간 통신 중앙 집중화 | N:N 통신을 1:N으로 단순화 시 |
| Memento | 캡슐화 유지하며 상태 저장/복원 | 스냅샷, 체크포인트 시 |
| Observer | 이벤트 기반 알림 구독 | 상태 변경을 여러 객체에 통지 시 |
| State | 상태별 객체 동작 변경 | 조건문 기반 상태 분기 제거 시 |
| Strategy | 런타임에 알고리즘 교체 | 동일 문제에 여러 해법 존재 시 |
| Template Method | 알고리즘 골격 유지, 단계 재정의 | 공통 흐름 + 가변 단계 시 |
| Visitor | 클래스 수정 없이 새 연산 추가 | 타입별 다른 연산 필요 시 |

Code examples with Python/JS: [references/gof-creational-structural.md](references/gof-creational-structural.md), [references/gof-behavioral.md](references/gof-behavioral.md)

## 5. DDD Tactical Patterns - Quick Reference

| Pattern | Intent | When to Use |
|---------|--------|-------------|
| Entity | 고유 식별자로 동일성 판단 | 생명주기가 있는 도메인 객체 |
| Value Object | 속성 값으로 동등성 판단, 불변 | 날짜, 금액, 주소 등 값 타입 |
| Aggregate | 불변 조건을 보호하는 일관성 경계 | 트랜잭션 단위로 묶이는 객체 군 |
| Repository | Aggregate의 영속성 추상화 | 데이터 접근 계층 분리 시 |
| Domain Service | 특정 Entity에 속하지 않는 도메인 로직 | 여러 Aggregate 간 조율 시 |
| Domain Event | 도메인에서 발생한 사건 표현 | Aggregate 간 비동기 통신 시 |
| Saga | 분산 트랜잭션의 보상 기반 관리 | 다수 서비스 걸친 비즈니스 프로세스 |

Code examples with Python/JS: [references/ddd-tactical.md](references/ddd-tactical.md)

## 6. When to Load References

- **OOP 원칙(SOLID, GRASP) 확인만 필요한 경우**: 이 SKILL.md로 충분
- **GoF 패턴의 Python/JS 코드 예시가 필요한 경우**:
  - 생성 + 구조 패턴 --> `references/gof-creational-structural.md`
  - 행위 패턴 --> `references/gof-behavioral.md`
- **DDD 전술 패턴 코드 예시가 필요한 경우**: `references/ddd-tactical.md`
- **GoF 패턴의 Mermaid 다이어그램이 필요한 경우**: `design-patterns` 스킬의 references 파일 참조
