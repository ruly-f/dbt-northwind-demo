select *
from {{ source('erp', 'category') }}
--where load_ts = '{{ var('load_date') }}'
where categoryname != 'Beverages'
