# GoF Behavioral Patterns (행위 패턴) - Python/JS 코드 예시

GoF 행위 패턴 11개의 Python + JS/TS 코드 예시 참조 문서.

## Table of Contents

1. [Chain of Responsibility](#1-chain-of-responsibility)
2. [Command](#2-command)
3. [Interpreter](#3-interpreter)
4. [Iterator](#4-iterator)
5. [Mediator](#5-mediator)
6. [Memento](#6-memento)
7. [Observer](#7-observer)
8. [State](#8-state)
9. [Strategy](#9-strategy)
10. [Template Method](#10-template-method)
11. [Visitor](#11-visitor)

---

## 1. Chain of Responsibility

**의도**: 요청을 핸들러 체인에 따라 전달, 각 핸들러가 처리하거나 다음에 넘긴다.

**해결하는 문제**: 순차적 검사/처리의 중첩 조건문 비대화. 미들웨어 파이프라인, 인증/검증 체인 등에 적용.

### Python

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Request:
    user: str
    role: str
    data: dict

class Handler(ABC):
    def __init__(self):
        self._next: Handler | None = None

    def set_next(self, handler: "Handler") -> "Handler":
        self._next = handler
        return handler

    def handle(self, request: Request) -> str | None:
        if self._next:
            return self._next.handle(request)
        return None

class AuthHandler(Handler):
    def handle(self, request: Request) -> str | None:
        if not request.user:
            return "Error: authentication required"
        return super().handle(request)

class RoleHandler(Handler):
    def __init__(self, required_role: str):
        super().__init__()
        self._required_role = required_role

    def handle(self, request: Request) -> str | None:
        if request.role != self._required_role:
            return f"Error: {self._required_role} role required"
        return super().handle(request)

class ValidationHandler(Handler):
    def handle(self, request: Request) -> str | None:
        if not request.data:
            return "Error: empty data"
        return super().handle(request)

# 체인 구성
auth = AuthHandler()
auth.set_next(RoleHandler("admin")).set_next(ValidationHandler())
result = auth.handle(Request(user="alice", role="admin", data={"key": "val"}))
# result is None -> all checks passed
```

### JS/TS

```typescript
interface Request {
  user: string;
  role: string;
  data: Record<string, unknown>;
}

abstract class Handler {
  private next?: Handler;

  setNext(handler: Handler): Handler {
    this.next = handler;
    return handler;
  }

  handle(request: Request): string | null {
    return this.next ? this.next.handle(request) : null;
  }
}

class AuthHandler extends Handler {
  handle(request: Request): string | null {
    if (!request.user) return "Error: authentication required";
    return super.handle(request);
  }
}

class RoleHandler extends Handler {
  constructor(private requiredRole: string) { super(); }

  handle(request: Request): string | null {
    if (request.role !== this.requiredRole)
      return `Error: ${this.requiredRole} role required`;
    return super.handle(request);
  }
}

class ValidationHandler extends Handler {
  handle(request: Request): string | null {
    if (Object.keys(request.data).length === 0) return "Error: empty data";
    return super.handle(request);
  }
}

// Chain construction
const auth = new AuthHandler();
auth.setNext(new RoleHandler("admin")).setNext(new ValidationHandler());
const result = auth.handle({ user: "alice", role: "admin", data: { key: "val" } });
```

**패턴 비교**: Decorator와 구조가 유사하나, Chain of Responsibility는 체인 내 어디서든 처리를 중단할 수 있다. Mediator/Observer는 요청 라우팅의 대안.

---

## 2. Command

**의도**: 요청을 독립 실행형 객체로 변환. 큐잉, 지연 실행, Undo/Redo 지원.

**해결하는 문제**: GUI 요소와 비즈니스 로직 결합, 동일 작업의 다중 진입점 코드 중복.

### Python

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

class Command(ABC):
    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...

class TextEditor:
    def __init__(self):
        self.content = ""

    def insert(self, text: str, pos: int) -> None:
        self.content = self.content[:pos] + text + self.content[pos:]

    def delete(self, pos: int, length: int) -> None:
        self.content = self.content[:pos] + self.content[pos + length:]

class InsertTextCommand(Command):
    def __init__(self, editor: TextEditor, text: str, pos: int):
        self._editor = editor
        self._text = text
        self._pos = pos

    def execute(self) -> None:
        self._editor.insert(self._text, self._pos)

    def undo(self) -> None:
        self._editor.delete(self._pos, len(self._text))

@dataclass
class CommandHistory:
    _stack: list[Command] = field(default_factory=list)

    def execute(self, cmd: Command) -> None:
        cmd.execute()
        self._stack.append(cmd)

    def undo(self) -> None:
        if self._stack:
            self._stack.pop().undo()

# Usage
editor = TextEditor()
history = CommandHistory()
history.execute(InsertTextCommand(editor, "Hello", 0))
history.execute(InsertTextCommand(editor, " World", 5))
# editor.content == "Hello World"
history.undo()
# editor.content == "Hello"
```

### JS/TS

```typescript
interface Command {
  execute(): void;
  undo(): void;
}

class TextEditor {
  content = "";

  insert(text: string, pos: number): void {
    this.content = this.content.slice(0, pos) + text + this.content.slice(pos);
  }

  delete(pos: number, length: number): void {
    this.content = this.content.slice(0, pos) + this.content.slice(pos + length);
  }
}

class InsertTextCommand implements Command {
  constructor(
    private editor: TextEditor,
    private text: string,
    private pos: number,
  ) {}

  execute(): void { this.editor.insert(this.text, this.pos); }
  undo(): void { this.editor.delete(this.pos, this.text.length); }
}

class CommandHistory {
  private stack: Command[] = [];

  execute(cmd: Command): void {
    cmd.execute();
    this.stack.push(cmd);
  }

  undo(): void { this.stack.pop()?.undo(); }
}

// Usage
const editor = new TextEditor();
const history = new CommandHistory();
history.execute(new InsertTextCommand(editor, "Hello", 0));
history.execute(new InsertTextCommand(editor, " World", 5));
// editor.content === "Hello World"
history.undo();
// editor.content === "Hello"
```

**패턴 비교**: Command + Memento는 Undo/Redo 구현의 표준 조합. Strategy는 알고리즘 교체에 집중하지만 Command는 작업 객체화에 집중.

---

## 3. Interpreter

**의도**: 언어에 대한 문법을 정의하고, 그 문법에 따라 문장을 해석하는 인터프리터 제공.

**해결하는 문제**: DSL, 규칙 엔진, 수식 평가 등 반복적인 문법 해석 필요.

### Python

```python
from abc import ABC, abstractmethod

class Expression(ABC):
    @abstractmethod
    def interpret(self, context: dict[str, bool]) -> bool: ...

class Variable(Expression):
    def __init__(self, name: str):
        self.name = name

    def interpret(self, context: dict[str, bool]) -> bool:
        return context.get(self.name, False)

class And(Expression):
    def __init__(self, left: Expression, right: Expression):
        self.left = left
        self.right = right

    def interpret(self, context: dict[str, bool]) -> bool:
        return self.left.interpret(context) and self.right.interpret(context)

class Or(Expression):
    def __init__(self, left: Expression, right: Expression):
        self.left = left
        self.right = right

    def interpret(self, context: dict[str, bool]) -> bool:
        return self.left.interpret(context) or self.right.interpret(context)

class Not(Expression):
    def __init__(self, expr: Expression):
        self.expr = expr

    def interpret(self, context: dict[str, bool]) -> bool:
        return not self.expr.interpret(context)

# (A AND B) OR (NOT C)
expr = Or(
    And(Variable("A"), Variable("B")),
    Not(Variable("C")),
)
result = expr.interpret({"A": True, "B": False, "C": False})
# result == True (NOT C is True)
```

### JS/TS

```typescript
interface Expression {
  interpret(context: Map<string, boolean>): boolean;
}

class Variable implements Expression {
  constructor(private name: string) {}
  interpret(context: Map<string, boolean>): boolean {
    return context.get(this.name) ?? false;
  }
}

class And implements Expression {
  constructor(private left: Expression, private right: Expression) {}
  interpret(context: Map<string, boolean>): boolean {
    return this.left.interpret(context) && this.right.interpret(context);
  }
}

class Or implements Expression {
  constructor(private left: Expression, private right: Expression) {}
  interpret(context: Map<string, boolean>): boolean {
    return this.left.interpret(context) || this.right.interpret(context);
  }
}

class Not implements Expression {
  constructor(private expr: Expression) {}
  interpret(context: Map<string, boolean>): boolean {
    return !this.expr.interpret(context);
  }
}

// (A AND B) OR (NOT C)
const expr = new Or(
  new And(new Variable("A"), new Variable("B")),
  new Not(new Variable("C")),
);
const ctx = new Map([["A", true], ["B", false], ["C", false]]);
const result = expr.interpret(ctx);
// result === true
```

**패턴 비교**: Composite과 구문 트리 구조 공유. 복잡한 문법에는 파서 제너레이터가 더 적합.

---

## 4. Iterator

**의도**: 컬렉션 내부 표현을 노출하지 않고 요소를 순회.

**해결하는 문제**: 다양한 컬렉션 구조(리스트, 트리, 그래프)의 일관적 순회.

### Python

```python
from collections.abc import Iterator, Iterable
from dataclasses import dataclass, field

@dataclass
class TreeNode:
    value: int
    children: list["TreeNode"] = field(default_factory=list)

class DepthFirstIterator(Iterator[int]):
    """Pre-order DFS iterator for a tree."""

    def __init__(self, root: TreeNode):
        self._stack: list[TreeNode] = [root]

    def __next__(self) -> int:
        if not self._stack:
            raise StopIteration
        node = self._stack.pop()
        self._stack.extend(reversed(node.children))
        return node.value

class Tree(Iterable[int]):
    def __init__(self, root: TreeNode):
        self._root = root

    def __iter__(self) -> DepthFirstIterator:
        return DepthFirstIterator(self._root)

# Usage (supports for-loop natively via __iter__)
root = TreeNode(1, [
    TreeNode(2, [TreeNode(4), TreeNode(5)]),
    TreeNode(3),
])
tree = Tree(root)
values = list(tree)  # [1, 2, 4, 5, 3]
```

### JS/TS

```typescript
class TreeNode {
  constructor(
    public value: number,
    public children: TreeNode[] = [],
  ) {}
}

class DepthFirstIterator implements IterableIterator<number> {
  private stack: TreeNode[];

  constructor(root: TreeNode) {
    this.stack = [root];
  }

  next(): IteratorResult<number> {
    if (this.stack.length === 0) return { done: true, value: undefined };
    const node = this.stack.pop()!;
    this.stack.push(...[...node.children].reverse());
    return { done: false, value: node.value };
  }

  [Symbol.iterator]() { return this; }
}

class Tree {
  constructor(private root: TreeNode) {}

  [Symbol.iterator](): DepthFirstIterator {
    return new DepthFirstIterator(this.root);
  }
}

// Usage (supports for...of natively via Symbol.iterator)
const root = new TreeNode(1, [
  new TreeNode(2, [new TreeNode(4), new TreeNode(5)]),
  new TreeNode(3),
]);
const tree = new Tree(root);
const values = [...tree]; // [1, 2, 4, 5, 3]
```

**패턴 비교**: Python의 `__iter__`/`__next__`, JS의 `Symbol.iterator`/`next()`는 언어 수준 Iterator 프로토콜. Visitor는 순회 + 작업을 결합.

---

## 5. Mediator

**의도**: 객체 간 직접 통신을 제한하고 중재자를 통해서만 협력.

**해결하는 문제**: 컴포넌트 간 복잡한 상호의존성으로 인한 재사용성 저하.

### Python

```python
from abc import ABC, abstractmethod

class Mediator(ABC):
    @abstractmethod
    def notify(self, sender: "Component", event: str) -> None: ...

class Component:
    def __init__(self, mediator: Mediator | None = None):
        self._mediator = mediator

    def set_mediator(self, mediator: Mediator) -> None:
        self._mediator = mediator

class AuthInput(Component):
    def submit(self, username: str, password: str) -> None:
        self._mediator.notify(self, f"auth:{username}")

class SubmitButton(Component):
    def click(self) -> None:
        self._mediator.notify(self, "submit")

class ErrorDisplay(Component):
    def show(self, message: str) -> None:
        print(f"[Error] {message}")

class LoginFormMediator(Mediator):
    def __init__(self, auth: AuthInput, button: SubmitButton, error: ErrorDisplay):
        self._auth = auth
        self._button = button
        self._error = error
        auth.set_mediator(self)
        button.set_mediator(self)
        error.set_mediator(self)

    def notify(self, sender: Component, event: str) -> None:
        if event == "submit":
            self._auth.submit("user", "pass")
        elif event.startswith("auth:"):
            username = event.split(":")[1]
            if not username:
                self._error.show("Username required")
```

### JS/TS

```typescript
interface Mediator {
  notify(sender: Component, event: string): void;
}

class Component {
  protected mediator?: Mediator;
  setMediator(mediator: Mediator): void { this.mediator = mediator; }
}

class AuthInput extends Component {
  submit(username: string, password: string): void {
    this.mediator?.notify(this, `auth:${username}`);
  }
}

class SubmitButton extends Component {
  click(): void { this.mediator?.notify(this, "submit"); }
}

class ErrorDisplay extends Component {
  show(message: string): void { console.error(`[Error] ${message}`); }
}

class LoginFormMediator implements Mediator {
  constructor(
    private auth: AuthInput,
    private button: SubmitButton,
    private error: ErrorDisplay,
  ) {
    auth.setMediator(this);
    button.setMediator(this);
    error.setMediator(this);
  }

  notify(sender: Component, event: string): void {
    if (event === "submit") this.auth.submit("user", "pass");
    else if (event.startsWith("auth:")) {
      const username = event.split(":")[1];
      if (!username) this.error.show("Username required");
    }
  }
}
```

**패턴 비교**: Observer는 분산 구독 방식이지만 Mediator는 중앙 집중 제어. Facade는 서브시스템 접근 단순화에 집중.

---

## 6. Memento

**의도**: 구현 세부사항 노출 없이 객체의 이전 상태를 저장/복원.

**해결하는 문제**: Undo 구현 시 캡슐화 위반 vs 스냅샷 불가 딜레마.

### Python

```python
from __future__ import annotations
from dataclasses import dataclass, field
import copy

@dataclass(frozen=True)
class EditorMemento:
    """Immutable snapshot of editor state."""
    content: str
    cursor_pos: int

class Editor:
    def __init__(self):
        self.content = ""
        self.cursor_pos = 0

    def type_text(self, text: str) -> None:
        self.content = (
            self.content[:self.cursor_pos] + text + self.content[self.cursor_pos:]
        )
        self.cursor_pos += len(text)

    def save(self) -> EditorMemento:
        return EditorMemento(content=self.content, cursor_pos=self.cursor_pos)

    def restore(self, memento: EditorMemento) -> None:
        self.content = memento.content
        self.cursor_pos = memento.cursor_pos

@dataclass
class Caretaker:
    _history: list[EditorMemento] = field(default_factory=list)

    def push(self, memento: EditorMemento) -> None:
        self._history.append(memento)

    def pop(self) -> EditorMemento | None:
        return self._history.pop() if self._history else None

# Usage
editor = Editor()
caretaker = Caretaker()

caretaker.push(editor.save())
editor.type_text("Hello")
caretaker.push(editor.save())
editor.type_text(" World")
# editor.content == "Hello World"

memento = caretaker.pop()
if memento:
    editor.restore(memento)
# editor.content == "Hello"
```

### JS/TS

```typescript
class EditorMemento {
  constructor(
    readonly content: string,
    readonly cursorPos: number,
  ) {}
}

class Editor {
  content = "";
  cursorPos = 0;

  typeText(text: string): void {
    this.content =
      this.content.slice(0, this.cursorPos) + text + this.content.slice(this.cursorPos);
    this.cursorPos += text.length;
  }

  save(): EditorMemento {
    return new EditorMemento(this.content, this.cursorPos);
  }

  restore(memento: EditorMemento): void {
    this.content = memento.content;
    this.cursorPos = memento.cursorPos;
  }
}

class Caretaker {
  private history: EditorMemento[] = [];

  push(memento: EditorMemento): void { this.history.push(memento); }
  pop(): EditorMemento | undefined { return this.history.pop(); }
}

// Usage
const editor = new Editor();
const caretaker = new Caretaker();

caretaker.push(editor.save());
editor.typeText("Hello");
caretaker.push(editor.save());
editor.typeText(" World");
// editor.content === "Hello World"

const memento = caretaker.pop();
if (memento) editor.restore(memento);
// editor.content === "Hello"
```

**패턴 비교**: Command + Memento는 Undo/Redo의 표준 조합. Prototype은 단순한 상태 복제 대안.

---

## 7. Observer

**의도**: 구독 메커니즘으로 관찰 대상 이벤트를 여러 객체에 알림.

**해결하는 문제**: 상태 변경 알림이 필요하지만 종속 객체가 동적으로 변함.

### Python

```python
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any

class Subscriber(ABC):
    @abstractmethod
    def update(self, event: str, data: Any) -> None: ...

class EventManager:
    def __init__(self):
        self._listeners: dict[str, list[Subscriber]] = defaultdict(list)

    def subscribe(self, event: str, listener: Subscriber) -> None:
        self._listeners[event].append(listener)

    def unsubscribe(self, event: str, listener: Subscriber) -> None:
        self._listeners[event].remove(listener)

    def notify(self, event: str, data: Any = None) -> None:
        for listener in self._listeners.get(event, []):
            listener.update(event, data)

class LoggingSubscriber(Subscriber):
    def update(self, event: str, data: Any) -> None:
        print(f"[LOG] {event}: {data}")

class MetricsSubscriber(Subscriber):
    def __init__(self):
        self.event_count: dict[str, int] = defaultdict(int)

    def update(self, event: str, data: Any) -> None:
        self.event_count[event] += 1

class OrderService:
    def __init__(self):
        self.events = EventManager()

    def place_order(self, order_id: str) -> None:
        # business logic...
        self.events.notify("order:placed", {"order_id": order_id})

# Usage
service = OrderService()
service.events.subscribe("order:placed", LoggingSubscriber())
service.events.subscribe("order:placed", MetricsSubscriber())
service.place_order("ORD-001")
```

### JS/TS

```typescript
interface Subscriber {
  update(event: string, data: unknown): void;
}

class EventManager {
  private listeners = new Map<string, Subscriber[]>();

  subscribe(event: string, listener: Subscriber): void {
    if (!this.listeners.has(event)) this.listeners.set(event, []);
    this.listeners.get(event)!.push(listener);
  }

  unsubscribe(event: string, listener: Subscriber): void {
    const subs = this.listeners.get(event);
    if (subs) this.listeners.set(event, subs.filter((s) => s !== listener));
  }

  notify(event: string, data?: unknown): void {
    this.listeners.get(event)?.forEach((l) => l.update(event, data));
  }
}

class LoggingSubscriber implements Subscriber {
  update(event: string, data: unknown): void {
    console.log(`[LOG] ${event}:`, data);
  }
}

class MetricsSubscriber implements Subscriber {
  eventCount = new Map<string, number>();

  update(event: string): void {
    this.eventCount.set(event, (this.eventCount.get(event) ?? 0) + 1);
  }
}

class OrderService {
  events = new EventManager();

  placeOrder(orderId: string): void {
    // business logic...
    this.events.notify("order:placed", { orderId });
  }
}

// Usage
const service = new OrderService();
service.events.subscribe("order:placed", new LoggingSubscriber());
service.events.subscribe("order:placed", new MetricsSubscriber());
service.placeOrder("ORD-001");
```

**패턴 비교**: Observer는 분산 Pub-Sub 방식. Mediator는 중앙 집중 대안으로 복잡한 상호작용에 적합.

---

## 8. State

**의도**: 내부 상태 변경 시 객체 동작을 변경. 클래스가 바뀐 것처럼 보임.

**해결하는 문제**: 수많은 상태 의존적 동작의 거대한 조건문(if/switch).

### Python

```python
from abc import ABC, abstractmethod

class DocumentState(ABC):
    @abstractmethod
    def publish(self, doc: "Document") -> None: ...

    @abstractmethod
    def edit(self, doc: "Document", content: str) -> None: ...

class DraftState(DocumentState):
    def publish(self, doc: "Document") -> None:
        doc.state = ReviewState()

    def edit(self, doc: "Document", content: str) -> None:
        doc.content = content

class ReviewState(DocumentState):
    def publish(self, doc: "Document") -> None:
        doc.state = PublishedState()

    def edit(self, doc: "Document", content: str) -> None:
        pass  # Cannot edit during review

class PublishedState(DocumentState):
    def publish(self, doc: "Document") -> None:
        pass  # Already published

    def edit(self, doc: "Document", content: str) -> None:
        doc.content = content
        doc.state = DraftState()  # Back to draft on edit

class Document:
    def __init__(self):
        self.state: DocumentState = DraftState()
        self.content = ""

    def publish(self) -> None:
        self.state.publish(self)

    def edit(self, content: str) -> None:
        self.state.edit(self, content)

# Usage
doc = Document()
doc.edit("Draft content")    # DraftState: allowed
doc.publish()                # -> ReviewState
doc.edit("Change")           # ReviewState: ignored
doc.publish()                # -> PublishedState
doc.edit("Fix typo")         # PublishedState -> DraftState
```

### JS/TS

```typescript
interface DocumentState {
  publish(doc: Document): void;
  edit(doc: Document, content: string): void;
}

class DraftState implements DocumentState {
  publish(doc: Document): void { doc.state = new ReviewState(); }
  edit(doc: Document, content: string): void { doc.content = content; }
}

class ReviewState implements DocumentState {
  publish(doc: Document): void { doc.state = new PublishedState(); }
  edit(_doc: Document, _content: string): void { /* Cannot edit during review */ }
}

class PublishedState implements DocumentState {
  publish(_doc: Document): void { /* Already published */ }
  edit(doc: Document, content: string): void {
    doc.content = content;
    doc.state = new DraftState(); // Back to draft on edit
  }
}

class Document {
  state: DocumentState = new DraftState();
  content = "";

  publish(): void { this.state.publish(this); }
  edit(content: string): void { this.state.edit(this, content); }
}

// Usage
const doc = new Document();
doc.edit("Draft content");  // DraftState: allowed
doc.publish();              // -> ReviewState
doc.edit("Change");         // ReviewState: ignored
doc.publish();              // -> PublishedState
doc.edit("Fix typo");       // PublishedState -> DraftState
```

**패턴 비교**: State는 Strategy의 확장이며, 상태 객체들이 서로를 인지하고 전이를 관리한다. Strategy는 알고리즘 교체만 담당하고 상태 전이가 없다.

---

## 9. Strategy

**의도**: 알고리즘 군을 정의하고 각각 별도 클래스에 넣어 교체 가능하게.

**해결하는 문제**: 알고리즘 변형의 조건 분기로 인한 비대한 클래스.

### Python

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

class CompressionStrategy(ABC):
    @abstractmethod
    def compress(self, data: bytes) -> bytes: ...

class GzipStrategy(CompressionStrategy):
    def compress(self, data: bytes) -> bytes:
        import gzip
        return gzip.compress(data)

class LZ4Strategy(CompressionStrategy):
    def compress(self, data: bytes) -> bytes:
        # LZ4 compression (simplified)
        return data  # placeholder

class NoCompressionStrategy(CompressionStrategy):
    def compress(self, data: bytes) -> bytes:
        return data

@dataclass
class FileCompressor:
    strategy: CompressionStrategy

    def compress_file(self, data: bytes) -> bytes:
        return self.strategy.compress(data)

# Usage - strategy is swappable at runtime
compressor = FileCompressor(strategy=GzipStrategy())
result = compressor.compress_file(b"Hello World")

compressor.strategy = NoCompressionStrategy()
result = compressor.compress_file(b"Hello World")
```

### JS/TS

```typescript
interface CompressionStrategy {
  compress(data: Buffer): Buffer;
}

class GzipStrategy implements CompressionStrategy {
  compress(data: Buffer): Buffer {
    const zlib = require("zlib");
    return zlib.gzipSync(data);
  }
}

class NoCompressionStrategy implements CompressionStrategy {
  compress(data: Buffer): Buffer { return data; }
}

class FileCompressor {
  constructor(private strategy: CompressionStrategy) {}

  setStrategy(strategy: CompressionStrategy): void {
    this.strategy = strategy;
  }

  compressFile(data: Buffer): Buffer {
    return this.strategy.compress(data);
  }
}

// Usage - strategy is swappable at runtime
const compressor = new FileCompressor(new GzipStrategy());
let result = compressor.compressFile(Buffer.from("Hello World"));

compressor.setStrategy(new NoCompressionStrategy());
result = compressor.compressFile(Buffer.from("Hello World"));
```

**패턴 비교**: Template Method는 상속 기반(정적)이며 알고리즘 골격을 고정. Strategy는 합성 기반(런타임)이며 전체 알고리즘을 교체. 함수형 프로그래밍에서는 고차 함수가 Strategy를 대체할 수 있다.

---

## 10. Template Method

**의도**: 상위 클래스에서 알고리즘 골격 정의, 하위 클래스가 특정 단계 재정의.

**해결하는 문제**: 사소한 차이만 있는 유사 알고리즘의 코드 중복.

### Python

```python
from abc import ABC, abstractmethod

class DataPipeline(ABC):
    """Template method pattern: define pipeline skeleton."""

    def process(self, source: str) -> dict:
        """Template method - do not override."""
        raw = self.extract(source)
        cleaned = self.transform(raw)
        result = self.load(cleaned)
        self.on_complete(result)  # hook
        return result

    @abstractmethod
    def extract(self, source: str) -> list[dict]:
        """Abstract step: must override."""
        ...

    @abstractmethod
    def transform(self, data: list[dict]) -> list[dict]:
        """Abstract step: must override."""
        ...

    def load(self, data: list[dict]) -> dict:
        """Optional step: has default implementation."""
        return {"count": len(data), "data": data}

    def on_complete(self, result: dict) -> None:
        """Hook: empty by default, override if needed."""
        pass

class CSVPipeline(DataPipeline):
    def extract(self, source: str) -> list[dict]:
        # Parse CSV file
        return [{"name": "Alice"}, {"name": "Bob"}]

    def transform(self, data: list[dict]) -> list[dict]:
        return [{"name": d["name"].upper()} for d in data]

    def on_complete(self, result: dict) -> None:
        print(f"Processed {result['count']} records from CSV")

class APIPipeline(DataPipeline):
    def extract(self, source: str) -> list[dict]:
        # Fetch from API
        return [{"id": 1, "name": "Item"}]

    def transform(self, data: list[dict]) -> list[dict]:
        return [{"item_name": d["name"]} for d in data]
```

### JS/TS

```typescript
abstract class DataPipeline {
  /** Template method - do not override. */
  process(source: string): Record<string, unknown> {
    const raw = this.extract(source);
    const cleaned = this.transform(raw);
    const result = this.load(cleaned);
    this.onComplete(result); // hook
    return result;
  }

  /** Abstract step: must override. */
  protected abstract extract(source: string): Record<string, unknown>[];

  /** Abstract step: must override. */
  protected abstract transform(
    data: Record<string, unknown>[],
  ): Record<string, unknown>[];

  /** Optional step: has default implementation. */
  protected load(data: Record<string, unknown>[]): Record<string, unknown> {
    return { count: data.length, data };
  }

  /** Hook: empty by default, override if needed. */
  protected onComplete(_result: Record<string, unknown>): void {}
}

class CSVPipeline extends DataPipeline {
  protected extract(_source: string) {
    return [{ name: "Alice" }, { name: "Bob" }];
  }

  protected transform(data: Record<string, unknown>[]) {
    return data.map((d) => ({ name: (d.name as string).toUpperCase() }));
  }

  protected onComplete(result: Record<string, unknown>): void {
    console.log(`Processed ${result.count} records from CSV`);
  }
}

class APIPipeline extends DataPipeline {
  protected extract(_source: string) {
    return [{ id: 1, name: "Item" }];
  }

  protected transform(data: Record<string, unknown>[]) {
    return data.map((d) => ({ itemName: d.name }));
  }
}
```

**패턴 비교**: Template Method는 상속 기반이므로 알고리즘 골격이 컴파일 타임에 결정. Strategy는 합성 기반이므로 런타임에 전체 알고리즘을 교체할 수 있다. Factory Method는 Template Method의 특수화로, 생성 단계만 서브클래스에 위임.

---

## 11. Visitor

**의도**: 알고리즘을 객체 구조로부터 분리, 클래스 수정 없이 새 동작 추가.

**해결하는 문제**: 복잡한 객체 구조에 새 작업 추가 시 클래스 변경 위험. 이중 디스패치(Double Dispatch)로 해결.

### Python

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
import math

class ShapeVisitor(ABC):
    @abstractmethod
    def visit_circle(self, circle: "Circle") -> None: ...

    @abstractmethod
    def visit_rectangle(self, rect: "Rectangle") -> None: ...

class Shape(ABC):
    @abstractmethod
    def accept(self, visitor: ShapeVisitor) -> None: ...

@dataclass
class Circle(Shape):
    radius: float

    def accept(self, visitor: ShapeVisitor) -> None:
        visitor.visit_circle(self)

@dataclass
class Rectangle(Shape):
    width: float
    height: float

    def accept(self, visitor: ShapeVisitor) -> None:
        visitor.visit_rectangle(self)

class AreaCalculator(ShapeVisitor):
    def __init__(self):
        self.total = 0.0

    def visit_circle(self, circle: Circle) -> None:
        self.total += math.pi * circle.radius ** 2

    def visit_rectangle(self, rect: Rectangle) -> None:
        self.total += rect.width * rect.height

class JsonExporter(ShapeVisitor):
    def __init__(self):
        self.items: list[dict] = []

    def visit_circle(self, circle: Circle) -> None:
        self.items.append({"type": "circle", "radius": circle.radius})

    def visit_rectangle(self, rect: Rectangle) -> None:
        self.items.append({"type": "rect", "w": rect.width, "h": rect.height})

# Usage: add new operations without modifying Shape classes
shapes: list[Shape] = [Circle(5), Rectangle(3, 4), Circle(2)]

calc = AreaCalculator()
for s in shapes:
    s.accept(calc)
# calc.total == pi*25 + 12 + pi*4

exporter = JsonExporter()
for s in shapes:
    s.accept(exporter)
# exporter.items == [{"type":"circle","radius":5}, ...]
```

### JS/TS

```typescript
interface ShapeVisitor {
  visitCircle(circle: Circle): void;
  visitRectangle(rect: Rectangle): void;
}

interface Shape {
  accept(visitor: ShapeVisitor): void;
}

class Circle implements Shape {
  constructor(public readonly radius: number) {}
  accept(visitor: ShapeVisitor): void { visitor.visitCircle(this); }
}

class Rectangle implements Shape {
  constructor(
    public readonly width: number,
    public readonly height: number,
  ) {}
  accept(visitor: ShapeVisitor): void { visitor.visitRectangle(this); }
}

class AreaCalculator implements ShapeVisitor {
  total = 0;

  visitCircle(circle: Circle): void {
    this.total += Math.PI * circle.radius ** 2;
  }

  visitRectangle(rect: Rectangle): void {
    this.total += rect.width * rect.height;
  }
}

class JsonExporter implements ShapeVisitor {
  items: Record<string, unknown>[] = [];

  visitCircle(circle: Circle): void {
    this.items.push({ type: "circle", radius: circle.radius });
  }

  visitRectangle(rect: Rectangle): void {
    this.items.push({ type: "rect", w: rect.width, h: rect.height });
  }
}

// Usage: add new operations without modifying Shape classes
const shapes: Shape[] = [new Circle(5), new Rectangle(3, 4), new Circle(2)];

const calc = new AreaCalculator();
shapes.forEach((s) => s.accept(calc));
// calc.total === Math.PI*25 + 12 + Math.PI*4

const exporter = new JsonExporter();
shapes.forEach((s) => s.accept(exporter));
// exporter.items === [{type:"circle",radius:5}, ...]
```

**패턴 비교**: Visitor는 OCP를 작업 추가 방향으로 적용 (새 Visitor 추가 용이, 새 Element 추가 어려움). Composite와 결합하여 트리 순회에 자주 사용. Iterator는 순회만 담당하고 Visitor는 순회 + 작업을 결합.

---

## 행위 패턴 비교 요약

| 문제 상황 | 추천 패턴 | 대안 패턴 |
|-----------|----------|----------|
| 순차적 처리기 체인 | Chain of Responsibility | Mediator |
| 작업 객체화/Undo | Command | Memento |
| DSL/문법 해석 | Interpreter | Composite + Visitor |
| 컬렉션 균일 순회 | Iterator | Visitor |
| 복잡한 통신 중앙 집중 | Mediator | Observer |
| 상태 스냅샷 저장/복원 | Memento | Prototype |
| 이벤트 기반 구독/알림 | Observer | Mediator |
| 상태별 동작 변경 | State | Strategy |
| 런타임 알고리즘 교체 | Strategy | Template Method |
| 알고리즘 골격 + 단계 재정의 | Template Method | Strategy |
| 클래스 변경 없이 새 작업 | Visitor | Iterator + 별도 로직 |

### 핵심 패턴 관계

- **Command + Memento**: Undo/Redo 구현의 표준 조합
- **Strategy vs Template Method**: 합성(런타임 교체) vs 상속(정적 골격)
- **State는 Strategy의 확장**: 상태 객체들이 서로 인지하고 전이를 관리
- **Observer vs Mediator**: 분산 Pub-Sub vs 중앙 집중 제어
- **Interpreter + Composite**: 구문 트리 구조를 공유하며 재귀적 해석
- **Iterator + Visitor**: 순회(Iterator)와 순회 중 작업(Visitor)의 역할 분리
