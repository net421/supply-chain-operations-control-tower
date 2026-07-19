-- DuckDB KPI marts used by the executable reconciliation pipeline.
-- Source views are registered from data/generated/*.csv by
-- validation/reconcile_sql_python.py.

-- One row per order. This portfolio model intentionally assumes one shipment
-- per order; split shipments would require a fulfillment bridge.
create or replace view mart_order_service as
with order_rollup as (
    select
        order_id,
        any_value(customer_id) as customer_id,
        any_value(warehouse) as warehouse,
        min(cast(order_date as date)) as order_date,
        max(cast(promised_date as date)) as promised_date,
        sum(units_ordered) as units_ordered,
        sum(units_shipped) as units_shipped,
        sum(revenue) as revenue
    from erp_order_lines
    group by order_id
), joined as (
    select
        o.*,
        s.carrier,
        cast(s.delivery_date as date) as delivery_date,
        s.freight_cost,
        s.handling_cost,
        s.exception_cost,
        s.shipment_weight_kg,
        o.units_shipped >= o.units_ordered as in_full,
        cast(s.delivery_date as date) <= o.promised_date as on_time
    from order_rollup o
    left join tms_shipments s using (order_id)
)
select
    *,
    in_full and on_time as otif,
    date_diff('day', order_date, delivery_date) as lead_time_days,
    greatest(units_ordered - units_shipped, 0) as backorder_units,
    freight_cost + handling_cost + exception_cost as cost_to_serve,
    freight_cost / nullif(shipment_weight_kg, 0) as freight_cost_per_kg
from joined;

-- One governed row of headline service and cost KPIs.
create or replace view mart_kpi_summary as
select
    count(*) as total_orders,
    sum(units_shipped) * 1.0 / nullif(sum(units_ordered), 0) as unit_fill_rate,
    avg(in_full::integer) as complete_order_rate,
    avg(on_time::integer) as on_time_delivery_rate,
    avg(otif::integer) as otif_rate,
    sum(backorder_units) * 1.0 / nullif(sum(units_ordered), 0) as backorder_rate,
    avg(lead_time_days) as average_lead_time_days,
    sum(cost_to_serve) as total_cost_to_serve
from mart_order_service;

-- One row per carrier with transparent service and cost rankings.
create or replace view mart_carrier_scorecard as
with carrier_metrics as (
    select
        carrier,
        count(*) as orders,
        avg(otif::integer) as otif_rate,
        avg(on_time::integer) as on_time_delivery_rate,
        avg(lead_time_days) as average_lead_time_days,
        avg(freight_cost_per_kg) as average_freight_cost_per_kg,
        quantile_cont(freight_cost_per_kg, 0.90) as p90_freight_cost_per_kg,
        sum(exception_cost) as total_exception_cost
    from mart_order_service
    group by carrier
)
select
    *,
    dense_rank() over (order by otif_rate desc) as service_rank,
    dense_rank() over (order by average_freight_cost_per_kg asc) as cost_rank
from carrier_metrics;

-- One row per order date. The rolling rates accumulate their natural
-- numerators and denominators: order counts for OTD/OTIF and units for fill.
-- Windows cover the preceding 29 calendar days plus the current day.
create or replace view mart_daily_service as
with daily as (
    select
        order_date,
        count(*) as orders,
        sum(coalesce(on_time, false)::integer) as on_time_orders,
        sum(coalesce(otif, false)::integer) as otif_orders,
        sum(units_ordered) as units_ordered,
        sum(units_shipped) as units_shipped,
        sum(coalesce(on_time, false)::integer) * 1.0
            / nullif(count(*), 0) as daily_otd_rate,
        sum(coalesce(otif, false)::integer) * 1.0
            / nullif(count(*), 0) as daily_otif_rate,
        sum(units_shipped) * 1.0 / nullif(sum(units_ordered), 0) as daily_fill_rate
    from mart_order_service
    group by order_date
), rolling as (
    select
        *,
        sum(orders) over (
            order by order_date
            range between interval 29 days preceding and current row
        ) as rolling_30d_orders,
        sum(on_time_orders) over (
            order by order_date
            range between interval 29 days preceding and current row
        ) as rolling_30d_on_time_orders,
        sum(otif_orders) over (
            order by order_date
            range between interval 29 days preceding and current row
        ) as rolling_30d_otif_orders,
        sum(units_ordered) over (
            order by order_date
            range between interval 29 days preceding and current row
        ) as rolling_30d_units_ordered,
        sum(units_shipped) over (
            order by order_date
            range between interval 29 days preceding and current row
        ) as rolling_30d_units_shipped
    from daily
)
select
    *,
    rolling_30d_on_time_orders * 1.0
        / nullif(rolling_30d_orders, 0) as rolling_30d_otd_rate,
    rolling_30d_otif_orders * 1.0
        / nullif(rolling_30d_orders, 0) as rolling_30d_otif_rate,
    rolling_30d_units_shipped * 1.0
        / nullif(rolling_30d_units_ordered, 0) as rolling_30d_fill_rate,
    daily_otd_rate - lag(daily_otd_rate) over (order by order_date)
        as day_over_day_otd_change,
    daily_otif_rate - lag(daily_otif_rate) over (order by order_date)
        as day_over_day_otif_change
from rolling;
