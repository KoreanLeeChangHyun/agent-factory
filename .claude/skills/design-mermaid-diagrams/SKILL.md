---
name: design-mermaid-diagrams
description: Generates Mermaid diagrams covering flowcharts, sequence diagrams, class diagrams, ER diagrams, state diagrams, Gantt charts, and pie charts. Use when visualizing system architecture, data models, process flows, or relationship structures, and when output is needed as Mermaid code, HTML preview, PNG, or SVG.
license: "Apache-2.0"
---

# Mermaid Diagrams

Mermaid를 사용하여 다양한 다이어그램을 생성합니다.

## 사용 시기

- 플로우차트, 시퀀스 다이어그램이 필요할 때
- 클래스 다이어그램, ER 다이어그램을 그릴 때
- 상태 다이어그램, 간트 차트가 필요할 때
- 시스템 아키텍처를 시각화할 때
- 데이터 모델을 표현할 때

---

## 지원 다이어그램 타입

### 1. Flowchart (플로우차트)

```mermaid
flowchart TD
    A[시작] --> B{조건}
    B -->|Yes| C[처리1]
    B -->|No| D[처리2]
    C --> E[끝]
    D --> E
```

**방향 옵션:**
- `TD` / `TB` - 위에서 아래
- `BT` - 아래에서 위
- `LR` - 왼쪽에서 오른쪽
- `RL` - 오른쪽에서 왼쪽

#### 화살표 방향 필수 규칙

Flowchart에서 모든 연결선은 **반드시 방향(화살표)을 포함**해야 합니다. 방향이 없는 연결선은 금지합니다.

| 구분 | 문법 | 설명 | 허용 여부 |
|------|------|------|----------|
| 방향 실선 | `-->` | 실선 화살표 | 허용 |
| 방향 점선 | `-.->` | 점선 화살표 | 허용 |
| 방향 굵은선 | `==>` | 굵은 실선 화살표 | 허용 |
| 라벨 실선 | `-->\|텍스트\|` | 라벨 포함 실선 화살표 | 허용 |
| 라벨 점선 | `-.->\|텍스트\|` | 라벨 포함 점선 화살표 | 허용 |
| 라벨 굵은선 | `==>\|텍스트\|` | 라벨 포함 굵은 화살표 | 허용 |
| **무방향 실선** | `---` | 방향 없는 실선 | **금지** |
| **무방향 점선** | `-.-` | 방향 없는 점선 | **금지** |
| **무방향 굵은선** | `===` | 방향 없는 굵은선 | **금지** |

> **원칙**: 흐름도에서 연결선은 데이터/제어 흐름의 방향을 나타내야 합니다. 방향 없는 연결은 흐름의 의미를 모호하게 만들므로 항상 화살표(`-->`, `-.->`, `==>`)를 사용합니다.

### 2. Sequence Diagram (시퀀스 다이어그램)

```mermaid
sequenceDiagram
    participant A as Client
    participant B as Server
    participant C as Database

    A->>B: Request
    B->>C: Query
    C-->>B: Result
    B-->>A: Response
```

### 3. Class Diagram (클래스 다이어그램)

```mermaid
classDiagram
    class Animal {
        +String name
        +int age
        +makeSound()
    }
    class Dog {
        +bark()
    }
    Animal <|-- Dog
```

### 4. ER Diagram (엔티티 관계 다이어그램)

```mermaid
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE-ITEM : contains
    PRODUCT ||--o{ LINE-ITEM : includes
```

### 5. State Diagram (상태 다이어그램)

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Processing: start
    Processing --> Success: complete
    Processing --> Error: fail
    Success --> [*]
    Error --> Idle: retry
```

### 6. Gantt Chart (간트 차트)

```mermaid
gantt
    title 프로젝트 일정
    dateFormat YYYY-MM-DD
    section 기획
        요구사항 분석 :a1, 2024-01-01, 7d
        설계 :a2, after a1, 5d
    section 개발
        구현 :b1, after a2, 14d
        테스트 :b2, after b1, 7d
```

### 7. Pie Chart (파이 차트)

```mermaid
pie title 예산 분배
    "개발" : 45
    "마케팅" : 25
    "운영" : 20
    "기타" : 10
```

## 출력 형식

- **Markdown (.md)**: Mermaid 코드 블록
- **HTML**: 인터랙티브 프리뷰
- **PNG**: 이미지 파일
- **SVG**: 벡터 이미지

## 변환 방법

### CLI 도구 (mmdc)

```bash
# 설치
npm install -g @mermaid-js/mermaid-cli

# PNG 변환
mmdc -i diagram.mmd -o diagram.png

# SVG 변환
mmdc -i diagram.mmd -o diagram.svg

# 테마 적용
mmdc -i diagram.mmd -o diagram.png -t dark
```

### HTML 임베드

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
</head>
<body>
    <div class="mermaid">
        flowchart LR
            A --> B
    </div>
    <script>mermaid.initialize({startOnLoad:true});</script>
</body>
</html>
```

## 스타일링

```mermaid
flowchart TD
    A[시작]:::start --> B[처리]:::process
    B --> C[끝]:::end

    classDef start fill:#90EE90
    classDef process fill:#87CEEB
    classDef end fill:#FFB6C1
```

## 특수문자 처리

노드 라벨에 특수문자(`/`, `\`, `(`, `)`, `{`, `}` 등)가 포함되면 Mermaid 형상 구문과 충돌하여 파싱 에러가 발생할 수 있습니다.

> **기본 원칙**: 특수문자가 1개라도 포함되면 라벨을 큰따옴표(`"`)로 감싼다. 큰따옴표 래핑만으로 해결되지 않는 문자(`/`, `\` 등 라벨 시작 위치, `|`, `"`, `#`)는 HTML 엔티티로 추가 치환한다.

### 충돌 원인

Mermaid는 대괄호 안의 특정 문자를 형상(shape) 구문으로 해석합니다:

| 구문 | 형상 | 충돌 문자 |
|------|------|----------|
| `[/ /]` | 사다리꼴 (lean-right) | `/` |
| `[\ \]` | 역사다리꼴 (lean-left) | `\` |
| `(( ))` | 이중 원 | `(`, `)` |
| `[( )]` | 실린더 | `(`, `)` |
| `{ }` | 다이아몬드 | `{`, `}` |
| `[ ]` | 사각형 (rectangle) 등 노드 형상 | `[`, `]` |
| `\|...\|` | 엣지 라벨 구분자 | `\|` (PIPE 토큰으로 파싱) |
| `"..."` | 문자열 토큰 | `"` (STR 토큰과 충돌) |
| `\n` | 리터럴 문자열 | `\n` (개행이 아닌 리터럴로 인식) |

> **슬래시 커맨드 패턴 주의**: 슬래시 커맨드 패턴(`/command`)이 라벨 시작 위치에 올 때 `[/`가 lean-right 사다리꼴로 파싱되는 대표적 실수 사례입니다. 예를 들어 `B1[/cost - API 전용]`은 `/cost`가 명령어이지만 Mermaid는 `[/cost ... ]`를 사다리꼴 형상으로 해석합니다. 반드시 큰따옴표 래핑과 HTML 엔티티를 병용하세요.

### 잘못된 예시 vs 올바른 예시

| 잘못된 예시 | 문제 | 올바른 예시 (큰따옴표) | 올바른 예시 (HTML 엔티티) |
|------------|------|----------------------|------------------------|
| `E[/path/to/file]` | `[/`가 사다리꼴 형상으로 파싱됨 | `E["/path/to/file"]` | `E["#sol;path#sol;to#sol;file"]` |
| `F[C:\Users\docs]` | `[\`가 역사다리꼴 형상으로 파싱됨 | `F["C:\Users\docs"]` | `F["C:#bsol;Users#bsol;docs"]` |
| `G[func(arg)]` | `()`가 형상 구문과 혼동됨 | `G["func(arg)"]` | `G["func#lpar;arg#rpar;"]` |
| `H[.claude-organic/workflow/ 경로]` | 라벨 내 슬래시가 파서 혼동 유발 | `H[".claude-organic/workflow/ 경로"]` | `H[".workflow#sol; 경로"]` |
| `B1[curl\|bash 파이프]` | `\|`가 엣지 라벨 PIPE 토큰으로 파싱됨 | `B1["curl #124; bash 파이프"]` | - |
| `Q[사용자 질의\n"d80 에러"]` | `"`가 STR 토큰과 충돌, `\n`은 개행 아님 | `Q["사용자 질의<br>#quot;d80 에러#quot;"]` | - |
| `A[첫째 줄\n둘째 줄]` | `\n`이 리터럴로 표시됨 (줄바꿈 안 됨) | `A["첫째 줄<br>둘째 줄"]` | Markdown 문자열 방식도 가능 (해결 방법 3 참조) |
| `B1[/cost - API 전용]` | `[/`가 lean-right 사다리꼴로 파싱됨 | `B1["#sol;cost - API 전용"]` | `B1["#sol;cost - API 전용"]` |
| `C[desc.lower() 매칭]` | `(`가 PS 토큰으로 파싱, 형상 구문과 충돌 | `C["desc.lower() 매칭"]` | `C["desc.lower#lpar;#rpar; 매칭"]` |
| `D[list[0] 접근]` | 내부 `[0]`가 새 노드 형상 시작으로 파싱 | `D["list#lsqb;0#rsqb; 접근"]` | - |
| `E[키워드<br>kw in items[i]]` | 내부 `]`가 노드 라벨 종료로 오인 | `E["키워드<br>kw in items#lsqb;i#rsqb;"]` | - |
| `B2[/stats 통계]` | `[/`가 lean-right 사다리꼴로 파싱됨 | `B2["#sol;stats 통계"]` | `B2["#sol;stats 통계"]` |

### 해결 방법 1: 큰따옴표 래핑 (권장)

라벨 전체를 큰따옴표(`"`)로 감싸면 내부 문자가 리터럴로 처리됩니다.

```mermaid
flowchart TD
    A["#sol;sync:history 커맨드"] --> B[".claude-organic/workflow/ 경로"]
    B --> C["func(arg) 호출"]
```

### 해결 방법 2: HTML 엔티티

큰따옴표 래핑이 불가능한 경우 HTML 엔티티로 대체합니다.

| 문자 | HTML 엔티티 | 예시 |
|------|------------|------|
| `/` | `#sol;` | `#sol;path` |
| `\` | `#bsol;` | `C:#bsol;Users` |
| `(` | `#lpar;` | `func#lpar;` |
| `)` | `#rpar;` | `#rpar;` |
| `[` | `#lsqb;` | `list#lsqb;0#rsqb;` |
| `]` | `#rsqb;` | `list#lsqb;0#rsqb;` |
| `\|` | `#124;` | `curl #124; bash` |
| `"` | `#quot;` | `#quot;에러 메시지#quot;` |
| `#` | `#35;` | `#35;sol;` (엔티티 리터럴 표시) |

```mermaid
flowchart TD
    A["#sol;sync:history 커맨드"] --> B["C:#bsol;Users"]
```

### 해결 방법 3: Markdown 문자열

Mermaid v10.7+에서 지원하는 Markdown 문자열 구문(`` "`...`" ``)을 사용하면 **굵게**, *기울임*, 자동 줄바꿈을 라벨 안에서 직접 사용할 수 있습니다.

- `\n` 리터럴 대신 **실제 개행 문자**를 넣으면 줄바꿈으로 렌더링됩니다.
- 내부에서 Markdown 인라인 서식(**bold**, *italic*)을 그대로 사용할 수 있습니다.
- `<br>` HTML 태그 없이도 여러 줄 라벨을 작성할 수 있습니다.

```mermaid
flowchart TD
    A["`첫째 줄
둘째 줄`"]
    B["`**굵은 텍스트**와
*기울임 텍스트*`"]
    A --> B
```

> **참고**: Markdown 문자열 안에서는 `"`, `|` 등 특수문자도 이스케이프 없이 사용할 수 있습니다. 단, 백틱(`` ` ``)은 구문 종료 문자이므로 사용할 수 없습니다.

> **원칙**: 라벨에 특수문자가 포함될 때는 항상 큰따옴표로 감싸는 것을 기본으로 합니다. 라벨 시작이 `/`나 `\`인 경우에는 큰따옴표와 HTML 엔티티를 함께 사용합니다.

## 문법 검증 체크리스트

다이어그램 작성 후 아래 항목을 순서대로 검증합니다.

- [ ] 라벨에 특수문자(`/`, `\`, `(`, `)`, `[`, `]`, `{`, `}`, `|`, `"`) 포함 시 큰따옴표(`"`)로 래핑했는가
- [ ] 라벨이 `/` 또는 `\`로 시작하는 경우 HTML 엔티티(`#sol;`, `#bsol;`)로 치환했는가
- [ ] 라벨 내부에 대괄호(`[`, `]`)가 포함된 경우 반드시 `#lsqb;`, `#rsqb;`로 치환했는가 (큰따옴표만으로 해결 불가)
- [ ] 라벨에 코드 표현식(`func()`, `list[0]`, `a.b()` 등)이 포함된 경우 큰따옴표 래핑 + 괄호류 HTML 엔티티 치환을 병용했는가
- [ ] 노드 ID에 특수문자가 포함되지 않았는가 (ID는 영문+숫자+언더스코어만 허용)
- [ ] flowchart 연결선에 방향 화살표(`-->`, `-.->`, `==>`)를 사용했는가 (무방향 `---`, `-.-`, `===` 금지)
- [ ] 엣지 라벨에 파이프(`|`) 사용 시 `#124;`로 이스케이프했는가
- [ ] `\n` 리터럴 대신 `<br>` 또는 Markdown 문자열(`` "`...`" ``)을 사용했는가

### 슬래시 커맨드 오류 사례

슬래시로 시작하는 커맨드명(`/cost`, `/stats` 등)을 노드 라벨에 그대로 넣으면 Mermaid가 사다리꼴 형상으로 해석하여 Lexical error가 발생합니다.

**실제 오류 로그:**

```
Lexical error on line 6. Unrecognized text.
...B1[/cost - API 전용]-->C1[결과]
---^
```

**원인 분석:** `B1[/cost - API 전용]`에서 `[/`가 lean-right 사다리꼴 시작 토큰으로 인식됩니다. Mermaid는 `[/ ... /]` 패턴을 기대하지만 닫는 `/]`가 없으므로 Lexical error가 발생합니다. `/stats`, `/help`, `/sync` 등 모든 슬래시 커맨드 패턴에서 동일한 오류가 발생합니다.

**수정 전 (오류):**

```mermaid
flowchart TD
    A[입력] --> B1[/cost - API 전용]
    A --> B2[/stats 통계]
    B1 --> C[출력]
    B2 --> C
```

**수정 후 (정상):**

```mermaid
flowchart TD
    A[입력] --> B1["#sol;cost - API 전용"]
    A --> B2["#sol;stats 통계"]
    B1 --> C[출력]
    B2 --> C
```

> **수정 요점**: (1) 큰따옴표로 라벨 전체를 래핑하고, (2) 라벨 시작 위치의 `/`를 `#sol;`로 치환합니다. 두 조치를 반드시 함께 적용해야 합니다.

### 코드 표현식 오류 사례

노드 라벨에 코드 표현식(`desc.lower()`, `list[i]`, `kw in items[0]` 등)을 포함하면 괄호와 대괄호가 Mermaid 형상 토큰으로 파싱되어 Parse error가 발생합니다.

**실제 오류 로그:**

```
Parse error on line 4:
...키워드 매칭<br>desc.lower() in keyword.lower]
-----------------------^
Expecting 'SQE', ..., got 'PS'
```

**원인 분석:** `desc.lower()`의 `(`가 PS(Parenthesis Start) 토큰으로 인식됩니다. Mermaid 파서는 노드 라벨 `[...]` 안에서 SQE(Square bracket End, `]`)를 기대하지만 PS(`(`)를 만나 파싱에 실패합니다. 대괄호 `[]`가 중첩되는 `items[i]` 패턴에서도 내부 `[`가 새 노드 형상 시작으로 오인되어 동일한 문제가 발생합니다.

**핵심 규칙:** 코드 표현식을 라벨에 넣을 때는 **큰따옴표 래핑 + 괄호류 전량 HTML 엔티티 치환**을 병용해야 합니다. 특히 대괄호(`[`, `]`)는 큰따옴표 래핑만으로 해결되지 않으므로 반드시 `#lsqb;`, `#rsqb;`로 치환합니다.

**수정 전 (오류):**

```mermaid
flowchart TD
    A[입력] --> B[키워드 매칭<br>desc.lower() in keyword.lower]
    B --> C[결과 필터링<br>items[i] 접근]
    C --> D[출력]
```

**수정 후 (정상):**

```mermaid
flowchart TD
    A[입력] --> B["키워드 매칭<br>desc.lower#lpar;#rpar; in keyword.lower"]
    B --> C["결과 필터링<br>items#lsqb;i#rsqb; 접근"]
    C --> D[출력]
```

> **수정 요점**: (1) 큰따옴표로 라벨을 래핑, (2) `()`를 `#lpar;#rpar;`로, `[]`를 `#lsqb;#rsqb;`로 치환합니다. `()`는 큰따옴표 래핑만으로 동작하는 경우도 있지만, `[]`는 노드 형상 구분자와 직접 충돌하므로 HTML 엔티티 치환이 필수입니다.

## 참고 링크

- [Mermaid 공식 문서](https://mermaid.js.org/)
- [Mermaid Live Editor](https://mermaid.live/)
