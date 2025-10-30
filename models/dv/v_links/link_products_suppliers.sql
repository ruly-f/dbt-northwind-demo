{{
    config(materialized='incremental')
}}

{%- set source_model = "v_stg_products" -%}
{%- set src_pk = "PRODUCT_SUPPLIER_HK" -%}
{%- set src_fk = ["PRODUCT_HK", "SUPPLIER_HK"] -%}
{%- set src_ldts = "LOAD_DATE" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{
    automate_dv.link(
        src_pk=src_pk
        , src_fk=src_fk
        , src_ldts=src_ldts
        , src_source=src_source
        , source_model=source_model
    )
}}