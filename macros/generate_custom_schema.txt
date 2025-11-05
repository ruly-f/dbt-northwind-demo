{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}
    
    {%- if custom_schema_name is not none and target.name in ('prd') -%}

        {{ custom_schema_name | trim }}

    {%- else -%}

        {{ default_schema }}

    {%- endif -%}

{%- endmacro %}