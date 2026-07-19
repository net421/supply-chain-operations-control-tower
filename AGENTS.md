# Repository Working Agreement

## Mission

Maintain this repository as a small, executable supply-chain analytics case.
Prefer deeper validation and clearer evidence over new platforms or features.

## Required verification

After changing data generation, KPI logic, SQL, validation or tests, run:

```bash
python run_pipeline.py --with-tests
git diff --check
```

Do not update committed CSV outputs manually. Regenerate them through the runner.

## Invariants

- `erp_order_lines` is line-grain; `mart_order_service` is order-grain.
- OTIF requires both on-time delivery and complete fulfillment.
- Unit fill rate and complete-order rate are distinct measures.
- Python and DuckDB headline KPIs must reconcile within the documented tolerance.
- Rolling OTD/OTIF is weighted by orders and rolling fill rate by units.
- Zero-actual forecast accuracy is 1 only when forecast is also zero; otherwise 0.
- Reconciliation evidence must be byte-stable across identical executions.
- Delivery cannot precede shipment and promise cannot precede order.
- Validation failures must exit non-zero.

## Claims policy

- Describe all data as deterministic and synthetic.
- Describe DuckDB as a local analytical database, not production PostgreSQL.
- Describe `tableau_spec/` as a specification, not a real Tableau or Power BI file.
- Do not claim cloud deployment, scheduled refresh, SLAs, real users, client
  impact, production incidents or professional platform experience.
- AI assistance may be disclosed, but every changed KPI, test and recommendation
  must remain explainable and human-reviewable.

## Scope discipline

Do not add cloud services, orchestration frameworks, databases or dashboards
unless a specific issue requires them. This repository is the technical backend;
visual evidence belongs in the separate `logistics-dashboard` project.
