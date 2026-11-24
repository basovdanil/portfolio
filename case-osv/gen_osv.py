#!/usr/bin/env python3
"""usage: gen_osv.py [--out DIR] [--json]

Генерирует синтетическую оборотно-сальдовую ведомость (ОСВ) небольшой
торговой компании за IV квартал и сохраняет ожидаемый результат проверок.
Дефекты не «пишутся руками в отчёт», а закладываются в данные:
кредитовое сальдо на активном счёте, арифметический разрыв по счёту 62,
отрицательный оборот по счёту 76.

Все контрагенты и показатели вымышлены: реальных организаций и людей нет.

Коды возврата: 0 — успех; 2 — аргументы; 3 — не удалось записать файлы.
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

# (счёт, наименование, тип, сальдо начальное нетто, оборот нетто)
# нетто > 0 — дебетовое, < 0 — кредитовое.
ROWS = [
    ("01", "Основные средства", "активный", 1_200_000, 0),
    ("10", "Материалы", "активный", 480_000, 250_000),
    ("19", "НДС по приобретённым ценностям", "активный", 96_000, 12_000),
    ("41", "Товары", "активный", 620_000, -700_000),
    ("50", "Касса", "активный", 25_000, -10_000),
    ("51", "Расчётные счета", "активный", 340_000, 300_000),
    ("60", "Расчёты с поставщиками", "пассивный", -410_000, 100_000),
    ("62", "Расчёты с покупателями", "активно-пассивный", 720_000, 150_000),
    ("68", "Расчёты по налогам и сборам", "пассивный", -85_000, 30_000),
    ("69", "Расчёты по социальному страхованию", "пассивный", -62_000, 18_000),
    ("70", "Расчёты с персоналом по оплате труда", "пассивный", -300_000, 200_000),
    ("76", "Расчёты с разными дебиторами и кредиторами", "активно-пассивный", -34_000, 0),
    ("80", "Уставный капитал", "пассивный", -1_000_000, 0),
    ("83", "Добавочный капитал", "пассивный", -1_000_000, 0),
    ("99", "Прибыли и убытки", "пассивный", 0, -350_000),
]


def sides(net):
    return (net, 0) if net >= 0 else (0, -net)


def main():
    ap = argparse.ArgumentParser(prog="gen_osv.py")
    ap.add_argument("--out", default="data")
    ap.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args()
    except SystemExit as e:
        return 0 if e.code == 0 else 2

    company = "ООО «Северный склад» (данные вымышлены)"
    period = "01.10.2026 — 31.12.2026"

    # 84 закрывает разрыв по начальному сальдо: получаем баланс на начало.
    plug = -sum(r[3] for r in ROWS)
    rows = list(ROWS) + [("84", "Нераспределённая прибыль", "активно-пассивный", plug, 0)]

    table = []
    for code, name, kind, open_net, turn_net in rows:
        od, oc = sides(open_net)
        td, tc = sides(turn_net)
        close_net = open_net + turn_net
        cd, cc = sides(close_net)
        table.append({
            "account": code, "name": name, "type": kind,
            "open_debit": od, "open_credit": oc,
            "turn_debit": td, "turn_credit": tc,
            "close_debit": cd, "close_credit": cc,
        })

    by_code = {r["account"]: r for r in table}

    # Дефект 1: арифметический разрыв в закрытии по 62 (+30 000 к дебету).
    by_code["62"]["close_debit"] += 30_000

    # Дефект 2: отрицательный оборот по кредиту 76.
    r76 = by_code["76"]
    r76["turn_credit"] = -12_000
    close_net_76 = (r76["open_debit"] - r76["open_credit"]) + (r76["turn_debit"] - r76["turn_credit"])
    r76["close_debit"], r76["close_credit"] = sides(close_net_76)

    # Дефект 3: кредитовое сальдо на активном счёте 41 возникает из данных.
    red = by_code["41"]
    red_account = "41"
    red_value = red["close_credit"]

    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, "osv.csv")
    cols = ["account", "name", "type", "open_debit", "open_credit",
            "turn_debit", "turn_credit", "close_debit", "close_credit"]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(table)

    expected = [
        {"code": "row_mismatch", "account": "62", "value": 30_000},
        {"code": "totals_close", "account": "", "value": 42_000},
        {"code": "totals_turn", "account": "", "value": 12_000},
        {"code": "red_balance", "account": red_account, "value": red_value},
        {"code": "negative_turnover", "account": "76", "value": -12_000},
    ]
    meta = {
        "company": company,
        "period": period,
        "rows": len(table),
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "expected": expected,
    }
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps({"csv": csv_path, "rows": len(table), "expected": expected,
                          "generated_at": meta["generated_at"]}, ensure_ascii=False))
    else:
        print(f"wrote {csv_path}: {len(table)} счетов, дефектов заложено: {len(expected)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
