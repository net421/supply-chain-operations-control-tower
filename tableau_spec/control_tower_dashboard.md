# Tableau Control Tower Dashboard Spec

## Audience

Operations leaders, supply chain analysts, logistics managers and service-level owners.

## Dashboard Purpose

Give stakeholders one place to identify service failures, inventory risks, and freight-cost pressure without hiding the data quality checks behind the dashboard.

## Data Sources

- `erp_orders_sample.csv`: order promise dates, ordered units, shipped units, revenue, SKU, warehouse.
- `tms_shipments_sample.csv`: carrier, ship date, delivery date, freight cost, source on-time flag.
- `wms_inventory_sample.csv`: on-hand units, demand, reorder point, cost, COGS, average inventory value.

## KPI Tiles

| Tile | Calculation | Decision Supported |
| --- | --- | --- |
| OTIF Rate | Orders delivered on time and in full / total orders | Service reliability trend |
| Fill Rate | Units shipped / units ordered | Demand fulfillment |
| Service Level | Orders delivered by promised date / total orders | Promise reliability |
| Backorder Units | Ordered units minus shipped units, floored at zero | Exception workload |
| Stockout Risk Locations | SKU-warehouse rows at or below reorder risk | Inventory triage |
| Freight Cost Per Shipped Unit | Freight cost / shipped units | Carrier cost control |

## Views

- OTIF and service level trend by promised week.
- Fill rate by SKU, warehouse, and customer.
- Freight cost and on-time delivery by carrier.
- Inventory risk table with days of inventory and reorder risk.
- Lead time distribution by carrier and warehouse.
- Exception queue filtered by priority, backorder units, late delivery, and stockout risk.

## Interaction Requirements

- Filters: promised week, carrier, warehouse, SKU, customer, exception priority.
- Drill path: portfolio KPI tile -> carrier/warehouse view -> order-level exception row.
- Highlight actions: selecting a carrier highlights related late orders and freight cost.
- Tooltip fields: order id, customer id, SKU, promised date, delivery date, fill rate, freight cost, exception reasons.

## Alert Rules

- High priority: no units shipped, or backorder units overlap stockout/reorder risk.
- Medium priority: partial fill or late delivery.
- Monitor: inventory below reorder point with no current late or partial order.

## Validation Criteria

- Order grain remains unique by `order_id`.
- Shipment rows reference valid orders.
- Shipped orders have a TMS shipment record.
- Units shipped do not exceed units ordered.
- Delivery dates do not precede ship dates.
- Source TMS on-time flag matches delivery date versus promised date.
