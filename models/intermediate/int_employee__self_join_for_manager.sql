with
    hub_employees as (
        select *
        from {{ ref('hub_employees') }}
    )

    , sat_employees_personal_details as (
        select *
        from {{ ref('sat_employees_personal_details') }}
    )

    , sat_employees_address_details as (
        select *
        from {{ ref('sat_employees_address_details') }}
    )

    , self_joined as (
        select
            hub_employees.employee_hk
            , hub_employees.employee_pk
            /* Employee's Personal Details */
            , sat_employees_personal_details.employee_name
            , sat_employees_personal_details.employee_title
            , managers.employee_name as manager_name
            , sat_employees_personal_details.employee_birth_date
            , sat_employees_personal_details.employee_hire_date
            /* Employee's Address Details */
            , sat_employees_address_details.employee_city
            , sat_employees_address_details.employee_region
            , sat_employees_address_details.employee_country
        from hub_employees
        left join sat_employees_personal_details
            on hub_employees.employee_hk = sat_employees_personal_details.employee_hk
        left join sat_employees_address_details
            on hub_employees.employee_hk = sat_employees_address_details.employee_hk
        left join sat_employees_personal_details as managers
            on sat_employees_personal_details.manager_hk = managers.employee_hk
    )

select *
from self_joined
