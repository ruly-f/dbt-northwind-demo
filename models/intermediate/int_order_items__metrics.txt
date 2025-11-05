with
    orders as (
        select *
        from {{ ref('stg_erp__orders') }}
    )

    , order_items as (
        select *
        from {{ ref('stg_erp__order_items') }}
    )

    , joined as (
        select
            order_items.order_item_sk
            , order_items.product_fk
            , orders.employee_fk
            , orders.customer_fk
            , orders.shipper_fk
            , orders.order_date
            , orders.ship_date
            , orders.required_delivery_date
            , order_items.discount_pct
            , order_items.unit_price
            , order_items.quantity
            , orders.freight
            , orders.order_number
            , orders.recipient_name
            , orders.recipient_city
            , orders.recipient_region
            , orders.recipient_country
        from order_items
        inner join orders on order_items.order_fk = orders.order_pk
    )

    , metrics as (
        select 
            order_item_sk
            , product_fk
            , employee_fk
            , customer_fk
            , shipper_fk
            , order_date
            , ship_date
            , required_delivery_date
            , discount_pct
            , unit_price
            , quantity
            , freight
            , unit_price * quantity as gross_total
            , unit_price * (1 - discount_pct) * quantity as net_total
            , cast((freight / count(*) over (partition by order_number)) as numeric(18,2)) as freight_allocated
            , case
                when discount_pct > 0 then true
                else false
            end as had_discount
            , order_number
            , recipient_name
            , recipient_city
            , recipient_region
            , recipient_country
        from joined
    )

select *
from metrics
