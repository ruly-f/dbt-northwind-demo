{{
    config(
        materialized='incremental'
        , unique_key='order_pk'
    )
}}

{% set yaml_metadata %}
source_model: raw_orders
derived_columns:
    RECORD_SOURCE: "!ERP-ORDERS"
    LOAD_DATE: load_ts
    EFFECTIVE_FROM: load_ts
hashed_columns:
    ORDER_HK: order_pk
    CUSTOMER_HK: customer_fk
    EMPLOYEE_HK: employee_fk
    SHIPPER_HK: shipper_fk
    ORDER_CUSTOMER_HK:
      - order_pk
      - customer_fk
    ORDER_EMPLOYEE_HK:
      - order_pk
      - employee_fk
    ORDER_SHIPPER_HK:
      - order_pk
      - shipper_fk
    ORDER_HASHDIFF:
      is_hashdiff: true
      columns:
       - order_number
       - order_date
       - ship_date
       - required_delivery_date
       - freight
       - recipient_name
       - recipient_city
       - recipient_region
       - recipient_country
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