"""Generate the BhuSetu integrated synthetic departmental benchmark (v1).

Synthetic demonstration data for TRL 3 evaluation; not official cadastral or
ownership data.

Design rules
------------
* Fixed seed (see SEED). Re-running is byte-reproducible given identical sources.
* Refuses to overwrite an existing generated package.
* Reuses existing valid files wherever possible instead of duplicating data:
    - parcel geometry   : synthetic_benchmark/inputs/parcels.geojson
    - parcel registry   : departmental/inputs/parcel_directory.json
    - department records: departmental/inputs/records.json (+ answers.json truth)
    - building fixtures : synthetic_benchmark/evaluation_only/expected_building_intersections.csv
    - utility fixtures  : synthetic_benchmark/inputs/utility_network_synthetic.geojson
    - context layers    : buildings/roads/landuse/amenities/utilities/aoi.geojson
  Reused departmental record IDs and parcel associations are preserved so this
  package does not create a competing benchmark.
* Operational data lives in inputs/. True parcel associations, utility service
  parcels and per-parcel answers live only in evaluation_only/.
* No personal names, Aadhaar numbers, phone numbers or other sensitive PII.

Run:
    python dataset/hyderabad_kondapur/synthetic_integrated_v1/scripts/generate_integrated_dataset.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

SEED = 20260925
CRS_METRIC = "EPSG:32644"
CRS_GEOG = "EPSG:4326"
AOI = {"west": 78.350, "south": 17.450, "east": 78.364, "north": 17.462}
LABEL = "Synthetic demonstration data for TRL 3 evaluation; not official cadastral or ownership data."

PACKAGE = Path(__file__).resolve().parents[1]
KONDAPUR = PACKAGE.parent

# Controlled scenario sizes -------------------------------------------------
RECORDLESS_PARCELS = 12      # parcels deliberately given no departmental record
COMPETING_RECORDS = 12       # one record competing between two nearby parcels
UTILITY_POINT_SHIFT_FRACTION = 0.30
MAX_BUILDING_DISTANCE_M = 10.0

DEPARTMENTS = ["revenue", "municipal", "electricity", "water", "sewer"]

SOURCES = {
    "parcel_geometry": KONDAPUR / "synthetic_benchmark/inputs/parcels.geojson",
    "parcel_reference": KONDAPUR / "synthetic_benchmark/evaluation_only/parcels_reference.geojson",
    "parcel_directory": KONDAPUR / "departmental/inputs/parcel_directory.json",
    "department_records": KONDAPUR / "departmental/inputs/records.json",
    "department_answers": KONDAPUR / "departmental/evaluation_only/answers.json",
    "building_intersections": KONDAPUR / "synthetic_benchmark/evaluation_only/expected_building_intersections.csv",
    "utility_network": KONDAPUR / "synthetic_benchmark/inputs/utility_network_synthetic.geojson",
    "context": [
        KONDAPUR / "buildings.geojson",
        KONDAPUR / "roads.geojson",
        KONDAPUR / "landuse.geojson",
        KONDAPUR / "amenities.geojson",
        KONDAPUR / "utilities.geojson",
        KONDAPUR / "aoi.geojson",
    ],
}

# Reused departmental scenario label -> documented spec scenario name.
SCENARIO_MAP = {
    "clean": "clean_exact_match",
    "format_variation": "format_variation",
    "missing_identifier": "missing_survey_identifier",
    "missing_geometry": "missing_geometry",
    "address_typo": "address_typo",
    "wrong_identifier": "wrong_identifier",
    "area_error": "area_error",
    "identifier_only": "identifier_only",
    "old_record": "old_record",
    "location_shift": "shifted_location",
    "missing_scope": "missing_district_or_village",
    "no_parcel_in_study_area": "record_without_matching_parcel",
    "additional_account": "multiple_accounts_one_parcel",
    "duplicate_account": "duplicate_account",
    "competing_record": "record_competing_between_parcels",
    "parcel_without_record": "parcel_without_departmental_record",
}

SCENARIO_NOTES = {
    "clean_exact_match": "Identifiers, address, area and location agree with the parcel.",
    "format_variation": "Survey and address formatting differ from the parcel registry.",
    "missing_survey_identifier": "Survey number is blank; address, area and location remain.",
    "missing_geometry": "No easting/northing; identifiers and address remain.",
    "address_typo": "Address contains a spelling error; other fields agree.",
    "wrong_identifier": "Survey number belongs to a different parcel; address/location agree.",
    "area_error": "Recorded area is inflated relative to the parcel geometry.",
    "identifier_only": "Only the survey identifier is present; no address, area or location.",
    "old_record": "Record date precedes 2020; no historical parcel geometry available.",
    "shifted_location": "Coordinates displaced outside the parcel, near a neighbour.",
    "missing_district_or_village": "Village scope missing, so the record is intentionally unmatchable.",
    "record_without_matching_parcel": "Identifiers and location fall outside the study parcels.",
    "multiple_accounts_one_parcel": "A second legitimate service account on the same parcel.",
    "duplicate_account": "The same department/account key appears twice.",
    "record_competing_between_parcels": "Identification evidence splits between two adjacent parcels.",
    "parcel_without_departmental_record": "The parcel has no departmental record in this package.",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")


def guard() -> None:
    for sub in ("inputs", "evaluation_only", "metadata"):
        target = PACKAGE / sub
        if target.exists() and any(target.iterdir()):
            raise FileExistsError(
                f"{target} already contains generated files; refusing to overwrite. "
                "Choose a new versioned directory."
            )


def load_sources():
    data = {}
    data["parcels"] = gpd.read_file(SOURCES["parcel_geometry"])
    data["reference"] = gpd.read_file(SOURCES["parcel_reference"])
    data["directory"] = json.loads(SOURCES["parcel_directory"].read_text(encoding="utf-8"))
    data["records"] = json.loads(SOURCES["department_records"].read_text(encoding="utf-8"))
    data["answers"] = json.loads(SOURCES["department_answers"].read_text(encoding="utf-8"))
    data["buildings"] = gpd.read_file(KONDAPUR / "buildings.geojson")
    data["utility_network"] = gpd.read_file(SOURCES["utility_network"])
    data["aoi"] = gpd.read_file(KONDAPUR / "aoi.geojson")
    return data


def build_parcels(data, rng):
    """Enrich the reused synthetic parcels with registry and administrative fields."""
    directory = {row["parcel_id"]: row for row in data["directory"]}
    parcels = data["parcels"].to_crs(CRS_METRIC)
    reference = data["reference"].set_index("parcel_id").to_crs(CRS_METRIC)

    mandals = ["DEMO-SERILINGAMPALLY", "DEMO-GACHIBOWLI", "DEMO-MADHAPUR"]
    rows = []
    shifted = []
    for _, row in parcels.iterrows():
        pid = row["parcel_id"]
        meta = directory[pid]
        survey = str(meta["survey_number"])
        subdivision = survey.split("/")[-1] if "/" in survey else ""
        index = int(pid.replace("SYN-P", ""))
        geometry_status = "reference"
        if pid in reference.index:
            drift = row.geometry.centroid.distance(reference.loc[pid].geometry.centroid)
            if drift > 1.0:
                geometry_status = "shifted_geometry"
                shifted.append(dict(parcel_id=pid, displacement_m=round(drift, 3)))
        rows.append(
            dict(
                parcel_id=pid,
                survey_number=survey,
                survey_subdivision=subdivision,
                district=meta["district"],
                mandal=mandals[index % len(mandals)],
                village=meta["village"],
                ward=f"DEMO-WARD-{index % 8 + 1:02d}",
                door_number=f"{index % 900 + 100}",
                address=meta["address"],
                area_sqm=round(float(row.geometry.area), 4),
                land_use=row["land_use"],
                source="BhuSetu synthetic integrated benchmark v1 (parcel registry)",
                synthetic=True,
                geometry_status=geometry_status,
                geometry=row.geometry,
            )
        )
    parcels = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS_METRIC)
    return parcels, shifted


def build_building_relationships(parcels, buildings):
    buildings = buildings.to_crs(CRS_METRIC)[["id", "geometry"]]
    parcel_ids = list(parcels.parcel_id)
    parcel_geoms = list(parcels.geometry)
    tree = STRtree(parcel_geoms)
    rows = []
    intersecting = 0
    for _, building in buildings.iterrows():
        geom = building.geometry
        if geom is None or geom.is_empty or geom.area <= 0:
            continue
        hits = []
        for j in tree.query(geom.buffer(MAX_BUILDING_DISTANCE_M)):
            j = int(j)
            inter = geom.intersection(parcel_geoms[j]).area
            distance = 0.0 if inter > 1e-6 else geom.distance(parcel_geoms[j])
            if inter > 1e-6 or distance <= MAX_BUILDING_DISTANCE_M:
                hits.append((j, inter, distance))
        crossing = sum(1 for _, inter, _ in hits if inter > 1.0) >= 2
        for j, inter, distance in hits:
            fraction = inter / geom.area if geom.area else 0.0
            if crossing and inter > 1.0:
                relation = "crosses_boundary"
            elif inter > 1e-6:
                relation = "within_parcel" if fraction >= 0.999 else "partial_overlap"
            else:
                relation = "adjacent_no_overlap"
            if inter > 1e-6:
                intersecting += 1
            rows.append(
                dict(
                    parcel_id=parcel_ids[j],
                    building_id=building["id"],
                    overlap_fraction=round(fraction, 6),
                    intersection_area_sqm=round(inter, 4),
                    distance_m=round(distance, 3),
                    relationship_type=relation,
                )
            )
    frame = pd.DataFrame(rows).sort_values(["parcel_id", "building_id"]).reset_index(drop=True)
    return frame, intersecting


def neighbour_map(parcels, tolerance=15.0):
    geoms = list(parcels.geometry)
    tree = STRtree(geoms)
    neighbours = {}
    for i, geom in enumerate(geoms):
        found = []
        for j in tree.query(geom.buffer(tolerance)):
            j = int(j)
            if j == i:
                continue
            found.append((geom.distance(geoms[j]), j))
        found.sort()
        neighbours[i] = found
    return neighbours


def build_utilities(data, parcels, rng):
    """Synthetic electricity, water and sewer service points and lines."""
    point_rows = []
    point_truth = []
    line_rows = []
    pid_list = list(parcels.parcel_id)
    geoms = list(parcels.geometry)
    representations = [g.representative_point() for g in geoms]
    neighbours = neighbour_map(parcels)

    counter = 0
    for i, pid in enumerate(pid_list):
        base = representations[i]
        forward = [(g, c) for g, c in neighbours[i] if c > i]
        partner = forward[0][1] if forward else i
        for department in ("electricity", "water", "sewer"):
            counter += 1
            service = "sewer" if department == "sewer" else department
            connection_id = f"SYN-{service[:3].upper()}-{counter:05d}"
            utility_id = f"SYN-UP-{counter:05d}"
            dx, dy = rng.uniform(-3, 3), rng.uniform(-3, 3)
            if rng.random() < UTILITY_POINT_SHIFT_FRACTION and partner != i:
                # Deliberate displacement toward the adjacent parcel.
                target = representations[partner]
                t = rng.uniform(0.25, 0.6)
                x = base.x + (target.x - base.x) * t + rng.uniform(-2, 2)
                y = base.y + (target.y - base.y) * t + rng.uniform(-2, 2)
            else:
                x, y = base.x + dx, base.y + dy
            point_rows.append(
                dict(utility_id=utility_id, department=department, connection_id=connection_id,
                     synthetic=True, geometry=Point(x, y))
            )
            point_truth.append(dict(utility_id=utility_id, department=department,
                                    connection_id=connection_id, parcel_id=pid))

    # Reuse the existing fictional water line fixture.
    existing = data["utility_network"].to_crs(CRS_METRIC)
    counter = 0
    for _, row in existing.iterrows():
        counter += 1
        line_rows.append(dict(utility_id=f"SYN-UL-{counter:05d}", department="water",
                              connection_id=f"SYN-WAT-L{counter:05d}", synthetic=True,
                              geometry=row.geometry))

    for department in ("electricity", "sewer"):
        for k in range(40):
            counter += 1
            i = rng.randrange(len(pid_list))
            forward = [(g, c) for g, c in neighbours[i] if c != i]
            j = forward[0][1] if forward else i
            a, b = representations[i], representations[j]
            offset = rng.uniform(-6, 6)
            geom = LineString([(a.x, a.y + offset), (b.x, b.y + offset)])
            line_rows.append(dict(utility_id=f"SYN-UL-{counter:05d}", department=department,
                                  connection_id=f"SYN-{department[:3].upper()}-L{counter:05d}",
                                  synthetic=True, geometry=geom))

    points = gpd.GeoDataFrame(point_rows, geometry="geometry", crs=CRS_METRIC)
    truth = gpd.GeoDataFrame(pd.merge(pd.DataFrame(point_truth), points.drop(columns="geometry"),
                                      on=["utility_id", "department", "connection_id"]),
                             geometry=points.geometry.values, crs=CRS_METRIC)
    lines = gpd.GeoDataFrame(line_rows, geometry="geometry", crs=CRS_METRIC)
    return points, truth, lines


def build_records(data, parcels, rng):
    """Repackage reused departmental records into per-department spec schemas."""
    parcel_lookup = parcels.set_index("parcel_id")
    truth = {row["record_id"]: row for row in data["answers"]}

    dev_parcels = {row["expected_parcel_id"] for row in data["answers"]
                   if row.get("split") == "development" and row.get("expected_parcel_id")}

    all_pids = sorted(parcel_lookup.index)
    recordless = set(sorted(rng.sample(all_pids, RECORDLESS_PARCELS)))

    reused = [r for r in data["records"] if r["department"] in DEPARTMENTS]
    reused = [r for r in reused if truth.get(r["record_id"], {}).get("expected_parcel_id") not in recordless]

    per_department = {d: [] for d in DEPARTMENTS}
    answers = []

    for record in reused:
        answer = truth[record["record_id"]]
        pid = answer["expected_parcel_id"]
        scenario = SCENARIO_MAP.get(answer["scenario"], answer["scenario"])
        parcel = parcel_lookup.loc[pid] if pid in parcel_lookup.index else None
        row = dict(
            record_id=record["record_id"],
            department=record["department"],
            account_id=record.get("account_id"),
            district=record.get("district", ""),
            mandal=parcel["mandal"] if parcel is not None else "",
            village=record.get("village", ""),
            survey_number=record.get("survey_number", ""),
            survey_subdivision=(str(record.get("survey_number", "")).split("/")[-1]
                                if "/" in str(record.get("survey_number", "")) else ""),
            address=record.get("address", ""),
            record_date=record.get("record_date"),
            easting_m=record.get("easting_m"),
            northing_m=record.get("northing_m"),
            crs=CRS_METRIC,
            synthetic=True,
            source=f"Synthetic integrated v1 · {record['department']} (reused departmental fixture)",
        )
        if record["department"] == "revenue":
            row["recorded_area_sqm"] = record.get("recorded_area_m2")
            row["land_use"] = parcel["land_use"] if parcel is not None else ""
        elif record["department"] == "municipal":
            row["assessment_id"] = f"DEMO-ASMT-{rng.randrange(10**8, 10**9)}"
            row["ward"] = parcel["ward"] if parcel is not None else ""
            row["door_number"] = parcel["door_number"] if parcel is not None else ""
            row["property_use"] = parcel["land_use"] if parcel is not None else ""
            row["built_area_sqm"] = (round(float(parcel["area_sqm"]) * rng.uniform(0.35, 0.9), 2)
                                     if parcel is not None else None)
        elif record["department"] == "electricity":
            row["connection_id"] = f"DEMO-ELEC-{rng.randrange(10**7, 10**8)}"
            row["connection_status"] = "active"
            row["connection_date"] = record.get("record_date")
        elif record["department"] == "water":
            row["connection_id"] = f"DEMO-WAT-{rng.randrange(10**7, 10**8)}"
            row["service_type"] = "water"
            row["connection_status"] = "active"
        per_department[record["department"]].append(row)
        answers.append(dict(
            record_id=record["record_id"], expected_parcel_id=pid,
            department=record["department"], scenario=scenario,
            split=answer.get("split", "test"),
            expected_matchable=bool(pid),
            notes=SCENARIO_NOTES.get(scenario, ""),
        ))

    # Sewer department: a genuine new set mirroring the reused water records.
    water_records = [r for r in per_department["water"]]

    def source_water_row(row):
        return next(r for r in reused if r["record_id"] == row["record_id"])

    for row in water_records:
        source = source_water_row(row)
        answer = truth[row["record_id"]]
        pid = answer["expected_parcel_id"]
        scenario = SCENARIO_MAP.get(answer["scenario"], answer["scenario"])
        sewer = dict(row)
        sewer["department"] = "sewer"
        sewer["record_id"] = "SYN-SEW-" + hashlib.sha256(
            f"{SEED}|sewer|{row['record_id']}".encode()).hexdigest()[:16].upper()
        sewer["account_id"] = "DEMO-" + format(rng.getrandbits(48), "012X")
        sewer["connection_id"] = f"DEMO-SEW-{rng.randrange(10**7, 10**8)}"
        sewer["service_type"] = "sewer"
        sewer["connection_status"] = "active"
        sewer["source"] = "Synthetic integrated v1 · sewer (generated, mirrors water scenario)"
        per_department["sewer"].append(sewer)
        answers.append(dict(
            record_id=sewer["record_id"], expected_parcel_id=pid, department="sewer",
            scenario=scenario, split=answer.get("split", "test"),
            expected_matchable=bool(pid), notes=SCENARIO_NOTES.get(scenario, ""),
        ))

    # Controlled scenario: one record competing between two nearby parcels.
    neighbours = neighbour_map(parcels)
    candidates = [i for i, found in neighbours.items()
                  if found and parcel_lookup.index[i] not in recordless]
    rng.shuffle(candidates)
    for k in range(COMPETING_RECORDS):
        i = candidates[k % len(candidates)]
        j = neighbours[i][0][1]
        own_pid, other_pid = parcel_lookup.index[i], parcel_lookup.index[j]
        own, other = parcel_lookup.iloc[i], parcel_lookup.iloc[j]
        point = own.geometry.intersection(other.geometry).centroid
        if point.is_empty:
            point = Point((own.geometry.centroid.x + other.geometry.centroid.x) / 2,
                          (own.geometry.centroid.y + other.geometry.centroid.y) / 2)
        department = DEPARTMENTS[k % len(DEPARTMENTS)]
        record_id = "SYN-CMP-" + hashlib.sha256(f"{SEED}|competing|{i}|{k}".encode()).hexdigest()[:16].upper()
        row = dict(
            record_id=record_id, department=department,
            account_id="DEMO-" + format(rng.getrandbits(48), "012X"),
            district=own["district"], mandal=own["mandal"], village=own["village"],
            survey_number=own["survey_number"], survey_subdivision=own["survey_subdivision"],
            address=other["address"], record_date="2025-12-01",
            easting_m=round(point.x, 6), northing_m=round(point.y, 6),
            crs=CRS_METRIC, synthetic=True,
            source="Synthetic integrated v1 · competing-identifier record",
        )
        if department == "revenue":
            row["recorded_area_sqm"] = round(float(own["area_sqm"]), 2)
            row["land_use"] = own["land_use"]
        elif department == "municipal":
            row["assessment_id"] = f"DEMO-ASMT-{rng.randrange(10**8, 10**9)}"
            row["ward"] = own["ward"]
            row["door_number"] = own["door_number"]
            row["property_use"] = own["land_use"]
            row["built_area_sqm"] = round(float(own["area_sqm"]) * 0.6, 2)
        elif department == "electricity":
            row["connection_id"] = f"DEMO-ELEC-{rng.randrange(10**7, 10**8)}"
            row["connection_status"] = "active"
            row["connection_date"] = "2025-12-01"
        elif department in ("water", "sewer"):
            row["connection_id"] = f"DEMO-{department[:3].upper()}-{rng.randrange(10**7, 10**8)}"
            row["service_type"] = department
            row["connection_status"] = "active"
        per_department[department].append(row)
        split = "development" if own_pid in dev_parcels else "test"
        answers.append(dict(
            record_id=record_id, expected_parcel_id=own_pid, department=department,
            scenario="record_competing_between_parcels", split=split, expected_matchable=True,
            notes=(f"Survey identifier belongs to {own_pid}; address and location point to "
                   f"neighbouring {other_pid}. Correct action is review, not silent auto-accept."),
        ))

    # Order columns to the documented schema.
    columns = {
        "revenue": ["record_id", "department", "account_id", "district", "mandal", "village",
                    "survey_number", "survey_subdivision", "address", "recorded_area_sqm",
                    "land_use", "record_date", "easting_m", "northing_m", "crs", "synthetic", "source"],
        "municipal": ["record_id", "department", "assessment_id", "account_id", "district",
                      "village", "ward", "door_number", "address", "survey_number", "property_use",
                      "built_area_sqm", "easting_m", "northing_m", "crs", "record_date",
                      "synthetic", "source"],
        "electricity": ["record_id", "department", "connection_id", "account_id", "district",
                        "village", "address", "survey_number", "connection_status", "connection_date",
                        "record_date", "easting_m", "northing_m", "crs", "synthetic", "source"],
        "water": ["record_id", "department", "connection_id", "account_id", "district", "village",
                  "address", "survey_number", "service_type", "connection_status", "record_date",
                  "easting_m", "northing_m", "crs", "synthetic", "source"],
        "sewer": ["record_id", "department", "connection_id", "account_id", "district", "village",
                  "address", "survey_number", "service_type", "connection_status", "record_date",
                  "easting_m", "northing_m", "crs", "synthetic", "source"],
    }
    ordered = {}
    for department, rows in per_department.items():
        ordered[department] = [{k: r.get(k) for k in columns[department]} for r in rows]

    parcels_without = []
    for pid in sorted(recordless):
        row = parcel_lookup.loc[pid]
        parcels_without.append(dict(
            parcel_id=pid, scenario="parcel_without_departmental_record",
            split="development" if pid in dev_parcels else "test", expected_matchable=True,
            notes=SCENARIO_NOTES["parcel_without_departmental_record"],
        ))
    return ordered, answers, parcels_without


def validate(parcels, relationships, utilities_points, utilities_lines, records, answers,
             aoi, recordless):
    failures = []
    # Geometry validity.
    for _, row in parcels.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty or not geom.is_valid or geom.area <= 0:
            failures.append(f"invalid parcel geometry: {row.parcel_id}")
    # Unique IDs.
    for label, values in [("parcel_id", list(parcels.parcel_id)),
                          ("utility_id(points)", list(utilities_points.utility_id)),
                          ("utility_id(lines)", list(utilities_lines.utility_id))]:
        if len(set(values)) != len(values):
            failures.append(f"duplicate {label}")
    all_record_ids = [r["record_id"] for rows in records.values() for r in rows]
    if len(set(all_record_ids)) != len(all_record_ids):
        failures.append("duplicate record_id across department files")
    if len(answers) != len(all_record_ids):
        failures.append(f"answers/records mismatch: {len(answers)} vs {len(all_record_ids)}")
    # CRS.
    for label, frame in [("parcels", parcels), ("utility_points", utilities_points),
                         ("utility_lines", utilities_lines)]:
        if frame.crs is None or frame.crs.to_string().upper() not in (CRS_GEOG, CRS_METRIC):
            failures.append(f"unexpected CRS for {label}: {frame.crs}")
    # AOI intersection.
    aoi_geom = aoi.to_crs(CRS_METRIC).union_all()
    for _, row in parcels.to_crs(CRS_METRIC).iterrows():
        if not row.geometry.intersects(aoi_geom):
            failures.append(f"parcel outside AOI: {row.parcel_id}")
    # Departments.
    valid_departments = set(DEPARTMENTS)
    for department, rows in records.items():
        for row in rows:
            if row["department"] != department or department not in valid_departments:
                failures.append(f"invalid department: {row['record_id']}")
    # Required fields.
    required = {
        "revenue": ["record_id", "department", "account_id", "district", "mandal", "village",
                    "survey_number", "survey_subdivision", "address", "recorded_area_sqm",
                    "land_use", "record_date", "crs"],
        "municipal": ["record_id", "department", "assessment_id", "account_id", "district", "village",
                      "ward", "door_number", "address", "survey_number", "property_use",
                      "built_area_sqm", "easting_m", "northing_m", "crs", "record_date"],
        "electricity": ["record_id", "department", "connection_id", "account_id", "district", "village",
                        "address", "survey_number", "connection_status", "connection_date",
                        "easting_m", "northing_m", "crs"],
        "water": ["record_id", "department", "connection_id", "account_id", "district", "village",
                  "address", "survey_number", "service_type", "connection_status", "crs"],
        "sewer": ["record_id", "department", "connection_id", "account_id", "district", "village",
                  "address", "survey_number", "service_type", "connection_status", "crs"],
    }
    for department, rows in records.items():
        columns = set(rows[0]) if rows else set()
        missing = [f for f in required[department] if f not in columns]
        if missing:
            failures.append(f"missing fields in {department}: {missing}")
    # PII guard.
    banned = ("aadhaar", "aadhar", "phone", "mobile", "owner_name", "first_name", "last_name",
              "father", "email")
    for department, rows in records.items():
        if rows and any(banned_token in key.lower() for key in rows[0] for banned_token in banned):
            failures.append(f"possible PII field in {department}")
    # Record-less parcels must really have no records.
    with_records = {a["expected_parcel_id"] for a in answers if a["expected_parcel_id"]}
    if recordless & with_records:
        failures.append(f"record-less parcels still have records: {sorted(recordless & with_records)}")
    return failures


def data_dictionary(records, relationships, shifted, recordless):
    lines = []
    lines.append("# BhuSetu integrated synthetic dataset — data dictionary\n")
    lines.append(f"> {LABEL}\n")
    lines.append("All coordinates are EPSG:4326 (WGS 84 longitude/latitude) in GeoJSON files and "
                 "EPSG:32644 (UTM zone 44N, metres) for metric attributes. Every synthetic feature "
                 "carries `synthetic: true`. No personal names, Aadhaar numbers, phone numbers, "
                 "emails or other sensitive personal information are present in any field.\n")
    lines.append("## inputs/parcels.geojson\n")
    lines.append("| field | type | units | CRS | source | status | generation rule | privacy |")
    lines.append("|---|---|---|---|---|---|---|---|")
    pfields = [
        ("parcel_id", "string", "—", "—", "synthetic", "synthetic", "Reused from synthetic_benchmark/inputs/parcels.geojson (SYN-P####)", "not personal"),
        ("survey_number", "string", "—", "—", "synthetic", "synthetic", "Reused from departmental/inputs/parcel_directory.json", "not personal"),
        ("survey_subdivision", "string", "—", "—", "synthetic", "synthetic", "Suffix of survey_number after '/'", "not personal"),
        ("district", "string", "—", "—", "synthetic", "synthetic", "Reused DEMO district label", "not personal"),
        ("mandal", "string", "—", "—", "synthetic", "synthetic", "Cyclic assignment from a fixed demo mandal list by parcel index", "not personal"),
        ("village", "string", "—", "—", "synthetic", "synthetic", "Reused DEMO village label", "not personal"),
        ("ward", "string", "—", "—", "synthetic", "synthetic", "Cyclic DEMO-WARD-nn assignment by parcel index", "not personal"),
        ("door_number", "string", "—", "—", "synthetic", "synthetic", "Deterministic demo door number by parcel index", "not personal"),
        ("address", "string", "—", "—", "synthetic", "synthetic", "Reused fictional plot/street address", "not personal"),
        ("area_sqm", "float", "m²", "EPSG:32644", "synthetic", "synthetic", "Geodesic-equivalent metric area of the emitted parcel geometry", "not personal"),
        ("land_use", "string", "—", "—", "synthetic", "synthetic", "Reused of residential/commercial/mixed_use", "not personal"),
        ("source", "string", "—", "—", "synthetic", "synthetic", "Fixed provenance string", "not personal"),
        ("synthetic", "boolean", "—", "—", "synthetic", "synthetic", "Always true", "not personal"),
        ("geometry_status", "string", "—", "—", "synthetic", "synthetic", "reference or shifted_geometry (>1 m centroid drift vs reference geometry)", "not personal"),
        ("geometry", "MultiPolygon/Polygon", "—", "EPSG:4326", "synthetic", "synthetic", "Reused synthetic parcel boundary; 30 carry controlled displacement", "not personal"),
    ]
    for name, typ, unit, crs, source, status, rule, privacy in pfields:
        lines.append(f"| `{name}` | {typ} | {unit} | {crs} | {source} | {status} | {rule} | {privacy} |")
    lines.append(f"\nShifted parcels: **{len(shifted)}**. Parcels with no departmental record: "
                 f"**{len(recordless)}**.\n")

    lines.append("## inputs/building_parcel_relationships.csv\n")
    lines.append("| field | type | units | CRS | source | status | generation rule | privacy |")
    lines.append("|---|---|---|---|---|---|---|---|")
    rfields = [
        ("parcel_id", "string", "—", "—", "synthetic", "synthetic", "Synthetic parcel identifier", "not personal"),
        ("building_id", "string", "—", "—", "real", "real (model-derived)", "Microsoft building footprint id (context only, not ownership)", "not personal"),
        ("overlap_fraction", "float", "fraction 0–1", "EPSG:32644", "derived", "derived", "intersection_area / building area", "not personal"),
        ("intersection_area_sqm", "float", "m²", "EPSG:32644", "derived", "derived", "Area of parcel ∩ building", "not personal"),
        ("distance_m", "float", "m", "EPSG:32644", "derived", "derived", "0 when intersecting; else parcel-to-building distance (≤10 m reported)", "not personal"),
        ("relationship_type", "string", "—", "—", "derived", "derived", "within_parcel | partial_overlap | crosses_boundary | adjacent_no_overlap", "not personal"),
    ]
    for name, typ, unit, crs, source, status, rule, privacy in rfields:
        lines.append(f"| `{name}` | {typ} | {unit} | {crs} | {source} | {status} | {rule} | {privacy} |")
    lines.append(f"\nRows: **{len(relationships)}**. Buildings are Microsoft model predictions, "
                 "not independently verified structures; they are context, never cadastral truth.\n")

    lines.append("## inputs/utility_points.geojson and inputs/utility_lines.geojson\n")
    lines.append("| field | type | units | CRS | source | status | generation rule | privacy |")
    lines.append("|---|---|---|---|---|---|---|---|")
    ufields = [
        ("utility_id", "string", "—", "—", "synthetic", "synthetic", "Sequential SYN-UP-##### (points) / SYN-UL-##### (lines)", "not personal"),
        ("department", "string", "—", "—", "synthetic", "synthetic", "electricity | water | sewer", "not personal"),
        ("connection_id", "string", "—", "—", "synthetic", "synthetic", "Fictional service connection key", "not personal"),
        ("synthetic", "boolean", "—", "—", "synthetic", "synthetic", "Always true", "not personal"),
        ("geometry", "Point / LineString", "—", "EPSG:4326", "synthetic", "synthetic", "Seeded jitter near a parcel; ~30% shifted toward a neighbour. Water lines reuse the existing fictional water fixture.", "not personal"),
    ]
    for name, typ, unit, crs, source, status, rule, privacy in ufields:
        lines.append(f"| `{name}` | {typ} | {unit} | {crs} | {source} | {status} | {rule} | {privacy} |")
    lines.append("\nThe true serving parcel is stored only in "
                 "`evaluation_only/utility_points_reference.geojson`.\n")

    lines.append("## inputs/{department}_records.json\n")
    lines.append("One file per department: revenue, municipal, electricity, water, sewer. "
                 "Record IDs are random and never encode the target parcel. No file contains a "
                 "`parcel_id` foreign key — the matcher must infer it.\n")
    lines.append("| field | type | units | CRS | source | status | generation rule | privacy |")
    lines.append("|---|---|---|---|---|---|---|---|")
    common = [
        ("record_id", "string", "—", "—", "synthetic", "synthetic", "Reused departmental record id (or generated for sewer/competing cases)", "not personal"),
        ("department", "string", "—", "—", "synthetic", "synthetic", "Fixed per file", "not personal"),
        ("account_id", "string", "—", "—", "synthetic", "synthetic", "Fictional department account key", "not personal"),
        ("district", "string", "—", "—", "synthetic", "synthetic", "As recorded; blank for missing-scope cases", "not personal"),
        ("village", "string", "—", "—", "synthetic", "synthetic", "As recorded; blank for missing-scope cases", "not personal"),
        ("survey_number", "string", "—", "—", "synthetic", "synthetic", "As recorded; may be blank, reformatted or wrong by scenario", "not personal"),
        ("address", "string", "—", "—", "synthetic", "synthetic", "Fictional plot/street address; may contain a typo", "not personal"),
        ("record_date", "string", "ISO date", "—", "synthetic", "synthetic", "Fixture date; pre-2020 for old_record", "not personal"),
        ("easting_m / northing_m", "float", "m", "EPSG:32644", "synthetic", "synthetic", "Parcel reference point with jitter; null when geometry is missing", "not personal"),
        ("crs", "string", "—", "—", "synthetic", "synthetic", "Always EPSG:32644", "not personal"),
        ("synthetic", "boolean", "—", "—", "synthetic", "synthetic", "Always true", "not personal"),
        ("source", "string", "—", "—", "synthetic", "synthetic", "Provenance string", "not personal"),
    ]
    extra = [
        ("mandal (revenue)", "string", "—", "—", "synthetic", "synthetic", "Parcel mandal", "not personal"),
        ("survey_subdivision (revenue)", "string", "—", "—", "synthetic", "synthetic", "Subdivision suffix", "not personal"),
        ("recorded_area_sqm (revenue)", "float", "m²", "EPSG:32644", "synthetic", "synthetic", "Parcel area; inflated for area_error", "not personal"),
        ("land_use (revenue)", "string", "—", "—", "synthetic", "synthetic", "Parcel land use", "not personal"),
        ("assessment_id (municipal)", "string", "—", "—", "synthetic", "synthetic", "Fictional assessment key", "not personal"),
        ("ward / door_number (municipal)", "string", "—", "—", "synthetic", "synthetic", "Parcel ward and demo door number", "not personal"),
        ("property_use (municipal)", "string", "—", "—", "synthetic", "synthetic", "Parcel land use", "not personal"),
        ("built_area_sqm (municipal)", "float", "m²", "EPSG:32644", "synthetic", "synthetic", "Parcel area × seeded 0.35–0.9 factor", "not personal"),
        ("connection_id", "string", "—", "—", "synthetic", "synthetic", "Fictional service connection key", "not personal"),
        ("connection_status", "string", "—", "—", "synthetic", "synthetic", "active for all generated records", "not personal"),
        ("connection_date (electricity)", "string", "ISO date", "—", "synthetic", "synthetic", "Mirrors record_date", "not personal"),
        ("service_type", "string", "—", "—", "synthetic", "synthetic", "water | sewer", "not personal"),
    ]
    for name, typ, unit, crs, source, status, rule, privacy in common + extra:
        lines.append(f"| `{name}` | {typ} | {unit} | {crs} | {source} | {status} | {rule} | {privacy} |")

    lines.append("\n## evaluation_only/answers.json\n")
    lines.append("| field | type | meaning |")
    lines.append("|---|---|---|")
    lines.append("| `record_id` | string | Operational record identifier |")
    lines.append("| `expected_parcel_id` | string / null | True synthetic parcel; null when no parcel matches |")
    lines.append("| `department` | string | Owning department |")
    lines.append("| `scenario` | string | Controlled scenario label |")
    lines.append("| `split` | string | development or test |")
    lines.append("| `expected_matchable` | boolean | Whether a correct parcel exists at all |")
    lines.append("| `notes` | string | Human-readable scenario explanation |")
    lines.append("\nAlso in evaluation_only/: `parcels_without_records.json` "
                 "(parcels deliberately given no departmental record) and "
                 "`utility_points_reference.geojson` (true serving parcel per utility point). "
                 "These files must never be read by the matching engine.\n")
    lines.append("## Scenario counts\n")
    lines.append("| scenario | records |")
    lines.append("|---|---:|")
    return "\n".join(lines) + "\n"


def main():
    guard()
    for sub in ("inputs", "evaluation_only", "metadata"):
        (PACKAGE / sub).mkdir(parents=True, exist_ok=True)

    rng = random.Random(SEED)
    data = load_sources()
    parcels, shifted = build_parcels(data, rng)
    relationships, intersecting_rows = build_building_relationships(parcels, data["buildings"])
    utilities_points, utility_truth, utilities_lines = build_utilities(data, parcels, rng)
    records, answers, recordless = build_records(data, parcels, rng)

    recordless_ids = {row["parcel_id"] for row in recordless}
    failures = validate(parcels, relationships, utilities_points, utilities_lines, records,
                        answers, data["aoi"], recordless_ids)

    # ---- write inputs ----
    parcels_out = parcels.to_crs(CRS_GEOG)
    parcels_out.to_file(PACKAGE / "inputs/parcels.geojson", driver="GeoJSON")
    relationships.to_csv(PACKAGE / "inputs/building_parcel_relationships.csv", index=False,
                         quoting=csv.QUOTE_MINIMAL)
    utilities_points.to_crs(CRS_GEOG).to_file(PACKAGE / "inputs/utility_points.geojson", driver="GeoJSON")
    utilities_lines.to_crs(CRS_GEOG).to_file(PACKAGE / "inputs/utility_lines.geojson", driver="GeoJSON")
    for department, rows in records.items():
        write_json(PACKAGE / f"inputs/{department}_records.json", rows)

    # ---- write evaluation_only ----
    write_json(PACKAGE / "evaluation_only/answers.json", answers)
    write_json(PACKAGE / "evaluation_only/parcels_without_records.json", recordless)
    utility_truth.to_crs(CRS_GEOG).to_file(
        PACKAGE / "evaluation_only/utility_points_reference.geojson", driver="GeoJSON")

    # ---- metadata ----
    counts = {
        "parcels": int(len(parcels)),
        "shifted_geometry_parcels": len(shifted),
        "parcels_without_departmental_record": len(recordless),
        "records_by_department": {d: len(rows) for d, rows in records.items()},
        "records_total": sum(len(rows) for rows in records.values()),
        "buildings_reused": int(len(data["buildings"])),
        "building_parcel_relationships": int(len(relationships)),
        "building_parcel_intersections": int(intersecting_rows),
        "utility_points": int(len(utilities_points)),
        "utility_lines": int(len(utilities_lines)),
        "overlapping_parcel_pairs": int(_overlapping_pairs(parcels)),
    }
    write_json(PACKAGE / "metadata/generation_summary.json", {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": SEED, "aoi": AOI, "crs_metric": CRS_METRIC, "crs_geojson": CRS_GEOG,
        "counts": counts, "validation_failures": failures, "notice": LABEL,
    })
    (PACKAGE / "metadata/data_dictionary.md").write_text(
        _fill_scenarios(data_dictionary(records, relationships, shifted, recordless), answers),
        encoding="utf-8")

    manifest = {
        "dataset": "hyderabad_kondapur/synthetic_integrated_v1",
        "notice": LABEL,
        "synthetic": True,
        "generation": {
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "generator": "scripts/generate_integrated_dataset.py",
            "fixed_seed": SEED,
        },
        "study_area": {"west": AOI["west"], "south": AOI["south"], "east": AOI["east"],
                       "north": AOI["north"], "metric_crs": CRS_METRIC, "geojson_crs": CRS_GEOG},
        "departments": DEPARTMENTS,
        "counts": counts,
        "scenario_counts": _scenario_counts(answers),
        "validation_failures": failures,
        "sources_reused": {
            path.relative_to(KONDAPUR).as_posix(): {"sha256": sha256_file(path),
                                                    "bytes": path.stat().st_size}
            for path in [SOURCES["parcel_geometry"], SOURCES["parcel_reference"],
                         SOURCES["parcel_directory"], SOURCES["department_records"],
                         SOURCES["department_answers"], SOURCES["building_intersections"],
                         SOURCES["utility_network"], *SOURCES["context"]]
        },
        "attribution": ["Microsoft GlobalMLBuildingFootprints — CDLA-Permissive-2.0",
                        "© OpenStreetMap contributors — ODbL-1.0"],
        "synthetic_limitations": [
            "Parcel boundaries are invented (seeded Voronoi clipped to the AOI), not official cadastral boundaries.",
            "No ownership, ownership transfer or legal title is represented anywhere in this package.",
            "Administrative scopes (district, mandal, village, ward) use DEMO- labels and are fictional.",
            "Departmental identities, accounts and service connections are invented; no real customer data.",
            "30 parcels carry controlled geometry displacement; a small number of overlaps/gaps are intentional.",
            "Utility points and lines do not follow real pipes, cables or roads.",
            "Building relationships use Microsoft model-derived footprints, which are predictions, not verified structures.",
            "Reused records and their true parcel associations come from the departmental fixture; reuse is documented above.",
            "This is a deterministic engineering benchmark, not independent real-world validation.",
            "evaluation_only/ must never be read by the matching application.",
        ],
        "files": {},
    }
    for path in sorted(PACKAGE.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            manifest["files"][path.relative_to(PACKAGE).as_posix()] = {
                "sha256": sha256_file(path), "bytes": path.stat().st_size}
    write_json(PACKAGE / "metadata/manifest.json", manifest)

    print(json.dumps({"counts": counts, "scenario_counts": _scenario_counts(answers),
                      "validation_failures": failures}, indent=2))


def _fill_scenarios(text, answers):
    counts = _scenario_counts(answers)
    lines = []
    for name in sorted(counts):
        lines.append(f"| `{name}` | {counts[name]} |")
    marker = "|---|---:|"
    head, _, tail = text.partition(marker)
    return head + marker + "\n" + "\n".join(lines) + "\n"


def _scenario_counts(answers):
    counts = {}
    for row in answers:
        counts[row["scenario"]] = counts.get(row["scenario"], 0) + 1
    return counts


def _overlapping_pairs(parcels):
    geoms = list(parcels.geometry)
    tree = STRtree(geoms)
    total = 0
    for i, geom in enumerate(geoms):
        for j in tree.query(geom):
            j = int(j)
            if j <= i:
                continue
            if geom.intersection(geoms[j]).area > 1.0:
                total += 1
    return total


if __name__ == "__main__":
    main()
