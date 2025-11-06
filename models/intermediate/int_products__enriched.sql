with
    -- Import CTEs
    products as (
        select *
        from {{ ref('int_products__snapshot') }}
    )

    , categories as (
        select *
        from {{ ref('snp_erp__categories') }}
        where dbt_valid_to is null
    )

    , suppliers as (
        select *
        from {{ ref('snp_erp__suppliers') }}
        where dbt_valid_to is null
    )

    -- Joined
    , enrich_products as (
        select
            products.product_hk
            , products.product_pk
            , products.supplier_fk
            , products.category_fk
            , products.product_name
            , products.quantity_per_unit
            , products.unit_price
            , products.units_in_stock
            , products.units_on_order
            , products.reorder_level
            , products.is_discontinued
            , products.product_active
            , categories.category_name
            , suppliers.supplier_name
            , suppliers.supplier_city
            , suppliers.supplier_country 
            , products.load_ts
            , products.insert_ts
            , products.valid_from
            , products.valid_to
        from products
        left join categories on products.category_fk = categories.category_pk
        left join suppliers on products.supplier_fk = suppliers.supplier_pk
    )

select *
from enrich_products
