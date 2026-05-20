---
name: agent-factory-verification
description: Use when deciding how to validate Agent Factory changes. Select focused tests based on the touched boundary, avoid broad test runs by default, and report exactly what was verified.
---

# Agent Factory Verification

Use this skill before claiming Agent Factory changes are complete.

## Test Selection

- Hooks/guards: `.agent-factory/tests/adapters/hooks` and matching `tests/application/apps/test_hooks_*`.
- Board API: `.agent-factory/tests/contracts/board_api`.
- LLM providers: `.agent-factory/tests/adapters/llm`, `.agent-factory/tests/application/llm`, and orchestration tests.
- Git/filesystem/sync adapters: matching `.agent-factory/tests/adapters/{git,filesystem,sync}`.
- Domain contracts: matching `.agent-factory/tests/domain/*`.
- Layout moves: architecture tests plus targeted import checks.

## Workflow

1. Compile changed Python modules when imports or paths changed.
2. Run the smallest tests that cover the modified boundary.
3. If tests are skipped or too broad, state that clearly.
4. For file moves, add at least one import check or focused test that exercises the new path.
5. Do not hide unrelated failing tests; identify whether they are outside the touched scope.

## Reporting

Final reports should include:

- changed boundary
- exact validation commands
- pass/fail/skipped result
- residual risk when validation was partial

