# BhuSetu — SIH 26013

Urban land integration prototype. The default workspace is **Kondapur, Hyderabad**:
480 real Microsoft building footprints, 251 OSM road/path segments, Sentinel-2
imagery and Copernicus elevation, alongside 300 synthetic parcels and fictional
revenue records. Verification and GNSS observations are simulated. The earlier
100-parcel synthetic demonstration remains selectable in the sidebar.

The **Parcel profile** and **Department matching** tabs now connect land to
1,610 fictional revenue, municipal, electricity, water and survey records.
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
   Accept/reject proposals; decisions persist with reviewer and audit history.
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
No correction or association is accepted automatically.

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
