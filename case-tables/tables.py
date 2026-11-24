#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Три ручные операции с таблицами: слить, сравнить, разложить.

usage: tables.py merge --inputs a.csv b.csv --key id --out merged.csv [--json]
       tables.py diff --old v1.csv --new v2.csv --key id --out diff.csv [--json]
       tables.py split --input v2.csv --by склад --outdir parts [--json]
Коды: 0 — готово, 2 — аргументы, 3 — нет файлов, 4 — ошибка данных.
"""
import argparse
import csv
import json
import os
import re
import sys

BAD_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return (r.fieldnames or []), list(r)


def write_csv(path, fields, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def safe_name(value):
    name = BAD_CHARS.sub("_", (value or "").strip()) or "без_значения"
    return name[:60]


def merge(args):
    fields, rows_in, seen, order, dups = [], 0, {}, [], 0
    for path in args.inputs:
        if not os.path.exists(path):
            print(f"нет файла: {path}", file=sys.stderr)
            return 3
        head, rows = read_csv(path)
        for h in head:
            if h not in fields:
                fields.append(h)
        for r in rows:
            rows_in += 1
            key = r.get(args.key, "")
            if not key:
                print(f"пустой ключ {args.key} в {path}", file=sys.stderr)
                return 4
            if key in seen:
                dups += 1
                continue
            seen[key] = True
            order.append(r)
    if args.key not in fields:
        print(f"нет колонки {args.key}", file=sys.stderr)
        return 4
    write_csv(args.out, fields, order)
    return {"out": args.out, "files": len(args.inputs), "rows_in": rows_in,
            "rows_out": len(order), "duplicates": dups}


def diff(args):
    for path in (args.old, args.new):
        if not os.path.exists(path):
            print(f"нет файла: {path}", file=sys.stderr)
            return 3
    fields, old = read_csv(args.old)
    new_fields, new = read_csv(args.new)
    extra = [f for f in new_fields if f not in fields]
    fields = fields + extra
    if args.key not in fields:
        print(f"нет колонки {args.key}", file=sys.stderr)
        return 4

    om = {r[args.key]: r for r in old}
    nm = {r[args.key]: r for r in new}
    added = [nm[k] for k in nm if k not in om]
    removed = [om[k] for k in om if k not in nm]
    changed = []
    for k, r in nm.items():
        if k not in om:
            continue
        if any((om[k].get(f) or "") != (r.get(f) or "") for f in fields if f != args.key):
            changed.append(r)

    out_rows = []
    for r in added:
        out_rows.append({**r, "_change": "добавлено"})
    for r in removed:
        out_rows.append({**r, "_change": "удалено"})
    for r in changed:
        out_rows.append({**r, "_change": "изменено"})
    write_csv(args.out, fields + ["_change"], out_rows)
    return {"out": args.out, "added": len(added), "removed": len(removed),
            "changed": len(changed), "rows_old": len(old), "rows_new": len(new)}


def split(args):
    if not os.path.exists(args.input):
        print(f"нет файла: {args.input}", file=sys.stderr)
        return 3
    fields, rows = read_csv(args.input)
    if args.by not in fields:
        print(f"нет колонки {args.by}", file=sys.stderr)
        return 4
    groups = {}
    for r in rows:
        groups.setdefault(r.get(args.by, ""), []).append(r)
    manifest = {}
    used = set()
    for value, items in groups.items():
        name = safe_name(value) + ".csv"
        while name in used:
            name = name[:-4] + "_.csv"
        used.add(name)
        write_csv(os.path.join(args.outdir, name), fields, items)
        manifest[value] = {"file": name, "rows": len(items)}
    manifest_path = os.path.join(args.outdir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return {"outdir": args.outdir, "parts": len(manifest), "rows": len(rows),
            "manifest": manifest_path, "detail": manifest}


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("merge", help="слить файлы по ключу, дубли отбросить")
    m.add_argument("--inputs", nargs="+", required=True)
    m.add_argument("--key", required=True)
    m.add_argument("--out", required=True)
    m.add_argument("--json", action="store_true")
    m.set_defaults(func=merge)

    d = sub.add_parser("diff", help="сравнить две версии таблицы")
    d.add_argument("--old", required=True)
    d.add_argument("--new", required=True)
    d.add_argument("--key", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=diff)

    s = sub.add_parser("split", help="разложить таблицу по значению колонки")
    s.add_argument("--input", required=True)
    s.add_argument("--by", required=True)
    s.add_argument("--outdir", required=True)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=split)
    return ap


def main():
    args = build_parser().parse_args()
    result = args.func(args)
    if isinstance(result, int):
        return result
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(" ".join(f"{k}={v}" for k, v in result.items() if k != "detail"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
