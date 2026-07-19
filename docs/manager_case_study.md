# Manager Case Study: 96.79% Unit Fill, 60.62% OTIF

> **Scope:** deterministic synthetic portfolio scenario. The decisions below are
> options for an operating review, not actions taken by a real company.

## The request

A supply-chain manager sees unit fill rate near 97% but OTIF near 61% and asks:

> Is the service gap more consistent with incomplete fulfillment, late delivery,
> or both? What should the team review first, and can the answer be reproduced?

The analysis must keep unlike denominators separate, reconcile headline metrics
between SQL and Python, and distinguish observations from decisions.
This manager-ready evidence package is tracked in
[Issue #5](https://github.com/net421/supply-chain-operations-control-tower/issues/5).

## Evidence used

| Evidence | Grain or purpose | Versioned result |
|---|---|---:|
| [`order_service_detail.csv`](../outputs/order_service_detail.csv) | one row per order | 2,400 orders |
| [`kpi_summary.csv`](../outputs/kpi_summary.csv) | governed headline metrics | 11 metrics |
| [`carrier_scorecard.csv`](../outputs/carrier_scorecard.csv) | carrier-level review queue | 4 carriers |
| [`sql_python_reconciliation.csv`](../outputs/sql_python_reconciliation.csv) | independent pandas/DuckDB comparison | 8/8 PASS |
| [`data_quality_report.csv`](../outputs/data_quality_report.csv) | source, grain, date, range and output contracts | 38/38 PASS |

The order population is assembled from 5,928 synthetic ERP order lines. KPI
definitions and denominators are documented in the
[`kpi_dictionary`](../kpis/kpi_dictionary.md).

## Findings

### 1. High unit fill does not imply high complete-order service

- Unit fill rate is **96.79%**: shipped units divided by ordered units.
- Complete-order rate is **85.75%**: 2,058 of 2,400 orders shipped in full.
- OTIF is **60.62%**: 1,455 orders were both in full and on time.

The 36.17 percentage-point difference between unit fill and OTIF is a useful
warning signal, not a mathematical decomposition: the first metric is
unit-weighted and the second is order-weighted.

### 2. Timing is the largest visible non-OTIF segment

The two governed order-level flags produce this mutually exclusive review queue:

| Fulfillment and timing outcome | Orders | Share of orders |
|---|---:|---:|
| In full and on time | 1,455 | 60.62% |
| In full but late | 603 | 25.12% |
| Incomplete but on time | 245 | 10.21% |
| Incomplete and late | 97 | 4.04% |

Shares may not sum to exactly 100% because displayed values are rounded.

There are **700 late orders** and **342 incomplete orders**. The 603 orders that
were complete but late are the largest non-OTIF segment, so they are the clearest
first queue for delivery-event review. This does not establish why they were
late.

### 3. Carrier averages are screening signals, not causal rankings

Carrier D has the highest modeled OTIF (**62.68%**) and lowest average freight
cost per kilogram (**0.738 modeled cost units/kg**). Carrier B has the lowest
modeled OTIF (**59.65%**) and highest average freight cost per kilogram
(**0.819 modeled cost units/kg**).

Those averages are not enough to replace or renegotiate a carrier. Shipment
weight, warehouse, customer and order mix may differ, and the model contains no
lane field.

## Decisions a manager could consider

| Priority | Decision to consider | Evidence needed before acting |
|---|---|---|
| 1 | Review the 603 complete-but-late orders separately from shortages. | Shipment event timestamps and delay reason codes; the synthetic model only has shipment and delivery dates. |
| 2 | Route the 342 incomplete orders to line-level availability analysis. | SKU, supplier and warehouse joins from the synthetic ERP/WMS sources. |
| 3 | Compare Carrier B with peers within equivalent operational segments. | Weight bands, warehouse, order size and customer mix; no lane comparison is possible here. |
| 4 | Set separate service targets for fill, complete-order rate, OTD and OTIF. | An agreed service policy, time horizon and cost trade-off; none is assumed by this project. |

No action, savings, SLA improvement or carrier outcome is claimed.

## Traceable delivery path

This repository also demonstrates how an analytics change can move from a
reported gap to checked evidence:

| Stage | Artifact | What a reviewer can verify |
|---|---|---|
| Manager-ready request | [Issue #5](https://github.com/net421/supply-chain-operations-control-tower/issues/5) | The presentation requirement and acceptance criteria are recorded separately from the implementation. |
| Problem | [Issue #3](https://github.com/net421/supply-chain-operations-control-tower/issues/3) | The SQL implementation was presented but not executed, and validation documentation was stale. |
| Change | [PR #4](https://github.com/net421/supply-chain-operations-control-tower/pull/4) | The local DuckDB path, pandas comparison, validation contracts and CI were made executable. |
| Regression checks | [`tests/`](../tests) | 11 tests cover KPI denominators and edge cases, rolling weights, reconciliation stability and deliberate mismatch detection. |
| Reconciled result | [`sql_python_reconciliation.csv`](../outputs/sql_python_reconciliation.csv) | Eight headline metrics agree within the documented tolerance. |
| Data contract | [`data_quality_report.csv`](../outputs/data_quality_report.csv) | All 38 current checks pass and validation failures exit non-zero. |

Reproduce the entire path from a clean environment with:

```bash
pip install -r requirements.txt
python run_pipeline.py --with-tests
```

## Limits of the recommendation

- All data is deterministic and synthetic; this is not measured business impact.
- The model assumes one shipment per order and cannot analyze split shipments.
- The order outcome table supports prioritization, not causal diagnosis.
- Carrier comparisons are unadjusted aggregates and do not include lanes.
- Cost fields use modeled units; no real currency or commercial rate is claimed.
- Supplier backorder attribution is order-level and may assign one shortage to
  multiple represented suppliers.
- The project runs locally with DuckDB; it has no production refresh, users or
  operational SLA.

The appropriate next deliverable would be a segmented root-cause analysis using
real operational fields and agreed service definitions, not a larger platform.
