with
    -- call required staging models
    categories as (
        select *
        from {{ ref('stg_erp__categories') }}
    )

    , suppliers as (
        select *
        from {{ ref('stg_erp__suppliers') }}
    )

    , products as (
        select *
        from {{ ref('stg_erp__products') }}
    )

    , enrich_products as (
        select
            products.product_pk
            , products.product_name
            , products.quantity_per_unit
            , products.unit_price
            , products.units_in_stock
            , products.units_on_order
            , products.reorder_level
            , products.is_discontinued
            , categories.category_name
            , suppliers.supplier_name
            , suppliers.supplier_city
            , suppliers.supplier_country 
        from products
        left join categories on products.category_fk = categories.category_pk
        left join suppliers on products.supplier_fk = suppliers.supplier_pk
    )

select *
from enrich_products
