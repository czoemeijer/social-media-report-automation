# Security policy

## Reporting a vulnerability

Do not attach private campaign evidence to a public issue. Report reproducible security defects to
the repository owner through GitHub's private vulnerability reporting channel when available.

Include the affected version, component, impact, and a synthetic proof of concept. Remove API keys,
signed URLs, account handles, and client data.

## Supported surface

Security fixes target the latest release and the current `main` branch. Archive parsing, upload
validation, Dify plugin boundaries, and accidental data retention are security-sensitive areas.

## Meta credentials

Store Meta tokens and app secrets only in the process environment or ignored `.env.local`. The
Meta client redacts credential query parameters, discards credential-bearing paging URLs, applies
`appsecret_proof` when an app secret is configured, and emits structured errors without raw bodies.
Never commit token debug output, production asset payloads, real account identifiers, or campaign
names. The integration is read-only and needs `ads_read`, not `ads_management`, for Ads reporting.

Long-lived and System User tokens can still be invalidated when permissions, assets, roles, or
business settings change. Run `social-report meta doctor` as an operational health check.

## Archive limits

ZIP processing rejects traversal and absolute paths, symlinks, encrypted entries, nested archives,
unsupported files, excessive file counts, excessive uncompressed size, and suspicious compression
ratios. Do not weaken these limits without tests and a documented deployment need.
