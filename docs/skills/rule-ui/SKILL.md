---
name: rule-ui
description: Design, implement, or audit the Human-facing MCP cloud SaaS interface
  in this repository using its shared visual system. Use for Workspace screens, navigation,
  forms, connection flows, responsive layout, and UI consistency work here; do not
  use for generic web design or plugin UI.
metadata:
  document-type: specification
  category: rule
  domain: null
  name: ui
  language: ko
  provenance:
    prior-provenance: null
    merged-from:
    - docs/skills/rule-ui/SKILL.md
    - docs/skills/rule-ui/references/audit-checklist.md
    - docs/skills/rule-ui/references/design-rules.md
    - docs/skills/rule-ui/references/sidebar-assets.md
    - docs/skills/rule-ui/references/ui-components.md
    - docs/skills/rule-ui/references/ui-kit-api.md
    - docs/skills/rule-ui/references/workspace-ui.md
    - docs/mcp/packages/design-system/catalog/POLICY.md
    source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
    merge-request: run-20260918T152016183617Z-2d18ad49
    source-metadata:
      name: rule-ui
      description: Design, implement, or audit the Human-facing MCP cloud SaaS interface
        in this repository using its shared visual system. Use for Workspace screens,
        navigation, forms, connection flows, responsive layout, and UI consistency
        work here; do not use for generic web design or plugin UI.
---


# UI Rules

- Build one coherent Agent Factory interface: use a VS Code-shaped application shell, AWS Cloudscape-like content grammar, and Agent Factory's own neutral visual identity. References inform decisions; do not import Cloudscape packages, clone AWS styling, or introduce VS Code extension concepts.

<a id="authority-and-boundaries"></a>

## 1. Authority and boundaries

- Apply decisions in this order:

1. The user's explicit direction for the current task.
2. Existing Agent Factory information architecture, owner-backed semantics, and repository contracts.
3. This design system.
4. External reference systems.

- Keep this Skill Git-owned under `../docs/skills/`. It may later describe or call an MCP capability when that capability exists, but it must not invent tools, data, connection state, or lifecycle authority. Do not add a plugin, top-level Activity, tab, card, or navigation layer merely to accommodate this Skill.

<a id="choose-the-work"></a>

## 2. Choose the work

- For UI implementation or redesign, read [design-rules](#design-rules) and [workspace-ui](#workspace-ui) completely before editing.
- For shared controls or UI-kit adapters, also read [ui-components](#ui-components) and [ui-kit-api](#ui-kit-api).
- For sidebar design, implementation, or migration, read [sidebar-assets](#sidebar-assets) completely.
- For UI review or consistency cleanup, read [audit-checklist](#audit-checklist) completely and report evidence using its format.
- Read both when auditing and fixing the same surface.

<a id="working-method"></a>

## 3. Working method

1. Inspect the existing template, behavior, shared tokens, and focused tests before proposing a new pattern.
2. Preserve user workflows and owner-backed data. Simplify presentation without removing required capability.
3. Reuse `static/css/ui.css` for shared primitives and tokens. Keep feature-specific layout in its feature stylesheet.
4. Prefer the smallest shared abstraction that makes the same meaning look and behave the same everywhere.
5. Verify the affected states at desktop and narrow widths, then run focused runtime and browser tests.

- The target is a dense, calm developer tool: clear hierarchy, compact geometry, restrained decoration, consistent actions, and honest system state.

<a id="audit-checklist"></a>

## 4. audit-checklist

- Audit the requested scope against actual templates, styles, scripts, API behavior, and browser output. Absence of an obvious defect is not proof; collect direct evidence.

<a id="meaning-and-information-architecture"></a>

## 5. Meaning and information architecture

- Does each surface have one clear task and one clear primary action?
- Are navigation, page headings, and section headings non-duplicative?
- Is every displayed fact owner-backed, including connection and health status?
- Were required capabilities preserved while explanatory clutter was removed?

<a id="shared-visual-language"></a>

## 6. Shared visual language

- Search for hardcoded colors, spacing, heights, radii, borders, and shadows.
- Confirm common values are semantic tokens in `static/css/ui.css`.
- Find selectors that implement the same component differently across feature files.
- Check that primary, secondary, destructive, copy, icon, and disabled actions each have one grammar.
- Check that fields, code boxes, section headers, metadata, status, and list rows reuse shared geometry.

- Useful searches:

```sh
rg -n '#[0-9a-fA-F]{3,8}|rgb\(|hsl\(' static/css
rg -n '(margin|padding|gap|height|border-radius):[^;]*[0-9]+px' static/css
rg -n 'box-shadow|border-(top|right|bottom|left)' static/css
```

<a id="alignment-and-density"></a>

## 7. Alignment and density

- Compare left edges of headings, labels, fields, code boxes, and list content.
- Compare right edges and vertical centers of section actions.
- Verify one control height within a row and consistent gaps between related elements.
- Inspect for adjacent borders that form double lines.
- Confirm ordinary sections are not card-boxed or shadowed without semantic need.

<a id="responsive-and-overflow"></a>

## 8. Responsive and overflow

- Verify wide desktop, the minimum supported sidebar width, a narrow editor split, and mobile width.
- Confirm grids collapse without reordering the task.
- Test long workspace names, Korean labels, UUIDs, commands, token names, and error messages.
- Confirm only the owning code/table region scrolls horizontally.

<a id="interaction-and-accessibility"></a>

## 9. Interaction and accessibility

- Navigate every action by keyboard and confirm visible focus.
- Verify labels, accessible names, native titles for icon actions, semantic headings, lists, and tables.
- Confirm selection and status are not communicated by color alone.
- Exercise loading, empty, normal, error, permission, disabled/busy, and success states that apply.
- Check that buttons do not move when labels or states change.

<a id="api-backed-workflows"></a>

## 10. API-backed workflows

- Confirm the request method and route match the backend contract.
- Verify successful persistence by reloading from the authoritative API or database-facing repository test.
- Distinguish validation errors, authentication/authorization failures, missing routes, and empty results.
- Do not treat a passing static UI test as proof that persistence works.

<a id="evidence-format"></a>

## 11. Evidence format

- Record each issue as:

```text
[severity] Rule — observable problem
Evidence: file:line, response/status, or browser geometry/state
Fix: smallest shared correction
Verification: focused test or browser assertion
```

- Finish with the commands run, viewport/state coverage, remaining risks, and any intentionally unresolved owner decision. A broad consistency claim requires browser evidence across every affected surface, not one screenshot or one page.

<a id="design-rules"></a>

## 12. design-rules

<a id="product-expression"></a>

## 13. Product expression

- Use this formula consistently:

- **Structure:** VS Code — Activity Bar, Primary Sidebar, Workspace area, compact tool chrome.
- **Content grammar:** AWS Cloudscape — predictable resource summaries, forms, tables, ordered tasks, and explicit states.
- **Identity:** Agent Factory — neutral dark surfaces, restrained blue interaction accents, compact Korean developer-tool copy.

- Reference systems are decision aids, not component dependencies or visual skins.

<a id="shell-and-navigation"></a>

## 14. Shell and navigation

- Preserve the repository's decided Workspace information architecture and exact Activity order.
- One navigation choice owns one sidebar view and one main Workspace view.
- Do not duplicate a navigation label as an in-content heading unless it adds essential context.
- Put item disclosure beside the item label and right-align row-level actions in a stable action slot.
- Use tabs only when content groups are independent and each supports a distinct task. Otherwise keep one continuous page.
- Keep the main workflow visible together when users must compare or complete its parts in sequence.

<a id="page-and-section-composition"></a>

## 15. Page and section composition

- Use this default sequence when applicable:

1. Compact page or panel header.
2. Resource identity and status summary.
3. Controls needed to choose a context.
4. Numbered action steps.
5. Result, history, or secondary management.

- A section header places the title on the left and its single primary local action on the right.
- A field places its label above the control. Related fields share a baseline and control height.
- An action step uses number → title/action → one short instruction → value or result.
- A code operation uses title/action → code box → optional one-line help.
- A list item uses identity and metadata on the left, local action on the right.
- Render state as a concise label, adding a status dot only when it improves scanning. Never rely on color alone.

<a id="resource-presentation-choices"></a>

## 16. Resource presentation choices

- Use a definition-list summary for one resource's stable metadata.
- Use a table for multiple resources with comparable fields, sorting, or scanning needs.
- Use cards only for small sets whose important attributes do not form useful columns.
- Use split view only when users must preserve list context while inspecting or troubleshooting one item.
- Prefer an all-at-once details page when the content fits and users benefit from comparison across sections.

<a id="tokens-and-geometry"></a>

## 17. Tokens and geometry

- Shared tokens belong in `static/css/ui.css`. Feature styles consume them rather than defining substitutes.

- Spacing scale: 4, 8, 12, 16, and 24 px. Use 32 px only for a deliberate page-level separation.
- Use one standard control height and one compact control height.
- Use a small common control radius. Do not create component-specific radii without semantic need.
- Use 1 px borders for real boundaries. Avoid stacked borders that render as double lines.
- Desktop resource summaries normally use three equal columns; use two when the content needs width and one at narrow sizes.
- Preserve DOM and task order when the layout collapses.

<a id="color-and-emphasis"></a>

## 18. Color and emphasis

- Use neutral surfaces for the application background, sidebar, work area, controls, and bounded code/table content.
- Reserve blue for primary actions, selection, focus, and links. Do not use it as decoration.
- Use semantic colors only for actual success, warning, and error states, always paired with text or an icon.
- Solid filled actions represent the highest-priority action in the current scope. Nearby actions remain neutral.
- Shadows are for overlays such as menus, dialogs, and transient notices—not ordinary sections.
- Use dividers sparingly and only once between actual regions or repeated rows.

<a id="components-and-interaction"></a>

## 19. Components and interaction

- The same semantic action uses the same label, height, border, color, and placement.
- Native controls must have visible labels. Icon-only buttons require an accessible name and native title.
- Place select indicators at the trailing edge with enough padding that text cannot collide with them.
- Code and long identifiers own their overflow. Do not force the whole page to scroll horizontally.
- Provide visible focus and keyboard operation for every interactive element.
- Disabled controls must be visibly disabled and remain distinguishable from loading or permission failure.
- Do not make non-interactive rows look clickable.

<a id="content-and-states"></a>

## 20. Content and states

- Write direct, task-oriented Korean. Delete introductions that repeat the heading or explain the obvious.
- Keep one instruction per step. Prefer “설정 파일을 다운로드해 프로젝트 디렉터리에 넣으세요.” over background prose.
- Use consistent nouns for the same entity and consistent verbs for the same action.
- Every data surface must deliberately handle loading, empty, normal, error, permission-denied, disabled/busy, and success states as applicable.
- Show only owner-backed state. Never infer that an integration is connected or healthy from local configuration alone.

<a id="mcp-connection-flow"></a>

## 21. MCP connection flow

- Automated connection is exactly four visible steps:

1. Issue or select a personal authentication token.
2. Download one ZIP containing every supported client configuration.
3. Copy the AI instructions and give the ZIP and instructions to the AI.
4. Check for actual MCP connection evidence.

- Do not require a client or environment choice in the browser. Client-specific configuration, registration commands, paths, and documentation belong in the ZIP. Token management is a secondary region and follows the same section, control, and list grammar.

<a id="responsive-behavior"></a>

## 22. Responsive behavior

- Start with the desktop information hierarchy, then reduce columns without changing meaning or order.
- At narrow widths, stack controls and actions before compressing labels or hit targets.
- Keep sidebar labels visible throughout the supported resize range.
- Test long Korean labels, identifiers, commands, token names, and error messages at each supported width.

<a id="sources"></a>

## 23. Sources

- VS Code UX overview: https://code.visualstudio.com/api/ux-guidelines/overview
- VS Code views: https://code.visualstudio.com/api/ux-guidelines/views
- VS Code sidebars: https://code.visualstudio.com/api/ux-guidelines/sidebars
- VS Code panels: https://code.visualstudio.com/api/ux-guidelines/panel
- VS Code theme colors: https://code.visualstudio.com/api/references/theme-color
- Cloudscape resource details: https://cloudscape.design/patterns/resource-management/details/
- Cloudscape resource view: https://cloudscape.design/patterns/resource-management/view/
- Cloudscape split view: https://cloudscape.design/patterns/resource-management/view/split-view/
- Cloudscape design tokens: https://cloudscape.design/foundation/visual-foundation/design-tokens/
- Cloudscape spacing: https://cloudscape.design/foundation/visual-foundation/spacing/
- Cloudscape visual style: https://cloudscape.design/foundation/visual-foundation/visual-style/

<a id="sidebar-assets"></a>

## 24. sidebar-assets

<a id="합의된-방향"></a>

## 25. 합의된 방향

- 사이드바는 작업마다 정보 구조와 표현이 달라질 수 있다. 하나의 완성된 사이드바를 모든 작업에 강제하지 말고, 작은 공통 에셋을 조합해 각 작업의 사이드바를 구성한다.

- 작업 목록은 최상위 작업을 전환하고, 사이드바는 선택한 작업의 탐색·목록·보조
  동작을 표시하며, 패널은 선택한 대상의 주 콘텐츠를 표시한다.
- 기본 사이드바는 하나의 공통 호스트를 사용하고 작업 전환 시 내부 뷰만 바꾼다.
  작업마다 별도 `aside`나 별도 셸 위치 규칙을 만들지 않는다.
- 공통 에셋은 구조, 시각 문법, 상태 표현, 키보드와 접근성을 소유한다.
- 각 작업은 데이터 조회, 권한, 선택 의미, 네트워크 동작, 기능별 생명주기를 소유한다.
- 사용자 작성기가 일반적인 SaaS 작업을 코드 없이 구성할 수 있도록 목록, 그룹, 트리,
  검색, 필터, 상세 행, 상태와 보조 동작을 여러 공통 에셋으로 계획해서 제공한다.
- 같은 의미의 중복 변형은 만들지 않고 한 작업에만 필요한 표현은 기능별 컴포넌트와 스타일로 유지한다.
- 공통 토큰과 프리미티브는 `static/css/ui.css`, 편집 가능한 에셋 소스는
  `assets/ui-kit/`, 제품 산출물은 `static/ui/`에 둔다. 생성 산출물을 직접 수정하지 않는다.

<a id="공통-에셋-범위"></a>

## 26. 공통 에셋 범위

- 구현 전 기존 에셋을 먼저 확인하고, 이미 있는 계약을 확장한다. 기본 후보는 다음과 같다.

| 영역 | 공통으로 소유할 내용 | 작업이 소유할 내용 |
| --- | --- | --- |
| 호스트 | 헤더·스크롤 본문·뷰 전환·열림 상태 | 작업별 제목과 헤더 동작 |
| 섹션 | 제목·접기/펼치기·동작 슬롯 | 섹션 구성과 노출 조건 |
| 탐색 행 | 선택·hover·focus·말줄임·우측 슬롯 | 라벨·메타데이터·실행 동작 |
| 상세 행 | 제목·설명·배지·보조정보 배치 | 표시할 도메인 상태 |
| 트리 | 계층 ARIA·키보드·disclosure·선택 | 계층 데이터·아이콘·도메인 동작 |
| 검색·필터 | 입력 배치·접근 가능한 라벨·상태 | 검색 기준·필터 의미·조회 |
| 상태 | 로딩·빈 상태·오류·권한 없음·처리 중 | 서버 응답의 상태 판정 |
| 하단 영역 | 고정 배치와 경계 | 작업별 보조 동작 |
| 크기 조절 | 포인터·키보드·최소/최대 너비 | 작업별 기본 열림 여부 |

- `bindSidebarHost`, `app-sidebar__*`, `af-sidebar-*`, `explorerTree`, 공통 상태와 리사이저 어댑터가 현재 출발점이다. 새 이름이나 병렬 구현을 만들기 전에 이 계약으로 표현할 수 있는지 확인한다.

<a id="작업-목록"></a>

## 27. 작업 목록

<a id="현황표-작성"></a>

### 27.1. 현황표 작성

- 조직, 작업공간, 일정, 에이전트, 문서, 연동, 로그, 테스트, 데이터베이스, 계정,
  관리자 사이드바의 구조와 상태를 조사한다.
- 각 화면에서 사용하는 헤더, 섹션, 평면 목록, 상세 목록, 트리, 검색, 필터, 배지,
  행 동작, 하단 영역을 기록한다.
- 기존 공통 에셋 사용 여부, 기능별 예외, 중복 구현, 테스트 범위를 구분한다.

<a id="카탈로그-범위-결정"></a>

### 27.2. 카탈로그 범위 결정

- 현재 작업의 반복 요소와 고객이 조합할 일반적인 SaaS 탐색 패턴을 함께 공통 후보로 확정한다.
- 각 공개 에셋에 안정적인 버전 ID, 속성 schema, 지원 상태·동작, 접근성 계약, 예제와 미리보기를 둔다.
- 공통 에셋이 DOM 데이터 속성, 이벤트 위임, API payload 또는 포커스 복원을
  깨뜨리지 않는지 확인한다.
- 작업별 디자인 차이를 없애기 위한 추상화는 만들지 않는다.

<a id="에셋-보강"></a>

### 27.3. 에셋 보강

- 필요한 경우 헤더 동작 슬롯, 상세 행, 검색·필터, 상태, 하단 영역을 작은 단위로 추가한다.
- 모든 상태는 정상, 로딩, 빈 상태, 오류, 권한 없음, 비활성 또는 처리 중을 필요한
  범위에서 표현한다.
- 아이콘 전용 버튼은 접근 가능한 이름과 `title`을 제공하고, 선택 상태는 색상 이외의
  의미와 적절한 `aria-current`, `aria-selected` 또는 `aria-pressed`를 사용한다.

<a id="작업별-적용"></a>

### 27.4. 작업별 적용

- 평면 탐색 화면부터 적용한 뒤 상세 목록, 계층형 탐색 순서로 진행한다.
- 기존 사용자 흐름과 작업별 생명주기를 보존한다.
- 기능별 CSS에는 계층, 추가 메타데이터, 기능 고유 상태만 남기고 공통 시각 속성은
  공통 토큰과 에셋으로 이동한다.

<a id="검증과-기록"></a>

### 27.5. 검증과 기록

- 180px, 268px, 520px 사이드바와 390px 좁은 화면에서 긴 한국어 이름, 넘침,
  스크롤, 포커스를 확인한다.
- 마우스와 키보드 전환, 선택·접힘·너비 복원, 작업 전환 후 정리, 동적 렌더링을 확인한다.
- 변경한 공통 에셋의 단위 검증, Workspace 계약 테스트, 영향을 받는 작업별 브라우저
  회귀 테스트를 실행한다.
- `assets/ui-kit/`을 변경했다면 제품 에셋을 빌드하고 동기화 검사를 실행한다.
- 완료된 적용과 아직 검증하지 않은 상태·브라우저·실환경 범위를 구분해 기록한다.

<a id="완료-기준"></a>

## 28. 완료 기준

- 모든 작업은 하나의 사이드바 호스트 안에서 자기 뷰를 구성한다.
- 공통 의미와 상호작용은 공통 에셋을 사용하지만 작업별 정보 구조는 유지된다.
- 기능별 스타일이 공통 배경, 경계, 타이포그래피, 선택, hover, focus를 다시 선언하지 않는다.
- 동적 항목도 정적 항목과 같은 공통 계약과 접근성 상태를 사용한다.
- 변경 범위의 데스크톱·좁은 화면·키보드·상태 회귀 검증이 통과한다.

<a id="ui-components"></a>

## 29. ui-components

- `static/css/ui.css` owns shared tokens and primitives. Feature CSS owns layout, including document splits, timeline tracks, sidebar indentation and responsive composition. Workspace and login both load the shared stylesheet. No framework or component runtime is required: static HTML, DOM builders and HTML-string renderers use the same classes.

<a id="actions-and-navigation"></a>

## 30. Actions and navigation

| Class | Use |
| --- | --- |
| `ui-button` | Secondary action, refresh, retry, copy |
| `ui-button ui-button--primary` | The main submit/complete action in a scope |
| `ui-button ui-button--danger` | Delete, revoke or disconnect |
| `ui-button ui-button--link` | Text/statistic action; no filled background |
| `ui-button ui-button--icon` | Square action; requires accessible name and title |
| `ui-button ui-button--compact` | Compact toolbar action |
| `ui-tabs` and `ui-tab` | Navigation; independent of action button styling |
| `ui-resource-row` | Selectable resource with identity and metadata |
| `app-sidebar__*` | Sidebar headers, sections, disclosure, rows and selection |

- Use native `button` elements for actions. State comes from native `disabled`, `aria-busy`, and the appropriate `aria-current`, `aria-selected` or `aria-pressed` attribute. Do not add `ui-button` to sidebar rows or tabs. Selection must have a non-color cue and an accessible state.

- Never style all buttons beneath a feature container in shared CSS. In particular, a mixed `:is()` list takes the highest specificity of any member; adding a dialog footer to such a list can override unrelated statistic or tab styles. Avoid using extra selector specificity to repair component conflicts.

- Organization's DOM builder accepts an explicit button variant; planning's builder preserves additional layout classes without emitting duplicate class attributes. Form submit variants are explicit. Labels or API responses must not be parsed to infer a button's role.

<a id="fields-messages-and-sections"></a>

## 31. Fields, messages and sections

- Native text inputs, selects and textareas inside Workspace, dialogs and login share control geometry. `ui-field` places a visible label above the control. Use `ui-field__help` for help and connect it with `aria-describedby` when it is needed to understand an input. Associate field errors with the affected field; use form-level errors when the server does not identify a field.

- `ui-message` owns text wrapping and message typography. Use `role="alert"` for errors and `role="status"` for nonurgent asynchronous feedback. `ui-message--muted`, `--error`, and `--success` express known state. Empty messages collapse; `ui-message--reserved` deliberately reserves a text line. Do not apply reserved space to every empty sidebar list. Planning's compact dashboard retains its existing fixed message slot to keep toolbar geometry.

- `ui-section-header` aligns a heading and its actions and permits wrapping. Feature-specific headers may retain geometry when needed for timeline or editor alignment; they consume shared font and spacing tokens.

- Async forms must prevent duplicate submission and restore controls after a failure. Set `aria-busy="true"` on the form or submit button while awaiting the operation. The busy indicator changes the button background without changing its width or replacing its label. Never re-enable a control that was disabled for an independent permission or validation reason. Existing confirmation dialogs and destructive-operation validation remain functional requirements.

<a id="tokens-and-deliberate-exceptions"></a>

## 32. Tokens and deliberate exceptions

- Shared palette, font, spacing, focus, radius and overlay tokens live in `ui.css`. Existing shell color names remain stable aliases for consumers; their definitions no longer live in `workspace.css`. Use 30px default and 22px compact controls. Feature CSS can set the control token locally.

- Editor tab-close, tree-disclosure and title-bar chrome retain their specialized hit geometry. Timeline coordinates, chart/status fills, avatar circles, document/PDF paper backgrounds and Google sign-in branding are not generic action-button or surface tokens. Login can retain its centered page composition while using the same native fields and password-login action as Workspace. Embedded Document package styles remain owned by the Document, not this shell.

<a id="verification"></a>

## 33. Verification

- Run the shared cascade/state regression and relevant real screen flows:

```sh
NODE_PATH=/tmp/af-pw/node_modules node tests/design_system/browser/ui-components.cjs
NODE_PATH=/tmp/af-pw/node_modules node tests/design_system/browser/ui-screens.cjs
NODE_PATH=/tmp/af-pw/node_modules node tests/organizations/browser/organizations.cjs
NODE_PATH=/tmp/af-pw/node_modules node tests/workspaces/browser/workspace-start.cjs
NODE_PATH=/tmp/af-pw/node_modules node tests/planning/browser/planning.cjs
NODE_PATH=/tmp/af-pw/node_modules node tests/connections/browser/mcp-onboarding.cjs
NODE_PATH=/tmp/af-pw/node_modules node tests/knowledge/browser/document-editor.cjs
DOCUMENT_HEADERS_ONLY=1 NODE_PATH=/tmp/af-pw/node_modules node tests/knowledge/browser/document-editor.cjs
.venv/bin/pytest -q tests/workspaces/regression/test_workspace_ui.py
.venv/bin/pytest -q tests/reporting/browser/reporting.py
```

- `NODE_PATH` must point to the local installation of Playwright; the path above is this development environment's installation, not a production dependency. The component test loads the shipped stylesheet order in seven feature hosts and exercises actual login HTML/JS with mocked authentication responses. Screen flow tests use mocked APIs and do not prove database persistence. Verify desktop and narrow widths, long Korean text, keyboard focus, disabled, busy, empty and error states when changing a shared primitive.

- The header-only document test compares all three explorer action columns at 180, 268 and 520px sidebar widths. Shared sidebar header defaults use `:where` so a feature's explicit grid layout survives without a specificity escalation.

- Two existing fixtures were brought in line with current contracts: the document download fallback uses an unsupported binary MIME type rather than ZIP (which now has a package preview), and the reporting fixture returns an empty array for the Workspace groups endpoint. ZIP previews have separate delivery tests.

<a id="ui-kit-api"></a>

## 34. ui-kit-api

- 이 키트는 제품 적용 전 독립 에셋이다. 현재 검증 범위는 [SCOPE.md](../../../docs/processed/process-ui-kit-scope/SKILL.md)와 `assets/ui-kit/tests/verify-*.cjs`에 기록한다. 생성 함수의 존재만으로 모든 상태가 검증됐다고 해석하지 않는다.

<a id="로딩과-소유권"></a>

## 35. 로딩과 소유권

1. static/css/ui.css
2. assets/ui-kit/generated/vendors.css
3. assets/ui-kit/styles/theme.css
4. `assets/ui-kit/src/components/`의 필요한 프로젝트 ES module

- 소유 컨테이너에 af-kit을 지정한다. 기존 공통 버튼·입력 스타일 범위를 사용하는 경우 workspace-shell도 함께 지정한다. 외부 native/reset CSS는 사용하지 않는다. 컴포넌트 데이터·권한·네트워크 작업은 호출자가 소유한다.

<a id="기본-컨트롤"></a>

## 36. 기본 컨트롤

- primitives.js: button({label,variant,compact,disabled,onClick}) → button DOM. variant는 secondary/primary/danger/link.
- 반환한 버튼의 setBusy(boolean)은 크기와 원래 비활성 상태를 보존하면서 aria-busy·처리 중 표시를 전환한다.
- field({label,type,value,help,required,disabled,options}) → {root,control,setError(message)}. type textarea/select는 해당 native 요소를 생성한다.
- toggle({label,type,checked,disabled,name,value}) → {root,control}. type checkbox/radio/switch.
- status({kind,text}), badge(text,kind), skeleton({label,lines}), sectionHeader(title,action) → DOM.
- icons.js: icon(name,{size}) → 장식용 SVG. size 14/16/24. iconButton(name,label,onClick)은 접근 가능한 이름과 title을 가진 버튼이다.
- navigation.js: buttonGroup(label,...buttons) → 이름 있는 액션 그룹. roving tabindex toolbar가 아니라 일반 Tab 순서다.

<a id="레이아웃"></a>

## 37. 레이아웃

- layouts.js 함수는 외부 HTML 문자열이 아닌 DOM 노드를 받는다.

- stack/inline/grid(...children), divider()
- pageLayout({title,description,actions,content})
- listDetailLayout({list,detail})
- collectionLayout({header,filters,content,pagination})
- settingsLayout({navigation,form,actions})
- metadataList([[label,value],...]), resourceRow({title,description,action})
- `af-workbench-panel`은 기본 사이드바와 메인 작업영역이 공유하는 셸 표면이다.
  고정 헤더는 `af-workbench-panel__header`, 독립 스크롤 본문은
- `af-workbench-panel__body`를 함께 사용한다. 간격과 모서리는 `--ui-workbench-panel-gap`, `--ui-workbench-panel-radius` 토큰을 따른다.
- sidebar-host.js `bindSidebarHost(host,{header,body,title,items,defaultTitle})` →
  `{host,views,select,selected,destroy}`. 하나의 기본 사이드바 호스트 안에서 도메인별
- 뷰를 전환하고 제목과 `hidden` 상태를 함께 갱신한다. 각 item은 고유 id/title/element를 제공한다. 호스트에는 공통 `af-kit`·`af-sidebar-host`, 뷰에는 `af-sidebar-view`를 적용한다. 기존 사이드바의 섹션·섹션 헤더·본문·탐색·행·상태는 대응하는 `af-sidebar-*` 공통 요소로 채택하며, 이후 동적으로 렌더되는 항목도 같은 계약을 따른다. 평면 탐색 행은 오른쪽 공통 탐색 표시 슬롯을 사용하고, 상태 문구는 공통 상태 표면으로 표시한다. 기존 버튼 노드와 이벤트·데이터 속성은 교체하지 않는다. 데이터 조회와 도메인별 헤더 동작은 호출자가 소유한다.

<a id="입력탐색"></a>

## 38. 입력·탐색

- explorer-tree.js `explorerTree({label,items,multiSelect,onSelect,onActivate,onToggle,onRender,renderIcon})` → `{root,destroy}`.
  계층 탐색의 우선 공통 에셋이다. 22px 행·12px 들여쓰기·항목 아이콘·긴 이름
- 말줄임·계층 안내선을 사용한다. item은 고유 id/label, 선택적 children/expanded/disabled/selected다. 기본 renderIcon은 Material Icon Theme 5.38.1 원본이며 공식 파일명·확장자·폴더명 매핑을 사용한다. 다른 리소스 계층은 renderIcon 콜백으로 항목 종류에 맞는 Node를 제공하거나 아이콘을 생략할 수 있다. 현재 묶음에서 지원하지 않는 이름에는 공식 기본 file/folder 아이콘을 사용한다. 선택 행은 회색 배경, 포커스 행은 파란 테두리로 표시하고 초기 selected는 콜백을 호출하지 않는다. children이 있으면 폴더다. 폴더의 `toggleOnClick=false`는 행/Enter 선택과 disclosure 토글을 분리한다. 방향키·Home/End·Enter·Space, Ctrl/Meta 다중 선택, Shift 범위 선택을 제공한다. 권한 없는 항목은 선택/활성화하지 않는다. `multiSelect=false`는 단일 선택 트리로 사용하며, `selectable=false`인 폴더는 펼침만 허용한다. onSelect는 선택 ID 배열, onActivate는 활성화할 항목 ID를 받으며 네트워크 요청을 수행하지 않는다. onToggle은 항목 ID와 펼침 상태를 받고, onRender는 렌더링할 때마다 현재 행을 받아 소유자가 드래그·메뉴 같은 도메인 동작을 다시 연결할 수 있게 한다. 데이터 갱신 시 소유자가 destroy 후 새 투영을 생성한다. 기존 renderNativeTree와 bindTreeKeyboard를 재사용한다. 원본 아이콘의 색상·도형과 MIT 고지를 보존한다.

- components.js createCombobox(labelledSelect,{multiple,load,onError,...settings}) → {control,setDisabled,setInvalid,destroy}. load(query,{signal})은 [{value,text}]를 반환하는 Promise다. 옵션 텍스트는 이스케이프한다.
- createSplitPane(root,{id,size,orientation,onResize,storageKey,label,keyboardResizeBy}) → {machine,setSizes,destroy}. root 직계 자식으로 data-af-panel 2개와 data-af-resizer 1개를 제공한다. id는 인스턴스별 고유해야 한다. 저장은 선택적이며 권한·데이터 상태를 저장하지 않는다.
- tabs({label,items,onChange}) → {root,select(index),selected}. 각 item은 id/label/content/disabled다. 수평·자동 활성화 탭이며 방향키·Home/End가 비활성 항목을 건너뛴다.
- breadcrumb([{label,href},...]) → nav. 마지막 항목은 현재 페이지다.
- pagination({total,pageSize,page,onChange}) → {root,setPage,setTotal,page}. 서버 데이터 요청은 호출자 책임이다.
- searchField({label,onSearch}) → field 계약. IME 조합 중간값은 검색 콜백으로 보내지 않는다.

<a id="오버레이알림"></a>

## 39. 오버레이·알림

- compositions.js의 resourceCollection({rows,pageSize})는 검색·유형 필터·목록/상세·페이지 이동을 조합한다. row는 id/title/kind/description이며 kind는 document/connection이다. setRows로 소유 데이터의 새 투영을 전달한다.

- settingsForm({initial,save})은 save(value,{signal})의 성공 응답을 받은 뒤에만 저장된 기준값을 갱신한다. 취소는 마지막 승인값으로 되돌린다. destroy는 미완료 저장을 취소한다.

- popovers.js createPopover(trigger,content,{menu}) → {open,close,destroy}. native popover top layer와 Floating UI 위치 계산을 사용한다. menu=true면 평면 menuitem 버튼을 제공해야 한다. 중첩 메뉴는 별도 범위다.
- overlays.js await createOverlay(waDialogOrDrawer) → {element,open(trigger),close,destroy}. 요소에 label이 필요하다.
- await createConfirmDialog(host,{title,message,confirmLabel,destructive}) → {element,ask(trigger),destroy}. ask는 명시적 승인만 true, 취소/Escape는 false를 반환한다. 동시에 두 요청을 열지 않는다.
- toasts.js createToastManager(host,{id,max}) → {show,update,dismiss,destroy,store}. show는 id를 반환한다. 같은 id는 갱신하며 오류/진행은 기본 지속, 나머지는 기본 5초다. 완료 전 상태를 success로 갱신하지 않는다.
- Tooltip은 wa-tooltip for="trigger-id"로 연결한다. 상호작용 가능한 내용은 Tooltip이 아니라 Popover를 사용한다.

<a id="업로드시간"></a>

## 40. 업로드·시간

- uploads.js createUploadQueue(host,{transport,maxFileSize,maxNumberOfFiles,allowedFileTypes}) → {uppy,add,destroy}.
- transport(file,{signal,onProgress})은 실제 서버 수락 후 resolve, 실패 시 reject해야 한다. onProgress(bytesUploaded,bytesTotal)를 호출하고 signal 취소를 준수한다.
- 카탈로그의 transport는 명시적인 로컬 시뮬레이션이며 제품 전송기로 사용하지 않는다.
- transport.js의 xhrTransport({endpoint,fieldName,headers,withCredentials,timeout})은 명시적으로 전달한 HTTP(S) 주소에 multipart POST를 수행한다. 기본 withCredentials는 false이고, 성공 JSON/빈 응답만 resolve한다. HTTP 오류·잘못된 JSON·시간초과·취소는 reject한다. 제품 CSRF/인증·저장 계약은 호출자 소유다.
- relative-time은 ISO datetime을 받고, 옆의 time 요소로 절대 시각을 함께 제공한다. 상대 시각은 연결 상태·실행 성공의 근거가 아니다.

<a id="정리와-라이선스"></a>

## 41. 정리와 라이선스

- web-components.js는 tooltip(trigger,text)을 제공하며 destroy로 제거한다. Web Awesome 기본 아이콘 공급원은 CDN 대신 키트의 로컬 SVG data URL로 고정했다.

- 아이콘 추가: vendor/tabler에 같은 고정 커밋의 검토된 SVG를 넣고 npm run build를 실행한다. 다른 출처/버전을 추가할 때는 build.mjs의 provenance 생성도 해당 출처에 맞춰 확장해야 한다. 원 저작권 고지는 유지한다.

- DOM 소유 화면을 제거할 때 제공되는 destroy를 호출한다. 운영 코드에 연결할 때 실제 화면 재진입·교체·중첩 모달·권한 변화 회귀 검증이 필요하다. generated/licenses, vendor/tabler/LICENSE, 생성 번들의 legal notices와 provenance를 함께 배포한다.
<a id="제품용-경량-어댑터"></a>

## 42. 제품용 경량 어댑터

- `resourceTable({headers, rows, emptyText})`는 스크롤 래퍼와 semantic table을 반환한다. headers는 열 제목, rows는 셀 배열이다. Node 셀은 그대로 이동하여 이벤트를 보존하고, 그 외 값은 text node로 표시한다. 정렬·페이지·가상화·권한 판단은 소유자 책임이다.

- `menuKeyboard({items, close})`는 keydown 핸들러를 반환한다. items()는 현재 메뉴 항목 DOM 배열, close(true)는 닫기 및 원래 포커스 복귀를 소유자에게 요청한다. 위치 계산·클릭·DOM 제거·listener 설치/해제는 소유자 책임이다.

- `setStatus(element, {kind, text})`는 기존 live region 노드의 참조와 data 속성을 유지하면서 공통 상태 스타일·role·busy를 갱신한다. 빈 text는 숨기며 loading을 벗어나면 aria-busy를 제거한다. kind 판단은 호출자가 서버 응답에 따라 명시한다. `af-metadata-grid`는 기존 dl > div > dt/dd용 3열/좁은 폭 1열 공통 레이아웃이다.

- `bindTabs({list, items, onChange, initial, notifyInitial})`는 기존 DOM을 유지한다. items는 `{id, button, panel}` 배열이다. `select(index, focus, notify)`, `selected`, `destroy()`를 제공한다. destroy는 이벤트만 해제하고 DOM은 소유자가 관리한다. 기본 초기 바인딩은 onChange를 호출하지 않는다. 수평 단일 tablist용이다.

- `fieldFor({label, control, help})`는 기존 native input/select/textarea를 이동하여 라벨·도움말·오류를 연결한다. `control`의 name/value/검증/이벤트와 기존 aria-describedby를 보존한다. 반환값은 `{root, control, setError(message)}`.

- `createNativeConfirm(host, {title, message, confirmLabel, destructive})`는 `{element, ask(trigger), destroy()}`를 반환한다. `ask`는 명시적 승인만 true, 취소/Escape/destroy는 false다. 동시 ask와 destroy 이후 ask는 허용하지 않는다. 소유자는 화면 전환 때 destroy하고, await 뒤 scope 유효성을 재검사해야 한다. Web Awesome과 무관한 경량 native dialog 버전이며 공유 theme.css를 사용한다.

- `bindCodeOperation({root, header, label, control, help})`는 기존 코드/비밀 값 영역에 공통 배치를 연결한다. root가 header와 id 있는 native input/textarea를 포함하고, header가 label을 포함해야 한다. label 연결과 도움말 aria-describedby를 설정하며 기존 설명 ID를 보존한다. 반환값은 `{root, control}`이다. 입력 값, readonly, password type, 버튼 이벤트, 복사·보안 처리와 표시/숨김은 소유자가 유지한다. DOM을 복제하거나 값을 HTML로 직렬화하지 않으며 이벤트/관찰자를 설치하지 않는다.

- `metadataGrid(entries)`는 `[label, value]` 배열을 `dl > div > dt/dd`로 생성한다. 모든 값은 텍스트로 출력하고 null/undefined는 `—`로 표시한다. `af-metadata-grid` 공유 스타일은 데스크톱 3열, 700px 이하 1열이다. 기존 DOM에 같은 클래스를 적용해도 되며 데이터 의미·정렬·갱신 시점은 호출자가 소유한다.

- `af-status--inline`은 `status`/`setStatus` 결과에 추가하는 압축 표시 변형이다. role·kind·busy 의미는 그대로 두고 테두리·내부 여백만 제거한다. 폼 내부 오류나 이미 공간을 예약한 작업 결과 메시지에 사용하며 색상은 공통 상태 토큰을 따른다.

- `bindNativeDialog(dialog)`는 기존 dialog에 af-dialog/af-kit을 적용하고 `{element, open({initialFocus}), close(value), destroy()}`를 반환한다. open 시 연결된 DOM과 접근성 이름을 요구하며 initialFocus는 dialog 내부 요소여야 한다. 모달 focus·Escape·close 이벤트는 브라우저가 소유한다. destroy는 닫고 재개를 차단하지만 소유자의 DOM/폼/이벤트를 제거하지 않는다. 기존 native close도 사용할 수 있다. 입력값·검증·저장·scope 전환 정책은 호출자가 유지한다.

- `bindResizeHandle(handle, {getValue, onChange, onDragging, axis, step})`는 픽셀 단위 리사이저의 pointer capture/방향키를 공유한다. 기본 axis는 horizontal, step은 16이다. 크기 제한·ARIA value·레이아웃·저장은 호출자가 소유한다. `{cancel, destroy}`를 반환하며 cancel은 현재 드래그만 끝내고 destroy는 이벤트까지 해제한다. 다른 포인터와 오른쪽 버튼은 드래그를 시작하지 않는다. lostpointercapture도 종료 처리한다.

- `bindTreeKeyboard(root, {items, isExpanded, onToggle, onActivate, onToggleSelection, onSelectAll, onContextMenu, onMove})`는 소유자가 제공하는 현재 보이는 depth-first 행 목록에 키보드 계약을 적용한다. 행은 `{key, parentKey, folder, element}`다. 방향키/Home/End는 focus, Enter/Space/전체 선택/메뉴는 콜백으로 전달한다. onMove에는 Shift 상태가 포함된 원래 이벤트가 전달된다. IME 조합과 이미 처리된 이벤트는 무시한다. destroy는 키보드 리스너만 해제하고 DOM/선택은 제거하지 않는다.

- `renderNativeTree(root, {entries, childrenOf, isExpanded, renderRow, groupClass, focusKey})` 는 native tree DOM을 생성하고 `{...entry, element, parentKey}` visible row 배열을 반환한다. entry의 key는 고유해야 하며 folder가 true인 항목만 펼침 상태를 갖는다. renderRow(entry, {level, expanded})는 소유한 콘텐츠/이벤트를 담은 요소를 반환한다. 공통 렌더러가 tree/treeitem/group ARIA, 형제 내 위치, roving tabindex와 focus 복원을 담당한다. 중복 키는 기존 DOM을 교체하기 전에 거부한다. 정렬·검색·선택·문서 액션은 소유자 계약이다.

- `selectKeys({keys, selected, anchor, key, range, toggle})`는 새 `{selected:Set, anchor}`를 반환하는 순수 다중 선택 계산이다. keys는 현재 보이는 선택 가능 항목 순서다. range는 양 끝을 포함하며 toggle보다 우선한다. 기준 항목이 필터로 사라지면 대상 하나를 새 기준으로 선택한다. 없는 대상은 기존 선택을 보존하고 입력 Set을 변경하지 않는다.

<a id="workspace-ui"></a>

## 43. workspace-ui

- 작업공간 화면의 여백, 들여쓰기, 글꼴, 스크롤을 수정할 때 이 기준을 적용한다. 구현 기준은 `static/css/ui.css`의 `--ui-*` 토큰이다. 화면마다 새로운 숫자를 추가하기 전에 기존 토큰으로 표현한다. 공통 컨트롤과 상호작용 스타일은 `static/css/ui.css`에서 관리하며 기능별 CSS 다음에 로드한다. 조직·작업공간·일정· 에이전트·문서·MCP 화면은 이 규칙을 공유하고 기능별 CSS는 배치와 의미별 상태를 담당한다.

<a id="여백과-정렬"></a>

## 44. 여백과 정렬

- 헤더는 한 줄로 유지하고 로고와 프로필만 배치한다. 왼쪽 작업 표시줄은 조직, 작업공간 순서로 배치한다. 개인/조직 선택은 조직 사이드바에, 작업공간 선택은 작업공간 사이드바에 둔다. 헤더에 선택 메뉴를 중복 배치하거나 별도 행으로 나누지 않는다.

| 용도 | 기준 |
| --- | --- |
| 간격 단위 | 4px |
| 라벨과 입력, 같은 목록의 행 간격 | 4px (`--ui-space-1`) |
| 관련 항목, 버튼 사이 | 8px (`--ui-space-2`) |
| 좁은 화면 본문 패딩 | 12px (`--ui-space-3`) |
| 기본 본문 패딩, 트리의 추가 단계 들여쓰기 | 16px (`--ui-space-4`) |
| 번호/글머리 목록 들여쓰기 | 24px (`--ui-space-6`) |
| 독립된 섹션 사이 | 16px: 기본 8px gap + 제목 앞 8px |

- 본문은 왼쪽부터 배치한다. 양쪽에 큰 여백을 만드는 임의의 중앙 정렬이나 고정 최대 너비를 추가하지 않는다. 목록의 후속 줄은 본문 시작점에 정렬한다. 공백 문자나 `&nbsp;`로 들여쓰지 않는다. 브라우저 기본 heading/list margin을 그대로 섞지 않는다. 관련 항목은 부모의 gap으로 간격을 정하고 자식 margin을 중복해서 더하지 않는다.

- 기존 셸의 5px 패널 간격, 1px 경계선, 7px 모서리, 60px 작업 표시줄과 아이콘 내부 여백은 사용자 지정 셸 규격으로 유지한다. 본문 간격 규칙 때문에 셸 규격을 바꾸지 않는다.

<a id="타이포그래피"></a>

## 45. 타이포그래피

- 본문은 루트의 기존 UI 글꼴을 상속한다. 버튼과 입력 주변 텍스트도 같은 글꼴을 사용한다. 외부 웹폰트를 추가하지 않는다.

| 역할 | 크기 / 줄 높이 | 굵기 |
| --- | --- | --- |
| 페이지 제목 | 18 / 24px | 600 |
| 섹션 제목 | 13 / 20px | 600 |
| 본문, 라벨, 버튼, 목록 | 12 / 20px | 400 |
| 보조 문구 | 11 / 16px | 400 |
| 코드 및 설정 | 11 / 16px, `--ui-font-code` | 400 |

- 작업 표시줄 아래 8px 라벨은 별도 셸 규격이다. 본문에 8px 크기를 사용하지 않는다. 강조를 위해 임의로 굵기를 높이거나 제목처럼 보이는 탭 장식을 추가하지 않는다. 탭은 실제로 여러 내용을 전환할 때만 사용한다. JSON은 2칸 들여쓰기로 출력한다.

<a id="스크롤"></a>

## 46. 스크롤

- 셸/페이지 자체는 스크롤하지 않고 사이드바와 본문이 각자의 영역에서 스크롤한다.
- 일반 안내 화면의 세로 스크롤 주체는 본문 하나다. 내부 안내 카드나 코드 상자에
  고정 높이와 세로 스크롤을 중복으로 만들지 않는다.
- MCP 설정은 코드 줄 수에 맞춰 높이를 정한다. 줄바꿈으로 JSON 들여쓰기를 흐트러뜨리지
  않으며 긴 코드 줄의 가로 스크롤만 코드 상자에 허용한다.
- 스크롤바는 `thin`, 손잡이는 `--ui-scroll-thumb`, 트랙은 투명으로 통일한다.
  본문은 `scrollbar-gutter: stable`로 스크롤바 출현에 따른 좌우 이동을 줄인다.
- 좁은 화면에서도 페이지 전체 가로 스크롤이 생기지 않게 `min-width: 0`과 유연한 너비를 사용한다.
- 키보드 포커스는 가려지지 않아야 하고, 포커스된 입력·버튼까지 스크롤할 수 있어야 한다.

<a id="적용-확인"></a>

## 47. 적용 확인

- 여백·글꼴 변경 시 데스크톱과 좁은 화면을 확인한다. 변경한 화면에서 중복 세로 스크롤, 페이지 가로 넘침, 버튼 줄바꿈, 목록 들여쓰기, 키보드 포커스를 점검한다. 새 예외가 필요하면 예외의 이유와 적용 범위를 여기에 기록하고 CSS 토큰으로 표현한다.

<a id="mcp-설정과-연결-토큰"></a>

## 48. MCP 설정과 연결 토큰

- 작업공간 패널의 상단 헤더 한 줄에 선택한 작업공간 이름과 `작업공간 정보`·`MCP 연결` 탭을 함께 둔다. 작업공간명이 길면 말줄임하며 전체 이름은 툴팁으로 확인한다. 작업공간 정보 탭은 서버가 반환한 메타데이터만 표시한다. MCP 연결 탭은 연결 상태와 상태 확인, 클라이언트 설정, 연결 토큰 관리를 함께 표시하며 `연결된 MCP`라는 별도 영역으로 오인시키지 않는다. 연결되지 않은 작업공간은 MCP 연결 탭을 먼저 열고, 연결이 확인된 작업공간은 마지막 탭 선택이 없을 때 작업공간 정보 탭을 먼저 연다. 본문은 클라이언트·사용 환경 선택 없이 `1. 인증 토큰 발급`, `2. MCP 클라이언트 설정 다운로드`, `3. AI 지침 복사`, `4. MCP 연결 확인`의 네 단계를 표시한다. ZIP은 지원하는 모든 클라이언트·환경 설정을 디렉터리별로 담는다. 사용자는 다운로드한 ZIP을 연결할 로컬 워크스페이스 루트에 넣고, 그 워크스페이스의 AI에게 복사한 지침을 전달한다. 2단계에는 설정 선택 컨트롤 대신 지원 가능한 MCP 클라이언트 수와 이름을 읽기 전용 안내 텍스트로 표시한다. 네 단계는 화면 너비와 관계없이 항상 순서대로 한 열에 쌓고, 동일한 제목·동작·설명 구조를 사용한다. 1단계의 토큰 발급을 누르면 대화상자에서 토큰 이름을 입력한다. 이름은 토큰 선택 목록과 관리 목록에 표시하며 공백 이름은 발급하지 않는다. 네 단계는 패널의 남은 세로 공간을 균등하게 사용하고 단계 사이의 단일 구분선으로 순서를 구분한다. 선택 토큰이 없으면 명시적 발급을 안내한다. 유효한 토큰이 선택되면 다운로드 기록 유무와 관계없이 AI 지침을 복사할 수 있다. 4단계의 상태 확인을 누르면 버튼에 `확인 중…`을 표시하고, 단계 아래에 확인 중 메시지를 즉시 보여 준다. 완료 후에는 선택 토큰의 연결 결과와 확인 시각을 표시한다. 상태가 변하지 않아도 이 피드백을 유지하며, 자동 주기 조회는 사용자의 최근 확인 시각을 덮어쓰지 않는다.

- 클라이언트를 선택해 보여 주는 수동 설정 미리보기·복사·설치 링크는 제공하지 않는다. 클라이언트별 설정, 등록 명령, 대상 경로, 인증 안내와 공식 문서는 ZIP의 `connection.json`과 각 클라이언트 디렉터리에서 제공한다.

- MCP 연결 탭의 오른쪽 320px 보조 영역은 연결 토큰 관리다. 헤더에는 목록 새로고침을 두고, 본문에는 목록과 토큰 상태·마지막 요청·폐기를 표시한다. 토큰 원문은 설정 ZIP 생성에만 사용하고 화면에 표시하거나 별도 복사 동작을 제공하지 않는다. 여러 토큰이 있을 때는 선택된 토큰 이름 옆에 작은 `선택됨` 표시만 두고 행 전체에 선택 배경이나 세로 강조선을 추가하지 않는다. 각 행은 짧은 ID·상태·마지막 요청·확인된 클라이언트·폐기 동작만 표시한다. 발급·폐기 결과는 토큰 선택 아래, ZIP·지침 결과는 왼쪽 안내 영역에 둔다. 구분선은 실제 목록 항목 사이에만 한 번 표시한다. 패널 경계선은 1px, 본문 여백은 12px, 요소 간격은 기존 4/8/12px 토큰을 사용한다.

- MCP 설정과 토큰 보조 영역의 헤더는 고정하고 본문이 넘칠 때만 독립적으로 스크롤한다. 패널 너비 760px 이하에서는 토큰 보조 영역을 아래로 배치하고 가용 높이를 3:2로 나눈다. 입력·동작은 줄바꿈하며 페이지 전체 가로 스크롤을 만들지 않는다.

- 작업 표시줄 버튼은 기본 52px이며 높이가 부족하면 44px까지 줄인다. 아이콘과 라벨을 유지하며, 최소 높이로도 부족한 경우에만 표시줄 내부를 스크롤한다.

<a id="화면-선택-복원-및-연결-알림"></a>

## 49. 화면 선택 복원 및 연결 알림

- 화면 탐색 상태는 localStorage에 저장한다. 조직 선택은 계정별, 마지막 작업공간·활동·문서 선택은 계정과 조직별, 아이콘 표시·순서·문서 트리 펼침은 계정·조직·작업공간별로 구분한다. MCP 연결 안내/작업 화면과 토큰 선택 ID도 계정·조직·작업공간별로 복원한다. 저장한 대상이 없거나 권한이 사라지면 현재 조회 결과로 복구한다. 토큰 원문이나 설정 파일의 인증 값은 localStorage에 저장하지 않는다. 사이드바의 마지막 너비와 닫힘 상태는 작업 목록 항목별로 저장하며 작업 전환과 새로고침 때 각각 복원한다. 처음 여는 작업은 공통 기본 너비의 열린 사이드바를 사용하되, 일정은 넓은 타임라인을 위해 닫힌 사이드바로 시작한다. 사용자가 작업 목록 항목을 다시 누르거나 Ctrl+B로 열면 해당 작업의 열린 상태로 갱신한다.

- Activity 안에서 새로고침 뒤 이어야 하는 사용자 상호작용은 Activity별 최신 상태 스냅샷으로 저장한다. 문서는 보기·선택 문서·트리 검색/접힘, 일정은 보기·선택 항목·트리 접힘·기간/축, 에이전트는 선택 에이전트·작업·로그 펼침, 연동은 선택 연결·범위·탭, 조직과 관리자는 마지막 하위 화면을 복원한다. 이 스냅샷은 계정·조직·작업공간으로 격리하며, 서버 이벤트 로그나 권위 데이터의 대체물이 아니다. 편집 폼 내용, 문서 본문, 토큰·인증 값, 클립보드 내용과 일시적인 메뉴·대화상자·포커스는 저장하지 않는다. 저장 ID가 현재 서버 조회 결과에 없으면 해당 Activity의 유효한 기본 상태로 정리한다.

- 여러 브라우저·사용자·작업자에게 공유되거나 권한·감사·동기화에 필요한 생성·수정·삭제, 작업 상태, 연동 상태와 그룹 상태는 인증된 API를 거쳐 PostgreSQL에 저장한 결과만 반영한다. 서버 변경 요청은 기존 append-only 감사 이벤트에도 남긴다. localStorage의 값으로 서버 상태나 권한을 추정하거나 서버 쓰기 성공을 표시하지 않는다.

- 작업공간 목록 그룹은 화면 탐색 상태가 아니라 사용자별·조직별 권위 데이터다. 그룹 생성, 이름, 접힘 상태와 작업공간 소속은 인증된 Workspace 그룹 API를 통해 PostgreSQL에 저장하며 localStorage를 대체 저장소로 사용하지 않는다. 조회할 때 현재 사용자가 읽을 수 있는 작업공간만 그룹 소속으로 반환하고, 그룹 이름 변경은 revision 충돌을 검사한다. 목록의 첫 영역은 `기본 그룹`으로 표시하고 사용자 그룹에 속하지 않은 작업공간을 둔다. `새 그룹`으로 만든 사용자 그룹은 기본 그룹 다음에 생성 순서대로 추가한다. 작업공간 탐색기는 파일·폴더 아이콘과 계층 안내선을 표시하지 않는다. 그룹에는 접기·펼치기 화살표만 두고, 아이콘이 없는 간결한 계층을 위해 하위 작업공간 이름은 그룹 이름보다 8px 들여쓴다. 일정 사이드바는 `기본 그룹`이나 `작업`·`하위 작업` 전역 영역을 만들지 않는다. 공통 `explorerTree`로 각 작업과 그 작업에 속한 하위 작업을 계층으로 표시하며, 작업별로 접고 펼칠 수 있다. 일반 폴더·문서 아이콘 대신 `static/images/planning-explorer/`의 작업 접힘·펼침 및 하위 작업 전용 SVG를 사용하고 disclosure 화살표를 함께 유지한다.

- MCP 상단 상태는 선택한 토큰 기준으로 표시한다. 다른 클라이언트의 성공 기록은 현재 선택의 연결 완료로 표시하지 않는다. connection-check·diagnostic·verification으로 식별되는 진단 기록은 서버 통신 확인으로 구분한다. 연결 증거는 마지막 요청에 대한 기록이며 실시간 온라인 상태나 클라이언트 제품 신원을 보증하지 않는다. 첫 연결 확인에는 토스트를 한 번 표시하고 초록색 MCP 연결됨 표시를 유지한다. 반복 조회와 새로고침 시 같은 토큰의 알림은 반복하지 않는다.

<a id="공통-표시-컨벤션"></a>

## 50. 공통 표시 컨벤션

- 작업공간 목록·상단 헤더·MCP 연결/토큰 패널은 `ui.css`의 공통 변수를 사용한다. 기본 사이드바, MCP 연결, 연결 토큰의 최상단 헤더는 모두 공통 35px 높이를 사용해 경계선을 한 줄로 맞춘다. 본문 12px, 보조 정보 11px, 영역 제목 13px, 간격 4/8/12/16px, 입력 높이 30px, 테두리 1px와 모서리 3px를 기준으로 한다. 작업 표시줄의 작은 라벨 규격은 기존 값을 유지한다.

- 선택 행은 문서 목록과 같은 선택 배경을 사용하고, 키보드 포커스가 있으면 활성 선택 배경을 사용한다. 작업공간 목록은 선택 배경과 `aria-current`로 상태를 나타내며 별도의 `선택됨` 텍스트를 반복하지 않는다. 연결 성공은 헤더와 토큰 목록 모두 같은 성공 색을 사용한다. 알림은 기존 패널 배경·본문 글자·공통 간격을 사용하며 성공 강조는 왼쪽 테두리로 표시한다. 단순 복사 완료 안내와 연결 전환 알림의 기존 동작은 유지한다.

- 패널의 고정 헤더와 본문 독립 스크롤, 계정·조직·작업공간별 선택 상태 복원, 연결 확인 후 MCP 화면 유지 규칙은 스타일 정리를 이유로 변경하지 않는다.

<a id="공통-컨트롤과-상호작용"></a>

## 51. 공통 컨트롤과 상호작용

- 기본 사이드바는 기능과 관계없이 하나의 `aside[data-region="primary-sidebar"]`만 사용한다. 모든 기본 사이드바는 이 호스트 안의 `data-sidebar-view`를 전환하며 별도 `aside`나 별도 위치 규칙을 만들지 않는다. 직접 자식은 하나의 35px `app-sidebar__header`와 하나의 독립 스크롤 `app-sidebar__body`로 고정한다. `app-sidebar__content`는 기존 선택자 호환을 위해 같은 바디에 함께 둔다. 조직·작업공간·일정·에이전트·문서·연동·로그·테스트·DB·계정·관리자 뷰의 선택·숨김·제목 갱신은 공통 에셋 `bindSidebarHost`가 한 번에 소유한다. 기본 사이드바와 메인 작업공간 패널은 공통 에셋의 `af-workbench-panel` 표면을 공유한다. 사이드바 헤더와 바디는 각각 `af-workbench-panel__header`, `af-workbench-panel__body`를 함께 사용하고, 기능 스타일은 패널 테두리·반경·배경을 다시 정의하지 않는다. 기본 탐색 행은 28px로 통일한다. 내부는 `app-sidebar__nav`, `app-sidebar__row`, `app-sidebar__state`를 조합하며 기능별 코드는 목록의 데이터, 계층, 동작만 담당한다. 계층형 바디의 기본 표현은 공통 에셋의 `af-explorer-tree`와 `af-explorer-row`를 사용한다. 문서 트리의 22px 고밀도 행과 에이전트의 상세 행은 정보 구조상 필요한 공통 변형으로 유지한다. 조직과 작업공간 화면도 하나의 `main[data-region="workspace"]` 안에서 같은 방식으로 전환한다. MCP 연결 전 잠금은 작업공간 전환과 조직 선택을 막지 않고 잠긴 기능 뷰에만 적용한다. 기본 사이드바는 별도 닫기 버튼을 두지 않는다. 너비 조절기를 최소 너비보다 왼쪽으로 끌거나 키보드 왼쪽 방향키로 줄이면 닫히며 Ctrl+B로도 전환한다. 닫힌 상태에서는 사이드바와 너비 조절기를 접근성 트리와 레이아웃에서 제외하고 작업 영역이 남은 너비와 높이를 사용한다. Activity를 선택하거나 Ctrl+B를 누르면 기존 너비와 현재 선택 화면을 유지한 채 다시 열린다.

- 각 `data-sidebar-view`의 내부 구조는 문서 사이드바를 기준으로 `app-sidebar__section` → `app-sidebar__section-header` → `app-sidebar__section-content` 순서를 사용한다. 섹션 제목은 `app-sidebar__section-title`, 탐색 목록과 행 및 상태는 위 공통 클래스를 사용한다. 기능별 클래스는 계층 표현, 추가 메타데이터, 기능 고유 동작에만 사용한다. 내용이 아직 결정되지 않은 사이드바도 같은 섹션 구조 안에서 `정의 대기` 상태를 표시하며 임의의 메뉴를 추가하지 않는다. 섹션 접기·펼치기는 정보 구조에서 명시적으로 허용된 경우에만 제공한다. 작업공간 목록과 문서 그룹처럼 접을 수 있는 정적 섹션은 공통 `data-sidebar-section-toggle` 동작을 사용하고, 화살표·SVG 아이콘·라벨의 순서와 26px 헤더 높이, hover·focus·접힘 상태를 공유한다. 단일 섹션의 이름이 바깥 기본 사이드바 헤더와 같고 동작도 그 헤더에 모을 수 있는 일정 화면은 중복 내부 헤더를 만들지 않고 바깥 헤더를 섹션 헤더로 사용한다. 일정 사이드바는 바깥 기본 사이드바 헤더의 `일정` 제목을 사용하며 같은 제목의 내부 섹션 헤더를 반복하지 않는다. 헤더 오른쪽에는 일정 대시보드를 여는 단일 SVG 아이콘과 새로고침·작업 추가 버튼을 둔다. 대시보드 본문 상단에서 `전체 일정`, `오늘 할 일`, `칸반`을 같은 데이터의 보기 전환 버튼으로 구분한다. 대시보드 제목은 `일정 대시보드`로 고정해 선택한 보기 이름과 중복하지 않는다. 본문에서는 공통 탐색기에서 각 작업과 그 작업에 속한 하위 작업을 계층으로 배치하며, 작업별로 접고 펼칠 수 있다. 작업 행 선택과 disclosure 토글은 분리한다. 대시보드 헤더는 제목·보기 전환·보기별 동작을 한 행에 두고 모든 보기에서 공통 35px 높이를 유지해 기본 사이드바 헤더의 하단 경계선과 수평으로 맞춘다. 상태 메시지와 보기 설명은 헤더 밖의 고정 행으로 분리하며, 보기별 동작 버튼은 줄바꿈으로 높이를 바꾸지 않는다. 전체 기본 사이드바는 상단 헤더의 전역 토글로 닫고 연다. 일정 대시보드 헤더에도 `작업 추가`를 제공해 사이드바가 닫혀 있어도 최상위 작업을 만들 수 있게 한다. 일정 사이드바는 삭제하지 않으며 작업 목록의 일정 항목 재선택 또는 Ctrl+B로 연다. 일정 작업 상세의 패널 헤더 왼쪽에는 현재 대시보드 보기를 유지한 채 돌아가는 `일정 대시보드` 동작을 표시한다. 상세의 수정은 패널 헤더에 두고 하위 작업 추가는 해당 목록 섹션의 단일 주 행동으로 표시한다.

- `오늘 할 일`은 오늘 기간에 포함된 미완료 작업과 기한 초과 미완료 작업을 별도 영역으로 표시한다. 칸반 카드는 상위 작업·담당자·목표일·막힘 상태를 표시하고, 편집 권한이 있으면 상태 선택 또는 열 간 끌어놓기로 상태를 변경한다. 마지막 대시보드 보기는 작업공간별 로컬 화면 선호로 기억한다. 전체 일정은 별도 중첩 패널을 만들지 않고 평면 작업영역을 유지한다. 공통 배경, 경계, 타이포그래피, 스크롤바 및 상태 토큰을 사용한다. 왼쪽 고정 열은 행 번호·상태·작업명· 최소 상태만 한 줄에 배치하고, 기간은 작업 툴팁과 오른쪽 막대에서 확인한다. 오른쪽은 같은 높이의 기간 막대와 날짜축을 사용한다. 행 추적을 위한 교차 배경과 일정 좌표만 일정 전용 표현으로 유지한다. 상위 작업과 하위 작업의 기간 막대는 같은 높이를 사용하고 색과 완료 진행률로만 의미를 구분한다. 전체 일정의 날짜축은 일·주·월 단위를 제공하고 마지막 선택을 작업공간별로 복원한다. 주 단위는 별도 대시보드 보기를 만들지 않고 이 날짜축에서 제공한다. 기간과 날짜가 없는 하위 작업도 전체 일정의 왼쪽 작업 열에서 누락하지 않는다. 한국 주말은 오류색 계열의 옅은 세로 밴드와 날짜 색으로 구분한다. 서버가 제공하는 한국 공휴일·대체공휴일은 주말보다 한 단계 진한 밴드로 표시하고 날짜 툴팁에 공휴일명을 제공한다. 상위 작업 막대는 실제 하위 작업 완료 수로 계산한 진행률을 보조 표시하고 같은 값을 텍스트로 함께 제공한다. 하위 작업이 없을 때는 진행률을 추정하지 않는다. 선후행 연결선은 서버가 제공하는 실제 의존 관계가 있을 때만 표시하며 부모 관계나 날짜 순서로 임의 추정하지 않는다.

- 입력·검색·선택 목록은 배경, 테두리, 3px 모서리, 본문 글꼴과 30px 높이를 공유한다.
  문서 트리와 표의 열 검색은 공간 제약 때문에 `--ui-control-compact-height`(22px)를 사용한다.
- 여러 줄 입력과 코드 필드는 내용에 맞춘 높이와 기존 코드 글꼴을 유지한다.
- 펼친 단일 선택 목록도 `ui.css`에서 배경·경계·그림자·행 간격·선택/hover/포커스를 관리한다.
  `appearance: base-select` 지원 브라우저에서는 기본 select의 키보드·폼·change 동작을
- 유지하면서 팝업을 꾸미고 선택 화살표는 컨트롤 오른쪽 끝에 정렬한다. 미지원 브라우저는 기존 네이티브 선택 목록을 유지한다. 목록은 컨트롤 아래에 4px 간격으로 표시하며 가용 화면 높이 안에서 스크롤한다.
- 선택 배경은 `--explorer-row-selected`, 목록 안의 키보드 포커스가 있는 선택은
  `--explorer-row-active-selected`다. 메뉴·행 hover는 `--explorer-row-hover`를 사용한다.
- 키보드 포커스는 `--focus-border`의 공통 테두리로 표시한다. 비활성 컨트롤은
  `--ui-disabled-opacity`를 사용하고 체크박스·라디오의 기본 조작 방식을 유지한다.
- 드래그 원본은 `is-dragging`, 드롭 영역은 `--ui-drop-background`, 삽입선은
  `--ui-drop-border`를 사용한다. 문서 분할·탭 이동·작업공간 그룹 이동·활동 순서 변경은
- 각각 기존 동작을 유지한다.
- 공통 시각 속성을 기능별 파일에 다시 선언하지 않는다. 일정 상태 막대·위험 동작처럼
  의미가 다른 요소만 범위를 좁힌 선택자로 표현한다.

- 작업공간 이름은 목록의 우클릭 메뉴 또는 F2로 편집한다. Enter로 저장하고 Esc로 취소하며, 공백 이름은 저장하지 않는다. 기존 PUT API의 workspace.update 권한 및 revision 충돌 검사를 사용한다. 실패 시 입력을 유지하며 성공 시 목록·최근 목록·상단 헤더·MCP 안내의 이름을 갱신한다. 그룹 및 연결 토큰의 ID는 이름 변경과 무관하게 유지된다.

- 작업공간이 선택된 상태에서 작업공간 Activity를 누르면 목록 사이드바와 현재 작업공간 패널을 함께 표시한다. 패널은 `작업공간 정보`와 `MCP 연결` 탭을 제공한다. 작업공간 정보는 서버의 WorkspaceResponse에 있는 이름·소속·작업공간 상태·slug(식별 이름)·생성일·수정일·ID를 보여준다. MCP 연결 탭에는 연결 설정과 본인이 발급한 연결 토큰을 표시하며 외부 MCP 서버 목록을 뜻하는 `연결된 MCP`로 부르지 않는다. 작업공간이 없을 때만 기존 빈 목록 화면을 사용한다. 이름 변경 시 패널 헤더와 정보 값도 갱신하며, 서버에 없는 날짜는 추측하지 않고 —로 표시한다.

<a id="catalog-policy"></a>

<a id="공통-에셋-카탈로그-정책"></a>

## 52. 공통 에셋 카탈로그 정책

- TypeScript `assetCatalog`를 작성 미리보기와 런타임 레지스트리의 유일한 descriptor 원본으로 사용합니다. 공개 ID마다 구현 하나, 닫힌 속성 허용 목록, 허용 영역, 상태, 동작, 접근성, 출처와 합성 예제가 있어야 합니다.
- 안정된 `@1` ID는 불변입니다. 대체 항목은 새 major ID를 사용하며 의미가 겹치는 별칭을 만들지 않습니다. 폐기 예정 구현은 한 릴리스 기간 동안 대체 항목을 알리고, 소비자 조사와 미리보기 검사를 마친 다음 major 릴리스에서 제거합니다.
- `catalog/provenance.json`은 검토된 다색 에셋의 정확한 바이트를 기존 위치와 연결하고 Material Icon Theme·Tabler 라이선스와 출처를 보존합니다. 전체 vendor 묶음은 파일 트리 입력이며 공개 작업 아이콘 카탈로그가 아닙니다.
- `resource-table@1`의 `records`는 `id`, `title`, 선택적 `status`·`meta`만 허용합니다. `columns`는 `title`·`status`·`meta`의 안정된 셀 ID와 접근성 레이블을 사용합니다. Native 소비자는 같은 `DataTable`과 신뢰된 React renderer를 사용할 수 있으나 사용자 Workbench는 렌더 함수를 주입하거나 임의 필드를 추가할 수 없습니다.
