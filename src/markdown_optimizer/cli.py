"""Run the full study and write every number the README quotes to ``outputs/``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from markdown_optimizer.data import generate, load, write
from markdown_optimizer.pipeline import Results, headline, run


def _table(df: pd.DataFrame, digits: int = 3) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        cells = [f"{v:,.{digits}f}" if isinstance(v, float) else str(v) for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_outputs(res: Results, out: Path, seed: int) -> dict[str, float]:
    out.mkdir(parents=True, exist_ok=True)
    res.elasticity_error.to_csv(out / "elasticity_error.csv", index=False)
    res.elasticity_by_sku.to_csv(out / "elasticity_by_sku.csv", index=False)
    res.lift_summary.to_csv(out / "lift_summary.csv", index=False)
    res.markdown_summary.to_csv(out / "markdown_summary.csv", index=False)
    res.markdown_by_event.to_csv(out / "markdown_by_event.csv", index=False)
    res.pooling_comparison.to_csv(out / "pooling_comparison.csv", index=False)
    res.plan.to_csv(out / "markdown_plan.csv", index=False)
    head = headline(res)
    (out / "results.json").write_text(json.dumps({"seed": seed, **head}, indent=2) + "\n")
    report = [
        f"# Run report (seed {seed})",
        "",
        "## Elasticity error against the true value",
        _table(res.elasticity_error),
        "",
        "## Promotion baseline against the true counterfactual",
        _table(res.lift_summary),
        "",
        "## Clearance events scored on the true demand curve",
        _table(res.markdown_summary, 2),
        "",
        "## Partial pooling against the other estimators (paired over SKU-events)",
        _table(res.pooling_comparison, 0),
        "",
        "## By event",
        _table(res.markdown_by_event, 2),
        "",
    ]
    (out / "report.md").write_text("\n".join(report))
    return head


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=Path("outputs"))
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--draws", type=int, default=400, help="demand draws per SKU-event when scoring plans")
    ap.add_argument("--refresh", action="store_true", help="regenerate the dataset first")
    ap.add_argument("--sweep", type=int, default=0, help="also rerun on this many further seeds")
    args = ap.parse_args()

    if args.refresh or not (args.data / "sales.csv").exists():
        write(generate(seed=args.seed), args.data)
    res = run(load(args.data), draws=args.draws)
    head = write_outputs(res, args.out, args.seed)
    print((args.out / "report.md").read_text())
    print(json.dumps(head, indent=2))

    if args.sweep:
        rows = [{"seed": args.seed, **head}]
        for seed in range(args.seed + 1, args.seed + 1 + args.sweep):
            print(f"seed {seed} ...", flush=True)
            rows.append({"seed": seed, **headline(run(generate(seed=seed), draws=args.draws))})
        sweep = pd.DataFrame(rows)
        sweep.to_csv(args.out / "seed_sweep.csv", index=False)
        print(sweep.describe().T[["mean", "std", "min", "max"]].to_string())


if __name__ == "__main__":
    main()
