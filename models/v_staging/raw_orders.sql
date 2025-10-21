with
    source_orders as (
        select *
        from {{ source('erp', 'orders') }}
    )

    , source_order_details as (
        select *
        from {{ source('erp', 'orders_detail') }}
    )

    , joining as (
        select
            cast(orders.id as int) as order_id
            , cast(order_details.productid as int) as product_id
            , cast(orders.employeeid as int) as employee_id
            , cast(orders.customerid as string) as customer_id
            , cast(orders.shipvia as int) as shipper_id
            , cast(orders.orderdate as date) as order_date
            , cast(orders.shippeddate as date) as ship_date
            , cast(orders.requireddate as date) as required_delivery_date
            , cast(order_details.discount as numeric(18,2)) as discount_pct
            , cast(order_details.unitprice as numeric(18,2)) as unit_price
            , cast(order_details.quantity as int) as quantity
            , cast(orders.freight as numeric) as freight
            , cast(orders.shipname as string) as recipient_name
            , cast(orders.shipcity as string) as recipient_city
            , cast(orders.shipregion as string) as recipient_region
            , cast(orders.shipcountry as string) as recipient_country
        from source_order_details as order_details
        inner join source_orders as orders
            on order_details.orderid = orders.id
    )

select *
from joining
