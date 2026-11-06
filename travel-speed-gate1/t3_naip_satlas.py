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
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.update({          # COG reads over HTTP: only the blocks needed, cached
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MULTIRANGE": "YES", "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_CACHEMAX": "1024", "VSI_CACHE": "TRUE", "VSI_CACHE_SIZE": "268435456",
    "GDAL_HTTP_MAX_RETRY": "8", "GDAL_HTTP_RETRY_DELAY": "3"})
import rasterio                                    # noqa: E402
import rasterio.errors                             # noqa: E402
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
    """A Planetary Computer read token for NAIP. A token lasts only about 15
    minutes (its msft:expiry), so it is renewed 2 minutes before it expires;
    a token that cannot be renewed stops the run (6 Nov: a 30-minute renewal
    let tokens expire and every region longer than ~14 minutes failed, 403)."""
    def __init__(self):
        self.value, self.until = None, 0.0

    def refresh(self):
        for k in range(10):
            try:
                req = urllib.request.Request(SAS, headers=UA)
                d = json.load(urllib.request.urlopen(req, timeout=60))
                expiry = datetime.fromisoformat(d["msft:expiry"].replace("Z", "+00:00")).timestamp()
                if expiry - time.time() > 180:          # at least 3 minutes left
                    self.value, self.until = d["token"], expiry - 120
                    return
                print(f"  token expires in {expiry - time.time():.0f} s; waiting for a new one", flush=True)
            except Exception as e:                       # the token service hiccuped
                print(f"  token retry {k + 1}: {e}", flush=True)
            time.sleep(15 * (k + 1))
        raise RuntimeError("no usable Planetary Computer token after 10 tries")

    def __call__(self):
        if time.time() > self.until:
            self.refresh()
        return self.value


def open_photo(href, token):
    return rasterio.open(f"/vsicurl/{href}?{token()}")


def photo_chips(href, lat, lon, token, tries=4):
    """All chips from one photo; on a failed read, a fresh token and a retry."""
    for k in range(tries):
        try:
            with open_photo(href, token) as src:
                return chips(src, lat, lon)
        except rasterio.errors.RasterioIOError as e:
            print(f"  retry {k + 1} {href.rsplit('/', 1)[-1]}: {e}", flush=True)
            token.refresh()
            time.sleep(5 * (k + 1))
    raise RuntimeError(f"cannot read {href} after {tries} tries")


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
    # progress is saved in parts of ~2,000 chips, so a failed task resumes
    parts = OUT / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    old = sorted(parts.glob(f"{region}_*.npz"))
    done = set(np.concatenate([np.load(p)["spot"] for p in old]).tolist()) if old else set()
    todo = s[~s.spot.isin(done)]
    print(f"{region}: {len(s):,} spots, {len(done):,} already done", flush=True)
    model, token = load_model(), Token()
    spots, embs, n_part = [], [], len(old)
    t0, n_done = time.time(), 0

    def save_part():
        nonlocal spots, embs, n_part
        if spots and limit is None:
            n_part += 1
            np.savez(parts / f"{region}_{n_part:04d}.npz",
                     spot=np.concatenate(spots), emb=np.concatenate(embs))
        spots, embs = [], []

    for href, g in todo.groupby("href", sort=False):
        x = photo_chips(href, g.lat.to_numpy(), g.lon.to_numpy(), token)
        embs.append(embed(model, x))
        spots.append(g.spot.to_numpy())
        n_done += len(x)
        if sum(len(v) for v in spots) >= 2000:
            save_part()
            print(f"  {n_done:,}/{len(todo):,} chips, {n_done / (time.time() - t0):.1f}/s", flush=True)
    save_part()
    print(f"{region}: {n_done:,} chips in {time.time() - t0:.0f} s", flush=True)
    if limit is None:
        allp = sorted(parts.glob(f"{region}_*.npz"))
        spot = np.concatenate([np.load(p)["spot"] for p in allp])
        emb = np.concatenate([np.load(p)["emb"] for p in allp])
        assert len(spot) == len(s) and len(set(spot.tolist())) == len(s)
        np.savez(dest, spot=spot, emb=emb)
        for p in allp:
            p.unlink()


if __name__ == "__main__":
    main()
