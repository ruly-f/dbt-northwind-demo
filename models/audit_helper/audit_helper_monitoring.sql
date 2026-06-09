{{
    config(
        materialized = 'incremental'
        , unique_key = 'ah_monitoring_sk'
        , full_refresh = true if var('override_full_refresh', 'no') == 'yes' else false
        , enabled = false
    )
}}
/*
    This is a monitoring table that generates a snapshot of how the matching % are everytime it runs.
*/
{% set validation_table_list = [] %}
{% set reference_list = [] %}

{%- for node in graph.nodes.values() -%}
    {%- if 'vld_1' in node.name and not node.name.startswith('stg_') -%}
        {%- do validation_table_list.append(node.name) -%}
    {%- endif -%}
{%- endfor %}

{%- for validation_table in validation_table_list %}
    {%- do reference_list.append(ref(validation_table)) -%}
{%- endfor %}

-- Add here all _vld1 models that this model depends on. Example:
/*
-- depends on: {{ ref('example_vld_1') }}
*/

with
    match_snapshot as (
        {%- for validation_table, reference in zip(validation_table_list, reference_list) %}
        select
            '{{ validation_table }}' as validation_table
            , current_date as match_analysis_check_date
            , cast(max(case when in_a = true and in_b = true then percent_of_total else 0.0 end) as decimal(10,4)) as equal
            , cast(max(case when in_a = true and in_b = false then percent_of_total else 0.0 end) as decimal(10,4)) as in_legacy__but_not_in_new
            , cast(max(case when in_a = false and in_b = true then percent_of_total else 0.0 end) as decimal(10,4)) as in_new__but_not_in_legacy
            , current_timestamp as match_analysis_check_ts
        from {{ reference }}
        {% if not loop.last -%}
        union all
        {%- endif -%}
        {%- endfor %}
    )

    , added_sk as (
        select
            {{ dbt_utils.generate_surrogate_key(['validation_table', 'match_analysis_check_date']) }} as ah_monitoring_sk
            , *
        from match_snapshot
    )

select *
from added_sk
