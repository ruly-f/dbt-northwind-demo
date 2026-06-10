# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`dbt_northwind` is a dbt demo project using the classic Northwind ERP dataset. It runs on **Snowflake** (source database: `MESH_RAW_DB.RAW_NORTHWIND`) and is managed through **dbt Cloud** (project-id: 548606). The profile is `dbt_northwind`.

## Common Commands

```bash
dbt deps                        # Install packages (dbt_utils 1.3.0)
dbt run                         # Run all models
dbt test                        # Run all tests
dbt build                       # Run + test together
dbt run -s staging              # Run only the staging layer
dbt run -s +fct_orders          # Run fct_orders and all upstream models
dbt test -s int_order_items__metrics  # Test a specific model
dbt clean                       # Remove target/ and dbt_packages/
```

## Model Architecture

Three-layer medallion pattern:

| Layer | Prefix | Materialization | Schema suffix |
|-------|--------|-----------------|---------------|
| Staging | `stg_<source>__<entity>` | view | `_stg` |
| Intermediate | `int_<entity>__<verb>` | view | `_int` |
| Marts | `dim_` / `fct_` | table | `_marts` |

**Schema naming:** In prod (`target.name = 'prod'`), schemas are `<target_schema>_stg`, `<target_schema>_int`, `<target_schema>_marts`. In all other environments, the custom schema suffix is dropped and everything lands in the default schema. This is controlled by `macros/generate_custom_schema.sql`.

**Data flow:**
```
sources (erp) → staging (8 models) → intermediate (5 models) → marts (7 models: 2 fct + 4 dim + dim_dates)
```

## Source Data

Defined in `models/staging/erp/_source_erp.yml`. Eight tables from `MESH_RAW_DB.RAW_NORTHWIND`: `category`, `products`, `suppliers`, `employees`, `orders`, `orders_detail`, `shippers`, `customer`.

## Key Patterns

**Staging:** Cast types and rename columns (e.g., `id` → `order_pk`, `employeeid` → `employee_fk`). No business logic.

**Intermediate:** Business logic and joins live here — metric calculations (`gross_total`, `net_total`, `freight_allocated`), self-joins (employee manager hierarchy), and enrichment joins (products + categories + suppliers). The `int_dates` model uses `dbt_utils.date_spine()` to build a full date dimension (2001–2021).

**Marts:** Dimensional model (dim/fct). Fact tables use surrogate keys via `dbt_utils.generate_surrogate_key()`. Mart models include **dbt semantic model definitions** (entities, dimensions, measures) in their `.yml` files for MetricFlow/BI tool integration.

## Testing

- Source and model YAML files define `unique` and `not_null` tests on primary keys.
- `tests/assert_correct_gross_total_in_2012.sql` is a singular data test that validates the annual gross sales metric against an audited value (R$ 230,784.68 ± 1.00) — protects `int_order_items__metrics` from silent logic regressions.
- Static analysis is set to `strict` in `dbt_project.yml`.

## Schema Files Location

Each layer stores YAML documentation in a `schema/` subdirectory alongside the SQL models (e.g., `models/staging/erp/schema/stg_erp__orders.yml`). Sources are defined in `_source_erp.yml` at the layer root.
