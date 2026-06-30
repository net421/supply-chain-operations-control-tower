# Supply Chain Operations Control Tower

A portfolio lab for ERP/WMS/TMS-style supply chain analytics. It demonstrates KPI definitions, exception monitoring, operational triage and BI-ready control tower design.

This is a synthetic lab, not a production system. It is designed to show how supply chain data can be joined, validated, modeled, and explained for operations stakeholders.

## Featured Artifact: Validated KPI Control Tower

| File | What it proves |
| --- | --- |
| `data/*.csv` | Synthetic ERP, TMS, and WMS source extracts with service, inventory, and freight edge cases. |
| `sql/supply_chain_kpis.sql` | SQL control tower mart pattern with OTIF, fill rate, service level, backorders, stockout risk, lead time, inventory turnover, and freight KPIs. |
| `python/calculate_kpis.py` | Executable standard-library pipeline with input validation, KPI calculations, carrier scorecard, and exception queue. |
| `kpis/kpi_dictionary.md` | Recruiter-readable KPI formulas, grains, business uses, and validation notes. |
| `tableau_spec/control_tower_dashboard.md` | Dashboard requirements for KPI tiles, filters, drill paths, alert rules, and validation criteria. |
| `docs/control_tower_validation.md` | Lineage, validation contract, assumptions, and exception-priority logic. |

## Local Validation

```bash
python python/calculate_kpis.py
```

The script loads the synthetic samples, validates source integrity, builds order-level control tower rows, and prints a JSON summary. It intentionally avoids external dependencies so the review path is lightweight.

## Skill Evidence

- ERP/WMS/TMS analytics modeling
- Supply chain KPI design: OTIF, fill rate, service level, lead time, backorders, stockout risk, inventory turnover, and freight cost
- Exception queue logic for operations triage
- SQL CTEs, joins, guarded division, and validation queries
- Python data pipeline with logging and validation
- Tableau-ready dashboard specification and stakeholder framing
