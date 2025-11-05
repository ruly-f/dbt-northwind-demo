select *
from {{ source('erp', 'suppliers') }}
