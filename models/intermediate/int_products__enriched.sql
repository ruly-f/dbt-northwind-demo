with
    hub_products as (
        select *
        from {{ ref('hub_products') }}
    )

    , sat_products as (
        select *
        from {{ ref('sat_products') }}
    )

    , link_products_categories as (
        select *
        from {{ ref('link_products_categories') }}
    )

    , link_products_suppliers as (
        select *
        from {{ ref('link_products_suppliers') }}
    )

    , sat_categories as (
        select *
        from {{ ref('sat_categories_details') }}
    )

    , sat_suppliers as (
        select *
        from {{ ref('sat_suppliers_details') }}
    )
    
    , enrich_products as (
        select
            hub_products.product_hk
            , sat_products.product_name
            , sat_products.quantity_per_unit
            , sat_products.unit_price
            , sat_products.units_in_stock
            , sat_products.units_on_order
            , sat_products.reorder_level
            , sat_products.is_discontinued
            , sat_categories.category_name
            , sat_suppliers.supplier_name
            , sat_suppliers.supplier_city
            , sat_suppliers.supplier_country 
        from hub_products
        left join sat_products
            on hub_products.product_hk = sat_products.product_hk
        left join link_products_categories
            on hub_products.product_hk = link_products_categories.product_hk
        left join sat_categories
            on link_products_categories.category_hk = sat_categories.category_hk
        left join link_products_suppliers
            on hub_products.product_hk = link_products_suppliers.product_hk
        left join sat_suppliers
            on link_products_suppliers.supplier_hk = sat_suppliers.supplier_hk
    )

select *
from enrich_products
