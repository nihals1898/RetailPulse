-- Build a local star schema from the Phase 5 clean tables.
-- Facts are dropped before dimensions because they reference the dimensions.
DROP TABLE IF EXISTS fact_returns;
DROP TABLE IF EXISTS fact_inventory;
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_store;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_customer (
    customer_key INTEGER PRIMARY KEY,
    customer_id TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    signup_date TEXT NOT NULL,
    birth_date TEXT,
    city TEXT,
    region TEXT,
    loyalty_tier TEXT
);

INSERT INTO dim_customer (
    customer_key, customer_id, first_name, last_name, email, phone,
    signup_date, birth_date, city, region, loyalty_tier
)
SELECT ROW_NUMBER() OVER (ORDER BY customer_id), customer_id, first_name,
       last_name, email, phone, signup_date, birth_date, city, region, loyalty_tier
FROM clean_customers;

CREATE TABLE dim_product (
    product_key INTEGER PRIMARY KEY,
    product_id TEXT NOT NULL UNIQUE,
    sku TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    brand TEXT,
    unit_cost REAL NOT NULL,
    list_price REAL NOT NULL,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
);

INSERT INTO dim_product (
    product_key, product_id, sku, product_name, category, subcategory,
    brand, unit_cost, list_price, is_active
)
SELECT ROW_NUMBER() OVER (ORDER BY product_id), product_id, sku, product_name,
       category, subcategory, brand, unit_cost, list_price,
       CASE WHEN is_active = 'true' THEN 1 ELSE 0 END
FROM clean_products;

CREATE TABLE dim_store (
    store_key INTEGER PRIMARY KEY,
    store_id TEXT NOT NULL UNIQUE,
    store_name TEXT NOT NULL,
    store_type TEXT,
    city TEXT,
    region TEXT,
    country TEXT NOT NULL,
    opened_date TEXT NOT NULL
);

INSERT INTO dim_store (
    store_key, store_id, store_name, store_type, city, region, country, opened_date
)
SELECT ROW_NUMBER() OVER (ORDER BY store_id), store_id, store_name, store_type,
       city, region, country, opened_date
FROM clean_stores;

CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    date_value TEXT UNIQUE,
    calendar_year INTEGER,
    calendar_quarter INTEGER,
    month_number INTEGER,
    month_name TEXT,
    year_month TEXT,
    day_of_month INTEGER,
    day_of_week_number INTEGER,
    day_name TEXT,
    is_weekend INTEGER,
    is_as_of_date INTEGER
);

INSERT INTO dim_date (date_key, date_value)
VALUES (0, NULL);

WITH RECURSIVE
event_dates(date_value) AS (
    SELECT order_date FROM clean_orders
    UNION ALL SELECT return_date FROM clean_returns
    UNION ALL SELECT snapshot_date FROM clean_inventory
    UNION ALL SELECT as_of_date FROM pipeline_config
),
bounds AS (
    SELECT COALESCE(MIN(date_value), (SELECT as_of_date FROM pipeline_config)) AS min_date,
           MAX(COALESCE(MAX(date_value), (SELECT as_of_date FROM pipeline_config)),
               (SELECT as_of_date FROM pipeline_config)) AS max_date
    FROM event_dates
),
calendar(date_value) AS (
    SELECT min_date FROM bounds
    UNION ALL
    SELECT DATE(calendar.date_value, '+1 day')
    FROM calendar CROSS JOIN bounds
    WHERE calendar.date_value < bounds.max_date
)
INSERT INTO dim_date (
    date_key, date_value, calendar_year, calendar_quarter, month_number,
    month_name, year_month, day_of_month, day_of_week_number, day_name,
    is_weekend, is_as_of_date
)
SELECT CAST(STRFTIME('%Y%m%d', calendar.date_value) AS INTEGER),
       calendar.date_value,
       CAST(STRFTIME('%Y', calendar.date_value) AS INTEGER),
       CAST((CAST(STRFTIME('%m', calendar.date_value) AS INTEGER) + 2) / 3 AS INTEGER),
       CAST(STRFTIME('%m', calendar.date_value) AS INTEGER),
       CASE STRFTIME('%m', calendar.date_value)
           WHEN '01' THEN 'January' WHEN '02' THEN 'February' WHEN '03' THEN 'March'
           WHEN '04' THEN 'April' WHEN '05' THEN 'May' WHEN '06' THEN 'June'
           WHEN '07' THEN 'July' WHEN '08' THEN 'August' WHEN '09' THEN 'September'
           WHEN '10' THEN 'October' WHEN '11' THEN 'November' WHEN '12' THEN 'December'
       END,
       STRFTIME('%Y-%m', calendar.date_value),
       CAST(STRFTIME('%d', calendar.date_value) AS INTEGER),
       CAST(STRFTIME('%w', calendar.date_value) AS INTEGER),
       CASE STRFTIME('%w', calendar.date_value)
           WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday'
           WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday'
           WHEN '6' THEN 'Saturday'
       END,
       CASE WHEN STRFTIME('%w', calendar.date_value) IN ('0', '6') THEN 1 ELSE 0 END,
       CASE WHEN calendar.date_value = (SELECT as_of_date FROM pipeline_config) THEN 1 ELSE 0 END
FROM calendar;

CREATE TABLE fact_sales (
    sales_key INTEGER PRIMARY KEY,
    order_id TEXT NOT NULL,
    order_item_id TEXT NOT NULL UNIQUE,
    order_status TEXT NOT NULL,
    order_date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    customer_key INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    product_key INTEGER NOT NULL REFERENCES dim_product(product_key),
    store_key INTEGER NOT NULL REFERENCES dim_store(store_key),
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    gross_line_amount REAL NOT NULL,
    discount_amount REAL NOT NULL,
    net_sales_amount REAL NOT NULL
);

INSERT INTO fact_sales (
    sales_key, order_id, order_item_id, order_status, order_date_key,
    customer_key, product_key, store_key, quantity, unit_price,
    gross_line_amount, discount_amount, net_sales_amount
)
SELECT ROW_NUMBER() OVER (ORDER BY oi.order_item_id),
       o.order_id, oi.order_item_id, o.order_status, d.date_key,
       dc.customer_key, dp.product_key, ds.store_key,
       oi.quantity, oi.unit_price,
       ROUND(oi.quantity * oi.unit_price, 2),
       oi.discount_amount, oi.line_total
FROM clean_order_items AS oi
JOIN clean_orders AS o ON o.order_id = oi.order_id
JOIN dim_date AS d ON d.date_value = o.order_date
JOIN dim_customer AS dc ON dc.customer_id = o.customer_id
JOIN dim_product AS dp ON dp.product_id = oi.product_id
JOIN dim_store AS ds ON ds.store_id = o.store_id;

CREATE TABLE fact_returns (
    return_fact_key INTEGER PRIMARY KEY,
    return_id TEXT NOT NULL UNIQUE,
    order_id TEXT NOT NULL,
    order_item_id TEXT NOT NULL,
    order_date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    return_date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    customer_key INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    product_key INTEGER NOT NULL REFERENCES dim_product(product_key),
    store_key INTEGER NOT NULL REFERENCES dim_store(store_key),
    return_quantity INTEGER NOT NULL,
    refund_amount REAL NOT NULL,
    return_reason TEXT NOT NULL,
    return_status TEXT NOT NULL
);

INSERT INTO fact_returns (
    return_fact_key, return_id, order_id, order_item_id, order_date_key,
    return_date_key, customer_key, product_key, store_key,
    return_quantity, refund_amount, return_reason, return_status
)
SELECT ROW_NUMBER() OVER (ORDER BY r.return_id),
       r.return_id, r.order_id, r.order_item_id, fs.order_date_key,
       return_date.date_key, fs.customer_key, fs.product_key, fs.store_key,
       r.return_quantity, r.refund_amount, r.return_reason, r.return_status
FROM clean_returns AS r
JOIN fact_sales AS fs ON fs.order_item_id = r.order_item_id
JOIN dim_date AS return_date ON return_date.date_value = r.return_date;

CREATE TABLE fact_inventory (
    inventory_fact_key INTEGER PRIMARY KEY,
    inventory_id TEXT NOT NULL UNIQUE,
    snapshot_date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    product_key INTEGER NOT NULL REFERENCES dim_product(product_key),
    store_key INTEGER NOT NULL REFERENCES dim_store(store_key),
    on_hand_quantity INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    inventory_value REAL NOT NULL,
    UNIQUE (snapshot_date_key, product_key, store_key)
);

INSERT INTO fact_inventory (
    inventory_fact_key, inventory_id, snapshot_date_key, product_key,
    store_key, on_hand_quantity, unit_cost, inventory_value
)
SELECT ROW_NUMBER() OVER (ORDER BY i.snapshot_date, i.product_id, i.store_id),
       i.inventory_id, d.date_key, p.product_key, s.store_key,
       i.on_hand_quantity, i.unit_cost, i.inventory_value
FROM clean_inventory AS i
JOIN dim_date AS d ON d.date_value = i.snapshot_date
JOIN dim_product AS p ON p.product_id = i.product_id
JOIN dim_store AS s ON s.store_id = i.store_id;
