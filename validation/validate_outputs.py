"""Validate source and output quality for the control tower lab."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "generated"
OUTPUTS = ROOT / "outputs"


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"check": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def run_validation() -> pd.DataFrame:
    orders = pd.read_csv(DATA / "erp_order_lines.csv")
    shipments = pd.read_csv(DATA / "tms_shipments.csv")
    summary = pd.read_csv(OUTPUTS / "kpi_summary.csv")
    carrier = pd.read_csv(OUTPUTS / "carrier_scorecard.csv")
    metric = summary.set_index("metric")["value"]

    checks = [
        check("order_line_key_unique", orders["order_line_id"].is_unique, f"rows={len(orders)}"),
        check("shipment_order_unique", shipments["order_id"].is_unique, f"orders={shipments['order_id'].nunique()}"),
        check("units_non_negative", bool((orders[["units_ordered", "units_shipped"]] >= 0).all().all()), "ordered and shipped units >= 0"),
        check("shipped_not_above_ordered", bool((orders["units_shipped"] <= orders["units_ordered"]).all()), "line-level shipped <= ordered"),
        check("unit_fill_rate_range", 0 <= metric["unit_fill_rate"] <= 1, f"value={metric['unit_fill_rate']:.4f}"),
        check("otif_rate_range", 0 <= metric["otif_rate"] <= 1, f"value={metric['otif_rate']:.4f}"),
        check("otif_not_above_components", metric["otif_rate"] <= min(metric["complete_order_rate"], metric["on_time_delivery_rate"]) + 1e-9, "OTIF <= in-full and on-time"),
        check("backorder_complements_fill", abs((metric["unit_fill_rate"] + metric["backorder_rate"]) - 1) < 1e-9, "fill + backorder = 1"),
        check("carrier_output_non_empty", not carrier.empty, f"carriers={len(carrier)}"),
    ]
    report = pd.DataFrame(checks)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    report.to_csv(OUTPUTS / "data_quality_report.csv", index=False)
    failures = report[report["status"] == "FAIL"]
    print(report.to_string(index=False))
    if not failures.empty:
        raise SystemExit(f"Validation failed: {len(failures)} check(s)")
    return report


if __name__ == "__main__":
    run_validation()
