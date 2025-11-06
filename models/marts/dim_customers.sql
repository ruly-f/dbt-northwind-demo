with
    fonte_customers as (
        select *
        from {{ ref('int_customer__snapshot') }}
    )

select *
from fonte_customers
