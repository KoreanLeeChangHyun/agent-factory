---
name: workbench-stage2-evidence-20260912
description: Workbench refactor stage 2 implementation evidence을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-12-workbench-stage2-evidence.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-12-workbench-stage2-evidence
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# Workbench refactor stage 2 implementation evidence

<a id="scope"></a>

## 1. Scope

- This dated Processed note records the RF-300–308 implementation slice. It does not replace ADR-010, the design-system catalog, or independent Verification evidence. Legacy templates, product navigation, backend business behavior, authentication, and provider state are unchanged.

<a id="implemented-design-system-slice"></a>

## 2. Implemented design-system slice

- `packages/design-system/src/tokens.css` defines dark, light, and high-contrast
  semantic foundations. Components consume semantic variables; reviewed multicolor
- resource icons are the explicit exception.
- Sixteen reusable React task icons cover the existing product categories plus common
  authoring needs. Selected, disabled, notification, accessible-label, and current-color
- behavior is owned by one component.
- One sidebar host composes flat, grouped/collapsible, tree, search, filter, detail,
  favorites/recent, and fixed-footer patterns. Selection, query/filter state, empty
- state, metadata rows, tree semantics, and native controls are implemented behavior.
- Panel layouts implement detail, list-detail, collection, settings form, dashboard,
  document, adjustable split, timeline, and kanban compositions. Layouts own real
- content slots and responsive collapse. The split separator supports pointer and keyboard adjustment with an announced value.
- Common controls include button, icon button, field, text/number/date/select,
  multiselect, checkbox, and toggle. Display and feedback assets include tabs, resource
- tree/table, metric, lazy visualization frame, code, Markdown, JSON, dialog, menu, popover, toast, and loading/empty/error/permission/busy/stale/success/progress states. Markdown renders plain text and only explicit HTTP(S) links; it never injects HTML.
- Dialog teardown removes keyboard handling, traps nested focus, restores the prior
  connected focus target, and supports Escape/backdrop/native button dismissal.

<a id="catalog-and-runtime"></a>

## 3. Catalog and runtime

- The versioned TypeScript catalog is the single descriptor and implementation registry. Every descriptor names its allowed region, closed properties, binding arrays, actions, states, accessibility behavior, provenance, and synthetic example. Registry construction rejects missing IDs and unsupported properties. Package tests exercise descriptor validity, ID uniqueness, complete implementation coverage, missing IDs, unsupported properties, and runtime instantiation.

- `apps/web` exposes the author/customer preview only at `/catalog`; normal product navigation remains unchanged. The preview switches theme, 180/268/520-pixel sidebar width, asset, and common state, and exposes real selection, search/filter, split, form, dialog, toast, focus, and resize behavior using explicitly synthetic data. Its narrow layout has a dedicated 390-pixel rule. Optional chart implementation remains outside the base bundle behind a lightweight frame.

- The Workbench sidebar schema adds `favorites-recent@1`; deterministic Python and TypeScript generated contract artifacts were regenerated. Contract fixtures add the favorites/recent sidebar and adjustable split descriptors. The runtime delegates asset construction to the same registry used by the preview.

<a id="asset-provenance-and-compatibility"></a>

## 4. Asset provenance and compatibility

- `packages/design-system/catalog/provenance.json` records exact legacy source paths and SHA-256 identities for six reviewed multicolor resource SVGs. Material Icon Theme 5.38.1 remains the file-tree source inventory, with its existing provenance and license retained under `static/ui`; Tabler 3.46.0 is retained as a legacy comparison input. No third-party generated JavaScript bundle was copied into the React implementation.

- Stable IDs are immutable within a major version, overlapping aliases are prohibited, and deprecation requires a named replacement and one release window before next-major removal. Legacy removal still requires consumer migration, byte/provenance comparison, visual/accessibility gates, and a rollback observation period.

<a id="verification-boundary"></a>

## 5. Verification boundary

- Work performed the authorized dependency lock update and deterministic contract generation only. It did not run tests, lint, type checks, builds, servers, browser checks, screenshots, or other verification. RF-300–308 therefore remain `부분 완료` until independent Verification runs the Stage 1 affected gates plus component tests, real Chromium previews at requested themes and widths, keyboard/focus and remount regressions, screenshots, and production build. The global legacy Ruff, packaging, source-inventory, runtime-image, and PostgreSQL limitations recorded after Stage 1 remain unchanged.

<a id="failed-verification-revision"></a>

## 6. Failed-Verification revision

- The revision following Verification run `run-20260912T112457925023Z-278b02af` addresses findings RF2-V001 through RF2-V006 without expanding the Stage 2 product scope:

- `resource-header@1` now has a real registered implementation, and the web package
  includes server-rendered regressions for both the retained Documents `/` route and
- the separate `/catalog` route.
- The task-list settings icon is now the unambiguous `preferences@1`; the panel retains
  `settings@1`. Descriptor IDs and implementation IDs remain one-to-one.
- DOM collections use `Array.from`, and the field child contract is compatible with
  React element construction, correcting the reported TypeScript errors.
- Descriptors now advertise only renderer-supported closed properties. Binding inputs,
  outputs, and actions are explicitly empty when no runtime callback exists; supported
- states reflect actual ready, empty, disabled, or feedback behavior. Per-asset examples use only accepted properties and are instantiated through the same registry in tests.
- The split layout changes to a real three-row mobile grid. At narrow width it exposes
  horizontal separator orientation, uses Up/Down keys and pointer Y coordinates, and
- updates the visible row percentage; desktop retains vertical orientation, Left/Right, and pointer X coordinates.
- Maintained tests now cover component interaction, search empty state, tab focus,
  mobile split semantics, dialog focus restoration/remount cleanup, unsafe Markdown,
- disabled inputs, normal/catalog route rendering, and a real Chromium matrix for all three themes, 180/268/520 widths, 390-pixel split resizing, screenshots, focus, and reload teardown.

- Work still did not execute these verification gates. This section records correction scope and intended coverage, not a pass claim.

<a id="second-failed-verification-revision"></a>

## 7. Second failed-Verification revision

- The revision following Verification run `run-20260912T113803579504Z-41c6b362` addresses RF2-R2-V001 through RF2-R2-V006:

- The React act-environment global uses an explicit type-safe intersection cast.
- Web Vitest configuration excludes `dist` and `dist-types`, keeping no-cleanup test
  discovery on authored sources after composite TypeScript output exists.
- The Chromium width assertion now follows the application-wide border-box contract.
- Mobile split rows use a definite 360-pixel frame and a numeric ratio over its
  328-pixel content track budget, so keyboard and pointer changes resolve to visible
- geometry rather than an indefinite percentage.
- Interactive descriptors now declare bounded inputs, outputs, and allowlisted actions.
  The implementation registry passes inputs to controls/compositions and dispatches
- typed `select`, `submit`, `toggle`, or `dismiss` events to the caller. It rejects unknown inputs, actions, outputs, types, and bounds. Catalog tests exercise every advertised action/output contract, while component tests exercise a real toggle transition.
- Dialogs use unique `useId` labels and an explicit open-dialog stack. Only the topmost
  layer owns Tab, Escape, and backdrop dismissal. Tests cover nested open/close order,
- unique labels, focus restoration through both layers, and destruction while open.

- These are Work corrections only. The independent no-cleanup checks, build, browser matrix, screenshots, and geometry assertions remain pending Verification.

<a id="final-independent-verification"></a>

## 8. Final independent Verification

- Verification run `run-20260912T121543075174Z-70a142f9` passed the final Stage 2 Work run `run-20260912T121403471303Z-1ed3b0ef` with no remaining findings. It passed frozen pnpm and uv installs, `git diff --check`, the full `make workbench-check` before and after an intervening `make workbench-build`, 17 design-system tests, the other package tests and 14 Python tests. The production Chromium catalog matrix exercised routing, all theme and region-width combinations, the 390-pixel viewport, keyboard focus, remount and overflow behavior, and produced ten screenshots in `/tmp/agent-factory-catalog-r6`. The existing Python deprecation warnings and unrelated legacy/full-refactor limitations remain unchanged.
