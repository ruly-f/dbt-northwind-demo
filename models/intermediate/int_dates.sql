with 
    date_spine as (
        {{ dbt_utils.date_spine(
            datepart='day',
            start_date="cast('2001-01-01' as date)",
            end_date="cast('2021-01-01' as date)"
        ) }}
    )
    
    , calendar as (
        select
            cast(date_day as date) as calendar_date
            , year(cast(date_day as date)) as calendar_year
            , quarter(cast(date_day as date)) as calendar_quarter
            , month(cast(date_day as date)) as calendar_month
            , day(cast(date_day as date)) as calendar_day_of_month
            , dayofweekiso(cast(date_day as date)) as iso_day_of_week
            , dayofyear(cast(date_day as date)) as day_of_year
            , weekiso(cast(date_day as date)) as iso_week_of_year
            , date_trunc('week', cast(date_day as date)) as week_start_date
            , date_trunc('month', cast(date_day as date)) as month_start_date
            , date_trunc('quarter', cast(date_day as date)) as quarter_start_date
            , date_trunc('year', cast(date_day as date)) as year_start_date
            , last_day(cast(date_day as date), 'month') as month_end_date
            , last_day(cast(date_day as date), 'quarter') as quarter_end_date
            , last_day(cast(date_day as date), 'year') as year_end_date
            , to_char(cast(date_day as date), 'MON') as month_name_short
            , to_char(cast(date_day as date), 'MONTH') as month_name
            , to_char(cast(date_day as date), 'DY') as day_name_short
            , to_char(cast(date_day as date), 'DAY') as day_name
            , case
                when dayofweekiso(cast(date_day as date)) in (6, 7) then true
                else false
            end as is_weekend
            , case
                when cast(date_day as date) = date_trunc('month', cast(date_day as date)) then true
                else false
            end as is_first_day_of_month
            , case
                when cast(date_day as date) = last_day(cast(date_day as date), 'month') then true
                else false
            end as is_last_day_of_month
        from date_spine
    )

select *
from calendar
