# Privacy and data handling

Campaign screenshots may contain confidential commercial information, personal handles, audience
statistics, or advertising data.

- Never commit screenshots, archives, generated private reports, credentials, or signed file URLs.
- The plugin performs deterministic processing in the Dify plugin runtime and creates no database.
- ZIP content is read in memory and is not extracted into an arbitrary filesystem location.
- The plugin does not log image bytes, base64 content, credentials, or full signed URLs.
- The configured Dify model provider receives images during reconstruction, extraction, and any
  targeted second pass. Operators must review that provider's terms, region, retention, and training
  settings.
- Dify may retain uploads, workflow runs, logs, and output files. Configure retention, backups,
  access control, and deletion according to organizational policy.
- Public fixtures are synthetic. Generated PNG evaluation fixtures are ignored by Git.

For deletion or incident handling, follow the operating procedure of the Dify deployment and model
provider; this repository has no independent copy of uploaded campaign data.
