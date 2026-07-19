"""Execute the DuckDB marts and reconcile them with the Python KPI outputs."""
from __future__ import annotations

import math
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "generated"
OUTPUTS = ROOT / "outputs"
SQL_FILE = ROOT / "sql" / "supply_chain_kpis.sql"
DEFAULT_TOLERANCE = 1e-9
DEFAULT_DECIMALS = 12
METRIC_DECIMALS = {
    "total_orders": 0,
    "total_cost_to_serve": 2,
}

SOURCE_FILES = {
    "erp_order_lines": "erp_order_lines.csv",
    "tms_shipments": "tms_shipments.csv",
}

RECONCILED_METRICS = (
    "total_orders",
    "unit_fill_rate",
    "complete_order_rate",
    "on_time_delivery_rate",
    "otif_rate",
    "backorder_rate",
    "average_lead_time_days",
    "total_cost_to_serve",
)


def _sql_path(path: Path) -> str:
    """Return a path safe to embed in a DuckDB string literal."""
    return str(path.resolve()).replace("'", "''")


def register_sources(connection: duckdb.DuckDBPyConnection) -> None:
    """Expose generated CSV sources as typed DuckDB views."""
    for table, filename in SOURCE_FILES.items():
        source_path = DATA / filename
        if not source_path.exists():
            raise FileNotFoundError(f"Missing source file: {source_path}")
        connection.execute(
            f"create or replace view {table} as "
            f"select * from read_csv_auto('{_sql_path(source_path)}', header=true)"
        )


def python_metric_values() -> dict[str, float]:
    """Read the independently generated Python outputs into a metric mapping."""
    summary_path = OUTPUTS / "kpi_summary.csv"
    detail_path = OUTPUTS / "order_service_detail.csv"
    if not summary_path.exists() or not detail_path.exists():
        raise FileNotFoundError("Run python/calculate_kpis.py before reconciliation")
    summary = pd.read_csv(summary_path).set_index("metric")["value"].to_dict()
    summary["total_orders"] = float(len(pd.read_csv(detail_path, usecols=["order_id"])))
    return {metric: float(summary[metric]) for metric in RECONCILED_METRICS}


def build_reconciliation(
    python_values: dict[str, float],
    sql_values: dict[str, float],
    tolerance: float = DEFAULT_TOLERANCE,
) -> pd.DataFrame:
    """Build a reviewable comparison without hiding rounding differences."""
    rows = []
    for metric in RECONCILED_METRICS:
        decimals = METRIC_DECIMALS.get(metric, DEFAULT_DECIMALS)
        python_value = round(float(python_values[metric]), decimals)
        sql_value = round(float(sql_values[metric]), decimals)
        difference = round(abs(python_value - sql_value), DEFAULT_DECIMALS)
        passed = math.isclose(
            python_value,
            sql_value,
            rel_tol=tolerance,
            abs_tol=tolerance,
        )
        rows.append(
            {
                "metric": metric,
                "python_value": python_value,
                "sql_value": sql_value,
                "absolute_difference": difference,
                "tolerance": tolerance,
                "status": "PASS" if passed else "FAIL",
            }
        )
    return pd.DataFrame(rows)


def run_reconciliation() -> pd.DataFrame:
    """Execute SQL marts, compare governed metrics and write audit evidence."""
    with duckdb.connect(":memory:") as connection:
        register_sources(connection)
        connection.execute(SQL_FILE.read_text(encoding="utf-8"))
        sql_row = connection.execute("select * from mart_kpi_summary").fetchdf().iloc[0]
        duplicate_orders = connection.execute(
            """
            select count(*)
            from (
                select order_id
                from mart_order_service
                group by order_id
                having count(*) <> 1
            )
            """
        ).fetchone()[0]

    if duplicate_orders:
        raise SystemExit(f"SQL mart grain failed: {duplicate_orders} duplicate order(s)")

    sql_values = {metric: float(sql_row[metric]) for metric in RECONCILED_METRICS}
    report = build_reconciliation(python_metric_values(), sql_values)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUTS / "sql_python_reconciliation.csv"
    report.to_csv(
        report_path,
        index=False,
        float_format="%.12g",
        lineterminator="\n",
    )
    print(report.to_string(index=False))

    failures = report[report["status"] == "FAIL"]
    if not failures.empty:
        raise SystemExit(f"SQL/Python reconciliation failed: {len(failures)} metric(s)")
    return report


if __name__ == "__main__":
    run_reconciliation()
