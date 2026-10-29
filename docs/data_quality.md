# Phase 4 — data quality framework

Phase 3 checks file names, headers, and CSV structure. Phase 4 evaluates record values. Run from the repository root:

```powershell
.\.venv\Scripts\python.exe validate_data.py
```

By default, the validator reads `data/raw` and writes:

- `data/processed/quality/quality_report.csv` — one result row per dataset and rule.
- `data/processed/quality/quality_violations.csv` — row keys and failure explanations, capped at 1,000 examples per rule by default.
- `data/processed/quality/quality_summary.json` — run timestamp, reference date, and rule totals.

Use `--as-of-date YYYY-MM-DD` to override the synthetic reference date. Use `--detail-cap-per-rule N` to adjust the detail limit. Add `--fail-on-issues` when a pipeline should exit with status 1 if any rule fails. Without that option, the command completes with exit status 0 after writing the report, even when the report contains failures; this source data intentionally contains defects. The summary distinguishes `run_status` (whether validation/reporting completed) from `quality_status` (whether any rules failed).

## Implemented rules

- **Completeness:** required fields are not empty strings or null.
- **Uniqueness:** source IDs are unique; order lines use `order_id + line_number`; inventory grain uses `product_id + store_id + snapshot_date`.
- **Validity:** ISO date/timestamp parsing; transaction dates do not exceed the configured reference date; prices and amounts are nonnegative; sales and return quantities are positive integers; inventory on-hand is a nonnegative integer.
- **Format/domain:** simple email and phone patterns, canonical product categories, and allowed payment methods.
- **Referential integrity:** order/customer/store; order-item/order/product; payment/order; inventory/product/store; return/order/order-item/product.
- **Business reconciliation:** line total equals quantity × unit price − discount; order total equals summed line totals; inventory value equals on-hand × unit cost; return quantity does not exceed its purchased line quantity; refund amount reconciles to the returned share of line total.

Money calculations use decimal arithmetic with a one-cent tolerance. Date and future checks use the generation summary's `as_of_date` unless overridden. A duplicate rule counts duplicate occurrences after the first occurrence, not every row in a duplicated group. Each rule reports its own failed-row count, so one source row can contribute to multiple rules. The JSON field `failed_row_counts_across_rules` is a sum of rule-level failures, not a distinct-record count. Violation details are a capped sample; `failed_rows` remains the full count.

The validator streams CSV records and retains key sets and aggregates needed for joins rather than loading all fact records into dataframes. It fails fast on missing or structurally malformed input and asks the operator to run Phase 3 ingestion first. This is a local teaching implementation, not a production orchestration service.
