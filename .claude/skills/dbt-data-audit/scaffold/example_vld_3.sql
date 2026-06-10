{{
    config(
        enabled = false
    )
}}

/*
    Template: vld_3 — per-column statistics (audit_helper.compare_column_values, looped)
    Output  : for each column, counts of perfect match / both null / null in one only / missing / values differ
    Next    : use patterns.md to diagnose the dominant category, then standardize the legacy side and re-run.
              if values-differ remains stubborn, scope vld_4 to that single column for row-level samples
    Note    : loops over column_list; long lists generate long queries — keep this scoped to problem columns from vld_2
*/

{% set old_query %} -- Legacy (A)
    select
        order_id
        , customer_id
        , order_date
        , status
        , amount
    from legacy_database.legacy_schema.stg_example_table_1
{% endset %}

{% set new_query %} -- New table (B)
    select
        order_id
        , customer_id
        , order_date
        , status
        , amount
    from {{ ref('stg_example_table_1') }}
{% endset %}

{% set column_list = [
    'customer_id',
    'order_date',
    'status',
    'amount'
] %}

{% for column in column_list %}

    (
        {{ audit_helper.compare_column_values(
            a_query = old_query,
            b_query = new_query,
            primary_key = "order_id",
            column_to_compare = column
        ) }}
    )

    {% if not loop.last %}
        union all
    {% endif %}

{% endfor %}
