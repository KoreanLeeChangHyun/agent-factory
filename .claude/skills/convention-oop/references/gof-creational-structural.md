# GoF Creational & Structural Patterns

GoF 생성 패턴 5개 + 구조 패턴 7개의 Python/JS·TS 코드 예시 참조 문서.

## Table of Contents

### Creational Patterns
1. [Factory Method](#1-factory-method)
2. [Abstract Factory](#2-abstract-factory)
3. [Builder](#3-builder)
4. [Prototype](#4-prototype)
5. [Singleton](#5-singleton)

### Structural Patterns
6. [Adapter](#6-adapter)
7. [Bridge](#7-bridge)
8. [Composite](#8-composite)
9. [Decorator](#9-decorator)
10. [Facade](#10-facade)
11. [Flyweight](#11-flyweight)
12. [Proxy](#12-proxy)
13. [비교 요약](#비교-요약)

---

## Creational Patterns (생성 패턴)

---

### 1. Factory Method

**의도**: 객체 생성 인터페이스를 상위 클래스에 정의하되, 구체 클래스 결정은 서브클래스에 위임한다.

**해결하는 문제**: `new` 연산자의 직접 사용이 분산되어 OCP 위반. 새 타입 추가 시 광범위한 수정 필요.

**사용 시기**: 생성할 객체의 타입을 서브클래스에서 결정해야 할 때. 프레임워크가 확장 가능한 생성 인터페이스를 제공할 때.

**Python:**

```python
from abc import ABC, abstractmethod

class Notification(ABC):
    @abstractmethod
    def send(self, message: str) -> None: ...

class EmailNotification(Notification):
    def send(self, message: str) -> None:
        print(f"Email: {message}")

class SMSNotification(Notification):
    def send(self, message: str) -> None:
        print(f"SMS: {message}")

class NotificationService(ABC):
    @abstractmethod
    def create_notification(self) -> Notification: ...

    def notify(self, message: str) -> None:
        notification = self.create_notification()
        notification.send(message)

class EmailService(NotificationService):
    def create_notification(self) -> Notification:
        return EmailNotification()

class SMSService(NotificationService):
    def create_notification(self) -> Notification:
        return SMSNotification()
```

**TypeScript:**

```typescript
interface Notification {
  send(message: string): void;
}

class EmailNotification implements Notification {
  send(message: string) { console.log(`Email: ${message}`); }
}

class SMSNotification implements Notification {
  send(message: string) { console.log(`SMS: ${message}`); }
}

abstract class NotificationService {
  abstract createNotification(): Notification;

  notify(message: string): void {
    const notification = this.createNotification();
    notification.send(message);
  }
}

class EmailService extends NotificationService {
  createNotification(): Notification { return new EmailNotification(); }
}

class SMSService extends NotificationService {
  createNotification(): Notification { return new SMSNotification(); }
}
```

**관련 패턴**: Abstract Factory (진화), Template Method (내부 호출), Prototype (대안)

---

### 2. Abstract Factory

**의도**: 관련 객체 제품군을 구체 클래스 명시 없이 생성하는 인터페이스를 제공한다.

**해결하는 문제**: 제품군 내 불일치 조합 방지. 새 변형(제품군) 추가 시 기존 코드 수정 없이 확장.

**사용 시기**: 여러 관련 객체를 일관된 제품군으로 생성해야 할 때. 크로스 플랫폼, 테마, 프로바이더 교체 시.

**Python:**

```python
from abc import ABC, abstractmethod

class Button(ABC):
    @abstractmethod
    def render(self) -> str: ...

class Checkbox(ABC):
    @abstractmethod
    def render(self) -> str: ...

class WindowsButton(Button):
    def render(self) -> str:
        return "<win-button/>"

class WindowsCheckbox(Checkbox):
    def render(self) -> str:
        return "<win-checkbox/>"

class MacButton(Button):
    def render(self) -> str:
        return "<mac-button/>"

class MacCheckbox(Checkbox):
    def render(self) -> str:
        return "<mac-checkbox/>"

class GUIFactory(ABC):
    @abstractmethod
    def create_button(self) -> Button: ...
    @abstractmethod
    def create_checkbox(self) -> Checkbox: ...

class WindowsFactory(GUIFactory):
    def create_button(self) -> Button:
        return WindowsButton()
    def create_checkbox(self) -> Checkbox:
        return WindowsCheckbox()

class MacFactory(GUIFactory):
    def create_button(self) -> Button:
        return MacButton()
    def create_checkbox(self) -> Checkbox:
        return MacCheckbox()

def build_ui(factory: GUIFactory) -> None:
    btn = factory.create_button()
    chk = factory.create_checkbox()
    print(btn.render(), chk.render())
```

**TypeScript:**

```typescript
interface Button { render(): string; }
interface Checkbox { render(): string; }

class WindowsButton implements Button {
  render() { return "<win-button/>"; }
}
class WindowsCheckbox implements Checkbox {
  render() { return "<win-checkbox/>"; }
}
class MacButton implements Button {
  render() { return "<mac-button/>"; }
}
class MacCheckbox implements Checkbox {
  render() { return "<mac-checkbox/>"; }
}

interface GUIFactory {
  createButton(): Button;
  createCheckbox(): Checkbox;
}

class WindowsFactory implements GUIFactory {
  createButton(): Button { return new WindowsButton(); }
  createCheckbox(): Checkbox { return new WindowsCheckbox(); }
}

class MacFactory implements GUIFactory {
  createButton(): Button { return new MacButton(); }
  createCheckbox(): Checkbox { return new MacCheckbox(); }
}

function buildUI(factory: GUIFactory): void {
  const btn = factory.createButton();
  const chk = factory.createCheckbox();
  console.log(btn.render(), chk.render());
}
```

**관련 패턴**: Factory Method (구현 수단), Singleton (팩토리 인스턴스), Facade (대안)

---

### 3. Builder

**의도**: 복잡한 객체의 생성과 표현을 분리하여, 동일 생성 과정으로 다른 표현을 만든다.

**해결하는 문제**: 텔레스코핑 생성자, 서브클래스 폭발, 복잡한 조립 로직.

**사용 시기**: 많은 선택적 매개변수를 가진 객체를 생성할 때. 단계별 조립이 필요할 때.

**Python:**

```python
from dataclasses import dataclass, field
from typing import Self

@dataclass
class HttpRequest:
    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: str | None = None
    timeout: int = 30

class HttpRequestBuilder:
    def __init__(self) -> None:
        self._request = HttpRequest()

    def method(self, method: str) -> Self:
        self._request.method = method
        return self

    def url(self, url: str) -> Self:
        self._request.url = url
        return self

    def header(self, key: str, value: str) -> Self:
        self._request.headers[key] = value
        return self

    def body(self, body: str) -> Self:
        self._request.body = body
        return self

    def timeout(self, seconds: int) -> Self:
        self._request.timeout = seconds
        return self

    def build(self) -> HttpRequest:
        if not self._request.url:
            raise ValueError("URL is required")
        return self._request

# 사용
request = (
    HttpRequestBuilder()
    .method("POST")
    .url("https://api.example.com/users")
    .header("Content-Type", "application/json")
    .body('{"name": "Alice"}')
    .timeout(10)
    .build()
)
```

**TypeScript:**

```typescript
interface HttpRequest {
  method: string;
  url: string;
  headers: Record<string, string>;
  body?: string;
  timeout: number;
}

class HttpRequestBuilder {
  private request: Partial<HttpRequest> = {
    method: "GET",
    headers: {},
    timeout: 30,
  };

  setMethod(method: string): this {
    this.request.method = method;
    return this;
  }

  setUrl(url: string): this {
    this.request.url = url;
    return this;
  }

  addHeader(key: string, value: string): this {
    this.request.headers![key] = value;
    return this;
  }

  setBody(body: string): this {
    this.request.body = body;
    return this;
  }

  setTimeout(seconds: number): this {
    this.request.timeout = seconds;
    return this;
  }

  build(): HttpRequest {
    if (!this.request.url) throw new Error("URL is required");
    return this.request as HttpRequest;
  }
}

// 사용
const request = new HttpRequestBuilder()
  .setMethod("POST")
  .setUrl("https://api.example.com/users")
  .addHeader("Content-Type", "application/json")
  .setBody('{"name": "Alice"}')
  .setTimeout(10)
  .build();
```

**관련 패턴**: Abstract Factory (즉시 vs 단계별), Composite (트리 구성), Bridge (결합)

---

### 4. Prototype

**의도**: 프로토타입 인스턴스를 복제(clone)하여 새 객체를 생성한다.

**해결하는 문제**: private 필드 접근 불가 시 복제, 구체 클래스 의존 제거, 비용이 큰 초기화 반복 방지.

**사용 시기**: 객체 생성 비용이 높고 유사 객체가 반복적으로 필요할 때. 런타임에 동적 타입의 객체를 복제할 때.

**Python:**

```python
import copy
from dataclasses import dataclass, field

@dataclass
class SpreadsheetCell:
    value: str
    formula: str | None
    style: dict[str, str] = field(default_factory=dict)

    def clone(self) -> "SpreadsheetCell":
        return copy.deepcopy(self)

class CellRegistry:
    def __init__(self) -> None:
        self._prototypes: dict[str, SpreadsheetCell] = {}

    def register(self, key: str, cell: SpreadsheetCell) -> None:
        self._prototypes[key] = cell

    def create(self, key: str) -> SpreadsheetCell:
        proto = self._prototypes.get(key)
        if proto is None:
            raise KeyError(f"Prototype '{key}' not found")
        return proto.clone()

# 사용
registry = CellRegistry()
registry.register("header", SpreadsheetCell(
    value="", formula=None, style={"bold": "true", "bg": "#333"}
))
cell = registry.create("header")
cell.value = "제목"
```

**TypeScript:**

```typescript
interface Cloneable<T> {
  clone(): T;
}

class SpreadsheetCell implements Cloneable<SpreadsheetCell> {
  constructor(
    public value: string,
    public formula: string | null,
    public style: Record<string, string> = {},
  ) {}

  clone(): SpreadsheetCell {
    return new SpreadsheetCell(
      this.value,
      this.formula,
      { ...this.style },
    );
  }
}

class CellRegistry {
  private prototypes = new Map<string, SpreadsheetCell>();

  register(key: string, cell: SpreadsheetCell): void {
    this.prototypes.set(key, cell);
  }

  create(key: string): SpreadsheetCell {
    const proto = this.prototypes.get(key);
    if (!proto) throw new Error(`Prototype '${key}' not found`);
    return proto.clone();
  }
}

// 사용
const registry = new CellRegistry();
registry.register("header", new SpreadsheetCell(
  "", null, { bold: "true", bg: "#333" }
));
const cell = registry.create("header");
cell.value = "제목";
```

**관련 패턴**: Factory Method (대안), Memento (상태 복제 활용)

---

### 5. Singleton

**의도**: 클래스 인스턴스를 하나로 보장하고 전역 접근점을 제공한다.

**해결하는 문제**: 공유 리소스(DB 풀, 설정, 로거)의 단일 접근 제어.

**사용 시기**: 전역적으로 단 하나의 인스턴스만 필요할 때. DI 컨테이너의 scope 관리 대상일 때.

**안티패턴 주의**: Singleton은 전역 상태를 도입하여 테스트를 어렵게 만든다. DI 컨테이너가 더 깔끔한 대안이다. 하드웨어 리소스 접근이나 DI 컨테이너 자체에는 여전히 유효하다.

**Python:**

```python
from threading import Lock

class DatabasePool:
    _instance: "DatabasePool | None" = None
    _lock = Lock()

    def __new__(cls) -> "DatabasePool":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._connections: list[object] = []
        return cls._instance

    def get_connection(self) -> object:
        return object()  # placeholder

# Python 모듈 수준 Singleton (더 파이썬다운 방식)
# config.py
class _Config:
    def __init__(self) -> None:
        self.debug = False
        self.db_url = ""

config = _Config()  # 모듈 import 시 단일 인스턴스 생성
```

**TypeScript:**

```typescript
class DatabasePool {
  private static instance: DatabasePool | null = null;
  private connections: object[] = [];

  private constructor() {}

  static getInstance(): DatabasePool {
    if (!DatabasePool.instance) {
      DatabasePool.instance = new DatabasePool();
    }
    return DatabasePool.instance;
  }

  getConnection(): object {
    return {};  // placeholder
  }
}

// 사용
const pool = DatabasePool.getInstance();
```

**관련 패턴**: Facade (Singleton으로 구현), Flyweight (다수 인스턴스 허용과 차이)

---

## Structural Patterns (구조 패턴)

---

### 6. Adapter

**의도**: 호환되지 않는 인터페이스를 변환하여 함께 동작하게 한다.

**해결하는 문제**: 레거시/서드파티 인터페이스가 현재 시스템과 불일치하는 경우.

**사용 시기**: 기존 클래스를 그대로 사용하고 싶지만 인터페이스가 맞지 않을 때. 서드파티 라이브러리 래핑 시.

**Python:**

```python
from abc import ABC, abstractmethod

class PaymentProcessor(ABC):
    @abstractmethod
    def pay(self, amount: float) -> dict[str, str]: ...

# 레거시 서드파티 (수정 불가)
class LegacyPayPal:
    def make_payment(self, usd_cents: int) -> str:
        return f"PayPal paid {usd_cents} cents"

class PayPalAdapter(PaymentProcessor):
    def __init__(self, paypal: LegacyPayPal) -> None:
        self._paypal = paypal

    def pay(self, amount: float) -> dict[str, str]:
        cents = int(amount * 100)
        result = self._paypal.make_payment(cents)
        return {"status": "ok", "message": result}

# 사용
processor: PaymentProcessor = PayPalAdapter(LegacyPayPal())
processor.pay(49.99)
```

**TypeScript:**

```typescript
interface PaymentProcessor {
  pay(amount: number): { status: string; message: string };
}

// 레거시 서드파티 (수정 불가)
class LegacyPayPal {
  makePayment(usdCents: number): string {
    return `PayPal paid ${usdCents} cents`;
  }
}

class PayPalAdapter implements PaymentProcessor {
  constructor(private paypal: LegacyPayPal) {}

  pay(amount: number): { status: string; message: string } {
    const cents = Math.round(amount * 100);
    const result = this.paypal.makePayment(cents);
    return { status: "ok", message: result };
  }
}

// 사용
const processor: PaymentProcessor = new PayPalAdapter(new LegacyPayPal());
processor.pay(49.99);
```

**관련 패턴**: Bridge (설계 초기 분리 vs 사후 호환), Decorator (기능 추가 vs 인터페이스 변환), Facade (서브시스템 단순화)

---

### 7. Bridge

**의도**: 추상화(Abstraction)와 구현(Implementation)을 분리하여 독립적으로 변경 가능하게 한다.

**해결하는 문제**: 두 차원(예: 모양 + 색상)의 상속 폭발. 런타임 구현 전환 필요.

**사용 시기**: 추상화와 구현이 독립적으로 확장되어야 할 때. 런타임에 구현을 교체해야 할 때.

**Python:**

```python
from abc import ABC, abstractmethod

class Renderer(ABC):
    @abstractmethod
    def render_circle(self, x: float, y: float, radius: float) -> str: ...

class SVGRenderer(Renderer):
    def render_circle(self, x: float, y: float, radius: float) -> str:
        return f'<circle cx="{x}" cy="{y}" r="{radius}"/>'

class CanvasRenderer(Renderer):
    def render_circle(self, x: float, y: float, radius: float) -> str:
        return f"ctx.arc({x}, {y}, {radius})"

class Shape(ABC):
    def __init__(self, renderer: Renderer) -> None:
        self._renderer = renderer

    @abstractmethod
    def draw(self) -> str: ...

class Circle(Shape):
    def __init__(self, renderer: Renderer, x: float, y: float, radius: float) -> None:
        super().__init__(renderer)
        self._x, self._y, self._radius = x, y, radius

    def draw(self) -> str:
        return self._renderer.render_circle(self._x, self._y, self._radius)

# 사용: 런타임 구현 교체
circle_svg = Circle(SVGRenderer(), 10, 20, 5)
circle_canvas = Circle(CanvasRenderer(), 10, 20, 5)
```

**TypeScript:**

```typescript
interface Renderer {
  renderCircle(x: number, y: number, radius: number): string;
}

class SVGRenderer implements Renderer {
  renderCircle(x: number, y: number, radius: number): string {
    return `<circle cx="${x}" cy="${y}" r="${radius}"/>`;
  }
}

class CanvasRenderer implements Renderer {
  renderCircle(x: number, y: number, radius: number): string {
    return `ctx.arc(${x}, ${y}, ${radius})`;
  }
}

abstract class Shape {
  constructor(protected renderer: Renderer) {}
  abstract draw(): string;
}

class Circle extends Shape {
  constructor(
    renderer: Renderer,
    private x: number,
    private y: number,
    private radius: number,
  ) {
    super(renderer);
  }

  draw(): string {
    return this.renderer.renderCircle(this.x, this.y, this.radius);
  }
}

// 사용: 런타임 구현 교체
const svgCircle = new Circle(new SVGRenderer(), 10, 20, 5);
const canvasCircle = new Circle(new CanvasRenderer(), 10, 20, 5);
```

**관련 패턴**: Adapter (사후 호환 vs 초기 분리), Abstract Factory (구현 객체 생성), Strategy (유사 구조, 행위 vs 구조)

---

### 8. Composite

**의도**: 트리 구조로 부분-전체 계층을 표현하여 개별/복합 객체를 균일하게 처리한다.

**해결하는 문제**: 재귀적 합성 표현. 개별 객체와 복합 객체를 동일하게 다루어야 하는 경우.

**사용 시기**: 파일 시스템, GUI 위젯 트리, 조직도, 메뉴 시스템 등 트리 구조를 다룰 때.

**Python:**

```python
from abc import ABC, abstractmethod

class FileSystemNode(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def get_size(self) -> int: ...

    @abstractmethod
    def display(self, indent: int = 0) -> str: ...

class File(FileSystemNode):
    def __init__(self, name: str, size: int) -> None:
        super().__init__(name)
        self._size = size

    def get_size(self) -> int:
        return self._size

    def display(self, indent: int = 0) -> str:
        return f"{'  ' * indent}{self.name} ({self._size}B)"

class Directory(FileSystemNode):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._children: list[FileSystemNode] = []

    def add(self, node: FileSystemNode) -> None:
        self._children.append(node)

    def get_size(self) -> int:
        return sum(child.get_size() for child in self._children)

    def display(self, indent: int = 0) -> str:
        lines = [f"{'  ' * indent}{self.name}/"]
        for child in self._children:
            lines.append(child.display(indent + 1))
        return "\n".join(lines)

# 사용
root = Directory("src")
root.add(File("main.py", 1200))
models = Directory("models")
models.add(File("user.py", 800))
root.add(models)
print(root.get_size())  # 2000
```

**TypeScript:**

```typescript
interface FileSystemNode {
  name: string;
  getSize(): number;
  display(indent?: number): string;
}

class FileNode implements FileSystemNode {
  constructor(public name: string, private size: number) {}

  getSize(): number { return this.size; }

  display(indent = 0): string {
    return `${"  ".repeat(indent)}${this.name} (${this.size}B)`;
  }
}

class DirectoryNode implements FileSystemNode {
  private children: FileSystemNode[] = [];

  constructor(public name: string) {}

  add(node: FileSystemNode): void { this.children.push(node); }

  getSize(): number {
    return this.children.reduce((sum, c) => sum + c.getSize(), 0);
  }

  display(indent = 0): string {
    const lines = [`${"  ".repeat(indent)}${this.name}/`];
    for (const child of this.children) {
      lines.push(child.display(indent + 1));
    }
    return lines.join("\n");
  }
}

// 사용
const root = new DirectoryNode("src");
root.add(new FileNode("main.ts", 1200));
const models = new DirectoryNode("models");
models.add(new FileNode("user.ts", 800));
root.add(models);
console.log(root.getSize()); // 2000
```

**관련 패턴**: Iterator (순회), Visitor (노드별 연산), Flyweight (Leaf 공유), Chain of Responsibility (부모 전파)

---

### 9. Decorator

**의도**: 객체에 추가 책임을 동적으로 부여한다. 서브클래싱의 유연한 대안.

**해결하는 문제**: 상속 없이 런타임 기능 확장. 기능 조합 폭발 방지.

**사용 시기**: 런타임에 기능을 추가/제거할 때. 로깅, 캐싱, 인증, 압축 등을 레이어로 쌓을 때.

**Python:**

```python
from abc import ABC, abstractmethod

class DataSource(ABC):
    @abstractmethod
    def write(self, data: str) -> str: ...
    @abstractmethod
    def read(self) -> str: ...

class FileDataSource(DataSource):
    def __init__(self, filename: str) -> None:
        self._filename = filename
        self._data = ""

    def write(self, data: str) -> str:
        self._data = data
        return f"wrote to {self._filename}"

    def read(self) -> str:
        return self._data

class DataSourceDecorator(DataSource):
    def __init__(self, wrappee: DataSource) -> None:
        self._wrappee = wrappee

    def write(self, data: str) -> str:
        return self._wrappee.write(data)

    def read(self) -> str:
        return self._wrappee.read()

class EncryptionDecorator(DataSourceDecorator):
    def write(self, data: str) -> str:
        encrypted = f"enc({data})"
        return super().write(encrypted)

    def read(self) -> str:
        data = super().read()
        return data.removeprefix("enc(").removesuffix(")")

class CompressionDecorator(DataSourceDecorator):
    def write(self, data: str) -> str:
        compressed = f"zip({data})"
        return super().write(compressed)

    def read(self) -> str:
        data = super().read()
        return data.removeprefix("zip(").removesuffix(")")

# 스택: 압축 -> 암호화 -> 파일
source = CompressionDecorator(EncryptionDecorator(FileDataSource("data.txt")))
source.write("hello")
```

**TypeScript:**

```typescript
interface DataSource {
  write(data: string): string;
  read(): string;
}

class FileDataSource implements DataSource {
  private data = "";
  constructor(private filename: string) {}

  write(data: string): string {
    this.data = data;
    return `wrote to ${this.filename}`;
  }

  read(): string { return this.data; }
}

class DataSourceDecorator implements DataSource {
  constructor(protected wrappee: DataSource) {}
  write(data: string): string { return this.wrappee.write(data); }
  read(): string { return this.wrappee.read(); }
}

class EncryptionDecorator extends DataSourceDecorator {
  write(data: string): string { return super.write(`enc(${data})`); }
  read(): string {
    const data = super.read();
    return data.slice(4, -1); // remove enc(...)
  }
}

class CompressionDecorator extends DataSourceDecorator {
  write(data: string): string { return super.write(`zip(${data})`); }
  read(): string {
    const data = super.read();
    return data.slice(4, -1); // remove zip(...)
  }
}

// 스택: 압축 -> 암호화 -> 파일
const source = new CompressionDecorator(
  new EncryptionDecorator(new FileDataSource("data.txt"))
);
source.write("hello");
```

**관련 패턴**: Adapter (인터페이스 변환 vs 기능 추가), Proxy (접근 제어 vs 기능 추가), Strategy (내부 vs 외부 변경)

---

### 10. Facade

**의도**: 복잡한 서브시스템에 단순화된 통합 인터페이스를 제공한다.

**해결하는 문제**: 다수 클래스를 직접 다루기 어려움. 서브시스템 간 결합도 감소.

**사용 시기**: 복잡한 서브시스템을 하나의 간단한 인터페이스로 제공할 때. 계층 구조에서 각 레이어의 진입점을 정의할 때.

**Python:**

```python
class VideoDecoder:
    def decode(self, filename: str) -> str:
        return f"video_data({filename})"

class AudioDecoder:
    def decode(self, filename: str) -> str:
        return f"audio_data({filename})"

class SubtitleParser:
    def parse(self, filename: str) -> list[str]:
        return [f"subtitle({filename})"]

class Display:
    def render(self, video: str, audio: str, subs: list[str]) -> str:
        return f"playing: {video} + {audio} + {len(subs)} subs"

class MediaPlayerFacade:
    def __init__(self) -> None:
        self._video = VideoDecoder()
        self._audio = AudioDecoder()
        self._subs = SubtitleParser()
        self._display = Display()

    def play(self, filename: str) -> str:
        video = self._video.decode(filename)
        audio = self._audio.decode(filename)
        subs = self._subs.parse(filename)
        return self._display.render(video, audio, subs)

# 사용: 복잡한 서브시스템을 1줄로
player = MediaPlayerFacade()
result = player.play("movie.mp4")
```

**TypeScript:**

```typescript
class VideoDecoder {
  decode(filename: string): string { return `video_data(${filename})`; }
}

class AudioDecoder {
  decode(filename: string): string { return `audio_data(${filename})`; }
}

class SubtitleParser {
  parse(filename: string): string[] { return [`subtitle(${filename})`]; }
}

class Display {
  render(video: string, audio: string, subs: string[]): string {
    return `playing: ${video} + ${audio} + ${subs.length} subs`;
  }
}

class MediaPlayerFacade {
  private video = new VideoDecoder();
  private audio = new AudioDecoder();
  private subs = new SubtitleParser();
  private display = new Display();

  play(filename: string): string {
    const video = this.video.decode(filename);
    const audio = this.audio.decode(filename);
    const subs = this.subs.parse(filename);
    return this.display.render(video, audio, subs);
  }
}

// 사용: 복잡한 서브시스템을 1줄로
const player = new MediaPlayerFacade();
const result = player.play("movie.mp4");
```

**관련 패턴**: Adapter (인터페이스 변환 vs 서브시스템 단순화), Mediator (객체 간 통신 vs 서브시스템 접근), Singleton (Facade를 Singleton으로)

---

### 11. Flyweight

**의도**: 공유를 통해 대량의 세밀한 객체를 효율적으로 지원한다. 메모리 최적화.

**해결하는 문제**: 대량 유사 객체의 과도한 메모리 소비.

**사용 시기**: 수천~수만 개의 유사 객체가 필요하고, 공유 가능한 내재 상태(intrinsic)와 고유한 외재 상태(extrinsic)로 분리 가능할 때.

**핵심 구분**:
- **Intrinsic (내재)**: Flyweight 내부에 저장. 불변. 여러 객체가 공유.
- **Extrinsic (외재)**: Client/Context에서 전달. 가변. 객체마다 고유.

**Python:**

```python
class TreeType:
    """Flyweight: 공유되는 내재 상태 (이름, 색상, 텍스처)"""
    def __init__(self, name: str, color: str, texture: str) -> None:
        self.name = name
        self.color = color
        self.texture = texture

    def draw(self, x: int, y: int) -> str:
        return f"{self.name}({self.color}) at ({x},{y})"

class TreeFactory:
    _cache: dict[str, TreeType] = {}

    @classmethod
    def get(cls, name: str, color: str, texture: str) -> TreeType:
        key = f"{name}-{color}-{texture}"
        if key not in cls._cache:
            cls._cache[key] = TreeType(name, color, texture)
        return cls._cache[key]

class Tree:
    """Context: 외재 상태 (위치)"""
    def __init__(self, x: int, y: int, tree_type: TreeType) -> None:
        self.x = x
        self.y = y
        self.type = tree_type

    def draw(self) -> str:
        return self.type.draw(self.x, self.y)

# 1만 그루의 나무, TreeType은 소수만 생성
forest = [
    Tree(i, i * 2, TreeFactory.get("Oak", "green", "oak.png"))
    for i in range(10000)
]
```

**TypeScript:**

```typescript
class TreeType {
  constructor(
    public readonly name: string,
    public readonly color: string,
    public readonly texture: string,
  ) {}

  draw(x: number, y: number): string {
    return `${this.name}(${this.color}) at (${x},${y})`;
  }
}

class TreeFactory {
  private static cache = new Map<string, TreeType>();

  static get(name: string, color: string, texture: string): TreeType {
    const key = `${name}-${color}-${texture}`;
    if (!this.cache.has(key)) {
      this.cache.set(key, new TreeType(name, color, texture));
    }
    return this.cache.get(key)!;
  }
}

class Tree {
  constructor(
    public x: number,
    public y: number,
    public type: TreeType,
  ) {}

  draw(): string { return this.type.draw(this.x, this.y); }
}

// 1만 그루의 나무, TreeType은 소수만 생성
const forest = Array.from({ length: 10000 }, (_, i) =>
  new Tree(i, i * 2, TreeFactory.get("Oak", "green", "oak.png"))
);
```

**관련 패턴**: Composite (Leaf를 Flyweight로), Singleton (Factory를 Singleton으로)

---

### 12. Proxy

**의도**: 다른 객체에 대한 대리인을 제공하여 접근을 제어한다.

**해결하는 문제**: 지연 초기화, 접근 제어, 캐싱, 로깅 등 추가적 접근 제어가 필요한 경우.

**사용 시기**: 지연 로딩(Virtual Proxy), 권한 검사(Protection Proxy), 캐싱(Caching Proxy), 로깅(Logging Proxy) 등.

**Python:**

```python
from abc import ABC, abstractmethod

class ImageLoader(ABC):
    @abstractmethod
    def display(self) -> str: ...

class RealImage(ImageLoader):
    def __init__(self, filename: str) -> None:
        self._filename = filename
        self._data = self._load()

    def _load(self) -> str:
        return f"loaded({self._filename})"  # 비용이 큰 작업

    def display(self) -> str:
        return f"displaying {self._data}"

class LazyImageProxy(ImageLoader):
    """Virtual Proxy: 실제 사용 시점까지 로딩 지연"""
    def __init__(self, filename: str) -> None:
        self._filename = filename
        self._real: RealImage | None = None

    def display(self) -> str:
        if self._real is None:
            self._real = RealImage(self._filename)
        return self._real.display()

class AccessControlProxy(ImageLoader):
    """Protection Proxy: 권한 검사"""
    def __init__(self, image: ImageLoader, user_role: str) -> None:
        self._image = image
        self._role = user_role

    def display(self) -> str:
        if self._role not in ("admin", "editor"):
            raise PermissionError("Access denied")
        return self._image.display()

# 사용
image = AccessControlProxy(LazyImageProxy("photo.jpg"), "admin")
image.display()  # 권한 확인 -> 지연 로딩 -> 표시
```

**TypeScript:**

```typescript
interface ImageLoader {
  display(): string;
}

class RealImage implements ImageLoader {
  private data: string;

  constructor(private filename: string) {
    this.data = this.load();
  }

  private load(): string {
    return `loaded(${this.filename})`; // 비용이 큰 작업
  }

  display(): string { return `displaying ${this.data}`; }
}

class LazyImageProxy implements ImageLoader {
  private real: RealImage | null = null;

  constructor(private filename: string) {}

  display(): string {
    if (!this.real) {
      this.real = new RealImage(this.filename);
    }
    return this.real.display();
  }
}

class AccessControlProxy implements ImageLoader {
  constructor(
    private image: ImageLoader,
    private userRole: string,
  ) {}

  display(): string {
    if (!["admin", "editor"].includes(this.userRole)) {
      throw new Error("Access denied");
    }
    return this.image.display();
  }
}

// 사용
const image = new AccessControlProxy(
  new LazyImageProxy("photo.jpg"), "admin"
);
image.display(); // 권한 확인 -> 지연 로딩 -> 표시
```

**관련 패턴**: Decorator (기능 추가 vs 접근 제어), Adapter (인터페이스 변환 vs 동일 인터페이스), Facade (서브시스템 단순화 vs 단일 객체 제어)

---

## 비교 요약

### 생성 패턴 비교

| 패턴 | 핵심 메커니즘 | 생성 시점 | 핵심 가치 |
|------|-------------|----------|----------|
| Factory Method | 상속 + 오버라이드 | 즉시 | 서브클래스에 생성 위임 |
| Abstract Factory | 인터페이스 조합 | 즉시 | 제품군 호환성 보장 |
| Builder | 단계별 조립 | 지연 | 복잡한 객체의 단계별 생성 |
| Prototype | 복제 (clone) | 즉시 | 기존 객체 기반 생성 |
| Singleton | 접근 제어 | 지연 | 단일 인스턴스 보장 |

**진화 경로**: Factory Method --> Abstract Factory (제품군 관리) / Builder (유연성) / Prototype (상속 회피)

### 구조 패턴 비교

| 패턴 | 핵심 목적 | 인터페이스 변경 | 메커니즘 |
|------|----------|---------------|---------|
| Adapter | 인터페이스 호환 | O (변환) | 위임/상속 |
| Bridge | 추상화-구현 분리 | X | 합성 |
| Composite | 부분-전체 계층 | X | 재귀 합성 |
| Decorator | 동적 기능 추가 | X | 재귀 래핑 |
| Facade | 복잡성 은닉 | O (단순화) | 위임 |
| Flyweight | 메모리 최적화 | X | 객체 공유 |
| Proxy | 접근 제어 | X | 대리 위임 |

**래핑 패턴 구별 (Adapter/Decorator/Proxy)**:
- **Adapter**: 인터페이스를 **변환**한다
- **Decorator**: 인터페이스를 **유지**하면서 **기능을 추가**한다
- **Proxy**: 인터페이스를 **유지**하면서 **접근을 제어**한다
