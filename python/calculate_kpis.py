"""Calculate governed supply chain KPIs and BI-ready outputs."""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "generated"
OUTPUTS = ROOT / "outputs"


def safe_divide(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def weighted_forecast_accuracy(forecasts: pd.DataFrame) -> float:
    """Return bounded weighted accuracy with an explicit zero-actual policy.

    Accuracy is 1.0 when forecast and actual totals are both zero, 0.0 when
    actual demand is zero but forecast error exists, and otherwise the bounded
    weighted absolute-error formula.
    """
    abs_error = (forecasts["forecast_units"] - forecasts["actual_units"]).abs().sum()
    actual = forecasts["actual_units"].sum()
    if actual == 0:
        return 1.0 if abs_error == 0 else 0.0
    return max(0.0, 1.0 - safe_divide(abs_error, actual))


def load_data() -> dict[str, pd.DataFrame]:
    date_columns = {
        "orders": ["order_date", "promised_date"],
        "shipments": ["ship_date", "delivery_date", "promised_date"],
        "inventory": ["snapshot_date"],
        "forecasts": ["month"],
        "warehouse_activity": ["activity_date"],
    }
    files = {
        "customers": "customers.csv",
        "suppliers": "suppliers.csv",
        "products": "products.csv",
        "orders": "erp_order_lines.csv",
        "shipments": "tms_shipments.csv",
        "inventory": "wms_inventory_snapshots.csv",
        "forecasts": "demand_forecasts.csv",
        "warehouse_activity": "warehouse_activity.csv",
    }
    result = {}
    for key, filename in files.items():
        result[key] = pd.read_csv(DATA / filename, parse_dates=date_columns.get(key))
    return result


def calculate_order_service(orders: pd.DataFrame, shipments: pd.DataFrame) -> pd.DataFrame:
    order_rollup = orders.groupby("order_id", as_index=False).agg(
        customer_id=("customer_id", "first"),
        warehouse=("warehouse", "first"),
        order_date=("order_date", "first"),
        promised_date=("promised_date", "first"),
        units_ordered=("units_ordered", "sum"),
        units_shipped=("units_shipped", "sum"),
        revenue=("revenue", "sum"),
    )
    service = order_rollup.merge(
        shipments[["order_id", "carrier", "delivery_date", "freight_cost", "handling_cost", "exception_cost", "shipment_weight_kg"]],
        on="order_id",
        how="left",
        validate="one_to_one",
    )
    service["in_full"] = service["units_shipped"] >= service["units_ordered"]
    service["on_time"] = service["delivery_date"] <= service["promised_date"]
    service["otif"] = service["in_full"] & service["on_time"]
    service["lead_time_days"] = (service["delivery_date"] - service["order_date"]).dt.days
    service["backorder_units"] = (service["units_ordered"] - service["units_shipped"]).clip(lower=0)
    service["cost_to_serve"] = service[["freight_cost", "handling_cost", "exception_cost"]].sum(axis=1)
    service["freight_cost_per_kg"] = np.where(service["shipment_weight_kg"] > 0, service["freight_cost"] / service["shipment_weight_kg"], np.nan)
    return service


def calculate_summary(service: pd.DataFrame, forecasts: pd.DataFrame, inventory: pd.DataFrame, activity: pd.DataFrame) -> pd.DataFrame:
    total_ordered = service["units_ordered"].sum()
    total_shipped = service["units_shipped"].sum()
    stockouts = ((inventory["on_hand_units"] <= 0) & (inventory["average_daily_demand"] > 0)).mean()
    warehouse_productivity = safe_divide(activity["units_processed"].sum(), activity["labor_hours"].sum())
    metrics = [
        ("unit_fill_rate", safe_divide(total_shipped, total_ordered)),
        ("complete_order_rate", float(service["in_full"].mean())),
        ("on_time_delivery_rate", float(service["on_time"].mean())),
        ("otif_rate", float(service["otif"].mean())),
        ("backorder_rate", safe_divide(service["backorder_units"].sum(), total_ordered)),
        ("average_lead_time_days", float(service["lead_time_days"].mean())),
        ("weighted_forecast_accuracy", weighted_forecast_accuracy(forecasts)),
        ("stockout_location_sku_rate", float(stockouts)),
        ("warehouse_productivity_units_per_hour", warehouse_productivity),
        ("average_freight_cost_per_kg", float(service["freight_cost_per_kg"].dropna().mean())),
        ("total_cost_to_serve", float(service["cost_to_serve"].sum())),
    ]
    return pd.DataFrame(metrics, columns=["metric", "value"])


def carrier_scorecard(service: pd.DataFrame) -> pd.DataFrame:
    return (
        service.groupby("carrier", as_index=False)
        .agg(
            orders=("order_id", "nunique"),
            otif_rate=("otif", "mean"),
            on_time_delivery_rate=("on_time", "mean"),
            average_lead_time_days=("lead_time_days", "mean"),
            average_freight_cost=("freight_cost", "mean"),
            average_freight_cost_per_kg=("freight_cost_per_kg", "mean"),
            total_exception_cost=("exception_cost", "sum"),
        )
        .sort_values(["otif_rate", "average_freight_cost_per_kg"], ascending=[False, True])
    )


def customer_cost_to_serve(service: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    result = service.groupby("customer_id", as_index=False).agg(
        orders=("order_id", "nunique"),
        revenue=("revenue", "sum"),
        cost_to_serve=("cost_to_serve", "sum"),
        otif_rate=("otif", "mean"),
        backorder_units=("backorder_units", "sum"),
    )
    result["cost_to_serve_pct_revenue"] = np.where(result["revenue"] > 0, result["cost_to_serve"] / result["revenue"], np.nan)
    return result.merge(customers, on="customer_id", how="left", validate="one_to_one").sort_values("cost_to_serve_pct_revenue", ascending=False)


def stockout_exceptions(inventory: pd.DataFrame) -> pd.DataFrame:
    exceptions = inventory[(inventory["average_daily_demand"] > 0) & (inventory["on_hand_units"] <= inventory["average_daily_demand"] * 5)].copy()
    exceptions["days_of_inventory"] = np.where(exceptions["average_daily_demand"] > 0, exceptions["on_hand_units"] / exceptions["average_daily_demand"], np.nan)
    exceptions["severity"] = pd.cut(exceptions["days_of_inventory"], bins=[-1, 0, 2, 5], labels=["Critical", "High", "Medium"])
    return exceptions.sort_values(["severity", "average_daily_demand"], ascending=[True, False])


def supplier_risk_scorecard(orders: pd.DataFrame, suppliers: pd.DataFrame, service: pd.DataFrame) -> pd.DataFrame:
    order_supplier = orders.groupby(["order_id", "supplier_id"], as_index=False).agg(units_ordered=("units_ordered", "sum"))
    joined = order_supplier.merge(service[["order_id", "otif", "backorder_units"]], on="order_id", how="left")
    score = joined.groupby("supplier_id", as_index=False).agg(
        orders=("order_id", "nunique"),
        otif_rate=("otif", "mean"),
        backorder_units=("backorder_units", "sum"),
    ).merge(suppliers, on="supplier_id", how="left", validate="one_to_one")
    tier_penalty = score["supplier_risk_tier"].map({"Low": 0.0, "Medium": 0.15, "High": 0.30}).fillna(0)
    backorder_norm = score["backorder_units"] / max(score["backorder_units"].max(), 1)
    score["resilience_risk_score"] = (0.60 * (1 - score["otif_rate"]) + 0.25 * backorder_norm + 0.15 * tier_penalty).clip(0, 1)
    return score.sort_values("resilience_risk_score", ascending=False)


def run() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    data = load_data()
    service = calculate_order_service(data["orders"], data["shipments"])
    calculate_summary(service, data["forecasts"], data["inventory"], data["warehouse_activity"]).to_csv(OUTPUTS / "kpi_summary.csv", index=False)
    carrier_scorecard(service).to_csv(OUTPUTS / "carrier_scorecard.csv", index=False)
    customer_cost_to_serve(service, data["customers"]).to_csv(OUTPUTS / "customer_cost_to_serve.csv", index=False)
    stockout_exceptions(data["inventory"]).to_csv(OUTPUTS / "stockout_exceptions.csv", index=False)
    supplier_risk_scorecard(data["orders"], data["suppliers"], service).to_csv(OUTPUTS / "supplier_risk_scorecard.csv", index=False)
    service.to_csv(OUTPUTS / "order_service_detail.csv", index=False)
    print(f"Wrote BI-ready outputs to {OUTPUTS}")


if __name__ == "__main__":
    run()
