with
    source_customers as (
        select *
        from {{ source('erp', 'customer') }}
    )

    , renamed as (
        select
            cast(id as varchar) as customer_pk
            , cast(companyname as varchar) as customer_company_name
            , cast(contactname as varchar) as customer_contact_name
            , cast(contacttitle as varchar) as customer_contact_title
            , cast(address as varchar) as customer_address
            , cast(city as varchar) as customer_city
            , cast(region as varchar) as customer_region
            , cast(country as varchar) as customer_country
            , cast(postalcode as varchar) as customer_postal_code
            , cast(phone as varchar) as customer_phone
            , cast(fax as varchar) as customer_fax
            , cast(load_ts as timestamp) as load_ts
        from source_customers
    )

select *
from renamed
-- where load_ts <= '2014-05-05 00:00:00.000'