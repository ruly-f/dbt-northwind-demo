{% set yaml_metadata %}
source_model: stg_erp__order_items
derived_columns:
    RECORD_SOURCE: "!ERP-ORDER_DETAILS"
    LOAD_DATE: dateadd(DAY, 15, current_timestamp())
    EFFECTIVE_FROM: current_timestamp()
hashed_columns:
    ORDER_ITEM_HK:
      - order_fk
      - product_fk
    ORDER_HK: order_fk
    PRODUCT_HK: product_fk
    ORDER_ITEM_HASHDIFF:
      is_hashdiff: true
      columns:
       - order_fk
       - product_fk
       - discount_pct
       - unit_price
       - quantity
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
