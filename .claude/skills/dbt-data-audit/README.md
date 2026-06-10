# dbt-data-audit

A Claude Code skill that validates a refactored or migrated dbt model against its legacy source using the `audit_helper` package. It runs the full comparison loop — column scoping, match-rate analysis, per-column diagnosis, fix iteration — and produces a documented audit trail.

## When to use it

- You rewrote a SQL script as a dbt model and want to confirm the output matches
- You refactored an existing dbt model and want to catch silent regressions
- You migrated data from a legacy system into a new model and need to sign off on data quality

## How to invoke

In Claude Code:

```
/dbt-data-audit
```

Then describe what you're validating, e.g.:
> "I want to validate `int_order_items__metrics` against the legacy seed `legacy_int_order_items__metrics`."

## What it produces

| File | Purpose | Enabled by |
|---|---|---|
| `models/audit_helper/<base>_vld_1.sql` | Overall match rate (% equal, A-only, B-only) | `dbt_project.yml` target gate |
| `models/audit_helper/<base>_vld_2.sql` | Which columns have any difference (binary) | `dbt_project.yml` target gate |
| `models/audit_helper/<base>_vld_3.sql` | Per-column mismatch categories and counts | `dbt_project.yml` target gate |
| `models/audit_helper/<base>_vld_4.sql` | Row-level samples for stubborn columns | `dbt_project.yml` target gate |
| `models/audit_helper/audit_helper_monitoring.sql` | Incremental snapshot of match rates over time | Hardcoded `enabled = true` |

All generated vld files carry no `config(enabled = ...)` block — they inherit the folder-level gate in `dbt_project.yml`:

```yaml
models:
  <project>:
    audit_helper:
      +enabled: "{{ target.name in ('dev', 'audit_helper') }}"
```

The `example_vld_*.sql` files in `models/audit_helper/` are reference-only and always disabled.

## Prerequisites

- `dbt-labs/audit_helper` in `packages.yml` (the skill installs it if missing)
- The legacy source accessible from dbt's connection — either a seed, a table, or a full SELECT you paste in
- Target name `dev` or `audit_helper` to run the models locally (controlled by the gate above)

## What "done" looks like

The session ends with a structured closing report that includes:

- **Closing match rate** after all fixes
- **Standardizations applied** — each fix, what it changed, and its effect on the match rate
- **Known acceptable mismatches** — each residual difference categorised as source drift, precision improvement, or intentional design change
- vld_1 enrolled in `audit_helper_monitoring.sql` for continuous tracking

## Skill internals

```
.claude/skills/dbt-data-audit/
├── README.md          # this file
├── SKILL.md           # Claude's operating runbook (step-by-step instructions)
├── scaffold/          # files copied into models/audit_helper/ on first use
│   ├── README.md
│   ├── workflow.md
│   ├── patterns.md
│   ├── example_vld_1..4.sql
│   ├── audit_helper_monitoring.sql
│   └── audit_helper_monitoring.yml
└── templates/         # parameterised SQL templates filled in per validation run
    ├── vld_1.sql.tmpl
    ├── vld_2.sql.tmpl
    ├── vld_3.sql.tmpl
    └── vld_4.sql.tmpl
```

Improvements found during a session (new diagnosis patterns, workflow refinements) are backported into `scaffold/` and `SKILL.md` so they ship with the skill next time.
