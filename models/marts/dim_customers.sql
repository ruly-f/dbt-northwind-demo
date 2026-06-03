with
    customers as (
        select *
        from {{ ref('stg_erp__customers') }}
    )

select *
from customers
