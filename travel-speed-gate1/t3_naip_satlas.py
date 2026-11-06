#!/usr/bin/env python3
"""
Track B of the imagery arm, step 2 (decision #126; docs/T3_naip_imagery_design.md):
a 96 m NAIP chip centred on each trail spot, embedded with the frozen Satlas
aerial Swin-B.

For one region (one Slurm array task per region): read each spot's chip from
its NAIP photo on Microsoft Planetary Computer (RGB, in the photo's UTM grid,
160 x 160 pixels = 0.6 m; 0.3 m photos are read at 0.6 m), scale to 0-1, run
Satlas Aerial_SwinB_SI (backbone only; weights ODC-BY), average its last
feature map (1,024 channels) and keep those numbers. Chips are not saved.

Input:  data/t3/naip_spots.parquet (t3_naip_spots.py)
        /engrfs/project/jacobsn/zhou.n/models/satlas/aerial_swinb_si.pth
Output: data/t3/naip_satlas/<region>.npz: spot (int), emb (float16, n x 1,024)
Run:    python t3_naip_satlas.py <region>     (cluster/t3_naip_satlas_job.sh)
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.update({          # COG reads over HTTP: only the blocks needed, cached
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MULTIRANGE": "YES", "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_CACHEMAX": "1024", "VSI_CACHE": "TRUE", "VSI_CACHE_SIZE": "268435456",
    "GDAL_HTTP_MAX_RETRY": "8", "GDAL_HTTP_RETRY_DELAY": "3"})
import rasterio                                    # noqa: E402
from rasterio.enums import Resampling              # noqa: E402
from rasterio.warp import transform as warp        # noqa: E402
from rasterio.windows import from_bounds           # noqa: E402

SPOTS = Path("data/t3/naip_spots.parquet")
WEIGHTS = Path("/engrfs/project/jacobsn/zhou.n/models/satlas/aerial_swinb_si.pth")
OUT = Path("data/t3/naip_satlas")
HALF_M, PX, BATCH = 48.0, 160, 32
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token/naip"
UA = {"User-Agent": "travel-speed-research-script"}


class Token:
    """A Planetary Computer read token for NAIP, renewed every 30 minutes."""
    def __init__(self):
        self.value, self.until = None, 0.0

    def __call__(self):
        if time.time() > self.until:
            for k in range(8):
                try:
                    req = urllib.request.Request(SAS, headers=UA)
                    self.value = json.load(urllib.request.urlopen(req, timeout=60))["token"]
                    break
                except Exception as e:             # the token service hiccuped
                    print(f"  token retry {k + 1}: {e}", flush=True)
                    time.sleep(10 * (k + 1))
            self.until = time.time() + 30 * 60
        return self.value


def open_photo(href, token):
    return rasterio.open(f"/vsicurl/{href}?{token()}")


def centre_xy(src, lat, lon):
    """Points in the photo's own (UTM) coordinates."""
    return warp("EPSG:4326", src.crs, list(lon), list(lat))


def chips(src, lat, lon):
    """RGB chips (n, 3, PX, PX), uint8, 96 m on a side, centred on each point."""
    xs, ys = centre_xy(src, lat, lon)
    out = np.zeros((len(xs), 3, PX, PX), np.uint8)
    for k, (x, y) in enumerate(zip(xs, ys)):
        win = from_bounds(x - HALF_M, y - HALF_M, x + HALF_M, y + HALF_M, src.transform)
        inside = (win.col_off >= 0 and win.row_off >= 0
                  and win.col_off + win.width <= src.width
                  and win.row_off + win.height <= src.height)
        out[k] = src.read([1, 2, 3], window=win, out_shape=(3, PX, PX),
                          resampling=Resampling.bilinear, boundless=not inside, fill_value=0)
    return out


def load_model():
    import torch
    import satlaspretrain_models as sp
    from satlaspretrain_models.utils import SatlasPretrain_weights
    info = SatlasPretrain_weights["Aerial_SwinB_SI"]
    w = torch.load(WEIGHTS, map_location="cpu")
    return sp.Model(info["num_channels"], info["multi_image"], info["backbone"],
                    fpn=False, head=None, weights=w).eval()


def embed(model, x):
    """1,024 numbers per chip: the mean of the backbone's last feature map,
    BATCH chips at a time."""
    import torch
    out = []
    with torch.inference_mode():
        for i in range(0, len(x), BATCH):
            f = model(torch.from_numpy(x[i:i + BATCH]).float() / 255)[-1]   # n x 1024 x 5 x 5
            out.append(f.mean((2, 3)).numpy().astype(np.float16))
    return np.concatenate(out)


def main():
    import torch
    region = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None        # a timing test
    dest = OUT / f"{region}.npz"
    if dest.exists() and limit is None:
        print(f"{dest} exists; nothing to do")
        return
    torch.set_num_threads(int(os.environ.get("SLURM_CPUS_PER_TASK", "8")))
    s = pd.read_parquet(SPOTS)
    s = s[(s.region == region) & s.href.notna()].sort_values(["href", "lat", "lon"])
    if limit:
        s = s.head(limit)
    model, token = load_model(), Token()
    spots, embs, buf, bufid = [], [], [], []
    t0, n_done = time.time(), 0
    for href, g in s.groupby("href", sort=False):
        with open_photo(href, token) as src:
            buf.append(chips(src, g.lat.to_numpy(), g.lon.to_numpy()))
            bufid.append(g.spot.to_numpy())
        if sum(len(b) for b in buf) >= BATCH:
            x = np.concatenate(buf)
            embs.append(embed(model, x))
            spots.append(np.concatenate(bufid))
            n_done += len(x)
            buf, bufid = [], []
            if len(embs) % 20 == 0:
                rate = n_done / (time.time() - t0)
                print(f"  {n_done:,}/{len(s):,} chips, {rate:.1f}/s", flush=True)
    if buf:
        embs.append(embed(model, np.concatenate(buf)))
        spots.append(np.concatenate(bufid))
    spot, emb = np.concatenate(spots), np.concatenate(embs)
    print(f"{region}: {len(spot):,} chips in {time.time() - t0:.0f} s", flush=True)
    if limit is None:
        OUT.mkdir(parents=True, exist_ok=True)
        np.savez(dest, spot=spot, emb=emb)


if __name__ == "__main__":
    main()
