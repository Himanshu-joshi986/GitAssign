# Security Policy

## Supported versions

Only the latest revision of `main` is supported with security updates.

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Instead, use
GitHub's private vulnerability reporting:

1. Open the repository's **Security** tab.
2. Choose **Report a vulnerability**.
3. Include affected endpoints or components, reproduction steps, and the
   potential impact.

You can expect an acknowledgement within 72 hours and a remediation plan within
seven days for confirmed issues.

## Operational guidance

- Store `GITHUB_TOKEN` in `.env` or your deployment's secret manager. Never
  commit it. Production tokens should use the minimum scopes required.
- GitAssign previews assignments by default. Keep
  `AUTO_ASSIGN_NEW_ISSUES=false` unless you have reviewed the workflow and
  granted a token with write access to the target repository.
- The SQLite database and GitHub cache under `data/` may contain repository
  metadata. Treat them as private runtime data and exclude them from backups
  or images that are shared publicly.
