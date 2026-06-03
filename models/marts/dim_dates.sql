with
    dim_dates as (
        select *
        from {{ ref('int_dates') }}
    )

select *
from dim_dates
