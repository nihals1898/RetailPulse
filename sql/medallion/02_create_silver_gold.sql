-- Silver is the typed, standardized, deduplicated, and validated clean layer.
-- Gold tables are business-facing summaries built by Phase 5 SQL.
DROP TABLE IF EXISTS silver_customers;
DROP TABLE IF EXISTS silver_products;
DROP TABLE IF EXISTS silver_stores;
DROP TABLE IF EXISTS silver_orders;
DROP TABLE IF EXISTS silver_order_items;
DROP TABLE IF EXISTS silver_payments;
DROP TABLE IF EXISTS silver_inventory;
DROP TABLE IF EXISTS silver_returns;

CREATE TABLE silver_customers AS SELECT * FROM clean_customers;
CREATE TABLE silver_products AS SELECT * FROM clean_products;
CREATE TABLE silver_stores AS SELECT * FROM clean_stores;
CREATE TABLE silver_orders AS SELECT * FROM clean_orders;
CREATE TABLE silver_order_items AS SELECT * FROM clean_order_items;
CREATE TABLE silver_payments AS SELECT * FROM clean_payments;
CREATE TABLE silver_inventory AS SELECT * FROM clean_inventory;
CREATE TABLE silver_returns AS SELECT * FROM clean_returns;

DROP TABLE IF EXISTS gold_monthly_sales;
DROP TABLE IF EXISTS gold_customer_summary;
DROP TABLE IF EXISTS gold_product_summary;
DROP TABLE IF EXISTS gold_store_summary;
DROP TABLE IF EXISTS gold_inventory_summary;
DROP TABLE IF EXISTS gold_returns_summary;
DROP TABLE IF EXISTS gold_low_sales_products;

CREATE TABLE gold_monthly_sales AS SELECT * FROM analytics_monthly_sales;
CREATE TABLE gold_customer_summary AS SELECT * FROM analytics_customer_summary;
CREATE TABLE gold_product_summary AS SELECT * FROM analytics_product_summary;
CREATE TABLE gold_store_summary AS SELECT * FROM analytics_store_summary;
CREATE TABLE gold_inventory_summary AS SELECT * FROM analytics_inventory_summary;
CREATE TABLE gold_returns_summary AS SELECT * FROM analytics_returns_summary;
CREATE TABLE gold_low_sales_products AS SELECT * FROM analytics_low_sales_products;
