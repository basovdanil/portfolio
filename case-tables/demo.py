#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Демо трёх ручных операций: строит входные файлы, гоняет CLI и сверяет результат.

usage: demo.py [--work DIR] [--json]
Коды: 0 — все сверки сошлись, 2 — аргументы, 3 — нет входа, 4 — расхождение.
"""
import argparse
import csv
import json
import os
import subprocess
import sys

COMPANIES = ["ООО «Кедр»", "ООО «Ласточка»", "ООО «Мельник»", "ООО «Полярник»",
             "ООО «Сосна»", "ООО «Тайфун»", "ООО «Верста»", "ООО «Купава»"]
WAREHOUSES = ["Склад Москва", "Склад Казань", "Склад Новосибирск"]
STATUSES = ["черновик", "согласован", "оплачен"]
FIELDS = ["id", "дата", "контрагент", "сумма", "склад", "статус"]


def rows_for(start, end):
    out = []
    for i in range(start, end + 1):
        out.append({
            "id": f"R-{i:04d}",
            "дата": f"2026-11-{(i - 1) % 28 + 1:02d}",
            "контрагент": COMPANIES[i % len(COMPANIES)],
            "сумма": 10000 + i * 137,
            "склад": WAREHOUSES[i % len(WAREHOUSES)],
            "статус": STATUSES[i % len(STATUSES)],
        })
    return out


def write(path, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def run(args):
    proc = subprocess.run([sys.executable, "tables.py", *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"tables.py {' '.join(args)} → код {proc.returncode}: {proc.stderr.strip()}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default="work")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    src = os.path.join(args.work, "in")
    out = os.path.join(args.work, "out")
    os.makedirs(src, exist_ok=True)
    os.makedirs(out, exist_ok=True)

    reg1 = rows_for(1, 25)
    reg2 = rows_for(20, 45)
    reg3 = rows_for(40, 60)
    p1, p2, p3 = (os.path.join(src, f"reg-0{i}.csv") for i in (1, 2, 3))
    write(p1, reg1)
    write(p2, reg2)
    write(p3, reg3)

    v1 = run(["merge", "--inputs", p1, p2, "--key", "id", "--out", os.path.join(out, "v1.csv"), "--json"])
    v2_full = run(["merge", "--inputs", p1, p2, p3, "--key", "id", "--out", os.path.join(out, "v2-full.csv"), "--json"])

    v2_rows = read(os.path.join(out, "v2-full.csv"))
    v2_rows = [r for r in v2_rows if r["id"] != "R-0010"]
    for r in v2_rows:
        if r["id"] == "R-0005":
            r["сумма"] = str(int(r["сумма"]) + 1000)
    v2_path = os.path.join(out, "v2.csv")
    write(v2_path, v2_rows)

    d = run(["diff", "--old", os.path.join(out, "v1.csv"), "--new", v2_path, "--key", "id",
             "--out", os.path.join(out, "diff.csv"), "--json"])
    s = run(["split", "--input", v2_path, "--by", "склад", "--outdir", os.path.join(out, "parts"), "--json"])

    parts_rows = 0
    for info in s["detail"].values():
        parts_rows += len(read(os.path.join(out, "parts", info["file"])))

    expected = {
        "merge_v1_rows": (v1["rows_out"], 45),
        "merge_v1_dups": (v1["duplicates"], 6),
        "merge_v2_rows": (v2_full["rows_out"], 60),
        "merge_v2_dups": (v2_full["duplicates"], 12),
        "diff_added": (d["added"], 15),
        "diff_removed": (d["removed"], 1),
        "diff_changed": (d["changed"], 1),
        "split_parts": (s["parts"], 3),
        "split_rows": (parts_rows, len(v2_rows)),
    }
    mismatches = [f"{k}: получено {got}, ожидалось {want}" for k, (got, want) in expected.items() if got != want]

    report = {
        "inputs": {"files": 3, "rows": len(reg1) + len(reg2) + len(reg3)},
        "merge_v1": v1, "merge_v2": v2_full, "diff": d,
        "split": {"parts": s["parts"], "rows": parts_rows},
        "checks": {k: {"got": g, "want": w, "ok": g == w} for k, (g, w) in expected.items()},
        "ok": not mismatches, "mismatches": mismatches,
    }
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(f"вход: 3 файла, {report['inputs']['rows']} строк")
        print(f"слияние v1: {v1['rows_out']} строк, дублей {v1['duplicates']}")
        print(f"слияние v2: {v2_full['rows_out']} строк, дублей {v2_full['duplicates']}")
        print(f"сравнение: +{d['added']} / -{d['removed']} / ~{d['changed']}")
        print(f"разложение: {s['parts']} части, {parts_rows} строк")
        print("сверки: " + ("все сошлись" if not mismatches else "; ".join(mismatches)))
    return 0 if not mismatches else 4


if __name__ == "__main__":
    sys.exit(main())
