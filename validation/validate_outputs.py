"""Validate source contracts, KPI invariants and generated evidence."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "generated"
OUTPUTS = ROOT / "outputs"


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"check": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def _composite_unique(frame: pd.DataFrame, columns: list[str]) -> bool:
    return not frame.duplicated(columns).any()


def run_validation() -> pd.DataFrame:
    customers = pd.read_csv(DATA / "customers.csv")
    suppliers = pd.read_csv(DATA / "suppliers.csv")
    products = pd.read_csv(DATA / "products.csv")
    orders = pd.read_csv(
        DATA / "erp_order_lines.csv", parse_dates=["order_date", "promised_date"]
    )
    shipments = pd.read_csv(
        DATA / "tms_shipments.csv",
        parse_dates=["ship_date", "delivery_date", "promised_date"],
    )
    inventory = pd.read_csv(DATA / "wms_inventory_snapshots.csv")
    forecasts = pd.read_csv(DATA / "demand_forecasts.csv")
    activity = pd.read_csv(DATA / "warehouse_activity.csv")
    summary = pd.read_csv(OUTPUTS / "kpi_summary.csv")
    detail = pd.read_csv(OUTPUTS / "order_service_detail.csv")
    carrier = pd.read_csv(OUTPUTS / "carrier_scorecard.csv")
    reconciliation = pd.read_csv(OUTPUTS / "sql_python_reconciliation.csv")
    metric = summary.set_index("metric")["value"]
    demanded_inventory = inventory[inventory["average_daily_demand"] > 0]
    stockout_count = int((demanded_inventory["on_hand_units"] <= 0).sum())
    demanded_inventory_count = len(demanded_inventory)
    expected_stockout_rate = (
        stockout_count / demanded_inventory_count if demanded_inventory_count else 0.0
    )

    expected_on_time = shipments["delivery_date"] <= shipments["promised_date"]
    source_on_time = shipments["on_time"].astype(str).str.lower().eq("true")
    erp_promises = orders.groupby("order_id")["promised_date"].agg(["nunique", "first"])
    shipment_promises = shipments.set_index("order_id")["promised_date"]
    erp_promise_for_shipment = erp_promises["first"].reindex(shipment_promises.index)
    promised_dates_match = bool(
        erp_promises["nunique"].eq(1).all()
        and erp_promise_for_shipment.notna().all()
        and shipment_promises.eq(erp_promise_for_shipment).all()
    )
    required_metrics = {
        "unit_fill_rate",
        "complete_order_rate",
        "on_time_delivery_rate",
        "otif_rate",
        "backorder_rate",
        "average_lead_time_days",
        "weighted_forecast_accuracy",
        "stockout_location_sku_rate",
        "warehouse_productivity_units_per_hour",
        "average_freight_cost_per_kg",
        "total_cost_to_serve",
    }

    checks = [
        check("customer_key_unique", customers["customer_id"].is_unique, f"rows={len(customers)}"),
        check("supplier_key_unique", suppliers["supplier_id"].is_unique, f"rows={len(suppliers)}"),
        check("product_key_unique", products["sku"].is_unique, f"rows={len(products)}"),
        check("order_line_key_unique", orders["order_line_id"].is_unique, f"rows={len(orders)}"),
        check("shipment_order_unique", shipments["order_id"].is_unique, f"orders={shipments['order_id'].nunique()}"),
        check(
            "shipment_orders_exist",
            set(shipments["order_id"]).issubset(set(orders["order_id"])),
            "every shipment references an ERP order",
        ),
        check(
            "order_shipment_coverage",
            set(orders["order_id"]) == set(shipments["order_id"]),
            "every modeled order has exactly one shipment",
        ),
        check(
            "order_customers_exist",
            set(orders["customer_id"]).issubset(set(customers["customer_id"])),
            "every order references a customer",
        ),
        check(
            "order_products_exist",
            set(orders["sku"]).issubset(set(products["sku"])),
            "every order line references a product",
        ),
        check(
            "order_suppliers_exist",
            set(orders["supplier_id"]).issubset(set(suppliers["supplier_id"])),
            "every order line references a supplier",
        ),
        check(
            "inventory_grain_unique",
            _composite_unique(inventory, ["snapshot_date", "warehouse", "sku"]),
            "grain=snapshot_date,warehouse,sku",
        ),
        check(
            "forecast_grain_unique",
            _composite_unique(forecasts, ["month", "warehouse", "sku"]),
            "grain=month,warehouse,sku",
        ),
        check(
            "activity_grain_unique",
            _composite_unique(activity, ["activity_date", "warehouse"]),
            "grain=activity_date,warehouse",
        ),
        check(
            "units_non_negative",
            bool((orders[["units_ordered", "units_shipped"]] >= 0).all().all()),
            "ordered and shipped units >= 0",
        ),
        check(
            "shipped_not_above_ordered",
            bool((orders["units_shipped"] <= orders["units_ordered"]).all()),
            "line-level shipped <= ordered",
        ),
        check(
            "promised_not_before_order",
            bool((orders["promised_date"] >= orders["order_date"]).all()),
            "promised date >= order date",
        ),
        check(
            "shipment_promise_matches_erp",
            promised_dates_match,
            "one ERP promise per order and TMS promise matches it",
        ),
        check(
            "delivery_not_before_ship",
            bool((shipments["delivery_date"] >= shipments["ship_date"]).all()),
            "delivery date >= ship date",
        ),
        check(
            "source_on_time_consistent",
            bool(source_on_time.equals(expected_on_time)),
            "source flag matches delivery <= promise",
        ),
        check(
            "inventory_non_negative",
            bool((inventory[["on_hand_units", "average_daily_demand", "inventory_value"]] >= 0).all().all()),
            "inventory measures >= 0",
        ),
        check(
            "forecast_non_negative",
            bool((forecasts[["forecast_units", "actual_units"]] >= 0).all().all()),
            "forecast and actual units >= 0",
        ),
        check(
            "activity_valid",
            bool((activity["units_processed"] >= 0).all() and (activity["labor_hours"] > 0).all()),
            "processed units >= 0 and labor hours > 0",
        ),
        check("summary_metric_unique", summary["metric"].is_unique, f"metrics={len(summary)}"),
        check(
            "summary_metrics_complete",
            required_metrics.issubset(set(summary["metric"])),
            f"required={len(required_metrics)}",
        ),
        check(
            "summary_values_finite",
            bool(np.isfinite(summary["value"]).all()),
            "all reported KPI values are finite",
        ),
        check("order_output_unique", detail["order_id"].is_unique, f"orders={len(detail)}"),
        check("unit_fill_rate_range", 0 <= metric["unit_fill_rate"] <= 1, f"value={metric['unit_fill_rate']:.4f}"),
        check(
            "complete_order_rate_range",
            0 <= metric["complete_order_rate"] <= 1,
            f"value={metric['complete_order_rate']:.4f}",
        ),
        check(
            "on_time_delivery_rate_range",
            0 <= metric["on_time_delivery_rate"] <= 1,
            f"value={metric['on_time_delivery_rate']:.4f}",
        ),
        check("otif_rate_range", 0 <= metric["otif_rate"] <= 1, f"value={metric['otif_rate']:.4f}"),
        check(
            "backorder_rate_range",
            0 <= metric["backorder_rate"] <= 1,
            f"value={metric['backorder_rate']:.4f}",
        ),
        check(
            "forecast_accuracy_range",
            0 <= metric["weighted_forecast_accuracy"] <= 1,
            f"value={metric['weighted_forecast_accuracy']:.4f}",
        ),
        check(
            "stockout_rate_range",
            0 <= metric["stockout_location_sku_rate"] <= 1,
            f"value={metric['stockout_location_sku_rate']:.4f}",
        ),
        check(
            "stockout_rate_matches_demanded_inventory",
            abs(metric["stockout_location_sku_rate"] - expected_stockout_rate)
            < 1e-9,
            f"stockouts={stockout_count}; "
            f"demanded_combinations={demanded_inventory_count}",
        ),
        check(
            "otif_not_above_components",
            metric["otif_rate"] <= min(metric["complete_order_rate"], metric["on_time_delivery_rate"]) + 1e-9,
            "OTIF <= in-full and on-time",
        ),
        check(
            "backorder_complements_fill",
            abs((metric["unit_fill_rate"] + metric["backorder_rate"]) - 1) < 1e-9,
            "fill + backorder = 1 under the documented model",
        ),
        check("carrier_output_non_empty", not carrier.empty, f"carriers={len(carrier)}"),
        check(
            "sql_python_reconciliation_passed",
            bool(not reconciliation.empty and reconciliation["status"].eq("PASS").all()),
            f"metrics={len(reconciliation)}",
        ),
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
