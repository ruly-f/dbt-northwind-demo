{{
    config(
        materialized='incremental',
        unique_key='customer_hk',
        on_schema_change='append_new_columns'
    )
}}

with
    {% if is_incremental() %}

    delta_customers as (
        select *
        from {{ ref('stg_erp__customers') }}
        where load_ts::timestamp > (select max(load_ts) from {{ this }} )
    )


    , historic_customers as (
        select *
        from {{ this }}
        where customer_pk in (select customer_pk from delta_customers)
    )

    , customers as (
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
            , null as customer_active
            , load_ts
            , insert_ts
            , null as valid_from
            , null as valid_to
        from delta_customers
        union all
        select *
        from historic_customers
    )

    {% else %}

    customers as (
        select *
        from {{ ref('stg_erp__customers') }}
    )

    {% endif %}

    , interval_customers as (
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
            , case 
                when row_number() over(
                    partition by customer_pk
                    order by insert_ts desc
                    ) = 1 then true
                else false
            end as customer_active
            , load_ts
            , insert_ts
            , case 
                when row_number() over (partition by customer_pk order by insert_ts) = 1 then '1970-01-01'
                else insert_ts
            end as valid_from
            , coalesce(
                lead(insert_ts, 1) over (
                    partition by customer_pk
                    order by insert_ts
                ) - interval '1 day'
                , '2099-01-01'
            ) as valid_to
        from customers
    )

select *
from interval_customers
