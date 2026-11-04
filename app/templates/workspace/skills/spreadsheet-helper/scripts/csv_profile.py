#!/usr/bin/env python3
"""Profile a CSV/TSV file: columns, types, missing values, numeric stats, top values. Standard library only.

Usage: csv_profile.py data.csv [--top 5]
"""
import csv
import statistics
import sys
from collections import Counter
from datetime import datetime


def kind(v):
    for f in (int, float):
        try:
            f(v.replace(",", "")) if f is float else f(v)
            return "int" if f is int else "float"
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y"):
        try:
            datetime.strptime(v, fmt)
            return "date"
        except ValueError:
            pass
    return "text"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 5
    raw = open(args[0], encoding="utf-8-sig", errors="replace", newline="").read()
    try:
        dialect = csv.Sniffer().sniff(raw[:20000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(raw.splitlines(), dialect))
    if not rows:
        sys.exit("Empty file")
    head, data = rows[0], rows[1:]
    print(f"Rows: {len(data)}   Columns: {len(head)}   Delimiter: {dialect.delimiter!r}\n")
    for i, name in enumerate(head):
        col = [r[i].strip() if i < len(r) else "" for r in data]
        vals = [v for v in col if v]
        kinds = Counter(kind(v) for v in vals)
        k = "int" if kinds and set(kinds) <= {"int"} else "float" if kinds and set(kinds) <= {"int", "float"} else (kinds.most_common(1)[0][0] if kinds else "empty")
        print(f"## {name}  [{k}]  filled {len(vals)}/{len(col)}  unique {len(set(vals))}")
        if k in ("int", "float"):
            nums = [float(v.replace(",", "")) for v in vals]
            print(f"   min {min(nums):g}  max {max(nums):g}  mean {statistics.mean(nums):.4g}  median {statistics.median(nums):g}  sum {sum(nums):.6g}")
        else:
            print("   top: " + "; ".join(f"{v} ({c})" for v, c in Counter(vals).most_common(top)))

    seen = Counter(tuple(r) for r in data)
    dups = sum(c - 1 for c in seen.values() if c > 1)
    print(f"\nExact duplicate rows: {dups}")


main()
