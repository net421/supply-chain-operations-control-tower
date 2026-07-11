# Operations Control Tower Dashboard Specification

## Audience

Operations directors, supply chain analysts, logistics managers, inventory planners and service-level owners.

## Page 1 — Executive service overview

KPI cards:

- OTIF
- Unit Fill Rate
- Complete Order Rate
- On-Time Delivery
- Backorder Rate
- Total Cost-to-Serve

Views:

- 30-day rolling OTIF and fill-rate trend
- service by region and customer segment
- carrier service-versus-cost quadrant
- prioritized exception queue

## Page 2 — Inventory and planning

- days of inventory by SKU and warehouse
- stockout and low-cover exception table
- forecast accuracy by category
- demand shock trend

## Page 3 — Transportation and supplier resilience

- freight cost per kg by carrier
- lead-time distribution
- supplier resilience risk scorecard
- Pareto view of exception cost

## Filters

Date, region, warehouse, customer segment, category, supplier, carrier and severity.

## Governed behavior

- All percentages use documented denominators.
- OTIF is never calculated as average of OTD and fill rate.
- KPI cards reconcile to `outputs/kpi_summary.csv`.
- Tooltips display formula, grain, refresh timestamp and data limitation.
