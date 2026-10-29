"""Demonstrate a versioned local Delta table and an incremental merge."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


def _product_record(row: dict[str, str], updated_at: str) -> dict[str, Any]:
    return {
        "product_id": row["product_id"],
        "sku": row["sku"],
        "product_name": row["product_name"],
        "category": row["category"],
        "brand": row["brand"],
        "list_price": Decimal(row["list_price"]),
        "source_updated_at": updated_at,
    }


def _read_sample_products(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) < 2:
        raise ValueError(
            "The Silver products file needs at least two valid rows for the merge example."
        )
    return rows[:2]


def _rows_by_product(table: Any) -> dict[str, dict[str, Any]]:
    return {row["product_id"]: row for row in table.to_pyarrow_table().to_pylist()}


def run_delta(
    products_path: Path = Path("data/processed/silver/products.csv"),
    table_path: Path = Path("data/processed/delta/product_catalog_merge_demo"),
) -> dict[str, Any]:
    """Create a small Delta table, merge one insert/update/unchanged row, and verify history."""
    products_path = products_path.resolve()
    table_path = table_path.resolve()
    if not products_path.is_file():
        raise FileNotFoundError(
            f"Silver products file not found: {products_path}; run run_sql.py first."
        )

    try:
        import pyarrow as pa
        from deltalake import DeltaTable, write_deltalake
    except ImportError as error:
        raise RuntimeError(
            "Install the optional Delta dependencies with `pip install -e '.[delta]'`."
        ) from error

    base_rows = _read_sample_products(products_path)
    initial_timestamp = "2025-12-01T00:00:00Z"
    merge_timestamp = "2025-12-15T00:00:00Z"
    initial = [_product_record(row, initial_timestamp) for row in base_rows]
    unchanged = dict(initial[0])
    changed = dict(initial[1])
    changed["list_price"] = (changed["list_price"] + Decimal("1.25")).quantize(Decimal("0.01"))
    changed["source_updated_at"] = merge_timestamp
    inserted = {
        "product_id": "PRD_PHASE9_DEMO_001",
        "sku": "SKU-PHASE9-DEMO-001",
        "product_name": "Delta Merge Demonstration Product",
        "category": base_rows[0]["category"],
        "brand": "RetailPulse Demo",
        "list_price": Decimal("24.99"),
        "source_updated_at": merge_timestamp,
    }
    merge_batch = [unchanged, changed, inserted]

    schema = pa.schema(
        [
            pa.field("product_id", pa.string(), nullable=False),
            pa.field("sku", pa.string()),
            pa.field("product_name", pa.string()),
            pa.field("category", pa.string()),
            pa.field("brand", pa.string()),
            pa.field("list_price", pa.decimal128(18, 2)),
            pa.field("source_updated_at", pa.string()),
        ]
    )
    initial_table = pa.Table.from_pylist(initial, schema=schema)
    source_table = pa.Table.from_pylist(merge_batch, schema=schema)

    write_deltalake(str(table_path), initial_table, mode="overwrite")
    table = DeltaTable(str(table_path))
    initial_version = table.version()
    initial_state = _rows_by_product(table)
    merge_metrics = (
        table.merge(
            source=source_table,
            predicate="target.product_id = source.product_id",
            source_alias="source",
            target_alias="target",
        )
        .when_matched_update(
            updates={
                "sku": "source.sku",
                "product_name": "source.product_name",
                "category": "source.category",
                "brand": "source.brand",
                "list_price": "source.list_price",
                "source_updated_at": "source.source_updated_at",
            },
            predicate=(
                "source.list_price <> target.list_price "
                "OR source.source_updated_at > target.source_updated_at"
            ),
        )
        .when_not_matched_insert_all()
        .execute()
    )

    current_table = DeltaTable(str(table_path))
    current_state = _rows_by_product(current_table)
    historical_state = _rows_by_product(DeltaTable(str(table_path), version=initial_version))
    expected_updated_price = changed["list_price"]
    checks = {
        "initial_version": initial_version,
        "current_version": current_table.version(),
        "initial_rows": len(initial_state),
        "current_rows": len(current_state),
        "time_travel_rows": len(historical_state),
        "changed_price_matches": (
            current_state[changed["product_id"]]["list_price"] == expected_updated_price
        ),
        "unchanged_row_preserved": (
            current_state[unchanged["product_id"]]["list_price"]
            == initial_state[unchanged["product_id"]]["list_price"]
        ),
        "new_product_inserted": inserted["product_id"] in current_state,
        "time_travel_has_pre_merge_price": (
            historical_state[changed["product_id"]]["list_price"]
            == initial_state[changed["product_id"]]["list_price"]
        ),
    }
    expected_metrics = {"num_target_rows_inserted": 1, "num_target_rows_updated": 1}
    if not all(
        checks[name]
        for name in (
            "changed_price_matches",
            "unchanged_row_preserved",
            "new_product_inserted",
            "time_travel_has_pre_merge_price",
        )
    ) or any(int(merge_metrics.get(key, -1)) != value for key, value in expected_metrics.items()):
        raise ValueError(
            f"Delta merge verification failed: checks={checks}, metrics={merge_metrics}"
        )

    summary = {
        "run_timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "engine": "delta-rs Python bindings",
        "delta_version": __import__("deltalake").__version__,
        "table_path": str(table_path),
        "merge_source_rows": len(merge_batch),
        "merge_metrics": merge_metrics,
        "checks": checks,
        "history": current_table.history(),
    }
    summary_path = table_path.parent / "delta_run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Demonstrate a local Delta Lake incremental merge."
    )
    parser.add_argument("--products", type=Path, default=Path("data/processed/silver/products.csv"))
    parser.add_argument(
        "--table", type=Path, default=Path("data/processed/delta/product_catalog_merge_demo")
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        summary = run_delta(args.products, args.table)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Delta pipeline could not complete: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
