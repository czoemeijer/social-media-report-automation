# Dify deployment

## Compatibility baseline

- Dify: 1.14.2 or newer
- Plugin runtime: Python 3.12
- Dify Plugin SDK: 0.9.x
- Dify CLI used for local package verification: 0.6.10
- Workflow DSL export shape: 0.6.0

The package builds and imports as Python modules locally. A live Dify installation was not available
for an actual plugin install, workflow import, or end-to-end run, so that compatibility gate remains
open.

## Install

```bash
uv sync --extra dev
uv run python scripts/package_plugin.py
uv run python scripts/validate_dify_dsl.py
```

Install `dist/dify-social-report-0.1.0.difypkg`, then import
`deploy/dify/social-media-report.yml`.

Alternatively, use the automated deployment helper `scripts/dify_deploy.py`:

```bash
# Discover deployment state, version, providers, vision models, limits
uv run python scripts/dify_deploy.py discover

# Verify installed plugin status & 6 tools
uv run python scripts/dify_deploy.py plugin-status

# Upload and install .difypkg
uv run python scripts/dify_deploy.py install-plugin dist/dify-social-report-0.1.0.difypkg

# Import or overwrite workflow DSL via OpenAPI / Console
uv run python scripts/dify_deploy.py import-workflow deploy/dify/social-media-report.yml [--app-id ID]

# Execute end-to-end synthetic runtime smoke test
uv run python scripts/dify_deploy.py smoke-test <app_id> --synthetic

# Export working DSL and sanitize deployment-specific bindings
uv run python scripts/dify_deploy.py export-workflow <app_id> deploy/dify/social-media-report.yml --sanitize
```

The DSL leaves all model names empty. In Dify, select a model for each LLM node. Required
capabilities are vision, strong UI/text reading, adequate image/context limits, and preferably native
structured JSON output. Model/provider names are deployment choices, not repository constants.

## Self-hosted file limits

Current upstream Dify exposes these environment variables. Inspect the variables available in the
exact deployed release before changing them:

```dotenv
UPLOAD_FILE_SIZE_LIMIT=25
UPLOAD_IMAGE_FILE_SIZE_LIMIT=25
UPLOAD_FILE_BATCH_LIMIT=30
IMAGE_FILE_BATCH_LIMIT=30
WORKFLOW_FILE_UPLOAD_LIMIT=30
SINGLE_CHUNK_ATTACHMENT_LIMIT=30
```

Values for size limits are megabytes. Restart the relevant Dify services after changing deployment
configuration. The committed workflow mirrors a 30-file, 25 MB-per-file operator target. The plugin
adds its own safeguards: 100 files maximum, 25 MB per file, 100 MB total ZIP uncompressed size
(safely bounded within the 256 MiB plugin memory limit), and a 100:1 per-entry compression-ratio ceiling.

For campaigns larger than the configured limits, use a ZIP to preserve directory evidence and split
truly large campaigns into coherent runs. The workflow uses a low-detail global pass and sends only
the current asset group's images to each detailed extraction iteration.

## Import and runtime verification checklist

1. Install the `.difypkg` without manifest or dependency errors.
2. Import the DSL without node migration warnings.
3. Bind one suitable model to the four LLM nodes.
4. Run a direct multi-image synthetic case.
5. Run the generated synthetic ZIP/folder case.
6. Confirm one Reel with multiple tabs becomes one asset.
7. Confirm Story scroll slices and later snapshots are grouped correctly.
8. Confirm missing Shares remains null and yields only a lower-bound ER.
9. Confirm organic and paid buckets remain separate.
10. Export JSON and CSV; retain the Dify run record as evidence.

Only after these checks may the DSL be called runtime verified for that Dify/model combination.
