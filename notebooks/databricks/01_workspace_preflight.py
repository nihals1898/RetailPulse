# Databricks notebook source
# ruff: noqa: E501, F821
# MAGIC %md
# MAGIC # RetailPulse — Databricks workspace preflight
# MAGIC
# MAGIC This notebook checks the selected workspace runtime and Unity Catalog context before the Delta merge demo. It does not create compute, catalogs, schemas, volumes, jobs, or secrets.

# COMMAND ----------

import sys

print(f"Spark version: {spark.version}")
print(f"Python version: {sys.version.split()[0]}")
print(f"Current catalog: {spark.sql('SELECT CURRENT_CATALOG()').first()[0]}")
print(f"Current schema: {spark.sql('SELECT CURRENT_SCHEMA()').first()[0]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Unity Catalog setup
# MAGIC
# MAGIC Before running the merge notebook, choose an existing catalog and create or select a schema where you have permission to create a managed table. The second notebook has widgets for both names. Use a development catalog and a dedicated schema for this demo.
# MAGIC
# MAGIC Unity Catalog provides the governed namespace and access-control boundary. A workspace is the collaborative user interface and object container; compute supplies the Spark execution environment. These are separate responsibilities.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Jobs and secrets
# MAGIC
# MAGIC After manually running the merge notebook, create a Lakeflow Job with one notebook task pointing at `02_delta_merge_demo.py`. Run it once on serverless or UC-compliant compute before considering a schedule. No Job is created by this notebook.
# MAGIC
# MAGIC This sample uses inline synthetic records and needs no credentials. For a real external source, store credentials in an approved secret manager and grant the job identity only the access it needs. Never place a secret value in notebook source, widgets, or logs.
