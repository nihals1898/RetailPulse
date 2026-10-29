# Phase 18 — GitHub portfolio checklist

This is a local publication-readiness review. It does not create a GitHub
repository, add a remote, commit files, or publish the project.

## Preflight findings

| Area | Finding |
| --- | --- |
| Project presentation | README, architecture diagram, setup instructions, evidence, and focused guides are present. |
| Local repository | Git repository is on branch `main`; it has no commits and no configured remote. Project files are currently untracked. |
| Generated data | Default CSV inputs, SQLite database, processed exports, and benchmark outputs are excluded by `.gitignore`. The sample data is synthetic. |
| Environment and logs | `.venv`, local logs, work outputs, `.env`, and `.env.*` are ignored. `.env.example` contains placeholders only. |
| Credential scan | A limited pattern scan of source and configuration files found no common private-key, AWS access-key, embedded-credential URL, or hard-coded secret patterns. This is a preflight aid, not a guarantee. |
| Power BI report | `dashboards/powerbi/RetailPulse.pbix` exists locally (2,401,240 bytes) and is ignored by Git. Screenshots shared by the user show the Sales Overview, Products & Returns, and Inventory pages. Data Source Settings shows absolute CSV paths under `C:\Users\nihal\...`, revealing the Windows account name and local folder structure. The PBIX contents have not been independently opened, and the report has not been published. |
| CI/CD | `azure-pipelines.yml` is a local configuration file; Azure Pipelines is not connected or run. No GitHub Actions workflow or hosted status badge is present. |
| Publication | No GitHub remote or public repository is configured. Nothing has been published. |

## Before making a GitHub repository

- [x] Explain the project, setup, architecture, measured results, and limitations in the README.
- [x] Keep generated raw/processed data, temporary benchmark outputs, environments, and secrets out of Git.
- [x] Confirm the only environment template contains placeholders and the source/config credential scan has no matches.
- [x] Identify the local PBIX and report the inspection/publishing status accurately.
- [x] Exclude the PBIX from Git until its source paths are neutralized; the current file paths reveal the Windows account name and local folder structure.
- [ ] If the PBIX is to be shared later, review it in Power BI Desktop for synthetic data only and unwanted metadata, then sanitize the paths and re-review the ignore rule.
- [ ] Save selected report screenshots under the project if visual examples should appear in the public repository.
- [ ] Choose public or private visibility and select a license only if the owner wants others to reuse the code.
- [ ] Review every candidate file and the staged diff before creating the initial commit. See [DevOps Git workflow](devops.md).
- [ ] Configure the actual GitHub remote after creating/selecting the destination repository; do not invent a remote URL.
- [ ] If publishing, verify the remote contents, README rendering, and repository visibility. Describe Azure Pipelines as unhosted unless it has actually run.

## Current publication status

The project is prepared for owner review, but it is **not published to GitHub**.
It has no initial commit or remote. The next publication steps require the owner
to review the staged file list, decide repository visibility and licensing,
create or select the destination repository, and provide its actual remote URL.
