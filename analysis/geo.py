"""Geography helpers (Stream B3): bubble maps of IT growth by metro and a QCEW metro-code stability check.

Maps
  * position   = CBSA internal point from the Census Gazetteer (data/raw/census_gazetteer_cbsa.csv)
  * size       = IT jobs 2019 (NAICS 5415); area proportional to jobs. Where 2019 jobs are known but growth is not
                 (employment withheld in 2024, e.g. Chicago) the 2019 level still sizes the bubble on the establishment map
  * colour     = growth 2019 to 2024 (diverging, centred on 0, clipped at the 5th and 95th percentile)
  * grey cross = metro with no usable value for that outcome
Only the lower 48 states are drawn (Alaska, Hawaii and Puerto Rico metros are counted in the footnote).
The outline is a hand-simplified polygon of about 100 points (Great Lakes filled in), a drawing aid and NOT an
official boundary; it is good enough to orient a national bubble map and nothing more.

Code stability
  QCEW metro areas are coded 'C####' (C + first four digits of the CBSA code). `code_stability` lists, for every
  year, which codes appear in the area file and flags those that are not present in both 2019 and 2024.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from collectors.common import PROCESSED, RAW

# (lon, lat), clockwise from Cape Flattery
US48_OUTLINE = [
    (-124.7, 48.4), (-123.1, 48.15), (-122.75, 49.0), (-95.15, 49.0), (-95.15, 49.4), (-94.6, 48.7), (-93.0, 48.6),
    (-91.4, 48.1), (-89.6, 48.0), (-90.8, 47.2), (-92.1, 46.8), (-90.4, 46.6), (-88.0, 47.4), (-87.4, 46.5),
    (-84.9, 46.8), (-84.5, 46.5), (-84.1, 46.2), (-84.7, 45.8), (-83.4, 45.1), (-83.0, 44.0), (-82.5, 43.0),
    (-82.9, 42.35), (-83.4, 41.7), (-82.7, 41.5), (-81.7, 41.5), (-80.5, 42.0), (-79.0, 42.8), (-79.0, 43.3),
    (-76.5, 43.5), (-76.2, 44.1), (-74.7, 45.0), (-71.5, 45.0), (-70.8, 45.4), (-70.0, 46.7), (-69.2, 47.45),
    (-68.3, 47.35), (-67.8, 47.07), (-67.8, 45.7), (-67.4, 45.2), (-67.0, 44.8), (-68.8, 44.3), (-70.2, 43.6),
    (-70.7, 43.0), (-70.8, 42.6), (-70.9, 42.3), (-70.0, 42.0), (-69.95, 41.7), (-70.6, 41.55), (-71.4, 41.45),
    (-72.0, 41.3), (-73.6, 41.0), (-74.0, 40.6), (-74.0, 40.0), (-74.9, 38.95), (-75.1, 38.4), (-75.9, 37.1),
    (-76.0, 36.9), (-75.5, 35.3), (-76.5, 34.7), (-77.9, 33.9), (-79.0, 33.3), (-79.9, 32.7), (-80.9, 32.0),
    (-81.4, 30.7), (-81.3, 29.9), (-80.6, 28.5), (-80.0, 26.8), (-80.15, 25.7), (-80.4, 25.2), (-81.1, 25.15),
    (-81.8, 26.1), (-82.7, 27.7), (-82.8, 29.0), (-83.7, 29.9), (-84.3, 30.0), (-85.3, 29.7), (-86.5, 30.4),
    (-87.5, 30.3), (-88.4, 30.35), (-89.4, 30.2), (-89.2, 29.0), (-90.5, 29.1), (-92.0, 29.55), (-93.8, 29.7),
    (-94.7, 29.35), (-95.9, 28.6), (-97.2, 27.7), (-97.4, 26.0), (-99.1, 26.4), (-99.5, 27.5), (-100.7, 29.1),
    (-101.4, 29.8), (-102.4, 29.8), (-103.2, 29.0), (-104.5, 29.65), (-106.5, 31.75), (-108.2, 31.78),
    (-108.2, 31.33), (-111.07, 31.33), (-114.8, 32.5), (-117.1, 32.53), (-117.3, 33.0), (-118.5, 34.0),
    (-119.5, 34.4), (-120.6, 34.55), (-121.9, 36.6), (-122.5, 37.8), (-123.8, 39.4), (-124.4, 40.4),
    (-124.1, 41.8), (-124.5, 42.8), (-124.1, 44.0), (-123.95, 46.2), (-124.1, 47.0), (-124.7, 48.4),
]
LOWER48 = dict(lon=(-125.5, -66.0), lat=(24.0, 49.8))


def in_lower48(lon, lat) -> np.ndarray:
    """Bounding-box test that separates the lower 48 from Alaska, Hawaii and Puerto Rico (all far outside the box)."""
    lon, lat = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
    return (lon >= LOWER48["lon"][0]) & (lon <= LOWER48["lon"][1]) & (lat >= LOWER48["lat"][0]) & (lat <= LOWER48["lat"][1])


def point_in_outline(lon, lat) -> np.ndarray:
    """Is each (lon, lat) inside the simplified outline? Used to sanity-check the outline itself."""
    from matplotlib.path import Path as MplPath
    pts = np.column_stack([np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)])
    return MplPath(US48_OUTLINE).contains_points(pts)


# ------------------------------------------------------------------ data
def load_geo_panel(panel_path: Path | None = None, gaz_path: Path | None = None) -> pd.DataFrame:
    """Metro panel joined to Gazetteer centroids on the 5-character CBSA code."""
    p = pd.read_csv(panel_path or PROCESSED / "metro_panel.csv", dtype={"cbsa_code": str})
    g = pd.read_csv(gaz_path or RAW / "census_gazetteer_cbsa.csv", dtype={"cbsa_code": str})
    p["cbsa_code"] = p["cbsa_code"].str.zfill(5)
    g = g.drop_duplicates("cbsa_code")[["cbsa_code", "lat", "lon", "name", "lsad"]].rename(columns={"name": "gaz_name"})
    out = p.merge(g, on="cbsa_code", how="left")
    if "emp_it_2019_reported" not in out:                      # older panel files: fall back to the usable level only
        out["emp_it_2019_reported"] = out["emp_it_2019"]
    out["size_jobs"] = out["emp_it_2019"].fillna(out["emp_it_2019_reported"])
    return out


def coverage_report(geo: pd.DataFrame) -> dict:
    """Which panel metros could not be placed on the map, and why."""
    no_xy = geo[geo["lat"].isna()]
    placed = geo.dropna(subset=["lat"])
    in48 = in_lower48(placed["lon"], placed["lat"])
    return {"metros": len(geo), "without_centroid": len(no_xy),
            "without_centroid_names": no_xy["metro_name"].fillna(no_xy["cbsa_code"]).tolist(),
            "outside_lower48": int((~in48).sum()), "drawn": int(in48.sum())}


# ------------------------------------------------------------------ maps
def short_name(name: str) -> str:
    return str(name).split(",")[0].split("-")[0].strip()


def bubble_map(geo: pd.DataFrame, growth_col: str, title: str, *, ax=None, label_top: int = 10,
               max_area: float = 1400.0, pct_clip: tuple[float, float] = (5, 95)):
    """Bubble map. Returns the matplotlib Axes."""
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm
    from matplotlib.lines import Line2D

    if ax is None:
        _, ax = plt.subplots(figsize=(12, 7))
    g = geo.dropna(subset=["lat", "lon"]).copy()
    g = g[in_lower48(g["lon"], g["lat"])]
    ax.fill(*zip(*US48_OUTLINE), facecolor="#f2f2f2", edgecolor="#9a9a9a", lw=0.8, zorder=0)

    has = g[growth_col].notna()
    none = g[~has]
    ax.scatter(none["lon"], none["lat"], marker="x", s=22, color="#8c8c8c", lw=1, zorder=2)

    d = g[has].copy()
    lo, hi = np.nanpercentile(d[growth_col], pct_clip)
    lim = max(abs(lo), abs(hi), 1e-9)
    norm = TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim)
    jobs_known = d["size_jobs"].notna()
    ref = float(d["size_jobs"].max()) if jobs_known.any() else 1.0
    d["area"] = np.where(jobs_known, d["size_jobs"].fillna(0) / ref * max_area, 18.0)
    d = d.sort_values("area", ascending=False)                                 # small bubbles on top
    sc = ax.scatter(d["lon"], d["lat"], s=d["area"].clip(lower=14), c=d[growth_col].clip(-lim, lim), cmap="RdBu",
                    norm=norm, edgecolor=np.where(d["size_jobs"].notna(), "#444444", "#000000"),
                    linewidths=np.where(d["size_jobs"].notna(), 0.4, 1.0), alpha=0.85, zorder=3)
    cb = plt.colorbar(sc, ax=ax, shrink=0.7, pad=0.01)
    cb.set_label(f"growth 2019 to 2024, % (clipped at {pct_clip[0]}th/{pct_clip[1]}th percentile)")

    big = pd.concat([g.nlargest(label_top, "emp_total_2019")] if "emp_total_2019" in g else [])
    for r in big.itertuples():
        ax.annotate(short_name(r.metro_name), (r.lon, r.lat), xytext=(5, 4), textcoords="offset points", fontsize=7.5, zorder=5)

    sizes = [s for s in (10_000, 50_000, 200_000) if s <= ref] or [ref]
    handles = [Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor="#444444",
                      markersize=float(np.sqrt(s / ref * max_area)), label=f"{s:,.0f} IT jobs (2019)") for s in sizes]
    handles.append(Line2D([], [], marker="x", ls="", color="#8c8c8c", label=f"no usable value ({len(none)})"))
    if (~jobs_known).any():
        handles.append(Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor="black", markeredgewidth=1,
                              markersize=4, label="size unknown (2019 jobs not reported)"))
    ax.legend(handles=handles, loc="lower left", fontsize=8, frameon=True, title="bubble area = IT jobs 2019", title_fontsize=8)
    ax.set_xlim(*LOWER48["lon"]); ax.set_ylim(*LOWER48["lat"])
    ax.set_aspect(1 / np.cos(np.radians(38)))
    ax.set_title(title, fontsize=12)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    return ax


def make_maps(geo: pd.DataFrame, outdir: Path | None = None) -> list[Path]:
    """Two maps: IT employment growth and IT establishment growth. Returns the saved paths."""
    import matplotlib.pyplot as plt
    outdir = Path(outdir or "reports/figures")
    outdir.mkdir(parents=True, exist_ok=True)
    cov = coverage_report(geo)
    foot = (f"Lower 48 only: {cov['drawn']} of {cov['metros']} metros drawn, {cov['outside_lower48']} outside, "
            f"{cov['without_centroid']} without a centroid. NAICS 5415 (IT consulting and computer systems design), QCEW.")
    paths = []
    for col, name, title in (("it_growth_pct", "06_map_it_employment_growth.png", "IT employment growth by metro, 2019 to 2024"),
                             ("estab_growth_pct", "06_map_it_establishment_growth.png", "IT establishment growth by metro, 2019 to 2024")):
        fig, ax = plt.subplots(figsize=(12, 7.2))
        bubble_map(geo, col, title, ax=ax)
        fig.text(0.01, 0.01, foot, fontsize=7.5, color="0.35")
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        path = outdir / name
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths


# ------------------------------------------------------------------ code stability
def code_stability(areas: pd.DataFrame, y0: int = 2019, y1: int = 2024, industry: str | None = None) -> pd.DataFrame:
    """Which QCEW metro codes (C####) appear in which years? `areas` = bls_qcew_areas_it_industries.csv.
    industry=None uses every industry in the file (a code is 'present' if it has any row that year); pass '10'
    (all industries) to test the delineation itself, since total employment is reported for every real area."""
    a = areas[areas["area_fips"].str.fullmatch(r"C\d{4}")]
    if industry is not None:
        a = a[a["industry_code"].astype(str) == industry]
    pres = a.groupby(["area_fips", "year"]).size().unstack("year").notna()
    pres = pres.reindex(sorted(pres.columns), axis=1)
    out = pres.copy()
    out.columns = [f"y{c}" for c in out.columns]
    out["in_y0"], out["in_y1"] = pres.get(y0, False), pres.get(y1, False)
    out["only_in"] = np.select([out["in_y0"] & ~out["in_y1"], ~out["in_y0"] & out["in_y1"]], [str(y0), str(y1)], "")
    out["cbsa_code"] = out.index.str[1:] + "0"
    return out.reset_index().drop(columns=["in_y0", "in_y1"])


def only_one_year(stab: pd.DataFrame, names: dict[str, str] | None = None) -> pd.DataFrame:
    """The metros present in only one of the two years, with a name where one is known."""
    x = stab[stab["only_in"] != ""].copy()
    if names is not None:
        x["name"] = x["cbsa_code"].map(names)
    return x.sort_values(["only_in", "area_fips"]).reset_index(drop=True)
