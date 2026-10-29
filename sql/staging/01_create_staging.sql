-- Staging keeps the source CSV representation as text and applies no cleanup.
DROP TABLE IF EXISTS stg_customers;
DROP TABLE IF EXISTS stg_products;
DROP TABLE IF EXISTS stg_stores;
DROP TABLE IF EXISTS stg_orders;
DROP TABLE IF EXISTS stg_order_items;
DROP TABLE IF EXISTS stg_payments;
DROP TABLE IF EXISTS stg_inventory;
DROP TABLE IF EXISTS stg_returns;

CREATE TABLE stg_customers (
    customer_id TEXT, first_name TEXT, last_name TEXT, email TEXT, phone TEXT,
    signup_date TEXT, birth_date TEXT, city TEXT, region TEXT, loyalty_tier TEXT
);
CREATE TABLE stg_products (
    product_id TEXT, sku TEXT, product_name TEXT, category TEXT, subcategory TEXT,
    brand TEXT, unit_cost TEXT, list_price TEXT, is_active TEXT
);
CREATE TABLE stg_stores (
    store_id TEXT, store_name TEXT, store_type TEXT, city TEXT, region TEXT,
    country TEXT, opened_date TEXT
);
CREATE TABLE stg_orders (
    order_id TEXT, customer_id TEXT, store_id TEXT, sales_channel TEXT,
    order_date TEXT, order_status TEXT, currency TEXT, order_total TEXT
);
CREATE TABLE stg_order_items (
    order_item_id TEXT, order_id TEXT, line_number TEXT, product_id TEXT,
    quantity TEXT, unit_price TEXT, discount_amount TEXT, line_total TEXT
);
CREATE TABLE stg_payments (
    payment_id TEXT, order_id TEXT, payment_date TEXT, payment_method TEXT,
    payment_status TEXT, amount TEXT
);
CREATE TABLE stg_inventory (
    inventory_id TEXT, product_id TEXT, store_id TEXT, snapshot_date TEXT,
    on_hand_quantity TEXT, unit_cost TEXT, inventory_value TEXT
);
CREATE TABLE stg_returns (
    return_id TEXT, order_id TEXT, order_item_id TEXT, product_id TEXT,
    return_date TEXT, return_quantity TEXT, refund_amount TEXT,
    return_reason TEXT, return_status TEXT
);
