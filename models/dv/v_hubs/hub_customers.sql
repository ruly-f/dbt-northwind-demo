{{
    config(
        materialized='incremental'
        , unique_key=['customer_pk', 'load_date']
        , incremental_strategy='merge'
        , on_schema_change='sync_all_columns'
    )
}}

{%- set source_model = "v_stg_customers" -%}
{%- set src_pk = "CUSTOMER_HK" -%}
{%- set src_nk = "customer_pk" -%}
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

{% if is_incremental %}

where load_date > (select coalesce(max(load_date), '1900-01-01') from {{ this }} )

{% endif %}
