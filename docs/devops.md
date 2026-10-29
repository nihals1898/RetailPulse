# Phase 12 — Git workflow and Azure DevOps

This phase adds a local Git workflow guide and an Azure Pipelines definition. The YAML is a repository artifact only: it has not been connected to an Azure DevOps organization, hosted agent, or remote repository, and no pipeline run or hosted artifact is claimed.

## Git workflow

The repository currently has an initialized `main` branch with no commits and no configured remote. Before the first commit, review the entire project and confirm generated data, `.env` files, credentials, and machine-specific outputs are excluded. The `.gitignore` already excludes `.env`, virtual environments, logs, and generated raw/processed data; `.env.example` is safe only while it contains placeholders.

For the initial local baseline, review the project and `.gitignore`, stage non-ignored files, then inspect exactly what will be committed:

```powershell
git status --short
git diff --check
git add -A
git diff --cached --stat
git diff --cached
```

Only stage other files after reviewing them. Then commit the reviewed baseline:

```powershell
git commit -m "Add RetailPulse project baseline"
```

For subsequent work, use a short-lived branch and a focused pull request:

```powershell
git switch main
git pull --ff-only
git switch -c feature/<short-description>
# make one focused change
git status --short
git diff --check
git diff
git add <reviewed-paths>
git diff --cached
git commit -m "Describe the change"
git push -u origin feature/<short-description>
```

Open a pull request against `main`, review the diff and pipeline result, address feedback, then merge using the repository's chosen policy. `origin` must exist before pull/push commands work; do not invent a remote URL. Publishing to a remote is a user-controlled step. Do not commit secrets, local `.venv`, generated run artifacts, customer data, or credentials. Confirm exclusions with `git status` and the staged diff before each commit.

## Azure Pipelines design

[`azure-pipelines.yml`](../azure-pipelines.yml) triggers for changes to `main` and pull requests targeting `main`. It defines two stages on a Microsoft-hosted Ubuntu agent:

1. **Validate:** selects Python 3.13, installs the project and development extras, checks that the CLI starts, runs pytest, and runs Ruff on `src` and `tests`. Ruff's existing source-wide E501, I001, UP017, and UP035 findings are excluded; the remaining configured checks run.
2. **Package:** runs only after Validate succeeds, builds a wheel, and publishes it as the `retailpulse-wheel` pipeline artifact.

The package requires Python `>=3.11,<3.14`, so Python 3.13 is inside the declared support range. Spark and Delta extras are omitted from CI to avoid installing large optional runtimes for the base package. pytest runs against the focused local suite added in Phase 13.

## Connect and run later

To use the definition, the owner must select or create an Azure DevOps organization/project, add the repository using its actual remote URL, and authorize the pipeline service connection/repository permissions. Then create a pipeline that points to `/azure-pipelines.yml`. Confirm the selected agent image and Python task are available in that organization before enabling triggers. No subscription, service connection, Azure resource, hosted run, or cost estimate was created in this phase.

Before a hosted run, review the configured triggers, project visibility, repository permissions, branch protection, available hosted parallelism, and any organization-specific billing. Avoid adding credentials until a pipeline needs them; store required secrets in a protected variable group or Key Vault integration and never print them in logs.

## Current status

| Capability | Status |
|---|---|
| Local Git workflow guidance | Documented |
| Azure Pipelines multi-stage YAML | Added and reviewed locally |
| Remote repository | Not configured |
| Azure DevOps organization/project or pipeline | Not connected or created |
| Hosted execution and artifact | Not run or produced |
| Automated pytest coverage | Added in Phase 13; wired into the pipeline definition |
