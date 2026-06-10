---
name: dbt-data-audit
description: Generate and iterate audit_helper validation models to compare a legacy table against a new or refactored dbt model. Use when validating SQL script migrations, dbt model refactors, or any side-by-side data comparison. Walks the user through scoping columns, running vld_1..vld_4, diagnosing mismatches via patterns.md, and applying legacy-side standardizations until match quality is acceptable.
---

# dbt-data-audit

Operationalizes the audit_helper validation workflow. The skill takes the user from "I just refactored a model" to "match rate is acceptable, enrolled in monitoring" through an interactive, iterative loop.

## How this skill is laid out

```
.claude/skills/dbt-data-audit/
├── SKILL.md           # this file — the runbook
├── scaffold/          # canonical install media — copied as-is into a new project's models/audit_helper/
│   ├── README.md
│   ├── workflow.md
│   ├── patterns.md
│   ├── example_vld_1..4.sql
│   ├── audit_helper_monitoring.sql
│   └── audit_helper_monitoring.yml
└── templates/         # parameterized templates filled in per validation run
    └── vld_*.sql.tmpl
```

**Source of truth rule**: the files inside `scaffold/` are canonical. When you carry this skill to a new project, the scaffold step plants those files into `models/audit_helper/`. After installation, the project copy is free to evolve, but **broadly useful improvements (typo fixes, new pattern entries, workflow refinements) must be backported into `scaffold/` here** so they ship with the skill next time.

> **Read first**: `scaffold/README.md`, `scaffold/workflow.md`, and `scaffold/patterns.md` (or, if you're running this skill against an already-installed project, read the equivalents at `models/audit_helper/`). The skill follows their conventions exactly — don't reinvent them.

## Inputs the skill collects

Always use `AskUserQuestion` (group up to 4 questions per round) — never assume:

1. **Legacy source** — 3-part identifier `db.schema.table`, OR a full SELECT statement (multi-table joins, aggregations, etc.)
2. **New target** — preferred: dbt model name to be wrapped in `{{ ref(...) }}`. Alternative: 3-part identifier
3. **Primary key** — single column, list of columns (will be wrapped with `dbt_utils.generate_surrogate_key`), or "no natural PK" (user must aggregate first)
4. **Base name for generated files** — defaults to the new model's name. Files land at `models/audit_helper/<base_name>_vld_N.sql`
5. **Optional filter** — a `WHERE` expression applied equivalently to both A and B so the comparison covers the same overlap of data (useful when dev/CI only has a subset, when validating one customer or date range at a time, or when excluding known-bad historical data). See **Step 2b** for details.

## Runbook

### 0. Bootstrap (run once per project)

Check the current working directory:

- Does `dbt_project.yml` exist? If not, this isn't a dbt project — stop and tell the user.
- Does `models/audit_helper/` exist with the docs (`README.md`, `workflow.md`, `patterns.md`) and the four `example_vld_*.sql` files? If **yes**, skip to Step 1.

If no, propose bootstrapping via `AskUserQuestion`. On confirmation:

1. **Create** `models/audit_helper/` if missing
2. **Copy** every file from `.claude/skills/dbt-data-audit/scaffold/` into `models/audit_helper/`, preserving filenames. Read each scaffold file and Write it to the destination — never edit during copy
3. **Add `audit_helper` to `packages.yml`**:
   - If `packages.yml` doesn't exist, create it with `dbt-labs/audit_helper` and (if obviously needed) `dbt-labs/dbt_utils`
   - If it exists and already lists `dbt-labs/audit_helper`, leave the existing version pin alone and tell the user (don't downgrade or upgrade silently)
   - If it exists without audit_helper, append the package with the latest version known at scaffold time (currently `0.14.0`)
4. **Add the `audit_helper` enabled gate to `dbt_project.yml`** under the project's models block:
   ```yaml
   models:
     <project_name>:
       audit_helper:
         +enabled: "{{ target.name in ('dev', 'audit_helper') }}"
   ```
   If the `audit_helper` key already exists under models, add `+enabled` to it without touching other settings. If the user has a different target convention (e.g. `ci` or `staging`), ask before writing.

   **Why this matters**: generated vld files carry no `config(enabled = ...)` block — they inherit this setting. This means all audit models are enabled in dev (where you work) and automatically disabled everywhere else. Example files keep `config(enabled = false)` hardcoded, which overrides the project setting so they're never run in any environment.

5. **Tell the user to run `dbt deps`** before generating any validation files
6. Stop after bootstrap and confirm with the user — don't proceed straight into generating validation models in the same turn; let them inspect what landed

Idempotency: if a file in `scaffold/` already exists at the destination with different content, **do not overwrite** — show a diff and ask. The user may have intentionally evolved the project copy.

### 1. Preflight

- Re-read `packages.yml`. If `dbt-labs/audit_helper` is still missing (e.g. user skipped bootstrap), stop and tell them to add it + run `dbt deps`. Do not generate models otherwise.
- Read `models/audit_helper/README.md` and quote the prerequisites back so the user knows the conventions.

### 2. Gather inputs

Use `AskUserQuestion` in one or two rounds. Example first round:
- Legacy table identifier (or "I'll paste a SELECT")
- New target (dbt ref name or 3-part identifier)
- Primary key approach

If the user said "I'll paste a SELECT", follow up with a plain prompt asking them to paste it.

### 2b. Ask about a filter (subset of data)

After the core inputs, ask whether a filter is needed via `AskUserQuestion`:

- **No filter** — compare full table to full table
- **Same filter on both sides** — single `WHERE` expression (e.g. `order_date >= '2024-01-01'`) injected into both A and B
- **Different filter per side** — needed when A and B use different column names for the same concept (e.g. legacy `dt_order` vs new `order_date`). Capture two separate expressions.

When applying the filter, **never wrap user-pasted SELECTs blindly**:

- If the user gave a 3-part identifier, build `select <cols> from <id> where <filter>`.
- If the user pasted their own SELECT, ask whether the filter should be appended (`where`/`and`) or whether they already included it. Don't string-mangle their query.

**Critical rule**: a filter must produce **equivalent row populations** in A and B. If the user says "filter to customer_id = 'ACME' on both sides", the column must mean the same thing on both. If equivalence is uncertain, prompt the user to verify with a row count: `select count(*) from <legacy> where <filter>` vs the same on the new model.

Echo the final filter expression(s) back to the user before generating files, and add a **header comment to every generated file** documenting the filter — e.g.:

```sql
/*
    ...
    Filter applied to A and B: order_date between '2024-01-01' and '2024-12-31'
    Reason: dev environment only has 2024 data
*/
```

This makes it obvious to anyone reading the validation results that the comparison was scoped — a `99% match` over a filtered subset is not the same claim as a `99% match` over full history.

### 3. Discover columns

- **If new target is a dbt ref**: read `models/**/<new_model>.sql` and look for the column list (either a final `select` or columns documented in the schema YAML next to it). Extract column names.
- **If new target is a 3-part identifier**: ask the user to paste the column list, one per line.

Present the extracted column list to the user for confirmation before proceeding.

### 4. Infer exclusion candidates

Scan the column list for metadata patterns:

| Pattern | Reason to exclude |
|---------|-------------------|
| ends in `_at`, `_ts`, `_timestamp` | likely audit timestamp |
| starts with `dbt_` | dbt-injected artifact |
| starts with `_loaded_`, `_ingested_`, `_etl_`, `_dlt_` | loader metadata |
| starts with `current_` | non-deterministic |
| matches `created_at`, `updated_at`, `inserted_at`, `modified_at` exactly | audit timestamp |

Present matches via `AskUserQuestion` (multiSelect: true) — the user confirms which to exclude. Default-check all heuristic matches, but let the user uncheck.

Then ask a follow-up question: any **business** columns to exclude, with a free-text reason for each. Capture each reason verbatim.

### 5. Generate vld_1 and vld_2

Read templates from `.claude/skills/dbt-data-audit/templates/`:
- `vld_1.sql.tmpl`
- `vld_2.sql.tmpl`

Substitute placeholders:
- `{{LEGACY_QUERY}}` — the legacy SELECT (built from the 3-part identifier + column list, with the legacy-side filter appended as a `where` clause if present; or pasted verbatim)
- `{{NEW_QUERY}}` — `select <columns> from {{ ref('<new_model>') }}` with the new-side filter appended (or the same shared filter)
- `{{PRIMARY_KEY}}` — quoted column name for single-key, or surrogate-key wrapping for composite
- `{{COLUMNS_LIST}}` — Jinja list of comparison columns
- `{{EXCLUDED_COLUMNS_BLOCK}}` — commented lines, one per exclusion, formatted as `        -- , <col>     -- excluded: <reason>`
- `{{FILTER_NOTE}}` — single-line header documenting any filter applied (or `Filter applied: none` if no filter)

**Critical formatting rule**: every excluded column appears as a commented line in BOTH the `select` block (inside `old_query` and `new_query`) AND the `columns = [...]` macro parameter, each with `-- excluded: <reason>`. Future readers must be able to see what was skipped and why.

Write the files to `models/audit_helper/<base_name>_vld_1.sql` and `<base_name>_vld_2.sql`. **Do not add a `config(enabled = ...)` block** — the files inherit the project-level `+enabled` gate from `dbt_project.yml`. The `audit_helper` block there already controls when they run.

Show the user the diff/preview of both files.

### 6. Execute vld_1/vld_2 and fetch results

**Always run models yourself first** using the Bash tool — do not ask the user to run them or paste results:

```bash
# Run the models
dbt run -s <base>_vld_1 <base>_vld_2

# Fetch results (no paste needed — use dbt show directly)
dbt show -s <base>_vld_1 --limit 10
dbt show -s <base>_vld_2 --limit 30
```

Set `enabled = true` in generated files **before** running so dbt-fusion doesn't skip them.

After running, announce the results and interpret them in the next step. Only ask the user for input if a run fails or if you need domain knowledge to interpret an unexpected result.

### 7. Interpret vld_1 / vld_2 output

Apply the same thresholds as `workflow.md`:

| vld_1 equal % | Action |
|---------------|--------|
| ≥ 98 | Done. Skip to Step 11 (enroll in monitoring) |
| 90–98 | Continue to Step 8 with the columns vld_2 flagged |
| < 90 | Check for row-level issues (joins, filters, PK uniqueness) before column-level diagnosis. If `in_a_only` or `in_b_only` dominates, ask the user to audit the new model's joins first |

For vld_2, collect every column where `has_difference = true`. That's the input list for vld_3.

### 8. Generate vld_3 and run it

Read `templates/vld_3.sql.tmpl`. Substitute the same placeholders, but `{{COLUMNS_LIST}}` is scoped to only the columns flagged by vld_2.

Write to `models/audit_helper/<base_name>_vld_3.sql` with `enabled = true`, then run immediately:

```bash
dbt run -s <base>_vld_3
dbt show -s <base>_vld_3 --limit 50
```

Do not ask the user to enable or run it — do it yourself. Interpret the results directly from `dbt show` output.

### 9. Diagnose using patterns.md

For each problem column, look at vld_3's dominant category:

- `null in a only` or `null in b only` → encoding mismatch (empty string, sentinel date)
- `values do not match` → real drift (whitespace, case, precision, timezone, units)
- `missing from a/b` → row-level, not column-level — audit joins

Walk through `models/audit_helper/patterns.md` and propose the most likely fix. Apply the fix inside the `old_query` block (legacy side) of the relevant vld file(s).

After applying a fix:
1. Re-run vld_3 yourself (`dbt run -s <base>_vld_3 && dbt show -s <base>_vld_3 --limit 50`)
2. Confirm the column moved to ✅ category
3. Propagate the same standardization to vld_1 and vld_2 so they reflect the corrected A representation

Cycle: diagnose → fix → re-run. Don't bundle multiple fixes per cycle — one fix, one re-run, so credit is attributable.

**When a fix attempt has no effect** (vld_3 count unchanged after re-run), escalate systematically before declaring the mismatch "acceptable":

1. **Check for invisible characters** — inspect the seed file bytes for the affected column:
   ```python
   python3 -c "
   import csv
   with open('seeds/<seed>.csv', encoding='utf-8') as f:
       for row in csv.DictReader(f):
           val = row['COLUMN_NAME']
           if '<search_term>' in val:
               print(repr(val), '->', val.encode('utf-8').hex())
               break
   "
   ```
   Look for: non-breaking spaces (`c2a0`), carriage returns (`0d`), zero-width characters (`e2808b`), combining Unicode (e.g. `e` + `cc80` instead of `c3a8`).

2. **Check the source model** — read the staging `.sql` that produces the column to see if the model itself applies a transformation (cast, trim, upper, replace) that the seed doesn't reflect.

3. **Check for source data drift** — if seed bytes are clean, staging is a plain pass-through, and the fix had no effect, the source table may have changed since the seed was exported. This is a **known acceptable mismatch**, not a fixable transformation issue. Document it in vld_3's old_query with a `-- NOTE:` comment and in the vld_1 header.

Only declare a mismatch "acceptable" after following all three escalation steps. Don't skip straight to "source drift" without checking bytes and the model first.

### 10. Generate vld_4 if vld_3 isn't enough

When vld_3's `values do not match` stays high and patterns.md doesn't yield an obvious cause, generate vld_4 from `templates/vld_4.sql.tmpl`. **Scope `{{COLUMNS_LIST}}` to one column at a time** — mixing columns in samples makes diagnosis harder.

Run it yourself and inspect `modified` rows:

```bash
dbt run -s <base>_vld_4
dbt show -s <base>_vld_4 --limit -1 2>&1 | grep "modified" | head -20
```

The `--limit -1` with `grep modified` surfaces the A vs B value pairs for mismatched rows without flooding the output. Inspect the actual (A_value, B_value) pairs for subtle differences (trailing whitespace, hidden characters, timezone offsets visible in seconds, scale multipliers like ×100, case differences).

**Reuse vld_4 for each stubborn column** by editing the column name and PK selection in the file — no need to create separate vld_4 files per column.

### 11. Close out

When match quality is acceptable:
1. Open `models/audit_helper/audit_helper_monitoring.sql`
2. Add a line: `-- depends on: {{ ref('<base_name>_vld_1') }}`
3. Leave vld_2/3/4 in place — they have no config block and are gated by `dbt_project.yml`. They'll only run in dev, which is fine; they're cheap views and useful to have available when re-investigating later.
4. Run `dbt run -s audit_helper_monitoring` to verify the snapshot picks up the new validation
5. Add a header comment to `<base_name>_vld_1.sql` documenting the closing match rate and all standardizations and known mismatches

### 12. Closing report (mandatory)

Always end the session with a structured report in the conversation — even if the user didn't ask for one. This is the audit's permanent record.

**Format:**

---
**Audit summary: `<new_model>` vs `<legacy_source>`**
**Closing match rate: XX% equal** (`<date>`)

**Standardizations applied (legacy/A side):**

| Column | Fix | Effect |
|---|---|---|
| `col` | description of transformation | `had_discount`: 0% → 99.86% match |

**Known acceptable mismatches:**

| Column | Rows | % | Category | Explanation |
|---|---|---|---|---|
| `col` | N | X% | source drift / precision / intentional | one-line explanation |

**3 rows missing from A**: PKs present in B but not legacy — expected new records.

**Next steps:**
- Enable `audit_helper_monitoring.sql` for continuous tracking
- [any remaining open questions or recommended follow-up]
---

**Depth rules for the report:**
- For each "standardization applied" row, state both the SQL fix AND the before/after match rate change so the reader knows the impact of each fix individually
- For each "acceptable mismatch", state whether it is: (a) **source drift** — data changed since seed export, (b) **precision improvement** — new model is more precise, (c) **intentional design difference** — new model behaves differently by design, or (d) **unresolved** — investigated but cause unknown (rare; flag clearly)
- If any mismatch is "unresolved", add a recommendation: what additional investigation would be needed (e.g. re-export the seed, run a direct source query, check the ETL pipeline)

## Rules the skill must always follow

- **Confirm before destructive edits**: never overwrite or delete a `<base>_vld_*.sql` that has `enabled = true` without explicit user confirmation
- **Always show diffs**: any change to a legacy query block (Step 9) is shown to the user before being written
- **Always confirm exclusions**: never auto-exclude a metadata-pattern column — present candidates via `AskUserQuestion` and let the user decide
- **Preserve excluded columns as comments**: never delete an excluded column from the file — keep it commented with its reason
- **One fix per iteration**: don't bundle multiple standardizations into a single Edit
- **Don't modify the new (B) side** to match legacy quirks — transformations only go on the A side, so the validation truly measures whether B matches the audited expectation
- **Backport improvements to `scaffold/`**: if during a session the user edits a doc or example file in `models/audit_helper/` in a way that is broadly useful (typo fix, new diagnosis pattern, clearer wording), offer to mirror the change back into `.claude/skills/dbt-data-audit/scaffold/` so the skill's install media stays current. Never auto-mirror — always confirm first, and skip the offer for project-specific edits

## Edge cases

- **No primary key**: prompt the user to pre-aggregate both A and B to a sensible grain (daily totals, customer monthly sum, etc.) and use that grain as the PK. Generated files then validate the aggregated grain, not raw rows.
- **Composite key**: wrap with `{{ dbt_utils.generate_surrogate_key(['col1', 'col2']) }}` in both A and B; use that surrogate as the `primary_key` parameter.
- **Huge column list (50+)**: vld_3's loop generates a long UNION ALL query that may exceed warehouse query limits. Batch vld_3 into chunks of ~10–15 columns at a time.
- **Legacy table inaccessible from dbt's connection**: the skill can't help — tell the user to either materialize the legacy data into the dbt warehouse first or run the validation outside dbt.
