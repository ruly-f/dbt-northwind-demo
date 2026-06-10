{{
    config(
        enabled = false
    )
}}

/*
    Template: vld_2 — which columns differ (audit_helper.compare_which_query_columns_differ)
    Output  : one row per column with has_difference true/false (binary; doesn't show magnitude)
    Next    : feed the columns flagged true into vld_3 to see how badly each one diverges
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
    audit_helper.compare_which_query_columns_differ(
        a_query = old_query,
        b_query = new_query,
        primary_key_columns = ['order_id'],
        columns = [
            'customer_id',
            'order_date',
            'status',
            'amount'
        ]
    )
}}
