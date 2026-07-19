"""Generate deterministic ERP/WMS/TMS-style supply chain data.

The generator intentionally creates partial shipments, delays, stockouts,
forecast error and supplier risk so the analytics pipeline has meaningful
exceptions to detect.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

SEED = 421
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "generated"


def _dates(rng: np.random.Generator, start: pd.Timestamp, days: int, n: int) -> pd.Series:
    offsets = rng.integers(0, days, size=n)
    return pd.Series(start + pd.to_timedelta(offsets, unit="D"))


def generate() -> None:
    rng = np.random.default_rng(SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    n_customers, n_products, n_suppliers = 180, 120, 20
    warehouses = np.array(["WH-NORTH", "WH-CENTRAL", "WH-SOUTH"])
    carriers = np.array(["CarrierA", "CarrierB", "CarrierC", "CarrierD"])
    regions = np.array(["North", "Central", "South", "West"])

    customers = pd.DataFrame({
        "customer_id": [f"C{i:04d}" for i in range(1, n_customers + 1)],
        "customer_segment": rng.choice(["Enterprise", "Mid-Market", "SMB"], n_customers, p=[0.20, 0.35, 0.45]),
        "region": rng.choice(regions, n_customers),
    })

    suppliers = pd.DataFrame({
        "supplier_id": [f"SUP{i:03d}" for i in range(1, n_suppliers + 1)],
        "supplier_name": [f"Supplier {i:02d}" for i in range(1, n_suppliers + 1)],
        "base_lead_time_days": rng.integers(5, 22, n_suppliers),
        "supplier_risk_tier": rng.choice(["Low", "Medium", "High"], n_suppliers, p=[0.55, 0.30, 0.15]),
    })

    products = pd.DataFrame({
        "sku": [f"SKU-{i:04d}" for i in range(1, n_products + 1)],
        "product_category": rng.choice(["Components", "Finished Goods", "Consumables", "Spare Parts"], n_products),
        "supplier_id": rng.choice(suppliers["supplier_id"], n_products),
        "unit_price": np.round(rng.uniform(8, 450, n_products), 2),
        "unit_weight_kg": np.round(rng.uniform(0.2, 24, n_products), 2),
    })

    n_orders = 2400
    order_ids = [f"O{i:06d}" for i in range(1, n_orders + 1)]
    order_dates = _dates(rng, pd.Timestamp("2025-01-01"), 365, n_orders)
    customer_ids = rng.choice(customers["customer_id"], n_orders)
    order_warehouse = rng.choice(warehouses, n_orders, p=[0.34, 0.42, 0.24])
    service_days = rng.choice([2, 3, 5, 7], n_orders, p=[0.10, 0.30, 0.45, 0.15])
    promised_dates = order_dates + pd.to_timedelta(service_days, unit="D")

    order_headers = pd.DataFrame({
        "order_id": order_ids,
        "customer_id": customer_ids,
        "warehouse": order_warehouse,
        "order_date": order_dates.dt.date,
        "promised_date": promised_dates.dt.date,
    })

    line_counts = rng.integers(1, 5, n_orders)
    rows = []
    line_id = 1
    product_index = products.set_index("sku")
    for idx, order in order_headers.iterrows():
        chosen = rng.choice(products["sku"], size=int(line_counts[idx]), replace=False)
        for sku in chosen:
            units_ordered = int(rng.integers(1, 45))
            fill_probability = 0.94
            units_shipped = units_ordered if rng.random() < fill_probability else int(rng.integers(0, units_ordered))
            product = product_index.loc[sku]
            rows.append({
                "order_line_id": f"OL{line_id:07d}",
                "order_id": order["order_id"],
                "customer_id": order["customer_id"],
                "warehouse": order["warehouse"],
                "order_date": order["order_date"],
                "promised_date": order["promised_date"],
                "sku": sku,
                "supplier_id": product["supplier_id"],
                "units_ordered": units_ordered,
                "units_shipped": units_shipped,
                "unit_price": float(product["unit_price"]),
                "unit_weight_kg": float(product["unit_weight_kg"]),
                "revenue": round(units_shipped * float(product["unit_price"]), 2),
            })
            line_id += 1
    order_lines = pd.DataFrame(rows)

    order_rollup = order_lines.groupby("order_id", as_index=False).agg(
        total_units_ordered=("units_ordered", "sum"),
        total_units_shipped=("units_shipped", "sum"),
        shipment_weight_kg=("unit_weight_kg", lambda s: 0.0),
    )
    weight = order_lines.assign(line_weight=lambda d: d["units_shipped"] * d["unit_weight_kg"]).groupby("order_id")["line_weight"].sum()
    order_rollup["shipment_weight_kg"] = order_rollup["order_id"].map(weight).round(2)
    shipments = order_headers[["order_id", "promised_date", "warehouse"]].merge(order_rollup, on="order_id")
    shipments["shipment_id"] = [f"S{i:06d}" for i in range(1, len(shipments) + 1)]
    shipments["carrier"] = rng.choice(carriers, len(shipments), p=[0.30, 0.28, 0.24, 0.18])
    shipments["ship_date"] = pd.to_datetime(order_headers["order_date"]) + pd.to_timedelta(rng.integers(0, 4, len(shipments)), unit="D")
    delay = rng.choice([-1, 0, 0, 0, 1, 2, 3, 5], len(shipments), p=[0.04, 0.48, 0.12, 0.08, 0.12, 0.08, 0.05, 0.03])
    candidate_delivery = pd.to_datetime(shipments["promised_date"]) + pd.to_timedelta(delay, unit="D")
    # A delivery cannot occur before the shipment leaves the warehouse. The
    # original simulation could violate this when a short service promise,
    # late ship date and negative delivery delay occurred together.
    shipments["delivery_date"] = pd.concat(
        [candidate_delivery, shipments["ship_date"]], axis=1
    ).max(axis=1)
    shipments["freight_cost"] = np.round(24 + shipments["shipment_weight_kg"] * rng.uniform(0.35, 0.85, len(shipments)) + rng.normal(0, 8, len(shipments)), 2).clip(8)
    shipments["handling_cost"] = np.round(rng.uniform(4, 18, len(shipments)), 2)
    effective_delay = (
        pd.to_datetime(shipments["delivery_date"])
        - pd.to_datetime(shipments["promised_date"])
    ).dt.days
    shipments["exception_cost"] = np.where(
        effective_delay > 0,
        np.round(rng.uniform(5, 60, len(shipments)), 2),
        0.0,
    )
    shipments["on_time"] = pd.to_datetime(shipments["delivery_date"]) <= pd.to_datetime(shipments["promised_date"])
    shipments = shipments[["shipment_id", "order_id", "carrier", "warehouse", "ship_date", "delivery_date", "promised_date", "shipment_weight_kg", "freight_cost", "handling_cost", "exception_cost", "on_time"]]

    months = pd.date_range("2025-01-01", periods=12, freq="MS")
    inventory_rows, forecast_rows, activity_rows = [], [], []
    for month in months:
        for warehouse in warehouses:
            wh_lines = order_lines[(pd.to_datetime(order_lines["order_date"]).dt.month == month.month) & (order_lines["warehouse"] == warehouse)]
            demand_by_sku = wh_lines.groupby("sku")["units_ordered"].sum()
            for sku in products["sku"]:
                monthly_demand = int(demand_by_sku.get(sku, 0))
                avg_daily_demand = monthly_demand / max(month.days_in_month, 1)
                demand_shock = 1.8 if (month.month in [9, 10] and sku.endswith(("7", "8", "9"))) else 1.0
                forecast_units = max(0, int(round(monthly_demand * demand_shock * rng.normal(1.0, 0.18))))
                safety_days = rng.uniform(5, 25)
                on_hand = max(0, int(round(avg_daily_demand * safety_days + rng.normal(0, 8))))
                inventory_value = round(on_hand * float(product_index.loc[sku, "unit_price"]) * 0.55, 2)
                inventory_rows.append({
                    "snapshot_date": month.date(),
                    "warehouse": warehouse,
                    "sku": sku,
                    "on_hand_units": on_hand,
                    "average_daily_demand": round(avg_daily_demand, 4),
                    "inventory_value": inventory_value,
                })
                forecast_rows.append({
                    "month": month.date(),
                    "warehouse": warehouse,
                    "sku": sku,
                    "forecast_units": forecast_units,
                    "actual_units": monthly_demand,
                })
            activity_rows.append({
                "activity_date": month.date(),
                "warehouse": warehouse,
                "units_processed": int(wh_lines["units_shipped"].sum()),
                "labor_hours": round(max(80, wh_lines["units_shipped"].sum() / rng.uniform(18, 34)), 2),
            })

    inventory = pd.DataFrame(inventory_rows)
    forecasts = pd.DataFrame(forecast_rows)
    warehouse_activity = pd.DataFrame(activity_rows)

    tables = {
        "customers.csv": customers,
        "suppliers.csv": suppliers,
        "products.csv": products,
        "erp_order_lines.csv": order_lines,
        "tms_shipments.csv": shipments,
        "wms_inventory_snapshots.csv": inventory,
        "demand_forecasts.csv": forecasts,
        "warehouse_activity.csv": warehouse_activity,
    }
    for name, frame in tables.items():
        frame.to_csv(OUT / name, index=False)

    print(f"Generated {len(order_lines):,} order lines across {n_orders:,} orders in {OUT}")


if __name__ == "__main__":
    generate()
