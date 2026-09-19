# Workspace Kanban full-height restoration evidence

## Execution target

- Work Unit: `workspace-kanban-full-height-restoration`
- Attempt: revision 1, attempt 1
- Invocation: `019fc33b-37a8-79e1-a7b5-ea8ef4bd9d8c`
- Worktree branch: `work-unit/workspace-kanban-full-height-restoration`

## TDD evidence

- Before the source change, `node --test test/unit/webviewShell.layout.test.js` failed with `board bottom 168 should match panel bottom 900`.
- Root cause: the hidden error element did not occupy the first explicit grid row, so auto-placement put `.kanban-board` in the content-sized first row and left the `1fr` second row empty.
- Source correction: `.kanban-board` is explicitly assigned to grid row 2. The existing first row remains available for visible error content.

## Verification

- `node --test test/unit/webviewShell.layout.test.js test/unit/webviewShell.test.js`: 12 passed, 0 failed.
- `npm run check`: syntax checks and 33 unit tests passed, 0 failed.
- `git diff --check`: passed.
- Changed paths are limited to `workspace/src/webviewShell.js` and `workspace/test/unit/webviewShell.layout.test.js`.
- Runtime: Google Chrome 144.0.7559.132.
- Work Unit commit: `01462ba74df6581480c5a5607426f15eb9ed609a` (`Restore full-height workspace Kanban`).
- Post-report worktree inspection: branch `work-unit/workspace-kanban-full-height-restoration`, clean status, no pending changes, expected locked worktree identity.

## Rendered geometry at 1440 x 900

- Viewport, document scroll height, and body scroll height: 900px.
- Workspace body client height and scroll height: 828px / 828px.
- Active Kanban panel: top 72px, bottom 900px, height 828px.
- Kanban board: top 72px, bottom 900px, height 828px.
- All six empty columns: bottom 900px, height 828px.
- All six card-list bodies: bottom 900px.
- Every measured column contained its empty-state element.

## AI Review

- Height ownership is continuous from the 100vh shell through the remaining grid row, active panel, Kanban workspace, explicitly placed board, columns, and card lists.
- The new regression uses Chromium `getBoundingClientRect`, client height, and scroll height instead of matching CSS strings.
- Empty columns occupy the complete board height.
- Document, body, and workspace body have no vertical outer overflow in the measured layout.
- Existing tests confirm no notice, metadata, actions, draggable behavior, card tabindex, or transition affordances were reintroduced.
- Existing localStorage tests confirm valid column visibility values still persist and damaged or unavailable storage still falls back safely.
- No Agents Chat or other Workspace tab behavior was changed.

## Human review boundary

- Human visual confirmation remains pending in the Extension Development Host.
- Integration, cleanup, push, deployment, and server restart were not performed.
