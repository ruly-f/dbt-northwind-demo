{{
    config(
        materialized='incremental',
        unique_key='product_hk',
        on_schema_change='append_new_columns'
    )
}}

with
    {% if is_incremental() %}

    delta_products as (
        select *
        from {{ ref('stg_erp__products') }}
        where load_ts::timestamp > (select max(load_ts) from {{ this }} )
    )


    , historic_products as (
        select *
        from {{ this }}
        where product_pk in (select product_pk from delta_products)
    )

    , products as (
        select
            product_hk
            , product_pk
            , supplier_fk
            , category_fk
            , product_name
            , quantity_per_unit
            , unit_price
            , units_in_stock
            , units_on_order
            , reorder_level
            , is_discontinued
            , null as product_active
            , load_ts
            , insert_ts
            , null as valid_from
            , null as valid_to
        from delta_products
        union all
        select *
        from historic_products
    )

    {% else %}

    products as (
        select *
        from {{ ref('stg_erp__products') }}
    )

    {% endif %}

    , interval_products as (
        select
            product_hk
            , product_pk
            , supplier_fk
            , category_fk
            , product_name
            , quantity_per_unit
            , unit_price
            , units_in_stock
            , units_on_order
            , reorder_level
            , is_discontinued
            , case 
                when row_number() over(
                    partition by product_pk
                    order by insert_ts desc
                ) = 1 then true
                else false
            end as product_active
            , load_ts
            , insert_ts
            , case 
                when row_number() over (partition by product_pk order by insert_ts) = 1 then timestamp '1970-01-01 00:00:00'
                else insert_ts
            end as valid_from
            , coalesce(
                lead(insert_ts, 1) over (
                    partition by product_pk
                    order by insert_ts
                ) - interval '1 day'
                , '2099-01-01'
            ) as valid_to
        from products
    )

select *
from interval_products
