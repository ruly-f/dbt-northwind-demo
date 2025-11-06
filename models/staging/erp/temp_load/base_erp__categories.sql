select *
from {{ source('erp', 'category') }}
where categoryname != 'Beverages'
