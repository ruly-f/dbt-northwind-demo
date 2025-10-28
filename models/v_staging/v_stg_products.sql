{% set yaml_metadata %}
source_model: raw_products
derived_columns:
    RECORD_SOURCE: "!ERP-PRODUCTS"
    LOAD_DATE: dateadd(DAY, 15, current_timestamp())
    EFFECTIVE_FROM: current_timestamp()
hashed_columns:
    PRODUCT_HK: product_pk
    CATEGORY_HK: category_fk
    SUPPLIER_HK: supplier_fk
    PRODUCT_CATEGORY_HK:
      - product_pk
      - category_fk
    PRODUCT_SUPPLIER_HK:
      - product_pk
      - supplier_fk
    PRODUCT_HASHDIFF:
      is_hashdiff: true
      columns:
       - product_pk
       - product_name
       - quantity_per_unit
       - unit_price
       - units_in_stock
       - units_on_order
       - reorder_level
       - is_discontinued
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
