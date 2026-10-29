-- Bronze retains every raw source value as text and appends ingestion metadata.
DROP TABLE IF EXISTS bronze_customers;
DROP TABLE IF EXISTS bronze_products;
DROP TABLE IF EXISTS bronze_stores;
DROP TABLE IF EXISTS bronze_orders;
DROP TABLE IF EXISTS bronze_order_items;
DROP TABLE IF EXISTS bronze_payments;
DROP TABLE IF EXISTS bronze_inventory;
DROP TABLE IF EXISTS bronze_returns;

CREATE TABLE bronze_customers (
    customer_id TEXT, first_name TEXT, last_name TEXT, email TEXT, phone TEXT,
    signup_date TEXT, birth_date TEXT, city TEXT, region TEXT, loyalty_tier TEXT,
    source_file TEXT NOT NULL, source_system TEXT NOT NULL, ingestion_timestamp TEXT NOT NULL,
    ingestion_run_id TEXT NOT NULL, source_row_number INTEGER NOT NULL,
    source_file_size_bytes INTEGER NOT NULL
);
CREATE TABLE bronze_products (
    product_id TEXT, sku TEXT, product_name TEXT, category TEXT, subcategory TEXT,
    brand TEXT, unit_cost TEXT, list_price TEXT, is_active TEXT,
    source_file TEXT NOT NULL, source_system TEXT NOT NULL, ingestion_timestamp TEXT NOT NULL,
    ingestion_run_id TEXT NOT NULL, source_row_number INTEGER NOT NULL,
    source_file_size_bytes INTEGER NOT NULL
);
CREATE TABLE bronze_stores (
    store_id TEXT, store_name TEXT, store_type TEXT, city TEXT, region TEXT,
    country TEXT, opened_date TEXT,
    source_file TEXT NOT NULL, source_system TEXT NOT NULL, ingestion_timestamp TEXT NOT NULL,
    ingestion_run_id TEXT NOT NULL, source_row_number INTEGER NOT NULL,
    source_file_size_bytes INTEGER NOT NULL
);
CREATE TABLE bronze_orders (
    order_id TEXT, customer_id TEXT, store_id TEXT, sales_channel TEXT,
    order_date TEXT, order_status TEXT, currency TEXT, order_total TEXT,
    source_file TEXT NOT NULL, source_system TEXT NOT NULL, ingestion_timestamp TEXT NOT NULL,
    ingestion_run_id TEXT NOT NULL, source_row_number INTEGER NOT NULL,
    source_file_size_bytes INTEGER NOT NULL
);
CREATE TABLE bronze_order_items (
    order_item_id TEXT, order_id TEXT, line_number TEXT, product_id TEXT,
    quantity TEXT, unit_price TEXT, discount_amount TEXT, line_total TEXT,
    source_file TEXT NOT NULL, source_system TEXT NOT NULL, ingestion_timestamp TEXT NOT NULL,
    ingestion_run_id TEXT NOT NULL, source_row_number INTEGER NOT NULL,
    source_file_size_bytes INTEGER NOT NULL
);
CREATE TABLE bronze_payments (
    payment_id TEXT, order_id TEXT, payment_date TEXT, payment_method TEXT,
    payment_status TEXT, amount TEXT,
    source_file TEXT NOT NULL, source_system TEXT NOT NULL, ingestion_timestamp TEXT NOT NULL,
    ingestion_run_id TEXT NOT NULL, source_row_number INTEGER NOT NULL,
    source_file_size_bytes INTEGER NOT NULL
);
CREATE TABLE bronze_inventory (
    inventory_id TEXT, product_id TEXT, store_id TEXT, snapshot_date TEXT,
    on_hand_quantity TEXT, unit_cost TEXT, inventory_value TEXT,
    source_file TEXT NOT NULL, source_system TEXT NOT NULL, ingestion_timestamp TEXT NOT NULL,
    ingestion_run_id TEXT NOT NULL, source_row_number INTEGER NOT NULL,
    source_file_size_bytes INTEGER NOT NULL
);
CREATE TABLE bronze_returns (
    return_id TEXT, order_id TEXT, order_item_id TEXT, product_id TEXT,
    return_date TEXT, return_quantity TEXT, refund_amount TEXT,
    return_reason TEXT, return_status TEXT,
    source_file TEXT NOT NULL, source_system TEXT NOT NULL, ingestion_timestamp TEXT NOT NULL,
    ingestion_run_id TEXT NOT NULL, source_row_number INTEGER NOT NULL,
    source_file_size_bytes INTEGER NOT NULL
);
