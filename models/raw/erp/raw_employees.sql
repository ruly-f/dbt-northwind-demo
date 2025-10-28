with
    source_employees as (
        select *
        from {{ source('erp', 'employees') }}
    )

    , renamed as (
        select
            cast(id as int) as employee_pk
            , cast(reportsto as int) as manager_fk
            , firstname || ' ' || lastname as employee_name
            , cast(title as varchar) as employee_title
            , cast(birthdate as date) as employee_birth_date
            , cast(hiredate as date) as employee_hire_date
            , cast(city as varchar) as employee_city
            , cast(region as varchar) as employee_region
            , cast(country as varchar) as employee_country
            -- , cast(titleofcourtesy as varchar)
            -- , cast(address as varchar) 
            -- , cast(postalcode as varchar) 
            -- , cast(homephone as varchar)
            -- , cast(extension as varchar)
            -- , cast(photo as varchar)
            -- , cast(notes as varchar)
            -- , cast(photopath as varchar)
        from source_employees
    )

select *
from renamed
