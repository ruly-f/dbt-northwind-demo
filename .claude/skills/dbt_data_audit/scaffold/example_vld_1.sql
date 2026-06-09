{{
    config(
        enabled = false
    )
}}

/*
    Template: vld_1 — summary match (audit_helper.compare_queries)
    Output  : % of rows that are equal, only in A (legacy), only in B (new)
    Next    : if equal % < 98, copy this file's old/new queries into vld_2 to find which columns differ
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
    audit_helper.compare_queries(
        a_query = old_query,
        b_query = new_query,
        primary_key = "order_id",
    )
}}
