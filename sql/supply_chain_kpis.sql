-- Supply chain KPI examples

select
    count(*) as total_orders,
    sum(case when units_shipped = units_ordered then 1 else 0 end) * 1.0 / count(*) as fill_complete_order_rate
from erp_orders;

select
    carrier,
    avg(freight_cost) as avg_freight_cost,
    sum(case when on_time then 1 else 0 end) * 1.0 / count(*) as on_time_delivery_rate
from tms_shipments
group by carrier;
