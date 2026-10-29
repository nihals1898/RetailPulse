-- Business-ready summaries for common retail questions.
DROP TABLE IF EXISTS analytics_monthly_sales;
DROP TABLE IF EXISTS analytics_customer_summary;
DROP TABLE IF EXISTS analytics_product_summary;
DROP TABLE IF EXISTS analytics_store_summary;
DROP TABLE IF EXISTS analytics_inventory_summary;
DROP TABLE IF EXISTS analytics_returns_summary;
DROP TABLE IF EXISTS analytics_low_sales_products;

CREATE TABLE analytics_monthly_sales AS
WITH gross_sales AS (
    SELECT
        STRFTIME('%Y-%m', o.order_date) AS sales_month,
        p.category,
        o.sales_channel,
        COUNT(DISTINCT o.order_id) AS total_orders,
        SUM(oi.quantity) AS units_sold,
        ROUND(SUM(oi.line_total), 2) AS gross_revenue
    FROM clean_orders AS o
    JOIN clean_order_items AS oi ON oi.order_id = o.order_id
    JOIN clean_products AS p ON p.product_id = oi.product_id
    WHERE o.order_status = 'completed'
    GROUP BY STRFTIME('%Y-%m', o.order_date), p.category, o.sales_channel
),
refunds AS (
    SELECT
        STRFTIME('%Y-%m', r.return_date) AS return_month,
        p.category,
        ROUND(SUM(r.refund_amount), 2) AS refunds
    FROM clean_returns AS r
    JOIN clean_products AS p ON p.product_id = r.product_id
    GROUP BY STRFTIME('%Y-%m', r.return_date), p.category
),
with_returns AS (
    SELECT g.*, COALESCE(r.refunds, 0) AS refunds,
           ROUND(g.gross_revenue - COALESCE(r.refunds, 0), 2) AS net_revenue
    FROM gross_sales AS g
    LEFT JOIN refunds AS r
      ON r.return_month = g.sales_month AND r.category = g.category
),
with_previous_month AS (
    SELECT *, LAG(gross_revenue) OVER (
        PARTITION BY category, sales_channel ORDER BY sales_month
    ) AS previous_month_revenue
    FROM with_returns
)
SELECT sales_month, category, sales_channel, total_orders, units_sold,
       gross_revenue, refunds, net_revenue, previous_month_revenue,
       CASE WHEN previous_month_revenue IS NULL OR previous_month_revenue = 0
            THEN NULL
            ELSE ROUND((gross_revenue - previous_month_revenue) / previous_month_revenue, 4)
       END AS revenue_growth_rate
FROM with_previous_month;

CREATE TABLE analytics_customer_summary AS
WITH customer_sales AS (
    SELECT o.customer_id,
           COUNT(DISTINCT o.order_id) AS completed_orders,
           ROUND(SUM(oi.line_total), 2) AS gross_revenue,
           MAX(o.order_date) AS last_order_date
    FROM clean_orders AS o
    JOIN clean_order_items AS oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'completed'
    GROUP BY o.customer_id
),
customer_refunds AS (
    SELECT o.customer_id, ROUND(SUM(r.refund_amount), 2) AS refunds
    FROM clean_returns AS r
    JOIN clean_orders AS o ON o.order_id = r.order_id
    GROUP BY o.customer_id
),
customer_value AS (
    SELECT c.customer_id, c.first_name, c.last_name, c.loyalty_tier,
           COALESCE(s.completed_orders, 0) AS completed_orders,
           COALESCE(s.gross_revenue, 0) AS gross_revenue,
           COALESCE(r.refunds, 0) AS refunds,
           ROUND(COALESCE(s.gross_revenue, 0) - COALESCE(r.refunds, 0), 2) AS net_revenue,
           s.last_order_date,
           CASE WHEN s.last_order_date >= DATE((SELECT as_of_date FROM pipeline_config), '-365 days')
                THEN 1 ELSE 0 END AS is_active_customer
    FROM clean_customers AS c
    LEFT JOIN customer_sales AS s ON s.customer_id = c.customer_id
    LEFT JOIN customer_refunds AS r ON r.customer_id = c.customer_id
)
SELECT *, RANK() OVER (ORDER BY net_revenue DESC) AS revenue_rank
FROM customer_value;

CREATE TABLE analytics_product_summary AS
WITH sales AS (
    SELECT oi.product_id,
           SUM(oi.quantity) AS units_sold,
           ROUND(SUM(oi.line_total), 2) AS gross_revenue,
           COUNT(DISTINCT o.order_id) AS order_count
    FROM clean_order_items AS oi
    JOIN clean_orders AS o ON o.order_id = oi.order_id
    WHERE o.order_status = 'completed'
    GROUP BY oi.product_id
),
returns AS (
    SELECT product_id, SUM(return_quantity) AS units_returned,
           ROUND(SUM(refund_amount), 2) AS refunds
    FROM clean_returns
    GROUP BY product_id
)
SELECT p.product_id, p.sku, p.product_name, p.category, p.brand,
       COALESCE(s.units_sold, 0) AS units_sold,
       COALESCE(s.order_count, 0) AS order_count,
       COALESCE(s.gross_revenue, 0) AS gross_revenue,
       COALESCE(r.units_returned, 0) AS units_returned,
       COALESCE(r.refunds, 0) AS refunds,
       CASE WHEN COALESCE(s.units_sold, 0) = 0 THEN 0.0
            ELSE ROUND(1.0 * COALESCE(r.units_returned, 0) / s.units_sold, 4)
       END AS unit_return_rate
FROM clean_products AS p
LEFT JOIN sales AS s ON s.product_id = p.product_id
LEFT JOIN returns AS r ON r.product_id = p.product_id;

CREATE TABLE analytics_store_summary AS
WITH sales AS (
    SELECT o.store_id,
           COUNT(DISTINCT o.order_id) AS completed_orders,
           ROUND(SUM(oi.line_total), 2) AS gross_revenue
    FROM clean_orders AS o
    JOIN clean_order_items AS oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'completed'
    GROUP BY o.store_id
),
returns AS (
    SELECT o.store_id, COUNT(DISTINCT r.return_id) AS return_count,
           ROUND(SUM(r.refund_amount), 2) AS refunds
    FROM clean_returns AS r
    JOIN clean_orders AS o ON o.order_id = r.order_id
    GROUP BY o.store_id
)
SELECT s.store_id, s.store_name, s.city, s.region,
       COALESCE(sales.completed_orders, 0) AS completed_orders,
       COALESCE(sales.gross_revenue, 0) AS gross_revenue,
       CASE WHEN COALESCE(sales.completed_orders, 0) = 0 THEN 0.0
            ELSE ROUND(sales.gross_revenue / sales.completed_orders, 2)
       END AS average_order_value,
       COALESCE(returns.return_count, 0) AS return_count,
       COALESCE(returns.refunds, 0) AS refunds
FROM clean_stores AS s
LEFT JOIN sales ON sales.store_id = s.store_id
LEFT JOIN returns ON returns.store_id = s.store_id;

CREATE TABLE analytics_inventory_summary AS
WITH ranked_snapshots AS (
    SELECT i.*,
           ROW_NUMBER() OVER (
               PARTITION BY i.product_id, i.store_id ORDER BY i.snapshot_date DESC
           ) AS snapshot_rank
    FROM clean_inventory AS i
),
latest_inventory AS (
    SELECT * FROM ranked_snapshots WHERE snapshot_rank = 1
)
SELECT s.store_id, s.store_name, p.category,
       COUNT(*) AS product_locations,
       SUM(i.on_hand_quantity) AS units_on_hand,
       ROUND(SUM(i.inventory_value), 2) AS inventory_value
FROM latest_inventory AS i
JOIN clean_stores AS s ON s.store_id = i.store_id
JOIN clean_products AS p ON p.product_id = i.product_id
GROUP BY s.store_id, s.store_name, p.category;

CREATE TABLE analytics_returns_summary AS
SELECT STRFTIME('%Y-%m', r.return_date) AS return_month,
       r.return_reason,
       p.category,
       s.store_id,
       s.store_name,
       COUNT(*) AS return_events,
       SUM(r.return_quantity) AS units_returned,
       ROUND(SUM(r.refund_amount), 2) AS refund_amount
FROM clean_returns AS r
JOIN clean_products AS p ON p.product_id = r.product_id
JOIN clean_orders AS o ON o.order_id = r.order_id
JOIN clean_stores AS s ON s.store_id = o.store_id
GROUP BY STRFTIME('%Y-%m', r.return_date), r.return_reason,
         p.category, s.store_id, s.store_name;

CREATE TABLE analytics_low_sales_products AS
WITH product_units AS (
    SELECT p.product_id, p.product_name, p.category,
           COALESCE(SUM(CASE WHEN o.order_id IS NOT NULL THEN oi.quantity ELSE 0 END), 0) AS units_sold
    FROM clean_products AS p
    LEFT JOIN clean_order_items AS oi ON oi.product_id = p.product_id
    LEFT JOIN clean_orders AS o
      ON o.order_id = oi.order_id AND o.order_status = 'completed'
    GROUP BY p.product_id, p.product_name, p.category
),
average_sales AS (
    SELECT AVG(units_sold) AS mean_units_sold FROM product_units
)
SELECT u.product_id, u.product_name, u.category, u.units_sold,
       ROUND(a.mean_units_sold, 2) AS catalog_average_units_sold
FROM product_units AS u
CROSS JOIN average_sales AS a
GROUP BY u.product_id, u.product_name, u.category, u.units_sold, a.mean_units_sold
HAVING u.units_sold < a.mean_units_sold;
