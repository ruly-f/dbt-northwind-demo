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
