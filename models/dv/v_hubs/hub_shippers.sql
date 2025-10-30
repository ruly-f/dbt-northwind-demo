{{
    config(materialized='incremental')
}}

{%- set source_model = "v_stg_shippers" -%}
{%- set src_pk = "SHIPPER_HK" -%}
{%- set src_nk = "shipper_pk" -%}
{%- set src_ldts = "LOAD_DATE" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ 
    automate_dv.hub(
        src_pk=src_pk,
        src_nk=src_nk,
        src_ldts=src_ldts,
        src_source=src_source,
        source_model=source_model
    )
}}