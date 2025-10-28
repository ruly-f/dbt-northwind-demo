{% set yaml_metadata %}
source_model: raw_customers
derived_columns:
    RECORD_SOURCE: "!ERP-CUSTOMERS"
    LOAD_DATE: dateadd(DAY, -15, current_timestamp())
    EFFECTIVE_FROM: current_timestamp()
hashed_columns:
    CUSTOMER_HK: customer_pk
    CUSTOMER_HASHDIFF:
      is_hashdiff: true
      columns:
       - customer_pk
       - customer_company_name
       - customer_city
       - customer_region
       - customer_country
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