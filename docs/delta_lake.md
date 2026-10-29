# Phase 9 — Delta Lake and incremental merge

Phase 9 demonstrates a local Delta table, a conditional merge, a table version, and a time-travel read. The runner is `run_delta.py` and its output is isolated under `data/processed/delta/product_catalog_merge_demo`.

## Delta Lake concepts

Delta Lake stores Parquet data files together with a transaction log in `_delta_log`. The log records committed table changes and lets readers select earlier table versions. A `MERGE` operation compares a source batch with target rows using a business key; matched rows can be conditionally updated, and unmatched rows can be inserted. In this example, an unchanged matched product is deliberately left untouched.

## Local engine choice

The installed project uses PySpark 4.2.1. Delta Lake's published connector matrix currently lists Delta 4.3.x as compatible with Spark 4.0.x and 4.1.x, but does not list Spark 4.2.x. [See the Delta Lake compatibility table](https://docs.delta.io/releases/).

For this local Windows exercise, the optional `delta` dependency uses Delta Lake's native Python/Rust library (`deltalake`, also called delta-rs) instead of the Spark connector. It writes the Delta transaction log and Parquet data directly, supports conditional merge and version reads, and leaves the Phase 8 PySpark environment unchanged. This demonstrates the Delta table format and merge behavior; it does **not** claim that the Spark 4.2 connector or Spark-to-Delta integration was tested. The delta-rs Python package is documented at [delta-rs installation](https://delta-io.github.io/delta-rs/python/installation.html) and its [merge guide](https://delta-io.github.io/delta-rs/1.5.1/usage/merging-tables/).

## Setup and run

The optional dependency group adds `deltalake` and uses the project's PyArrow dependency. Install it from the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[delta]"
```

Refresh Phase 7 Silver input, then create and merge the demonstration table:

```powershell
.\.venv\Scripts\python.exe run_sql.py
.\.venv\Scripts\python.exe run_delta.py
```

The runner rebuilds the two-row starting snapshot from the first two cleaned Silver products, then merges three source rows: one unchanged product, one changed product, and one new demonstration product. It verifies the initial and merged snapshots, checks that the changed record was updated, that the new record was inserted, and that the unchanged record retained its value. It also reads the pre-merge Delta version and records the operation history.

Outputs:

- `data/processed/delta/product_catalog_merge_demo/` — Delta table directory with `_delta_log` and Parquet data files.
- `data/processed/delta/delta_run_summary.json` — Delta version, merge metrics, current and historical row counts, and verification results.

The operation is repeatable: the seed snapshot is overwritten from the same two source products, then the merge is applied again. The Delta version history remains local to the ignored `data/processed` output.

## Verified local result

The Delta runner was executed successfully in normal PowerShell using `deltalake` 1.6.6. Version 0 contained two products. The merge read three source rows and committed version 1 with **one insert, one update, zero deletes, and one unchanged matched row**. The post-merge table held three rows. All checks passed: the changed price was applied, the unchanged row was preserved, the new product was inserted, and version 0 still returned the pre-merge price.

The machine-readable evidence is in `data/processed/delta/delta_run_summary.json`; the transaction log records both the initial `WRITE` and subsequent `MERGE`. The verified table is `product_catalog_merge_demo`. A separate `product_catalog_demo` directory may remain from an earlier sandbox attempt; it is incomplete and is not the verified table.

The compatible `delta-spark` connector path remains a later setup option requiring a supported Spark/Delta pair. No cloud service, Databricks workspace, or remote table is used in this phase.
