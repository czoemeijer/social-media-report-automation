# Social Report Dify Plugin

Project-owned deterministic tools for the Social Media Report workflow.

The plugin requires no credentials and makes no third-party network calls. Dify supplies uploaded
files to the plugin runtime. The plugin validates input, safely reads ZIP archives in memory,
normalizes structured vision output, performs scope-aware calculations, and exports audited data.

## Tools

- `prepare_campaign_input`: MIME validation, limits, SHA-256, perceptual hash, and manifest.
- `unpack_campaign_archive`: bounded ZIP reading with traversal, symlink, nested archive, and bomb protection.
- `select_asset_files`: sends only one reconstructed asset's screenshots to detailed extraction.
- `validate_extraction`: canonical measurement and confidence validation.
- `audit_campaign`: deterministic metrics, Story-safe semantics, scope buckets, and warnings.
- `export_campaign`: JSON, CSV, or deterministic Markdown file output.

## Build

From the repository root, run:

```bash
uv run python scripts/package_plugin.py
```

The build script stages the canonical `src/social_report` package into the plugin package before
calling the official Dify CLI. This avoids maintaining a second copy of the business logic.

## Compatibility

The source contract targets Dify 1.14.2 or newer, Python 3.12, and Dify Plugin SDK 0.9.x. A
successful `.difypkg` build validates the manifest/package shape but is not an installation test.
