# Privacy Policy

## Data processed

The plugin processes files that the user uploads to Dify and structured campaign JSON produced in
the workflow. Screenshots may contain account handles, campaign details, audience statistics, or
other confidential business information.

## Data use and sharing

Processing is limited to file validation, hashing, in-memory ZIP reading, structured-data
validation, deterministic calculations, and requested exports. The plugin does not send content to
third-party services. Vision model disclosure is the responsibility of the surrounding Dify
workflow and its configured model provider.

## Retention

The plugin does not create its own durable data store. Temporary bytes live only for the plugin
invocation. Dify may retain uploads, workflow runs, logs, and outputs according to the operator's
deployment and retention configuration.

## Logging

The plugin does not log image bytes, base64 content, credentials, or signed file URLs. Errors may
identify a filename or relative ZIP path so an operator can locate invalid evidence.

## Contact

Open a privacy or security issue in the source repository without attaching confidential campaign
material.
