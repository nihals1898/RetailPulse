"""Seeded synthetic data generation for the RetailPulse learning project.

The generator uses only Python's standard library and streams fact rows to CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from array import array
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any


CUSTOMER_FIELDS = [
    "customer_id", "first_name", "last_name", "email", "phone", "signup_date",
    "birth_date", "city", "region", "loyalty_tier",
]
PRODUCT_FIELDS = [
    "product_id", "sku", "product_name", "category", "subcategory", "brand",
    "unit_cost", "list_price", "is_active",
]
STORE_FIELDS = [
    "store_id", "store_name", "store_type", "city", "region", "country", "opened_date",
]
ORDER_FIELDS = [
    "order_id", "customer_id", "store_id", "sales_channel", "order_date", "order_status",
    "currency", "order_total",
]
ORDER_ITEM_FIELDS = [
    "order_item_id", "order_id", "line_number", "product_id", "quantity", "unit_price",
    "discount_amount", "line_total",
]
PAYMENT_FIELDS = [
    "payment_id", "order_id", "payment_date", "payment_method", "payment_status", "amount",
]
INVENTORY_FIELDS = [
    "inventory_id", "product_id", "store_id", "snapshot_date", "on_hand_quantity",
    "unit_cost", "inventory_value",
]
RETURN_FIELDS = [
    "return_id", "order_id", "order_item_id", "product_id", "return_date",
    "return_quantity", "refund_amount", "return_reason", "return_status",
]

FIRST_NAMES = ["Alex", "Amina", "Ben", "Camila", "Chen", "David", "Elena", "Fatima", "Grace", "Hugo", "Imani", "Jamie", "Kai", "Lena", "Maya", "Noah", "Olivia", "Priya", "Sam", "Theo"]
LAST_NAMES = ["Adams", "Bennett", "Chen", "Diaz", "Evans", "Fischer", "Garcia", "Haddad", "Ivanov", "Jones", "Kim", "Lopez", "Martin", "Nguyen", "Osei", "Patel", "Rossi", "Singh", "Taylor", "Wilson"]
LOCATIONS = [
    ("Lyon", "Auvergne-Rhone-Alpes"), ("Paris", "Ile-de-France"),
    ("Marseille", "Provence-Alpes-Cote d'Azur"), ("Lille", "Hauts-de-France"),
    ("Bordeaux", "Nouvelle-Aquitaine"), ("Nantes", "Pays de la Loire"),
    ("Toulouse", "Occitanie"), ("Nice", "Provence-Alpes-Cote d'Azur"),
]
CATEGORIES = {
    "Electronics": ["Audio", "Computing", "Accessories"],
    "Home and Kitchen": ["Cookware", "Storage", "Small Appliances"],
    "Apparel": ["Tops", "Outerwear", "Footwear"],
    "Beauty": ["Skincare", "Haircare", "Fragrance"],
    "Sports": ["Fitness", "Outdoor", "Team Sports"],
    "Books": ["Fiction", "Nonfiction", "Children"],
}
BRANDS = ["Northstar", "Brightline", "Everyday Co", "Urban Field", "Blue Orchard", "Peak House"]
PAYMENT_METHODS = ["credit_card", "debit_card", "gift_card", "paypal", "bank_transfer"]
RETURN_REASONS = ["damaged", "wrong_item", "not_as_described", "changed_mind", "size_or_fit"]


@dataclass(frozen=True)
class GenerationConfig:
    """Input settings; optional fact counts are resolved from the order count."""

    customers: int = 5_000
    products: int = 500
    stores: int = 20
    orders: int = 20_000
    order_items: int | None = None
    payments: int | None = None
    inventory: int = 10_000
    returns: int | None = None
    seed: int = 42
    as_of_date: date = date(2025, 12, 31)
    defect_rate: float = 0.02
    output_dir: Path = Path("data/raw")

    def resolved_counts(self) -> dict[str, int]:
        item_count = self.order_items if self.order_items is not None else self.orders * 2
        payment_count = self.payments if self.payments is not None else self.orders
        return_count = self.returns if self.returns is not None else self.orders // 20
        return {
            "customers": self.customers,
            "products": self.products,
            "stores": self.stores,
            "orders": self.orders,
            "order_items": item_count,
            "payments": payment_count,
            "inventory": self.inventory,
            "returns": return_count,
        }

    def validate(self) -> dict[str, int]:
        counts = self.resolved_counts()
        if any(value < 0 for value in counts.values()):
            raise ValueError("Row counts cannot be negative.")
        if not 0 <= self.defect_rate <= 0.25:
            raise ValueError("--defect-rate must be between 0 and 0.25.")
        if self.orders and min(self.customers, self.products, self.stores) == 0:
            raise ValueError("Orders require at least one customer, product, and store.")
        if self.orders and counts["order_items"] < self.orders:
            raise ValueError("order_items must be at least the order count so every order has a line.")
        if not self.orders and counts["order_items"]:
            raise ValueError("order_items require at least one order.")
        if counts["returns"] > counts["order_items"]:
            raise ValueError("returns cannot exceed order_items in this generator.")
        if counts["payments"] and not self.orders:
            raise ValueError("Payments require at least one order.")
        if counts["inventory"] and min(self.products, self.stores) == 0:
            raise ValueError("Inventory requires at least one product and one store.")
        return counts


def _write_rows(path: Path, fields: list[str], rows: Any) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _money(value: float) -> str:
    return f"{value:.2f}"


def _timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _date_between(rng: random.Random, start: date, end: date) -> date:
    span = (end - start).days
    return start + timedelta(days=rng.randrange(span + 1))


def _defect_indices(
    size: int, rate: float, seed: int, issue: int, excluded: set[int] | None = None
) -> set[int]:
    """Choose stable, non-first row positions for one injected defect rule."""
    blocked = excluded or set()
    candidates = [index for index in range(1, size) if index not in blocked]
    if not candidates or rate == 0:
        return set()
    count = min(len(candidates), max(1, round(size * rate)))
    return set(random.Random(seed + issue * 1_000_003).sample(candidates, count))


def _base_date_range(as_of: date) -> tuple[date, date]:
    return date(as_of.year - 3, 1, 1), as_of


def _make_customer_rows(
    count: int, seed: int, defect_rate: float, defects: dict[str, int], as_of: date
) -> tuple[list[str], list[dict[str, str]]]:
    rng = random.Random(seed + 11)
    duplicate = _defect_indices(count, defect_rate, seed, 1)
    missing_email = _defect_indices(count, defect_rate, seed, 2)
    invalid_email = _defect_indices(count, defect_rate, seed, 3, missing_email)
    missing_phone = _defect_indices(count, defect_rate, seed, 4)
    invalid_signup = _defect_indices(count, defect_rate, seed, 5)
    defects.update({
        "customers.duplicate_customer_id": len(duplicate),
        "customers.missing_email": len(missing_email),
        "customers.invalid_email": len(invalid_email),
        "customers.missing_phone": len(missing_phone),
        "customers.invalid_signup_date": len(invalid_signup),
    })
    customer_ids: list[str] = []
    rows: list[dict[str, str]] = []
    for index in range(count):
        customer_id = f"CUS{index + 1:08d}"
        customer_ids.append(customer_id)
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{index + 1:06d}@retailpulse.example"
        signup = _date_between(rng, date(as_of.year - 8, 1, 1), as_of).isoformat()
        birth = _date_between(rng, date(as_of.year - 85, 1, 1), date(as_of.year - 18, 12, 31)).isoformat()
        city, region = rng.choice(LOCATIONS)
        if index in duplicate:
            customer_id = f"CUS{index:08d}"
        if index in missing_email:
            email = ""
        elif index in invalid_email:
            email = "not-an-email"
        if index in missing_phone:
            phone = ""
        else:
            phone = f"+33-6-{rng.randrange(10_000_000, 100_000_000)}"
        if index in invalid_signup:
            signup = "2025-19-42"
        rows.append({
            "customer_id": customer_id,
            "first_name": first,
            "last_name": last,
            "email": email,
            "phone": phone,
            "signup_date": signup,
            "birth_date": birth,
            "city": city,
            "region": region,
            "loyalty_tier": rng.choice(["standard", "silver", "gold", "platinum"]),
        })
    return customer_ids, rows


def _make_products(count: int, seed: int, rate: float, defects: dict[str, int]) -> list[dict[str, str]]:
    rng = random.Random(seed + 23)
    duplicate = _defect_indices(count, rate, seed, 11)
    missing_category = _defect_indices(count, rate, seed, 12)
    inconsistent_category = _defect_indices(count, rate, seed, 13, missing_category)
    negative_cost = _defect_indices(count, rate, seed, 14)
    negative_price = _defect_indices(count, rate, seed, 15)
    defects.update({
        "products.duplicate_product_id": len(duplicate),
        "products.missing_category": len(missing_category),
        "products.inconsistent_category": len(inconsistent_category),
        "products.negative_unit_cost": len(negative_cost),
        "products.negative_list_price": len(negative_price),
    })
    rows: list[dict[str, str]] = []
    for index in range(count):
        product_id = f"PRD{index + 1:07d}"
        category = rng.choice(list(CATEGORIES))
        cost = round(rng.uniform(2.0, 120.0), 2)
        price = round(cost * rng.uniform(1.25, 2.8), 2)
        if index in duplicate:
            product_id = f"PRD{index:07d}"
        if index in missing_category:
            category_value = ""
        elif index in inconsistent_category:
            category_value = "Home & Kitchen" if category == "Home and Kitchen" else category.lower()
        else:
            category_value = category
        if index in negative_cost:
            cost = -cost
        if index in negative_price:
            price = -price
        rows.append({
            "product_id": product_id,
            "sku": f"SKU-{index + 1:07d}",
            "product_name": f"{rng.choice(BRANDS)} {rng.choice(CATEGORIES[category])} {index + 1:04d}",
            "category": category_value,
            "subcategory": rng.choice(CATEGORIES[category]),
            "brand": rng.choice(BRANDS),
            "unit_cost": _money(cost),
            "list_price": _money(price),
            "is_active": str(rng.random() >= 0.04).lower(),
        })
    return rows


def _make_stores(count: int, seed: int, as_of: date) -> list[dict[str, str]]:
    rng = random.Random(seed + 31)
    rows = []
    for index in range(count):
        city, region = rng.choice(LOCATIONS)
        rows.append({
            "store_id": f"STR{index + 1:04d}",
            "store_name": f"RetailPulse {city} {index + 1:03d}",
            "store_type": rng.choice(["flagship", "standard", "outlet"]),
            "city": city,
            "region": region,
            "country": "France",
            "opened_date": _date_between(rng, as_of - timedelta(days=20 * 365), as_of).isoformat(),
        })
    return rows


def _new_order(index: int, rng: random.Random, customer_ids: list[str], store_ids: list[str], start: date, as_of: date) -> tuple[dict[str, str], int]:
    offset = rng.randrange((as_of - start).days + 1)
    day = start + timedelta(days=offset)
    seconds = rng.randrange(24 * 60 * 60)
    order_status = rng.choices(
        ["completed", "pending", "cancelled", "partially_refunded"],
        weights=[86, 6, 5, 3],
        k=1,
    )[0]
    return {
        "order_id": f"ORD{index + 1:09d}",
        "customer_id": rng.choice(customer_ids),
        "store_id": rng.choice(store_ids),
        "sales_channel": rng.choice(["online", "store"]),
        "order_date": _timestamp(datetime.combine(day, time()) + timedelta(seconds=seconds)),
        "order_status": order_status,
        "currency": "EUR",
    }, offset


def generate(config: GenerationConfig) -> dict[str, Any]:
    """Generate all source files and return a reproducible counts/defects summary."""
    counts = config.validate()
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    defects: dict[str, int] = {}

    customer_ids, customers = _make_customer_rows(
        counts["customers"], config.seed, config.defect_rate, defects, config.as_of_date
    )
    products = _make_products(counts["products"], config.seed, config.defect_rate, defects)
    stores = _make_stores(counts["stores"], config.seed, config.as_of_date)
    store_ids = [row["store_id"] for row in stores]
    _write_rows(output_dir / "customers.csv", CUSTOMER_FIELDS, customers)
    _write_rows(output_dir / "products.csv", PRODUCT_FIELDS, products)
    _write_rows(output_dir / "stores.csv", STORE_FIELDS, stores)

    order_count = counts["orders"]
    item_count = counts["order_items"]
    extra_item_counts = array("I", [0]) * order_count
    remaining = item_count - order_count
    distribution_rng = random.Random(config.seed + 41)
    for _ in range(remaining):
        extra_item_counts[distribution_rng.randrange(order_count)] += 1
    item_counts = array("I", (value + 1 for value in extra_item_counts))
    order_totals = array("d", [0.0]) * order_count
    order_date_offsets = array("I", [0]) * order_count

    item_duplicate_product = _defect_indices(item_count, config.defect_rate, config.seed, 21)
    item_missing_product = _defect_indices(item_count, config.defect_rate, config.seed, 22)
    item_negative_quantity = _defect_indices(item_count, config.defect_rate, config.seed, 23)
    item_negative_price = _defect_indices(item_count, config.defect_rate, config.seed, 24)
    defects.update({
        "order_items.invalid_product_id": len(item_duplicate_product),
        "order_items.missing_product_id": len(item_missing_product),
        "order_items.negative_quantity": len(item_negative_quantity),
        "order_items.negative_unit_price": len(item_negative_price),
    })
    return_items: list[dict[str, Any]] = []
    item_rng = random.Random(config.seed + 43)
    order_rng = random.Random(config.seed + 47)
    start, _ = _base_date_range(config.as_of_date)
    item_index = 0
    with (output_dir / "order_items.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ORDER_ITEM_FIELDS)
        writer.writeheader()
        for order_index in range(order_count):
            _, date_offset = _new_order(order_index, order_rng, customer_ids, store_ids, start, config.as_of_date)
            order_date_offsets[order_index] = date_offset
            for line_number in range(1, item_counts[order_index] + 1):
                product = item_rng.choice(products)
                quantity = item_rng.randint(1, 5)
                unit_price = round(float(product["list_price"]) * item_rng.uniform(0.80, 1.0), 2)
                discount = round(quantity * unit_price * item_rng.uniform(0.0, 0.12), 2)
                line_total = round(quantity * unit_price - discount, 2)
                order_item_id = f"ITM{item_index + 1:010d}"
                order_id = f"ORD{order_index + 1:09d}"
                if item_index < counts["returns"]:
                    return_items.append({
                        "order_index": order_index,
                        "order_id": order_id,
                        "order_item_id": order_item_id,
                        "product_id": product["product_id"],
                        "quantity": quantity,
                        "line_total": line_total,
                    })
                order_totals[order_index] += line_total
                output_product_id = product["product_id"]
                output_quantity = quantity
                output_unit_price = unit_price
                if item_index in item_duplicate_product:
                    output_product_id = "PRD9999999"
                if item_index in item_missing_product:
                    output_product_id = ""
                if item_index in item_negative_quantity:
                    output_quantity = -quantity
                if item_index in item_negative_price:
                    output_unit_price = -unit_price
                writer.writerow({
                    "order_item_id": order_item_id,
                    "order_id": order_id,
                    "line_number": line_number,
                    "product_id": output_product_id,
                    "quantity": output_quantity,
                    "unit_price": _money(output_unit_price),
                    "discount_amount": _money(discount),
                    "line_total": _money(line_total),
                })
                item_index += 1

    order_duplicate = _defect_indices(order_count, config.defect_rate, config.seed, 31)
    order_bad_customer = _defect_indices(order_count, config.defect_rate, config.seed, 32)
    order_missing_store = _defect_indices(order_count, config.defect_rate, config.seed, 33)
    order_invalid_date = _defect_indices(order_count, config.defect_rate, config.seed, 34)
    order_future_date = _defect_indices(order_count, config.defect_rate, config.seed, 35, order_invalid_date)
    order_negative_total = _defect_indices(order_count, config.defect_rate, config.seed, 36)
    defects.update({
        "orders.duplicate_order_id": len(order_duplicate),
        "orders.invalid_customer_id": len(order_bad_customer),
        "orders.missing_store_id": len(order_missing_store),
        "orders.invalid_order_date": len(order_invalid_date),
        "orders.future_order_date": len(order_future_date),
        "orders.negative_order_total": len(order_negative_total),
    })
    order_rng = random.Random(config.seed + 47)
    with (output_dir / "orders.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ORDER_FIELDS)
        writer.writeheader()
        for index in range(order_count):
            row, _ = _new_order(index, order_rng, customer_ids, store_ids, start, config.as_of_date)
            if index in order_duplicate:
                row["order_id"] = f"ORD{index:09d}"
            if index in order_bad_customer:
                row["customer_id"] = "CUS99999999"
            if index in order_missing_store:
                row["store_id"] = ""
            if index in order_invalid_date:
                row["order_date"] = "not-a-date"
            elif index in order_future_date:
                row["order_date"] = _timestamp(datetime.combine(config.as_of_date + timedelta(days=90), time()))
            total = order_totals[index]
            if index in order_negative_total:
                total = -max(total, 1.0)
            row["order_total"] = _money(total)
            writer.writerow(row)

    payment_missing_method = _defect_indices(counts["payments"], config.defect_rate, config.seed, 41)
    payment_invalid_method = _defect_indices(counts["payments"], config.defect_rate, config.seed, 42, payment_missing_method)
    payment_orphan_order = _defect_indices(counts["payments"], config.defect_rate, config.seed, 43)
    payment_negative = _defect_indices(counts["payments"], config.defect_rate, config.seed, 44)
    defects.update({
        "payments.missing_payment_method": len(payment_missing_method),
        "payments.invalid_payment_method": len(payment_invalid_method),
        "payments.invalid_order_id": len(payment_orphan_order),
        "payments.negative_amount": len(payment_negative),
    })
    payment_rng = random.Random(config.seed + 53)
    with (output_dir / "payments.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAYMENT_FIELDS)
        writer.writeheader()
        for index in range(counts["payments"]):
            order_index = index % order_count
            order_id = f"ORD{order_index + 1:09d}"
            base_day = start + timedelta(days=order_date_offsets[order_index])
            paid_day = min(config.as_of_date, base_day + timedelta(days=payment_rng.randrange(0, 6)))
            amount = order_totals[order_index]
            if index in payment_missing_method:
                method = ""
            elif index in payment_invalid_method:
                method = "unknown_tender"
            else:
                method = payment_rng.choice(PAYMENT_METHODS)
            if index in payment_orphan_order:
                order_id = "ORD999999999"
            if index in payment_negative:
                amount = -max(amount, 1.0)
            writer.writerow({
                "payment_id": f"PAY{index + 1:09d}",
                "order_id": order_id,
                "payment_date": _timestamp(datetime.combine(paid_day, time()) + timedelta(seconds=payment_rng.randrange(86400))),
                "payment_method": method,
                "payment_status": payment_rng.choices(["captured", "authorized", "failed", "refunded"], [82, 8, 7, 3], k=1)[0],
                "amount": _money(amount),
            })

    inventory_missing_store = _defect_indices(counts["inventory"], config.defect_rate, config.seed, 51)
    inventory_negative_stock = _defect_indices(counts["inventory"], config.defect_rate, config.seed, 52)
    inventory_negative_cost = _defect_indices(counts["inventory"], config.defect_rate, config.seed, 53)
    inventory_duplicate_snapshot = _defect_indices(counts["inventory"], config.defect_rate, config.seed, 54)
    defects.update({
        "inventory.missing_store_id": len(inventory_missing_store),
        "inventory.negative_on_hand_quantity": len(inventory_negative_stock),
        "inventory.negative_unit_cost": len(inventory_negative_cost),
        "inventory.duplicate_product_store_snapshot": len(inventory_duplicate_snapshot),
    })
    inventory_rng = random.Random(config.seed + 59)
    combinations_per_snapshot = len(products) * len(stores)
    with (output_dir / "inventory.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=INVENTORY_FIELDS)
        writer.writeheader()
        for index in range(counts["inventory"]):
            combination = index % combinations_per_snapshot
            product_index = combination // len(stores)
            store_index = combination % len(stores)
            snapshot_number = index // combinations_per_snapshot
            month_index = snapshot_number % 24
            month_start = date(config.as_of_date.year, config.as_of_date.month, 1)
            snapshot_date = _add_months(month_start, -month_index)
            product_id = products[product_index]["product_id"]
            store_id = store_ids[store_index]
            on_hand = inventory_rng.randint(0, 250)
            unit_cost = float(products[product_index]["unit_cost"])
            if index in inventory_duplicate_snapshot and index > 0:
                product_id = products[0]["product_id"]
                store_id = store_ids[0]
                snapshot_date = config.as_of_date.replace(day=1)
            if index in inventory_missing_store:
                store_id = ""
            if index in inventory_negative_stock:
                on_hand = -inventory_rng.randint(1, 20)
            if index in inventory_negative_cost:
                unit_cost = -abs(unit_cost)
            writer.writerow({
                "inventory_id": f"INV{index + 1:09d}",
                "product_id": product_id,
                "store_id": store_id,
                "snapshot_date": snapshot_date.isoformat(),
                "on_hand_quantity": on_hand,
                "unit_cost": _money(unit_cost),
                "inventory_value": _money(on_hand * unit_cost),
            })

    return_orphan_order = _defect_indices(counts["returns"], config.defect_rate, config.seed, 61)
    return_excess_quantity = _defect_indices(counts["returns"], config.defect_rate, config.seed, 62)
    return_invalid_date = _defect_indices(counts["returns"], config.defect_rate, config.seed, 63)
    return_future_date = _defect_indices(counts["returns"], config.defect_rate, config.seed, 64, return_invalid_date)
    return_negative_refund = _defect_indices(counts["returns"], config.defect_rate, config.seed, 65)
    defects.update({
        "returns.invalid_order_id": len(return_orphan_order),
        "returns.quantity_exceeds_purchase": len(return_excess_quantity),
        "returns.invalid_return_date": len(return_invalid_date),
        "returns.future_return_date": len(return_future_date),
        "returns.negative_refund_amount": len(return_negative_refund),
    })
    return_rows = []
    return_rng = random.Random(config.seed + 67)
    for index, item in enumerate(return_items):
        order_index = item["order_index"]
        purchased_day = start + timedelta(days=order_date_offsets[order_index])
        return_day = min(config.as_of_date, purchased_day + timedelta(days=return_rng.randrange(1, 61)))
        quantity = return_rng.randint(1, item["quantity"])
        refund = round(item["line_total"] * quantity / item["quantity"], 2)
        order_id = item["order_id"]
        if index in return_orphan_order:
            order_id = "ORD999999999"
        if index in return_excess_quantity:
            quantity = item["quantity"] + 1
        if index in return_invalid_date:
            return_date = "2025-40-90"
        elif index in return_future_date:
            return_date = (config.as_of_date + timedelta(days=120)).isoformat()
        else:
            return_date = return_day.isoformat()
        if index in return_negative_refund:
            refund = -max(refund, 1.0)
        return_rows.append({
            "return_id": f"RET{index + 1:08d}",
            "order_id": order_id,
            "order_item_id": item["order_item_id"],
            "product_id": item["product_id"],
            "return_date": return_date,
            "return_quantity": quantity,
            "refund_amount": _money(refund),
            "return_reason": return_rng.choice(RETURN_REASONS),
            "return_status": return_rng.choice(["approved", "received", "refunded"]),
        })
    _write_rows(output_dir / "returns.csv", RETURN_FIELDS, return_rows)

    summary = {
        "seed": config.seed,
        "as_of_date": config.as_of_date.isoformat(),
        "defect_rate": config.defect_rate,
        "row_counts": counts,
        "injected_defects_by_rule": defects,
        "note": "Defect counts are rule-level counts; one row may contain multiple injected defects.",
    }
    (output_dir / "generation_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def _add_months(value: date, months: int) -> date:
    month_number = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_number, 12)
    month = month_zero + 1
    return date(year, month, min(value.day, 28))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate reproducible RetailPulse CSV source data with intentional quality defects."
    )
    parser.add_argument("--customers", type=int, default=5_000, help="Customer rows (default: 5000).")
    parser.add_argument("--products", type=int, default=500, help="Product rows (default: 500).")
    parser.add_argument("--stores", type=int, default=20, help="Store rows (default: 20).")
    parser.add_argument("--orders", type=int, default=20_000, help="Order rows (default: 20000).")
    parser.add_argument("--order-items", type=int, default=None, help="Order-item rows (default: 2 per order).")
    parser.add_argument("--payments", type=int, default=None, help="Payment rows (default: 1 per order).")
    parser.add_argument("--inventory", type=int, default=10_000, help="Inventory snapshots (default: 10000).")
    parser.add_argument("--returns", type=int, default=None, help="Return rows (default: 5%% of orders).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42).")
    parser.add_argument("--as-of-date", default="2025-12-31", help="Synthetic reference date, YYYY-MM-DD.")
    parser.add_argument("--defect-rate", type=float, default=0.02, help="Rate per injected rule, 0 to 0.25 (default: 0.02).")
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"), help="CSV output folder (default: data/raw).")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        reference_date = date.fromisoformat(args.as_of_date)
        config = GenerationConfig(
            customers=args.customers,
            products=args.products,
            stores=args.stores,
            orders=args.orders,
            order_items=args.order_items,
            payments=args.payments,
            inventory=args.inventory,
            returns=args.returns,
            seed=args.seed,
            as_of_date=reference_date,
            defect_rate=args.defect_rate,
            output_dir=args.output_dir,
        )
        summary = generate(config)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"Generated RetailPulse datasets in: {config.output_dir.resolve()}")
    for dataset, row_count in summary["row_counts"].items():
        print(f"  {dataset}: {row_count:,} rows")
    print(f"  quality rules with injected examples: {sum(value > 0 for value in summary['injected_defects_by_rule'].values())}")


if __name__ == "__main__":
    main()
