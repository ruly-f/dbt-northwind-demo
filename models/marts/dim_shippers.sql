with
    shippers as (
        select *
        from {{ ref('snp_erp__shippers') }}
        where dbt_valid_to is null
    )

select *
from shippers