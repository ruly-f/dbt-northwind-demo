with
    hub_shippers as (
        select *
        from {{ ref('hub_shippers') }}
    )

    , sat_shippers_details as (
        select *
        from {{ ref('sat_shippers_details') }}
    )

    , joined as (
        select
            hub_shippers.shipper_hk
            , hub_shippers.shipper_pk
            , sat_shippers_details.shipper_name
        from hub_shippers
        left join sat_shippers_details
            on hub_shippers.shipper_hk = sat_shippers_details.shipper_hk
    )

select *
from joined