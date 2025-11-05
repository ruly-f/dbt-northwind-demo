with
    dim_products as (
        select *
        from {{ ref('int_products__enriched') }}
    )

select *
from dim_products
