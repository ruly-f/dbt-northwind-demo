with
    order_items_metrics as (
        select *
        from {{ ref('int_order_items__metrics') }}
    )

select *
from order_items_metrics
