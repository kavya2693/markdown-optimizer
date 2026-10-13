"""Write the seeded dataset to data/ (or --out). Same seed, same bytes."""

from __future__ import annotations

import argparse
from pathlib import Path

from markdown_optimizer.data import generate, write


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=Path("data"))
    args = ap.parse_args()
    ds = generate(seed=args.seed)
    write(ds, args.out)
    print(
        f"wrote {len(ds.skus)} SKUs, {len(ds.sales):,} SKU-weeks, "
        f"{ds.events['event_id'].nunique()} clearance events ({len(ds.events)} SKU-events) to {args.out}/"
    )


if __name__ == "__main__":
    main()
