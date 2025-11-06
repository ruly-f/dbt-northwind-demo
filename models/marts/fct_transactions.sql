with
    order_items_metrics as (
        select *
        from {{ ref('int_transactions') }}
    )

select *
from order_items_metrics
