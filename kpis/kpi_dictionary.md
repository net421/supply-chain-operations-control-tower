# Supply Chain KPI Dictionary

This dictionary defines the synthetic control tower KPIs used in the SQL and Python artifacts. The examples are lab evidence, not production metric ownership.

| KPI | Formula | Grain | Business Use | Validation / Review Note |
|---|---|---|---|---|
| OTIF | Orders where `units_shipped >= units_ordered` and `delivery_date <= promised_date` / total orders | Order | Service reliability | Requires ERP order quantities joined to TMS delivery dates. |
| Fill Rate | `sum(units_shipped) / sum(units_ordered)` | Portfolio, customer, SKU, warehouse | Demand fulfillment | Units shipped cannot exceed units ordered. |
| Service Level | Orders delivered by promised date / total orders | Order | Customer promise reliability | Less strict than OTIF because it ignores partial fills. |
| Backorder Units | `sum(greatest(units_ordered - units_shipped, 0))` | Order, SKU, warehouse | Service gap and inventory triage | Backorders should route to exception queue. |
| Stockout / Reorder Risk | SKU-location rows where `on_hand_units <= 0` or `on_hand_units < reorder_point_units` | SKU + warehouse | Availability risk | WMS inventory grain must be unique by SKU and warehouse. |
| Days of Inventory | `on_hand_units / average_daily_demand` | SKU + warehouse | Stock coverage | Demand of zero needs guarded division. |
| Lead Time | `delivery_date - order_date` | Order | Responsiveness | Delivery date cannot precede ship date or order date. |
| Inventory Turnover 90d | `trailing_90d_cogs / average_inventory_value` | SKU + warehouse or portfolio | Inventory efficiency | Average inventory value must be positive. |
| Freight Cost Per Shipped Unit | `sum(freight_cost) / sum(units_shipped)` | Carrier, order, portfolio | Logistics cost control | Orders with no shipped units should not divide by zero. |
| Exception Priority | High when no units ship or backorders overlap stockout risk; medium for late/partial orders; monitor for inventory risk only | Order | Operational triage | Used by the dashboard exception queue. |

## Hiring Manager Readout

The artifact proves the ability to define operational KPIs, join ERP/WMS/TMS concepts, guard metric math, and document assumptions clearly enough for BI review.
