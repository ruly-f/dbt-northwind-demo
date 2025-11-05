select *
from {{ source('erp', 'customer') }}
where load_ts = {{ var('load_date') }}
