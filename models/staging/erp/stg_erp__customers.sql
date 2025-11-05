{{
    config(
        materialized='incremental',
        unique_key='customer_hk',
        on_schema_change='append_new_columns'
    )
}}

with
    source_customers as (
        select *
        from {{ ref('base_erp__customers') }}
        {% if is_incremental() %}
            where load_ts::timestamp > (select max(load_ts) from {{ this }} )
        {% endif %}
    )

    , renamed as (
        select
            {{ dbt_utils.generate_surrogate_key([
                'id',
                'companyname',
                'city',
                'region',
                'country'
            ]) }} as customer_hk
            , cast(id as varchar) as customer_pk
            , cast(companyname as varchar) as customer_company_name
            , cast(city as varchar) as customer_city
            , cast(region as varchar) as customer_region
            , cast(country as varchar) as customer_country
            , cast(load_ts as timestamp) as load_ts
            , cast(load_ts as timestamp) + interval '2 hours' as insert_ts
        from source_customers
    )

select *
from renamed
