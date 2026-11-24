#!/usr/bin/env python3
"""usage: check_osv.py [--dir DIR] [--json]

Независимая проверка ОСВ: пересчитывает итоги и арифметику каждой строки
из CSV, находит кредитовое сальдо на активных счетах, дебетовое — на
пассивных и отрицательные обороты. Сверяет найденное с ожидаемым набором
из meta.json.

Коды возврата: 0 — набор найденного совпал с ожидаемым;
                2 — аргументы; 3 — нет файлов;
                4 — расхождение с ожидаемым набором.
"""
import argparse
import csv
import json
import os
import sys


def load(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    return float(v) if v not in ("", None) else 0.0


def check(rows):
    findings = []
    totals = {"open_debit": 0.0, "open_credit": 0.0, "turn_debit": 0.0,
              "turn_credit": 0.0, "close_debit": 0.0, "close_credit": 0.0}

    for r in rows:
        acc = r["account"]
        od, oc = num(r["open_debit"]), num(r["open_credit"])
        td, tc = num(r["turn_debit"]), num(r["turn_credit"])
        cd, cc = num(r["close_debit"]), num(r["close_credit"])
        for k, v in (("open_debit", od), ("open_credit", oc), ("turn_debit", td),
                     ("turn_credit", tc), ("close_debit", cd), ("close_credit", cc)):
            totals[k] += v

        open_net = od - oc
        turn_net = td - tc
        close_net = cd - cc
        diff = round(close_net - (open_net + turn_net), 2)
        if abs(diff) > 0.01:
            findings.append({"code": "row_mismatch", "account": acc, "value": diff})

        kind = r["type"]
        if kind == "активный" and cc > 0.01:
            findings.append({"code": "red_balance", "account": acc, "value": cc})
        if kind == "пассивный" and cd > 0.01:
            findings.append({"code": "red_balance", "account": acc, "value": cd})

        if td < -0.01:
            findings.append({"code": "negative_turnover", "account": acc, "value": td})
        if tc < -0.01:
            findings.append({"code": "negative_turnover", "account": acc, "value": tc})

    for key, code in (("open", "totals_open"), ("turn", "totals_turn"), ("close", "totals_close")):
        diff = round(totals[f"{key}_debit"] - totals[f"{key}_credit"], 2)
        if abs(diff) > 0.01:
            findings.append({"code": code, "account": "", "value": diff})

    return findings, totals


def normalize(findings):
    return sorted((f["code"], f["account"], round(float(f["value"]), 2)) for f in findings)


def main():
    ap = argparse.ArgumentParser(prog="check_osv.py")
    ap.add_argument("--dir", default="data")
    ap.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args()
    except SystemExit as e:
        return 0 if e.code == 0 else 2

    csv_path = os.path.join(args.dir, "osv.csv")
    meta_path = os.path.join(args.dir, "meta.json")
    missing = [p for p in (csv_path, meta_path) if not os.path.exists(p)]
    if missing:
        print("нет файлов: " + ", ".join(missing), file=sys.stderr)
        return 3

    rows = load(csv_path)
    expected = json.load(open(meta_path, encoding="utf-8"))["expected"]
    findings, totals = check(rows)
    got, want = normalize(findings), normalize(expected)
    match = got == want

    if args.json:
        print(json.dumps({
            "rows": len(rows), "match": match, "findings": findings,
            "totals": {k: round(v, 2) for k, v in totals.items()},
        }, ensure_ascii=False))
    else:
        print(f"строк: {len(rows)}, найдено: {len(findings)}, ожидалось: {len(expected)}")
        for f in findings:
            acc = f" счёт {f['account']}" if f["account"] else ""
            print(f"  {f['code']}{acc}: {f['value']:,.2f}".replace(",", " "))
        for k, v in totals.items():
            print(f"  {k}: {v:,.2f}".replace(",", " "))
        print("совпало с ожидаемым" if match else "РАСХОЖДЕНИЕ с ожидаемым набором")

    return 0 if match else 4


if __name__ == "__main__":
    sys.exit(main())
