"""Run a local PySpark implementation of the product performance summary."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _prepare_java_path() -> None:
    """Make JAVA_HOME's bin directory discoverable on Windows processes."""
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        java_bin = str(Path(java_home) / "bin")
        current_path = os.environ.get("PATH", "")
        if java_bin.lower() not in current_path.lower().split(os.pathsep):
            os.environ["PATH"] = java_bin + os.pathsep + current_path


def _read_gold(database_path: Path) -> list[tuple[Any, ...]]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT product_id, sku, product_name, category, brand, units_sold,
                   order_count, gross_revenue, units_returned, refunds, unit_return_rate
            FROM gold_product_summary
            ORDER BY product_id
            """
        ).fetchall()
    return rows


def _spark_rows(frame: Any) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in frame.orderBy("product_id").collect()]


def _compare_results(
    spark_rows: list[tuple[Any, ...]], gold_rows: list[tuple[Any, ...]]
) -> dict[str, Any]:
    if len(spark_rows) != len(gold_rows):
        raise ValueError(
            f"Product summary row-count mismatch: Spark={len(spark_rows)}, SQLite={len(gold_rows)}"
        )
    numeric_tolerances = {5: 0.0, 6: 0.0, 7: 0.01, 8: 0.0, 9: 0.01, 10: 0.0001}
    mismatches = []
    for spark_row, gold_row in zip(spark_rows, gold_rows, strict=True):
        for index in range(len(gold_row)):
            left, right = spark_row[index], gold_row[index]
            if index in numeric_tolerances:
                if (
                    left is None
                    or right is None
                    or abs(float(left) - float(right)) > numeric_tolerances[index]
                ):
                    mismatches.append((spark_row[0], index, left, right))
                    break
            elif left != right:
                mismatches.append((spark_row[0], index, left, right))
                break
    if mismatches:
        sample = mismatches[:5]
        raise ValueError(
            "Spark product summary differs from SQLite Gold "
            f"({len(mismatches)} products); sample={sample}"
        )
    return {
        "compared_products": len(spark_rows),
        "mismatched_products": 0,
        "currency_tolerance": 0.01,
        "return_rate_tolerance": 0.0001,
        "count_tolerance": 0,
    }


def run_spark(
    input_dir: Path = Path("data/processed/silver"),
    database_path: Path = Path("data/processed/retailpulse.db"),
    output_path: Path = Path("data/processed/spark/product_summary.parquet"),
) -> dict[str, Any]:
    """Calculate Gold product KPIs with PySpark, compare them, and write Parquet."""
    input_dir = input_dir.resolve()
    database_path = database_path.resolve()
    output_path = output_path.resolve()
    required_inputs = ["products.csv", "orders.csv", "order_items.csv", "returns.csv"]
    missing = [name for name in required_inputs if not (input_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing Silver inputs: {', '.join(missing)}; run run_sql.py first."
        )
    if not database_path.is_file():
        raise FileNotFoundError(
            f"SQLite database does not exist: {database_path}; run run_sql.py first."
        )

    started_at = time.perf_counter()
    _prepare_java_path()
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
        from pyspark.sql import types as T
    except ImportError as error:
        raise RuntimeError(
            "Install the Spark extras with `pip install -e '.[spark]'` first."
        ) from error

    spark = (
        SparkSession.builder.master("local[*]")
        .appName("RetailPulse Phase 8 product summary")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    try:

        def read_csv(name: str) -> Any:
            return (
                spark.read.option("header", True)
                .option("inferSchema", True)
                .csv(str(input_dir / name))
            )

        products = read_csv("products.csv").select(
            "product_id", "sku", "product_name", "category", "brand"
        )
        orders = read_csv("orders.csv").select("order_id", "order_status")
        items = read_csv("order_items.csv").select(
            "order_item_id", "order_id", "product_id", "quantity", "line_total"
        )
        returns = read_csv("returns.csv").select("product_id", "return_quantity", "refund_amount")

        sales = (
            items.join(orders, "order_id", "inner")
            .filter(F.col("order_status") == "completed")
            .groupBy(items.product_id.alias("product_id"))
            .agg(
                F.sum("quantity").cast("long").alias("units_sold"),
                F.countDistinct("order_id").cast("long").alias("order_count"),
                F.round(F.sum(F.col("line_total").cast(T.DecimalType(18, 2))), 2).alias(
                    "gross_revenue"
                ),
            )
        )
        return_totals = returns.groupBy("product_id").agg(
            F.sum("return_quantity").cast("long").alias("units_returned"),
            F.round(F.sum(F.col("refund_amount").cast(T.DecimalType(18, 2))), 2).alias("refunds"),
        )

        units_sold = F.coalesce(F.col("units_sold"), F.lit(0)).cast("long")
        units_returned = F.coalesce(F.col("units_returned"), F.lit(0)).cast("long")

        product_summary = (
            products.join(sales, "product_id", "left")
            .join(return_totals, "product_id", "left")
            .select(
                "product_id",
                "sku",
                "product_name",
                "category",
                "brand",
                units_sold.alias("units_sold"),
                F.coalesce("order_count", F.lit(0)).cast("long").alias("order_count"),
                F.coalesce("gross_revenue", F.lit(0).cast(T.DecimalType(18, 2))).alias(
                    "gross_revenue"
                ),
                units_returned.alias("units_returned"),
                F.coalesce("refunds", F.lit(0).cast(T.DecimalType(18, 2))).alias("refunds"),
                F.when(units_sold == 0, F.lit(0.0))
                .otherwise(F.round(units_returned / units_sold, 4))
                .alias("unit_return_rate"),
            )
        )

        spark_result = _spark_rows(product_summary)
        gold_result = _read_gold(database_path)
        comparison = _compare_results(spark_result, gold_result)
        parquet_schema = pa.schema(
            [
                pa.field("product_id", pa.string()),
                pa.field("sku", pa.string()),
                pa.field("product_name", pa.string()),
                pa.field("category", pa.string()),
                pa.field("brand", pa.string()),
                pa.field("units_sold", pa.int64()),
                pa.field("order_count", pa.int64()),
                pa.field("gross_revenue", pa.decimal128(28, 2)),
                pa.field("units_returned", pa.int64()),
                pa.field("refunds", pa.decimal128(28, 2)),
                pa.field("unit_return_rate", pa.float64()),
            ]
        )
        parquet_table = pa.Table.from_pylist(
            [dict(zip(product_summary.columns, row, strict=True)) for row in spark_result],
            schema=parquet_schema,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(parquet_table, output_path)
        summary = {
            "run_timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "spark_version": spark.version,
            "master": spark.sparkContext.master,
            "input_dir": str(input_dir),
            "output_parquet_path": str(output_path),
            "output_rows": len(spark_result),
            "output_size_bytes": output_path.stat().st_size,
            "duration_seconds": round(time.perf_counter() - started_at, 3),
            "java_home": os.environ.get("JAVA_HOME"),
            "comparison": comparison,
        }
        summary_path = output_path.with_name("spark_run_summary.json")
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary
    finally:
        spark.stop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and verify a RetailPulse product summary with local PySpark."
    )
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed/silver"))
    parser.add_argument("--database", type=Path, default=Path("data/processed/retailpulse.db"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/spark/product_summary.parquet")
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        summary = run_spark(args.input_dir, args.database, args.output)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"PySpark pipeline could not complete: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
