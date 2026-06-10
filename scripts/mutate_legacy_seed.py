"""
mutate_legacy_seed.py — rewrite seeds/legacy_int_order_items__metrics.csv as a
fake legacy ERP export, so it diverges from the live `int_order_items__metrics`
model in ways that map 1:1 to entries in models/audit_helper/patterns.md.

Demo arc: invoking the dbt-data-audit skill against this seed (A) vs the live
model (B) walks the user through diagnosing each pattern in sequence.

Patterns applied (numbered to match patterns.md sections):
  #2 Sentinel dates           SHIP_DATE NULL -> '1900-01-01'
  #3 Whitespace               RECIPIENT_NAME -> append '  ' on ~10% of rows
  #4 Case sensitivity         RECIPIENT_COUNTRY -> upper-case
  #5 String prefix            ORDER_NUMBER -> 'LEG-' + value
  #6 Numeric precision        NET_TOTAL -> round to 2 decimals
  #8 Boolean encoding         HAD_DISCOUNT TRUE/FALSE -> Y/N
  #9 Unit conversion          UNIT_PRICE -> integer cents (* 100)

Not applied:
  #1 Empty string vs NULL — RECIPIENT_REGION has 0 NULL rows in this dataset,
     no natural place to showcase the pattern. Mentioned in patterns.md but
     not demonstrated by this seed.
  #7 Timezone offsets — dataset is dates only, no time-of-day, so no realistic
     timezone story.

Row-level:
  Drop 3 rows by deterministic index -> showcases `in_b_only`
  Duplicate 1 row with PK suffix '-A' -> showcases `in_a_only`

Metadata column:
  Add LOADED_AT with timestamps in the 30 days preceding RUN_REFERENCE.
  The skill's exclusion heuristic should flag this for exclusion automatically.

Usage:
  python scripts/mutate_legacy_seed.py
  dbt seed -s legacy_int_order_items__metrics
"""

import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(42)

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_PATH = REPO_ROOT / "seeds" / "legacy_int_order_items__metrics.csv"

DROP_INDICES = {17, 842, 1956}
DUPLICATE_INDEX = 503
WHITESPACE_SAMPLE_RATE = 0.10
RUN_REFERENCE = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def random_loaded_at() -> str:
    delta_seconds = random.randint(0, 30 * 24 * 3600)
    return (RUN_REFERENCE - timedelta(seconds=delta_seconds)).strftime("%Y-%m-%d %H:%M:%S")


def mutate(row: dict) -> dict:
    if row["SHIP_DATE"] == "":
        row["SHIP_DATE"] = "1900-01-01"

    if random.random() < WHITESPACE_SAMPLE_RATE:
        row["RECIPIENT_NAME"] = row["RECIPIENT_NAME"] + "  "

    row["RECIPIENT_COUNTRY"] = row["RECIPIENT_COUNTRY"].upper()

    row["ORDER_NUMBER"] = "LEG-" + row["ORDER_NUMBER"]

    row["NET_TOTAL"] = f"{float(row['NET_TOTAL']):.2f}"

    flag = row["HAD_DISCOUNT"].strip().upper()
    if flag == "TRUE":
        row["HAD_DISCOUNT"] = "Y"
    elif flag == "FALSE":
        row["HAD_DISCOUNT"] = "N"

    row["UNIT_PRICE"] = str(int(round(float(row["UNIT_PRICE"]) * 100)))

    row["LOADED_AT"] = random_loaded_at()
    return row


def main() -> None:
    with SEED_PATH.open(newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise RuntimeError(f"{SEED_PATH} has no header row")
        rows = list(reader)

    if "LOADED_AT" in fieldnames:
        raise RuntimeError(
            f"{SEED_PATH} already has a LOADED_AT column — the script has already been "
            "applied. Revert with `git checkout seeds/legacy_int_order_items__metrics.csv` "
            "before re-running."
        )

    new_fieldnames = list(fieldnames) + ["LOADED_AT"]

    output_rows = []
    phantom_source = None
    for idx, row in enumerate(rows):
        if idx in DROP_INDICES:
            continue
        if idx == DUPLICATE_INDEX:
            phantom_source = dict(row)
        output_rows.append(mutate(dict(row)))

    if phantom_source is None:
        raise RuntimeError(f"DUPLICATE_INDEX {DUPLICATE_INDEX} out of range (rows={len(rows)})")

    phantom = mutate(phantom_source)
    phantom["ORDER_ITEM_SK"] = phantom["ORDER_ITEM_SK"] + "-A"
    output_rows.append(phantom)

    with SEED_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"input rows : {len(rows)}")
    print(f"dropped    : {len(DROP_INDICES)} (indices {sorted(DROP_INDICES)})")
    print(f"phantom    : 1 (source index {DUPLICATE_INDEX}, PK suffixed with '-A')")
    print(f"output rows: {len(output_rows)}")
    print(f"new column : LOADED_AT")
    print(f"wrote      : {SEED_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
