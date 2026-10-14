"""Re-run the repo's own pipeline for ONE clearance event and export the analyst's markdown sheet.

Same data (seed 7), estimator (partial pooling), controls refit, 210-path ladder search,
75% sell-through target and scorer (400 paired draws on the true curve, seed 11) as `make run`,
restricted to clearance event E1 (100 SKUs, starting 2026-01-26). Elasticities are still
estimated on all 400 SKUs, because pooling borrows across each category.
The result must equal the E1 rows of outputs/markdown_plan.csv; the audit report checks this.

Run:  cd <repo> && PYTHONPATH=src .venv/bin/python <this file> <out.json>
"""

import json
import sys
from pathlib import Path

import numpy as np

from markdown_optimizer.config import LADDER, POLICY
from markdown_optimizer.data import load
from markdown_optimizer.elasticity import estimate, fit_controls
from markdown_optimizer.features import prepare
from markdown_optimizer.optimize import fixed_plan, ladder_paths, plan_events
from markdown_optimizer.simulate import model_demand, simulate

EVENT = "E1"
ds = load(Path("data"))
prepared = prepare(ds.sales)
est = estimate(prepared)["partial_pooling"].set_index("sku_id")
coefs = fit_controls(prepared, est.reset_index())
last_cpi = prepared.sort_values("t").groupby("sku_id")["competitor_index"].last()
demand_fn = model_demand(coefs, last_cpi)

# simulate() seeds each SKU-event by its row index in the full events table, so keep that index.
events = ds.events
idx = np.flatnonzero(events["event_id"].to_numpy() == EVENT)
assert idx[0] == 0 and (np.diff(idx) == 1).all(), "E1 must be the first block of events.csv"
ev = events.iloc[idx].reset_index(drop=True)

plan = plan_events(ev, demand_fn)
truth = ds.truth.set_index("sku_id")
future = ds.future_cpi.set_index(["sku_id", "t"])["competitor_index"]
out_plan = simulate(ev, plan, truth, future, draws=400)
out_fix = simulate(ev, fixed_plan(ev), truth, future, draws=400)

paths = ladder_paths(POLICY.event_weeks)
depths = np.array(LADDER)
rows = []
for i, e in ev.iterrows():
    p = plan.iloc[i]
    path = [float(p[f"depth_w{w + 1}"]) for w in range(POLICY.event_weeks)]
    # planner's expected stock left after each week on the chosen path (what the sheet promises)
    mu = demand_fn(e, depths)
    rung = [int(np.argmin(np.abs(depths - d))) for d in path]
    left, stock_left = float(e["opening_stock"]), []
    for w, r in enumerate(rung):
        left -= min(left, float(mu[r, w]))
        stock_left.append(round(left / float(e["opening_stock"]), 4))
    rows.append(
        {
            "sku_id": e["sku_id"],
            "category": e["category"],
            "opening_stock": int(e["opening_stock"]),
            "regular_price": float(e["regular_price"]),
            "unit_cost": float(e["unit_cost"]),
            "elasticity": round(float(est.at[e["sku_id"], "beta"]), 3),
            "depths": path,
            "planned_sell_through": round(float(p["planned_sell_through"]), 4),
            "planned_stock_left": stock_left,
            "margin": round(float(out_plan.at[i, "margin"]), 2),
            "sell_through": round(float(out_plan.at[i, "sell_through"]), 4),
            "fixed_30_margin": round(float(out_fix.at[i, "margin"]), 2),
            "fixed_30_sell_through": round(float(out_fix.at[i, "sell_through"]), 4),
        }
    )

out = {
    "event_id": EVENT,
    "start_week": str(ev["start_week"].iat[0]),
    "weeks": POLICY.event_weeks,
    "target": POLICY.sell_through_target,
    "n_paths": len(paths),
    "skus": len(rows),
    "opening_stock": int(ev["opening_stock"].sum()),
    "margin": round(float(out_plan["margin"].sum()), 2),
    "fixed_30_margin": round(float(out_fix["margin"].sum()), 2),
    "sell_through": round(float(out_plan["units_sold"].sum() / out_plan["opening_stock"].sum()), 4),
    "skus_better_than_fixed": int((out_plan["margin"] > out_fix["margin"]).sum()),
    "rows": rows,
}
Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
print({k: v for k, v in out.items() if k != "rows"})
