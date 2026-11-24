#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Собирает вакансии из открытых данных в таблицу по белому списку полей.

usage: fetch_jobs.py (--from-raw DIR | --live) [--out FILE] [--json]
Коды: 0 — готово, 2 — аргументы, 3 — нет исходных данных, 4 — ошибка разбора.
"""
import argparse
import csv
import json
import os
import sys

FIELDS = ["id", "region", "region_code", "company", "job", "specialisation",
          "employment", "schedule", "experience", "salary_min", "salary_max",
          "currency", "date", "url"]

FORBIDDEN = ("contact", "email", "phone", "person", "requirements", "duty", "term")

API = "https://opendata.trudvsem.ru/api/v1/vacancies"
UA = "MultiTool-research/1.0 (+contact via app)"


def pick(vac):
    region = vac.get("region") or {}
    company = vac.get("company") or {}
    req = vac.get("requirement") or {}
    cat = vac.get("category") or {}
    return {
        "id": str(vac.get("id") or ""),
        "region": (region.get("name") or "").strip(),
        "region_code": str(region.get("region_code") or ""),
        "company": (company.get("name") or "").strip(),
        "job": (vac.get("job-name") or "").strip(),
        "specialisation": (cat.get("specialisation") or "").strip(),
        "employment": (vac.get("employment") or "").strip(),
        "schedule": (vac.get("schedule") or "").strip(),
        "experience": req.get("experience", ""),
        "salary_min": int(vac.get("salary_min") or 0),
        "salary_max": int(vac.get("salary_max") or 0),
        "currency": (vac.get("currency") or "").strip(),
        "date": str(vac.get("creation-date") or "")[:10],
        "url": (vac.get("vac_url") or "").strip(),
    }


def rows_from_dump(obj):
    res = obj.get("results") or {}
    items = res.get("vacancies") or []
    out = []
    for item in items:
        vac = item.get("vacancy") if isinstance(item, dict) else None
        if isinstance(vac, dict):
            out.append(pick(vac))
    return out


def rows_from_dir(path):
    if not os.path.isdir(path):
        print(f"нет папки: {path}", file=sys.stderr)
        return None
    rows, bad = [], 0
    for name in sorted(os.listdir(path)):
        if not name.lower().endswith(".json"):
            continue
        full = os.path.join(path, name)
        try:
            with open(full, encoding="utf-8") as f:
                rows.extend(rows_from_dump(json.load(f)))
        except (json.JSONDecodeError, OSError) as e:
            bad += 1
            print(f"пропущен {name}: {e}", file=sys.stderr)
    if bad and not rows:
        return None
    return rows


def rows_from_api(limit=100):
    import urllib.parse
    import urllib.request
    q = urllib.parse.urlencode({"limit": limit})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return rows_from_dump(json.load(r))


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        if not r["id"] or r["id"] in seen:
            continue
        seen.add(r["id"])
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-raw", metavar="DIR", help="папка с JSON-дампами API")
    src.add_argument("--live", action="store_true", help="один запрос к открытому API")
    ap.add_argument("--out", default="data/jobs.csv")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.live:
        try:
            rows = rows_from_api()
        except Exception as e:
            print(f"API недоступен: {e}", file=sys.stderr)
            return 3
    else:
        rows = rows_from_dir(args.from_raw)
        if rows is None:
            return 3

    rows = dedupe(rows)
    if not rows:
        print("не нашлось ни одной вакансии", file=sys.stderr)
        return 4

    leaked = [f for f in FIELDS if any(t in f for t in FORBIDDEN)]
    if leaked:
        print(f"запрещённое поле в белом списке: {leaked}", file=sys.stderr)
        return 4

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})

    with_salary = sum(1 for r in rows if r["salary_min"] or r["salary_max"])
    if args.json:
        print(json.dumps({"out": args.out, "rows": len(rows), "with_salary": with_salary}, ensure_ascii=False))
    else:
        print(f"{args.out}: {len(rows)} строк, с зарплатой {with_salary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
