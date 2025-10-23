{% set yaml_metadata %}
source_model: stg_erp__categories
derived_columns:
    RECORD_SOURCE: "!ERP-CATEGORIES"
    LOAD_DATE: dateadd(DAY, -15, current_timestamp())
    EFFECTIVE_FROM: current_timestamp()
hashed_columns:
    CATEGORY_HK: category_pk
    CATEGORY_HASHDIFF:
      is_hashdiff: true
      columns:
       - category_name
       - category_description
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