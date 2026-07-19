from pathlib import Path
import sys

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "validation"))

from reconcile_sql_python import (  # noqa: E402
    RECONCILED_METRICS,
    build_reconciliation,
    run_reconciliation,
)


def test_reconciliation_detects_a_metric_difference():
    python_values = {metric: 1.0 for metric in RECONCILED_METRICS}
    sql_values = python_values.copy()
    sql_values["otif_rate"] = 0.5
    report = build_reconciliation(python_values, sql_values)
    status = report.set_index("metric")["status"]
    assert status["otif_rate"] == "FAIL"
    assert status.drop("otif_rate").eq("PASS").all()


def test_repository_sql_and_python_outputs_reconcile():
    report = run_reconciliation()
    assert report["status"].eq("PASS").all()
    total_orders = report.set_index("metric").loc["total_orders", "sql_value"]
    assert total_orders == 2400


def test_reconciliation_csv_is_byte_stable():
    report_path = ROOT / "outputs" / "sql_python_reconciliation.csv"
    run_reconciliation()
    first = report_path.read_bytes()
    run_reconciliation()
    second = report_path.read_bytes()
    assert first == second


def test_rolling_rates_use_natural_weights():
    orders = pd.DataFrame({
        "order_id": ["O1", "O2", "O3", "O4"],
        "customer_id": ["C1"] * 4,
        "warehouse": ["W1"] * 4,
        "order_date": pd.to_datetime([
            "2025-01-01", "2025-01-02", "2025-01-02", "2025-01-02"
        ]),
        "promised_date": pd.to_datetime([
            "2025-01-01", "2025-01-02", "2025-01-02", "2025-01-02"
        ]),
        "units_ordered": [100, 1, 1, 1],
        "units_shipped": [100, 0, 0, 0],
        "revenue": [100.0, 0.0, 0.0, 0.0],
    })
    shipments = pd.DataFrame({
        "order_id": ["O1", "O2", "O3", "O4"],
        "carrier": ["A"] * 4,
        "delivery_date": pd.to_datetime([
            "2025-01-02", "2025-01-02", "2025-01-02", "2025-01-02"
        ]),
        "freight_cost": [1.0] * 4,
        "handling_cost": [0.0] * 4,
        "exception_cost": [0.0] * 4,
        "shipment_weight_kg": [1.0] * 4,
    })
    with duckdb.connect(":memory:") as connection:
        connection.register("erp_order_lines", orders)
        connection.register("tms_shipments", shipments)
        connection.execute(
            (ROOT / "sql" / "supply_chain_kpis.sql").read_text(encoding="utf-8")
        )
        row = connection.execute(
            """
            select rolling_30d_orders, rolling_30d_otd_rate,
                   rolling_30d_fill_rate
            from mart_daily_service
            where order_date = date '2025-01-02'
            """
        ).fetchone()
    assert row[0] == 4
    assert row[1] == 3 / 4
    assert row[2] == 100 / 103
