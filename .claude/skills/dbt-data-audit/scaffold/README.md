# Audit Helper

Side-by-side data validation for dbt model refactors and source migrations. Wraps the [dbt-labs/audit_helper](https://github.com/dbt-labs/dbt-audit-helper) package macros into four reusable example models so you can compare a **legacy** table (A) against a **new** dbt model (B) and prove parity before cutover.

## When to use this

- You refactored an existing dbt model and want to confirm it produces the same data
- You migrated a legacy SQL script to dbt and need to validate row-for-row equivalence
- You replaced an upstream source and want to monitor drift over time

## Prerequisites

1. `dbt-labs/audit_helper` declared in `packages.yml` (already pinned to `0.14.0`)
2. `dbt deps` has been run
3. You can identify:
   - The **legacy** table by 3-part identifier (`database.schema.table`)
   - The **new** target by `ref('model_name')` or 3-part identifier
   - A **primary key** column (or composite key — pre-aggregate if the table has no natural PK)

## The four validation models

| Model | audit_helper macro | Answers | Output shape |
|-------|-------------------|---------|--------------|
| `*_vld_1` | `compare_queries` | What % of rows match? | Summary: `in_a`, `in_b`, `count`, `percent_of_total` |
| `*_vld_2` | `compare_which_query_columns_differ` | Which columns have any difference? | Per-column boolean `has_difference` |
| `*_vld_3` | `compare_column_values` | For each column, how do values differ? | Categories: perfect match, both null, null in one, missing, values differ |
| `*_vld_4` | `compare_and_classify_query_results` | Row-level samples per status | Classified rows: `unchanged`, `added`, `removed`, `modified` |

The four `example_vld_*.sql` files in this directory are working templates. **Copy them, rename to `<your_model>_vld_N.sql`, and adjust the queries.**

## The `enabled = false` convention

Every example ships with `config(enabled = false)` so they don't compile into your warehouse. When you copy a template:

- Keep `enabled = false` until you're ready to run it
- Set `enabled = true` (or delete the config block) to run
- After a validation is closed out, switch the file back to `enabled = false` to keep CI fast — or delete vld_2/3/4 entirely and leave only vld_1 for ongoing monitoring

## Ongoing monitoring

`audit_helper_monitoring.sql` auto-discovers every `*_vld_1` model in the project and snapshots its match percentages each run. To enroll a new validation, add a `-- depends on: {{ ref('<your_model>_vld_1') }}` comment inside the monitoring file so `dbt parse` can build the DAG correctly (the dynamic discovery alone isn't visible to the parser).

## Next steps

- **First time running a validation?** → [`workflow.md`](workflow.md) — step-by-step iteration loop
- **Match rate < 98% and you don't know why?** → [`patterns.md`](patterns.md) — common legacy-vs-new mismatch recipes
- **Want the workflow automated?** → invoke the `dbt-data-audit` skill (`.claude/skills/dbt-data-audit/`) and let it generate the validation models from your inputs
