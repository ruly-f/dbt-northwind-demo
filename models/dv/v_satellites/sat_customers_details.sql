{{
    config(materialized='incremental')
}}

{%- set yaml_metadata -%}
source_model: "v_stg_customers"
src_pk: "CUSTOMER_HK"
src_hashdiff: 
  source_column: "CUSTOMER_HASHDIFF"
  alias: "HASHDIFF"
src_payload:
  - customer_company_name
  - customer_contact_name
  - customer_contact_title
  - customer_address
  - customer_city
  - customer_region
  - customer_country
  - customer_postal_code
  - customer_phone
  - customer_fax
src_eff: "EFFECTIVE_FROM"
src_ldts: "LOAD_DATE"
src_source: "RECORD_SOURCE"
{%- endset -%}

{% set metadata_dict = fromyaml(yaml_metadata) %}

{{
    automate_dv.sat(
        src_pk=metadata_dict["src_pk"],
        src_hashdiff=metadata_dict["src_hashdiff"],
        src_payload=metadata_dict["src_payload"],
        src_eff=metadata_dict["src_eff"],
        src_ldts=metadata_dict["src_ldts"],
        src_source=metadata_dict["src_source"],
        source_model=metadata_dict["source_model"]
    )
}}