# Validation Workflow

A predictable loop for validating a new dbt model against a legacy table. Each step has a single purpose; don't skip ahead.

> Throughout, **A = legacy** (the existing table), **B = new** (the refactored or migrated dbt model). Always apply fixes to the **A side** so that A is transformed into B's representation — never modify B to match a legacy quirk.

---

## Step 0 — Prerequisites

- [ ] `audit_helper` installed (`dbt deps`)
- [ ] Legacy table identified by 3-part name (`database.schema.table`)
- [ ] New target identified by `ref('model_name')` (preferred) or 3-part name
- [ ] Primary key chosen:
  - Single column → use directly
  - Composite key → wrap with `{{ dbt_utils.generate_surrogate_key([...]) }}` in both A and B queries
  - No natural PK → pre-aggregate A and B to a higher grain (e.g. daily totals) and use that grain as the key
- [ ] Optional but recommended when dev only has a **subset** of data: pick a `WHERE` filter (date range, single customer, single region) and **apply it equivalently to both A and B**. Match rates over a filtered subset aren't the same claim as match rates over full history — record the filter in a header comment on every validation file so future readers know the scope. If A and B use different column names for the same concept, you'll need two parallel filter expressions.

## Step 1 — Column scoping

List every column you plan to compare. Then **explicitly exclude**:

1. **Metadata columns** that will never match between systems:
   - Audit timestamps: `created_at`, `updated_at`, `dbt_loaded_at`, `_etl_ts`, `_ingested_at`
   - dbt artifacts: any `dbt_*` columns from `generate_surrogate_key` or similar
2. **Context-sensitive columns**:
   - Anything derived from `current_timestamp` or `current_date`
   - Random IDs or session tokens
   - Surrogate keys that hash differently between systems (validate the **underlying** columns instead)
3. **Out-of-scope business columns** the user explicitly excludes

**Excluded columns must stay visible in the file as commented lines with a reason**, so that the next reader (or auditor) understands what was left out and why. Example:

```sql
select
    order_id
    , customer_id
    , order_date
    , status
    , amount
    -- , dbt_loaded_at     -- excluded: ingestion timestamp, will never match
    -- , session_token     -- excluded: random per-session, not a business field
from legacy_database.legacy_schema.orders
```

Mirror the same comments inside the `columns = [...]` parameter passed to the macro.

## Step 2 — `vld_1`: how close are we?

Copy `example_vld_1.sql` → `<model>_vld_1.sql`, fill in A and B queries and the PK, set `enabled = true`, then:

```bash
dbt run -s <model>_vld_1
```

Read the result table:

| Verdict | Match rate | Action |
|---------|------------|--------|
| Green | `equal % ≥ 98` | Low priority. Enroll in monitoring (Step 8) and move on |
| Yellow | `90 ≤ equal % < 98` | Continue to Step 3 |
| Red | `equal % < 90` | Continue to Step 3 — likely a systemic issue (timezone, dedup, scope) |

If `in_a_only` or `in_b_only` dominate the mismatch, you have a **row-level** problem (missing records) rather than a column-level one — check filters, joins, and PK uniqueness in the new model before continuing.

## Step 3 — `vld_2`: which columns are off?

Copy `example_vld_2.sql` → `<model>_vld_2.sql`, reuse the same A/B queries from vld_1, list every comparison column in the `columns = [...]` parameter.

```bash
dbt run -s <model>_vld_2
```

Output is one row per column: `has_difference` true/false. Note: it's binary — one differing row out of a billion still shows `true`, so use this only to **scope** which columns to inspect next.

## Step 4 — `vld_3`: how bad is each column?

Copy `example_vld_3.sql` → `<model>_vld_3.sql`. Set the `column_list` to only the columns vld_2 flagged.

```bash
dbt run -s <model>_vld_3
```

For each column you get the row counts per category:

| Category | Meaning |
|----------|---------|
| ✅ perfect match | Values agree |
| ✅ both null | Both sides null |
| 🤷 missing from a / b | Row missing on that side |
| 🤷 value is null in a / b only | One side null, the other has a value — common encoding mismatch |
| ❌ values do not match | Both sides have a value but they differ |

If `null in a only` or `null in b only` is high → encoding mismatch (empty string vs null, sentinel date vs null). Jump to [`patterns.md`](patterns.md).

If `values do not match` is high → real value drift. Continue to Step 7 (vld_4) for samples.

## Step 5 — Diagnose & standardize (legacy side)

Use [`patterns.md`](patterns.md) to identify the cause for each flagged column. Apply the fix **inside the `old_query` block** of the relevant validation file, e.g.:

```sql
{% set old_query %}
    select
        order_id
        , customer_id
        , order_date
        , status
        , nullif(trim(amount_string), '') as amount   -- aligned: legacy stores '' instead of null
    from legacy_database.legacy_schema.orders
{% endset %}
```

Commit one fix at a time so you can attribute improvements to specific changes.

## Step 6 — Re-run vld_3, then propagate

After a fix:
1. `dbt run -s <model>_vld_3` — verify the column is now ✅
2. Copy the standardization into `<model>_vld_1.sql` and `<model>_vld_2.sql` so they reflect the same A representation
3. Re-run vld_1; the equal % should rise

## Step 7 — `vld_4`: row-level samples

When vld_3 still shows a stubborn column, copy `example_vld_4.sql` → `<model>_vld_4.sql`. **Scope the `columns = [...]` to a single column** so the sample rows aren't a mix of unrelated mismatches.

```bash
dbt run -s <model>_vld_4
```

Look at rows tagged `modified` — they expose the actual (A_value, B_value) pair so you can spot subtle differences (whitespace, trailing zeros, timezone shifts) that summary stats hide. Cycle back to Step 5 with what you learned.

## Step 8 — Enroll in monitoring

Once `equal %` is stable above your threshold:

1. Open `audit_helper_monitoring.sql`
2. Add a line inside the `-- depends on:` block:
   ```sql
   -- depends on: {{ ref('<model>_vld_1') }}
   ```
3. Decide what to keep:
   - `<model>_vld_1.sql` → leave `enabled = true` for continuous monitoring
   - `<model>_vld_2/3/4.sql` → set `enabled = false` or delete (they're scratch tools)
4. Run `dbt run -s audit_helper_monitoring` to confirm the new validation appears in the snapshot

The monitoring model dynamically discovers every `*_vld_1` node, so the `depends on` comment is purely for `dbt parse` — it doesn't change query behaviour, but without it the DAG won't build correctly.

---

## When to stop iterating

You don't always need 100% match. Stop when:

- The remaining mismatches are explainable (known data quality issues in legacy, intentional new-system improvements)
- The match rate exceeds the threshold agreed with the data consumer
- All differences are documented in the validation file as comments

Document the reason in a header comment on `<model>_vld_1.sql` so future readers know the closing state.
