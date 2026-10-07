# Dify deployment

## Compatibility is component-specific

| Component | Compatibility statement |
|---|---|
| Plugin manifest | Declares minimum Dify `1.14.2`; package shape is locally verified, not live-installed |
| Workflow DSL | Version `0.6.0`; statically validated, not live-imported |
| Deployment helper | Exact released API adapters for Dify `1.14.2` and `1.17.1` only |
| Plugin SDK | `0.9.x` |
| Plugin runtime | Python `3.12` |
| Packaging CLI | Dify Plugin CLI `0.6.10` |

The helper fails closed on other Dify versions. Supporting another release requires checking that
release's routes and response models and adding contract tests; GitHub `main` is not treated as a
released API contract.

## Local credentials

Copy `.env.example` to the ignored `.env.local` file and restrict its permissions:

```bash
cp .env.example .env.local
chmod 600 .env.local
```

Alternatively use `~/.config/social-report/dify.env` or pass `--env-file PATH`. Precedence, from
lowest to highest, is user config, repository `.env.local`, explicit env file, process environment,
and explicit command-line values.

The three credentials are deliberately distinct:

- `DIFY_OPENAPI_TOKEN`: account-scoped OAuth bearer used by the Dify `1.17.1` OpenAPI.
- `DIFY_CONSOLE_ACCESS_TOKEN`: existing authenticated Console access token.
- `DIFY_CSRF_TOKEN`: matching Console CSRF header/cookie token.

An App Service API key is not accepted as a fallback. The helper never logs complete tokens. Do not
commit `.env.local`, user configuration, cookies, passwords, or provider credentials.

## Build and discover

```bash
uv sync --extra dev
uv run python scripts/package_plugin.py
uv run python scripts/validate_dify_dsl.py
uv run python scripts/dify_deploy.py discover
```

Discovery uses the unauthenticated `GET /openapi/v1/_version` and `_health` routes on `1.17.1`, or
the released Console version route on `1.14.2`. Authenticated capabilities are reported separately
as `VERIFIED`, `UNAVAILABLE`, `UNAUTHORIZED`, `UNSUPPORTED_VERSION`, or `ERROR`. On Dify `1.17.1`,
OpenAPI calls automatically discover and attach the required `X-Dify-Catalog` header via
`/openapi/v1/_catalog`. When Console auth is configured, discovery lists only configured LLM models
that advertise vision/multimodal support; it does not read or modify provider secret values.

## Install and verify the plugin

```bash
uv run python scripts/dify_deploy.py install-plugin --replace-installed
uv run python scripts/dify_deploy.py plugin-status
```

The helper uses the released Console contracts:

- `POST /console/api/workspaces/current/plugin/upload/pkg`, multipart field `pkg`;
- `POST /console/api/workspaces/current/plugin/install/pkg` with `plugin_unique_identifiers`;
- bounded polling of `/plugin/tasks/{task_id}` using its wrapped `task` object;
- `/plugin/list` plus authoritative provider detail route
  `/console/api/workspaces/current/tool-provider/builtin/<provider>/tools` for tool declarations.

When signature verification is enforced by the live Dify plugin daemon, install packages signed
against the trusted daemon public key. Use `--replace-installed` to safely update an existing build
of the project plugin while preserving credentials.

`PASS` requires the exact unique identifier, version, checksum, loaded provider, and the six tool
names derived from `provider/social_report.yaml`. An empty tool response is `PARTIAL`, never a pass.

## Import or update the draft

For automated model binding, select an already configured model returned by `discover`:

```dotenv
DIFY_MODEL_PROVIDER=provider-identifier
DIFY_MODEL_NAME=vision-model-name
```

Then run:

```bash
uv run python scripts/dify_deploy.py import-workflow
```

The deployment copy is parsed as YAML and only LLM `model.provider` and `model.name` fields are
bound. The public repository DSL remains provider-independent. Binding fails unless the Console API
confirms an active configured vision model.

Import is idempotent by exact app name or explicit `--app-id`. Ambiguous duplicate names fail. On
`1.17.1`, the helper uses account-scoped OpenAPI import and its `:confirm` route. On `1.14.2`, it
uses the released Console `/apps/imports` and `/confirm` routes. Both paths require an empty
`leaked_dependencies` result before success.

## Draft and published runtime tests

Draft execution is the default and requires Console credentials:

```bash
uv run python scripts/dify_deploy.py smoke-test APP_ID --synthetic direct
uv run python scripts/dify_deploy.py smoke-test APP_ID --synthetic zip
```

For a published Dify `1.17.1` app, use:

```bash
uv run python scripts/dify_deploy.py smoke-test APP_ID --synthetic direct --mode published
```

The helper uploads each file through the version-specific released endpoint and supplies the file
objects to the workflow's `inputs.files` variable. A pass requires:

- `status == succeeded`;
- non-empty `report_markdown`;
- structured `audit_json` with a valid review status, all four scope buckets, and warnings list;
- non-empty `json_files` and `csv_files` arrays.

The combined live check is opt-in so normal CI cannot spend model credits:

```bash
DIFY_LIVE_TEST=1 uv run python scripts/dify_deploy.py verify-live APP_ID --synthetic zip
```

## Safe export

```bash
uv run python scripts/dify_deploy.py export-workflow APP_ID
```

Exports always request `include_secret=false`. Model bindings are cleared structurally, never with
regular expressions, and the exported graph/tool/edge structure must match the repository DSL
before a file is written.

## Self-hosted file limits

Inspect the variables exposed by the exact deployed release before changing them:

```dotenv
UPLOAD_FILE_SIZE_LIMIT=25
UPLOAD_IMAGE_FILE_SIZE_LIMIT=25
UPLOAD_FILE_BATCH_LIMIT=30
IMAGE_FILE_BATCH_LIMIT=30
WORKFLOW_FILE_UPLOAD_LIMIT=30
SINGLE_CHUNK_ATTACHMENT_LIMIT=30
```

Restart the relevant Dify services after deployment configuration changes. The plugin separately
enforces 100 files maximum, 25 MiB per file, 100 MiB total ZIP uncompressed size, nested archive
rejection, and a 100:1 per-entry compression-ratio ceiling.

### Operational note: Internal nginx DNS resolver

In containerized deployments, Dify's internal nginx proxy may cache upstream container IP addresses.
If service containers (such as the plugin daemon) restart with newly assigned internal IPs, nginx
may return `502 Bad Gateway` until its resolver TTL expires or the nginx container is reloaded
(`docker exec docker-nginx-1 nginx -s reload`).

Only record `LIVE_DIFY_VERIFIED` after plugin installation, dependency checking, model binding, and
the required synthetic draft scenarios have actually completed on the named Dify/model combination.
