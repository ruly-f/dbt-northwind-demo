with
    source_categories as (
        select *
        from {{ source('erp', 'category') }}
    )

    , renamed as (
        select
            cast(id as int) as category_pk
            , cast(categoryname as string) as category_name
            , cast(description as string) as category_description
        from source_categories
    )

select *
from renamed