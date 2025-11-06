with
    dim_employee as (
        select *
        from {{ ref('int_employee__manager_self_join') }}
    )

select *
from dim_employee
