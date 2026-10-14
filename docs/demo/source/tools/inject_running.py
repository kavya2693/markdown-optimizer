"""Inline the outputs that slide 06 draws into compositions/s04-running.html (renders cannot fetch files).

The repo writes no plots, so slide 06 draws its two charts from these files, unchanged:
  outputs/elasticity_by_sku.csv   true vs estimated own-price elasticity, 400 SKUs (no / partial pooling)
  outputs/elasticity_error.csv    mean absolute error per estimator
  outputs/markdown_by_event.csv   margin per clearance event for each policy

Usage: python3 tools/inject_running.py <repo> compositions/s04-running.html
"""

import argparse
import json
import re
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("repo", type=Path)
ap.add_argument("html")
a = ap.parse_args()
out = a.repo / "outputs"

sku = pd.read_csv(out / "elasticity_by_sku.csv")
wide = sku.pivot(index="sku_id", columns="estimator", values="beta_hat")
true = sku.drop_duplicates("sku_id").set_index("sku_id")["beta_true"]
err = pd.read_csv(out / "elasticity_error.csv").set_index("estimator")
ev = pd.read_csv(out / "markdown_by_event.csv")
POOLS = ("no_pooling", "partial_pooling")
data = {
    "pts": [
        [round(float(v), 3) for v in (true[s], wide.at[s, "no_pooling"], wide.at[s, "partial_pooling"])]
        for s in sorted(wide.index)
    ],
    "mae": {k: round(float(err.at[k, "beta_mae"]), 3) for k in POOLS},
    "mae_few": {k: round(float(err.at[k, "beta_mae_few_promos"]), 3) for k in POOLS},
    "events": [
        {
            "event_id": e,
            **{
                p: round(float(ev[(ev["event_id"] == e) & (ev["policy"] == p)]["margin"].iat[0]), 2)
                for p in ("fixed_30", "partial_pooling", "oracle")
            },
        }
        for e in ("E1", "E2", "E3")
    ],
}
with open(a.html) as fh:
    html = fh.read()
block = "/* DATA:BEGIN */ const DATA = " + json.dumps(data, separators=(",", ":")) + "; /* DATA:END */"
html, n = re.subn(r"/\* DATA:BEGIN \*/.*?/\* DATA:END \*/", lambda _: block, html, flags=re.S)
assert n == 1, "marker not found"
with open(a.html, "w") as fh:
    fh.write(html)
print("injected", len(data["pts"]), "SKUs,", len(data["events"]), "events")
