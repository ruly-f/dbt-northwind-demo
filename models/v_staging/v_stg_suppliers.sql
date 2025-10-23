{% set yaml_metadata %}
source_model: stg_erp__suppliers
derived_columns:
    RECORD_SOURCE: "!ERP-SUPPLIERS"
    LOAD_DATE: dateadd(DAY, -15, current_timestamp())
    EFFECTIVE_FROM: current_timestamp()
hashed_columns:
    SUPPLIER_HK: supplier_pk
    SUPPLIER_HASHDIFF:
      is_hashdiff: true
      columns:
       - supplier_name
       - supplier_city
       - supplier_country
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