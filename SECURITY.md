# Security policy

## Reporting a vulnerability

Do not attach private campaign evidence to a public issue. Report reproducible security defects to
the repository owner through GitHub's private vulnerability reporting channel when available.

Include the affected version, component, impact, and a synthetic proof of concept. Remove API keys,
signed URLs, account handles, and client data.

## Supported surface

Security fixes target the latest release and the current `main` branch. Archive parsing, upload
validation, Dify plugin boundaries, and accidental data retention are security-sensitive areas.

## Archive limits

ZIP processing rejects traversal and absolute paths, symlinks, encrypted entries, nested archives,
unsupported files, excessive file counts, excessive uncompressed size, and suspicious compression
ratios. Do not weaken these limits without tests and a documented deployment need.
