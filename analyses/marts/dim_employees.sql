with
    dim_employee as (
        select *
        from {{ ref('int_employee__self_join_for_manager') }}
    )

select *
from dim_employee
-- add
