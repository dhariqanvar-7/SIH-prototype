
#!/usr/bin/env python3
"""
generate_dataset.py
===================
Synthetic, reproducible multi-source dataset for **SIH 26013**
("AI-enabled geospatial integration platform for urban land administration").

Everything produced here is FICTIONAL. No real parcel, owner, address or
location is represented. Coordinates are anchored on a fictional site inside
UTM zone 43N (EPSG:32643) at a deliberately round false origin.

Quick start
-----------
    python generate_dataset.py --out dataset
    python generate_dataset.py --out dataset --verify

Requires: numpy, pandas, geopandas>=0.14, shapely>=2.0, pyproj>=3.5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.validation import explain_validity

try:
    from shapely.validation import make_valid  # noqa: F401  (shapely >= 2.0)
except ImportError:  # pragma: no cover
    sys.exit("shapely >= 2.0 is required (shapely.validation.make_valid missing).")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEED = 20260213
WARD_ID = "WARD-01"
CRS_PROJ = "EPSG:32643"          # UTM 43N, metres  (fictional site)
CRS_GEOG = "EPSG:4326"           # WGS84, for browser-facing GeoJSON

ORIGIN_X, ORIGIN_Y = 500_000.0, 3_000_000.0
SITE_W = SITE_H = 500.0
ROAD_W = 20.0
BLOCK_W = BLOCK_H = 140.0
N_BLOCKS_X = N_BLOCKS_Y = 3

N_PARCELS = 100
N_BUILDINGS_T1 = 120
N_REVENUE = 100
N_MUNICIPAL = 90
N_GT = 30
N_GNSS = 20
N_UTILITIES = 15

T1_DATE = "2024-11-15"
T2_DATE = "2025-11-20"

LAND_USE = ["residential", "commercial", "mixed", "industrial",
            "institutional", "open_space", "utility"]
LAND_USE_P = [0.46, 0.12, 0.14, 0.06, 0.08, 0.10, 0.04]
BUILT_USE = {"residential", "commercial", "mixed", "industrial", "institutional"}
MUNI_USE_MAP = {
    "residential": "Residential",
    "commercial": "Commercial",
    "mixed": "Mixed Use",
    "industrial": "Industrial",
    "institutional": "Institutional",
    "open_space": "Open Space",
    "utility": "Utility",
}

# error-injection volumes (see the SIH brief)
N_DISPLACED = 12
N_OVERLAP_PAIRS = 5
N_SELF_INTERSECT = 3
N_DUPLICATE_REVENUE = 4
N_ID_FORMAT_REVENUE = 8
N_ID_FORMAT_MUNICIPAL = 7
N_AREA_MISMATCH = 10
N_MISSING_MUNICIPAL = 10
N_MISSING_DETECTIONS = 8
N_FALSE_DETECTIONS = 5

N_ADDED_T2 = 6
N_REMOVED_T2 = 3
N_EXTENDED_T2 = 5

TOL_ROUNDTRIP_M = 1e-6


def log(msg: str) -> None:
    print(f"[generate] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Small geometry helpers
# ---------------------------------------------------------------------------
def largest_polygon(geom):
    """Return the largest Polygon inside any geometry, or None."""
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, Polygon):
        return geom
    polys = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon) and not g.is_empty]
    if not polys:
        return None
    return max(polys, key=lambda g: g.area)


def subdivide(b: Polygon, n: int, rng, acc: list) -> None:
    """Recursively cut a rectangle into `n` varied rectangles."""
    if n <= 1:
        acc.append(b)
        return
    minx, miny, maxx, maxy = b.bounds
    w, h = maxx - minx, maxy - miny
    if w > h * 1.15:
        axis = 0
    elif h > w * 1.15:
        axis = 1
    else:
        axis = int(rng.integers(0, 2))
    frac = float(rng.uniform(0.36, 0.64))
    n_left = n // 2
    if n > 3 and rng.random() < 0.6:
        n_left += int(rng.integers(-1, 2))
    n_left = int(np.clip(n_left, 1, n - 1))
    if axis == 0:
        xs = minx + w * frac
        subdivide(box(minx, miny, xs, maxy), n_left, rng, acc)
        subdivide(box(xs, miny, maxx, maxy), n - n_left, rng, acc)
    else:
        ys = miny + h * frac
        subdivide(box(minx, miny, maxx, ys), n_left, rng, acc)
        subdivide(box(minx, ys, maxx, maxy), n - n_left, rng, acc)


def irregularize(poly: Polygon, rng) -> Polygon:
    """Make a rectangle look like a real cadastral parcel (notch and/or jitter).

    Both operations only ever *shrink* the rectangle, so parcels can never
    overlap each other by accident.
    """
    # 1) corner notch -> L-shaped parcel
    if rng.random() < 0.45:
        minx, miny, maxx, maxy = poly.bounds
        w, h = maxx - minx, maxy - miny
        cw, ch = w * rng.uniform(0.22, 0.36), h * rng.uniform(0.22, 0.36)
        cx = minx if rng.random() < 0.5 else maxx - cw
        cy = miny if rng.random() < 0.5 else maxy - ch
        cand = poly.difference(box(cx, cy, cx + cw, cy + ch))
        if isinstance(cand, Polygon) and cand.is_valid and cand.area > 0.45 * poly.area:
            poly = cand

    # 2) pull one corner towards the centroid (irregular quadrilateral)
    if rng.random() < 0.6 and isinstance(poly, Polygon) and len(poly.exterior.coords) == 5:
        coords = list(poly.exterior.coords)[:-1]
        k = int(rng.integers(0, 4))
        c = np.array([poly.centroid.x, poly.centroid.y])
        v = np.array(coords[k], dtype=float)
        d = c - v
        nd = float(np.linalg.norm(d))
        if nd > 1e-6:
            t = np.array([-d[1], d[0]]) / nd
            nv = v + 0.13 * d + t * float(rng.uniform(-0.9, 0.9))
            new_coords = coords.copy()
            new_coords[k] = (float(nv[0]), float(nv[1]))
            cand = Polygon(new_coords)
            if cand.is_valid and cand.area > 0.55 * poly.area:
                poly = cand
    return poly


def block_footprints():
    step = BLOCK_W + ROAD_W
    out = []
    for j in range(N_BLOCKS_Y):
        for i in range(N_BLOCKS_X):
            x0 = ORIGIN_X + ROAD_W + i * step
            y0 = ORIGIN_Y + ROAD_W + j * step
            out.append((f"BLK-{j * N_BLOCKS_X + i + 1:02d}",
                        box(x0, y0, x0 + BLOCK_W, y0 + BLOCK_H)))
    return out


def road_centerlines():
    step = BLOCK_W + ROAD_W
    lines = []
    for i in range(N_BLOCKS_X + 1):
        c = ORIGIN_X + ROAD_W / 2 + i * step
        lines.append(LineString([(c, ORIGIN_Y), (c, ORIGIN_Y + SITE_H)]))
    for j in range(N_BLOCKS_Y + 1):
        c = ORIGIN_Y + ROAD_W / 2 + j * step
        lines.append(LineString([(ORIGIN_X, c), (ORIGIN_X + SITE_W, c)]))
    return lines


def place_buildings_in(parcel_geom, n: int, rng) -> list:
    """Place up to `n` rectangular footprints inside a parcel."""
    if n <= 0:
        return []
    inner = parcel_geom.buffer(-3.0)
    if inner.is_empty or inner.area < 80:
        inner = parcel_geom.buffer(-1.5)
    if inner.is_empty or inner.area < 40:
        return []
    minx, miny, maxx, maxy = inner.bounds
    placed, tries = [], 0
    while len(placed) < n and tries < 600:
        tries += 1
        p = Point(float(rng.uniform(minx, maxx)), float(rng.uniform(miny, maxy)))
        if not inner.contains(p):
            continue
        w = float(rng.uniform(7.0, 13.0))
        h = float(rng.uniform(7.0, 13.0))
        cand = largest_polygon(box(p.x - w / 2, p.y - h / 2,
                                   p.x + w / 2, p.y + h / 2).intersection(inner))
        if cand is None or cand.area < 30:
            continue
        if any(cand.intersects(g) for g in placed):
            continue
        placed.append(cand)
    return placed


# ---------------------------------------------------------------------------
# 1. Clean ground truth
# ---------------------------------------------------------------------------
def build_clean_parcels(rng) -> gpd.GeoDataFrame:
    blocks = block_footprints()
    per_block = [12] + [11] * 8            # 12 + 88 = 100
    rng.shuffle(per_block)

    rows, pid = [], 0
    for (bid, bgeom), n in zip(blocks, per_block):
        acc = []
        subdivide(bgeom, int(n), rng, acc)
        for g in acc:
            pid += 1
            g = irregularize(g, rng)
            rows.append({
                "parcel_id": f"P-{pid:03d}",
                "ward_id": WARD_ID,
                "block_id": bid,
                "land_use": str(rng.choice(LAND_USE, p=LAND_USE_P)),
                "geometry": g,
            })
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS_PROJ)
    gdf["area_m2"] = gdf.geometry.area.round(2)
    assert len(gdf) == N_PARCELS, len(gdf)
    assert gdf.geometry.is_valid.all(), "clean parcels must be valid"
    return gdf


def build_clean_buildings_t1(parcels: gpd.GeoDataFrame, rng) -> gpd.GeoDataFrame:
    """120 buildings; 8 of them live alone in their parcel (omission targets)."""
    pids = list(parcels["parcel_id"])
    geom_of = dict(zip(parcels["parcel_id"], parcels["geometry"]))
    land_of = dict(zip(parcels["parcel_id"], parcels["land_use"]))

    # seed a Poisson-ish allocation
    counts = {p: 0 for p in pids}
    remaining = N_BUILDINGS_T1
    while remaining > 0:
        p = pids[int(rng.integers(0, len(pids)))]
        if counts[p] < 3:
            counts[p] += 1
            remaining -= 1

    per_parcel = {p: place_buildings_in(geom_of[p], counts[p], rng) for p in pids}
    total = sum(len(v) for v in per_parcel.values())

    guard = 0
    while total < N_BUILDINGS_T1 and guard < 8000:
        guard += 1
        p = pids[int(rng.integers(0, len(pids)))]
        if len(per_parcel[p]) >= 3:
            continue
        got = place_buildings_in(geom_of[p], len(per_parcel[p]) + 1, rng)
        if len(got) > len(per_parcel[p]):
            total += len(got) - len(per_parcel[p])
            per_parcel[p] = got

    guard = 0
    while total > N_BUILDINGS_T1 and guard < 8000:
        guard += 1
        p = pids[int(rng.integers(0, len(pids)))]
        if per_parcel[p]:
            per_parcel[p].pop()
            total -= 1
    assert total == N_BUILDINGS_T1, total

    rows, bid = [], 0
    for p in pids:
        for g in per_parcel[p]:
            bid += 1
            rows.append({
                "building_id": f"B-{bid:03d}",
                "parcel_id": p,
                "floors": int(rng.integers(1, 9)),
                "survey_date": T1_DATE,
                "geometry": g,
            })
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS_PROJ)
    gdf["footprint_m2"] = gdf.geometry.area.round(2)
    return gdf, per_parcel, land_of


def build_clean_buildings_t2(clean_t1, parcels, land_of, rng):
    """t2 = t1 + 6 added − 3 removed + 5 extended (stable IDs kept)."""
    all_ids = list(clean_t1["building_id"])
    per_parcel_count = clean_t1.groupby("parcel_id").size().to_dict()

    # --- 8 omission candidates: parcels with exactly one building -------------
    singles = [r.building_id for r in clean_t1.itertuples()
               if per_parcel_count.get(r.parcel_id, 0) == 1
               and land_of.get(r.parcel_id) in BUILT_USE]
    if len(singles) < N_MISSING_DETECTIONS:
        singles = [r.building_id for r in clean_t1.itertuples()
                   if per_parcel_count.get(r.parcel_id, 0) == 1]
    rng.shuffle(singles)
    omission_ids = singles[:N_MISSING_DETECTIONS]

    pool = [b for b in all_ids if b not in omission_ids]
    rng.shuffle(pool)

    removed_ids = pool[:N_REMOVED_T2]
    pool = pool[N_REMOVED_T2:]

    # --- extensions ----------------------------------------------------------
    gdf_idx = clean_t1.set_index("building_id")
    other_geoms = {b: gdf_idx.loc[b].geometry for b in all_ids}
    extended_ids, extended_geoms = [], {}
    for cand in pool:
        if len(extended_ids) >= N_EXTENDED_T2:
            break
        g = gdf_idx.loc[cand].geometry
        my_parcel = gdf_idx.loc[cand].parcel_id
        forbidden = [v for k, v in other_geoms.items()
                     if k != cand and gdf_idx.loc[k].parcel_id == my_parcel]
        minx, miny, maxx, maxy = g.envelope.bounds
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        rng.shuffle(dirs)
        for dx, dy in dirs:
            d = float(rng.uniform(2.2, 3.6))
            if dx == 1:
                strip = box(maxx, miny, maxx + d, maxy)
            elif dx == -1:
                strip = box(minx - d, miny, minx, maxy)
            elif dy == 1:
                strip = box(minx, maxy, maxx, maxy + d)
            else:
                strip = box(minx, miny - d, maxx, miny)
            new = g.union(strip)
            if not new.is_valid or new.geom_type != "Polygon":
                continue
            ratio = new.area / g.area
            if not (1.15 <= ratio <= 1.95):
                continue
            if any(new.intersects(f) and not new.touches(f) for f in forbidden):
                continue
            extended_ids.append(cand)
            extended_geoms[cand] = new
            break

    pool = [b for b in pool if b not in set(extended_ids)]
    displaced_ids = pool[:N_DISPLACED]

    # --- assemble t2 ---------------------------------------------------------
    rows = []
    for r in clean_t1.itertuples():
        if r.building_id in removed_ids:
            continue
        g = extended_geoms.get(r.building_id, r.geometry)
        rows.append({"building_id": r.building_id, "parcel_id": r.parcel_id,
                     "floors": r.floors, "survey_date": T2_DATE, "geometry": g})

    # 6 new buildings placed on parcels that have room
    pid_counts = pd.Series([x["parcel_id"] for x in rows]).value_counts().to_dict()
    parcel_geom = dict(zip(parcels["parcel_id"], parcels["geometry"]))
    new_ids = []
    next_id = max(all_ids, key=lambda s: int(s.split("-")[1]))
    next_n = int(next_id.split("-")[1])
    added_geoms = {}
    tries = 0
    while len(new_ids) < N_ADDED_T2 and tries < 4000:
        tries += 1
        p = list(parcel_geom)[int(rng.integers(0, len(parcel_geom)))]
        if pid_counts.get(p, 0) >= 3:
            continue
        got = place_buildings_in(parcel_geom[p], pid_counts.get(p, 0) + 1, rng)
        if len(got) <= pid_counts.get(p, 0):
            continue
        next_n += 1
        bid = f"B-{next_n:03d}"
        new_ids.append(bid)
        added_geoms[bid] = got[-1]
        rows.append({"building_id": bid, "parcel_id": p,
                     "floors": int(rng.integers(1, 9)), "survey_date": T2_DATE,
                     "geometry": got[-1]})
        pid_counts[p] = pid_counts.get(p, 0) + 1

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS_PROJ)
    gdf["footprint_m2"] = gdf.geometry.area.round(2)

    plan = {
        "added": new_ids,
        "removed": removed_ids,
        "extended": extended_ids,
        "displaced": displaced_ids,
        "omission_ids": omission_ids,
    }
    return gdf, plan


# ---------------------------------------------------------------------------
# 2. Error injection
# ---------------------------------------------------------------------------
class ErrorLog:
    def __init__(self):
        self.rows = []

    def add(self, source_file, source_feature_id, error_type,
            original_value, modified_value, expected_action, parcel_id="", truth_group=""):
        self.rows.append({
            "error_id": f"ERR-{len(self.rows) + 1:04d}",
            "source_file": source_file,
            "source_feature_id": source_feature_id,
            "error_type": error_type,
            "original_value": original_value,
            "modified_value": modified_value,
            "expected_action": expected_action,
            "parcel_id": parcel_id,
            "truth_group": truth_group,
        })

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=[
            "error_id", "source_file", "source_feature_id", "error_type",
            "original_value", "modified_value", "expected_action",
            "parcel_id", "truth_group"])


def make_bowtie(poly: Polygon) -> Polygon:
    """Turn the envelope of a polygon into a self-intersecting bow-tie."""
    minx, miny, maxx, maxy = poly.envelope.bounds
    return Polygon([(minx, miny), (maxx, maxy), (maxx, miny), (minx, maxy)])


def inject_parcel_errors(clean_parcels, rng, err: ErrorLog):
    """Overlaps + self-intersections on the shipped cadastral layer."""
    gdf = clean_parcels.copy()
    geoms = list(gdf.geometry)

    # --- 3 self-intersecting parcels ----------------------------------------
    order = rng.permutation(len(gdf))
    self_int_idx = list(order[:N_SELF_INTERSECT])
    for i in self_int_idx:
        before = geoms[i]
        geoms[i] = make_bowtie(before)
        err.add("inputs/cadastral.gpkg", gdf.parcel_id.iloc[i], "self_intersection",
                "valid polygon", f"self-intersecting ({explain_validity(geoms[i])})",
                "repair_geometry_and_flag_for_survey_review",
                parcel_id=gdf.parcel_id.iloc[i], truth_group="invalid_geometry")

    # --- 5 overlapping parcel pairs -----------------------------------------
    cand_pairs = []
    for i in range(len(gdf)):
        if i in self_int_idx:
            continue
        for j in range(i + 1, len(gdf)):
            if j in self_int_idx:
                continue
            if geoms[i].distance(geoms[j]) < 0.02:
                cand_pairs.append((i, j))
    rng.shuffle(cand_pairs)

    used, overlap_pairs = set(), []
    for i, j in cand_pairs:
        if len(overlap_pairs) >= N_OVERLAP_PAIRS:
            break
        if i in used or j in used:
            continue
        sliver = geoms[i].buffer(1.6).intersection(geoms[j])
        if sliver.is_empty or sliver.area < 2.0:
            continue
        new_i = geoms[i].union(sliver)
        if not new_i.is_valid:
            continue
        geoms[i] = new_i
        used.update({i, j})
        overlap_pairs.append((gdf.parcel_id.iloc[i], gdf.parcel_id.iloc[j]))
        err.add("inputs/cadastral.gpkg", f"{gdf.parcel_id.iloc[i]}|{gdf.parcel_id.iloc[j]}",
                "parcel_overlap",
                "touching boundary", f"overlap area {sliver.area:.2f} m2",
                "resolve_topology_conflict",
                parcel_id=gdf.parcel_id.iloc[i], truth_group="overlap")

    gdf = gpd.GeoDataFrame(
        gdf.drop(columns="geometry").assign(geometry=geoms),
        geometry="geometry", crs=CRS_PROJ)
    return gdf, [p[0] for p in overlap_pairs]


def inject_revenue_errors(clean_parcels, rng, err: ErrorLog):
    """Revenue CSV: duplicates, id-format drift, area conflicts."""
    base = clean_parcels[["parcel_id", "area_m2"]].copy()
    n = len(base)

    rows, next_rec = [], 1
    for i, r in enumerate(base.itertuples(), start=1):
        rows.append({
            "record_id": f"REV-{next_rec:04d}",
            "survey_no": f"{i:03d}",
            "owner_ref": f"OWNER-{i:03d}",
            "recorded_area_m2": round(r.area_m2 * (1 + float(rng.normal(0, 0.008))), 2),
            "parcel_id": r.parcel_id,
            "canonical_survey_no": f"{i:03d}",
        })
        next_rec += 1

    df = pd.DataFrame(rows)

    # 10 area conflicts (+10 % .. +25 %)
    area_idx = rng.choice(len(df), size=N_AREA_MISMATCH, replace=False)
    for k in area_idx:
        old = float(df.at[k, "recorded_area_m2"])
        factor = 1.0 + float(rng.choice([-1, 1]) * rng.uniform(0.10, 0.25))
        new = round(old * factor, 2)
        df.at[k, "recorded_area_m2"] = new
        err.add("inputs/revenue.csv", df.at[k, "record_id"], "area_mismatch",
                f"{old:.2f}", f"{new:.2f}",
                "flag_attribute_conflict_and_recompute_from_geometry",
                parcel_id=df.at[k, "parcel_id"], truth_group="area_conflict")

    # 8 identifier-format variants
    fmt_idx = rng.choice([i for i in range(len(df)) if i not in set(area_idx)],
                         size=N_ID_FORMAT_REVENUE, replace=False)
    variant_fns = [
        lambda s: str(int(s)),
        lambda s: f" {s}",
        lambda s: f"{s} ",
        lambda s: f"P-{s}",
        lambda s: f"p-{s}",
        lambda s: f"{s}\t",
    ]
    for k in fmt_idx:
        old = df.at[k, "survey_no"]
        new = str(rng.choice(variant_fns)(old))
        df.at[k, "survey_no"] = new
        err.add("inputs/revenue.csv", df.at[k, "record_id"], "identifier_format",
                old, new, "normalise_identifier_and_link_to_parcel",
                parcel_id=df.at[k, "parcel_id"], truth_group="id_format")

    # 4 duplicates (new record_id, same business key)
    dup_sources = [i for i in range(len(df))
                   if i not in set(area_idx) and i not in set(fmt_idx)]
    rng.shuffle(dup_sources)
    dup_rows = []
    for k in dup_sources[:N_DUPLICATE_REVENUE]:
        extra = df.iloc[k].to_dict()
        extra["record_id"] = f"REV-{next_rec:04d}"
        next_rec += 1
        dup_rows.append(extra)
        err.add("inputs/revenue.csv", extra["record_id"], "duplicate_record",
                "", f"duplicate of {df.at[k, 'record_id']} "
                    f"(survey_no={df.at[k, 'survey_no']})",
                "deduplicate_on_business_key",
                parcel_id=df.at[k, "parcel_id"], truth_group="duplicate")

    out = pd.concat([df, pd.DataFrame(dup_rows)], ignore_index=True)
    out = out.drop(columns=["parcel_id", "canonical_survey_no"])
    return out


def inject_municipal_errors(clean_parcels, rng, err: ErrorLog):
    """Municipal CSV: 10 records missing, 7 id-format variants."""
    n = len(clean_parcels)
    missing_idx = set(rng.choice(n, size=N_MISSING_MUNICIPAL, replace=False).tolist())

    kept, next_id = [], 1
    for i, r in enumerate(clean_parcels.itertuples(), start=1):
        if (i - 1) in missing_idx:
            err.add("inputs/municipal.csv", f"MUN-{i:04d}", "missing_record",
                    f"plot_ref=P / {i:03d} (parcel {r.parcel_id})", "",
                    "flag_incomplete_source_coverage",
                    parcel_id=r.parcel_id, truth_group="missing_municipal")
            continue
        kept.append({
            "property_id": f"MUN-{next_id:04d}",
            "plot_ref": f"P / {i:03d}",
            "address": f"{int(rng.integers(1, 199))} Synthetic Lane {int(rng.integers(1, 9))}",
            "use_type": MUNI_USE_MAP[r.land_use],
            "parcel_id": r.parcel_id,
            "canonical_plot_ref": f"P / {i:03d}",
        })
        next_id += 1

    df = pd.DataFrame(kept)
    fmt_idx = rng.choice(len(df), size=N_ID_FORMAT_MUNICIPAL, replace=False)
    variant_fns = [
        lambda s: s.replace(" ", ""),
        lambda s: s.replace(" / ", "/"),
        lambda s: s.lower(),
        lambda s: s.replace(" / ", " - "),
        lambda s: f" {s}",
    ]
    for k in fmt_idx:
        old = df.at[k, "plot_ref"]
        new = str(rng.choice(variant_fns)(old))
        df.at[k, "plot_ref"] = new
        err.add("inputs/municipal.csv", df.at[k, "property_id"], "identifier_format",
                old, new, "normalise_identifier_and_link_to_parcel",
                parcel_id=df.at[k, "parcel_id"], truth_group="id_format")

    return df.drop(columns=["parcel_id", "canonical_plot_ref"])


def derive_extracted_buildings(clean_gdf, plan, tag, rng, err: ErrorLog,
                               fp_geoms, id_prefix, start_n, displaced_ids,
                               missing_ids):
    """Extractor output: dropped detections, false positives, displacement."""
    missing = set(missing_ids)
    disp = set(displaced_ids)
    base_offsets = {b: (float(rng.uniform(1.2, 3.0)), float(rng.uniform(0, 2 * np.pi)))
                    for b in disp}

    rows, n = [], start_n
    for r in clean_gdf.itertuples():
        if r.building_id in missing:
            err.add(f"inputs/extracted_buildings_{tag}.geojson", r.building_id,
                    "missing_detection", f"clean footprint {r.building_id} present", "",
                    "flag_extraction_omission_via_ground_truth",
                    parcel_id=r.parcel_id, truth_group="missing_detection")
            continue
        g = r.geometry
        if r.building_id in disp:
            mag, ang = base_offsets[r.building_id]
            jx, jy = float(rng.normal(0, 0.6)), float(rng.normal(0, 0.6))
            dx = mag * np.cos(ang) + jx
            dy = mag * np.sin(ang) + jy
            g = affinity.translate(g, xoff=float(dx), yoff=float(dy))
            err.add(f"inputs/extracted_buildings_{tag}.geojson",
                    f"{id_prefix}-{n + 1:04d}", "geometry_displacement",
                    "0.00 m", f"{float(np.hypot(dx, dy)):.2f} m",
                    "match_spatially_despite_positional_offset",
                    parcel_id=r.parcel_id, truth_group="displacement")
        n += 1
        rows.append({"extracted_id": f"{id_prefix}-{n:04d}", "geometry": g})

    for g in fp_geoms:
        n += 1
        fid = f"{id_prefix}-{n:04d}"
        rows.append({"extracted_id": fid, "geometry": g})
        err.add(f"inputs/extracted_buildings_{tag}.geojson", fid,
                "false_detection", "", f"spurious footprint {g.area:.1f} m2",
                "flag_unsupported_detection",
                truth_group="false_detection")

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS_PROJ)
    return gdf, n


def make_false_positives(parcels, rng):
    """2 footprints in road corridors + 3 in open-space / utility parcels."""
    fps = []
    # 2 in road corridors -> completely outside any cadastral parcel
    for line in rng.choice(road_centerlines(), size=2, replace=False):
        x, y = line.interpolate(float(rng.uniform(0.15, 0.85)), normalized=True).coords[0]
        s = float(rng.uniform(7.0, 10.0))
        fps.append(box(x - s / 2, y - s / 2, x + s / 2, y + s / 2))

    # 3 in parcels whose land use is open_space / utility
    candidates = parcels[parcels.land_use.isin(["open_space", "utility"])]
    if len(candidates) < 3:
        candidates = parcels.sample(n=3, random_state=int(rng.integers(0, 1 << 30)))
    chosen = candidates.sample(n=min(3, len(candidates)),
                               random_state=int(rng.integers(0, 1 << 30)))
    for geom in chosen.geometry:
        p = geom.representative_point()
        s = float(rng.uniform(7.0, 10.0))
        fps.append(box(p.x - s / 2, p.y - s / 2, p.x + s / 2, p.y + s / 2))
    return fps


# ---------------------------------------------------------------------------
# 3. Writing
# ---------------------------------------------------------------------------
def write_geojson(gdf, path: Path, crs_out=CRS_GEOG):
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_crs(crs_out).to_file(path, driver="GeoJSON")


def write_gpkg(gdf, path: Path, layer: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    gdf.to_file(path, layer=layer, driver="GPKG")


def write_nocrs_geojson(gdf, path: Path):
    """Deliberately strip CRS metadata -> consumer must ask, not guess."""
    path.parent.mkdir(parents=True, exist_ok=True)
    gj = json.loads(gdf.to_json())
    gj.pop("crs", None)
    gj["name"] = "legacy_parcels_no_crs"
    gj["synthetic"] = True
    gj["_warning"] = ("CRS metadata intentionally absent. Do NOT guess; the "
                      "integration engine must flag this source for clarification.")
    path.write_text(json.dumps(gj, indent=1), encoding="utf-8")


def content_hash(path: Path) -> str:
    """Deterministic content hash (GPKG embeds timestamps -> canonicalise)."""
    if path.suffix.lower() == ".gpkg":
        gdf = gpd.read_file(path)
        gdf = gdf.sort_values(by=[c for c in gdf.columns if c != "geometry"]).reset_index(drop=True)
        h = hashlib.sha256()
        for _, row in gdf.iterrows():
            for c in gdf.columns:
                if c == "geometry":
                    h.update(shapely.to_wkb(row.geometry))
                else:
                    h.update(str(row[c]).encode())
        return h.hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dataset_signature(root: Path) -> dict:
    sig = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name not in {"manifest.json"}:
            sig[str(p.relative_to(root))] = content_hash(p)
    return sig


# ---------------------------------------------------------------------------
# 4. Writers (README, manifest, data dictionary, evaluation files)
# ---------------------------------------------------------------------------
def write_readme(root: Path) -> None:
    (root / "README.md").write_text(
        "# Synthetic SIH 26013 Dataset\n\n"
        "**All content is FICTIONAL. No real parcel, owner, address or place\n"
        "is represented anywhere in this dataset.**\n\n"
        "Generated by `generate_dataset.py` for demonstrating multi-source\n"
        "geospatial integration (SIH problem 26013).\n\n"
        "## Layout\n\n"
        "```\n"
        "inputs/           # department copies with injected errors -> feed to matcher\n"
        "evaluation_only/  # answer key -> NEVER feed to matcher\n"
        "```\n\n"
        "## CRS\n\n"
        f"- Projected: `{CRS_PROJ}` (metres)\n"
        f"- Browser export: `{CRS_GEOG}` (degrees)\n\n"
        "## Reproducibility\n\n"
        f"- Seed: `{SEED}` — re-running yields identical data.\n"
        "- Every file carries `synthetic: true` in the manifest.\n",
        encoding="utf-8")


def write_data_dictionary(root: Path) -> None:
    rows = [
        # file, field, type, description
        ("cadastral.gpkg", "parcel_id", "string", "Canonical parcel identifier (P-###)"),
        ("cadastral.gpkg", "ward_id", "string", "Administrative ward label"),
        ("cadastral.gpkg", "block_id", "string", "Block identifier (BLK-##)"),
        ("cadastral.gpkg", "land_use", "string", "Land-use class"),
        ("cadastral.gpkg", "area_m2", "float", "Geometric area in m^2"),
        ("extracted_buildings_t1.geojson", "extracted_id", "string", "Extractor-side id"),
        ("extracted_buildings_t2.geojson", "extracted_id", "string", "Extractor-side id"),
        ("revenue.csv", "record_id", "string", "Revenue record id"),
        ("revenue.csv", "survey_no", "string", "Revenue survey number (may be formatted)"),
        ("revenue.csv", "owner_ref", "string", "Fictional owner reference"),
        ("revenue.csv", "recorded_area_m2", "float", "Area as recorded by revenue dept"),
        ("municipal.csv", "property_id", "string", "Municipal property id"),
        ("municipal.csv", "plot_ref", "string", "Municipal plot reference"),
        ("municipal.csv", "address", "string", "Fictional postal address"),
        ("municipal.csv", "use_type", "string", "Municipal use classification"),
        ("ground_truth_observations.geojson", "observation_id", "string", "GT point id"),
        ("ground_truth_observations.geojson", "observed_use", "string", "Field-observed use"),
        ("ground_truth_observations.geojson", "verification_status", "string", "verification state"),
        ("gnss_observations.csv", "point_id", "string", "GNSS point id"),
        ("gnss_observations.csv", "easting", "float", "Projected easting (m)"),
        ("gnss_observations.csv", "northing", "float", "Projected northing (m)"),
        ("gnss_observations.csv", "accuracy_m", "float", "Reported accuracy (m)"),
        ("utilities.geojson", "utility_id", "string", "Utility feature id"),
        ("utilities.geojson", "utility_type", "string", "water | sewer | power | telecom"),
        ("utilities.geojson", "status", "string", "active | proposed | abandoned"),
        ("evaluation_only/clean_parcels.gpkg", "parcel_id", "string", "Answer key — canonical parcel"),
        ("evaluation_only/clean_buildings_t1.gpkg", "building_id", "string", "Answer key — t1 footprint"),
        ("evaluation_only/clean_buildings_t2.gpkg", "building_id", "string", "Answer key — t2 footprint"),
        ("evaluation_only/injected_errors.csv", "error_id", "string", "Error row id"),
        ("evaluation_only/injected_errors.csv", "error_type", "string", "Class of injected error"),
        ("evaluation_only/injected_errors.csv", "expected_action", "string", "Correct system behaviour"),
        ("evaluation_only/expected_changes.csv", "change_type", "string", "added | removed | extended"),
        ("evaluation_only/record_links.csv", "source_file", "string", "Input file the row belongs to"),
        ("evaluation_only/record_links.csv", "source_feature_id", "string", "Row id inside that file"),
        ("evaluation_only/record_links.csv", "parcel_id", "string", "Canonical parcel it maps to"),
    ]
    df = pd.DataFrame(rows, columns=["file", "field", "type", "description"])
    df.to_csv(root / "data_dictionary.csv", index=False)


def write_record_links(root: Path, cad_clean, rev_raw, muni_raw) -> None:
    """Cross-file link table so evaluation can score joins."""
    rows = []

    # revenue <-> parcel
    canon = {f"{i:03d}": p for i, p in enumerate(cad_clean["parcel_id"], start=1)}
    for r in rev_raw.itertuples():
        key = str(r.survey_no).strip().lstrip("pP-").strip()
        try:
            key = f"{int(key):03d}"
        except ValueError:
            key = None
        pid = canon.get(key, "")
        rows.append({"source_file": "inputs/revenue.csv",
                     "source_feature_id": r.record_id,
                     "parcel_id": pid, "link_type": "revenue_to_parcel"})

    # municipal <-> parcel
    for r in muni_raw.itertuples():
        raw = str(r.plot_ref).strip().lower()
        digits = "".join(ch for ch in raw if ch.isdigit())
        pid = canon.get(f"{int(digits):03d}", "") if digits else ""
        rows.append({"source_file": "inputs/municipal.csv",
                     "source_feature_id": r.property_id,
                     "parcel_id": pid, "link_type": "municipal_to_parcel"})

    pd.DataFrame(rows, columns=["source_file", "source_feature_id",
                                "parcel_id", "link_type"]
                 ).to_csv(root / "evaluation_only" / "record_links.csv", index=False)


def write_expected_changes(root: Path, plan, clean_t1, clean_t2) -> None:
    rows = []
    for bid in plan["added"]:
        r = clean_t2[clean_t2.building_id == bid].iloc[0]
        rows.append({"building_id": bid, "change_type": "added",
                     "parcel_id": r.parcel_id,
                     "notes": f"new footprint {r.footprint_m2:.1f} m2"})
    for bid in plan["removed"]:
        r = clean_t1[clean_t1.building_id == bid].iloc[0]
        rows.append({"building_id": bid, "change_type": "removed",
                     "parcel_id": r.parcel_id, "notes": "present at t1, absent at t2"})
    for bid in plan["extended"]:
        a = clean_t1[clean_t1.building_id == bid].iloc[0].footprint_m2
        b = clean_t2[clean_t2.building_id == bid].iloc[0].footprint_m2
        rows.append({"building_id": bid, "change_type": "extended",
                     "parcel_id": clean_t1[clean_t1.building_id == bid].iloc[0].parcel_id,
                     "notes": f"{a:.1f} -> {b:.1f} m2 (+{100*(b/a-1):.1f}%)"})
    pd.DataFrame(rows, columns=["building_id", "change_type",
                                "parcel_id", "notes"]
                 ).to_csv(root / "evaluation_only" / "expected_changes.csv", index=False)


def write_manifest(root: Path, sig: dict, counts: dict) -> None:
    man = {
        "synthetic": True,
        "seed": SEED,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ward_id": WARD_ID,
        "crs_projected": CRS_PROJ,
        "crs_geographic": CRS_GEOG,
        "units": "metres (projected), degrees (geographic)",
        "warning": "All content is fictional. No real parcel/owner/place represented.",
        "expected_counts": counts,
        "feature_counts": counts,
        "files": [],
    }
    for rel, h in sorted(sig.items()):
        p = root / rel
        ext = p.suffix.lower()
        entry = {
            "path": rel,
            "bytes": p.stat().st_size,
            "sha256_canonical": h,
            "synthetic": True,
        }
        if ext in {".gpkg", ".geojson"}:
            try:
                g = gpd.read_file(p)
                entry["crs"] = str(g.crs)
                entry["geometry_type"] = g.geom_type.dropna().unique().tolist()
                entry["record_count"] = int(len(g))
            except Exception:
                pass
        elif ext == ".csv":
            try:
                df = pd.read_csv(p)
                entry["record_count"] = int(len(df))
            except Exception:
                pass
        man["files"].append(entry)
    (root / "manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# 5. Validation
# ---------------------------------------------------------------------------
def validate(root: Path, cad_input, plan, counts, clean_p, clean_b1, clean_b2,
             err_log, rng2) -> None:
    log("running validation ...")

    # clean geometries valid
    assert clean_p.geometry.is_valid.all(), "clean parcels invalid"
    assert clean_b1.geometry.is_valid.all(), "clean buildings t1 invalid"
    assert clean_b2.geometry.is_valid.all(), "clean buildings t2 invalid"

    # source identifiers unique
    assert clean_p.parcel_id.is_unique
    assert clean_b1.building_id.is_unique
    assert clean_b2.building_id.is_unique

    # every clean building sits in its declared parcel
    pgeom = dict(zip(clean_p.parcel_id, clean_p.geometry))
    for r in clean_b1.itertuples():
        assert pgeom[r.parcel_id].buffer(0.01).contains(r.geometry.centroid), \
            f"{r.building_id} centroid outside {r.parcel_id}"
    for r in clean_b2.itertuples():
        assert pgeom[r.parcel_id].buffer(0.01).contains(r.geometry.centroid), \
            f"{r.building_id} centroid outside {r.parcel_id}"

    # every injected error recorded
    expected = (N_SELF_INTERSECT + N_OVERLAP_PAIRS + N_DUPLICATE_REVENUE
                + N_ID_FORMAT_REVENUE + N_ID_FORMAT_MUNICIPAL + N_AREA_MISMATCH
                + N_MISSING_MUNICIPAL + N_MISSING_DETECTIONS + N_FALSE_DETECTIONS
                + N_DISPLACED)
    actual = len(err_log.rows)
    assert actual >= expected, f"error log {actual} < expected {expected}"

    # coordinate round-trip
    from pyproj import Transformer
    fwd = Transformer.from_crs(CRS_PROJ, CRS_GEOG, always_xy=True)
    inv = Transformer.from_crs(CRS_GEOG, CRS_PROJ, always_xy=True)
    sample = clean_p.geometry.iloc[:5]
    for g in sample:
        x, y = g.representative_point().x, g.representative_point().y
        lon, lat = fwd.transform(x, y)
        x2, y2 = inv.transform(lon, lat)
        assert abs(x - x2) < TOL_ROUNDTRIP_M and abs(y - y2) < TOL_ROUNDTRIP_M

    # determinism: two runs of the RNG produce identical geometry counts
    r_a = np.random.default_rng(SEED)
    r_b = np.random.default_rng(SEED)
    assert np.array_equal(r_a.random(1000), r_b.random(1000))

    # evaluation files not among inputs
    input_files = {p.name for p in (root / "inputs").iterdir()}
    eval_files = {p.name for p in (root / "evaluation_only").iterdir()}
    assert not (input_files & eval_files), "input/eval files collide"

    log(f"  valid geometry ........... OK")
    log(f"  unique identifiers ....... OK")
    log(f"  building->parcel ......... OK")
    log(f"  injected errors recorded . OK ({actual} >= {expected})")
    log(f"  CRS round-trip ........... OK (< {TOL_ROUNDTRIP_M} m)")
    log(f"  determinism (seeded RNG) . OK")
    log(f"  inputs/eval separation ... OK")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(out_dir: Path, verify: bool) -> None:
    root = out_dir.resolve()
    if root.exists():
        shutil.rmtree(root)
    (root / "inputs").mkdir(parents=True)
    (root / "evaluation_only").mkdir(parents=True)

    rng = np.random.default_rng(SEED)
    err = ErrorLog()

    # ---- clean truth ------------------------------------------------------
    log("building clean parcels ...")
    clean_p = build_clean_parcels(rng)

    log("building clean buildings t1 ...")
    clean_b1, per_parcel, land_of = build_clean_buildings_t1(clean_p, rng)

    log("building clean buildings t2 (change plan) ...")
    clean_b2, plan = build_clean_buildings_t2(clean_b1, clean_p, land_of, rng)
    log(f"  t2 added={len(plan['added'])} removed={len(plan['removed'])} "
        f"extended={len(plan['extended'])}")

    # ---- derive inputs with injected errors -------------------------------
    log("injecting cadastral errors ...")
    cad_input, overlap_parcels = inject_parcel_errors(clean_p, rng, err)

    log("building revenue.csv (duplicates, id-format, area conflicts) ...")
    rev_raw = inject_revenue_errors(clean_p, rng, err)

    log("building municipal.csv (missing + id-format) ...")
    muni_raw = inject_municipal_errors(clean_p, rng, err)

    log("deriving extracted buildings t1 / t2 ...")
    fp_geoms = make_false_positives(clean_p, rng)
    ext_t1, next_n = derive_extracted_buildings(
        clean_b1, plan, "t1", rng, err, fp_geoms,
        id_prefix="EXT-T1", start_n=0,
        displaced_ids=plan["displaced"],
        missing_ids=plan["omission_ids"])
    ext_t2, _ = derive_extracted_buildings(
        clean_b2, plan, "t2", rng, err, fp_geoms,
        id_prefix="EXT-T2", start_n=next_n + 100,
        displaced_ids=plan["displaced"],
        missing_ids=plan["omission_ids"])

    # ---- observations, GNSS, utilities ------------------------------------
    log("building ground-truth observations, GNSS, utilities ...")
    gt_rows, gnss_rows, util_rows = [], [], []
    for i, r in enumerate(clean_p.sample(n=N_GT, random_state=SEED).itertuples(), start=1):
        gt_rows.append({
            "observation_id": f"OBS-{i:03d}",
            "observed_use": r.land_use if rng.random() > 0.15
                            else str(rng.choice(LAND_USE)),
            "verification_status": str(rng.choice(["verified", "verified", "pending"])),
            "geometry": r.geometry.representative_point().buffer(0.5, quad_segs=6),
        })
    gt_gdf = gpd.GeoDataFrame(gt_rows, geometry="geometry", crs=CRS_PROJ)

    for i in range(1, N_GNSS + 1):
        p = clean_p.sample(n=1, random_state=SEED + i).geometry.iloc[0]
        c = p.representative_point()
        gnss_rows.append({
            "point_id": f"GNSS-{i:03d}",
            "easting":  round(c.x + float(rng.normal(0, 0.4)), 3),
            "northing": round(c.y + float(rng.normal(0, 0.4)), 3),
            "accuracy_m": round(float(rng.uniform(0.02, 0.15)), 3),
        })
    gnss_df = pd.DataFrame(gnss_rows)

    lines = road_centerlines()
    for i in range(1, N_UTILITIES + 1):
        line = lines[int(rng.integers(0, len(lines)))]
        a = float(rng.uniform(0.05, 0.45))
        b = min(1.0, a + float(rng.uniform(0.25, 0.5)))
        seg = LineString([line.interpolate(a, normalized=True).coords[0],
                          line.interpolate(b, normalized=True).coords[0]])
        util_rows.append({
            "utility_id": f"UTIL-{i:03d}",
            "utility_type": str(rng.choice(["water", "sewer", "power", "telecom"])),
            "status": str(rng.choice(["active", "active", "proposed", "abandoned"])),
            "geometry": seg,
        })
    util_gdf = gpd.GeoDataFrame(util_rows, geometry="geometry", crs=CRS_PROJ)

    # ---- write inputs -----------------------------------------------------
    log("writing inputs/ ...")
    write_gpkg(cad_input, root / "inputs" / "cadastral.gpkg", "cadastral")
    write_geojson(ext_t1, root / "inputs" / "extracted_buildings_t1.geojson")
    write_geojson(ext_t2, root / "inputs" / "extracted_buildings_t2.geojson")
    rev_raw.to_csv(root / "inputs" / "revenue.csv", index=False)
    muni_raw.to_csv(root / "inputs" / "municipal.csv", index=False)
    write_geojson(gt_gdf, root / "inputs" / "ground_truth_observations.geojson")
    gnss_df.to_csv(root / "inputs" / "gnss_observations.csv", index=False)
    write_geojson(util_gdf, root / "inputs" / "utilities.geojson")

    # Optional: one file with deliberately missing CRS metadata
    no_crs = cad_input.copy()
    no_crs.crs = None
    write_nocrs_geojson(no_crs, root / "inputs" / "legacy_parcels_no_crs.geojson")

    # ---- write evaluation_only -------------------------------------------
    log("writing evaluation_only/ (answer key) ...")
    write_gpkg(clean_p,  root / "evaluation_only" / "clean_parcels.gpkg", "clean_parcels")
    write_gpkg(clean_b1, root / "evaluation_only" / "clean_buildings_t1.gpkg", "clean_buildings_t1")
    write_gpkg(clean_b2, root / "evaluation_only" / "clean_buildings_t2.gpkg", "clean_buildings_t2")
    err.to_frame().to_csv(root / "evaluation_only" / "injected_errors.csv", index=False)
    write_expected_changes(root, plan, clean_b1, clean_b2)
    write_record_links(root, clean_p, rev_raw, muni_raw)

    # ---- README / data dictionary / manifest -----------------------------
    log("writing README / data_dictionary / manifest ...")
    write_readme(root)
    write_data_dictionary(root)

    counts = {
        "cadastral_features":        int(len(cad_input)),
        "extracted_buildings_t1":    int(len(ext_t1)),
        "extracted_buildings_t2":    int(len(ext_t2)),
        "revenue_records":           int(len(rev_raw)),
        "municipal_records":         int(len(muni_raw)),
        "ground_truth_observations": int(len(gt_gdf)),
        "gnss_observations":         int(len(gnss_df)),
        "utility_features":          int(len(util_gdf)),
        "clean_parcels":             int(len(clean_p)),
        "clean_buildings_t1":        int(len(clean_b1)),
        "clean_buildings_t2":        int(len(clean_b2)),
        "injected_errors":           int(len(err.rows)),
        "expected_changes":          int(len(plan["added"]) + len(plan["removed"]) + len(plan["extended"])),
    }

    # manifest needs the generator file itself next to the outputs
    gen_src = Path(__file__).resolve()
    if gen_src.parent != root and gen_src.name != "generate_dataset.py":
        shutil.copy2(gen_src, root / "generate_dataset.py")
    elif gen_src.parent != root:
        shutil.copy2(gen_src, root / "generate_dataset.py")

    sig = dataset_signature(root)
    write_manifest(root, sig, counts)

    # ---- validation -------------------------------------------------------
    if verify:
        validate(root, cad_input, plan, counts, clean_p, clean_b1, clean_b2,
                 err, np.random.default_rng(SEED))

    # ---- summary ----------------------------------------------------------
    log("")
    log("=" * 62)
    log(f"dataset written to: {root}")
    log("=" * 62)
    for k, v in counts.items():
        log(f"  {k:<28} {v}")
    log("")
    log("Next steps:")
    log(f"  1. Inspect:  Get-ChildItem -Recurse {root}")
    log(f"  2. Verify :  python generate_dataset.py --out {out_dir} --verify")
    log(f"  3. IMPORTANT: never feed {root/'evaluation_only'} into the matcher.")
    log("=" * 62)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("dataset"),
                    help="output directory (default: ./dataset)")
    ap.add_argument("--verify", action="store_true",
                    help="run built-in validation after generation")
    args = ap.parse_args()
    main(args.out, args.verify)