with
    -- call required staging model
    employees as (
        select *
        from {{ ref('snp_erp__employees') }}
        where dbt_valid_to is null
    )

    , self_joined as (
        select
            employees.employee_pk
            , employees.employee_name
            , employees.employee_title
            , managers.employee_name as manager_name
            , employees.employee_birth_date
            , employees.employee_hire_date
            , employees.employee_city
            , employees.employee_region
            , employees.employee_country
            , employees.load_ts
            , employees.insert_ts
        from employees
        left join employees as managers
            on employees.manager_fk = managers.employee_pk
    )

select *
from self_joined
