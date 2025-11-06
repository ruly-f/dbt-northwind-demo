{{
    config(
        materialized='incremental'
        , unique_key=['customer_pk', 'load_ts']
    )
}}

{% set yaml_metadata %}
source_model: raw_customers
derived_columns:
    RECORD_SOURCE: "!ERP-CUSTOMERS"
    LOAD_DATE: load_ts
    EFFECTIVE_FROM: load_ts
hashed_columns:
    CUSTOMER_HK: customer_pk
    CUSTOMER_HASHDIFF:
      is_hashdiff: true
      columns:
       - customer_pk
       - customer_company_name
       - customer_contact_name
       - customer_contact_title
       - customer_address
       - customer_city
       - customer_region
       - customer_country
       - customer_postal_code
       - customer_phone
       - customer_fax
{% endset %}

{% set metadata_dict = fromyaml(yaml_metadata) %}

{{
    automate_dv.stage(
        include_source_columns=true
        , source_model=metadata_dict['source_model']
        , derived_columns=metadata_dict['derived_columns']
        , null_columns=none
        , hashed_columns=metadata_dict['hashed_columns']
        , ranked_columns=none
    )
}}

{% if is_incremental %}

where load_ts > (select coalesce(max(load_ts), '1900-01-01') from {{ this }} )

{% endif %}

