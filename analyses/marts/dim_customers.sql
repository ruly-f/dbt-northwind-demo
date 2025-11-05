with
    fonte_customers as (
        select *
        from {{ ref('stg_erp__customers') }}
    )

select *
from fonte_customers
-- add
-- add