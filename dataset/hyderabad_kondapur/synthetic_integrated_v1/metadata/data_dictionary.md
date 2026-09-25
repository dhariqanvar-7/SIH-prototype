# BhuSetu integrated synthetic dataset — data dictionary

> Synthetic demonstration data for TRL 3 evaluation; not official cadastral or ownership data.

All coordinates are EPSG:4326 (WGS 84 longitude/latitude) in GeoJSON files and EPSG:32644 (UTM zone 44N, metres) for metric attributes. Every synthetic feature carries `synthetic: true`. No personal names, Aadhaar numbers, phone numbers, emails or other sensitive personal information are present in any field.

## inputs/parcels.geojson

| field | type | units | CRS | source | status | generation rule | privacy |
|---|---|---|---|---|---|---|---|
| `parcel_id` | string | — | — | synthetic | synthetic | Reused from synthetic_benchmark/inputs/parcels.geojson (SYN-P####) | not personal |
| `survey_number` | string | — | — | synthetic | synthetic | Reused from departmental/inputs/parcel_directory.json | not personal |
| `survey_subdivision` | string | — | — | synthetic | synthetic | Suffix of survey_number after '/' | not personal |
| `district` | string | — | — | synthetic | synthetic | Reused DEMO district label | not personal |
| `mandal` | string | — | — | synthetic | synthetic | Cyclic assignment from a fixed demo mandal list by parcel index | not personal |
| `village` | string | — | — | synthetic | synthetic | Reused DEMO village label | not personal |
| `ward` | string | — | — | synthetic | synthetic | Cyclic DEMO-WARD-nn assignment by parcel index | not personal |
| `door_number` | string | — | — | synthetic | synthetic | Deterministic demo door number by parcel index | not personal |
| `address` | string | — | — | synthetic | synthetic | Reused fictional plot/street address | not personal |
| `area_sqm` | float | m² | EPSG:32644 | synthetic | synthetic | Geodesic-equivalent metric area of the emitted parcel geometry | not personal |
| `land_use` | string | — | — | synthetic | synthetic | Reused of residential/commercial/mixed_use | not personal |
| `source` | string | — | — | synthetic | synthetic | Fixed provenance string | not personal |
| `synthetic` | boolean | — | — | synthetic | synthetic | Always true | not personal |
| `geometry_status` | string | — | — | synthetic | synthetic | reference or shifted_geometry (>1 m centroid drift vs reference geometry) | not personal |
| `geometry` | MultiPolygon/Polygon | — | EPSG:4326 | synthetic | synthetic | Reused synthetic parcel boundary; 30 carry controlled displacement | not personal |

Shifted parcels: **30**. Parcels with no departmental record: **12**.

## inputs/building_parcel_relationships.csv

| field | type | units | CRS | source | status | generation rule | privacy |
|---|---|---|---|---|---|---|---|
| `parcel_id` | string | — | — | synthetic | synthetic | Synthetic parcel identifier | not personal |
| `building_id` | string | — | — | real | real (model-derived) | Microsoft building footprint id (context only, not ownership) | not personal |
| `overlap_fraction` | float | fraction 0–1 | EPSG:32644 | derived | derived | intersection_area / building area | not personal |
| `intersection_area_sqm` | float | m² | EPSG:32644 | derived | derived | Area of parcel ∩ building | not personal |
| `distance_m` | float | m | EPSG:32644 | derived | derived | 0 when intersecting; else parcel-to-building distance (≤10 m reported) | not personal |
| `relationship_type` | string | — | — | derived | derived | within_parcel | partial_overlap | crosses_boundary | adjacent_no_overlap | not personal |

Rows: **1750**. Buildings are Microsoft model predictions, not independently verified structures; they are context, never cadastral truth.

## inputs/utility_points.geojson and inputs/utility_lines.geojson

| field | type | units | CRS | source | status | generation rule | privacy |
|---|---|---|---|---|---|---|---|
| `utility_id` | string | — | — | synthetic | synthetic | Sequential SYN-UP-##### (points) / SYN-UL-##### (lines) | not personal |
| `department` | string | — | — | synthetic | synthetic | electricity | water | sewer | not personal |
| `connection_id` | string | — | — | synthetic | synthetic | Fictional service connection key | not personal |
| `synthetic` | boolean | — | — | synthetic | synthetic | Always true | not personal |
| `geometry` | Point / LineString | — | EPSG:4326 | synthetic | synthetic | Seeded jitter near a parcel; ~30% shifted toward a neighbour. Water lines reuse the existing fictional water fixture. | not personal |

The true serving parcel is stored only in `evaluation_only/utility_points_reference.geojson`.

## inputs/{department}_records.json

One file per department: revenue, municipal, electricity, water, sewer. Record IDs are random and never encode the target parcel. No file contains a `parcel_id` foreign key — the matcher must infer it.

| field | type | units | CRS | source | status | generation rule | privacy |
|---|---|---|---|---|---|---|---|
| `record_id` | string | — | — | synthetic | synthetic | Reused departmental record id (or generated for sewer/competing cases) | not personal |
| `department` | string | — | — | synthetic | synthetic | Fixed per file | not personal |
| `account_id` | string | — | — | synthetic | synthetic | Fictional department account key | not personal |
| `district` | string | — | — | synthetic | synthetic | As recorded; blank for missing-scope cases | not personal |
| `village` | string | — | — | synthetic | synthetic | As recorded; blank for missing-scope cases | not personal |
| `survey_number` | string | — | — | synthetic | synthetic | As recorded; may be blank, reformatted or wrong by scenario | not personal |
| `address` | string | — | — | synthetic | synthetic | Fictional plot/street address; may contain a typo | not personal |
| `record_date` | string | ISO date | — | synthetic | synthetic | Fixture date; pre-2020 for old_record | not personal |
| `easting_m / northing_m` | float | m | EPSG:32644 | synthetic | synthetic | Parcel reference point with jitter; null when geometry is missing | not personal |
| `crs` | string | — | — | synthetic | synthetic | Always EPSG:32644 | not personal |
| `synthetic` | boolean | — | — | synthetic | synthetic | Always true | not personal |
| `source` | string | — | — | synthetic | synthetic | Provenance string | not personal |
| `mandal (revenue)` | string | — | — | synthetic | synthetic | Parcel mandal | not personal |
| `survey_subdivision (revenue)` | string | — | — | synthetic | synthetic | Subdivision suffix | not personal |
| `recorded_area_sqm (revenue)` | float | m² | EPSG:32644 | synthetic | synthetic | Parcel area; inflated for area_error | not personal |
| `land_use (revenue)` | string | — | — | synthetic | synthetic | Parcel land use | not personal |
| `assessment_id (municipal)` | string | — | — | synthetic | synthetic | Fictional assessment key | not personal |
| `ward / door_number (municipal)` | string | — | — | synthetic | synthetic | Parcel ward and demo door number | not personal |
| `property_use (municipal)` | string | — | — | synthetic | synthetic | Parcel land use | not personal |
| `built_area_sqm (municipal)` | float | m² | EPSG:32644 | synthetic | synthetic | Parcel area × seeded 0.35–0.9 factor | not personal |
| `connection_id` | string | — | — | synthetic | synthetic | Fictional service connection key | not personal |
| `connection_status` | string | — | — | synthetic | synthetic | active for all generated records | not personal |
| `connection_date (electricity)` | string | ISO date | — | synthetic | synthetic | Mirrors record_date | not personal |
| `service_type` | string | — | — | synthetic | synthetic | water | sewer | not personal |

## evaluation_only/answers.json

| field | type | meaning |
|---|---|---|
| `record_id` | string | Operational record identifier |
| `expected_parcel_id` | string / null | True synthetic parcel; null when no parcel matches |
| `department` | string | Owning department |
| `scenario` | string | Controlled scenario label |
| `split` | string | development or test |
| `expected_matchable` | boolean | Whether a correct parcel exists at all |
| `notes` | string | Human-readable scenario explanation |

Also in evaluation_only/: `parcels_without_records.json` (parcels deliberately given no departmental record) and `utility_points_reference.geojson` (true serving parcel per utility point). These files must never be read by the matching engine.

## Scenario counts

| scenario | records |
|---|---:|
| `address_typo` | 126 |
| `area_error` | 131 |
| `clean_exact_match` | 137 |
| `duplicate_account` | 21 |
| `format_variation` | 126 |
| `identifier_only` | 127 |
| `missing_district_or_village` | 126 |
| `missing_geometry` | 133 |
| `missing_survey_identifier` | 130 |
| `multiple_accounts_one_parcel` | 57 |
| `old_record` | 135 |
| `record_competing_between_parcels` | 12 |
| `record_without_matching_parcel` | 50 |
| `shifted_location` | 133 |
| `wrong_identifier` | 136 |
