select *
from {{ source('erp', 'category') }}
