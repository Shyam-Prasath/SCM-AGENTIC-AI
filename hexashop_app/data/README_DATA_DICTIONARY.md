# HexaShop SCM — Capstone Dataset (Pre-Processed)

Clean, interlinked sample data for the **Agentic AI for Supply Chain Management** capstone. Everything is already cleaned and consistent: SKUs, supplier IDs, customer IDs, and warehouses match across every file, dates are ISO-formatted, there are no missing values, and the numbers are internally coherent (reorder points are derived from real demand, PO values from real supplier costs). Reference date for all data is **2 July 2026**; sales history covers the prior 90 days.

## Files

| File | Format | Rows | Feeds tool |
|---|---|---|---|
| `products.csv` | CSV | 36 | product catalog lookups |
| `inventory.csv` | CSV | 67 | `inventory_db` |
| `sales_history.csv` | CSV | 3,240 | `forecast_model` |
| `suppliers.csv` | CSV | 8 | `supplier_api` |
| `supplier_catalog.csv` / `.json` | CSV + JSON | 93 | `supplier_api` |
| `carriers.csv` / `.json` | CSV + JSON | 5 | `shipping_api` |
| `customers.csv` | CSV | 25 | `notify_tool` |
| `orders.csv` | CSV | 60 | order/fulfilment logic |
| `scm.sqlite` | SQLite | all 8 tables | drop-in DB for `inventory_db` |
| `sample_queries.sql` | SQL | — | ready-made queries per use case |

You can use the CSVs, the JSON files, or the single **`scm.sqlite`** database — whichever your tool implementation prefers. All three contain the same data.

## Schema & columns

**products** — `sku` (PK), `product_name`, `category` (Electronics / Fashion / Home), `subcategory`, `brand`, `unit_price` (retail, USD), `weight_kg` (for shipping cost).

**inventory** — one row per SKU per warehouse. `sku`, `warehouse` (North DC / South DC / West DC), `region` (North / South / West), `on_hand`, `safety_stock`, `reorder_point`, `reorder_qty`, `last_restock_date`. **Rule:** replenishment is needed when `on_hand < reorder_point`.

**sales_history** — daily units sold per SKU for 90 days. `date`, `sku`, `units_sold`. Contains a mild trend, weekend seasonality, and a few promo spikes so forecasting is non-trivial.

**suppliers** — `supplier_id` (PK), `supplier_name`, `country`, `specialty`, `reliability_score` (0–1), `on_time_rate`, `payment_terms`, `lead_time_status`. Note **SUP-02 is flagged `Delayed +6d`** — its lead times are currently slipping.

**supplier_catalog** — which supplier sells which SKU, and on what terms. `supplier_id`, `sku`, `unit_cost` (USD), `moq` (min order qty), `lead_time_days`, `available_qty`. Every SKU has 2–3 supplier options so the procurement agent has a real choice.

**carriers** — `carrier_id`, `carrier_name`, `service_level`, `base_cost`, `cost_per_kg`, `eta_days`, `regions_covered`, `reliability`. Shipping cost ≈ `base_cost + cost_per_kg × weight_kg × qty`. Note carriers differ on cost, speed, and coverage.

**customers** — `customer_id` (PK), `customer_name`, `email`, `region`, `tier` (Standard / Premium).

**orders** — `order_id` (PK), `customer_id` (FK), `sku` (FK), `qty`, `order_date`, `promised_date`, `ship_to_region`, `status` (Pending / Allocated / Shipped / Delivered). 27 orders are `Pending`.

## Scenarios deliberately built into the data

The dataset is seeded so each use case has something real to act on:

- **UC-1 (Inventory Q&A):** exactly **7 SKUs sit below reorder point in the North warehouse** (e.g. ELC-1009 Noise-Cancelling Headphones: 16 on hand vs 59 reorder point). A grounded single agent should return this list.
- **UC-2 (Auto-replenishment + Human-in-the-Loop):** several replenishment POs exceed a **$10,000 approval threshold** — ELC-1001 ≈ \$18.7k, ELC-1003 ≈ \$16.1k, ELC-1009 ≈ \$12.8k, ELC-1005 ≈ \$12.1k, HOM-3004 ≈ \$11.7k. These must pause for human approval; smaller POs can auto-place.
- **UC-3 (Logistics):** 27 pending orders across three regions, with 5 carriers that trade off cost vs ETA vs coverage (e.g. PrimeCarrier is fastest but doesn't serve the South region).
- **UC-4 (Delay handling):** **SUP-02's lead time has slipped +6 days**, putting ~11 pending/allocated orders on SKUs it supplies at delay risk. The Comms agent should draft proactive notifications.
- **UC-5 (Escalation):** **ELC-1005 (Smartwatch)** needs 175 units but no single supplier has more than 120 available and MOQs run up to 250 — no clean fulfilment exists, so the agent should escalate to a human with options.

## Suggested tool → data mapping

- `inventory_db(sku?, warehouse?)` → query `inventory` (+ join `products`). Use `scm.sqlite` for zero setup.
- `forecast_model(sku, days)` → aggregate `sales_history`; a 7- or 30-day moving average is a fine baseline.
- `supplier_api.get_quotes(sku)` → filter `supplier_catalog` + `suppliers`; `place_po(...)` just returns a mock confirmation.
- `shipping_api.get_rates(region, weight, qty)` → filter `carriers` by coverage, compute cost & ETA.
- `notify_tool(customer_id, message)` → look up `customers`, return a mock "sent".

## Quick start

```python
import sqlite3, pandas as pd
con = sqlite3.connect("scm.sqlite")
low = pd.read_sql("""
  SELECT sku, warehouse, on_hand, reorder_point, reorder_qty
  FROM inventory WHERE region='North' AND on_hand < reorder_point
  ORDER BY (reorder_point - on_hand) DESC
""", con)
print(low)   # <- your UC-1 answer, straight from the tool
```

See `sample_queries.sql` for one ready-made query per use case (UC-1 through UC-5).

## Notes for trainees

- Treat all external systems (`supplier_api`, `shipping_api`, `notify_tool`) as **mocked** — read from these files, return canned confirmations. Nothing hits a live system.
- Don't hard-code the answers. The point is that your **agents + tools** discover these facts from the data at runtime.
- The `$10,000` approval threshold and the low-stock set are intentionally easy to hit so your human-in-the-loop gate actually fires during the demo.
