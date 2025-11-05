with
    source_shippers as (
        select *
        from {{ ref('base_erp__shippers') }}
    )

    , renamed as (
        select
            cast(id as int) as shipper_pk
            , cast(companyname as varchar) as shipper_name
            , cast(load_ts as timestamp) as load_ts
        from source_shippers
    )

select *
from renamed
