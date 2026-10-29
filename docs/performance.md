# Phase 16 — Performance baseline

Run the repeatable local SQL benchmark from the repository root:

```powershell
.\.venv\Scripts\python.exe benchmark_sql.py --runs 3
```

The benchmark reads the existing `data/raw` CSVs without modifying them. Each
iteration writes to a new isolated SQLite database and output folder under
`work/performance/<timestamp>/`. The JSON report records the input size and
files, wall-clock pipeline duration for each run, median/minimum/maximum
duration, row totals, database/output sizes, Python/SQLite versions, and host
platform details. Temporary benchmark outputs are ignored by Git.

To use a different input directory or number of runs:

```powershell
.\.venv\Scripts\python.exe benchmark_sql.py --input-dir data/raw --runs 5
```

## Reading the results

- Compare timings only when input files, code revision, and environment are
  comparable. Keep the run count and input byte/row counts with the timing.
- The first run and later runs may differ because the operating system caches
  file reads. The report preserves each duration and summarizes the median.
- `run_status` reports execution success. `quality_status` is independent and
  can be `failed` for the project's intentionally dirty sample inputs.
- These are local measurements, not a promise for other computers or a cloud
  service. The benchmark is a baseline for later optimization work, not an
  optimization by itself.

## Recorded baseline

Measured locally on 2026-10-29 with Python 3.13.15, SQLite 3.50.4, Windows 11,
an AMD64 Family 25 Model 116 processor, and 16 logical CPUs:

| Metric | Observed result |
| --- | ---: |
| Source CSVs | 8 files, 6,990,977 bytes |
| Input rows | 96,520 |
| End-to-end SQL duration, three runs | 4.056 s, 4.014 s, 4.050 s |
| Median duration | 4.050 s |
| SQLite database | 44,019,712 bytes |
| Processed output directory per run | 74,188,635 bytes |
| Silver / Gold / Power BI model rows | 72,530 / 6,570 / 43,466 |

All three pipeline executions completed with `run_status=success`; data-quality
status was `failed` because the generated input intentionally contains defects.
The machine-specific JSON evidence is saved at
`work/performance/20261029T110218Z/benchmark_report.json` and is ignored by Git.
