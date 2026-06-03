with
    orders_metrics as (
        select *
        from {{ ref('int_orders__metrics') }}
    )

select *
from orders_metrics
