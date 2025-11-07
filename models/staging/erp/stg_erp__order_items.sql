{{
    config(
        materialized='incremental',
        unique_key='order_item_sk',
        on_schema_change='append_new_columns'
    )
}}

with
    source_order_details as (
        select *
        from {{ source('erp', 'orders_detail') }}
        where load_ts = '{{ var('load_date') }}'
        {% if is_incremental() %}
            and load_ts::timestamp > (select max(load_ts) from {{ this }} )
        {% endif %}
    )

    , renamed as (
        select
            {{ dbt_utils.generate_surrogate_key([
                'orderid'
                , 'productid'
            ]) }} as order_item_sk
            , cast(orderid as int) as order_fk
            , cast(productid as int) as product_fk
            , cast(discount as numeric(18,2)) as discount_pct
            , cast(unitprice as numeric(18,2)) as unit_price
            , cast(quantity as int) as quantity
            , cast(load_ts as timestamp) as load_ts
            , cast(load_ts as timestamp) + interval '2 hours' as insert_ts
        from source_order_details
    )

select *
from renamed
