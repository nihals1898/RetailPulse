# Phase 8 — PySpark and Parquet

Phase 8 moves one representative Gold transformation from SQLite SQL to PySpark. The transformation reads the Phase 7 Silver CSVs, joins order items to completed orders, aggregates product sales and returns, calculates a unit return rate, checks its result against `gold_product_summary` in SQLite, and writes the matching rows to Parquet.

## What Spark is doing

- A **DataFrame** is a distributed table with named columns and a schema.
- Operations such as `select`, `join`, `filter`, `groupBy`, and `agg` describe a transformation plan. Spark is lazy: it generally waits until an action such as `collect` or a write is requested before executing the plan.
- A **Spark session** is the entry point for reading data and building DataFrames. This project uses `local[*]`, which runs Spark on the current machine using available local worker threads.
- **Parquet** is a columnar file format that stores a schema and supports efficient analytical reads. It differs from CSV, which stores text values without database types.

This local run demonstrates the API and transformation model. It is not a distributed cluster run or a performance benchmark.

## Install and run

The main project dependencies do not include Spark by default. From the repository root in PowerShell, install the optional Spark dependencies once:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[spark]"
```

Then refresh the Phase 7 Silver and SQLite Gold inputs, followed by the Spark job:

```powershell
.\.venv\Scripts\python.exe run_sql.py
.\.venv\Scripts\python.exe run_spark.py
```

The runner uses `JAVA_HOME` if it is set and adds its `bin` directory to the child process path. On this machine, `JAVA_HOME` points to JDK 24. Spark 4.2.1 started and ran the pipeline successfully with that JDK; however, Apache's [Spark 4.2.1 overview](https://spark.apache.org/docs/4.2.1/) lists Java 17, 21, and 25 as supported runtime versions, so JDK 24 is outside the published list. For a reproducible supported setup, install one of those listed Java versions and set `JAVA_HOME` to it. The [PySpark installation guide](https://spark.apache.org/docs/4.2.1/api/python/getting_started/install.html) lists Python 3.10 and above; the project uses Python 3.13.

The local Windows launch emits warnings about Hadoop `winutils.exe` and native libraries. Spark can still read the Silver CSVs and execute the DataFrame transformations. The Hadoop Parquet writer cannot create output directories without `winutils.exe`, so this pipeline uses PyArrow to serialize the already-computed and compared Spark result as a standard Parquet file. It avoids a machine-wide Hadoop setup.

If the Codex-managed PowerShell sandbox reports an access error for its default temp location, set a project-local temporary directory for that command:

```powershell
New-Item -ItemType Directory -Force .\work\spark-temp | Out-Null
$env:TEMP = (Resolve-Path .\work\spark-temp).Path
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe run_spark.py
```

## Transformation and output

Spark reads `products.csv`, `orders.csv`, `order_items.csv`, and `returns.csv` from `data/processed/silver`. It filters orders to `completed`, sums units and line revenue per product, counts distinct completed orders, then joins those measures back to the product catalog. Return quantities and refunds are aggregated by product and joined to sales. Products with no sales or returns are retained and their missing measures become zero. Return rate is returned units divided by sold units, rounded to four decimal places; products with zero units sold receive rate zero.

The monetary values use Spark decimal types. The comparison requires row counts, product attributes, and integer counts to match exactly; revenue/refund amounts may differ by at most EUR 0.01. Return rates are rounded to four decimals, so the comparison allows one last-place unit (0.0001) for SQLite and Spark midpoint-rounding differences.

Output files:

- `data/processed/spark/product_summary.parquet` — one row per product, with a Parquet schema.
- `data/processed/spark/spark_run_summary.json` — Spark version, local master, source and output paths, output size, duration, Java home, and comparison result.

The Spark runner expects the Phase 7 outputs and `retailpulse.db` to exist; run `run_sql.py` first if they are missing or stale.

## Verified local result

The Phase 8 run used PySpark 4.2.1 with `local[*]`. It compared **461 products** to SQLite Gold with **zero mismatches** and wrote an 11-column Parquet file (23,407 bytes). The saved run summary records **12.487 seconds** on this machine; this is a single local observation, not a benchmark or scale claim. The machine's quality checks still report the intentional source defects documented in [`data_quality.md`](data_quality.md).

## Learning note

Use PySpark when data volume or a Spark-based execution platform calls for distributed processing. Keep small local jobs simple: SQLite and Pandas may be easier to develop and operate at this sample size. The useful portability step is validating that a business transformation has equivalent results across implementations before moving it to a Spark environment.
