# Audit Helper Validation Models

This document describes the four example validation models that use the [dbt-labs/audit_helper](https://github.com/dbt-labs/dbt-audit-helper) package to compare legacy (source) data with new (ref) models. Use them when migrating or validating that refactored dbt models match existing tables.

---

## example_vld_1 — Summary Row-by-row query comparison

**Macro:** `audit_helper.compare_queries`

**Purpose:** Compares two queries row-by-row by a primary key and returns a summary of how many rows match, exist only in the legacy query (A), or only in the new query (B). Useful to get an overall result of the matching percentage. It's a required model for the audit_helper_monitoring model that tracks how the matching result is after every new data refresh of the legacy model vs the new one. It's a good starting point to understand how close the tables are, but will not show to you where the issues are if the matching of the new model has a poor result.

**Parameters:**

| Parameter     | Description |
|--------------|-------------|
| `a_query`    | SQL for the legacy/source table (query A). |
| `b_query`    | SQL for the new model, typically `{{ ref('model_name') }}` (query B). |
| `primary_key`| Single column name used to join and compare rows (e.g. `"order_id"`). |
| `summarize`  | Optional. If `true` (default), returns a summary; if `false`, returns detailed row-level comparison. |


**Output:** A result set with match classification summary so you can see equal %, in legacy only %, and in new only %. By default, the generated query returns a summary of the count of rows that are unique to `a`, unique to `b`, and identical:

| in_a  | in_b  | count | percent_of_total |
|-------|-------|------:|-----------------:|
| True  | True  | 6870  | 99.74            |
| True  | False | 9     | 0.13             |
| False | True  | 9     | 0.13             |

---

## example_vld_2 — Which columns differ

**Macro:** `audit_helper.compare_which_query_columns_differ`

**Purpose:** Compares the same two queries and identifies which columns have differences (not just whether rows differ). Use this when you need to know exactly which fields disagree between legacy and new.

**Parameters:**

| Parameter            | Description |
|----------------------|-------------|
| `a_query`            | SQL for the legacy/source table (query A). |
| `b_query`            | SQL for the new model, e.g. `{{ ref('model_name') }}` (query B). |
| `primary_key_columns`| List of column(s) that uniquely identify a row, e.g. `['order_id']`. |
| `columns`            | List of columns to compare for differences (e.g. `customer_id`, `order_date`, `status`, `amount`). |

**Output:** Results showing which of the specified columns differ between A and B for each primary key (or aggregated by column), so you can focus on problematic fields. It's a true/false indication if the column is causing matching issues. If the column has 1 row that is not matching out of billions of row it will still show that is no matching here so it doesnt give the sense of how problematic the column is. 

The generated query returns whether or not each column has any differences:

| column_name | has_difference |
|-------------|----------------|
| order_id    | False          |
| customer_id | False          |
| order_date  | True           |
| status      | False          |
| amount      | True           |

---

## example_vld_3 — Detailed statistcs per column

**Macro:** `audit_helper.compare_column_values`

**Purpose:** Compares a column within two queries and classifies each row into different categories. Gives both row-level classification and summary counts. The model _vld3 is a modification of the default behaviour of the macro that tests only one column at each time, but in this model a for loop is used to test all. There is a limitation though if too many columns are added the macro will generate a long query which might not be accepeted by the data warehouse. This is good to understand in more detailed what might be happening between legacy and new.

**Parameters:**

| Parameter            | Description |
|----------------------|-------------|
| `a_query` / `old_query` | Legacy query (first argument in example). |
| `b_query` / `new_query` | New model query (second argument). |
| `primary_key_columns`   | List of column(s) that form the primary key, e.g. `['order_id']`. |
| `column_to_compare`               | Column that will be checked for issues. |


**Output:** A table informing how many rows are in both tables and how may rows are missing from each relation. The generated query returns a summary of the count of rows where the column's values:

- match perfectly
- differ
- are null in `a` or `b` or both
- are missing from `a` or `b`

| match_status                | count  | percent_of_total |
|-----------------------------|-------:|-----------------:|
| ✅: perfect match            | 37,721 | 79.03            |
| ✅: both are null            | 5,789  | 12.13            |
| 🤷: missing from a          | 5     | 0.01             |
| 🤷: missing from b          | 20     | 0.04             |
| 🤷: value is null in a only | 59     | 0.12             |
| 🤷: value is null in b only | 73     | 0.15             |
| ❌: ‍values do not match    | 4,064  | 8.51             |

---

## example_vld_4 — Compare and classify (added / removed / changed)

**Macro:** `audit_helper.compare_and_classify_query_results`

**Purpose:** Compares two queries and classifies each primary key into: **unchanged**, **added** (only in new), **removed** (only in legacy), or **modified** (in both but with differences). Gives both row-level classification and summary counts. It also has categories for when a primary key used in duplicated.

**Parameters:**

| Parameter            | Description |
|----------------------|-------------|
| `a_query` / `old_query` | Legacy query (first argument in example). |
| `b_query` / `new_query` | New model query (second argument). |
| `primary_key_columns`   | List of column(s) that form the primary key, e.g. `['order_id']`. |
| `columns`               | List of columns to compare (e.g. `['order_id', 'amount', 'customer_id']`). |
| `sample_limit`          | Optional. Number of sample rows per status to return (default 20). |

**Output:** Rows classified as unchanged, added, removed, or modified, with summary statistics so you can see how many records fall into each bucket without querying multiple comparison tables.


---

## audit_helper_monitoring

**What it does:** 
The audit helper monitoring model is a central snapshot of how well legacy and new data match across all your vld_1 validation models. Each vld_1 compares a legacy source (A) to a refactored dbt model (B) and produces metrics like “equal,” “only in legacy,” and “only in new.” The monitoring model doesn’t re-run those comparisons; it reads the outputs of every vld_1 in the project and turns each one into a single summary row. So you get one row per validation (e.g. one for fact_ib_interval_vld_1, one for dim_customer_vld_1, etc.), each with the three match percentages and a timestamp. That gives you one table to see “how healthy” all your validations are at a given run or date.

**Why it’s useful:**
It automates discovery of vld_1 models (no manual list) and gives you a time-series view of match quality. By running it on a schedule (e.g. daily) and storing results with a unique key per validation and date, you can track whether match rates are improving or regressing over time and quickly spot which validations need attention, without opening each vld_1 result separately.
This model can also be used in a dashboard to keep track of the history of the match score over time

**Test**
With this model, there is a new singular test inside the tests/audit_helper folder that will check if there is any models below a defined threshold and it can warn in the pipeline if any models are failing the check. TODO: Create the test.

## Devloper or Agent Workflow

TODO improve text: The model vld_1 needs to be built first so audit helper monitoring can be used. Is necessary to add the new model to the depends on list inside the audit helper monitoring so it wont work as the model is dynamic created and this brings problem for the dbt parse to compile the dag. After the model is created the user can check how the match is going if is greater than 98% no action needs to be done as this will be low priority. If the math is less than 98% then the user needs to understand which columns are being the problem. Is good to remember that both for vld_1 and all other validation model we should not validate columns that are context-sensitve for exampe metadata columns, current_timestamp and things that will never match. For an agent or skill this should be asked to the user or infered. The user also needs to know the path for the legacy table with the 3 level identifier database, schema and table name, for the model in dbt just the reference will do. The user also needs to specify a primarity key or generate the primary key in both legacy and new query if the primary key are multiple columns. If the table doesnt have a primary key it might be useful to aggregate the table first so a primary key is generated in some higher granularity and the remaing columns can be validated like metrics for example. Now going to model vld_2 the user will get the column list with issues which he will then add to model vld_3 to get an understand of what might be happening for each column. Sometimes the issue is just how legacy and new treats certain columns or datatypes for example it might be that in legacy instead of showing null it shows a blank space '', or how a date column in legacy when it supposed to be null is 1901-01-01 but in the new system it shows as null or maybe legacy uses a prefix in a string column, etc. After you learn this you can implement quick fix to the legacy column to align the column to the new system way to show the data and run the vld_3 again if this fixed then apply the same standardization to model vld_1 and vld_2. Finally what can be easily fixed we need to understand what is happening so we use vld_4 model and compare only the column with problem, we might need to increase sample to have a better picture of what is the difference between legacy and new, it might be easier sometimes to do one column at each time so the sample is not mixed with a lof of other columns and is easier for the user or agent to get the diagnostic of the issue. 