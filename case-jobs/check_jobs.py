#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Независимо проверяет собранную таблицу: отсутствие ПД, дубли, арифметику.

usage: check_jobs.py [--dir DIR] [--json]
Коды: 0 — нарушений нет, 2 — аргументы, 3 — нет файлов, 4 — найдены нарушения.
"""
import argparse
import csv
import json
import os
import re
import statistics
import sys

FIELDS = ["id", "region", "region_code", "job", "specialisation",
          "employment", "schedule", "experience", "salary_min", "salary_max",
          "currency", "date", "url"]

# Контакты в свободном тексте: почта и российский номер в любой записи.
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?:\+7|\b8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
FORBIDDEN_HEADER = ("contact", "email", "phone", "person")
# Телефон ищем только в текстовых полях: в кодах ОКАТО и ссылках длинные цифры — норма.
TEXT_FIELDS = ("region", "company", "job", "specialisation", "employment", "schedule")
CODE = re.compile(r"^\d{13}$")
URL_PREFIX = "https://trudvsem.ru/"


def load(path):
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        return r.fieldnames or [], list(r)


def midpoint(r):
    lo = int(r["salary_min"] or 0)
    hi = int(r["salary_max"] or 0)
    return (lo + hi) / 2 if (lo and hi) else float(lo or hi)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="data")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    jobs_path = os.path.join(args.dir, "jobs.csv")
    summary_path = os.path.join(args.dir, "summary.json")
    region_path = os.path.join(args.dir, "by_region.csv")
    for p in (jobs_path, summary_path, region_path):
        if not os.path.exists(p):
            print(f"нет файла: {p}", file=sys.stderr)
            return 3

    fieldnames, rows = load(jobs_path)
    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)
    with open(region_path, encoding="utf-8", newline="") as f:
        by_region = list(csv.DictReader(f))

    problems = []

    missing = [f for f in FIELDS if f not in fieldnames]
    if missing:
        problems.append(f"в таблице нет колонок: {missing}")
    leak = [f for f in fieldnames if any(t in f.lower() for t in FORBIDDEN_HEADER)]
    if leak:
        problems.append(f"контактные колонки в таблице: {leak}")

    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        problems.append(f"дубли id: {len(ids) - len(set(ids))}")

    emails = phones = bad_code = bad_url = 0
    for r in rows:
        for k, v in r.items():
            s = str(v)
            emails += len(EMAIL.findall(s))
            if k in TEXT_FIELDS:
                phones += len(PHONE.findall(s))
        if r["region_code"] and not CODE.match(r["region_code"]):
            bad_code += 1
        if not r["url"].startswith(URL_PREFIX):
            bad_url += 1
    if emails:
        problems.append(f"найдены адреса почты: {emails}")
    if phones:
        problems.append(f"найдены телефоны в текстовых полях: {phones}")
    if bad_code:
        problems.append(f"код региона не той формы: {bad_code}")
    if bad_url:
        problems.append(f"ссылок не на trudvsem.ru: {bad_url}")

    for r in rows:
        lo, hi = int(r["salary_min"] or 0), int(r["salary_max"] or 0)
        if lo < 0 or hi < 0:
            problems.append(f"отрицательная зарплата в {r['id']}")
            break
        if lo and hi and lo > hi:
            problems.append(f"минимум больше максимума в {r['id']}")
            break

    sal = [midpoint(r) for r in rows if midpoint(r) > 0]
    recalc = {
        "rows": len(rows),
        "with_salary": len(sal),
        "median_salary": round(statistics.median(sal)) if sal else 0,
    }
    for k, v in recalc.items():
        if summary.get(k) != v:
            problems.append(f"{k}: в сводке {summary.get(k)}, пересчёт {v}")

    region_sum = sum(int(x["count"]) for x in by_region)
    if region_sum != len(rows):
        problems.append(f"сумма по регионам {region_sum} ≠ строк {len(rows)}")
    for x in by_region:
        if int(x["with_salary"]) > int(x["count"]):
            problems.append(f"регион «{x['name']}»: с зарплатой больше, чем всего")
            break

    result = {"rows": len(rows), "emails": emails, "phones": phones,
              "unique_ids": len(set(ids)), "region_sum": region_sum,
              "problems": problems, "ok": not problems}
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"строк {result['rows']}, уникальных id {result['unique_ids']}, "
              f"почт {emails}, телефонов {phones}, нарушений {len(problems)}")
        for p in problems:
            print(f"  ! {p}")
    return 0 if not problems else 4


if __name__ == "__main__":
    sys.exit(main())
