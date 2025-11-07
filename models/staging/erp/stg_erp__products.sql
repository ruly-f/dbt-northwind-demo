{{
    config(
        materialized='incremental',
        unique_key='product_hk',
        on_schema_change='append_new_columns'
    )
}}

with
    source_products as (
        select *
        from {{ source('erp', 'products') }}
        where load_ts = '{{ var('load_date') }}'
        {% if is_incremental() %}
            and load_ts::timestamp > (select max(load_ts) from {{ this }} )
        {% endif %}
    )

    , renamed as (
        select
            {{ dbt_utils.generate_surrogate_key([
                'id',
                'supplierid',
                'categoryid',
                'productname',
                'quantityperunit',
                'unitprice',
                'unitsinstock',
                'unitsonorder',
                'reorderlevel',
                'discontinued'
            ]) }} as product_hk
            , cast(id as int) as product_pk
            , cast(supplierid as int) as supplier_fk
            , cast(categoryid as int) as category_fk
            , cast(productname as string) as product_name
            , cast(quantityperunit as string) as quantity_per_unit
            , cast(unitprice as numeric(18,2)) as unit_price
            , cast(unitsinstock as int) as units_in_stock
            , cast(unitsonorder as int) as units_on_order
            , cast(reorderlevel as int) as reorder_level
            , discontinued as is_discontinued
            , cast(load_ts as timestamp) as load_ts
            , cast(load_ts as timestamp) + interval '2 hours' as insert_ts
        from source_products
    )

select *
from renamed
