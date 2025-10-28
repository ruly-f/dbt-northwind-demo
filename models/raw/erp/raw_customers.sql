with
    source_customers as (
        select *
        from {{ source('erp', 'customer') }}
    )

    , renamed as (
        select
            cast(id as varchar) as customer_pk
            , cast(companyname as varchar) as customer_company_name
            , cast(city as varchar) as customer_city
            , cast(region as varchar) as customer_region
            , cast(country as varchar) as customer_country
        from source_customers
    )

select *
from renamed
