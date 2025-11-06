with
    sat_orders as (
        select *
        from {{ ref('sat_orders') }}
    )

    , sat_order_items as (
        select *
        from {{ ref('sat_order_items') }}
    )

    , link_orders_products as (
        select *
        from {{ ref('link_orders_products') }}
    )

    , link_orders_customers as (
        select *
        from {{ ref('link_orders_customers') }}
    )

    , link_orders_employees as (
        select *
        from {{ ref('link_orders_employees') }}
    )

    , link_orders_shippers as (
        select *
        from {{ ref('link_orders_shippers') }}
    )

    , int_customers as (
        select *
        from {{ ref('int_customers') }}
    )

    , joined as (
        select
            /* Primary Link Keys */
            link_orders_products.order_item_hk
            , link_orders_products.order_hk
            , link_orders_products.product_hk
            /* Secondary Link Keys */
            , link_orders_employees.employee_hk
            , link_orders_customers.customer_hk
            , int_customers.customer_hashdiff
            , link_orders_shippers.shipper_hk
            /* Satellite Attributes */
            , sat_orders.order_date
            , sat_orders.ship_date
            , sat_orders.required_delivery_date
            , sat_order_items.discount_pct
            , sat_order_items.unit_price
            , sat_order_items.quantity
            , sat_orders.freight
            , sat_orders.order_number
            , sat_orders.recipient_name
            , sat_orders.recipient_city
            , sat_orders.recipient_region
            , sat_orders.recipient_country
            , sat_orders.load_date
            , sat_orders.effective_from
        from link_orders_products
        left join sat_order_items
            on link_orders_products.order_item_hk = sat_order_items.order_item_hk
        left join sat_orders
            on link_orders_products.order_hk = sat_orders.order_hk
        left join link_orders_customers
            on link_orders_products.order_hk = link_orders_customers.order_hk
        left join link_orders_employees
            on link_orders_products.order_hk = link_orders_employees.order_hk
        left join link_orders_shippers
            on link_orders_products.order_hk = link_orders_shippers.order_hk
        left join int_customers
            on link_orders_customers.customer_hk = int_customers.customer_hk
            and sat_orders.order_date between int_customers.start_date and int_customers.end_date
    )

    , metrics as (
        select 
            order_item_hk
            , order_hk
            , product_hk
            , employee_hk
            , customer_hk
            , customer_hashdiff
            , shipper_hk
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
                when discount_pct > 0
                    then true
                else false
            end as had_discount
            , order_number
            , recipient_name
            , recipient_city
            , recipient_region
            , recipient_country
            , effective_from
            , load_date
        from joined
    )

select *
from metrics
