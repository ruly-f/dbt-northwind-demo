{{
    config(
        enabled = false
    )
}}

{% set old_query %} -- Legacy (A)
    select
        order_id
        , customer_id
        , order_date
        , status
        , amount
    from legacu_database.legacy_schema.stg_example_table_1
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
