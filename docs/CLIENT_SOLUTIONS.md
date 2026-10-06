# Client and UI architecture

The only maintained product surface is the Dify WebApp defined by
`deploy/dify/social-media-report.yml`.

Non-technical users see two inputs:

- Upload screenshots or campaign ZIP (required)
- Optional instructions (language, reporting period, or contextual note)

Dify owns authentication, upload UX, model-provider selection, orchestration, workflow runs, and
the final WebApp. The project-owned plugin handles deterministic file and reporting work. The
canonical core remains reusable by the Agent Skills.

Streamlit is not maintained, and n8n is not in the core execution path. If an organization later
needs email, schedule, Google Drive, or notification triggers, n8n may call Dify externally; Dify
must not call n8n and then return to Dify.

See [DIFY_DEPLOYMENT.md](DIFY_DEPLOYMENT.md) for installation and operator settings.
