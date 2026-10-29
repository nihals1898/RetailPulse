# Phase 3 — raw CSV ingestion

## Local implementation

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe ingest_data.py
```

The default inputs are the eight expected CSV files in `data/raw`. The command writes:

- `data/processed/ingestion/ingestion_summary.csv` — one row per expected or discovered CSV file.
- `data/processed/ingestion/ingestion_errors.csv` — file-level and malformed-row diagnostics.
- `data/processed/ingestion/run_summary.json` — one run's overall status and timestamp.
- `logs/ingestion.log` — UTC operational log.
- `data/quarantine/ingestion/files/` — copies of unexpected or invalid-schema files with a reason JSON sidecar.
- `data/quarantine/ingestion/rows/` — structurally malformed CSV records, preserving line number and raw cell values.

Input files are read-only from the framework's perspective. A structurally invalid file is copied to quarantine; the source remains available for investigation. Valid files stay in `data/raw`. This phase validates file contracts and CSV structure. It does not fix values or reject rows for missing business fields, invalid dates, negative prices, or broken foreign keys; those checks belong to Phase 4.

The summary includes dataset, source filename, UTC ingestion timestamp, row count, status, error count, file size in bytes, valid row count, quarantined row count, and an error message. `row_count` means data records after the header, including structurally malformed records. Status is `success`, `partial`, `failed`, or `missing`. The CLI exits with status 1 if any expected file is missing, a file contract fails, or a file is only partially readable.

Use custom folders when exploring failures:

```powershell
.\.venv\Scripts\python.exe ingest_data.py --input-dir data/sample/incoming --report-dir data/sample/report --quarantine-dir data/sample/quarantine --log-file data/sample/ingestion.log
```

## Production mapping

In production, a scheduler or storage event would trigger a run. A manifest/run record would capture source URI, checksum, arrival time, schema version, row counts, run ID, and status. Retries would use idempotent run IDs; alerts would distinguish missing or malformed files from record-level quality failures. Quarantine would have access controls, retention rules, and replay procedures. The local implementation demonstrates file contracts and run evidence only; it is not connected to Azure, a scheduler, cloud storage, or alerting.
