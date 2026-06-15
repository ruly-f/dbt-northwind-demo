---
name: dbt-lineage
description: Answer model AND column lineage questions for a dbt project. Source of truth is dbt's manifest.json (parsed by `dbt compile`); column-level analysis is SQLGlot-parsed compiled SQL. Compares current branch against a configurable baseline branch (main/master/develop/qa) via git worktree. Use when an engineer asks "what feeds model X", "what consumes model Y", "how does column C flow downstream", "is column C just a passthrough or is it used in joins/filters/aggregations?", "what does my PR change in lineage vs main?", or wants to validate that depends_on matches the SQL.
---

# dbt-lineage skill

Two analysis modes — **model lineage** and **column lineage** — backed by `manifest.json` + sqlglot. Designed to be carried across dbt projects regardless of warehouse dialect (Snowflake / BigQuery / Postgres / Redshift / Databricks / etc.) — the dialect is auto-detected from `profiles.yml`.

## What it can answer

**Model lineage**
- What models / sources feed `<model>` (direct or transitive)?
- What downstream models consume `<model>`?
- Shortest path between two models.
- What's added/removed/modified in lineage vs. the baseline branch?

**Column lineage** (forward trace from source/staging downstream)
- Is column `<col>` a **passthrough** all the way to the leaf models?
- Where does it get **truncated** — i.e. reaches a model but isn't propagated further?
- Where is it part of a **meaningful transformation**, and which kind:
  - `join_key` — used in a `JOIN ... ON` predicate
  - `filter` — used in `WHERE` / `HAVING` / `QUALIFY`
  - `groupby` — used in `GROUP BY`
  - `order_by` — used in `ORDER BY`
  - `window` — used inside an `OVER()` partition/order
  - `select_transform` — appears in the SELECT projection wrapped in a function or expression (`SUM`, `CASE`, `COALESCE`, arithmetic, `CAST`, etc.)
  - `select_passthrough` — appears in SELECT as a bare reference (just propagated as-is)
- If the column is renamed (e.g. `id AS order_pk`), the trace follows the new name downstream automatically.

## Python models

- **Model lineage works** for Python (.py) models: dbt populates `depends_on.nodes` regardless of language, so the DAG includes Python models and traversal returns them correctly.
- **Column lineage does NOT work** for Python models: their body is Python, not SQL, so sqlglot can't parse it. When the forward column trace hits a Python model, the hop is recorded with `classification: "unknown_python"` and a note — but the trace stops at that branch (we have no way to know which incoming columns the Python code actually consumed or how it transformed them). Other branches that don't pass through the Python model continue tracing.

## What it CANNOT answer (limitations — call out when relevant)

- **Macros that need a DB round-trip** (`run_query(...)` in a model body) won't appear in compiled SQL; flagged as `low` confidence by `validate`.
- **Same-name collisions** across joined tables (`a.id` vs `b.id`) — we conflate the two during tagging. If your model joins two tables that both have `id`, classification may be ambiguous.
- **Catalog-level type info** — we don't read `catalog.json`; column types and physical sizes aren't surfaced.

## Derived column lineage (`coalesce`, `sum`, arithmetic, etc.)

The trace **does** continue past expressions like `coalesce(a, b) AS c`, `sum(qty) AS total`, or `(price * qty) AS line_total`. Each hop reports two propagation channels:

- `outgoing_names` — **direct** propagation: the column itself (or a rename via `col AS new_name`) is in the model's output. Lineage fidelity is exact.
- `derived_names` — **derived** propagation: the column was used inside an aliased expression (anywhere in the model, including inner CTEs). The trace continues with the derived alias name, but **fidelity degrades** because the derived column combines this source with others (or is the result of an aggregate). For example, `quantity` flows into `sum(quantity) AS total_quantity` in an inner CTE; the trace will follow `total_quantity` downstream and tag the hop's `derived_names` field with `total_quantity`.

When `coalesce(a, b) AS c` appears, tracing forward from either `a` OR `b` reports `c` in `derived_names`. We cannot say, row by row, whether the value of `c` came from `a` or `b` — but you'll know `a` and `b` both contribute to `c`, and you can follow `c` downstream.

## Layout

```
.claude/skills/dbt-lineage/
├── SKILL.md                 ← this file
├── requirements.txt         ← sqlglot + networkx + pyyaml
├── config.yml               ← auto-written: { compare_branch: <auto-detected> }
└── scripts/
    ├── __main__.py          ← CLI entry
    ├── cli.py               ← subcommand dispatch
    ├── manifest.py          ← load manifest.json + detect dialect from profiles.yml
    ├── git_ops.py           ← branch detection, worktree dance, cache management
    ├── graph.py             ← networkx DAG from manifest.depends_on
    ├── model_lineage.py     ← up/down traversal
    ├── classifier.py        ← AST-walking column classifier
    ├── column_lineage.py    ← forward column tracing through DAG
    ├── diff.py              ← manifest diff (added/removed/modified models)
    └── visualize.py         ← Mermaid + ASCII tree renderers

target/lineage_cache/        ← cached manifests, gitignored via dbt's `target/` ignore
  └── <branch>_<sha>.json
```

## Installation in a new dbt project

This skill is portable. To use it in another dbt project:

1. Copy the `.claude/skills/dbt-lineage/` directory.
2. Install the skill's Python dependencies (`sqlglot`, `networkx`, `pyyaml`) into wherever the skill will be run from. Same Python that the skill is invoked with — does not have to be the same as the one that runs dbt.
3. First invocation auto-detects the default branch from `origin/HEAD` and writes `.claude/skills/dbt-lineage/config.yml`. Edit that file to change the compare branch (e.g. `master`, `develop`, `qa`).
4. Dialect is auto-detected from the `type:` field in the active profile in `profiles.yml`. Override per-invocation with `--dialect`.

## How the skill finds `dbt`

The skill calls `dbt compile` to (re)build manifest.json. It picks which `dbt` binary to invoke in this order:

| Priority | Path | When this wins |
|---|---|---|
| 1 | `<project>/.venv/bin/dbt` | Most common: dbt installed in a project venv via pip/uv/poetry |
| 2 | `<project>/venv/bin/dbt` | Alternative venv directory name |
| 3 | `<project>/.virtualenv/bin/dbt` | Less common |
| 4 | `dbt` on `$PATH` | System install: pipx, homebrew, dbt Cloud CLI, etc. |

**If you have both a project-venv install AND a system/CLI install**, the project venv wins. This is intentional — project venvs pin dbt + adapter versions in `requirements*.txt`, so honoring them avoids subtle compile drift between contributors. The `refresh` command echoes `dbt_binary` and `dbt_binary_source` in its JSON output so you can verify which one was used.

**If you only have a CLI install** (no project venv): the skill falls back to `dbt` on `$PATH`, which works fine. You'll see `dbt_binary_source: "system-path"` in the `refresh` output.

If you want to force a specific dbt (e.g. switch between two project Pythons), activate the venv before running the skill — the inherited `PATH` is what step 4 uses.

## Operating modes

Run from the dbt project root (the directory containing `dbt_project.yml`):

```
PYTHONPATH=.claude/skills/dbt-lineage \
  .venv/bin/python -m scripts <subcommand> [args] [flags]
```

All commands print JSON by default (when `--format` isn't specified) or accept `--format mermaid|json|tree`. Use `--json` as a shortcut.

### 1. Refresh

Materialize / refresh the manifests this skill works with.

```
... -m scripts refresh [--branch <name>] [--force]
```

- Without `--force`: reuses an existing `target/manifest.json` for the current branch (so you don't trigger a compile every time). Always (re)builds the compare-branch manifest if its cache file for the current HEAD SHA is missing.
- With `--force`: recompiles both branches from scratch.
- `--branch` overrides the configured compare branch for this run only.

Compile failures (e.g. broken tests, macro version mismatches) are reported in the JSON output without aborting the skill — model/column queries can still run against the existing manifests.

### 2. Model lineage

```
... -m scripts model <name>
        [--direction up|down|both]     default: both
        [--depth N]                     default: unlimited
        [--diff]                        overlay diff vs compare branch
        [--branch <name>]               override compare branch
        [--format mermaid|json|tree]
        [--json]
```

`<name>` is the short model name (e.g. `fct_orders`, `stg_erp__orders`) or a source spec (`erp.orders`).

Returns the target node summary plus upstream/downstream lists. With `--diff`, adds `diff.upstream_added/removed` and `diff.downstream_added/removed` showing what changed vs. the compare branch.

### 3. Column lineage (forward)

```
... -m scripts column <model>.<column>
        [--to <downstream-model>]       restrict trace to shortest path
        [--branch <name>]
        [--dialect <name>]              override sqlglot dialect
        [--dbt-target <name>]           override dbt target when detecting dialect
        [--format mermaid|json|tree]
        [--json]
```

Without `--to`, the trace fans out forward through every downstream model in topological order, classifying each hop. With `--to`, the trace is restricted to the shortest path from source to target.

Each hop in the result carries:
- `incoming_names` — what the column is called when entering this model
- `outgoing_names` — what it's called when leaving (handles renames like `id AS order_pk`)
- `classification` — `passthrough` | `meaningful` | `truncated` | `absent`
- `labels` — set of the sublabels described above
- `appears_in_output` — whether the column propagates to downstream models

### 4. Diff

```
... -m scripts diff [--branch <name>]
```

Model-level diff between current branch and compare branch:
- `added_models` — net new in current
- `removed_models` — present on compare branch, gone in current
- `modified_models` — each with `code_changed`, `added_deps`, `removed_deps`, `added_columns`, `removed_columns`

### 5. Validate

```
... -m scripts validate
```

Cross-checks `depends_on.nodes` against sqlglot-parsed physical tables in `compiled_code`. Surfaces:
- `hardcoded_refs` — models that reference a known table by physical name instead of via `{{ ref() }}` / `{{ source() }}`
- `parse_failures` — models whose compiled SQL sqlglot couldn't parse

Use this to validate the integrity of the lineage before reporting findings.

## Answering style — what every answer MUST include

When you respond to the user's lineage question, your reply should:

1. **Lead with the direct answer** — list of models / columns / paths.
2. **State the comparison context** — current branch SHA, compare-branch SHA, whether `--diff` was used.
3. **Classify column hops** in plain language: "passthrough through staging and intermediate; in `int_orders__metrics` it's used as a `join_key` AND renamed to `freight_total`; from there it passes through to `fct_orders` unchanged."
4. **Surface truncations explicitly** — "the column dies at `int_order_items__metrics`: used as a join key but not in the model's output."
5. **Flag limitations** when they apply — "this column is renamed via `coalesce()`, so the downstream trace doesn't continue; rerun with the new column name to follow it."
6. **For diffs, name the impact** — "your PR adds 3 upstream sources to `fct_orders` and drops `freight` from the output."

Render Mermaid output whenever the answer is graph-shaped — it renders inline in Claude Code chat and is the fastest read for the engineer.

## Quick orientation

| Where | What lives there |
|---|---|
| `target/manifest.json` | Current branch manifest — read directly when present |
| `target/lineage_cache/<branch>_<sha>.json` | Cached compare-branch manifests |
| `.claude/skills/dbt-lineage/scripts/` | Skill source — read these to extend behaviour |
| `.claude/skills/dbt-lineage/config.yml` | `{ compare_branch }` — auto-written on first run |
| `profiles.yml` (DBT_PROFILES_DIR or ~/.dbt/) | Active adapter → sqlglot dialect mapping |

## Dialect mapping

| dbt adapter | sqlglot dialect |
|---|---|
| snowflake | snowflake |
| bigquery | bigquery |
| postgres | postgres |
| redshift | redshift |
| databricks / spark | databricks / spark |
| duckdb | duckdb |
| athena / trino | athena / trino |
| sqlserver / mssql / fabric | tsql |
| clickhouse | clickhouse |

If your adapter isn't listed, pass `--dialect <sqlglot-dialect>` and extend `ADAPTER_TO_DIALECT` in `scripts/manifest.py` for future runs.

## Worked example — tracing `freight` from staging

```
... -m scripts column stg_erp__orders.freight --format tree
```

Sample output (this dbt_northwind project):

```
=== stg_erp__orders.freight ===
  → int_order_items__metrics  [TRUNCATED  ] labels=select_passthrough,select_transform out=<not propagated>
  → int_orders__metrics       [PASSTHROUGH] labels=select_passthrough                  out=freight_total
  → fct_orders                [PASSTHROUGH] labels=select_passthrough                  out=freight_total
```

How to read:
- `int_order_items__metrics` consumes `freight` (the `freight_allocated` computation uses it via `cast((freight / count(*) over ...) as numeric)`) but does NOT keep it in its output — **truncated** here.
- `int_orders__metrics` sums `freight` into `freight_total` and passes that downstream — name change tracked automatically.
- `fct_orders` is a thin wrapper (`select *`), so `freight_total` continues to propagate.
