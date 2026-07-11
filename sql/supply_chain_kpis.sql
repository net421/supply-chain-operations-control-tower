-- DuckDB-compatible advanced supply chain KPI examples.
-- Expected grains are documented in each section.

-- 1) Order service detail: one row per order.
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

-- 2) Governed headline KPIs: one row.
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

-- 3) Carrier scorecard with rankings and percentiles: one row per carrier.
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
from carrier_metrics
order by service_rank, cost_rank;

-- 4) Rolling 30-day service trend: one row per calendar day with orders.
with daily as (
    select
        order_date,
        count(*) as orders,
        avg(otif::integer) as daily_otif,
        sum(units_shipped) * 1.0 / nullif(sum(units_ordered), 0) as daily_fill_rate
    from mart_order_service
    group by order_date
)
select
    *,
    sum(orders) over (order by order_date rows between 29 preceding and current row) as rolling_30d_orders,
    avg(daily_otif) over (order by order_date rows between 29 preceding and current row) as rolling_30d_otif,
    avg(daily_fill_rate) over (order by order_date rows between 29 preceding and current row) as rolling_30d_fill_rate,
    daily_otif - lag(daily_otif) over (order by order_date) as day_over_day_otif_change
from daily
order by order_date;

-- 5) Reconciliation checks: every query should return zero rows or zero variance.
select
    sum(units_ordered) as source_units_ordered,
    sum(units_shipped) as source_units_shipped
from erp_order_lines;

select
    sum(units_ordered) as mart_units_ordered,
    sum(units_shipped) as mart_units_shipped
from mart_order_service;

select order_id, count(*) as row_count
from mart_order_service
group by order_id
having count(*) <> 1;
