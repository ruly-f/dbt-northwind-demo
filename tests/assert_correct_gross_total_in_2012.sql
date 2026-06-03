/*
    Metric regression test: annual gross sales for calendar year 2012.

    Purpose:
      Protects the core gross sales metric in `int_order_items__metrics` from silent logic drift.
      This is a regression check against an audited finance total for 2012.

    Business assertion:
      The sum of `gross_total` for orders dated in 2012 should remain aligned to the audited
      value of R$ 230,784.68.

    Why this test uses a tolerance band:
      We allow a narrow range instead of exact equality to avoid false failures caused by
      rounding differences in aggregation or numeric casting.

    Failure behavior:
      Custom data tests pass when they return zero rows. This test returns one row only when
      the actual aggregated gross total falls outside the accepted range.
*/

with 
    gross_total_2012 as (
        select sum(gross_total) as actual_gross_total
        from {{ ref('int_order_items__metrics') }}
        where order_date between '2012-01-01' and '2012-12-31'
    )

    , data_validation as (
        select
            230784.68 as expected_gross_total
            , 230784.00 as accepted_min_gross_total
            , 230785.00 as accepted_max_gross_total
            , actual_gross_total
            , actual_gross_total - 230784.68 as variance_to_expected
        from gross_total_2012
    )

select *
from data_validation
where actual_gross_total not between accepted_min_gross_total and accepted_max_gross_total
