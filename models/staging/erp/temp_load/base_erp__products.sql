select *
from {{ source('erp', 'products') }}
where load_ts = '{{ var('load_date') }}'