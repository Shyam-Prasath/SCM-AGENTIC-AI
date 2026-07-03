-- SQLite quick-start queries for the ShopSphere SCM capstone
-- Run:  sqlite3 scm.sqlite < sample_queries.sql   (or paste individually)

-- UC-1  Which SKUs are below reorder level in the North warehouse?
SELECT i.sku, p.product_name, i.warehouse, i.on_hand, i.reorder_point, i.reorder_qty
FROM inventory i JOIN products p ON p.sku = i.sku
WHERE i.region = 'North' AND i.on_hand < i.reorder_point
ORDER BY (i.reorder_point - i.on_hand) DESC;

-- UC-2  Replenishment candidates network-wide (low stock) with cheapest supplier & PO value
SELECT i.sku, i.warehouse, i.on_hand, i.reorder_point, i.reorder_qty,
       MIN(c.unit_cost)                         AS best_unit_cost,
       ROUND(i.reorder_qty * MIN(c.unit_cost),2) AS est_po_value
FROM inventory i
JOIN supplier_catalog c ON c.sku = i.sku
WHERE i.on_hand < i.reorder_point
GROUP BY i.sku, i.warehouse
ORDER BY est_po_value DESC;   -- values > 10000 must go through human approval

-- Supplier options for a given SKU (procurement decision)
SELECT c.supplier_id, s.supplier_name, s.reliability_score, s.lead_time_status,
       c.unit_cost, c.moq, c.lead_time_days, c.available_qty
FROM supplier_catalog c JOIN suppliers s ON s.supplier_id = c.supplier_id
WHERE c.sku = 'ELC-1009'
ORDER BY c.unit_cost;

-- Recent demand (last 14 days) for a SKU -> feed the forecast tool
SELECT date, units_sold FROM sales_history
WHERE sku = 'ELC-1001' AND date >= date('2026-07-01','-14 day')
ORDER BY date;

-- 30-day average daily demand per SKU (simple baseline forecast input)
SELECT sku, ROUND(AVG(units_sold),2) AS avg_daily_30d
FROM sales_history
WHERE date >= date('2026-07-01','-30 day')
GROUP BY sku ORDER BY avg_daily_30d DESC;

-- UC-3  Pending orders needing a shipping plan, with carrier options for their region
SELECT o.order_id, o.sku, o.qty, o.ship_to_region, o.promised_date, p.weight_kg
FROM orders o JOIN products p ON p.sku = o.sku
WHERE o.status = 'Pending'
ORDER BY o.promised_date;

-- UC-4  Orders at delay risk (SKUs sourced from the delayed supplier SUP-02)
SELECT DISTINCT o.order_id, o.sku, o.status, o.promised_date, s.lead_time_status
FROM orders o
JOIN supplier_catalog c ON c.sku = o.sku
JOIN suppliers s ON s.supplier_id = c.supplier_id
WHERE s.supplier_id = 'SUP-02' AND o.status IN ('Pending','Allocated');

-- UC-5  Constrained SKU: reorder need vs max supplier availability
SELECT i.sku, i.warehouse, i.reorder_qty, MAX(c.available_qty) AS max_available
FROM inventory i JOIN supplier_catalog c ON c.sku = i.sku
WHERE i.sku = 'ELC-1005'
GROUP BY i.sku, i.warehouse;   -- reorder_qty > max_available => escalate to human
