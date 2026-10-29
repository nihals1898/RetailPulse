-- Clean tables apply the documented Phase 5 SQL rules to staging data.
DROP TABLE IF EXISTS clean_customers;
DROP TABLE IF EXISTS clean_products;
DROP TABLE IF EXISTS clean_stores;
DROP TABLE IF EXISTS clean_orders;
DROP TABLE IF EXISTS clean_order_items;
DROP TABLE IF EXISTS clean_payments;
DROP TABLE IF EXISTS clean_inventory;
DROP TABLE IF EXISTS clean_returns;

CREATE TABLE clean_customers AS
WITH normalized AS (
    SELECT
        TRIM(customer_id) AS customer_id,
        TRIM(first_name) AS first_name,
        TRIM(last_name) AS last_name,
        LOWER(TRIM(email)) AS email,
        TRIM(phone) AS phone,
        DATE(signup_date) AS signup_date,
        DATE(birth_date) AS birth_date,
        TRIM(city) AS city,
        TRIM(region) AS region,
        LOWER(TRIM(loyalty_tier)) AS loyalty_tier,
        ROW_NUMBER() OVER (
            PARTITION BY TRIM(customer_id)
            ORDER BY DATE(signup_date) DESC, LOWER(TRIM(email))
        ) AS record_rank
    FROM stg_customers
    WHERE NULLIF(TRIM(customer_id), '') IS NOT NULL
      AND NULLIF(TRIM(first_name), '') IS NOT NULL
      AND NULLIF(TRIM(last_name), '') IS NOT NULL
      AND NULLIF(TRIM(email), '') IS NOT NULL
      AND INSTR(TRIM(email), '@') > 1
      AND INSTR(SUBSTR(TRIM(email), INSTR(TRIM(email), '@') + 1), '.') > 1
      AND NULLIF(TRIM(phone), '') IS NOT NULL
      AND LENGTH(REPLACE(REPLACE(REPLACE(TRIM(phone), '-', ''), ' ', ''), '+', '')) >= 7
      AND DATE(signup_date) IS NOT NULL
      AND DATE(signup_date) <= (SELECT as_of_date FROM pipeline_config)
      AND (birth_date = '' OR DATE(birth_date) IS NOT NULL)
      AND (birth_date = '' OR DATE(birth_date) <= (SELECT as_of_date FROM pipeline_config))
)
SELECT customer_id, first_name, last_name, email, phone, signup_date,
       birth_date, city, region, loyalty_tier
FROM normalized
WHERE record_rank = 1;

CREATE TABLE clean_products AS
WITH normalized AS (
    SELECT
        TRIM(product_id) AS product_id,
        TRIM(sku) AS sku,
        TRIM(product_name) AS product_name,
        CASE LOWER(TRIM(category))
            WHEN 'electronics' THEN 'Electronics'
            WHEN 'home and kitchen' THEN 'Home and Kitchen'
            WHEN 'home & kitchen' THEN 'Home and Kitchen'
            WHEN 'apparel' THEN 'Apparel'
            WHEN 'beauty' THEN 'Beauty'
            WHEN 'sports' THEN 'Sports'
            WHEN 'books' THEN 'Books'
            ELSE NULL
        END AS category,
        TRIM(subcategory) AS subcategory,
        TRIM(brand) AS brand,
        CAST(unit_cost AS REAL) AS unit_cost,
        CAST(list_price AS REAL) AS list_price,
        LOWER(TRIM(is_active)) AS is_active,
        ROW_NUMBER() OVER (
            PARTITION BY TRIM(product_id)
            ORDER BY TRIM(sku), TRIM(product_name)
        ) AS record_rank
    FROM stg_products
    WHERE NULLIF(TRIM(product_id), '') IS NOT NULL
      AND NULLIF(TRIM(sku), '') IS NOT NULL
      AND NULLIF(TRIM(product_name), '') IS NOT NULL
      AND CAST(unit_cost AS REAL) >= 0
      AND CAST(list_price AS REAL) >= 0
)
SELECT product_id, sku, product_name, category, subcategory, brand,
       unit_cost, list_price, is_active
FROM normalized
WHERE record_rank = 1 AND category IS NOT NULL;

CREATE TABLE clean_stores AS
WITH normalized AS (
    SELECT
        TRIM(store_id) AS store_id,
        TRIM(store_name) AS store_name,
        LOWER(TRIM(store_type)) AS store_type,
        TRIM(city) AS city,
        TRIM(region) AS region,
        UPPER(TRIM(country)) AS country,
        DATE(opened_date) AS opened_date,
        ROW_NUMBER() OVER (
            PARTITION BY TRIM(store_id)
            ORDER BY DATE(opened_date), TRIM(store_name)
        ) AS record_rank
    FROM stg_stores
    WHERE NULLIF(TRIM(store_id), '') IS NOT NULL
      AND NULLIF(TRIM(store_name), '') IS NOT NULL
      AND NULLIF(TRIM(country), '') IS NOT NULL
      AND DATE(opened_date) IS NOT NULL
      AND DATE(opened_date) <= (SELECT as_of_date FROM pipeline_config)
)
SELECT store_id, store_name, store_type, city, region, country, opened_date
FROM normalized
WHERE record_rank = 1;

CREATE TABLE clean_orders AS
WITH normalized AS (
    SELECT
        TRIM(order_id) AS order_id,
        TRIM(customer_id) AS customer_id,
        TRIM(store_id) AS store_id,
        LOWER(TRIM(sales_channel)) AS sales_channel,
        DATE(order_date) AS order_date,
        LOWER(TRIM(order_status)) AS order_status,
        UPPER(TRIM(currency)) AS currency,
        CAST(order_total AS REAL) AS order_total,
        ROW_NUMBER() OVER (
            PARTITION BY TRIM(order_id)
            ORDER BY DATE(order_date) DESC, CAST(order_total AS REAL) DESC
        ) AS record_rank
    FROM stg_orders
    WHERE NULLIF(TRIM(order_id), '') IS NOT NULL
      AND NULLIF(TRIM(customer_id), '') IS NOT NULL
      AND NULLIF(TRIM(store_id), '') IS NOT NULL
      AND DATE(order_date) IS NOT NULL
      AND DATE(order_date) <= (SELECT as_of_date FROM pipeline_config)
      AND CAST(order_total AS REAL) >= 0
      AND LOWER(TRIM(sales_channel)) IN ('online', 'store')
      AND LOWER(TRIM(order_status)) IN ('completed', 'pending', 'cancelled', 'partially_refunded')
      AND UPPER(TRIM(currency)) = 'EUR'
)
SELECT n.order_id, n.customer_id, n.store_id, n.sales_channel, n.order_date,
       n.order_status, n.currency, n.order_total
FROM normalized AS n
JOIN clean_customers AS c ON c.customer_id = n.customer_id
JOIN clean_stores AS s ON s.store_id = n.store_id
WHERE n.record_rank = 1;

CREATE TABLE clean_order_items AS
WITH normalized AS (
    SELECT
        TRIM(order_item_id) AS order_item_id,
        TRIM(order_id) AS order_id,
        CAST(line_number AS INTEGER) AS line_number,
        TRIM(product_id) AS product_id,
        CAST(quantity AS INTEGER) AS quantity,
        CAST(unit_price AS REAL) AS unit_price,
        CAST(discount_amount AS REAL) AS discount_amount,
        CAST(line_total AS REAL) AS line_total,
        ROW_NUMBER() OVER (
            PARTITION BY TRIM(order_item_id)
            ORDER BY TRIM(order_id), CAST(line_number AS INTEGER)
        ) AS record_rank
    FROM stg_order_items
    WHERE NULLIF(TRIM(order_item_id), '') IS NOT NULL
      AND NULLIF(TRIM(order_id), '') IS NOT NULL
      AND CAST(line_number AS INTEGER) > 0
      AND NULLIF(TRIM(product_id), '') IS NOT NULL
      AND CAST(quantity AS INTEGER) > 0
      AND CAST(unit_price AS REAL) >= 0
      AND CAST(discount_amount AS REAL) >= 0
      AND CAST(discount_amount AS REAL) <= CAST(quantity AS INTEGER) * CAST(unit_price AS REAL)
      AND ABS(CAST(line_total AS REAL) - ROUND(
            CAST(quantity AS INTEGER) * CAST(unit_price AS REAL) - CAST(discount_amount AS REAL), 2
          )) <= 0.01
)
SELECT n.order_item_id, n.order_id, n.line_number, n.product_id, n.quantity,
       n.unit_price, n.discount_amount, n.line_total
FROM normalized AS n
JOIN clean_orders AS o ON o.order_id = n.order_id
JOIN clean_products AS p ON p.product_id = n.product_id
WHERE n.record_rank = 1;

CREATE TABLE clean_payments AS
WITH normalized AS (
    SELECT
        TRIM(payment_id) AS payment_id,
        TRIM(order_id) AS order_id,
        DATETIME(payment_date) AS payment_date,
        LOWER(TRIM(payment_method)) AS payment_method,
        LOWER(TRIM(payment_status)) AS payment_status,
        CAST(amount AS REAL) AS amount,
        ROW_NUMBER() OVER (
            PARTITION BY TRIM(payment_id)
            ORDER BY DATETIME(payment_date) DESC
        ) AS record_rank
    FROM stg_payments
    WHERE NULLIF(TRIM(payment_id), '') IS NOT NULL
      AND NULLIF(TRIM(order_id), '') IS NOT NULL
      AND DATETIME(payment_date) IS NOT NULL
      AND DATE(payment_date) <= (SELECT as_of_date FROM pipeline_config)
      AND LOWER(TRIM(payment_method)) IN ('credit_card', 'debit_card', 'gift_card', 'paypal', 'bank_transfer')
      AND LOWER(TRIM(payment_status)) IN ('captured', 'authorized', 'failed', 'refunded')
      AND CAST(amount AS REAL) >= 0
)
SELECT n.payment_id, n.order_id, n.payment_date, n.payment_method,
       n.payment_status, n.amount
FROM normalized AS n
JOIN clean_orders AS o ON o.order_id = n.order_id
WHERE n.record_rank = 1;

CREATE TABLE clean_inventory AS
WITH normalized AS (
    SELECT
        TRIM(inventory_id) AS inventory_id,
        TRIM(product_id) AS product_id,
        TRIM(store_id) AS store_id,
        DATE(snapshot_date) AS snapshot_date,
        CAST(on_hand_quantity AS INTEGER) AS on_hand_quantity,
        CAST(unit_cost AS REAL) AS unit_cost,
        CAST(inventory_value AS REAL) AS inventory_value,
        ROW_NUMBER() OVER (
            PARTITION BY TRIM(product_id), TRIM(store_id), DATE(snapshot_date)
            ORDER BY TRIM(inventory_id)
        ) AS grain_rank
    FROM stg_inventory
    WHERE NULLIF(TRIM(inventory_id), '') IS NOT NULL
      AND NULLIF(TRIM(product_id), '') IS NOT NULL
      AND NULLIF(TRIM(store_id), '') IS NOT NULL
      AND DATE(snapshot_date) IS NOT NULL
      AND DATE(snapshot_date) <= (SELECT as_of_date FROM pipeline_config)
      AND CAST(on_hand_quantity AS INTEGER) >= 0
      AND CAST(unit_cost AS REAL) >= 0
      AND ABS(CAST(inventory_value AS REAL) - ROUND(
            CAST(on_hand_quantity AS INTEGER) * CAST(unit_cost AS REAL), 2
          )) <= 0.01
)
SELECT n.inventory_id, n.product_id, n.store_id, n.snapshot_date,
       n.on_hand_quantity, n.unit_cost, n.inventory_value
FROM normalized AS n
JOIN clean_products AS p ON p.product_id = n.product_id
JOIN clean_stores AS s ON s.store_id = n.store_id
WHERE n.grain_rank = 1;

CREATE TABLE clean_returns AS
WITH normalized AS (
    SELECT
        TRIM(r.return_id) AS return_id,
        TRIM(r.order_id) AS order_id,
        TRIM(r.order_item_id) AS order_item_id,
        TRIM(r.product_id) AS product_id,
        DATE(r.return_date) AS return_date,
        CAST(r.return_quantity AS INTEGER) AS return_quantity,
        CAST(r.refund_amount AS REAL) AS refund_amount,
        LOWER(TRIM(r.return_reason)) AS return_reason,
        LOWER(TRIM(r.return_status)) AS return_status,
        ROW_NUMBER() OVER (
            PARTITION BY TRIM(r.return_id)
            ORDER BY DATE(r.return_date) DESC
        ) AS record_rank
    FROM stg_returns AS r
    JOIN clean_order_items AS oi
      ON oi.order_item_id = TRIM(r.order_item_id)
     AND oi.order_id = TRIM(r.order_id)
     AND oi.product_id = TRIM(r.product_id)
    WHERE NULLIF(TRIM(r.return_id), '') IS NOT NULL
      AND DATE(r.return_date) IS NOT NULL
      AND DATE(r.return_date) <= (SELECT as_of_date FROM pipeline_config)
      AND CAST(r.return_quantity AS INTEGER) > 0
      AND CAST(r.return_quantity AS INTEGER) <= oi.quantity
      AND CAST(r.refund_amount AS REAL) >= 0
      AND ABS(CAST(r.refund_amount AS REAL) - ROUND(
            oi.line_total * CAST(r.return_quantity AS INTEGER) / oi.quantity, 2
          )) <= 0.01
      AND LOWER(TRIM(r.return_status)) IN ('approved', 'received', 'refunded')
)
SELECT return_id, order_id, order_item_id, product_id, return_date,
       return_quantity, refund_amount, return_reason, return_status
FROM normalized
WHERE record_rank = 1;
