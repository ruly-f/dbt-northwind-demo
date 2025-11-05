{{
    config(
        materialized='incremental',
        unique_key='order_item_sk',
        on_schema_change='append_new_columns'
    )
}}

with
    -- import ctes
    orders as (
        select *
        from {{ ref('stg_erp__orders') }}
        {% if is_incremental() %}
            where load_ts::timestamp > (select max(load_ts) from {{ this }} )
        {% endif %}
    )

    , order_items as (
        select *
        from {{ ref('stg_erp__order_items') }}
        {% if is_incremental() %}
            where load_ts::timestamp > (select max(load_ts) from {{ this }} )
        {% endif %}
    )

    , customers_snp as (
        select *
        from {{ ref('int_customer__snapshot') }}
        {% if is_incremental() %}
            where customer_pk in (select customer_pk from orders)
        {% endif %}
    )

    , products_snp as (
        select *
        from {{ ref('int_products__enriched') }}
        {% if is_incremental() %}
            where product_pk in (select product_fk from order_items)
        {% endif %}
    )

    -- transformation
    , metrics as (
        select
            order_items.order_item_sk
            --
            , customers_snp.customer_hk
            , products_snp.product_hk
            --
            , order_items.product_fk
            , orders.employee_fk
            , orders.customer_fk
            , orders.shipper_fk
            --
            , orders.order_date
            , orders.ship_date
            , orders.required_delivery_date
            , order_items.discount_pct
            , order_items.unit_price
            , order_items.quantity
            , orders.freight
            , order_items.unit_price * order_items.quantity as gross_total
            , order_items.unit_price * (1 - order_items.discount_pct) * order_items.quantity as net_total
            , cast((orders.freight / count(*) over (partition by orders.order_number)) as numeric(18,2)) as freight_allocated
            , case
                when order_items.discount_pct > 0 then true
                else false
            end as had_discount
            , orders.order_number
            , orders.recipient_name
            , orders.recipient_city
            , orders.recipient_region
            , orders.recipient_country
            , orders.load_ts
            , orders.insert_ts
        from order_items
        inner join orders on order_items.order_fk = orders.order_pk
        left join customers_snp
            on customers_snp.customer_pk = orders.customer_fk
            and orders.order_date between customers_snp.valid_from and customers_snp.valid_to
        left join products_snp
            on products_snp.product_pk = order_items.product_fk
            and orders.order_date between products_snp.valid_from and products_snp.valid_to
    )

select *
from metrics
