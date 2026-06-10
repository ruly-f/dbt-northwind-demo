# Diagnosis Patterns

Common reasons a column doesn't match between legacy (A) and new (B), with detection signals from `vld_3` / `vld_4` and a legacy-side fix snippet. All snippets go inside the `old_query` block — **transform A to look like B**, never the other way around.

> Snippets use Snowflake-flavored SQL because that's this project's warehouse. Function names may need adjusting on other engines.

---

## 1. Empty string vs `NULL`

**Symptom in vld_3:** `value is null in b only` is high; values in A are mostly blank strings.

**Cause:** Legacy systems often store an empty string (`''`) where the new system stores `NULL`.

**Fix:**
```sql
nullif(trim(legacy_col), '') as legacy_col
```

---

## 2. Sentinel dates vs `NULL`

**Symptom in vld_3:** `value is null in b only` is high on date columns. vld_4 samples show A_value like `1900-01-01`, `1901-01-01`, `9999-12-31`.

**Cause:** Legacy stored a placeholder date instead of allowing `NULL`.

**Fix:**
```sql
case
    when legacy_date in ('1900-01-01'::date, '1901-01-01'::date, '9999-12-31'::date)
        then null
    else legacy_date
end as legacy_date
```

Adjust the sentinel set per the legacy system's convention.

---

## 3. Leading / trailing whitespace

**Symptom in vld_3:** `values do not match` is high on string columns. vld_4 shows A and B that look identical but compare as unequal.

**Cause:** Padding from fixed-width legacy systems or import errors.

**Fix:**
```sql
trim(legacy_col) as legacy_col
```

Use `ltrim` / `rtrim` instead if only one side is padded.

---

## 4. Case sensitivity

**Symptom in vld_4:** A_value and B_value differ only in capitalization (e.g. `Brazil` vs `brazil`).

**Cause:** Source system stored mixed-case; new model normalized.

**Fix:**
```sql
lower(legacy_col) as legacy_col
```

**Caution:** Don't lowercase free-text user content (names, addresses) without confirming the new model also normalizes — match the new model's exact transformation.

---

## 5. String prefix / suffix differences

**Symptom in vld_4:** A_value has a consistent prefix or suffix that B_value doesn't (or vice versa). Examples: `CUST-12345` vs `12345`, `2024-Q1-orders` vs `orders`.

**Cause:** Legacy concatenated metadata into identifiers; new model split them apart.

**Fix:**
```sql
-- Strip a known prefix
regexp_replace(legacy_id, '^CUST-', '') as legacy_id

-- Strip a suffix
regexp_replace(legacy_id, '_v[0-9]+$', '') as legacy_id
```

If the prefix encodes information you need elsewhere, validate it as a separate column rather than discarding it.

---

## 6. Numeric precision / trailing zeros

**Symptom in vld_3:** `values do not match` on numeric columns. vld_4 shows tiny absolute differences like `12.50` vs `12.5000` or `100.00` vs `99.999999`.

**Cause:** Different decimal/numeric precision, or float-vs-decimal storage.

**Fix:**
```sql
-- Snap to a known scale
cast(legacy_amount as decimal(18, 2)) as legacy_amount

-- Or round to a tolerance
round(legacy_amount, 2) as legacy_amount
```

If the new model intentionally carries more precision, the legacy side is the lossy version — match its scale on **both** sides and document that the validation can't catch sub-precision drift.

---

## 7. Timezone offsets

**Symptom in vld_4:** Timestamps differ by a consistent number of hours (3, 4, 5, 12).

**Cause:** Legacy stored local time; new model stores UTC (or vice versa).

**Fix:**
```sql
-- Convert legacy local time to UTC
convert_timezone('America/Sao_Paulo', 'UTC', legacy_ts) as legacy_ts

-- Or drop to date if time-of-day doesn't matter
cast(legacy_ts as date) as legacy_date
```

If the validation should care only about the day, drop both sides to `date` and continue.

---

## 8. Boolean encoding

**Symptom in vld_3:** `values do not match` on boolean-like columns. vld_4 shows pairs like `Y` vs `true`, `1` vs `true`, `N` vs `false`.

**Cause:** Different boolean conventions across systems.

**Fix:**
```sql
case
    when upper(trim(legacy_flag)) in ('Y', 'YES', 'T', 'TRUE', '1') then true
    when upper(trim(legacy_flag)) in ('N', 'NO', 'F', 'FALSE', '0') then false
    else null
end as legacy_flag
```

---

## 9. Currency / unit conversion

**Symptom in vld_4:** Values are off by a constant factor (100×, 1000×).

**Cause:** Legacy stored cents; new model stores dollars (or grams vs kilograms).

**Fix:**
```sql
legacy_amount_cents / 100.0 as legacy_amount
```

Verify the factor with a few sample rows from vld_4 before applying broadly.

---

## 10. NULL-safe joins / fanout

**Symptom in vld_1:** Row counts in A and B differ significantly. vld_3 shows `missing from a` or `missing from b` high.

**Cause:** Not a column issue — a **join** or **filter** in the new model is producing fanout, missing rows, or duplicate keys.

**Fix:** Stop and audit the new model's joins. Common culprits:
- `LEFT JOIN` where `INNER JOIN` was intended (or vice versa)
- Missing `WHERE` filter (e.g. excluding test customers)
- Duplicate keys upstream — verify with `select pk, count(*) from new_model group by 1 having count(*) > 1`
- Timezone shift moving rows across day boundaries

Don't try to paper over join issues with audit-helper standardizations — fix the model.

---

## Adding a new pattern

When you hit a mismatch type that isn't listed here, add a section using the same template:
1. **Symptom** — what you saw in vld_3 or vld_4
2. **Cause** — the underlying data difference
3. **Fix** — the SQL applied to the A side

Patterns documented here become reusable shortcuts for the next migration.
