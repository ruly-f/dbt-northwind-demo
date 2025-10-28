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
            , hub_customers.customer_pk
            , sat_customers_details.customer_company_name
            , sat_customers_details.customer_city
            , sat_customers_details.customer_region
            , sat_customers_details.customer_country
        from hub_customers
        left join sat_customers_details
            on hub_customers.customer_hk = sat_customers_details.customer_hk
    )

select *
from joined
