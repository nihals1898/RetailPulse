# Phase 13 — automated testing

Run the local suite from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp work\pytest-tmp
```

The project-local `--basetemp` keeps temporary fixtures under ignored `work/`. This is useful in restricted Windows environments where pytest cannot create folders under the default user temp path. Azure Pipelines runs pytest on its hosted agent with the default temporary location.

## Coverage

- **Generation and schemas:** same seed/config produces identical CSV bytes and expected file headers; invalid row counts, defect rates, and entity relationships are rejected.
- **Ingestion:** clean contracts and row counts are reported without modifying inputs; malformed rows are quarantined as partial data; schema mismatch quarantines the full file.
- **Quality and business rules:** a small clean synthetic fixture passes; an order-total reconciliation error and a return quantity greater than its purchased quantity are reported; violation detail caps are respected; missing inputs fail clearly.
- **SQL transformations and model:** a clean fixture runs through staging, Bronze/Silver/Gold exports, analytics and star-schema creation; the test checks table counts, foreign keys, and reconciles product-summary revenue against completed sales facts.

The clean fixture uses temporary files and a zero defect rate. Separate tests intentionally change one field to assert the expected quality failure; these are passing tests of the failure-handling behavior, not unexpected suite failures.

## Current results

The latest local run completed with **13 passed in 1.19 seconds** using the command above. This is a local result, not a hosted Azure Pipelines result. The pipeline configuration runs pytest but has not been connected or executed in Azure DevOps. Phase 15 also tests that SQL monitoring records both successful and failed runs.

Ruff has pre-existing findings across application source under E501, I001, UP017, and UP035. The pipeline currently excludes those four existing rule categories while running the remaining configured Ruff checks against `src` and `tests`. A separate lint-cleanup phase can address that baseline without mixing broad formatting changes into this test phase.
