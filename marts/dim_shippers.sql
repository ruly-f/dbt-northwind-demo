with
    stg_shippers as (
        select *
        from {{ ref('stg_erp__shippers') }}
    )

select *
from stg_shippers