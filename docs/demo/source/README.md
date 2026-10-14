# Video and audit report sources

Everything needed to rebuild the silent walkthrough (`docs/demo/demo.mp4`) and the audit report
(`docs/demo/AUDIT_REPORT.*`) from this repository alone. Paths below are relative to the repo root.

## What is here

| Path | What it is |
|---|---|
| `index.html` | Root of the video: theme (colours, type), and the timing of every slide |
| `compositions/bg.html`, `compositions/chrome.html` | Background grid, and the persistent project label, slide counter and progress bar |
| `compositions/s01-context.html` | Slide 01, the industry and four everyday problems |
| `compositions/s02-hook.html` | Slide 02, the project in one sentence |
| `compositions/explainer.html` | Slides 03-04, the white "how it works" chapter (edit its `CONFIG` block) |
| `compositions/s03-architecture.html` | Slide 05, the layered architecture diagram (node table `N`, wire table `W`) |
| `compositions/s04-running.html` | Slide 06, elasticity scatter and margin per event (data injected by `tools/inject_running.py`) |
| `compositions/value.html` | Slide 07, the markdown plan sheet and shelf scene (data injected by `tools/inject_sheet.py`) |
| `compositions/s05-results.html`, `s06-twist.html`, `s07-end.html` | Slides 08-10, results, what didn't win, end card |
| `assets/markdown_sheet.json` | Clearance event E1 markdown sheet, exported by `tools/export_markdown_sheet.py` |
| `assets/plan-heatmap.png` | End-card background: `outputs/markdown_plan.csv` drawn as a heatmap by `tools/plan_heatmap.py` |
| `audit/facts.yaml` | Every figure (F-xx), assumption (A-xx), slide text and check expression used by the report |
| `tools/build_audit_report.py` | Builds the slide stills, re-checks every figure against the repo outputs, writes MD, DOCX and PDF |
| `tools/export_markdown_sheet.py` | Re-runs the repo's own estimation, ladder search and scorer for event E1 and exports the sheet as JSON |
| `tools/inject_sheet.py` | Inlines that JSON into `compositions/value.html` (renders cannot fetch files) |
| `tools/inject_running.py` | Inlines `outputs/elasticity_by_sku.csv`, `elasticity_error.csv` and `markdown_by_event.csv` into slide 06 |
| `tools/plan_heatmap.py` | Draws the end-card heatmap from `outputs/markdown_plan.csv` |
| `package.json`, `hyperframes.json`, `meta.json` | HyperFrames project files (CLI pinned to 0.8.156) |

The repo writes no plots, so the slide 06 charts are drawn by the video from the output CSVs with
their values unchanged; the audit report checks the injected data against the CSVs.

Fonts (Inter, JetBrains Mono, Montserrat) are referenced by name and embedded by the HyperFrames
renderer; all three are SIL Open Font License.

## Requirements

- Node 22 and `npx` (HyperFrames 0.8.156 is fetched by `npx`), plus Chrome/Chromium for rendering.
- `ffmpeg` for compressing the video and extracting slide stills.
- LibreOffice (`soffice`) to convert the report to PDF.
- The repo's own environment (`uv sync`) for `make run` and `export_markdown_sheet.py`.
- For `build_audit_report.py`, `inject_sheet.py`, `inject_running.py` and `plan_heatmap.py` (any
  Python 3.11+, not added to the repo's `pyproject.toml`):
  `pip install pyyaml pandas python-docx pillow numpy matplotlib`.

## Rebuild the numbers, the video and the report

```bash
# 1. repo outputs (about 10 seconds; make sweep adds seeds 8-11)
make run
make sweep

# 2. inputs for the video
PYTHONPATH=src .venv/bin/python docs/demo/source/tools/export_markdown_sheet.py docs/demo/source/assets/markdown_sheet.json
python3 docs/demo/source/tools/inject_sheet.py docs/demo/source/assets/markdown_sheet.json \
  docs/demo/source/compositions/value.html \
  --rows SKU0222,SKU0315,SKU0195,SKU0271,SKU0199,SKU0169 --animate SKU0222,SKU0315,SKU0195,SKU0271
python3 docs/demo/source/tools/inject_running.py . docs/demo/source/compositions/s04-running.html
python3 docs/demo/source/tools/plan_heatmap.py outputs/markdown_plan.csv docs/demo/source/assets/plan-heatmap.png

# 3. render (88.8 s, 1920x1080, 30 fps, silent) and compress
cd docs/demo/source
npx --yes hyperframes@0.8.156 check
npx --yes hyperframes@0.8.156 render -f 30 -q looks -o renders/markdown-optimizer-master.mp4
cd -
ffmpeg -y -i docs/demo/source/renders/markdown-optimizer-master.mp4 -c:v libx264 -preset slow -crf 25 \
  -pix_fmt yuv420p -movflags +faststart -an docs/demo/demo.mp4

# 4. audit report: slide stills, automated checks, AUDIT_REPORT.md/.docx/.pdf
python3 docs/demo/source/tools/build_audit_report.py docs/demo/source/audit/facts.yaml
```

`build_audit_report.py` exits with code 1 if any figure on screen no longer matches the repo outputs.
The pipeline is seeded (data seed 7, scorer seed 11), so a fresh `make run` reproduces the outputs
byte for byte; the report lists which figures and slides each input affects (change-impact matrix).

GIFs for the README (same filter for both; 12 fps, 800 px wide):

```bash
F="fps=12,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
ffmpeg -y -ss 57.9 -t 12 -i docs/demo/source/renders/markdown-optimizer-master.mp4 -vf "$F" -loop 0 docs/demo/demo.gif
ffmpeg -y -ss 32.6 -t 8 -i docs/demo/source/renders/markdown-optimizer-master.mp4 -vf "$F" -loop 0 docs/demo/architecture.gif
```

The `renders/` folder (about 16 MB) is not committed; step 3 recreates it.
