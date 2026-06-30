-- Supply chain control tower KPI patterns.
-- Portfolio lab example using synthetic ERP, TMS, and WMS-style tables.
-- Tables assumed:
--   erp_orders(order_id, customer_id, order_date, promised_date, sku, warehouse, units_ordered, units_shipped, revenue)
--   tms_shipments(shipment_id, order_id, carrier, ship_date, delivery_date, freight_cost, on_time)
--   wms_inventory(sku, warehouse, on_hand_units, average_daily_demand, reorder_point_units, unit_cost, trailing_90d_cogs, average_inventory_value)

with orders as (
    select
        cast(order_id as varchar) as order_id,
        customer_id,
        cast(order_date as date) as order_date,
        cast(promised_date as date) as promised_date,
        sku,
        warehouse,
        cast(units_ordered as numeric) as units_ordered,
        cast(units_shipped as numeric) as units_shipped,
        cast(revenue as numeric) as revenue
    from erp_orders
),

shipments as (
    select
        shipment_id,
        cast(order_id as varchar) as order_id,
        carrier,
        cast(ship_date as date) as ship_date,
        cast(delivery_date as date) as delivery_date,
        cast(freight_cost as numeric) as freight_cost,
        cast(on_time as boolean) as source_on_time_flag
    from tms_shipments
),

inventory as (
    select
        sku,
        warehouse,
        cast(on_hand_units as numeric) as on_hand_units,
        cast(average_daily_demand as numeric) as average_daily_demand,
        cast(reorder_point_units as numeric) as reorder_point_units,
        cast(unit_cost as numeric) as unit_cost,
        cast(trailing_90d_cogs as numeric) as trailing_90d_cogs,
        cast(average_inventory_value as numeric) as average_inventory_value
    from wms_inventory
),

order_fulfillment as (
    select
        orders.order_id,
        orders.customer_id,
        orders.order_date,
        orders.promised_date,
        orders.sku,
        orders.warehouse,
        coalesce(shipments.carrier, 'NO_SHIPMENT') as carrier,
        shipments.ship_date,
        shipments.delivery_date,
        orders.units_ordered,
        orders.units_shipped,
        greatest(orders.units_ordered - orders.units_shipped, 0) as backorder_units,
        orders.units_shipped / nullif(orders.units_ordered, 0) as fill_rate,
        case when orders.units_shipped >= orders.units_ordered then true else false end as in_full,
        case when shipments.delivery_date <= orders.promised_date then true else false end as delivered_on_time,
        case
            when orders.units_shipped >= orders.units_ordered
                and shipments.delivery_date <= orders.promised_date
            then true
            else false
        end as otif,
        coalesce(shipments.freight_cost, 0) as freight_cost,
        coalesce(shipments.freight_cost, 0) / nullif(orders.units_shipped, 0) as freight_cost_per_shipped_unit,
        datediff(day, orders.order_date, shipments.ship_date) as days_to_ship,
        datediff(day, orders.order_date, shipments.delivery_date) as lead_time_days,
        inventory.on_hand_units,
        inventory.average_daily_demand,
        inventory.reorder_point_units,
        inventory.on_hand_units / nullif(inventory.average_daily_demand, 0) as days_of_inventory,
        case
            when inventory.on_hand_units <= 0
                or inventory.on_hand_units < inventory.reorder_point_units
            then true
            else false
        end as stockout_risk,
        inventory.trailing_90d_cogs / nullif(inventory.average_inventory_value, 0) as inventory_turnover_90d
    from orders
    left join shipments
        on orders.order_id = shipments.order_id
    left join inventory
        on orders.sku = inventory.sku
        and orders.warehouse = inventory.warehouse
),

control_tower_mart as (
    select
        *,
        case
            when units_shipped = 0
                or (backorder_units > 0 and stockout_risk)
            then 'high'
            when backorder_units > 0
                or not delivered_on_time
            then 'medium'
            when stockout_risk then 'monitor'
            else 'normal'
        end as exception_priority
    from order_fulfillment
)

select
    count(*) as total_orders,
    sum(units_shipped) / nullif(sum(units_ordered), 0) as fill_rate,
    avg(case when otif then 1.0 else 0.0 end) as otif_rate,
    avg(case when delivered_on_time then 1.0 else 0.0 end) as service_level,
    sum(backorder_units) as backorder_units,
    count(distinct case when stockout_risk then sku || ':' || warehouse end) as stockout_or_reorder_risk_sku_locations,
    avg(lead_time_days) as avg_lead_time_days,
    sum(freight_cost) as total_freight_cost,
    sum(freight_cost) / nullif(sum(units_shipped), 0) as freight_cost_per_shipped_unit,
    sum(case when exception_priority = 'high' then 1 else 0 end) as high_priority_exceptions
from control_tower_mart;

-- Carrier scorecard for logistics review.
with control_tower_mart as (
    select
        orders.order_id,
        coalesce(shipments.carrier, 'NO_SHIPMENT') as carrier,
        orders.units_ordered,
        orders.units_shipped,
        case when shipments.delivery_date <= orders.promised_date then true else false end as delivered_on_time,
        case
            when orders.units_shipped >= orders.units_ordered
                and shipments.delivery_date <= orders.promised_date
            then true
            else false
        end as otif,
        coalesce(shipments.freight_cost, 0) as freight_cost
    from erp_orders as orders
    left join tms_shipments as shipments
        on orders.order_id = shipments.order_id
)
select
    carrier,
    count(*) as orders,
    avg(case when delivered_on_time then 1.0 else 0.0 end) as on_time_delivery_rate,
    avg(case when otif then 1.0 else 0.0 end) as otif_rate,
    sum(freight_cost) as freight_cost,
    sum(freight_cost) / nullif(sum(units_shipped), 0) as freight_cost_per_shipped_unit
from control_tower_mart
group by 1;

-- Validation queries should return zero rows before dashboard consumption.

-- 1. ERP order grain should be unique.
select order_id, count(*) as row_count
from erp_orders
group by 1
having count(*) > 1;

-- 2. Shipments should reference valid ERP orders.
select shipments.*
from tms_shipments as shipments
left join erp_orders as orders
    on shipments.order_id = orders.order_id
where orders.order_id is null;

-- 3. Shipped orders should have a TMS shipment record.
select orders.*
from erp_orders as orders
left join tms_shipments as shipments
    on orders.order_id = shipments.order_id
where orders.units_shipped > 0
    and shipments.order_id is null;

-- 4. Fill quantities should not exceed ordered quantities.
select *
from erp_orders
where units_shipped < 0
    or units_ordered < 0
    or units_shipped > units_ordered;

-- 5. Delivery chronology should move forward.
select shipments.*
from tms_shipments as shipments
join erp_orders as orders
    on shipments.order_id = orders.order_id
where shipments.delivery_date < shipments.ship_date
    or shipments.delivery_date < orders.order_date;

-- 6. TMS on-time flag should agree with promised date.
select shipments.*
from tms_shipments as shipments
join erp_orders as orders
    on shipments.order_id = orders.order_id
where shipments.on_time <> (shipments.delivery_date <= orders.promised_date);
