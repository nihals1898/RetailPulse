-- Read these statements after running run_sql.py. Each query demonstrates a SQL feature.

-- SELECT, filtering, and sorting.
SELECT order_id, order_date, order_status, order_total
FROM clean_orders
WHERE order_status = 'completed'
ORDER BY order_date DESC
LIMIT 10;

-- INNER JOIN and GROUP BY: revenue by product category.
SELECT p.category, ROUND(SUM(oi.line_total), 2) AS revenue
FROM clean_order_items AS oi
JOIN clean_products AS p ON p.product_id = oi.product_id
GROUP BY p.category
ORDER BY revenue DESC;

-- LEFT JOIN and HAVING: categories with more than 100 returned units.
SELECT p.category, COALESCE(SUM(r.return_quantity), 0) AS units_returned
FROM clean_products AS p
LEFT JOIN clean_returns AS r ON r.product_id = p.product_id
GROUP BY p.category
HAVING COALESCE(SUM(r.return_quantity), 0) > 100;

-- CASE: map channel values to report-friendly labels.
WITH labeled_channels AS (
    SELECT CASE sales_channel
               WHEN 'online' THEN 'Digital'
               WHEN 'store' THEN 'Physical store'
               ELSE 'Other'
           END AS channel_label
    FROM clean_orders
    WHERE order_status = 'completed'
)
SELECT channel_label, COUNT(*) AS completed_orders
FROM labeled_channels
GROUP BY channel_label;

-- CTE and window function: compare category revenue with the prior month.
WITH monthly AS (
    SELECT STRFTIME('%Y-%m', o.order_date) AS sales_month,
           p.category,
           ROUND(SUM(oi.line_total), 2) AS revenue
    FROM clean_orders AS o
    JOIN clean_order_items AS oi ON oi.order_id = o.order_id
    JOIN clean_products AS p ON p.product_id = oi.product_id
    WHERE o.order_status = 'completed'
    GROUP BY STRFTIME('%Y-%m', o.order_date), p.category
),
with_prior AS (
    SELECT *, LAG(revenue) OVER (PARTITION BY category ORDER BY sales_month) AS prior_month_revenue
    FROM monthly
)
SELECT sales_month, category, revenue, prior_month_revenue,
       CASE WHEN prior_month_revenue IS NULL OR prior_month_revenue = 0 THEN NULL
            ELSE ROUND((revenue - prior_month_revenue) / prior_month_revenue, 4)
       END AS growth_rate
FROM with_prior
ORDER BY category, sales_month;

-- Date functions: monthly order counts and revenue.
SELECT STRFTIME('%Y-%m', order_date) AS order_month,
       COUNT(*) AS completed_orders,
       ROUND(SUM(order_total), 2) AS source_order_total
FROM clean_orders
WHERE order_status = 'completed'
GROUP BY STRFTIME('%Y-%m', order_date)
ORDER BY order_month;
