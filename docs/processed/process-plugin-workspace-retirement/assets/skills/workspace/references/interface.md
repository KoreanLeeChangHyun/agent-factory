# Workspace Interface

## Human control tower

- Workspace uses a developer-familiar VS Code-shaped shell whose three principal regions
  have the exact Korean names `작업 표시줄`, `기본 사이드바`, and `작업 영역`.
- Its primary spatial relationship is `작업 표시줄 (Activity Bar) -> 기본 사이드바 (Primary
  Sidebar) -> 작업 영역 (Workspace area)`.
- It presents project state for Human navigation and control without becoming the
  canonical store or executor for the state it may later project.

Keep common layout, interaction, and visual tokens in the selected Agent Factory
MCP runtime's canonical `static/workspace/` package. The Activity Bar contains
exactly these six top-level items, in this order, with these Korean labels:

1. 일정
2. 에이전트
3. 문서
4. 외부연동
5. 로그
6. 테스트

- Render each listed Korean label as visible text below its decorative inline SVG icon
  in the Activity Bar.
- The label remains visible at narrow supported viewport widths rather than collapsing
  the bar to icon-only navigation.

No other top-level Activity item is allowed. In particular, do not add separate
Explorer/File Explorer, Planning/Specification, Project Skills,
overview/dashboard, Roadmap, or alias buttons.

- Render `외부연동` as the fourth regular Activity with
  `data-activity="external-integrations"`, not as a bottom utility or overlay.
- It selects its corresponding Primary Sidebar and Workspace views through the same
  interaction as the other Activities.
- Its Workspace view starts with the honest status `외부연동 상태 연결 대기` and no sample
  integrations.

- The `외부연동` Primary Sidebar renders exactly seven category group rows in this order:
  `웹·리서치`, `문서·파일`, `메일·메시지`, `일정·회의`, `지식·업무관리`, `개발·운영`, `데이터·비즈니스`.
- Use a semantic list with visible text and no button, link, selected state, disclosure,
  or fabricated count until category navigation or child sources are explicitly decided.
- Keep the rows readable throughout the supported sidebar resize range.
- Match the Document Primary Sidebar's compact group-heading row height, typography,
  label inset, background, and divider rhythm.
- Do not add a redundant in-content title; because these rows are static, do not reserve
  or render a disclosure-icon slot.
- These are work-purpose categories.
- Provider, account, integration method, status, permission scope, and last
  synchronization time remain attributes of a future owner-backed integration item
  rather than category axes.

- The Activity view is a read-only projection boundary.
- It exposes `window.agentFactoryWorkspace.externalIntegrations.replaceItems(items)` for
  a future owner-backed loader.
- Every item is an object with a non-empty stable `integrationIdentity`; optional
  `provider`, `account`, `method`, and `status` values are rendered as plain text, and
  duplicate identities fail closed.
- The empty adapter result returns the view to its waiting state.
- Do not hardcode a personal account, infer installed/connected/healthy state, expose
  secret material, or add connection/disconnection controls until an authoritative
  provider and lifecycle route are implemented.
- `외부연동` is the Human-facing umbrella for plugins, connectors, MCP servers, direct
  OAuth/API integration, local mounts or synchronization, service accounts, external
  document URLs, and manual imports.
- A connector is only one method.
- Workspace owns only the projection and interaction; Tool and each actual host, plugin,
  MCP server, or provider retain lifecycle authority.

- One Activity Bar item owns one corresponding Primary Sidebar view and one main
  Workspace view.
- The Document sidebar contains three prominent, independently collapsible explorer-like
  groups in this order: `원본 문서`, `가공 문서`, and `명세 문서`.
- Original provides `개요` and `문서검색`; the search item selects a compact semantic table
  view with no top tab bar.
- It uses an accessible semantic table. No browser library is distributed by this
  plugin; richer sorting, resizing, search, and filter behavior belongs to the MCP
  application's implementation and dependency policy.
- Its exact visible order and labels are `문서 분류`, `출처`, `태그`, `문서 이름`, `확장자`, `수정 일자`.
- Content-appropriate widths use the available desktop space, while per-column minimum
  widths preserve table-owned horizontal overflow when the viewport is genuinely narrow.
- The `문서 이름` header is plain text; each populated name cell is the source link.
- `출처` shows decorative inline SVG plus visible provider text so color is never the only
  distinction.
- Processed and Specification each provide `개요`, then a visible `탐색기` parent row
  immediately below it.
- The actual Document list or its honest loading, empty, unresolved, or error state is
  nested inside that explorer, not rendered as a sibling of the explorer row.
- The two regions remain visually and semantically consistent.
- The Korean UI label is exactly `명세 문서`, while the semantic type, identifier, metadata,
  and path remain Specification and `specification`.

- Render `개요` and `탐색기` with the same explorer-row geometry and interaction grammar:
  equal fixed row height, equal non-shrinking icon size, one label baseline, aligned
  icon and label axes, and consistent hover and visible-focus background/alignment.
- Give `탐색기` a leading disclosure-arrow slot, but align its folder icon and label with
  the overview document icon and label rather than shifting the whole row.
- Use a compact VS Code-like child alignment: place each expanded child Document's 14 px
  SVG icon on the `탐색기` folder-icon axis, which is the 22 px logical inset in the
  current row grammar.
- Start the child title after the 14 px icon and its 4 px gap so it aligns with the
  `탐색기` parent-label axis.
- The parent disclosure arrow alone provides the visual parent/child distinction; do not
  add another icon-plus-gap offset.
- Reset the nested list's margin and inline padding to zero and remove its marker so
  user-agent list padding cannot be added to the child inset.
- A Document row must remain one line at the default 252 px sidebar and throughout the
  supported 180–520 px resize range.
- Its icon does not shrink; its text region owns the shrinkage and uses ellipsis without
  causing horizontal scrolling.
- Preserve the complete Document name in native HTML title text.
- Keep selected, hover, and focus treatments on the same row box.
- Render honest loading, empty, error, and unresolved messages as separate, readable
  supporting states only; they may wrap but must never overlap a Document row.

- The Processed region loads tenant-scoped Document records from
  `/api/organizations/<organization-id>/workspaces/<workspace-id>/documents` and filters
  by the Processed type. It never scans a project-local package directory.
- Use a short, simple visible title for both Processed and Specification rows, preserve
  the complete title in native HTML `title` text, and keep the visible label single-line
  with ellipsis.

- The Specification region uses the same tenant-scoped Document endpoint filtered by the
  Specification type. Pair status and AI Skill bindings come from authoritative Document
  metadata and provenance, never from a project-local directory scan.
- Render only authorized records. Empty and request-failure states remain explicit;
  downloads use the authenticated immutable revision-content endpoint.

- Use the Specification explorer as the read-only source for a recursive, VS Code-like
  split viewer.
- Its discovered entries are actual tree items, and every split leaf is one editor
  group.
- Each group owns a semantic tab strip and one linked `role=tab` and
  `role=tabpanel`/iframe pair per open Specification.
- Clicking a paired item remains the baseline path for environments where DnD is
  unavailable: open it as a new tab in the active editor group, or the first group when
  none is active.
- If that Specification is already open in the target group, activate its existing tab
  without creating a duplicate.
- Consecutive different selections accumulate tabs in that group.
- Selecting a tab reveals only its linked panel; preserve the complete title as the
  tab's accessible name and native title while a narrow visual label stays on one line
  and ellipsizes.
- Connect tab and panel with `aria-selected`, `aria-controls`, and `aria-labelledby`,
  use roving focus, and support automatic selection with ArrowLeft, ArrowRight, Home,
  and End plus Enter and Space activation.

- Track the active editor group independently from each group's active tab.
- Tab, pointer, or focus interaction marks a group active, and the Specification
  explorer selection reflects that group's active tab.
- Dragging a paired item to the empty 작업 영역 or the center of a group opens or activates
  its tab there.
- Dropping at the left or right edge creates a horizontal split;
- dropping at the top or bottom edge creates a vertical split whose new group opens the
  dropped Specification as its first tab.
- A group inside any existing split remains a target for another center or edge drop, so
  splits recurse.
- While the internal drag is active, iframe pointer hit testing must yield to the owning
  group so dragover and drop are not swallowed by the embedded document.
- Switching from another Document view during dragover must still allow the empty 작업 영역
  to accept the first drop.
- Keep the empty guidance until the first group opens.
- Only when a group is the sole editor group may it remain after its last tab closes.
- Keep that sole zero-tab group ID as a flat, full split leaf and center its guidance
  across the whole content area below the tab strip;
- do not render a fixed-size, maximum-size, bordered, or colored empty-state card.
- Never leave a zero-tab group beside another surviving group.
- Render center and edge drop indicators only while an actual internal Specification
  drag is active.
- The center indicator is a subtle full-content target below the tab strip, not a
  floating inset card, while the four edge indicators preserve their directional split
  regions.
- Successful and invalid drops, dragend, Escape or other cancellation, Activity or
  Document-view changes, and closing the last tab clear the dragged identity, body drag
  class, layout/group drop markers, and iframe hit-testing override.
- A normal no-drag group must never retain any drop indicator.
- Keep the active-group focus outline as a separate semantic focus state rather than a
  permanent blue ring around an empty group.
- Remove the global `명세 문서 편집기` header; only each group's tab strip owns document
  chrome.
- Give every open tab a real close button beside—not inside—its tab activation button.
- Use a decorative inline SVG X with `aria-hidden=true` and `focusable=false`; the
  button has the accessible name and native title `<full document name> 닫기`.
- Keep the title ellipsis and a fixed close hit target in narrow tabs, reveal the
  control clearly for hover, focus, and the active tab, and keep keyboard focus visible.
- Close-button focus does not enter the group activation route, and close-button click
  does not propagate into tab activation or split/drop behavior.
- Normal tab activation and group focus/click continue to activate the group.

- Closing an inactive tab preserves the target group's current active tab and panel.
- Closing the locally active tab activates the immediate right neighbor, or the left
  neighbor when there is no right neighbor.
- If the target group is not globally active, neighbor activation stays local to it and
  preserves both the previously active global group and its explorer selection.

- After any group closes its last tab, inspect the full editor layout.
- If another group survives, remove the zero-tab group and collapse its direct
  `.specification-split` parent into the remaining sibling subtree.
- Repeat split normalization as needed so nested horizontal and vertical trees contain
  no empty or unary split wrapper and the remaining groups expand into the released
  space.
- If the removed group was globally active, deterministically activate the nearest
  surviving leaf: choose the sibling subtree's first leaf when the removed group was
  before it, or the last leaf when it was after it.
- Reflect the chosen group's local active tab and panel in explorer selection and safely
  focus that active tab when possible.
- If the removed group was inactive, preserve the previous globally active group and
  explorer selection.
- Clear drag identity, body state, group/layout drop markers, and iframe hit-testing
  override immediately around collapse.
- Removal discards the closed group's tabs, panels, iframes, ARIA state, group state,
  listeners, and drop marker.

- Only when no other group survives does closing the final tab preserve the current
  group ID as a readable full-area empty drop target and clear explorer selection.
- A later explorer click or center drop uses the active surviving group, or creates the
  first tab again in that sole empty group.
- The operation is scoped to the target group even when the same Specification is open
  elsewhere, and removes only transient viewing state;
- it never deletes or modifies a Specification, Skill, or server data.

Every tab is an internal drag source. Apply these tab drop rules:

- within the same tab strip, insert it before or after the indicated tab and
  preserve its iframe and active state;
- at another group's center or tab strip, move it into that group;
- at any group's left, right, top, or bottom edge, move it into a new split
  group in that direction;
- if the destination already has the same Specification, activate that tab and
  remove the source tab without creating a duplicate;
- after a cross-group move, apply the same empty-group removal, recursive split
  normalization, active-group selection, explorer synchronization, and drag
  cleanup used by final-tab close.

- Use an explicit tab-drag payload and `move` effect so tab movement is distinct from
  the explorer item's `copy`-like open action.
- A canceled or invalid tab drag changes nothing.
- This remains transient viewing state and never edits the Specification.
- Do not infer pin/preview semantics, dirty state, save/edit, group resizing, layout
  persistence, or cross-origin loading, and do not render fake disabled controls for
  them.

- When the Workspace embeds an allowlisted same-origin Human Specification, apply an
  explicit `data-agent-factory-workspace-embedded="true"` marker to the iframe document
  root on load.
- Catch unavailable document access and retain the standalone presentation; never add a
  query or fragment, broaden the exact same-origin path rule, or weaken the read-only
  boundary.
- The iframe background uses `--workspace-background` before and beyond document paint.
- Under the marker, align page, surface, muted surface, text, muted text, border, and
  focus tokens to the neutral shell palette (`#1f1f1f`, `#181818`, `#2b2b2b`, `#cccccc`,
  `#a0a0a0`, `#0078d4`).
- Keep code, table, card, note, and diagram surfaces neutral and use blue only for
  meaningful focus/accent roles.
- Preserve standalone light/dark behavior when the marker is absent.

- Use the editor width efficiently.
- Remove the fixed centered 74 rem content cap; use roughly 12–16 px desktop outer
  insets and 10–14 px in narrow splits or mobile layouts.
- Present the Specification as one continuous technical document rather than a
  dashboard/card grid.
- Ordinary source sections and articles use headings, compact vertical spacing, and an
  optional thin divider instead of a bordered, rounded, filled box.
- Do not replace removed boxes with large padding or margins.
- Retain explicit boxes only for meaningfully bounded elements such as tables,
  preformatted blocks, actual diagram nodes, and notes/callouts.
- Comparison cards and steps use a low-contrast surface or divider only when the
  grouping needs it; the outer diagram canvas is unboxed.
- Compact the header, layout top/bottom padding, section gaps, heading and paragraph
  rhythm, cards, steps, diagrams, notes, table cells, preformatted blocks, and footer,
  without reducing readable font sizes or line height.
- Let cards, diagrams, tables, and sections use the available width while keeping prose
  itself near a readable line length.
- Keep the document viewport free of unnecessary horizontal scrolling; long tables and
  preformatted blocks own their horizontal overflow and must not be clipped.
- Maintain one consistent presentation asset set across the six Human Specifications
  without altering their meaning, translated source order/hierarchy, tables, diagrams,
  provenance, or source manifest.
- The reusable Document template may adopt the same presentation for future copy-once
  scaffolding, but it is never a mechanism for overwriting an existing Specification.

- The Original search table is a read-only metadata and source-link projection.
- It does not copy, normalize, or edit Original bodies, and it does not own or trigger
  Gather synchronization.
- No live browser query/API/source adapter, synchronization trigger or status contract,
  or metadata edit authority and persistence has been accepted.
- The browser therefore starts in the truthful `데이터 연결 대기` state without sample records
  and exposes only `window.agentFactoryWorkspace.originalSearch.replaceRows(rows)` for a
  future owner-backed loader.
- Rows carry `classification`, `provider`, `tags`, `name`, `extension`, `modifiedAt`,
  `sourceUrl`, and stable `sourceIdentity` fields.
- Unsafe URL schemes are not linked; external HTTP(S) links use appropriate
  opener/referrer isolation.
- Global search treats input only as literal text matched against the six displayed
  fields.
- The implemented bounded catalog search CLI does not connect this table.
- Original overview details and the other four Activity sidebars and their detailed
  capabilities remain Human-owned and undecided and must say so.
- Existing server/discovery utilities do not authorize a top-level Activity or a data
  integration beyond this decided Document view shape.
- This unresolved boundary no longer applies to the explicitly resolved local Processed
  package discovery endpoint.
- The Original overview content uses the compact workspace inset directly, without an
  editor header.
- The Document Sidebar's terminal Specification group has no trailing bottom divider
  below its discovery list or visible discovery state; separators between the three
  groups remain.
- These chrome decisions do not resolve the overview's contents.

- Use actual SVG for every user-facing icon.
- The `개요` and `탐색기` rows use decorative inline SVG marked out of the accessibility tree
  while their visible Korean text remains the interactive element's accessible name.
- Preserve semantic HTML, keyboard access, visible focus, readable contrast, responsive
  behavior, and usable baseline content without JavaScript.

## MCP runtime and publication

The selected Agent Factory MCP application owns the Workspace implementation,
separately from this plugin's Skill contract.

- Canonical browser assets are maintained under the MCP application's
  `static/workspace/` directory under that application's dependency policy.
- FastAPI serves the Human shell at `/workspace/` and tenant resources below `/api/`.
- The same application exposes the Agent Factory MCP transport at `/mcp`.
- The runtime resolves tenant organization and workspace identity through authenticated
  requests; it does not copy Workspace browser assets into a project.
- PostgreSQL owns tenant metadata and pgvector indexes, while S3-compatible object
  storage owns immutable Document revision bodies.
- Consumer projects contain no `.agent-factory/workspace/` runtime or Workspace-owned
  projections. Non-authoritative client state may live below `~/.agent-factory/`.
- Runtime source, deployment adapters, and runtime tests belong to the MCP repository.
  Do not recreate them under `skills/workspace/` or the project root.

Run the MCP application from its own environment:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- The MCP HTTP host attaches `Cache-Control: no-store`
  to every successful static-file response resolved from their allowlisted roots.
- This covers the `/workspace/` browser shell and its canonical local CSS and JavaScript.
- Do not extend this static-file freshness policy to JSON API responses or redirects.
- Preserve `X-Content-Type-Options: nosniff`, path containment, symlink rejection, and
  traversal defenses alongside it.
- Restart an already-running MCP application after changing server code;
- the next browser request then fetches the current file without heuristic cache reuse.

## Storage and authority boundary

The Workspace UI is a projection and control surface. Visibility does
not imply acceptance, health, completion, or authority. Agent sessions,
Original/Processed/Specification Documents, Project Skills, and Human decisions
retain their owning stores and rules.

- The exact local catalog at `<project-root>/.agent-factory/db.sqlite`, its schema,
  manager, initialization, rebuild, status, searches, publication and recovery are
  Agent-owned.
- Workspace does not invoke those operations, and MCP application startup has no catalog
  initialization side effect.
- Workspace has no catalog/search UI, query API, or search executor.
- It may later present read-only results supplied through an explicit Agent-owned
  interface, but that possibility does not authorize direct database access, a
  source/query binding, Activity behavior, or any transfer of Agent, Document, or
  catalog ownership.
- Apply the detailed catalog contract only from `skills/agent/SKILL.md`.

- A server-hosted Workspace is exposed by its selected host or adapter and does not
  require the local launcher.
- The local static-file `no-store` contract does not silently select policy for another
  host.
- Backend configuration, identity, synchronization/conflict policy, authentication,
  availability, and caching for that external host remain unresolved until explicitly
  decided.
