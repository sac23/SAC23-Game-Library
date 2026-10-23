# Security and privacy

- The HTTP server binds only to `127.0.0.1`, and checks Host, Origin and write request Content-Type.
- The scanner reads game files but does not edit/move/execute them. Only select game folders you trust.
- Library settings, file paths and cached art live under `%LOCALAPPDATA%\SAC23_Game_Library` on Windows.
- Optional API keys are stored unencrypted. Keep `library.json` out of public repositories and bug reports.
- Cover reports omit full paths but include some package filenames, which should be reviewed before sharing.
- Do not expose this development server via a public host or reverse proxy.
- If GitHub private vulnerability reporting is enabled, use it for security issues rather than posting exploit details publicly.
