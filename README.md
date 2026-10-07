# Social Media Report Automation

An auditable multimodal social-media reporting engine that reconstructs campaigns from messy
screenshot evidence, validates metrics deterministically, and runs natively in Dify or as portable
Agent Skills.

The primary product experience is one Dify WebApp: upload Instagram, Facebook, or Meta campaign
screenshots—or a ZIP containing a human-organized folder—press Run, and receive a Markdown report
plus JSON and CSV audit artifacts. Campaign, client, creator, platform, format, and screenshot
relationships are inferred from evidence when possible and remain `unknown` when they are not.

## Architecture

```text
Dify WebApp / Workflow
        |
        v
project-owned Dify plugin
  intake, ZIP safety, hashes, file selection,
  validation, deterministic audit, export
        |
        v
src/social_report (one business-logic source of truth)
        ^
        |
portable Agent Skill wrappers
```

There is no Streamlit frontend, n8n dependency, standalone API service, queue, or database. n8n can
be added later only as an optional external trigger into Dify. OCR is off by design; vision models,
structured output, deterministic validation, and a confidence-gated second pass are the v1 path.

## What is implemented

- Direct multi-image and ZIP intake with MIME checks, SHA-256, optional difference hashes, and
  source manifests.
- In-memory ZIP processing with path traversal, absolute-path, symlink, encrypted-entry, nested
  archive, file-count, decompressed-size, and compression-ratio defenses.
- Global campaign reconstruction before per-asset extraction.
- Per-asset screenshot selection so detailed vision nodes do not receive the entire campaign.
- Canonical JSON Schemas for manifests, reconstruction, extraction, and audit output.
- Exact/approximate/missing/unreadable measurement semantics with simple provenance.
- Organic, paid, mixed-or-unknown, and unknown aggregation buckets.
- Lower-bound engagement rates, signed discrepancies, and Story temporal-consistency safeguards.
- A Dify workflow with a confidence-driven second pass and a report writer that cannot access
  screenshots or recompute metrics.
- JSON, CSV, and deterministic Markdown exports.
- A synthetic evaluation harness; no provider benchmark results are claimed.

## Dify quickstart

Requirements: Python 3.12 plugin runtime, Dify Plugin SDK 0.9.x, and an installed vision-capable
model with reliable UI text reading. The plugin manifest declares Dify 1.14.2 as its minimum; the
deployment helper is deliberately pinned to the released 1.14.2 and 1.17.1 API contracts. See the
[component-specific compatibility matrix](docs/DIFY_DEPLOYMENT.md) rather than assuming one broad
minimum for every operation.

```bash
uv sync --extra dev
uv run python scripts/package_plugin.py
cp .env.example .env.local
chmod 600 .env.local
uv run python scripts/dify_deploy.py discover
```

Then:

1. Configure distinct account OpenAPI and Console/CSRF credentials in the ignored `.env.local`.
2. Install and verify `dist/dify-social-report-0.1.1.difypkg` with `dify_deploy.py install-plugin`.
3. Import or update `deploy/dify/social-media-report.yml` with `dify_deploy.py import-workflow`.
4. Select the same suitable vision model in the reconstruction, extraction, second-pass, and report
   writer LLM nodes. The committed DSL intentionally has no provider/model hard-code.
5. Review deployment file limits and retention settings in [Dify deployment](docs/DIFY_DEPLOYMENT.md).
6. Run the direct-image and ZIP synthetic draft tests before publishing.

The plugin package shape and imports are locally verified. The DSL is statically validated but has
not been imported into a live Dify instance in this repository environment; see the status table
below.

## Agent Skills and CLI

The two Agent Skills remain independent of Dify:

```bash
python3 skills/social-report-audit/scripts/calculate_metrics.py examples/sample-input.json
python3 skills/story-series-extract/scripts/extract_story_series.py examples/sample-story-series-input.json
```

Both are thin wrappers over `src/social_report`.

## Development and verification

```bash
uv sync --extra dev
uv run ruff check src tests scripts evals plugins skills
uv run mypy
uv run python -m unittest discover -s tests -v
uv run python scripts/validate_dify_dsl.py
uv run python scripts/package_plugin.py
uv build
```

## Evaluation

Generate privacy-safe screenshot-like fixtures and score a real Dify/model run:

```bash
uv run python evals/generate_synthetic_fixture.py
uv run python evals/evaluate.py path/to/prediction.json
```

The scorer covers field extraction, exact-number fidelity, null-vs-zero semantics, scope,
asset/Story grouping, and deterministic numerical consistency. See [evals/README.md](evals/README.md).

## Verification status

| Area | Status | Evidence |
|---|---|---|
| Deterministic core | VERIFIED | Unit/regression tests, Ruff, mypy, package build |
| ZIP/folder intake | VERIFIED | Direct, invalid ZIP, traversal, nested archive, duplicate filename tests |
| Dify plugin package | VERIFIED | Official CLI package build and packaged-module import smoke test |
| Dify workflow structure | VERIFIED | YAML parse and graph/tool/model-boundary static validator |
| Live Dify import/run | NOT_RUNTIME_VERIFIED | No compatible Dify instance was available in this environment |
| Vision reconstruction/extraction | IMPLEMENTED_NOT_RUNTIME_VERIFIED | Prompts, schemas, grouping iteration, and second pass committed |
| Provider evaluation results | NOT_IMPLEMENTED | Harness exists; no paid model run or benchmark result is published |

## Privacy and security

Never commit campaign screenshots. The plugin does not call external services or create durable
storage; the surrounding Dify workflow sends images to the operator-selected model provider. Dify
upload, workflow-run, log, and output retention remain deployment responsibilities. Read
[privacy](docs/PRIVACY.md) and [security](SECURITY.md) before processing confidential material.

## Project layout

```text
src/social_report/                 canonical deterministic core
plugins/dify-social-report/        project-owned Dify plugin source
deploy/dify/                       workflow DSL and prompts
schemas/                           generated canonical JSON Schema artifacts
skills/                            portable Agent Skill entry points
evals/                             synthetic fixtures and scorer
tests/                             core, intake, workflow, and regression tests
docs/                              deployment, architecture, privacy, and SOP
```

Licensed under the [MIT License](LICENSE).
