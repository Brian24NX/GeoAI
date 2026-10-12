#!/usr/bin/env python3
"""
Build Project_Explainer.html (the visual guide to the whole project) from
docs/explainer_template.html plus the latest numbers.

  1. on the cluster: python make_explainer_data.py   (-> results/explainer_data.json)
  2. copy results/explainer_data.json to this folder's results/
  3. python make_explainer.py                         (-> ../Project_Explainer.html)
"""

import base64
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEMPLATE = ROOT / "docs" / "explainer_template.html"
DATA = HERE / "results" / "explainer_data.json"
MAP_PNG = ROOT / "meeting_plots" / "oct9" / "fig_t1_dataset.png"
TRAIL_PNG = HERE / "results" / "t4_trail_map" / "fig_wm_pace.png"
OUT = ROOT / "Project_Explainer.html"


def main():
    html = TEMPLATE.read_text(encoding="utf-8")
    data = json.dumps(json.loads(DATA.read_text()), separators=(",", ":"))
    data = data.replace("</", "<\\/")          # never close the script tag
    img = base64.b64encode(MAP_PNG.read_bytes()).decode("ascii")
    assert "/*__DATA__*/" in html and "__IMG_WM_MAP__" in html
    html = html.replace("/*__DATA__*/", data).replace("__IMG_WM_MAP__", img)
    if "__IMG_TRAIL_MAP__" in html:          # the pace map, as a small JPEG
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            jpg = Path(tmp) / "trail.jpg"
            subprocess.run(["sips", "-s", "format", "jpeg", "-s",
                            "formatOptions", "70", "--resampleWidth", "1600",
                            str(TRAIL_PNG), "--out", str(jpg)],
                           check=True, capture_output=True)
            html = html.replace("__IMG_TRAIL_MAP__", base64.b64encode(
                jpg.read_bytes()).decode("ascii"))
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
