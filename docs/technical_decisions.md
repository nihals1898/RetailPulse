# Technical decisions

Initial choices and tradeoffs are recorded in [Phase 0 requirements](phase-0-requirements.md). Decisions will be updated when implementation evidence is available.

## Phase 2 — synthetic data generation

- Use the Python standard library `csv` writer so CSV generation does not require an additional third-party package.
- Stream the large fact tables (`order_items`, `orders`, `payments`, and `inventory`) rather than holding every fact row in memory. Compact numeric arrays retain only order totals, dates, and line counts needed to build related files.
- Use an explicit seed (`42` by default) and a fixed synthetic `as_of_date` (`2025-12-31` by default) instead of the wall clock. This makes repeat runs comparable; intentionally future-dated records are future relative to that reference date.
- Inject defects into source CSVs on purpose. Phase 2 preserves those bad source values; cleaning and quarantine belong to later phases.
- Keep the starter profile modest. Configurable target-scale counts are supported but have not been generated or benchmarked in this phase.

## Phase 3 — raw ingestion

- Treat generated source CSVs as read-only. Ingestion records evidence and quarantine copies while leaving the raw inputs available for replay and inspection.
- Validate exact expected filenames and the required header column set. Header order is allowed to differ because the file contract is name-based; missing, extra, duplicate, or blank headers fail the file.
- Quarantine whole files when their contract cannot be trusted; quarantine structurally malformed rows separately when the header is valid. Business-value defects remain visible in raw data and are deferred to Phase 4 checks.
- Keep run summaries and logs local and ignored by Git because they contain machine-specific timestamps and paths.

## Phase 4 — data quality

- Evaluate source CSVs directly and preserve original values. Quality reporting observes defects; it does not repair them or silently discard rows.
- Use decimal arithmetic for monetary rules and a one-cent tolerance to handle the source's two-decimal storage convention.
- Resolve future-date checks against the fixed synthetic reference date from the generation summary, not the runtime clock.
- Store full failed-row counts in the rule report and cap detailed examples per rule so large inputs do not require retaining every failure in memory.
- Stream record checks and retain only key sets, order/item aggregates, and return-line references needed for cross-dataset validation.

## Phase 5 — SQL and SQLite

- Use Python's built-in SQLite engine for a zero-service local SQL environment. The actual local runtime reports SQLite 3.50.4.
- Load staging columns as text to preserve CSV source values, then cast and standardize in separate clean tables.
- Keep transformations in version-controlled `.sql` files; a small Python runner handles CSV loading and execution.
- Use CTEs and window functions to make deduplication and multi-step summaries inspectable. Demonstrate joins, aggregates, `HAVING`, `CASE`, windows, and date functions in SQL examples.
- SQLite `REAL` is used for this learning sample's money fields with a one-cent comparison tolerance. A production financial model should use fixed-precision decimal or integer minor units.

## Phase 6 — star schema

- Build the three facts at distinct, documented grains and share four conformed dimensions. Keep source/business IDs on dimensions and source transaction IDs on facts for traceability.
- Assign deterministic integer surrogate keys by sorted business key during this full-refresh local build. Incremental production loads would persist key assignments and add slowly changing dimension handling.
- Use a shared date dimension with separate order, return, and inventory date roles; reserve date key `0` for unknown dates.
- Enforce dimension foreign keys in SQLite and verify them with `PRAGMA foreign_key_check` after building the model.
- Keep the returns fact connected to dimensions, not directly related to the sales fact in the BI model. Retain order/item IDs for drill-through.
- Treat inventory as semi-additive over time; select a snapshot date before summing stock value.

## Phase 7 — local medallion layers

- Keep SQLite as the transformation engine and export the layers as CSV for easy inspection in this local learning project. Parquet and Delta are deferred until their runtime and use are introduced.
- Store Bronze source fields as text to preserve their original CSV representation. Add file, source-system, run, timestamp, file-size, and row-number metadata during the same read that loads staging.
- Derive Silver from the existing typed and cleaned SQL tables, avoiding a second competing cleaning implementation. Preserve quality rule results and the validator's bounded violation examples next to the Silver exports.
- Derive Gold exports from the documented analytics summaries. Keep the star schema in SQLite as the dimensional model; the initial Gold CSVs are domain summaries rather than duplicate fact and dimension exports.
- Accept a failed quality status for this intentionally defective synthetic sample while requiring successful ingestion and zero star-schema foreign-key violations for a completed pipeline run.

## Phase 8 — PySpark and Parquet

- Keep PySpark in an optional `spark` dependency group because the PySpark package bundles a large Spark distribution and requires a usable Java runtime. The regular project install remains lightweight.
- Migrate the product performance Gold summary first. It demonstrates joins, grouped aggregates, null handling, and a derived return rate while allowing a direct result comparison with the existing SQLite Gold table.
- Compare counts exactly, currency within EUR 0.01, and the four-decimal return rate within one last-place unit (0.0001) to allow SQLite/Spark midpoint-rounding differences. Use decimal arithmetic for monetary aggregation in Spark.
- Run Spark in `local[*]` mode. Do not treat a local run as cluster or scalability evidence.
- On this Windows environment Spark's own Hadoop Parquet writer needs `winutils.exe`. Keep Spark responsible for computation, compare its output first, then serialize the collected result with PyArrow to produce a standard Parquet artifact without a machine-wide Hadoop setup.
- JDK 24 successfully launched this Spark 4.2.1 run, but Apache's published tested runtime list is Java 17, 21, and 25. Record the observed result and the compatibility caveat rather than claiming JDK 24 is supported.

## Phase 9 — Delta Lake

- Keep Phase 8's PySpark 4.2.1 installation intact. The currently published Delta connector matrix does not list Spark 4.2; the Delta Lake 4.3 line lists Spark 4.0 and 4.1 compatibility.
- Use the native Delta Lake Python/Rust implementation for the local format, transaction-log, conditional-merge, and time-travel demonstration. Do not present this as a Spark Delta connector run.
- Build the example from two cleaned Silver products and merge one unchanged row, one changed row, and one new synthetic demonstration product. Verify insert/update metrics and the pre-merge table version.
- The normal PowerShell run verified the native Delta table and merge: version 0 held two rows; version 1 held three rows after one insert and one update. The unchanged row and pre-merge time-travel result both matched expectations.

## Phase 10 — Databricks

- Keep Databricks assets as importable source-format Python notebooks with the official `# Databricks notebook source` marker and command-cell separators. This format can be reviewed and versioned locally without a workspace.
- Demonstrate a managed Delta table under a Unity Catalog catalog/schema, but require the user to supply an existing workspace and authorized development namespace when they choose to run it.
- Use a Databricks Runtime-provided Spark/Delta integration rather than installing a `delta-spark` version into the local Spark 4.2.1 environment.
- Document workspace, compute, Jobs, Unity Catalog, and secrets. No account, compute, Job, catalog, or secret is created in this phase; cloud deployment remains behind the project's cost and approval gate.

## Phase 11 — Azure target architecture

- Use ADLS Gen2 with hierarchical namespace as the target lake because the architecture needs directory semantics and Unity Catalog external-location support.
- Start with a Databricks Lakeflow Job for Spark/Delta orchestration. Add Azure Data Factory only when external ingestion or cross-service control flow warrants its separate runtime, identity, and cost.
- Use a Databricks Access Connector managed identity with Unity Catalog storage credentials/external locations for external ADLS paths. Use Key Vault for external-system secrets; avoid storage keys or long-lived credentials in notebooks.
- Route selected service diagnostics and pipeline signals to Azure Monitor/Log Analytics. Set retention deliberately and alert on failures, freshness, quality outcomes, and budget thresholds.
- Treat Azure as design-only. Require a region-specific estimate, identity/network review, cost budget, teardown plan, and explicit user approval before creating chargeable resources.

## Phase 12 — DevOps

- Keep the Git workflow local-first: review staged changes, exclude secrets and generated data, use focused feature branches and pull requests after the initial baseline commit. Do not invent or configure a remote repository on the user's behalf.
- Add a two-stage Azure Pipelines YAML definition: a base-package validation/CLI/Ruff stage followed by a wheel build and pipeline artifact publication. Use Python 3.13, within the package's declared `>=3.11,<3.14` support range.
- Keep Spark and Delta dependencies out of the base CI job. At Phase 12, pytest was deferred until tests existed; Phase 13 added coverage and wired pytest into the Validate stage.
- Treat the YAML as locally reviewed configuration only. No Azure DevOps organization, pipeline, remote, hosted agent, or artifact has been connected or run.

## Phase 13 — automated testing

- Use deterministic, small synthetic fixtures in temporary directories so tests do not depend on the user's generated data or change project outputs.
- Cover generator repeatability and config boundaries, ingestion success/schema/quarantine behavior, clean and intentionally invalid quality outcomes, and a small SQLite/medallion integration run with business-summary reconciliation and foreign-key checks.
- Run pytest locally and report the exact pass/fail count. Keep intentionally dirty cases separate from the clean fixture so expected data-quality failures are assertions rather than suite failures.
- Add pytest to the Azure Pipelines Validate stage. Preserve lint enforcement for the selected Ruff checks while documenting existing E501, I001, UP017, and UP035 source findings that the pipeline excludes.

## Phase 14 — Power BI

- Export the local star-schema dimensions and facts to a dedicated `data/processed/powerbi_model/` CSV interface. Keep the existing Gold summary CSVs as a separate, pre-aggregated interface; do not mix summary grains with the fact model in one semantic model.
- Exclude the unreferenced unknown-date key 0 from the Power BI date export so its `date_value` is nonblank and can be marked as a date table. Keep all fact foreign keys and verify current facts do not reference key 0.
- Use dimensions filtering facts with single-direction one-to-many relationships and no fact-to-fact relationships. Use return date as the active date role for returns and an explicit DAX measure for original-order-date cohorts.
- Provide DAX and report-building guidance. The user built report pages and saved `dashboards/powerbi/RetailPulse.pbix`; do not claim the file contents were independently inspected or that the model was published.

## Phase 15 — Monitoring

- Record local SQL pipeline runs in an append-only CSV beside processed data. Include run status/timing, source-file freshness, ingestion and quality totals, foreign-key violations, and layer/Power BI export totals.
- Keep execution status separate from data-quality status: a run may finish successfully while rules flag deliberately dirty sample data.
- Measure freshness from the newest input CSV's filesystem modification time at run start. This is an operational file-freshness signal, not a business-date completeness metric.
- Keep alerts, retention automation, and Azure Monitor integration out of scope; Azure services remain design-only.

## Phase 16 — Performance

- Benchmark the existing end-to-end SQL pipeline against the local source CSVs, using a fresh isolated database and output directory per iteration so existing processed and Power BI files remain untouched.
- Report each wall-clock timing plus median/range, input bytes/files, output row counts and sizes, and Python/SQLite/host environment details. Preserve individual timings because later iterations may benefit from the operating-system file cache.
- Treat results as a reproducible baseline for comparable local environments, not a cross-machine guarantee or evidence of optimization.

## Phase 17 — Documentation

- Keep the README oriented around setup, implemented local flow, measured evidence, and an index to focused guides. Detailed contracts and walkthroughs stay in their existing topic documents.
- Label user-reported Power BI Desktop work separately from artifacts that are available in the repository; do not claim to have inspected a `.pbix` that is not present.
- Keep cloud and hosted CI status explicit as design-only/unrun, and update summary claims when later phases produce evidence.

## Phase 18 — GitHub portfolio

- Perform a local publication-readiness review first. The owner then created the GitHub destination, reviewed the staged file list, committed the baseline, and pushed it to the provided remote.
- Preserve generated data, environments, logs, and work outputs as ignored local artifacts. Treat the saved PBIX as a candidate portfolio artifact that the owner should review for personal metadata and source paths before publishing.
- Report credential scans as limited pattern checks, not proof that every possible secret is absent.

## Phase 19 — Final metrics

- Derive metrics only from the latest local run summaries, the saved benchmark report, and the recorded local test result. Keep one-off pipeline/Spark/Delta timings separate from repeated benchmark results.
- Explain that quality failures are rule-level counts over intentionally defective synthetic inputs; do not present their sum as distinct bad records.
- State the test and cloud/hosted-CI evidence boundaries. Do not turn local observations into production-scale or cross-machine claims.
