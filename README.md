# BhuSetu — SIH 26013

Urban land integration prototype. The default workspace is **Kondapur · Integrated
synthetic v1**: 300 fictional parcels and 1,580 fictional records across revenue,
municipal, electricity, water and sewer. It reuses 480 real Microsoft building
footprints, 251 OSM road/path segments, Sentinel-2 imagery and Copernicus
elevation. The earlier Kondapur and 100-parcel demonstrations remain selectable.

The **Parcel profile** and **Department matching** tabs connect land to the
selected workspace's fictional records. The earlier Kondapur workspace contains
1,610 records, including survey records; the integrated workspace has 1,580 and
adds sewer records and synthetic utility geometry.
**Approved Records** lists accepted and automatically approved records by parcel.
Choose a parcel and then a record to inspect its source fields and match evidence;
a reviewer can return a disputed approval to pending or reject it there.
Matching combines scoped identifier indexes, an R-tree and address-token search,
then scores department-specific evidence and flags uncertainty. See the
[algorithm and measured results](reports/MATCHING_REPORT.md) and
[SIH demonstration guide](reports/DEMO_WALKTHROUGH.md).

## Run

From PowerShell in this project, run `./start.ps1`, then open http://localhost:8501.
The launcher prefers `.venv` and can use the bundled Codex Python runtime with
local packages if the virtual environment points to a missing Python installation.
For a fresh environment, create `.venv`, install `requirements.txt`, and run
`python -m streamlit run app.py --server.address 127.0.0.1`.

## Demo walkthrough

1. **Map & evidence:** choose a parcel, toggle real and synthetic vector layers,
   and display satellite imagery or surface elevation. Hover for properties.
2. **Review queue:** inspect overlaps, ambiguous building links and area conflicts.
   Select a parcel to inspect its proposed department records. Accept, reject,
   leave pending, or remove a mapping; decisions persist with reviewer and audit
   history. Other proposal types remain under a separate expander.
3. **Building changes:** Kondapur has one footprint snapshot with unknown imagery
   dates, so temporal analysis is unavailable. The legacy workspace retains its
   two synthetic snapshots for demonstrating change analysis.
4. **Validation:** inspect geometry results, source status and raster coverage.
5. **Export:** download integrated parcels, decisions, source status and audit.
   Synthetic labels and source provenance remain attached to parcel exports.

## Dataset and method

The new source package is in `dataset/hyderabad_kondapur`. Its
[dataset guide](dataset/hyderabad_kondapur/REMAINING_DATA.md) describes source
availability, licences, acquisition dates and synthetic substitutes. Nothing in
this dataset establishes legal boundaries, real ownership or surveyed accuracy.

Metric operations use **EPSG:32644** for Kondapur and **EPSG:32643** for the legacy
demo. Inputs are transformed explicitly; map and GeoJSON exports use EPSG:4326.
Satellite imagery is 10 m and elevation is approximately 30 m. Elevation is a
surface model, not a detailed bare-earth model. Raster overlays are georeferenced;
source files remain unchanged.

`data_sources.py` adapts the new formats without rewriting source data.
`pipeline.py` reads only operational inputs and relevant metadata. Evaluation
answers are not read by the app or matching engine. Input fingerprints isolate
review decisions between workspaces and data revisions; raster files are included
in cache invalidation.

The original baseline record links use normalized parcel identifiers. The newer
departmental matcher handles inconsistent and missing fields without receiving
the hidden parcel answer. Building candidates lie within
15 m of valid parcels; scores combine 75% building-overlap fraction, 15% proximity
and 10% area fit. Scores are heuristic rankings, not probabilities. Accepted
repairs affect export; matching continues to use valid original geometries.
Strong top-ranked departmental associations are approved automatically and can
be returned to pending or rejected by a reviewer. Scores are evidence rankings,
not calibrated confidence probabilities. Building links and geometry repairs
still use manual review.
If two records of the same department point to one parcel, both require human
review, even when their individual evidence scores are strong. A reviewer may
approve both after checking whether they represent legitimate separate accounts.

The integrated workspace uses the same indexed department matcher and recomputes
building-to-parcel candidates from the input geometries. Its synthetic utility
points and lines appear on the map and as proximity evidence in parcel profiles.
Their connection IDs do not join the fictional department records, so proximity
alone is not presented as a confirmed service association. The operational
package is in `dataset/hyderabad_kondapur/synthetic_integrated_v1/inputs/`;
`evaluation_only/` remains outside the runtime matching path.

Kondapur includes 30 displaced synthetic parcels and 20 inflated record areas.
Voronoi-based test parcels can cut buildings and are not recovered cadastral
boundaries. Synthetic utilities are separate from real OSM objects. OSM data
are not authoritative municipal records. The dataset guide includes Microsoft,
OpenStreetMap and Copernicus attribution.

## Validation

With the project environment active:

```powershell
python -m pytest -q
python evaluate.py
python evaluate.py --legacy
python evaluate_departments.py
python benchmark_matching.py --size 100000
```

Evaluation reads answer keys only after input-only pipeline output exists. The
Kondapur evaluator measures synthetic record linkage and area-conflict detection;
it does not establish real-world cadastral or building association accuracy.
Tests cover answer-key isolation, coordinate systems, source preservation, raster
extent/transparency, review persistence, export provenance and both workspaces.

Original synthetic data and previous generator copies remain preserved. The
legacy unknown-CRS fixture stays quarantined. `SIH.py` is an untouched historical
generator, not the app entry point. The prototype does not implement image
segmentation, authentication, live department APIs or production synchronization.
