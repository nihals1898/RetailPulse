"""Reusable source-data quality checks for the RetailPulse CSV datasets."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

from retailpulse.generation import CATEGORIES
from retailpulse.ingestion.framework import EXPECTED_SCHEMAS

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_PATTERN = re.compile(r"^\+?\d[\d\s()-]{5,20}$")
CENT = Decimal("0.01")
TOLERANCE = Decimal("0.01")

REQUIRED_FIELDS: dict[str, list[str]] = {
    "customers": ["customer_id", "first_name", "last_name", "email", "phone", "signup_date"],
    "products": ["product_id", "sku", "product_name", "category", "unit_cost", "list_price"],
    "stores": ["store_id", "store_name", "country", "opened_date"],
    "orders": ["order_id", "customer_id", "store_id", "order_date", "order_status", "currency", "order_total"],
    "order_items": ["order_item_id", "order_id", "line_number", "product_id", "quantity", "unit_price", "discount_amount", "line_total"],
    "payments": ["payment_id", "order_id", "payment_date", "payment_method", "payment_status", "amount"],
    "inventory": ["inventory_id", "product_id", "store_id", "snapshot_date", "on_hand_quantity", "unit_cost", "inventory_value"],
    "returns": ["return_id", "order_id", "order_item_id", "product_id", "return_date", "return_quantity", "refund_amount", "return_reason", "return_status"],
}

RULE_NAMES: dict[str, list[str]] = {
    "customers": [
        *[f"required_{field}" for field in REQUIRED_FIELDS["customers"]],
        "customer_id_unique", "signup_date_valid", "signup_date_not_future", "birth_date_valid",
        "birth_date_not_future", "email_format", "phone_format",
    ],
    "products": [
        *[f"required_{field}" for field in REQUIRED_FIELDS["products"]],
        "product_id_unique", "unit_cost_nonnegative", "list_price_nonnegative", "category_valid",
    ],
    "stores": [
        *[f"required_{field}" for field in REQUIRED_FIELDS["stores"]],
        "store_id_unique", "opened_date_valid", "opened_date_not_future",
    ],
    "orders": [
        *[f"required_{field}" for field in REQUIRED_FIELDS["orders"]],
        "order_id_unique", "customer_id_exists", "store_id_exists", "order_date_valid",
        "order_date_not_future", "order_total_nonnegative", "order_total_reconciles_lines",
    ],
    "order_items": [
        *[f"required_{field}" for field in REQUIRED_FIELDS["order_items"]],
        "order_item_id_unique", "order_line_key_unique", "order_id_exists", "product_id_exists",
        "quantity_positive", "unit_price_nonnegative", "line_total_calculation",
    ],
    "payments": [
        *[f"required_{field}" for field in REQUIRED_FIELDS["payments"]],
        "payment_id_unique", "order_id_exists", "payment_date_valid", "payment_date_not_future",
        "amount_nonnegative", "payment_method_valid",
    ],
    "inventory": [
        *[f"required_{field}" for field in REQUIRED_FIELDS["inventory"]],
        "inventory_id_unique", "product_store_snapshot_unique", "product_id_exists", "store_id_exists",
        "snapshot_date_valid", "snapshot_date_not_future", "on_hand_nonnegative",
        "unit_cost_nonnegative", "inventory_value_reconciles",
    ],
    "returns": [
        *[f"required_{field}" for field in REQUIRED_FIELDS["returns"]],
        "return_id_unique", "order_id_exists", "order_item_id_exists", "product_id_exists",
        "return_date_valid", "return_date_not_future", "return_quantity_positive",
        "return_quantity_within_purchase", "refund_amount_nonnegative", "refund_reconciles_to_line",
    ],
}

REPORT_FIELDS = [
    "dataset", "rule", "total_rows", "failed_rows", "status", "failure_rate",
    "detail_rows_written", "details_truncated",
]
VIOLATION_FIELDS = ["dataset", "rule", "row_key", "details"]


def _blank(value: Any) -> bool:
    return value is None or not str(value).strip()


def _decimal(value: Any) -> Decimal | None:
    if _blank(value):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def _date(value: Any) -> date | None:
    if _blank(value):
        return None
    raw = str(value).strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None


def _rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        yield from csv.DictReader(handle, strict=True)


def _read_reference_date(input_dir: Path, override: date | None) -> date:
    if override is not None:
        return override
    summary_path = input_dir / "generation_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        return date.fromisoformat(summary["as_of_date"])
    return date(2025, 12, 31)


class QualityEngine:
    """Counts each failed rule and keeps a bounded sample of row-level details."""

    def __init__(self, detail_cap_per_rule: int = 1_000) -> None:
        if detail_cap_per_rule < 0:
            raise ValueError("detail_cap_per_rule cannot be negative.")
        self.detail_cap_per_rule = detail_cap_per_rule
        self.counters: dict[tuple[str, str], list[int]] = {}
        self.details: list[dict[str, str]] = []
        self.details_written: Counter[tuple[str, str]] = Counter()

    def register(self, dataset: str) -> None:
        for rule in RULE_NAMES[dataset]:
            self.counters.setdefault((dataset, rule), [0, 0])

    def observe(
        self,
        dataset: str,
        rule: str,
        passed: bool,
        row_key: Any,
        reason: str,
    ) -> None:
        key = (dataset, rule)
        counter = self.counters.setdefault(key, [0, 0])
        counter[0] += 1
        if passed:
            return
        counter[1] += 1
        if self.details_written[key] < self.detail_cap_per_rule:
            self.details.append({
                "dataset": dataset,
                "rule": rule,
                "row_key": "" if row_key is None else str(row_key),
                "details": reason,
            })
            self.details_written[key] += 1

    def required(self, dataset: str, row: dict[str, str], row_key: str) -> None:
        for field in REQUIRED_FIELDS[dataset]:
            value = row.get(field)
            self.observe(
                dataset,
                f"required_{field}",
                not _blank(value),
                row_key,
                f"Required field {field} is empty.",
            )

    def unique(
        self,
        dataset: str,
        rule: str,
        value: str,
        seen: set[str],
        row_key: str,
    ) -> None:
        key = value.strip()
        passed = not key or key not in seen
        if key:
            seen.add(key)
        self.observe(dataset, rule, passed, row_key, f"Duplicate key value: {key}")

    def as_report_rows(self) -> list[dict[str, Any]]:
        results = []
        for (dataset, rule), (total, failed) in sorted(self.counters.items()):
            results.append({
                "dataset": dataset,
                "rule": rule,
                "total_rows": total,
                "failed_rows": failed,
                "status": "not_applicable" if total == 0 else ("passed" if failed == 0 else "failed"),
                "failure_rate": "0.0000" if total == 0 else f"{failed / total:.4f}",
                "detail_rows_written": self.details_written[(dataset, rule)],
                "details_truncated": max(0, failed - self.details_written[(dataset, rule)]),
            })
        return results


def _check_date(
    engine: QualityEngine,
    dataset: str,
    row: dict[str, str],
    row_key: str,
    field: str,
    as_of: date,
) -> date | None:
    parsed = _date(row.get(field))
    engine.observe(dataset, f"{field}_valid", parsed is not None, row_key, f"{field} is not a valid ISO date/timestamp: {row.get(field)!r}")
    engine.observe(
        dataset,
        f"{field}_not_future",
        parsed is None or parsed <= as_of,
        row_key,
        f"{field} is after the synthetic reference date {as_of.isoformat()}: {row.get(field)!r}",
    )
    return parsed


def _check_nonnegative(engine: QualityEngine, dataset: str, rule: str, value: Any, row_key: str, field: str) -> None:
    parsed = _decimal(value)
    engine.observe(
        dataset, rule, parsed is not None and parsed >= 0, row_key,
        f"{field} must be a valid nonnegative number; received {value!r}.",
    )


def _check_foreign_key(
    engine: QualityEngine, dataset: str, rule: str, value: Any, reference: set[str], row_key: str, field: str
) -> None:
    key = "" if _blank(value) else str(value).strip()
    engine.observe(
        dataset, rule, bool(key) and key in reference, row_key,
        f"{field} value {value!r} is blank or absent from its reference dataset.",
    )


def _check_unique_row(
    engine: QualityEngine, dataset: str, rule: str, value: str, seen: set[str], row_key: str
) -> None:
    engine.unique(dataset, rule, value, seen, row_key)


def _check_csv_shape(path: Path, dataset: str) -> None:
    """Fail early if Phase 3 structural ingestion has not produced a usable CSV."""
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle, strict=True)
            header = next(reader)
            for line_number, row in enumerate(reader, start=2):
                if len(row) != len(header):
                    raise ValueError(f"{path.name}, line {line_number}: malformed CSV row; run Phase 3 ingestion first.")
    except StopIteration as error:
        raise ValueError(f"{path.name} is empty; run Phase 3 ingestion first.") from error
    except csv.Error as error:
        raise ValueError(f"{path.name} is structurally malformed: {error}; run Phase 3 ingestion first.") from error
    expected = EXPECTED_SCHEMAS[dataset]
    if set(header) != set(expected) or len(header) != len(expected):
        raise ValueError(f"{path.name} has a schema mismatch; run Phase 3 ingestion first.")


def validate(
    input_dir: Path = Path("data/raw"),
    output_dir: Path = Path("data/processed/quality"),
    as_of_date: date | None = None,
    detail_cap_per_rule: int = 1_000,
) -> dict[str, Any]:
    """Run completeness, uniqueness, validity, format, relationship, and business checks."""
    input_dir = input_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for dataset in RULE_NAMES:
        path = input_dir / f"{dataset}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"Required input is missing: {path}")
        _check_csv_shape(path, dataset)
    reference_date = _read_reference_date(input_dir, as_of_date)
    engine = QualityEngine(detail_cap_per_rule)
    for dataset in RULE_NAMES:
        engine.register(dataset)

    customer_ids: set[str] = set()
    customer_seen: set[str] = set()
    for index, row in enumerate(_rows(input_dir / "customers.csv"), start=1):
        key = row.get("customer_id", "") or ""
        engine.required("customers", row, key or str(index))
        _check_unique_row(engine, "customers", "customer_id_unique", key, customer_seen, key or str(index))
        if key.strip():
            customer_ids.add(key.strip())
        _check_date(engine, "customers", row, key or str(index), "signup_date", reference_date)
        _check_date(engine, "customers", row, key or str(index), "birth_date", reference_date)
        email = row.get("email", "") or ""
        phone = row.get("phone", "") or ""
        engine.observe("customers", "email_format", bool(EMAIL_PATTERN.fullmatch(email)), key or str(index), f"Email does not match the expected address pattern: {email!r}.")
        engine.observe("customers", "phone_format", bool(PHONE_PATTERN.fullmatch(phone)), key or str(index), f"Phone does not match the expected phone pattern: {phone!r}.")

    product_ids: set[str] = set()
    product_seen: set[str] = set()
    for index, row in enumerate(_rows(input_dir / "products.csv"), start=1):
        key = row.get("product_id", "") or ""
        engine.required("products", row, key or str(index))
        _check_unique_row(engine, "products", "product_id_unique", key, product_seen, key or str(index))
        if key.strip():
            product_ids.add(key.strip())
        _check_nonnegative(engine, "products", "unit_cost_nonnegative", row.get("unit_cost"), key or str(index), "unit_cost")
        _check_nonnegative(engine, "products", "list_price_nonnegative", row.get("list_price"), key or str(index), "list_price")
        category = row.get("category", "") or ""
        engine.observe("products", "category_valid", category in CATEGORIES, key or str(index), f"Unknown or noncanonical category: {category!r}.")

    store_ids: set[str] = set()
    store_seen: set[str] = set()
    for index, row in enumerate(_rows(input_dir / "stores.csv"), start=1):
        key = row.get("store_id", "") or ""
        engine.required("stores", row, key or str(index))
        _check_unique_row(engine, "stores", "store_id_unique", key, store_seen, key or str(index))
        if key.strip():
            store_ids.add(key.strip())
        _check_date(engine, "stores", row, key or str(index), "opened_date", reference_date)

    order_ids: set[str] = set()
    order_seen: set[str] = set()
    order_records: list[tuple[str, str, int]] = []
    for index, row in enumerate(_rows(input_dir / "orders.csv"), start=1):
        key = row.get("order_id", "") or ""
        row_key = key or str(index)
        engine.required("orders", row, row_key)
        _check_unique_row(engine, "orders", "order_id_unique", key, order_seen, row_key)
        if key.strip():
            order_ids.add(key.strip())
        _check_foreign_key(engine, "orders", "customer_id_exists", row.get("customer_id"), customer_ids, row_key, "customer_id")
        _check_foreign_key(engine, "orders", "store_id_exists", row.get("store_id"), store_ids, row_key, "store_id")
        _check_date(engine, "orders", row, row_key, "order_date", reference_date)
        _check_nonnegative(engine, "orders", "order_total_nonnegative", row.get("order_total"), row_key, "order_total")
        order_records.append((key.strip(), row.get("order_total", ""), index))

    return_item_ids: set[str] = set()
    for row in _rows(input_dir / "returns.csv"):
        item_id = row.get("order_item_id", "") or ""
        if item_id.strip():
            return_item_ids.add(item_id.strip())

    item_seen: set[str] = set()
    line_key_seen: set[str] = set()
    item_ids: set[str] = set()
    return_item_metrics: dict[str, tuple[int | None, Decimal | None]] = {}
    item_totals_by_order: dict[str, Decimal] = defaultdict(Decimal)
    for index, row in enumerate(_rows(input_dir / "order_items.csv"), start=1):
        key = row.get("order_item_id", "") or ""
        row_key = key or str(index)
        engine.required("order_items", row, row_key)
        _check_unique_row(engine, "order_items", "order_item_id_unique", key, item_seen, row_key)
        if key.strip():
            item_ids.add(key.strip())
        line_key = f"{row.get('order_id', '')}|{row.get('line_number', '')}"
        _check_unique_row(engine, "order_items", "order_line_key_unique", line_key, line_key_seen, row_key)
        _check_foreign_key(engine, "order_items", "order_id_exists", row.get("order_id"), order_ids, row_key, "order_id")
        _check_foreign_key(engine, "order_items", "product_id_exists", row.get("product_id"), product_ids, row_key, "product_id")
        quantity = _decimal(row.get("quantity"))
        engine.observe("order_items", "quantity_positive", quantity is not None and quantity > 0 and quantity == quantity.to_integral_value(), row_key, f"quantity must be a positive integer; received {row.get('quantity')!r}.")
        _check_nonnegative(engine, "order_items", "unit_price_nonnegative", row.get("unit_price"), row_key, "unit_price")
        price = _decimal(row.get("unit_price"))
        discount = _decimal(row.get("discount_amount"))
        line_total = _decimal(row.get("line_total"))
        calculated = None if quantity is None or price is None or discount is None else (quantity * price - discount).quantize(CENT, rounding=ROUND_HALF_UP)
        formula_passed = calculated is not None and line_total is not None and abs(calculated - line_total) <= TOLERANCE
        engine.observe("order_items", "line_total_calculation", formula_passed, row_key, f"line_total should equal quantity × unit_price - discount_amount; calculated={calculated}, actual={line_total}.")
        order_id = row.get("order_id", "") or ""
        if order_id.strip() and line_total is not None:
            item_totals_by_order[order_id.strip()] += line_total
        if key.strip() in return_item_ids:
            purchased_quantity = None if quantity is None else int(quantity)
            return_item_metrics[key.strip()] = (purchased_quantity, line_total)

    for order_id, raw_total, index in order_records:
        source_total = _decimal(raw_total)
        item_total = item_totals_by_order.get(order_id, Decimal("0"))
        passed = source_total is not None and abs(source_total - item_total) <= TOLERANCE
        engine.observe("orders", "order_total_reconciles_lines", passed, order_id or str(index), f"Order total {source_total} differs from summed line totals {item_total}.")

    payment_seen: set[str] = set()
    valid_payment_methods = {"credit_card", "debit_card", "gift_card", "paypal", "bank_transfer"}
    for index, row in enumerate(_rows(input_dir / "payments.csv"), start=1):
        key = row.get("payment_id", "") or ""
        row_key = key or str(index)
        engine.required("payments", row, row_key)
        _check_unique_row(engine, "payments", "payment_id_unique", key, payment_seen, row_key)
        _check_foreign_key(engine, "payments", "order_id_exists", row.get("order_id"), order_ids, row_key, "order_id")
        _check_date(engine, "payments", row, row_key, "payment_date", reference_date)
        _check_nonnegative(engine, "payments", "amount_nonnegative", row.get("amount"), row_key, "amount")
        method = row.get("payment_method", "") or ""
        engine.observe("payments", "payment_method_valid", method in valid_payment_methods, row_key, f"Unknown or missing payment method: {method!r}.")

    inventory_seen: set[str] = set()
    inventory_grain_seen: set[str] = set()
    for index, row in enumerate(_rows(input_dir / "inventory.csv"), start=1):
        key = row.get("inventory_id", "") or ""
        row_key = key or str(index)
        engine.required("inventory", row, row_key)
        _check_unique_row(engine, "inventory", "inventory_id_unique", key, inventory_seen, row_key)
        _check_foreign_key(engine, "inventory", "product_id_exists", row.get("product_id"), product_ids, row_key, "product_id")
        _check_foreign_key(engine, "inventory", "store_id_exists", row.get("store_id"), store_ids, row_key, "store_id")
        grain_key = "|".join((row.get("product_id", "") or "", row.get("store_id", "") or "", row.get("snapshot_date", "") or ""))
        _check_unique_row(engine, "inventory", "product_store_snapshot_unique", grain_key, inventory_grain_seen, row_key)
        _check_date(engine, "inventory", row, row_key, "snapshot_date", reference_date)
        quantity = _decimal(row.get("on_hand_quantity"))
        engine.observe("inventory", "on_hand_nonnegative", quantity is not None and quantity >= 0 and quantity == quantity.to_integral_value(), row_key, f"on_hand_quantity must be a nonnegative integer; received {row.get('on_hand_quantity')!r}.")
        _check_nonnegative(engine, "inventory", "unit_cost_nonnegative", row.get("unit_cost"), row_key, "unit_cost")
        cost = _decimal(row.get("unit_cost"))
        value = _decimal(row.get("inventory_value"))
        calculated_value = None if quantity is None or cost is None else (quantity * cost).quantize(CENT, rounding=ROUND_HALF_UP)
        engine.observe("inventory", "inventory_value_reconciles", calculated_value is not None and value is not None and abs(calculated_value - value) <= TOLERANCE, row_key, f"inventory_value should equal on_hand_quantity × unit_cost; calculated={calculated_value}, actual={value}.")

    return_seen: set[str] = set()
    for index, row in enumerate(_rows(input_dir / "returns.csv"), start=1):
        key = row.get("return_id", "") or ""
        row_key = key or str(index)
        engine.required("returns", row, row_key)
        _check_unique_row(engine, "returns", "return_id_unique", key, return_seen, row_key)
        _check_foreign_key(engine, "returns", "order_id_exists", row.get("order_id"), order_ids, row_key, "order_id")
        _check_foreign_key(engine, "returns", "order_item_id_exists", row.get("order_item_id"), item_ids, row_key, "order_item_id")
        _check_foreign_key(engine, "returns", "product_id_exists", row.get("product_id"), product_ids, row_key, "product_id")
        _check_date(engine, "returns", row, row_key, "return_date", reference_date)
        returned = _decimal(row.get("return_quantity"))
        engine.observe("returns", "return_quantity_positive", returned is not None and returned > 0 and returned == returned.to_integral_value(), row_key, f"return_quantity must be a positive integer; received {row.get('return_quantity')!r}.")
        item_id = (row.get("order_item_id", "") or "").strip()
        purchased, purchase_total = return_item_metrics.get(item_id, (None, None))
        within_purchase = purchased is not None and returned is not None and returned <= purchased
        engine.observe("returns", "return_quantity_within_purchase", within_purchase, row_key, f"Return quantity {returned} exceeds purchased quantity {purchased} or the source line is unavailable.")
        _check_nonnegative(engine, "returns", "refund_amount_nonnegative", row.get("refund_amount"), row_key, "refund_amount")
        refund = _decimal(row.get("refund_amount"))
        expected_refund = None
        if purchased is not None and purchased > 0 and returned is not None and purchase_total is not None:
            expected_refund = (purchase_total * returned / purchased).quantize(CENT, rounding=ROUND_HALF_UP)
        refund_passed = refund is not None and expected_refund is not None and abs(refund - expected_refund) <= TOLERANCE
        engine.observe("returns", "refund_reconciles_to_line", refund_passed, row_key, f"Refund {refund} differs from expected line-based refund {expected_refund}.")

    report_rows = engine.as_report_rows()
    _write_report(output_dir / "quality_report.csv", REPORT_FIELDS, report_rows)
    _write_report(output_dir / "quality_violations.csv", VIOLATION_FIELDS, engine.details)
    failed_rules = sum(row["status"] == "failed" for row in report_rows)
    passed_rules = sum(row["status"] == "passed" for row in report_rows)
    not_applicable = sum(row["status"] == "not_applicable" for row in report_rows)
    result = {
        "validation_timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "input_dir": str(input_dir),
        "as_of_date": reference_date.isoformat(),
        "rules_evaluated": len(report_rows),
        "rules_passed": passed_rules,
        "rules_failed": failed_rules,
        "rules_not_applicable": not_applicable,
        "failed_row_counts_across_rules": sum(row["failed_rows"] for row in report_rows),
        "violation_details_written": len(engine.details),
        "violation_detail_cap_per_rule": detail_cap_per_rule,
        "run_status": "completed",
        "quality_status": "failed" if failed_rules else "passed",
    }
    (output_dir / "quality_summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _write_report(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run reusable RetailPulse data-quality checks.")
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/quality"))
    parser.add_argument("--as-of-date", type=date.fromisoformat, default=None, help="Override reference date (YYYY-MM-DD).")
    parser.add_argument("--detail-cap-per-rule", type=int, default=1_000, help="Maximum violation samples saved per rule.")
    parser.add_argument("--fail-on-issues", action="store_true", help="Exit with status 1 when any rule fails.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        result = validate(args.input_dir, args.output_dir, args.as_of_date, args.detail_cap_per_rule)
    except (OSError, ValueError, json.JSONDecodeError, csv.Error) as error:
        print(f"Quality validation could not complete: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    print(json.dumps(result, indent=2))
    if args.fail_on_issues and result["quality_status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
