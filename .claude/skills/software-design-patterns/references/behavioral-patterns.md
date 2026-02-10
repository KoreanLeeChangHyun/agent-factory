# Behavioral Patterns (행위 패턴)

GoF 행위 패턴 11개의 상세 참조 문서.

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
12. [비교 요약](#비교-요약)

---

## 1. Chain of Responsibility

**의도**: 요청을 핸들러 체인에 따라 전달, 각 핸들러가 처리하거나 다음에 넘긴다.

**해결하는 문제**: 순차적 검사/처리의 중첩 조건문 비대화.

| 참여자 | 역할 |
|--------|------|
| Handler | 요청 처리 인터페이스 |
| Base Handler | 다음 핸들러 참조 보일러플레이트 |
| Concrete Handlers | 실제 처리 로직, 전달 여부 결정 |

**적용**: 미들웨어 파이프라인, 이벤트 버블링, 인증/검증 체인

| 장점 | 단점 |
|------|------|
| SRP/OCP, 유연한 순서 제어 | 일부 요청 미처리 가능 |

**관련 패턴**: Command, Mediator, Observer (요청 라우팅 대안), Decorator (구조 유사, 전파 중단 차이)

---

## 2. Command

**의도**: 요청을 독립 실행형 객체로 변환. 큐잉, 지연 실행, Undo 지원.

**해결하는 문제**: GUI 요소와 비즈니스 로직 결합, 동일 작업의 다중 진입점 코드 중복.

| 참여자 | 역할 |
|--------|------|
| Invoker/Sender | 커맨드를 트리거 |
| Command Interface | 실행 메서드 선언 |
| Concrete Commands | 리시버에 위임하는 특정 작업 구현 |
| Receiver | 실제 비즈니스 로직 |

**적용**: Undo/Redo, 매크로 녹화/재생, 트랜잭션 롤백, 작업 큐잉/스케줄링

```typescript
interface Command { execute(): void; undo(): void; }
class InsertTextCommand implements Command {
  constructor(private editor: TextEditor, private text: string, private pos: number) {}
  execute() { this.editor.insert(this.text, this.pos); }
  undo() { this.editor.delete(this.pos, this.text.length); }
}
class CommandHistory {
  private stack: Command[] = [];
  push(cmd: Command) { cmd.execute(); this.stack.push(cmd); }
  undo() { this.stack.pop()?.undo(); }
}
```

| 장점 | 단점 |
|------|------|
| SRP/OCP, Undo/Redo 지원 | 추가 계층으로 복잡도 증가 |
| 단순 커맨드로 복합 조합 가능 | |

**관련 패턴**: Memento (Undo 협력), Strategy (매개변수화 vs 알고리즘)

---

## 3. Interpreter

**의도**: 언어에 대한 문법을 정의하고, 그 문법에 따라 문장을 해석하는 인터프리터 제공.

**해결하는 문제**: DSL, 규칙 엔진, 수식 평가 등 반복적인 문법 해석 필요.

| 참여자 | 역할 |
|--------|------|
| AbstractExpression | interpret() 메서드 선언 |
| TerminalExpression | 문법의 터미널 심볼 해석 |
| NonterminalExpression | 비터미널 규칙 해석, 재귀 합성 |
| Context | 해석에 필요한 전역 정보 |

**적용**: DSL 파서, 정규표현식 엔진, SQL 파서, 수식 계산기

| 장점 | 단점 |
|------|------|
| 문법 변경/확장 용이 | 복잡한 문법에 부적합 (파서 제너레이터 사용) |
| 간단한 문법에 효과적 | 성능 이슈 |

**관련 패턴**: Composite (구문 트리), Iterator (트리 순회), Visitor (트리 연산)

---

## 4. Iterator

**의도**: 컬렉션 내부 표현을 노출하지 않고 요소를 순회.

**해결하는 문제**: 다양한 컬렉션 구조의 일관적 순회, 순회 알고리즘과 컬렉션 분리.

| 참여자 | 역할 |
|--------|------|
| Iterator Interface | next(), hasNext() 등 순회 작업 |
| Concrete Iterator | 특정 순회 알고리즘, 독립 상태 추적 |
| Collection Interface | 이터레이터 생성 메서드 |
| Concrete Collection | 적절한 이터레이터 반환 |

**적용**: 파일 시스템 순회, DB 커서, 스트림 처리, 트리 DFS/BFS

| 장점 | 단점 |
|------|------|
| SRP/OCP, 병렬 순회 가능 | 단순 컬렉션에 과도 |

**관련 패턴**: Composite (트리 순회), Factory Method (이터레이터 생성), Visitor (순회 + 작업)

---

## 5. Mediator

**의도**: 객체 간 직접 통신을 제한하고 중재자를 통해서만 협력.

**해결하는 문제**: 컴포넌트 간 복잡한 상호의존성, 재사용성 저하.

| 참여자 | 역할 |
|--------|------|
| Components | 비즈니스 로직 클래스, 중재자만 참조 |
| Mediator Interface | 단일 알림 메서드 |
| Concrete Mediator | 컴포넌트 관계 캡슐화, 참조 유지 |

**적용**: 채팅방, GUI 폼 조율, 항공 교통 관제

| 장점 | 단점 |
|------|------|
| SRP/OCP, 결합 감소 | God Object 위험 |
| 컴포넌트 재사용성 향상 | |

**관련 패턴**: Observer (분산 vs 중앙 집중), Facade (서브시스템 접근 단순화)

---

## 6. Memento

**의도**: 구현 세부사항 노출 없이 객체의 이전 상태를 저장/복원.

**해결하는 문제**: Undo 구현 시 캡슐화 위반 vs 스냅샷 불가 딜레마.

| 참여자 | 역할 |
|--------|------|
| Originator | 스냅샷 생성 및 상태 복원 |
| Memento | 불변 값 객체, 상태 저장 |
| Caretaker | 메멘토 이력(스택) 관리 |

**구현 접근법**: (1) 중첩 클래스 (2) 중간 인터페이스 (3) 엄격한 캡슐화

**적용**: Undo/Redo, 트랜잭션 롤백, 게임 저장/로드

| 장점 | 단점 |
|------|------|
| 캡슐화 유지 스냅샷 | 빈번한 생성 시 RAM 소비 |
| 이력 관리 위임 | 동적 언어에서 불변성 보장 불가 |

**관련 패턴**: Command (Undo 협력), Prototype (단순 대안)

---

## 7. Observer

**의도**: 구독 메커니즘으로 관찰 대상 이벤트를 여러 객체에 알림.

**해결하는 문제**: 상태 변경 알림이 필요하지만 종속 객체가 동적으로 변함.

| 참여자 | 역할 |
|--------|------|
| Publisher/Subject | 이벤트 발행, 구독 관리 |
| Subscriber Interface | update() 메서드 |
| Concrete Subscribers | 알림 응답 구현 |

**적용**: 이벤트 시스템, 모델-뷰 동기화, 알림 서비스, GUI 이벤트

```typescript
interface Subscriber { update(event: string, data: any): void; }
class EventManager {
  private listeners = new Map<string, Subscriber[]>();
  subscribe(event: string, listener: Subscriber) {
    if (!this.listeners.has(event)) this.listeners.set(event, []);
    this.listeners.get(event)!.push(listener);
  }
  notify(event: string, data: any) {
    this.listeners.get(event)?.forEach(l => l.update(event, data));
  }
}
```

| 장점 | 단점 |
|------|------|
| OCP, 런타임 관계 수립 | 예측 불가 알림 순서 |
| | 메모리 누수 (구독 해지 미처리) |

**관련 패턴**: Mediator (중앙 집중 대안)

---

## 8. State

**의도**: 내부 상태 변경 시 객체 동작을 변경. 클래스가 바뀐 것처럼 보임.

**해결하는 문제**: 수많은 상태 의존적 동작의 거대한 조건문.

| 참여자 | 역할 |
|--------|------|
| Context | 상태 객체 참조 유지, 위임 |
| State Interface | 상태별 동작 메서드 |
| Concrete States | 상태별 구현, 전환 가능 |

**적용**: 자판기, 문서 승인 워크플로우, TCP 연결 관리

| 장점 | 단점 |
|------|------|
| SRP/OCP, 조건문 제거 | 상태 적으면 과도 |

**관련 패턴**: Strategy (State는 Strategy 확장, 상태 간 인지 가능)

---

## 9. Strategy

**의도**: 알고리즘 군을 정의하고 각각 별도 클래스에 넣어 교체 가능하게.

**해결하는 문제**: 알고리즘 변형의 조건 분기로 인한 비대한 클래스.

| 참여자 | 역할 |
|--------|------|
| Context | 전략 참조, 인터페이스 통해 통신 |
| Strategy Interface | 실행 메서드 선언 |
| Concrete Strategies | 알고리즘 변형 구현 |

**적용**: 정렬/검색 알고리즘 교체, 결제 방식 선택, 압축 전략, 라우팅 알고리즘

```typescript
interface SortStrategy { sort(data: number[]): number[]; }
class QuickSort implements SortStrategy {
  sort(data: number[]) { /* quicksort */ return data; }
}
class MergeSort implements SortStrategy {
  sort(data: number[]) { /* mergesort */ return data; }
}
class Sorter {
  constructor(private strategy: SortStrategy) {}
  setStrategy(s: SortStrategy) { this.strategy = s; }
  sort(data: number[]) { return this.strategy.sort(data); }
}
```

| 장점 | 단점 |
|------|------|
| 런타임 교체, OCP | 알고리즘 적으면 불필요 |
| 상속을 합성으로 대체 | 함수형에서 불필요할 수 있음 |

**관련 패턴**: Template Method (합성 vs 상속), State (확장), Command (매개변수화 vs 알고리즘)

---

## 10. Template Method

**의도**: 상위 클래스에서 알고리즘 골격 정의, 하위 클래스가 특정 단계 재정의.

**해결하는 문제**: 사소한 차이만 있는 유사 알고리즘의 코드 중복.

**단계 유형**:
- **추상 단계**: 모든 하위 클래스 필수 구현
- **선택적 단계**: 기본 구현 있음, 재정의 가능
- **훅(Hook)**: 빈 본문, 확장 지점

| 참여자 | 역할 |
|--------|------|
| Abstract Class | 템플릿 메서드 + 단계 메서드 선언 |
| Concrete Classes | 필수 단계 구현, 선택적 단계 재정의 |

**적용**: 프레임워크 라이프사이클 훅, 데이터 처리 파이프라인, 문서 파서

```typescript
abstract class DataMiner {
  mine(path: string) {          // template method
    const raw = this.openFile(path);
    const data = this.extractData(raw);
    const parsed = this.parseData(data);
    this.analyze(parsed);
    this.sendReport();          // hook
  }
  abstract openFile(path: string): string;
  abstract extractData(raw: string): any[];
  abstract parseData(data: any[]): any;
  analyze(data: any) { /* default */ }
  sendReport() { /* hook - optional override */ }
}
```

| 장점 | 단점 |
|------|------|
| 중복 코드 제거 | 알고리즘 골격 제약 |
| 특정 부분만 재정의 | LSP 위반 위험 |

**관련 패턴**: Factory Method (특수화), Strategy (합성 대안)

---

## 11. Visitor

**의도**: 알고리즘을 객체 구조로부터 분리, 클래스 수정 없이 새 동작 추가.

**해결하는 문제**: 복잡한 객체 구조에 새 작업 추가 시 클래스 변경 위험.

**핵심: 이중 디스패치(Double Dispatch)** - 요소가 자신을 방문자에게 식별, 방문자가 올바른 메서드 실행.

| 참여자 | 역할 |
|--------|------|
| Visitor Interface | 각 요소 타입별 visit 메서드 |
| Concrete Visitors | 다양한 동작 변형 구현 |
| Element Interface | accept(visitor) 메서드 |
| Concrete Elements | visitor의 올바른 메서드로 리다이렉트 |

**적용**: 컴파일러 AST 순회, 문서 내보내기(XML/JSON), 보고서 생성

```typescript
interface Visitor {
  visitCircle(c: CircleElement): void;
  visitRect(r: RectElement): void;
}
interface Element { accept(v: Visitor): void; }
class CircleElement implements Element {
  accept(v: Visitor) { v.visitCircle(this); }
}
class AreaCalculator implements Visitor {
  private total = 0;
  visitCircle(c: CircleElement) { this.total += Math.PI * c.r ** 2; }
  visitRect(r: RectElement) { this.total += r.w * r.h; }
}
```

| 장점 | 단점 |
|------|------|
| OCP/SRP, 순회 중 정보 축적 | 요소 추가/제거 시 모든 Visitor 수정 |
| | private 멤버 접근 불가 |

**관련 패턴**: Composite (트리 순회), Iterator (구조 탐색), Command (기능 확장)

---

## 비교 요약

| 문제 상황 | 추천 패턴 | 대안 패턴 |
|-----------|----------|----------|
| 순차적 처리기 체인 | Chain of Responsibility | Mediator |
| 작업 객체화/Undo | Command | Memento |
| 컬렉션 균일 순회 | Iterator | Visitor |
| 복잡한 통신 중앙 집중 | Mediator | Observer |
| 상태 스냅샷 저장/복원 | Memento | Prototype |
| 이벤트 기반 구독/알림 | Observer | Mediator |
| 상태별 동작 변경 | State | Strategy |
| 런타임 알고리즘 교체 | Strategy | Template Method |
| 알고리즘 골격 + 단계 재정의 | Template Method | Strategy |
| 클래스 변경 없이 새 작업 | Visitor | Iterator + 별도 로직 |

**패턴 간 핵심 관계**:
- **Command + Memento**: Undo/Redo 구현의 표준 조합
- **Strategy vs Template Method**: 합성(런타임) vs 상속(정적)
- **State는 Strategy의 확장**: 상태 간 서로 인지 가능
- **Observer vs Mediator**: 분산 구독 vs 중앙 집중 제어
