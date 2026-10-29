# Phase 5 — SQL transformations walkthrough

## Run the local SQL pipeline

From the repository root:

```powershell
.\.venv\Scripts\python.exe run_sql.py
```

The runner uses Python's built-in `sqlite3` module. It loads all eight CSVs into `stg_*` tables, runs the SQL files under `sql/transformations` and `sql/analytics`, then builds the Phase 6 model in `sql/model`. It writes `data/processed/retailpulse.db` plus `data/processed/sql_run_summary.json`. Rerunning rebuilds the project's staging, clean, analytics, dimension, and fact tables. Raw CSVs are not modified.

The SQLite database uses `TEXT` in staging to preserve the CSV source representation. Clean tables cast dates, quantities, and prices into SQLite date/numeric values. The SQL scripts are also readable independently: staging DDL is in `sql/staging/01_create_staging.sql`, cleaning is in `sql/transformations/01_clean_tables.sql`, business outputs are in `sql/analytics/01_business_summaries.sql`, and query examples are in `sql/analytics/02_sql_concepts_examples.sql`.

## Beginner view

- **Staging** is a faithful landing area. It keeps the received text values so later SQL can compare against what arrived.
- **Clean tables** keep rows that meet documented SQL rules, normalize text, cast types, and remove duplicate keys. Invalid rows remain in staging for inspection.
- **Analytics tables** summarize trusted clean data for business questions such as monthly revenue, customer value, product returns, store performance, and stock value.

## SQL concepts demonstrated

| Concept | Plain-language meaning | Where it appears |
|---|---|---|
| `SELECT`, `WHERE`, `ORDER BY` | Choose columns, filter rows, and choose display order | All scripts and the query examples |
| `CAST` and date functions | Convert source text to a usable number/date; extract a month | Clean transformations use `CAST`/`DATE`; analytics use `STRFTIME` |
| `JOIN` | Keep rows that have a matching record on both sides | Orders to customers/stores; items to products/orders |
| `LEFT JOIN` | Keep every row from the left table even when there is no match | Customer/product/store summaries preserve entities with no sales |
| `GROUP BY` and aggregates | Combine detail rows into a summary per category/date/entity | Revenue, inventory, customer, product, store, and return summaries |
| `HAVING` | Filter groups after aggregation | `analytics_low_sales_products` keeps products with at most 10 sold units |
| `CASE` | Apply if/then logic inside a query | Category standardization and revenue growth calculation |
| CTE (`WITH`) | Name intermediate query steps to make a complex query easier to read | Every clean-table query and multi-step analytics |
| Window functions | Compare or rank rows without collapsing them into one group | `ROW_NUMBER` deduplicates; `RANK` orders customers; `LAG` compares monthly revenue |
| Deduplication | Choose one source record per business key using a stable rule | Customer/product/order/payment IDs and inventory natural grain |

## Business rules in this SQL layer

- Customer and product duplicates are reduced to one row using a deterministic `ROW_NUMBER` ordering.
- Product category spelling/case variants are standardized to canonical category labels.
- Orders are retained only when customer and store references resolve, dates are valid and not after the synthetic `as_of_date`, and totals are nonnegative.
- Order lines require valid product/order relationships, positive quantity, nonnegative price and discount, and a line total within one cent of `quantity × unit_price − discount`.
- Returns are retained when they resolve to a clean order line, do not exceed the purchased quantity, have a valid reference-date-bounded date, and their refund matches the returned share of line total within one cent.
- The sales summaries use completed orders. Gross sales sum line totals. Monthly net revenue subtracts refunds recorded in the same return month and category. This is a period reporting convention, not order-cohort accounting.
- Customer activity means a completed order in the 365 days ending on `as_of_date`. Customer revenue is observed synthetic history, not a forecast.
- Product return rate is returned units divided by sold units. Inventory value is based on the latest valid snapshot for each product/store and uses unit cost.
- `analytics_low_sales_products` defines low sales as units sold below the average across the cleaned product catalog; this relative threshold produces a useful list for the current synthetic sample.

## Actual local run

SQLite version **3.50.4** loaded the 96,520 raw rows into staging. The run produced 4,533 clean customers, 461 clean products, 20 clean stores, 15,886 clean orders, 27,859 clean order lines, 14,639 clean payments, 8,513 clean inventory rows, and 619 clean returns. The seven business summary tables contain 576 monthly sales rows, 4,533 customer rows, 461 product rows, 20 store rows, 120 inventory rows, 605 return-summary rows, and 255 below-average-sales products. These counts describe the current synthetic sample and are not performance claims.

## Professional notes and limits

SQLite is useful for a portable local project because it requires no database service. Its numeric storage is not a production financial ledger; this project casts money to `REAL` and uses a one-cent tolerance for teaching. A production warehouse should use a fixed-precision decimal type or integer minor units and explicitly manage currencies, taxes, discounts, refunds, and late-arriving updates.

The SQL is written for SQLite. For example, the examples use `LIMIT` and SQLite date functions such as `STRFTIME`; SQL Server would commonly use `TOP` and different date functions. The concepts transfer, while syntax may need translation for T-SQL, Spark SQL, or another warehouse dialect.

The Phase 5 SQL layer and Phase 6 star schema are local SQLite implementations. The formal Bronze/Silver/Gold organization is still Phase 7. SQL does not include row-level quarantine: rejected source rows remain visible in staging and are counted by the Phase 4 quality report.
