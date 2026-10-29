# Phase 10 — Databricks workspace guide

Phase 10 prepares importable notebooks and a manual run path for an existing Databricks workspace. It does **not** create a workspace, start compute, create a Job, provision a catalog, or create secrets. Those actions can require account permissions and incur charges.

## Databricks concepts

| Concept | Role in this project |
|---|---|
| Workspace | Collaborative environment for notebooks, files, Git folders, and Jobs. It is the user interface and project container; it is not the Spark engine. |
| Compute | Serverless compute or a configured cluster provides the Spark runtime that executes notebooks and Jobs. For governed data, select compute supported by Unity Catalog. |
| Notebook | Interactive document that combines explanation and executable cells. The provided `.py` source notebooks include Databricks' notebook marker and cell separators. |
| Lakeflow Job | Orchestrates tasks such as notebook runs, dependencies, parameters, compute, schedules, and run history. |
| Unity Catalog | Governance layer and namespace for data objects. The usual structure is metastore → catalog → schema → table, with access controls, lineage, and audit capabilities. |
| Secrets | Credential store for tokens, passwords, and keys. Keep values out of notebook source, widgets, and logs. The demo uses synthetic inline data and needs no secret. |

Official references: [Databricks notebook formats](https://docs.databricks.com/aws/en/notebooks/notebook-format), [import/export notebooks](https://docs.databricks.com/aws/en/notebooks/notebook-export-import), [Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog), [Lakeflow Jobs quickstart](https://docs.databricks.com/aws/en/jobs/jobs-quickstart), and [Unity Catalog secrets](https://docs.databricks.com/aws/en/security/secrets/unity-catalog-secrets).

## Included notebooks

| Notebook | Purpose |
|---|---|
| `notebooks/databricks/01_workspace_preflight.py` | Shows Spark/Python versions and the active catalog/schema; explains workspace, compute, Jobs, and secret boundaries. |
| `notebooks/databricks/02_delta_merge_demo.py` | Creates a small managed Unity Catalog Delta table, merges one changed product and one insert while preserving an unchanged product, then checks operation history and time travel. |

These are Databricks source-format notebooks, not ordinary local scripts. The first-line `# Databricks notebook source` marker identifies the file as a notebook when imported; `# COMMAND ----------` separates cells. Databricks also supports `.ipynb`, `.sql`, `.scala`, and other notebook formats; see the linked import guide for the current list.

## Requirements before a workspace run

- An existing Databricks workspace with Unity Catalog enabled.
- A development catalog and permission to create or use a schema and managed table.
- Unity Catalog-compatible compute, such as serverless notebook compute or a standard/single-user cluster supported by the workspace configuration.

The notebooks rely on the Databricks Runtime's Spark and Delta integration. Do not install local `delta-spark` or PySpark versions into a Databricks Runtime to run this example.

## Import and run manually

1. In the Databricks sidebar, open **Workspace** and select or create a project folder.
2. Use the folder menu's **Import** action and select `notebooks/databricks/01_workspace_preflight.py`. Repeat for `02_delta_merge_demo.py`. The source marker and cell separators let Databricks recognize each Python source file as a notebook.
3. Open `01_workspace_preflight`, attach Unity Catalog-compatible compute, and choose **Run all**. Confirm that Spark starts and the current catalog/schema queries work.
4. Open `02_delta_merge_demo`. In the `catalog` and `schema` widgets, choose a development namespace you are authorized to use. The default catalog is `main`; the notebook creates the `retailpulse_demo` schema if permitted.
5. Attach the same compatible compute and choose **Run all**. The first run creates a two-row Delta table and merges three source records. Later runs reuse the table and should be idempotent: they should not insert or update those same values again.
6. Inspect the displayed table history and current rows. The notebook reads the pre-merge version using Delta time travel and asserts the expected values.

If schema creation is not permitted, ask the workspace administrator for a development schema or use an existing authorized schema in the `schema` widget. Do not use production catalogs for this learning exercise.

## Optional one-time Job

After the notebook succeeds interactively, you can create a one-task Job from the workspace UI:

1. Open **Jobs & Pipelines** (some workspace layouts label this **Workflows** or **Jobs**) and choose **Create job**.
2. Add a **Notebook** task that points to the imported `02_delta_merge_demo` notebook.
3. Select compatible job compute. Set the notebook task parameters `catalog` and `schema` to the same development namespace used for the interactive run.
4. Run the Job once and inspect its run output and notebook assertions.

Leave the schedule unset for the initial example. This repository contains instructions only; no Job or schedule has been created.

## Catalog and secret guidance

Use a development namespace, not a production catalog. Unity Catalog governs access to catalog objects and can record lineage and audit activity. Grant only the privileges needed by the notebook or Job identity.

The sample data is inline and synthetic, so the notebooks do not create or retrieve credentials. If a later pipeline reads a protected source, store its credential in an approved secret manager and retrieve it at runtime (for example, through the workspace-supported secret interface). Never print the returned value or commit it to Git. Secret scopes and Unity Catalog secrets have different governance models; follow the workspace administrator's policy.

## Verification and deployment status

The notebooks were checked as source files and their Python syntax was validated locally. They have **not** been run in a Databricks workspace. There is no workspace URL, compute resource, Job, catalog, or secret configured by this project. The local Phase 9 run used delta-rs; this notebook uses Databricks Runtime's Spark/Delta integration and has not been executed, so do not describe Databricks integration as verified.

If you want to create or use a workspace, compute, or scheduled Job, review the workspace and pricing first. This phase does not start billable cloud resources.
