select *
from {{ source('erp', 'orders') }}
where load_ts = '{{ var('load_date') }}'
