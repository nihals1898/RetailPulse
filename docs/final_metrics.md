# Phase 19 — Final project metrics

This page consolidates observed results from the local run summaries, benchmark
report, and most recently recorded test result. Measurements describe this
synthetic sample and local Windows environment; they are not production or
cross-machine performance claims.

## Data and quality

| Metric | Recorded result | Evidence/meaning |
| --- | ---: | --- |
| Source CSVs | 8 files; 6,990,977 bytes | Phase 16 benchmark input profile |
| Input rows | 96,520 | Sum of the eight configured source row counts |
| Generator | Seed 42; `as_of_date=2025-12-31`; 2% configured defect rate | `data/raw/generation_summary.json` |
| Quality rules | 106 evaluated; 66 passed; 40 failed | Latest `quality_summary.json` |
| Failed rows across rules | 16,553 | Rule-level counts summed together; not a distinct-record count |
| Violation details written | 14,821 | Capped examples, at most 1,000 per rule |
| SQL foreign-key violations | 0 | Latest SQL run summary |

The quality run reports `quality_status=failed` because the sample deliberately
contains duplicate, missing, invalid, and inconsistent values. The SQL pipeline
itself completed with `run_status=success`.

## Local SQL outputs

The latest recorded pipeline run completed on 2026-10-29 in **6.093 seconds**.
It loaded 96,520 staging rows and produced:

| Output | Rows |
| --- | ---: |
| Bronze exports | 96,520 |
| Silver exports | 72,530 |
| Gold summary exports | 6,570 |
| Power BI model exports (4 dimensions + 3 facts) | 43,466 |

The Power BI model contains 4,533 customers, 461 products, 20 stores, 1,461
exported dates, 27,859 sales lines, 619 return events, and 8,513 inventory
snapshots. The unknown-date row is omitted from the Power BI date export; the
SQLite date dimension contains 1,462 rows including that row.

The regular pipeline runtime and the benchmark runtime below are separate
observations. The pipeline run wrote to the project's processed directory;
the benchmark used fresh isolated output directories.

## Performance baseline

Three isolated end-to-end SQL benchmark runs produced these measured durations:

| Run 1 | Run 2 | Run 3 | Median |
| ---: | ---: | ---: | ---: |
| 4.056 s | 4.014 s | 4.050 s | 4.050 s |

Each run produced a 44,019,712-byte SQLite database and 74,188,635 bytes of
processed output. Environment: Windows 11, CPython 3.13.15, SQLite 3.50.4, AMD64
Family 25 Model 116 processor, and 16 logical CPUs. Later runs may benefit from
the operating system's file cache. See the complete
The complete local report is at
`work/performance/20261029T110218Z/benchmark_report.json` (ignored by Git); see
the [benchmark notes](performance.md).

## Tests and optional engines

| Measurement | Recorded result | Limit |
| --- | --- | --- |
| Local pytest suite | 13 passed in 1.19 s | Most recently recorded local run; not a hosted CI result |
| PySpark product-summary comparison | 461 products compared; 0 mismatches; 23,407-byte Parquet output; 12.487 s | One local `local[*]` run using PySpark 4.2.1, not a cluster benchmark |
| Delta merge demonstration | 3 source rows; 1 insert, 1 update, 0 deletes; 14 ms merge execution | Tiny local delta-rs sample; not a scale/performance result |

Azure Pipelines has not been connected or run. Databricks and Azure components
remain design-only. The user built the Power BI report locally; its PBIX is
excluded from Git because its source paths contain the Windows account name.

## Evidence locations

- Latest SQL result: `data/processed/sql_run_summary.json`
- Latest quality result: `data/processed/quality/quality_summary.json`
- Latest ingestion result: `data/processed/ingestion/run_summary.json`
- Benchmark result: `work/performance/20261029T110218Z/benchmark_report.json`
- Spark result: `data/processed/spark/spark_run_summary.json`
- Delta result: `data/processed/delta/delta_run_summary.json`
- Test command and coverage: [testing guide](testing.md)
