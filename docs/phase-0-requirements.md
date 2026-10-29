# RetailPulse — Phase 0 Requirements and Delivery Plan

**Status:** Phase 0 — requirements and design only
**Implementation status:** No repository, cloud resource, pipeline, dataset, or dashboard has been created by this document.

## 1. Purpose and scope

RetailPulse is a fictional omnichannel retailer. This project will build a locally runnable learning platform that takes synthetic operational data through ingestion, validation, transformation, modeling, and business-ready analytics. Later phases will demonstrate selected PySpark and Delta Lake workflows and document how the local design maps to Azure services.

The primary outcome is a reproducible portfolio project with evidence for each implemented capability. Azure, Databricks, Power BI, and other services will be labeled as **implemented** only after they have actually been configured and exercised. Otherwise, they will be labeled **designed / future deployment**.

## 2. Business requirements

The platform must provide a consistent analytical source for sales, customers, products, stores, inventory, and returns. It should help business users answer the 20 questions in the project brief, including revenue and order trends, product and store performance, customer value, stock levels, inventory value, and return rates.

It must make source-data defects visible instead of silently hiding them. Examples include duplicates, missing values, invalid formats and dates, impossible prices or quantities, and broken relationships between entities. Data-quality outcomes and rejected records must be explainable and traceable to their source.

The solution should be understandable to a learner with prior SQL, Python, ETL, and BI exposure but limited hands-on experience with Spark, Azure, Databricks, and Delta Lake. Explanations should distinguish conceptual design from work that has been run locally or deployed.

## 3. Functional requirements

### FR-1 — Synthetic source data

Generate configurable CSV datasets for customers, products, stores, orders, order items, payments, inventory, and returns. Generation must be reproducible with a seed, preserve intended entity relationships for clean records, and support controlled injection of realistic defects. Row counts must be configurable rather than embedded as fixed constants.

### FR-2 — Source contract and ingestion

Discover expected input files, check names and required columns, capture ingestion time and source metadata, record file size and row counts, and report success or failure. Invalid files or records must be made visible in a quarantine or error output with a reason.

### FR-3 — Data quality

Provide reusable checks for completeness, uniqueness, validity, format, referential integrity, and business rules. Each result must report the dataset, rule, inspected rows, failed rows, status, and enough context to investigate failures. Checks must include, at minimum, the project brief’s examples: required IDs, email format, positive quantities, nonnegative prices, date validity, order totals, foreign keys, and return quantity versus purchased quantity.

### FR-4 — Transformations and analytical outputs

Standardize and type source fields, deduplicate according to documented rules, validate relationships, and create analytical outputs for sales, customers, products, stores, inventory, and returns. Transformation rules must be documented and reproducible.

### FR-5 — SQL and analytical model

Demonstrate staging, cleaned, and analytical SQL. Include joins, aggregations, CTEs, conditional logic, deduplication, date handling, and window functions. Build a documented star schema with FactSales, FactReturns, FactInventory, and appropriate customer, product, store, and date dimensions.

### FR-6 — Medallion layers

Define Bronze as source-preserving data plus ingestion metadata; Silver as typed, standardized, quality-assessed data; and Gold as business-ready analytical datasets. Layer boundaries and treatment of invalid records must be clear.

### FR-7 — Distributed and cloud-target learning

Migrate suitable local transformations to PySpark and demonstrate Parquet output. Where supported in the local environment, demonstrate Delta Lake concepts and an incremental merge. Provide Databricks-compatible notebooks and an Azure target architecture without implying that a cloud deployment exists.

### FR-8 — Quality evidence and operations

Record pipeline runs, row counts, rejected records, duplicates, failed checks, duration, status, and freshness where implemented. Produce machine-readable quality and run summaries.

### FR-9 — BI-ready data

Provide Gold outputs and documented KPI definitions for total revenue, orders, customers, average order value, return rate, revenue growth, category/product/store revenue, monthly revenue, and inventory value. Explain the proposed Power BI semantic model and DAX. Do not fabricate screenshots or claim a report exists unless created.

### FR-10 — Documentation and portfolio readiness

Document architecture, data flow, schemas, data-quality rules, model grain and relationships, technical decisions, setup, execution, testing, CI/CD, performance evidence, limitations, and future improvements. Include diagrams and examples where they can be kept accurate.

## 4. Non-functional requirements

- **Reproducibility:** deterministic synthetic generation where practical; documented commands and configuration.
- **Traceability:** preserve source identity and run metadata through processing; make rejection reasons inspectable.
- **Correctness:** define grains, keys, metrics, deduplication rules, and business assumptions before implementation.
- **Maintainability:** use modular Python, SQL organized by purpose, configuration outside hard-coded business logic, and clear repository conventions.
- **Portability:** develop on Windows with PowerShell-compatible instructions; keep local processing independent of paid Azure resources.
- **Scalability path:** support configurable volumes and document a realistic local development scale before attempting the brief’s larger target volumes.
- **Security:** never commit credentials, personal data, or secrets; use synthetic data and an example-only environment file.
- **Honest evidence:** report only measured counts, test results, runtimes, sizes, and deployments. Label design proposals as proposals.
- **Learnability:** explain each major concept before implementation, then show actual results and a short learning/interview note.
- **Cost control:** prefer local alternatives; explain service purpose and potential costs before any action that may incur meaningful charges, and obtain the user's approval first.

## 5. Technical requirements and proposed choices

| Area | Local implementation target | Later target / boundary |
|---|---|---|
| Language | Python | Python remains the orchestration and utility language |
| Tabular processing | Pandas for an initial, manageable dataset | PySpark for distributed-processing concepts and portable transformations |
| SQL engine | SQLite for a low-friction local start, subject to a prerequisite check | Azure Databricks SQL/Spark SQL concepts; no cloud instance assumed |
| Source/interchange | CSV | Parquet for columnar outputs; Delta Lake only where local support is verified |
| Quality and tests | pytest; lightweight linting such as Ruff | CI checks in Azure DevOps YAML; actual hosted execution only if configured |
| Version control | Git repository with documented branch and PR practices | GitHub hosting is a later user-controlled publication step |
| Orchestration | Local scripts initially, with run logging | ADF / Databricks Workflows as design targets unless actually implemented |
| Storage | Local project data folders | ADLS Gen2 as the cloud mapping target, not a presumed resource |
| BI | Power BI-ready Gold tables and measure definitions | A Power BI report only if actually built and verified |
| Configuration | Environment/config files with safe examples | Secrets conceptually mapped to Key Vault; never commit secret values |

SQLite is proposed because it is bundled with Python and allows SQL learning without a separate database service. Its tradeoff is that it is not a distributed analytics engine and is not a stand-in for Databricks. Before Phase 1 selects dependencies or assumes installed tools, the environment will be checked. No Docker, Azure CLI, Databricks CLI, or paid service is assumed available.

## 6. Assumptions

1. All initial records are synthetic and exist for learning; there is no real retailer source system or private customer data.
2. Store and online orders share the same order/order-item model. `sales_channel` distinguishes online from in-store transactions.
3. An order has one customer where known, one order timestamp, and one fulfillment/store context; customer and store IDs may be intentionally missing or invalid in defective source records.
4. `order_items` is the sales fact’s natural grain: one row per order line. Revenue is defined initially as quantity multiplied by unit selling price, less line discount if the field is included. Taxes, shipping, promotions, and currency conversion are excluded unless added as explicit fields and rules.
5. `orders.order_total` is a source control total to reconcile against its item lines; it is not independently added to line revenue, which would double-count sales.
6. Payments are separate transactions and may be split or have statuses. Revenue metrics use fulfilled/valid order lines under a documented rule, not raw payment attempts. The precise treatment of cancellations, refunds, and tax will be finalized before transformation implementation.
7. Returns reference an original order and product/order line where possible. The return fact’s grain is one return event per returned order line; returned quantities and values cannot exceed eligible purchased amounts after valid historical returns are considered.
8. Inventory is a periodic snapshot by product, store, and snapshot date. Inventory value is on-hand quantity multiplied by a documented unit cost, not selling price.
9. “Active customer” means at least one valid completed order during a defined rolling period; the time window will be configured and documented before Gold implementation.
10. Customer lifetime value is an observed-period measure of net sales for the available synthetic history; it is not a forecast or a true lifetime estimate.
11. The initial local sample will be intentionally smaller than the target volumes in the brief. A proposed starting profile is 5,000 customers, 500 products, 20 stores, 20,000 orders, approximately 40,000 order items, 20,000 payments, and 10,000 inventory snapshots/rows plus returns. The final configurable counts and resulting sizes will be recorded only after generation and measurement.
12. The project is local-first; cloud deployment, GitHub publication, and Power BI screenshots require actual setup and user-controlled accounts/actions.

## 7. Constraints and risks

- Large CSV volumes can consume substantial disk, memory, and generation time on a personal Windows machine. Start with a small sample and increase only after measuring resource use.
- Pandas is single-machine memory-bound for the selected workload. Spark on one computer demonstrates APIs and execution concepts, not proof of cluster-scale performance.
- Local Delta Lake support depends on compatible runtime/package versions. If unsupported or impractical, retain a clearly marked design/notebook path instead of claiming a working Delta implementation.
- SQLite differs from production cloud warehouses in SQL features, concurrency, and performance. SQL examples may need dialect-specific adjustments later.
- KPI definitions depend on business rules for cancellations, payment status, returns, discounts, taxes, and snapshot timing. Those rules must be explicit to avoid misleading results.
- Azure, hosted CI, Databricks, and Power BI may require account setup or incur charges. No paid resource will be created without first explaining its role, alternatives, and potential costs and getting approval.
- No performance claim or scale claim is valid without a measured run on the actual environment and dataset.

## 8. Success criteria

The project is complete only when the brief’s final criteria are demonstrated with evidence. At a high level:

1. Configurable, reproducible data generation creates all eight related datasets and controlled quality defects.
2. Ingestion validates file contracts and writes run summaries; malformed inputs are traceable and quarantined.
3. Quality rules execute and produce machine-readable results, including detected duplicates, invalid values, and broken references.
4. Documented transformations create Bronze, Silver, and Gold outputs and reconcile important business totals.
5. SQL transformations and the star schema support the specified business questions with documented grain and KPI definitions.
6. PySpark transformations run on the chosen local setup and write Parquet. Delta behavior is counted as implemented only if run and verified.
7. Automated tests, linting, and the CI pipeline configuration are present; actual pipeline execution is reported separately from configuration.
8. Power BI-ready Gold datasets and DAX definitions are documented; actual report artifacts are claimed only if built.
9. Documentation, diagrams, setup instructions, and security hygiene are complete.
10. Final project metrics and CV bullets use only actual measured outcomes; the user can explain the data flow, choices, limitations, and next steps.

## 9. High-level architecture

```text
Synthetic operational CSV sources
        |
        v
Local ingestion + file/schema contract checks
        |
        v
Bronze: source-preserving records + run/source metadata
        |
        v
Validation + quarantine + quality reports
        |
        v
Silver: typed, standardized, deduplicated, relationship-checked data
        |
        v
SQL / Pandas transformations --> PySpark learning path --> Parquet (Delta where verified)
        |
        v
Gold: sales, customer, product, store, inventory, returns datasets
        |
        v
Star schema + KPI definitions --> Power BI-ready analytical layer
```

**Cloud mapping (future design unless actually deployed):** local files map to ADLS Gen2; local PySpark jobs map to Azure Databricks; local scheduling maps to ADF or Databricks Workflows; secrets map to Key Vault; monitoring maps to Azure Monitor; source control and YAML CI map to GitHub/Azure DevOps. Identity, networking, deployment, and cost choices will be documented before any cloud resource is considered.

## 10. Data flow

1. Generate seeded synthetic source files with clean relationships plus controlled defects.
2. Ingest each expected file and record run ID, source path/name, ingestion timestamp, byte size, row count, schema result, and status.
3. Preserve the received representation in Bronze and attach metadata; do not silently overwrite source values.
4. Run quality checks. Separate rejectable records into quarantine with rule/reason and retain aggregate quality results.
5. Standardize data types and domain values, deduplicate using declared business keys and precedence rules, and validate references in Silver.
6. Transform trusted records into facts, dimensions, and domain summaries. Reconcile sales totals, returns, and inventory values against source controls where possible.
7. Publish Gold files/tables with documented grains and KPI semantics for analysts and Power BI.
8. Capture run and quality metrics. In later phases, run suitable transformations through PySpark and compare outputs for correctness before documenting runtime or scale observations.

## 11. Dataset design

| Dataset | Proposed grain / key | Main relationships and notable quality cases |
|---|---|---|
| customers | One customer record; `customer_id` | Orders reference customer; duplicate IDs, missing email/phone, malformed email, invalid IDs |
| products | One product record; `product_id` | Order items and inventory reference product; duplicate products, missing/inconsistent category, invalid cost/price |
| stores | One store; `store_id` | Orders and inventory reference store; intentionally missing/unknown store IDs in selected records |
| orders | One order; `order_id` | Customer/store references; duplicate order IDs, malformed/future dates, negative/control-total inconsistencies, channel/status |
| order_items | One product line in an order; proposed composite natural key `order_id + line_number` | References order and product; invalid product IDs, nonpositive quantity, negative price, line-total mismatch |
| payments | One payment attempt/transaction; `payment_id` | References order; missing method, multiple attempts, statuses, invalid amounts or timestamps |
| inventory | One product-store-date snapshot; proposed key `product_id + store_id + snapshot_date` | References product/store; negative on-hand, missing store, invalid cost, duplicate snapshots |
| returns | One return event per order line; `return_id` | References order and original line/product; orphan order, invalid date/quantity/value, cumulative quantity above purchased quantity |

Each generated file will have a schema and data dictionary. The project will distinguish a source/business key from any warehouse surrogate key. Synthetic IDs and dates will be chosen to make joins and time-series questions useful; exact columns and nullability will be frozen in Phase 2’s data contract before generation code is written.

## 12. Technology mapping and learning sequence

- **Python:** generation, configuration, ingestion, reusable validation, orchestration, and logging.
- **Pandas:** first local transformation implementation with manageable data, emphasizing eager, in-memory tabular processing.
- **SQL / SQLite:** staging and analytical transformations, joins, aggregates, CTEs, windows, and dimensional-model queries.
- **PySpark:** distributed-processing model, DataFrames, lazy evaluation, partitions, joins, aggregations, windows, and Parquet. Local Spark is a learning environment, not a claim of distributed scale.
- **Delta Lake:** ACID table concepts, schema enforcement/evolution, time travel, and merge/upsert; implement only if compatible local support is confirmed.
- **Azure Databricks / ADLS Gen2:** explain and map the local layers to target services; create resources only with explicit cost discussion and approval.
- **GitHub / Azure DevOps:** versioning and YAML CI configuration; distinguish checked-in configuration from a hosted pipeline that has actually run.
- **Power BI:** semantic model and DAX definitions over Gold; screenshots and report completion only after actual manual or automated creation and verification.

## 13. Complete implementation roadmap

Each phase is a checkpoint. Work stops at its end until the user instructs continuation, as requested in the project brief.

| Phase | Deliverable / teaching focus | Completion evidence |
|---|---|---|
| 0. Requirements (current) | This requirements document, assumptions, architecture, flow, data design, technology map, roadmap | Document reviewed; no implementation started |
| 1. Project initialization | Repository layout, Python environment and dependencies, configuration, README skeleton, Git basics | Prerequisite check and project startup verified |
| 2. Data generation | Reusable seeded CLI generator, eight configurable CSVs, injected defects, data dictionary | Generated sample counts, schemas, and reproducibility checked |
| 3. Raw ingestion | File discovery, contract checks, metadata, logs, failure handling, quarantine | Ingestion summary and failure example |
| 4. Data validation | Reusable quality rules and machine-readable report | Rule-level pass/fail output and invalid-record examples |
| 5. SQL | Staging, cleaned and analytical SQL; core and advanced SQL concepts | Queries run locally and outputs explained |
| 6. Data model | Fact/dimension design, grain, keys, relationships, ERD | Schema documentation and join paths |
| 7. Bronze/Silver/Gold | Layered transformations and domain Gold summaries | Reconciled local outputs and transformation notes |
| 8. PySpark | Spark concepts then suitable transformation migration | Local PySpark output compared for correctness; Parquet written |
| 9. Delta Lake | Delta concepts and incremental merge | Insert/update/unchanged behavior run if local support permits |
| 10. Databricks | Workspace, compute, notebooks, jobs, catalog, secrets concepts | Portable notebooks and exact run guidance; deployment status stated |
| 11. Azure | ADLS, Databricks, orchestration, Key Vault, monitoring, security and cost design | Implemented versus designed services clearly labeled |
| 12. DevOps | Git workflow and Azure DevOps multi-stage YAML | YAML reviewed; hosted run reported only if it occurs |
| 13. Automated testing | pytest coverage for ingestion, schemas, transformations, quality, business rules | Actual test summary; intentionally failing examples isolated/documented |
| 14. Power BI | Gold interface, semantic model, KPIs and DAX | Measures and build/capture instructions; no fabricated visuals |
| 15. Monitoring | Pipeline execution and data-quality metrics | Run log records configured metrics and freshness |
| 16. Performance | Measurements for meaningful local workloads | Reproducible measured timings/sizes/counts with environment context |
| 17. Documentation | Professional README and architecture/data/quality/decision docs | Instructions and diagrams match actual implementation |
| 18. GitHub portfolio | Repository presentation, examples, sample data, setup and security review | Portfolio checklist; publication status accurately stated |
| 19. Final metrics | Actual implementation, quality, test, and performance metrics | Metrics table derived from run artifacts, no estimates presented as results |
| 20. CV entry | Maximum 2–3 evidence-based project bullets | Wording clearly represents hands-on project work, not professional experience |
| Interview preparation | Question bank across ten topic areas and 60-second, 2-minute, and 5-minute explanations | Answers grounded in project decisions, results, limitations, and trade-offs |

### Phase gates

- **Gate A:** Wait for `CONTINUE TO PHASE 1` before creating the repository or environment.
- **Gate B onward:** At the end of each numbered implementation phase, summarize what was taught, changed, and verified, then stop for the user’s next instruction.
- **Cloud gate:** Before any action that could create meaningful cloud charges, explain the service, purpose, local alternative, and potential costs, then ask for approval.
- **Evidence gate:** Do not report a test, performance result, hosted deployment, screenshot, or metric until it has actually been produced and inspected.

## 14. Phase 0 exit condition

Phase 0 is complete when the user has a reviewable requirements baseline and can choose whether to proceed. The next authorized action is Phase 1 only after the user says **“CONTINUE TO PHASE 1.”**
