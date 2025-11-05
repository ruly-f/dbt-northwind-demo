select *
from {{ source('erp', 'employees') }}
