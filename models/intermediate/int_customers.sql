with
    hub_customers as (
        select *
        from {{ ref('hub_customers') }}
    )

    , sat_customers_details as (
        select *
        from {{ ref('sat_customers_details') }}
    )

    , joined as (
        select
            hub_customers.customer_hk
            , sat_customers_details.hashdiff as customer_hashdiff
            , hub_customers.customer_pk
            , sat_customers_details.customer_company_name
            , sat_customers_details.customer_contact_name
            , sat_customers_details.customer_contact_title
            , sat_customers_details.customer_address
            , sat_customers_details.customer_city
            , sat_customers_details.customer_region
            , sat_customers_details.customer_country
            , sat_customers_details.customer_postal_code
            , sat_customers_details.customer_phone
            , sat_customers_details.customer_fax
            , sat_customers_details.effective_from
            , sat_customers_details.load_date
        from hub_customers
        left join sat_customers_details
            on hub_customers.customer_hk = sat_customers_details.customer_hk
    )

    , ordered as (
        select
            customer_hk
            , customer_hashdiff
            , customer_pk
            , customer_company_name
            , customer_contact_name
            , customer_contact_title
            , customer_address
            , customer_city
            , customer_region
            , customer_country
            , customer_postal_code
            , customer_phone
            , customer_fax
            , effective_from as start_date
            , lead(effective_from) over (
                partition by customer_hk
                order by effective_from
            ) as next_effective_from
            , row_number() over (
                partition by customer_hk
                order by effective_from
            ) as version_number
            , load_date
        from joined
    )

    , end_date_rule as (
        select
            customer_hk
            , customer_hashdiff
            , customer_pk
            , customer_company_name
            , customer_contact_name
            , customer_contact_title
            , customer_address
            , customer_city
            , customer_region
            , customer_country
            , customer_postal_code
            , customer_phone
            , customer_fax
            , load_date
            , case 
                when version_number = 1
                    then cast('1970-01-01' as date)
                else start_date
            end as start_date
            , coalesce(
                dateadd(day, -1, next_effective_from)
                , cast('9999-12-12' as date)
            ) as end_date
        from ordered
    )

select *
from end_date_rule
