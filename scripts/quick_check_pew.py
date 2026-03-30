import csv
from pathlib import Path
from collections import defaultdict

p = Path("data/interim/pew/pew_question_inventory.csv")
rows = list(csv.DictReader(p.open(encoding="utf-8", newline="")))

def miss(v):
    return (v or "").strip().lower() in {"", "unknown", "na", "n/a", "null", "none"}

for c in ["inventory_id","pew_wave","field_dates","dataset_file","variable_name"]:
    print(c, sum(1 for r in rows if miss(r.get(c))))

by_wave = defaultdict(int)
for r in rows:
    if miss(r.get("field_dates")):
        by_wave[r.get("pew_wave","")] += 1
print("waves_with_missing_field_dates", len(by_wave))