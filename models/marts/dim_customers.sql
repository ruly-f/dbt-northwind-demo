with
    int_customers as (
        select
            *
            , row_number() over(partition by customer_hk order by start_date desc) as ordering
        from {{ ref('int_customers') }}
    )

    , active_profile_rule as (
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
            , case
                when ordering = 1
                    then true
                else false
            end as active_profile
            , load_date
            , start_date
            , end_date
        from int_customers
    )

select *
from active_profile_rule
