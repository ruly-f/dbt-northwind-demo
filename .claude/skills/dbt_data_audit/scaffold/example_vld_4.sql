{{
    config(
        enabled = false
    )
}}

/*
    Template: vld_4 — row-level classification (audit_helper.compare_and_classify_query_results)
    Output  : sample rows classified as unchanged / added / removed / modified, with summary counts
    Next    : inspect 'modified' rows to see the actual (A_value, B_value) pair side-by-side
    Tip     : scope the columns list to ONE column at a time for sharper samples; raise sample_limit if patterns aren't obvious
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

{{
    audit_helper.compare_and_classify_query_results(
        old_query,
        new_query,
        primary_key_columns = ['order_id'],
        columns = ['customer_id', 'order_date', 'amount', 'status']
    )
}}
