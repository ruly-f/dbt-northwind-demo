{% set yaml_metadata %}
source_model: stg_erp__employees
derived_columns:
    RECORD_SOURCE: "!ERP-EMPLOYEES"
    LOAD_DATE: dateadd(DAY, -15, current_timestamp())
    EFFECTIVE_FROM: current_timestamp()
hashed_columns:
    EMPLOYEE_HK: employee_pk
    MANAGER_HK: manager_fk
    EMPLOYEE_HASHDIFF:
      is_hashdiff: true
      columns:
       - employee_name
       - employee_title
       - employee_birth_date
       - employee_hire_date
       - employee_city
       - employee_region
       - employee_country
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