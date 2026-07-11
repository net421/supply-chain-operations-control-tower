from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from calculate_kpis import calculate_order_service, safe_divide  # noqa: E402


def test_safe_divide_handles_zero():
    assert safe_divide(10, 0) == 0.0


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
