select *
from {{ source('erp', 'orders_detail') }}
where load_ts = '{{ var('load_date') }}'
