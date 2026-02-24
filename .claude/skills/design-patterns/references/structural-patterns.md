# Structural Patterns (구조 패턴)

GoF 구조 패턴 7개의 상세 참조 문서.

## Table of Contents

1. [Adapter](#1-adapter)
2. [Bridge](#2-bridge)
3. [Composite](#3-composite)
4. [Decorator](#4-decorator)
5. [Facade](#5-facade)
6. [Flyweight](#6-flyweight)
7. [Proxy](#7-proxy)
8. [비교 요약](#비교-요약)

---

## 1. Adapter

**의도**: 호환되지 않는 인터페이스를 변환하여 함께 동작하게 한다.

**해결하는 문제**: 레거시/서드파티 인터페이스가 현재 시스템과 불일치.

| 구분 | 클래스 어댑터 | 오브젝트 어댑터 |
|------|-------------|----------------|
| 메커니즘 | 다중 상속 | 합성(composition) |
| 유연성 | 특정 Adaptee 고정 | 다양한 Adaptee 가능 |
| 언어 제약 | 다중 상속 필요(C++) | 모든 OOP 언어 |

| 참여자 | 역할 |
|--------|------|
| Target | 클라이언트가 사용하는 인터페이스 |
| Adaptee | 적응이 필요한 기존 인터페이스 |
| Adapter | Adaptee를 Target으로 변환 |

**적용**: 레거시 API 통합, 데이터 포맷 변환(CSV/JSON/XML), 서드파티 래핑, DB 드라이버 통합, 로깅 프레임워크(SLF4J)

```typescript
interface MediaPlayer { play(type: string, file: string): void; }

class AdvancedMediaPlayer {
  playVlc(file: string) { /* VLC */ }
  playMp4(file: string) { /* MP4 */ }
}

class MediaAdapter implements MediaPlayer {
  constructor(private advanced: AdvancedMediaPlayer) {}
  play(type: string, file: string) {
    if (type === 'vlc') this.advanced.playVlc(file);
    else if (type === 'mp4') this.advanced.playMp4(file);
  }
}
```

| 장점 | 단점 |
|------|------|
| SRP/OCP 준수 | 전체 복잡성 증가 |
| 기존 기능 재사용 | 성능 오버헤드 가능 |

**관련 패턴**: Bridge (설계 초기 분리 vs 사후 호환), Decorator (기능 추가 vs 인터페이스 변환), Facade (서브시스템 단순화), Proxy (동일 인터페이스 유지)

---

## 2. Bridge

**의도**: 추상화(Abstraction)와 구현(Implementation)을 분리하여 독립적 변경 가능하게 한다.

**해결하는 문제**: 두 차원(예: 모양+색상)의 상속 폭발, 런타임 구현 전환 필요.

| 참여자 | 역할 |
|--------|------|
| Abstraction | 고수준 제어, Implementor에 위임 |
| Refined Abstraction | Abstraction 확장 |
| Implementor | 구현의 공통 인터페이스 |
| Concrete Implementor | 구체적 구현 |

**적용**: 크로스 플랫폼 GUI, DB 드라이버 분리, 렌더링 엔진(OpenGL/DirectX), 메시지 전송 시스템

```typescript
interface Renderer { renderCircle(x: number, y: number, r: number): void; }
class SVGRenderer implements Renderer {
  renderCircle(x: number, y: number, r: number) { /* SVG */ }
}
class CanvasRenderer implements Renderer {
  renderCircle(x: number, y: number, r: number) { /* Canvas */ }
}
abstract class Shape {
  constructor(protected renderer: Renderer) {}
  abstract draw(): void;
}
class Circle extends Shape {
  constructor(renderer: Renderer, private x: number, private y: number, private r: number) {
    super(renderer);
  }
  draw() { this.renderer.renderCircle(this.x, this.y, this.r); }
}
```

| 장점 | 단점 |
|------|------|
| 독립적 확장, OCP/SRP | 구현 하나뿐일 때 과도 |
| 플랫폼 독립적 설계 | 초기 설계 비용 높음 |

**관련 패턴**: Adapter (사후 호환 vs 초기 분리), Abstract Factory (구현 객체 생성), Strategy (유사 구조, 행위 vs 구조)

---

## 3. Composite

**의도**: 트리 구조로 부분-전체 계층을 표현, 개별/복합 객체를 균일하게 처리.

**해결하는 문제**: 재귀적 합성 표현, 개별/복합 객체의 동일 처리.

| 참여자 | 역할 |
|--------|------|
| Component | Leaf/Composite 공통 인터페이스 |
| Leaf | 말단 노드, 실제 작업 수행 |
| Composite | 자식 Component 보유, 위임 |

**적용**: 파일 시스템, GUI 위젯 트리, 조직도, 메뉴 시스템, 수학 표현식 트리

```typescript
interface FSComponent {
  getName(): string;
  getSize(): number;
}
class File implements FSComponent {
  constructor(private name: string, private size: number) {}
  getName() { return this.name; }
  getSize() { return this.size; }
}
class Directory implements FSComponent {
  private children: FSComponent[] = [];
  constructor(private name: string) {}
  getName() { return this.name; }
  getSize() { return this.children.reduce((s, c) => s + c.getSize(), 0); }
  add(c: FSComponent) { this.children.push(c); }
}
```

| 장점 | 단점 |
|------|------|
| 재귀적 순회 자연스러움 | 타입 안전성 저하 |
| OCP, 클라이언트 단순화 | 깊은 계층 성능 이슈 |

**관련 패턴**: Iterator (순회), Visitor (노드별 연산), Flyweight (Leaf 공유), Chain of Responsibility (부모 전파)

---

## 4. Decorator

**의도**: 객체에 추가 책임을 동적으로 부여. 서브클래싱의 유연한 대안.

**해결하는 문제**: 상속 없이 런타임 기능 확장, final 클래스 기능 추가, 기능 조합 폭발 방지.

| 참여자 | 역할 |
|--------|------|
| Component | 공통 인터페이스 |
| Concrete Component | 기본 행위 구현 |
| Base Decorator | Component 참조 보유, 위임 |
| Concrete Decorator | 추가 행위 정의 |

**적용**: I/O 스트림(Java BufferedInputStream), 로깅/캐싱/인증 데코레이터, 압축/암호화 계층, UI 스크롤바/테두리

```typescript
interface DataSource {
  writeData(data: string): void;
  readData(): string;
}
class FileDataSource implements DataSource {
  constructor(private filename: string) {}
  writeData(data: string) { /* write */ }
  readData() { return ''; }
}
class DataSourceDecorator implements DataSource {
  constructor(protected wrappee: DataSource) {}
  writeData(data: string) { this.wrappee.writeData(data); }
  readData() { return this.wrappee.readData(); }
}
class EncryptionDecorator extends DataSourceDecorator {
  writeData(data: string) { super.writeData(`encrypted(${data})`); }
  readData() { return this.decrypt(super.readData()); }
  private decrypt(d: string) { return d.replace(/encrypted\((.+)\)/, '$1'); }
}
// 스택: new Compression(new Encryption(new FileDataSource('f.txt')))
```

| 장점 | 단점 |
|------|------|
| SRP/OCP, 런타임 동적 추가 | 데코레이터 수프 (복잡한 체인) |
| 상속 폭발 방지 | 디버깅 어려움 |
| 다양한 기능 조합 | 순서 의존적 동작 |

**관련 패턴**: Adapter (인터페이스 변환 vs 기능 추가), Proxy (접근 제어 vs 기능 추가), Strategy (내부 vs 외부 변경)

---

## 5. Facade

**의도**: 복잡한 서브시스템에 단순화된 통합 인터페이스 제공.

**해결하는 문제**: 다수 클래스를 직접 다루기 어려움, 서브시스템 간 결합도 감소.

| 참여자 | 역할 |
|--------|------|
| Facade | 요청을 서브시스템에 위임, 단순 인터페이스 |
| Subsystem Classes | 실제 기능 구현, Facade에 대해 무지 |
| Additional Facade | 복잡한 Facade 분할 |

**적용**: 컴파일러(`compile()`), 홈 시어터(`watchMovie()`), ORM, 빌드 시스템, 결제 시스템(`processPayment()`)

```typescript
class VideoDecoder { decode(f: string) { return `video(${f})`; } }
class AudioDecoder { decode(f: string) { return `audio(${f})`; } }
class Display { render(v: string, a: string) { /* play */ } }

class MediaPlayerFacade {
  private video = new VideoDecoder();
  private audio = new AudioDecoder();
  private display = new Display();
  playMovie(file: string) {
    this.display.render(this.video.decode(file), this.audio.decode(file));
  }
}
```

| 장점 | 단점 |
|------|------|
| 복잡성 은닉, 결합도 감소 | God Object 위험 |
| 가독성 향상 | 고급 기능 접근 제한 |

**관련 패턴**: Adapter (인터페이스 변환 vs 서브시스템 단순화), Mediator (객체 간 통신 vs 서브시스템 접근), Singleton (Facade를 Singleton으로)

---

## 6. Flyweight

**의도**: 공유를 통해 대량의 세밀한 객체를 효율적으로 지원. 메모리 최적화.

**해결하는 문제**: 대량 유사 객체의 과도한 메모리 소비.

**핵심: Intrinsic vs Extrinsic State**

| 구분 | Intrinsic (내재) | Extrinsic (외재) |
|------|-----------------|-----------------|
| 위치 | Flyweight 내부 | Client/Context |
| 공유 | 여러 객체 공유 | 객체마다 고유 |
| 변경 | 불변 | 가변 |
| 예시 | 글꼴, 문자 코드 | 위치, 크기, 색상 |

**적용**: 텍스트 에디터 글리프, 게임 나무/풀 모델, String Pool, 브라우저 이미지 캐시

```typescript
class TreeType {
  constructor(public readonly name: string, public readonly color: string) {}
  draw(x: number, y: number) { /* render */ }
}
class TreeFactory {
  private static types = new Map<string, TreeType>();
  static get(name: string, color: string): TreeType {
    const key = `${name}-${color}`;
    if (!this.types.has(key)) this.types.set(key, new TreeType(name, color));
    return this.types.get(key)!;
  }
}
class Tree {
  constructor(private x: number, private y: number, private type: TreeType) {}
  draw() { this.type.draw(this.x, this.y); }
}
```

| 장점 | 단점 |
|------|------|
| 메모리 대폭 절감 | 코드 복잡성 증가 |
| 확장성 향상 | 공유 데이터 적으면 오버헤드 |

**관련 패턴**: Composite (Leaf를 Flyweight로), Singleton (Factory를 Singleton으로)

---

## 7. Proxy

**의도**: 다른 객체에 대한 대리인을 제공하여 접근을 제어.

**해결하는 문제**: 지연 초기화, 접근 제어, 원격 대리, 캐싱, 로깅 필요.

**Proxy 종류**:

| 종류 | 목적 | 예시 |
|------|------|------|
| Virtual | 지연 초기화 | 이미지 Lazy Loading |
| Protection | 접근 제어 | 권한별 API 접근 |
| Remote | 원격 대리 | gRPC 클라이언트 |
| Caching | 결과 캐싱 | DB 쿼리 캐시 |
| Logging | 요청 기록 | 서비스 모니터링 |

```typescript
interface DatabaseService { query(sql: string): any[]; }

class RealDatabaseService implements DatabaseService {
  query(sql: string) { return [{ id: 1 }]; }
}

class CachingProxy implements DatabaseService {
  private cache = new Map<string, any[]>();
  constructor(private real: RealDatabaseService) {}
  query(sql: string) {
    if (this.cache.has(sql)) return this.cache.get(sql)!;
    const result = this.real.query(sql);
    this.cache.set(sql, result);
    return result;
  }
}
```

| 장점 | 단점 |
|------|------|
| 투명한 접근 제어 | 코드 복잡성 |
| OCP, 성능 최적화 | 간접 호출 지연 |

**관련 패턴**: Decorator (기능 추가 vs 접근 제어), Adapter (인터페이스 변환 vs 동일 인터페이스), Facade (서브시스템 단순화 vs 단일 객체 제어)

---

## 비교 요약

| 패턴 | 핵심 목적 | 인터페이스 변경 | 메커니즘 |
|------|----------|---------------|---------|
| Adapter | 인터페이스 호환 | O (변환) | 위임/상속 |
| Bridge | 추상화-구현 분리 | X | 합성 |
| Composite | 부분-전체 계층 | X | 재귀 합성 |
| Decorator | 동적 기능 추가 | X | 재귀 래핑 |
| Facade | 복잡성 은닉 | O (단순화) | 위임 |
| Flyweight | 메모리 최적화 | X | 객체 공유 |
| Proxy | 접근 제어 | X | 대리 위임 |

**래핑 패턴 구별 가이드** (Adapter/Decorator/Proxy):
- **Adapter**: 인터페이스를 **변환**한다. 기존 인터페이스를 다른 인터페이스로.
- **Decorator**: 인터페이스를 **유지**하면서 **기능을 추가**한다.
- **Proxy**: 인터페이스를 **유지**하면서 **접근을 제어**한다.
