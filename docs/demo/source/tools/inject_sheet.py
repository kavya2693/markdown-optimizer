"""Inline the exported markdown sheet into compositions/value.html (renders cannot fetch files).

Usage: python3 tools/inject_sheet.py assets/markdown_sheet.json compositions/value.html \
         --rows SKU0222,SKU0315,SKU0195,SKU0271,SKU0199,SKU0169 --animate SKU0222,SKU0315,SKU0195,SKU0271
"""

import argparse
import json
import re

ap = argparse.ArgumentParser()
ap.add_argument("sheet")
ap.add_argument("html")
ap.add_argument("--rows", required=True, help="SKU ids shown as sheet rows, in order")
ap.add_argument("--animate", required=True, help="SKU ids put on the shelf in the 2D scene (max 4)")
a = ap.parse_args()

with open(a.sheet) as fh:
    d = json.load(fh)
by_sku = {r["sku_id"]: r for r in d["rows"]}
rows = a.rows.split(",")
anim = a.animate.split(",")
keep = (
    "sku_id",
    "category",
    "opening_stock",
    "elasticity",
    "depths",
    "planned_sell_through",
    "planned_stock_left",
    "margin",
    "fixed_30_margin",
)
head = (
    "event_id",
    "start_week",
    "weeks",
    "target",
    "skus",
    "opening_stock",
    "margin",
    "fixed_30_margin",
    "sell_through",
    "skus_better_than_fixed",
)
sheet_rows = [{k: by_sku[s][k] for k in keep} | {"animate": anim.index(s) if s in anim else -1} for s in rows]
slim = {k: d[k] for k in head} | {"rows": sheet_rows}
with open(a.html) as fh:
    html = fh.read()
block = "/* SHEET:BEGIN */ const SHEET = " + json.dumps(slim, separators=(",", ":")) + "; /* SHEET:END */"
html, n = re.subn(r"/\* SHEET:BEGIN \*/.*?/\* SHEET:END \*/", lambda _: block, html, flags=re.S)
assert n == 1, "marker not found"
with open(a.html, "w") as fh:
    fh.write(html)
print("injected", len(slim["rows"]), "rows,", len(anim), "on the shelf")
