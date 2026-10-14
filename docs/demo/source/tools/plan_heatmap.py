"""Draw the end-card background: the chosen markdown depth of every SKU-event (rows) in every week
(columns), straight from outputs/markdown_plan.csv. Darker mint = deeper markdown.

Usage: python3 tools/plan_heatmap.py <repo>/outputs/markdown_plan.csv assets/plan-heatmap.png
Needs: pandas, Pillow.
"""

import sys

import pandas as pd
from PIL import Image, ImageDraw

plan = pd.read_csv(sys.argv[1])
cols = ["depth_w1", "depth_w2", "depth_w3", "depth_w4"]
cw, rh, gap = 34, 4, 2  # 300 rows x 4 weeks, laid out as three event blocks side by side
blocks = [plan[plan["event_id"] == e][cols].to_numpy() for e in ("E1", "E2", "E3")]
W = len(blocks) * (4 * (cw + gap) + 24)
H = max(len(b) for b in blocks) * (rh + gap)
img = Image.new("RGB", (W, H), (0x0A, 0x11, 0x19))
d = ImageDraw.Draw(img)
bg = (0x0A, 0x11, 0x19)
mint = (0x3F, 0xD8, 0xA8)
for bi, b in enumerate(blocks):
    x0 = bi * (4 * (cw + gap) + 24)
    for r, row in enumerate(b):
        for w, v in enumerate(row):
            a = 0.12 + min(v, 0.6) / 0.6 * 0.88
            c = tuple(int(bg[k] + (mint[k] - bg[k]) * a) for k in range(3))
            x, y = x0 + w * (cw + gap), r * (rh + gap)
            d.rectangle([x, y, x + cw - 1, y + rh - 1], fill=c)
img.save(sys.argv[2])
print(sys.argv[2], img.size)
