from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from calculate_kpis import (  # noqa: E402
    calculate_order_service,
    calculate_summary,
    safe_divide,
    weighted_forecast_accuracy,
)


def test_safe_divide_handles_zero():
    assert safe_divide(10, 0) == 0.0


def test_forecast_accuracy_handles_zero_actual_demand_honestly():
    no_demand_no_forecast = pd.DataFrame({
        "forecast_units": [0, 0],
        "actual_units": [0, 0],
    })
    no_demand_with_forecast = pd.DataFrame({
        "forecast_units": [5, 0],
        "actual_units": [0, 0],
    })
    assert weighted_forecast_accuracy(no_demand_no_forecast) == 1.0
    assert weighted_forecast_accuracy(no_demand_with_forecast) == 0.0


def test_otif_requires_on_time_and_in_full():
    orders = pd.DataFrame({
        "order_id": ["O1", "O2", "O3", "O4"],
        "customer_id": ["C1"] * 4,
        "warehouse": ["W1"] * 4,
        "order_date": pd.to_datetime(["2025-01-01"] * 4),
        "promised_date": pd.to_datetime(["2025-01-05"] * 4),
        "units_ordered": [10, 10, 10, 10],
        "units_shipped": [10, 8, 10, 8],
        "revenue": [100, 80, 100, 80],
    })
    shipments = pd.DataFrame({
        "order_id": ["O1", "O2", "O3", "O4"],
        "carrier": ["A"] * 4,
        "delivery_date": pd.to_datetime(["2025-01-05", "2025-01-05", "2025-01-06", "2025-01-06"]),
        "freight_cost": [10.0] * 4,
        "handling_cost": [1.0] * 4,
        "exception_cost": [0.0, 0.0, 2.0, 2.0],
        "shipment_weight_kg": [5.0] * 4,
    })
    service = calculate_order_service(orders, shipments)
    assert service["in_full"].tolist() == [True, False, True, False]
    assert service["on_time"].tolist() == [True, True, False, False]
    assert service["otif"].tolist() == [True, False, False, False]


def test_multi_line_order_rolls_up_before_service_classification():
    orders = pd.DataFrame({
        "order_id": ["O1", "O1"],
        "customer_id": ["C1", "C1"],
        "warehouse": ["W1", "W1"],
        "order_date": pd.to_datetime(["2025-01-01", "2025-01-01"]),
        "promised_date": pd.to_datetime(["2025-01-05", "2025-01-05"]),
        "units_ordered": [6, 4],
        "units_shipped": [6, 3],
        "revenue": [60.0, 30.0],
    })
    shipments = pd.DataFrame({
        "order_id": ["O1"],
        "carrier": ["A"],
        "delivery_date": pd.to_datetime(["2025-01-05"]),
        "freight_cost": [10.0],
        "handling_cost": [2.0],
        "exception_cost": [3.0],
        "shipment_weight_kg": [5.0],
    })
    service = calculate_order_service(orders, shipments)
    assert len(service) == 1
    assert service.loc[0, "units_ordered"] == 10
    assert service.loc[0, "units_shipped"] == 9
    assert bool(service.loc[0, "on_time"])
    assert not bool(service.loc[0, "in_full"])
    assert not bool(service.loc[0, "otif"])
    assert service.loc[0, "cost_to_serve"] == 15.0


def test_fill_rate_and_complete_order_rate_are_not_interchangeable():
    service = pd.DataFrame({
        "units_ordered": [100, 1],
        "units_shipped": [99, 1],
        "in_full": [False, True],
        "on_time": [True, True],
        "otif": [False, True],
        "backorder_units": [1, 0],
        "lead_time_days": [2, 2],
        "freight_cost_per_kg": [1.0, 1.0],
        "cost_to_serve": [10.0, 5.0],
    })
    forecasts = pd.DataFrame({"forecast_units": [90], "actual_units": [100]})
    inventory = pd.DataFrame({"on_hand_units": [0], "average_daily_demand": [1]})
    activity = pd.DataFrame({"units_processed": [100], "labor_hours": [10]})
    summary = calculate_summary(service, forecasts, inventory, activity).set_index("metric")["value"]
    assert summary["unit_fill_rate"] == 100 / 101
    assert summary["complete_order_rate"] == 0.5
    assert summary["unit_fill_rate"] + summary["backorder_rate"] == 1.0


def test_stockout_rate_excludes_zero_demand_combinations():
    service = pd.DataFrame({
        "units_ordered": [10],
        "units_shipped": [10],
        "in_full": [True],
        "on_time": [True],
        "otif": [True],
        "backorder_units": [0],
        "lead_time_days": [2],
        "freight_cost_per_kg": [1.0],
        "cost_to_serve": [10.0],
    })
    forecasts = pd.DataFrame({"forecast_units": [10], "actual_units": [10]})
    inventory = pd.DataFrame({
        "on_hand_units": [0, 0, 5],
        "average_daily_demand": [2, 0, 2],
    })
    activity = pd.DataFrame({"units_processed": [10], "labor_hours": [1]})

    summary = calculate_summary(
        service, forecasts, inventory, activity
    ).set_index("metric")["value"]

    assert summary["stockout_location_sku_rate"] == 0.5


def test_zero_shipment_weight_does_not_create_infinite_cost():
    orders = pd.DataFrame({
        "order_id": ["O1"],
        "customer_id": ["C1"],
        "warehouse": ["W1"],
        "order_date": pd.to_datetime(["2025-01-01"]),
        "promised_date": pd.to_datetime(["2025-01-05"]),
        "units_ordered": [10],
        "units_shipped": [0],
        "revenue": [0.0],
    })
    shipments = pd.DataFrame({
        "order_id": ["O1"],
        "carrier": ["A"],
        "delivery_date": pd.to_datetime(["2025-01-05"]),
        "freight_cost": [10.0],
        "handling_cost": [1.0],
        "exception_cost": [0.0],
        "shipment_weight_kg": [0.0],
    })
    service = calculate_order_service(orders, shipments)
    assert pd.isna(service.loc[0, "freight_cost_per_kg"])
