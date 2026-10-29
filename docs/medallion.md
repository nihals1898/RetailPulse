# Bronze, Silver, and Gold

Phase 7 adds a local medallion-style layout to the existing RetailPulse SQL pipeline. It is an educational SQLite and CSV implementation; it does not use Spark, Parquet, Delta Lake, cloud storage, or a deployed orchestrator.

## Data flow

```text
data/raw/*.csv
    │ Phase 3 contract and structural checks
    ├── ingestion report + malformed-file/row quarantine
    │
    ├── Bronze: original CSV field values + ingestion metadata
    │
    ├── Phase 4 quality validation: rule results + bounded violation examples
    │
    └── SQLite staging → SQL clean tables → analytics summaries + star schema
                                │                         │
                                └── Silver CSVs           └── Gold CSVs
```

`run_sql.py` performs these steps in order: ingestion, quality validation, Bronze and staging loads, SQL cleaning, analytics summaries, star-schema construction, Silver/Gold table creation, and CSV exports. Ingestion contract failures stop the pipeline. The quality validator observes defects and does not repair source rows; the generated source is intentionally dirty, so its quality status can be `failed` while the pipeline still completes. The SQLite model checks foreign keys before exports.

## Layer contents

### Bronze

Each `bronze_*` SQLite table and corresponding CSV retains all accepted source rows and the original CSV field values as text. Six metadata fields are added: `source_file`, `source_system`, `ingestion_timestamp`, `ingestion_run_id`, `source_row_number`, and `source_file_size_bytes`. This makes each source row traceable to its file and ingestion run. Files that fail the ingestion contract are handled by the Phase 3 quarantine process rather than loaded into Bronze.

### Silver

The `silver_*` tables select from the Phase 5 `clean_*` tables. Those SQL transformations cast types, normalize values, apply business rules, and deduplicate records. Thus Silver contains the rows retained by the clean layer, not a verbatim copy of Bronze. The validation report and bounded detailed examples are copied beside the layer exports as `quality_rule_results.csv` and `quality_violation_examples.csv`; inspect them to understand rejected or flagged source data.

### Gold

The `gold_*` tables and CSVs are derived from the Phase 5 analytics summaries. They provide report-ready summaries by month, customer, product, store, inventory, and return, plus a list of low-sales products. The shared dimensional facts and dimensions remain available in SQLite, documented in [`data_model.md`](data_model.md); Phase 7 does not duplicate them as Gold CSVs.

## Output locations

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe run_sql.py
```

The pipeline creates the following directories and writes `sql_run_summary.json` and `retailpulse.db` under `data/processed`:

| Layer | Output directory | CSVs |
|---|---|---|
| Bronze | `data/processed/bronze` | `customers`, `products`, `stores`, `orders`, `order_items`, `payments`, `inventory`, `returns` |
| Silver | `data/processed/silver` | The same eight datasets, plus quality rule results and violation examples |
| Gold | `data/processed/gold` | `sales_monthly`, `customer_summary`, `product_summary`, `store_summary`, `inventory_summary`, `returns_summary`, `low_sales_products` |

All CSV files use UTF-8 encoding and include a header row. SQLite remains the typed queryable copy; CSV serialization does not preserve database column types.

## Verified default sample

The completed local run recorded these layer row counts in `data/processed/sql_run_summary.json`:

| Layer | Rows by output |
|---|---|
| Bronze | customers 5,000; products 500; stores 20; orders 20,000; order items 40,000; payments 20,000; inventory 10,000; returns 1,000 |
| Silver | customers 4,533; products 461; stores 20; orders 15,886; order items 27,859; payments 14,639; inventory 8,513; returns 619 |
| Gold | monthly sales 576; customer summary 4,533; product summary 461; store summary 20; inventory summary 120; returns summary 605; low-sales products 255 |

The run built 4 dimensions and 3 facts with zero foreign-key violations. The Phase 4 quality status was `failed` for this dataset by design: the generator inserts duplicate, missing, invalid, and inconsistent values to support the project's cleaning and validation exercises. Treat that status as a report on source quality, separate from whether ingestion and SQL transformations ran successfully.

## What is deferred

This phase establishes layer boundaries and traceability locally. Parquet, Delta Lake transaction handling, incremental loads, schema evolution, partitioning, cloud storage permissions, orchestration retries, and production-grade quarantine/replay are later design or implementation work.
