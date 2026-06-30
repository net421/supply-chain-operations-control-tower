"""Supply chain control tower KPI calculator and validator.

This script uses only the Python standard library so reviewers can run it in a
lightweight environment. It turns synthetic ERP, TMS, and WMS extracts into a
validated control tower summary for OTIF, fill rate, backorders, stockout risk,
lead time, service level, inventory turnover, and freight cost.
"""

from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


@dataclass(frozen=True)
class ValidationResult:
    name: str
    failing_rows: int
    detail: str = ""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def to_int(value: str | int | None) -> int:
    return int(value or 0)


def to_float(value: str | float | None) -> float:
    return float(value or 0)


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def calculate_fill_rate(orders: Iterable[dict[str, object]]) -> float:
    rows = list(orders)
    units_ordered = sum(to_int(row["units_ordered"]) for row in rows)
    units_shipped = sum(to_int(row["units_shipped"]) for row in rows)
    return safe_divide(units_shipped, units_ordered)


def flag_stockouts(inventory: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    flagged = []
    for row in inventory:
        on_hand = to_int(row["on_hand_units"])
        reorder_point = to_int(row.get("reorder_point_units", 0))
        demand = to_float(row["average_daily_demand"])
        enriched = dict(row)
        enriched["stockout_risk"] = on_hand <= 0 or on_hand < reorder_point
        enriched["days_of_inventory"] = round(safe_divide(on_hand, demand), 2)
        flagged.append(enriched)
    return flagged


def validate_inputs(
    orders: list[dict[str, str]],
    shipments: list[dict[str, str]],
    inventory: list[dict[str, str]],
) -> list[ValidationResult]:
    results: list[ValidationResult] = []

    order_ids = [row["order_id"] for row in orders]
    duplicate_orders = len(order_ids) - len(set(order_ids))
    results.append(ValidationResult("unique_order_id", duplicate_orders))

    inventory_keys = [(row["sku"], row["warehouse"]) for row in inventory]
    duplicate_inventory = len(inventory_keys) - len(set(inventory_keys))
    results.append(ValidationResult("unique_sku_warehouse_inventory", duplicate_inventory))

    valid_order_ids = set(order_ids)
    invalid_shipments = [row["shipment_id"] for row in shipments if row["order_id"] not in valid_order_ids]
    results.append(
        ValidationResult(
            "shipments_reference_valid_orders",
            len(invalid_shipments),
            ",".join(invalid_shipments),
        )
    )

    bad_order_quantities = [
        row["order_id"]
        for row in orders
        if to_int(row["units_ordered"]) < 0
        or to_int(row["units_shipped"]) < 0
        or to_int(row["units_shipped"]) > to_int(row["units_ordered"])
        or to_float(row["revenue"]) < 0
    ]
    results.append(
        ValidationResult("non_negative_order_values_and_valid_fill", len(bad_order_quantities), ",".join(bad_order_quantities))
    )

    bad_order_dates = [
        row["order_id"]
        for row in orders
        if parse_date(row["promised_date"]) and parse_date(row["order_date"]) and parse_date(row["promised_date"]) < parse_date(row["order_date"])
    ]
    results.append(ValidationResult("promised_date_not_before_order_date", len(bad_order_dates), ",".join(bad_order_dates)))

    bad_shipment_dates = [
        row["shipment_id"]
        for row in shipments
        if parse_date(row["delivery_date"]) and parse_date(row["ship_date"]) and parse_date(row["delivery_date"]) < parse_date(row["ship_date"])
    ]
    results.append(ValidationResult("delivery_date_not_before_ship_date", len(bad_shipment_dates), ",".join(bad_shipment_dates)))

    orders_by_id = {row["order_id"]: row for row in orders}
    on_time_mismatches = []
    for shipment in shipments:
        order = orders_by_id.get(shipment["order_id"])
        if not order:
            continue
        computed_on_time = parse_date(shipment["delivery_date"]) <= parse_date(order["promised_date"])
        if computed_on_time != parse_bool(shipment["on_time"]):
            on_time_mismatches.append(shipment["shipment_id"])
    results.append(ValidationResult("tms_on_time_flag_matches_dates", len(on_time_mismatches), ",".join(on_time_mismatches)))

    shipped_order_ids = {row["order_id"] for row in orders if to_int(row["units_shipped"]) > 0}
    shipment_order_ids = {row["order_id"] for row in shipments}
    missing_shipments = sorted(shipped_order_ids - shipment_order_ids)
    results.append(ValidationResult("shipped_orders_have_tms_shipment", len(missing_shipments), ",".join(missing_shipments)))

    bad_inventory = [
        f"{row['sku']}:{row['warehouse']}"
        for row in inventory
        if to_int(row["on_hand_units"]) < 0
        or to_float(row["average_daily_demand"]) < 0
        or to_float(row["trailing_90d_cogs"]) < 0
        or to_float(row["average_inventory_value"]) <= 0
    ]
    results.append(ValidationResult("inventory_values_are_non_negative", len(bad_inventory), ",".join(bad_inventory)))

    return results


def build_control_tower_rows(
    orders: list[dict[str, str]],
    shipments: list[dict[str, str]],
    inventory: list[dict[str, str]],
) -> list[dict[str, object]]:
    shipments_by_order = {row["order_id"]: row for row in shipments}
    inventory_by_sku_warehouse = {(row["sku"], row["warehouse"]): row for row in inventory}
    control_rows: list[dict[str, object]] = []

    for order in orders:
        shipment = shipments_by_order.get(order["order_id"])
        stock = inventory_by_sku_warehouse.get((order["sku"], order["warehouse"]), {})
        order_date = parse_date(order["order_date"])
        promised_date = parse_date(order["promised_date"])
        ship_date = parse_date(shipment["ship_date"]) if shipment else None
        delivery_date = parse_date(shipment["delivery_date"]) if shipment else None
        units_ordered = to_int(order["units_ordered"])
        units_shipped = to_int(order["units_shipped"])
        freight_cost = to_float(shipment["freight_cost"]) if shipment else 0.0
        on_hand_units = to_int(stock.get("on_hand_units", 0))
        reorder_point = to_int(stock.get("reorder_point_units", 0))
        average_daily_demand = to_float(stock.get("average_daily_demand", 0))
        backorder_units = max(units_ordered - units_shipped, 0)
        in_full = units_shipped >= units_ordered
        delivered_on_time = bool(delivery_date and promised_date and delivery_date <= promised_date)
        otif = in_full and delivered_on_time
        stockout_risk = on_hand_units <= 0 or on_hand_units < reorder_point
        days_to_ship = (ship_date - order_date).days if ship_date and order_date else None
        lead_time_days = (delivery_date - order_date).days if delivery_date and order_date else None

        exception_reasons = []
        if not shipment and units_shipped > 0:
            exception_reasons.append("missing_tms_shipment")
        if backorder_units > 0:
            exception_reasons.append("backorder")
        if not delivered_on_time:
            exception_reasons.append("late_or_not_delivered")
        if stockout_risk:
            exception_reasons.append("stockout_or_reorder_risk")

        control_rows.append(
            {
                "order_id": order["order_id"],
                "customer_id": order["customer_id"],
                "sku": order["sku"],
                "warehouse": order["warehouse"],
                "carrier": shipment["carrier"] if shipment else "NO_SHIPMENT",
                "order_date": order["order_date"],
                "promised_date": order["promised_date"],
                "delivery_date": shipment["delivery_date"] if shipment else None,
                "units_ordered": units_ordered,
                "units_shipped": units_shipped,
                "fill_rate": round(safe_divide(units_shipped, units_ordered), 4),
                "backorder_units": backorder_units,
                "delivered_on_time": delivered_on_time,
                "in_full": in_full,
                "otif": otif,
                "freight_cost": freight_cost,
                "freight_cost_per_shipped_unit": round(safe_divide(freight_cost, units_shipped), 2) if units_shipped else None,
                "days_to_ship": days_to_ship,
                "lead_time_days": lead_time_days,
                "on_hand_units": on_hand_units,
                "days_of_inventory": round(safe_divide(on_hand_units, average_daily_demand), 2),
                "stockout_risk": stockout_risk,
                "inventory_turnover_90d": round(
                    safe_divide(to_float(stock.get("trailing_90d_cogs", 0)), to_float(stock.get("average_inventory_value", 0))),
                    4,
                ),
                "exception_reasons": exception_reasons,
                "exception_priority": classify_exception_priority(backorder_units, delivered_on_time, stockout_risk, units_shipped),
            }
        )

    return control_rows


def classify_exception_priority(
    backorder_units: int,
    delivered_on_time: bool,
    stockout_risk: bool,
    units_shipped: int,
) -> str:
    if units_shipped == 0 or (backorder_units > 0 and stockout_risk):
        return "high"
    if backorder_units > 0 or not delivered_on_time:
        return "medium"
    if stockout_risk:
        return "monitor"
    return "normal"


def summarize_control_tower(
    control_rows: list[dict[str, object]],
    inventory: list[dict[str, str]],
) -> dict[str, object]:
    total_orders = len(control_rows)
    units_ordered = sum(int(row["units_ordered"]) for row in control_rows)
    units_shipped = sum(int(row["units_shipped"]) for row in control_rows)
    otif_orders = sum(1 for row in control_rows if row["otif"])
    on_time_orders = sum(1 for row in control_rows if row["delivered_on_time"])
    backorder_units = sum(int(row["backorder_units"]) for row in control_rows)
    lead_times = [int(row["lead_time_days"]) for row in control_rows if row["lead_time_days"] is not None]
    freight_cost = sum(float(row["freight_cost"]) for row in control_rows)
    high_priority_exceptions = sum(1 for row in control_rows if row["exception_priority"] == "high")
    inventory_stockouts = sum(1 for row in flag_stockouts(inventory) if row["stockout_risk"])
    total_cogs = sum(to_float(row["trailing_90d_cogs"]) for row in inventory)
    total_average_inventory_value = sum(to_float(row["average_inventory_value"]) for row in inventory)

    return {
        "total_orders": total_orders,
        "otif_rate": round(safe_divide(otif_orders, total_orders), 4),
        "fill_rate": round(safe_divide(units_shipped, units_ordered), 4),
        "service_level": round(safe_divide(on_time_orders, total_orders), 4),
        "backorder_units": backorder_units,
        "stockout_or_reorder_risk_sku_locations": inventory_stockouts,
        "average_lead_time_days": round(safe_divide(sum(lead_times), len(lead_times)), 2),
        "total_freight_cost": round(freight_cost, 2),
        "freight_cost_per_shipped_unit": round(safe_divide(freight_cost, units_shipped), 2),
        "inventory_turnover_90d": round(safe_divide(total_cogs, total_average_inventory_value), 4),
        "high_priority_exceptions": high_priority_exceptions,
    }


def summarize_carriers(control_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in control_rows:
        grouped[str(row["carrier"])].append(row)

    summaries = []
    for carrier, rows in sorted(grouped.items()):
        shipped_units = sum(int(row["units_shipped"]) for row in rows)
        summaries.append(
            {
                "carrier": carrier,
                "orders": len(rows),
                "on_time_delivery_rate": round(safe_divide(sum(1 for row in rows if row["delivered_on_time"]), len(rows)), 4),
                "otif_rate": round(safe_divide(sum(1 for row in rows if row["otif"]), len(rows)), 4),
                "freight_cost": round(sum(float(row["freight_cost"]) for row in rows), 2),
                "freight_cost_per_shipped_unit": round(safe_divide(sum(float(row["freight_cost"]) for row in rows), shipped_units), 2),
            }
        )
    return summaries


def run_control_tower(data_dir: Path = DATA_DIR) -> dict[str, object]:
    LOGGER.info("Loading ERP, TMS, and WMS samples from %s", data_dir)
    orders = read_csv(data_dir / "erp_orders_sample.csv")
    shipments = read_csv(data_dir / "tms_shipments_sample.csv")
    inventory = read_csv(data_dir / "wms_inventory_sample.csv")

    validation_results = validate_inputs(orders, shipments, inventory)
    failing_results = [result for result in validation_results if result.failing_rows > 0]
    if failing_results:
        details = "; ".join(f"{result.name}={result.failing_rows} {result.detail}" for result in failing_results)
        raise AssertionError(f"Input validation failed: {details}")

    control_rows = build_control_tower_rows(orders, shipments, inventory)
    return {
        "summary": summarize_control_tower(control_rows, inventory),
        "carrier_summary": summarize_carriers(control_rows),
        "validation_checks": len(validation_results),
        "exception_queue": [
            row
            for row in control_rows
            if row["exception_priority"] in {"high", "medium"}
        ],
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run_control_tower()
    print(json.dumps(result, indent=2, sort_keys=True))
