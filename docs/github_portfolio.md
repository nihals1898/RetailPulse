# Phase 18 — GitHub portfolio checklist

This checklist records the local portfolio preflight and the subsequent initial
GitHub push. It does not claim to have independently inspected the PBIX or
verified repository visibility.

## Preflight findings

| Area | Finding |
| --- | --- |
| Project presentation | README, architecture diagram, setup instructions, evidence, and focused guides are present. |
| Local repository | Branch `main`; root commit `bc98414` is pushed to `origin/main`. Later Phase 19 documentation updates are currently local and need a follow-up commit/push. |
| Generated data | Default CSV inputs, SQLite database, processed exports, and benchmark outputs are excluded by `.gitignore`. The sample data is synthetic. |
| Environment and logs | `.venv`, local logs, work outputs, `.env`, and `.env.*` are ignored. `.env.example` contains placeholders only. |
| Credential scan | A limited pattern scan of source and configuration files found no common private-key, AWS access-key, embedded-credential URL, or hard-coded secret patterns. This is a preflight aid, not a guarantee. |
| Power BI report | `dashboards/powerbi/RetailPulse.pbix` exists locally (2,401,240 bytes) and is ignored by Git. Screenshots shared by the user show the Sales Overview, Products & Returns, and Inventory pages. Data Source Settings shows absolute CSV paths under `C:\Users\nihal\...`, revealing the Windows account name and local folder structure. The PBIX contents have not been independently opened, and the report has not been published. |
| CI/CD | `azure-pipelines.yml` is a local configuration file; Azure Pipelines is not connected or run. No GitHub Actions workflow or hosted status badge is present. |
| Publication | Baseline commit pushed to `https://github.com/nihals1898/RetailPulse`; the owner-selected public/private visibility has not been independently verified. |

## Before making a GitHub repository

- [x] Explain the project, setup, architecture, measured results, and limitations in the README.
- [x] Keep generated raw/processed data, temporary benchmark outputs, environments, and secrets out of Git.
- [x] Confirm the only environment template contains placeholders and the source/config credential scan has no matches.
- [x] Identify the local PBIX and report the inspection/publishing status accurately.
- [x] Exclude the PBIX from Git until its source paths are neutralized; the current file paths reveal the Windows account name and local folder structure.
- [ ] If the PBIX is to be shared later, review it in Power BI Desktop for synthetic data only and unwanted metadata, then sanitize the paths and re-review the ignore rule.
- [ ] Save selected report screenshots under the project if visual examples should appear in the public repository.
- [ ] Choose public or private visibility and select a license only if the owner wants others to reuse the code.
- [x] Review the candidate files and staged diff before the initial commit. See [DevOps Git workflow](devops.md).
- [x] Configure the GitHub remote and push the local baseline commit.
- [ ] Verify the remote page, README rendering, and repository visibility. Describe Azure Pipelines as unhosted unless it has actually run.

## Current publication status

The local baseline commit is published at the configured GitHub remote. The
owner should confirm the repository visibility and rendered contents in the
browser. The PBIX remains excluded because its data-source paths contain the
Windows account name. No license has been added.
