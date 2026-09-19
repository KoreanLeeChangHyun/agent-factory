---
name: workbench-stage1-evidence-20260912
description: Workbench refactor stage 1 implementation evidence을 확인할 때 사용합니다.
document-type: processed
category: process
domain: null
language: ko
provenance:
  prior-provenance: null
  merged-from:
  - docs/processed/notes/2026-09-12-workbench-stage1-evidence.md
  source-language-policy: 원문·인용·코드·식별자는 원래 언어를 보존합니다.
  merge-request: run-20260918T152016183617Z-2d18ad49
  renamed-from: docs/processed/process-2026-09-12-workbench-stage1-evidence
  classification-request: run-20260918T154226499325Z-8d8d4959
---


# Workbench refactor stage 1 implementation evidence

<a id="scope-and-authority"></a>

## 1. Scope and authority

- This dated note records the RF-100–105 and RF-200–204 implementation slice. It is Processed implementation evidence, not a replacement for the maintained ADRs or platform specifications. The legacy `app/`, `template/`, and `static/` feature paths remain unchanged.

<a id="implemented-contracts"></a>

## 2. Implemented contracts

- `contracts/schemas/workbench/v1/` owns closed definition, release, descriptor,
  sidebar, panel, component, binding, action, and view-state schemas.
- `contracts/schemas/catalog/v1/asset-descriptor.schema.json` uses a fixed parameter
  vocabulary rather than accepting embedded JSON Schema. Catalog parameters are
- bounded scalar/list declarations; external references and arbitrary schema keywords are not representable.
- `contracts/schemas/appearance/v1/theme-profile.schema.json` permits only the
  `dark`, `light`, and `high-contrast` foundations, compact/comfortable density, and
- approved semantic color tokens. It has no CSS, SVG, import, URL, header, or credential field.
- Workbench v1 is deliberately a fixed, versioned vocabulary. New action kinds,
  binding sources, layout families, or executable capabilities require a schema and
- renderer version change; unknown properties remain rejected. Future extensibility is not modeled as free-form extension objects.

- The bounded runtime policy is 262,144 encoded bytes, depth 12, 5,000 JSON nodes, 4,096 characters per string, and 100 milliseconds measured validation time. Component counts are additionally limited to 40 in the 사이드바 and 80 in the 패널. Schema generation rejects traversal, network, and cross-directory references; only local fragments and sibling schema filenames are accepted.

<a id="generated-packages-and-gates"></a>

## 3. Generated packages and gates

- `scripts/generate_workbench_contracts.py` deterministically emits useful TypedDict and TypeScript interfaces plus canonical schema/fixture bundles. `--check` compares the expected bytes with every generated file without depending on Git tracking. Python and TypeScript validators apply the same limit source and schema bundle. The parity gate runs both validators over the same valid and invalid manifest.

- The compatibility gate examines required properties, removed closed-object properties, narrowed types/enums, and tightened numeric/string/collection bounds. Its fixtures prove both an additive compatible change and multiple real breaking changes; it does not infer compatibility from a version label.

- The dependency guard parses Python imports and TypeScript static, export, `require`, and dynamic imports. It checks forbidden core SDK/framework imports and relative cross-package bypasses. Root tests include explicit violations and allowed core → contracts and adapters → core examples.

<a id="verification-finding-revision"></a>

## 4. Verification-finding revision

- The revision after failed Verification reconciles camel-case state/input identifiers with the bounded path vocabulary used by the Documents fixture. Component properties now use an explicit fixed allowlist instead of a negative property-name list, and text values reject URL schemes, protocol-relative URLs, executable expressions, and raw markup. Dedicated fixtures cover WebSocket, FTP, access-token, and request-header bypasses.

- Compatibility analysis now covers constants, patterns, object closure, constrained additional properties, uniqueness, formats, type/enum restrictions, bounds, local references, combinators, items, and pattern properties used by the Stage 1 vocabulary. Generated types now include every asset parameter field and precise component/catalog state, asset kind, parameter type, sidebar/panel asset, accessibility, provenance, and theme-override structures. Python and TypeScript type fixtures exercise all parameter variants and nested structures.

- The dependency guard now parses `pyproject.toml` project, optional, and build-system requirements plus `package.json` runtime, optional, peer, and development dependencies. Manifest fixtures cover forbidden and allowed Python and TypeScript dependency edges.

- The subsequent TypeScript revision uses AJV's declared named `Ajv2020` constructor, which avoids default-import interop ambiguity under NodeNext. The parity entrypoint uses the command-owned repository-root working directory rather than non-portable `import.meta.dirname`, allowing the pinned `tsx` runner to select either module transform without changing fixture resolution.

<a id="minimal-composition"></a>

## 5. Minimal composition

- `packages/platform-core` contains a framework-independent Workbench query and port.
- `packages/platform-adapters` provides the stage-1 reference-fixture port adapter.
- `apps/api` composes FastAPI liveness, readiness, and reference fixture routes.
  Readiness returns 503 when `DATABASE_URL` is absent and explicitly reports that no
- database check ran; configuration alone is not represented as a live DB check.
- `apps/worker` exposes only an explicit offline `--smoke` fixture validation mode.
- `apps/web` is a minimal Vite/React health surface using the shared generated fixture,
  runtime, semantic tokens, and canonical 작업 목록 | 사이드바 | 패널 regions.
- The design-system catalog includes eight task icons, seven sidebar/navigation
  entries, nine panel layouts, controls, displays, feedback assets, full state/action
- metadata, accessibility metadata, provenance, examples, and unique versioned IDs.

<a id="locks-and-independent-verification"></a>

## 6. Locks and independent verification

- The revision Work generated real root `pnpm-lock.yaml` and `uv.lock` files from the declared workspace manifests. Work did not run verification. Independent Verification run `run-20260912T110652332335Z-131f19c5`, bound to Work run `run-20260912T110519020161Z-d6ce4e31`, subsequently passed the Stage 1 slice at commit `301a4ea`.

```sh
pnpm install --frozen-lockfile                         # passed with pnpm 10.15.1 / Node 22
uv sync --frozen --all-packages --extra dev           # passed with uv 0.8.15
make workbench-check                                  # passed
uv run agent-factory-worker --smoke                   # passed
make workbench-build                                  # passed
make workbench-check                                  # passed again without cleanup
```

- The common Workbench gate covered formatting, Ruff, ESLint, TypeScript and mypy, deterministic generation, validator parity, compatibility and dependency checks, six TypeScript tests, and 14 Python tests. The build transformed 211 Vite modules and built all six Python sdists and wheels. The second no-cleanup gate demonstrates that generated `dist-types` output no longer breaks dependency inspection.

- This evidence does not make the global legacy baseline green. Root `make check` still encounters pre-existing Ruff formatting drift after dependency resolution, and the legacy full pytest surface retains packaging/setuptools, source-inventory, runtime-image, and PostgreSQL prerequisite limitations. Those limitations remain outside the Stage 1 focused pass and are not reclassified here.
