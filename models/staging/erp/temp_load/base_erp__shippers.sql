select *
from {{ source('erp', 'shippers') }}
