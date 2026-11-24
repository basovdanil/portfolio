#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Считает разрезы по собранным вакансиям.

usage: stats_jobs.py [--csv FILE] [--out DIR] [--json]
Коды: 0 — готово, 2 — аргументы, 3 — нет файла, 4 — битые данные.
"""
import argparse
import csv
import json
import os
import statistics
import sys


def load(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def midpoint(r):
    lo = int(r["salary_min"] or 0)
    hi = int(r["salary_max"] or 0)
    if lo and hi:
        return (lo + hi) / 2
    return float(lo or hi)


def agg(rows, key):
    groups = {}
    for r in rows:
        groups.setdefault(r[key] or "не указано", []).append(r)
    out = []
    for name, items in groups.items():
        sal = [midpoint(r) for r in items if midpoint(r) > 0]
        out.append({
            "name": name,
            "count": len(items),
            "with_salary": len(sal),
            "median": round(statistics.median(sal)) if sal else 0,
            "no_salary_share": round(1 - len(sal) / len(items), 3),
        })
    out.sort(key=lambda x: (-x["count"], x["name"]))
    return out


def write_csv(path, rows, fields):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default="data/jobs.csv")
    ap.add_argument("--out", default="data")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.csv):
        print(f"нет файла: {args.csv}", file=sys.stderr)
        return 3
    rows = load(args.csv)
    if not rows:
        print("пустая таблица", file=sys.stderr)
        return 4

    bad = [r for r in rows if not r.get("region") or not r.get("job")]
    if bad:
        print(f"строк без региона или профессии: {len(bad)}", file=sys.stderr)
        return 4

    by_region = agg(rows, "region")
    by_spec = agg(rows, "specialisation")
    sal = [midpoint(r) for r in rows if midpoint(r) > 0]
    dates = sorted(r["date"] for r in rows if r.get("date"))

    os.makedirs(args.out, exist_ok=True)
    write_csv(os.path.join(args.out, "by_region.csv"), by_region,
              ["name", "count", "with_salary", "median", "no_salary_share"])
    write_csv(os.path.join(args.out, "by_specialisation.csv"), by_spec,
              ["name", "count", "with_salary", "median", "no_salary_share"])

    summary = {
        "rows": len(rows),
        "with_salary": len(sal),
        "median_salary": round(statistics.median(sal)) if sal else 0,
        "mean_salary": round(sum(sal) / len(sal)) if sal else 0,
        "regions": len(by_region),
        "specialisations": len(by_spec),
        "top_region": by_region[0]["name"] if by_region else "",
        "top_region_count": by_region[0]["count"] if by_region else 0,
        "date_min": dates[0] if dates else "",
        "date_max": dates[-1] if dates else "",
    }
    with open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(f"строк {summary['rows']}, с зарплатой {summary['with_salary']}, "
              f"медиана {summary['median_salary']} ₽, регионов {summary['regions']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
