# Reproducible Operating Review

This summary is generated from the deterministic portfolio scenario. It shows
how the outputs could support an operating conversation; it does not report a
real company's performance or measured financial impact.

For the request, evidence trail, decision options and delivery history, see the
[`manager case study`](../docs/manager_case_study.md).

## Service signal

- **Unit fill rate is 96.79%**, while **complete-order rate is 85.75%**.
- **On-time delivery is 70.83%** and **OTIF is 60.62%**.
- **Backorder rate is 3.21%** and average lead time is **4.87 days**.

The 36.17 percentage-point gap between fill rate and OTIF indicates that service
risk is not explained by unit shortages alone. Whole-order completeness and
delivery timing both need review. A manager should not use fill rate as a proxy
for OTIF.

The four-way order segmentation in the linked case study identifies 603
complete-but-late orders as the largest non-OTIF review queue. This is a
prioritization observation, not a diagnosis of cause.

## Transportation signal

Carrier D has the strongest modeled OTIF at **62.68%** and the lowest average
freight cost per kilogram at **0.738 modeled cost units/kg** among the four
carriers. Carrier B has the weakest modeled OTIF at **59.65%** and the highest
average freight cost per kilogram at **0.819 modeled cost units/kg**. This makes
Carrier B a candidate for warehouse-, weight- and order-mix-adjusted review, not
an automatic replacement decision.

## Inventory and planning signal

- The location-SKU stockout rate is **9.50%**: 302 of 3,179 combinations with
  positive average daily demand have zero on-hand inventory.
- Weighted forecast accuracy is **82.90%**.
- Warehouse productivity is **25.76 units per labor hour**.

The exception file should be filtered by warehouse, SKU demand and days of
inventory before prioritizing replenishment. The aggregate forecast metric alone
cannot reveal category-specific bias.

## Cost and resilience signal

- Total modeled cost-to-serve is **972,618.91**.
- Customer C0042 has the highest modeled cost-to-serve share in the generated
  scorecard at **5.51% of revenue**.
- Supplier SUP015 has the highest modeled resilience-risk score at **0.5125**.

These are prioritization signals. Customer mix, warehouse, product weight and
order size should be controlled before drawing a profitability conclusion.
Supplier risk is especially limited because an order-level backorder can be
attributed to more than one supplier represented in the order.

## Questions for the next operating review

1. Which late orders were fully shipped, separating carrier timing from inventory
   availability?
2. Does Carrier B remain expensive after comparing equivalent warehouses,
   weights and order sizes?
3. Which critical stockouts combine positive demand with high-value customers?
4. Is forecast error systematically biased by category or warehouse?
5. Which supplier risks remain high after allocating shortages at order-line
   rather than order level?

## Evidence and limits

Eight headline service and cost metrics reconcile between pandas and DuckDB in
[`outputs/sql_python_reconciliation.csv`](../outputs/sql_python_reconciliation.csv).
The remaining figures trace to deterministic versioned outputs but are not part
of that independent SQL comparison. The source and output contract is recorded
in [`outputs/data_quality_report.csv`](../outputs/data_quality_report.csv).

The data is synthetic, the refresh is local and no recommendation was used by a
real organization. The analysis demonstrates reasoning and implementation, not
production experience or business impact.
