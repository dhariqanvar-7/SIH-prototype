# BhuSetu — SIH 26013

Local synthetic urban land integration demo. Run from PowerShell:

```powershell
cd C:\Users\aadhi\SIH
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open http://localhost:8501. Select the `.venv` interpreter in VS Code.
For a fresh setup, create a Python virtual environment and run `python -m pip install -r requirements.txt`.
The existing `SIH.py` is an older generator, preserved unchanged; the application entry point is `app.py`.
The old `requirement.txt` contains shell syntax; use `requirements.txt`.

## Demo walkthrough

1. Open Map & evidence; toggle cadastral, T1/T2, utilities, polygon observation areas and GNSS layers.
2. Select a parcel for source properties, candidate scores and observation evidence.
3. Review queue shows invalid polygons, overlaps, duplicates, missing records, area/use conflicts and uncertain building links.
4. Select a proposal, inspect its evidence, accept/reject and save. Decisions persist in `state/reviews.sqlite` with reviewer, UTC time and append-only history. Set pending to undo a decision. Dataset fingerprints isolate changed inputs.
5. Building changes compares actual footprint geometry across acquisition dates despite different IDs.
6. Export integrated parcel GeoJSON, proposal decisions, audit CSV and change CSV.

## Data and method

Pipeline reads only `dataset/inputs` and manifest. Metric calculations use EPSG:32643; map and export use EPSG:4326. Every input geometry is checked before spatial operations. Invalid features are excluded from matching, preserved in originals, and given make_valid repair proposals. Accepted parcel repairs affect export; matching remains based on valid original geometries, so review does not silently rewrite evidence. Overlaps and other conflicts remain advisory.

Record references are normalized, with one proposal per source record. Multiple records are retained for human review. Building candidates use a spatial index within 15 m; score is 0.75 × building overlap fraction + 0.15 × proximity + 0.10 × area fit. Scores are heuristic, not probabilities. Temporal matching greedily assigns candidates by IoU, centroid distance and area similarity. Area growth above 15% is a possible extension. Extraction omissions and displacement can produce false changes.

The legacy GeoJSON has unknown CRS and stays quarantined. To admit it requires explicit source CRS confirmation and a documented ingestion rule; this demo provides no automatic assignment. GNSS date is unknown and no reference correspondences exist. Observations are polygon areas, not points. Synthetic data does not establish real-world model performance or legal accuracy. No learned classifier is claimed.

Original inputs and answer keys were preserved. Previous metadata/generator copies are in `backups/pre-mvp`; `fix_metadata.py` corrects metadata with the generator's canonical hash convention. Root and dataset generators contain the same corrections and refuse to overwrite existing output directories. Generate into a new directory to preserve original data. `SIH.py` is an untouched legacy copy and should not be used to regenerate.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe evaluate.py
```

Evaluation loads answer keys only after the input-only pipeline finishes. It measures record link correctness and reports temporal counts, not temporal accuracy. Tests cover source hash preservation, metadata hashes, answer-key isolation, invalid geometry review, persistence, reversal, changed-dataset isolation, spatial changes and Streamlit rendering.

This MVP does not implement imagery segmentation, live department APIs, authentication, production synchronization or cadastral adjudication. Map vectors are local; optional OpenStreetMap tiles and browser map libraries require network access.
