CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS marts;

DROP TABLE IF EXISTS warehouse.dim_customer CASCADE;
CREATE TABLE warehouse.dim_customer AS
SELECT customer_id, first_name, last_name, gender, birth_year, country,
       COALESCE(NULLIF(city, ''), 'Unknown') AS city, region,
       acquisition_channel, loyalty_tier, registration_date::date,
       email, COUNT(*) OVER (PARTITION BY email) > 1 AS shared_email_flag
FROM staging.customers_raw;
ALTER TABLE warehouse.dim_customer ADD PRIMARY KEY (customer_id);

DROP TABLE IF EXISTS warehouse.dim_product CASCADE;
CREATE TABLE warehouse.dim_product AS SELECT * FROM staging.products;
ALTER TABLE warehouse.dim_product ADD PRIMARY KEY (product_id);

DROP TABLE IF EXISTS warehouse.dim_store CASCADE;
CREATE TABLE warehouse.dim_store AS SELECT * FROM staging.stores;
ALTER TABLE warehouse.dim_store ADD PRIMARY KEY (store_id);

DROP TABLE IF EXISTS warehouse.fact_order CASCADE;
CREATE TABLE warehouse.fact_order AS
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY order_date) AS rn
  FROM staging.orders_raw
) x WHERE rn = 1;
ALTER TABLE warehouse.fact_order DROP COLUMN rn;
ALTER TABLE warehouse.fact_order ADD PRIMARY KEY (order_id);

DROP TABLE IF EXISTS warehouse.fact_order_item CASCADE;
CREATE TABLE warehouse.fact_order_item AS
SELECT i.*, ROUND((i.quantity * i.unit_price_eur * (1-i.discount_pct))::numeric, 2) AS recalculated_line_net_eur,
       ABS(i.line_net_amount_eur - i.quantity*i.unit_price_eur*(1-i.discount_pct)) > 0.02 AS reconciliation_flag
FROM staging.order_items_raw i
JOIN warehouse.fact_order o USING (order_id)
WHERE i.quantity > 0;
ALTER TABLE warehouse.fact_order_item ADD PRIMARY KEY (order_item_id);

DROP TABLE IF EXISTS marts.monthly_kpi;
CREATE TABLE marts.monthly_kpi AS
SELECT DATE_TRUNC('month', o.order_date::date)::date AS month,
       o.country, o.sales_channel,
       COUNT(DISTINCT o.order_id)::bigint AS orders,
       COUNT(DISTINCT NULLIF(o.customer_id,''))::bigint AS customers,
       ROUND(SUM(i.recalculated_line_net_eur)::numeric,2) AS revenue_eur,
       ROUND(SUM(i.quantity*p.unit_cost_eur)::numeric,2) AS cost_eur,
       ROUND((1-SUM(i.quantity*p.unit_cost_eur)/NULLIF(SUM(i.recalculated_line_net_eur),0))::numeric*100,2)::float8 AS gross_margin_pct,
       ROUND((SUM(i.recalculated_line_net_eur)/COUNT(DISTINCT o.order_id))::numeric,2)::float8 AS average_order_value_eur
FROM warehouse.fact_order o
JOIN warehouse.fact_order_item i USING (order_id)
JOIN warehouse.dim_product p USING (product_id)
WHERE o.order_status IN ('completed','refunded')
GROUP BY 1,2,3;

CREATE INDEX IF NOT EXISTS idx_fact_order_date ON warehouse.fact_order(order_date);
CREATE INDEX IF NOT EXISTS idx_fact_item_order ON warehouse.fact_order_item(order_id);

