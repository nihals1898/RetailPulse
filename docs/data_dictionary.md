# RetailPulse data dictionary

This dictionary describes the synthetic CSV source contracts produced by `generate_data.py`. CSV values are written as text; the listed types are the intended logical types for later validation and transformation. Empty strings represent missing values. IDs are synthetic business keys, not warehouse surrogate keys.

## Generation profile

The default local profile creates 5,000 customers, 500 products, 20 stores, 20,000 orders, 40,000 order items, 20,000 payments, 10,000 inventory rows, and 1,000 returns. Counts are configurable. The default seed is `42`; the synthetic reference date is `2025-12-31`; the default defect rate is 2% per applicable rule. Future-dated defect examples are future relative to the configured reference date.

`data/raw/generation_summary.json` records the configured row counts, seed, reference date, defect rate, and rule-level defect counts. The rule counts can overlap because one record may contain more than one defect. Re-running with the same settings overwrites the same eight CSVs and summary with reproducible contents.

## Dataset overview

| File | Grain | Primary/business key | Relationships |
|---|---|---|---|
| `customers.csv` | One source customer record | `customer_id` | Referenced by orders |
| `products.csv` | One source product record | `product_id` | Referenced by order items, inventory, and returns |
| `stores.csv` | One physical store | `store_id` | Referenced by orders and inventory |
| `orders.csv` | One order header | `order_id` | References customer and store; parent of order items and payments |
| `order_items.csv` | One product line within an order | `order_item_id`; candidate business key `order_id + line_number` | References orders and products |
| `payments.csv` | One payment attempt/transaction | `payment_id` | References orders |
| `inventory.csv` | One product/store/snapshot observation | `inventory_id`; intended grain key `product_id + store_id + snapshot_date` | References products and stores |
| `returns.csv` | One return event for an order line | `return_id` | References orders, order items, and products |

## `customers.csv`

| Column | Logical type | Meaning |
|---|---|---|
| `customer_id` | string | Synthetic customer business key |
| `first_name` | string | Synthetic given name |
| `last_name` | string | Synthetic family name |
| `email` | string | Synthetic `.example` address; may be missing or malformed |
| `phone` | string | Synthetic phone-like value; may be missing |
| `signup_date` | date | Account sign-up date; selected rows contain an invalid date string |
| `birth_date` | date | Synthetic date of birth |
| `city` | string | Synthetic French city |
| `region` | string | Synthetic French region |
| `loyalty_tier` | category | `standard`, `silver`, `gold`, or `platinum` |

Intentional defects include duplicate customer IDs, missing email/phone, invalid email format, and invalid sign-up date.

## `products.csv`

| Column | Logical type | Meaning |
|---|---|---|
| `product_id` | string | Synthetic product business key |
| `sku` | string | Synthetic stock keeping unit |
| `product_name` | string | Generated brand/category-based display name |
| `category` | string | Product category; can be missing or inconsistently cased/spelled |
| `subcategory` | string | Product subcategory |
| `brand` | string | Synthetic brand |
| `unit_cost` | decimal(10,2) | Synthetic unit acquisition cost; selected rows are negative |
| `list_price` | decimal(10,2) | Synthetic list price; selected rows are negative |
| `is_active` | boolean | Whether the source product is active |

Categories begin with Electronics, Home and Kitchen, Apparel, Beauty, Sports, and Books. Intentional defects include duplicate product IDs, missing/inconsistent category labels, and negative cost or list price.

## `stores.csv`

| Column | Logical type | Meaning |
|---|---|---|
| `store_id` | string | Synthetic store business key |
| `store_name` | string | Generated store display name |
| `store_type` | category | `flagship`, `standard`, or `outlet` |
| `city` | string | Synthetic French city |
| `region` | string | Synthetic French region |
| `country` | string | `France` |
| `opened_date` | date | Synthetic store opening date |

The initial generator keeps store dimension records valid; missing store references are injected into orders and inventory.

## `orders.csv`

| Column | Logical type | Meaning |
|---|---|---|
| `order_id` | string | Synthetic order business key |
| `customer_id` | string | Customer reference; selected rows point to an unknown ID |
| `store_id` | string | Store/fulfillment reference; selected rows are blank |
| `sales_channel` | category | `online` or `store` |
| `order_date` | timestamp | Order timestamp; selected rows are malformed or after the reference date |
| `order_status` | category | `completed`, `pending`, `cancelled`, or `partially_refunded` |
| `currency` | string | `EUR` |
| `order_total` | decimal(12,2) | Sum of generated source line totals before quality defects; selected rows are negative |

Intentional defects include duplicate order IDs, invalid customer references, missing store IDs, invalid/future dates, and negative order totals. Order totals are source control totals; later sales calculations should use order lines to avoid double-counting.

## `order_items.csv`

| Column | Logical type | Meaning |
|---|---|---|
| `order_item_id` | string | Synthetic order-line identifier |
| `order_id` | string | Parent order reference |
| `line_number` | integer | Line sequence within an order |
| `product_id` | string | Product reference; selected values are missing or unknown |
| `quantity` | integer | Units purchased; selected values are negative |
| `unit_price` | decimal(10,2) | Synthetic selling price per unit; selected values are negative |
| `discount_amount` | decimal(10,2) | Line discount |
| `line_total` | decimal(12,2) | `quantity × unit_price - discount_amount` before defects are applied |

The generator ensures each generated order has at least one line. Intentional defects include unknown/missing product IDs, negative quantities, and negative unit prices. The output row count stays equal to the configured row count.

## `payments.csv`

| Column | Logical type | Meaning |
|---|---|---|
| `payment_id` | string | Synthetic payment transaction identifier |
| `order_id` | string | Parent order reference; selected rows point to an unknown order |
| `payment_date` | timestamp | Synthetic payment time, normally within five days of the order |
| `payment_method` | category | `credit_card`, `debit_card`, `gift_card`, `paypal`, or `bank_transfer`; can be missing/unknown |
| `payment_status` | category | `captured`, `authorized`, `failed`, or `refunded` |
| `amount` | decimal(12,2) | Synthetic payment amount; selected rows are negative |

The payment count defaults to one row per order and can be configured independently. Intentional defects include missing/invalid methods, unknown order references, and negative amounts.

## `inventory.csv`

| Column | Logical type | Meaning |
|---|---|---|
| `inventory_id` | string | Synthetic snapshot row identifier |
| `product_id` | string | Product reference |
| `store_id` | string | Store reference; selected rows are blank |
| `snapshot_date` | date | Monthly snapshot date |
| `on_hand_quantity` | integer | Units on hand; selected rows are negative |
| `unit_cost` | decimal(10,2) | Inventory valuation cost; selected rows are negative |
| `inventory_value` | decimal(14,2) | `on_hand_quantity × unit_cost` |

The intended natural grain is one product, store, and snapshot date. Intentional defects include missing store IDs, duplicate natural-grain keys, negative on-hand quantity, and negative unit cost. The configurable row count may be a subset or multiple months of product/store combinations.

## `returns.csv`

| Column | Logical type | Meaning |
|---|---|---|
| `return_id` | string | Synthetic return event identifier |
| `order_id` | string | Parent order reference; selected rows point to an unknown order |
| `order_item_id` | string | Purchased line being returned |
| `product_id` | string | Returned product reference |
| `return_date` | date | Return date; selected rows are invalid or after the reference date |
| `return_quantity` | integer | Units returned; selected rows exceed the purchased quantity |
| `refund_amount` | decimal(12,2) | Synthetic refunded amount; selected rows are negative |
| `return_reason` | category | `damaged`, `wrong_item`, `not_as_described`, `changed_mind`, or `size_or_fit` |
| `return_status` | category | `approved`, `received`, or `refunded` |

Returns default to 5% of the order count and each clean return references a generated order line. Intentional defects include unknown order IDs, excess return quantity, invalid/future return dates, and negative refund amounts.

## Synthetic-data limitations

Names and contact fields are generated placeholders, not real customer data. Prices and business distributions are illustrative rather than calibrated to a real retailer. The initial output is for local development and learning; target-scale volume must be generated and measured separately before claiming it was processed.
