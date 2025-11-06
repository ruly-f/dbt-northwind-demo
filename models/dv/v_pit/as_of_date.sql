{{ config(materialized='table') }}

with
    source as (
        {{
            dbt_utils.date_spine(
                datepart="day"
                , start_date="cast('2014-05-01' as date)"
                , end_date="cast('2014-06-01' as date)"
            )
        }}
    )

select date_day as as_of_date
from source
