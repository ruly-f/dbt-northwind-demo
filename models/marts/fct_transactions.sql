with
    transactions as (
        select *
        from {{ ref('int_order_items__metrics') }}
    )

select *
from transactions
