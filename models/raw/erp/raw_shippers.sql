with
    source_shippers as (
        select *
        from {{ source('erp', 'shippers') }}
    )

    , renamed as (
        select
            cast(id as int) as shipper_pk
            , cast(companyname as varchar) as shipper_name
        from source_shippers
    )

select *
from renamed
