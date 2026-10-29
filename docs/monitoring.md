# Phase 15 — Local pipeline monitoring

The SQL pipeline appends one record for every completed run to:

```text
data/processed/monitoring/pipeline_runs.csv
```

The latest run's detailed JSON summary is written to `data/processed/sql_run_summary.json`.

## Run and inspect

From the RetailPulse repository root in PowerShell, run:

```powershell
.\.venv\Scripts\python.exe run_sql.py
```

Inspect the run history with:

```powershell
Import-Csv .\data\processed\monitoring\pipeline_runs.csv |
  Select-Object pipeline_run_id, run_status, duration_seconds, source_files_seen,
    latest_source_file, source_freshness_age_seconds, quality_status,
    quality_rules_failed, foreign_key_violations |
  Format-Table -AutoSize
```

The CSV is append-only. Each run includes timestamps, duration, source directory,
number of CSV inputs, latest source file and its modification time, source
freshness at pipeline start, ingestion totals, data-quality rule totals,
foreign-key violations, Bronze/Silver/Gold export totals, Power BI model export
totals, and—when the pipeline raises an error—the exception type and message.

`source_freshness_age_seconds` is the age of the newest source CSV's filesystem
modification time when the run starts. It measures file freshness, not the
business-date coverage of the records.

## Interpret status

- `run_status=success` means the local pipeline completed.
- `run_status=failed` means it raised an error; inspect `error_type` and
  `error_message`.
- `quality_status` reports data-quality rules independently of execution
  status. The intentionally corrupted sample can complete successfully while
  reporting `quality_status=failed`. That is a recorded quality outcome, not a
  pipeline crash.

This phase adds local evidence only. It does not send alerts, delete old records,
or connect to Azure Monitor. Cloud monitoring remains design-only.
