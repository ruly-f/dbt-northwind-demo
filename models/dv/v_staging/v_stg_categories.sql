{{
    config(
        materialized='incremental'
        , unique_key=['category_pk', 'load_ts']
    )
}}

{% set yaml_metadata %}
source_model: raw_categories
derived_columns:
    RECORD_SOURCE: "!ERP-CATEGORIES"
    LOAD_DATE: load_ts
    EFFECTIVE_FROM: load_ts
hashed_columns:
    CATEGORY_HK: category_pk
    CATEGORY_HASHDIFF:
      is_hashdiff: true
      columns:
       - category_pk
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

{% if is_incremental %}

where load_ts > (select coalesce(max(load_ts), '1900-01-01') from {{ this }} )

{% endif %}
