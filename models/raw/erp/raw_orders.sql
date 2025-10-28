with
    source_orders as (
        select *
        from {{ source('erp', 'orders') }}
    )

    , renamed as (
        select
            cast(id as int) as order_pk
            , cast(employeeid as int) as employee_fk
            , cast(customerid as string) as customer_fk
            , cast(shipvia as int) as shipper_fk
            , cast(id as int) as order_number
            , cast(orderdate as date) as order_date
            , cast(shippeddate as date) as ship_date
            , cast(requireddate as date) as required_delivery_date
            , cast(freight as numeric) as freight
            , cast(shipname as string) as recipient_name
            , cast(shipcity as string) as recipient_city
            , cast(shipregion as string) as recipient_region
            , cast(shipcountry as string) as recipient_country
        from source_orders
    )

select *
from renamed
