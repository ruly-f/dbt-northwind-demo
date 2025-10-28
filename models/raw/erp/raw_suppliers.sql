with
    source_suppliers as (
        select *
        from {{ source('erp', 'suppliers') }}
    )

    , renamed as (
        select
            cast(id as int) as supplier_pk
            , cast(companyname as varchar) as supplier_name
            , cast(city as varchar) as supplier_city
            , cast(country as varchar) as supplier_country
        from source_suppliers
    )

select *
from renamed
