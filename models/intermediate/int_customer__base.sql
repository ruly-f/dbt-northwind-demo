with
    --import ctes
    src_customers_erp as (
        select
            customer_hk
            , customer_pk
            , customer_company_name
            , customer_city
            , customer_region
            , customer_country
            , customer_postal_code
            , customer_phone
            , customer_fax
            , load_ts
            , insert_ts
        from {{ ref('stg_erp__customers') }} 
    )
    
    , src_customers_crm as (
        select
            customer_hk
            , customer_pk
            , customer_company_name
            , customer_city
            , customer_country
            , 'MockColumn' as customer_tier
            , customer_phone
            , customer_fax
            , load_ts
            , insert_ts
        from {{ ref('stg_erp__customers') }}
        where false
    )

    -- schema compatibilization
    , union_customers as (
        select
            customer_hk
            , customer_pk
            , customer_company_name
            , customer_city
            , customer_region
            , customer_country
            , customer_postal_code
            , customer_phone
            , customer_fax
            , null as customer_tier
            , load_ts
            , insert_ts
        from src_customers_erp
        union all
        select
            customer_hk
            , customer_pk
            , customer_company_name
            , customer_city
            , null as customer_region
            , customer_country
            , null as customer_postal_code
            , customer_phone
            , customer_fax
            , customer_tier
            , load_ts
            , insert_ts
        from src_customers_crm
    )

select *
from union_customers
