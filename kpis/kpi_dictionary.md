# Governed Supply Chain KPI Dictionary

| KPI | Grain | Formula | Interpretation | Validation |
|---|---|---|---|---|
| Unit Fill Rate | portfolio / period | `sum(units_shipped) / sum(units_ordered)` | Share of demanded units fulfilled | Must be between 0 and 1 |
| Complete Order Rate | order | fully shipped orders / total orders | Orders with no unit shortage | Must not be labeled fill rate |
| On-Time Delivery | order | orders delivered by promised date / delivered orders | Delivery reliability independent of quantity | Between 0 and 1 |
| OTIF | order | on-time and in-full orders / total orders | End-to-end service reliability | Must be <= OTD and complete order rate |
| Backorder Rate | portfolio / period | backordered units / ordered units | Demand not immediately fulfilled | `fill rate + backorder rate = 1` under this simulation |
| Lead Time | order | delivery date - order date | Customer responsiveness | Non-negative days |
| Days of Inventory | SKU/location/snapshot | on-hand units / average daily demand | Stock coverage | Null when demand is zero |
| Stockout Rate | SKU/location/snapshot | demanded combinations with zero on hand / demanded combinations | Availability risk | Filter to positive demand |
| Forecast Accuracy | SKU/location/month | `1 - sum(abs(forecast-actual))/sum(actual)` when actual total > 0 | Weighted planning accuracy | Clamp at zero; return 1 only when forecast and actual are both zero, otherwise 0 when actual is zero |
| Warehouse Productivity | warehouse/period | units processed / labor hours | Labor efficiency | Labor hours must be positive |
| Freight Cost per kg | shipment | freight cost / shipped weight | Transport cost efficiency | Exclude zero-weight shipments |
| Cost-to-Serve | order/customer | freight + handling + exception cost | Service profitability pressure | Reconcile to shipment costs |
| Supplier Resilience Risk | supplier | weighted service failure, backorders and stated risk tier | Prioritizes suppliers requiring review | Formula documented; 0 = lower risk, 1 = higher risk |

## Important distinction

A unit fill rate and a complete order rate answer different questions. The first measures units; the second measures whole orders. OTIF requires both service dimensions: timeliness and completeness.
