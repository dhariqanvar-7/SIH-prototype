# Remaining datasets: acquired and prepared

Study area: Kondapur, Hyderabad; west 78.350, south 17.450, east 78.364,
north 17.462. Acquisition performed 24 September 2026.

## Real downloaded rasters

| File | Contents | Resolution / grid |
|---|---|---|
| `rasters/imagery_rgbnir_10m.tif` | Sentinel-2 L2A red, green, blue and near-infrared bands | 10 m; 152 × 136; EPSG:32644 |
| `rasters/imagery_truecolor_10m.tif` | Display-ready true colour image | 10 m; EPSG:32644 |
| `rasters/scene_classification_20m.tif` | Sentinel-2 scene quality classification | 20 m; EPSG:32644 |
| `rasters/sentinel_*_10m.tif` | Individual spectral bands | 10 m; EPSG:32644 |
| `rasters/surface_elevation_glo30.tif` | Copernicus GLO-30 surface elevations | Approximately 30 m (1 arcsecond); 51 × 44; EPSG:4326 |

The selected scene is **S2B_T44QKE_20251213T052354_L2A**, acquired
**13 December 2025**. All AOI pixel centres have valid imagery and elevation
values. Its 20 m scene-classification mask contains no pixels classified as
cloud, cloud shadow, cirrus, snow, defective or no-data inside the AOI. This is
an automated quality check, not field validation. The search used the dry-season
November 2025–March 2026 window; the scene is not claimed to be the latest image.

The GeoTIFFs retain native grids, with pixel centres outside the boundary masked.
The four-band file stores source digital numbers: **reflectance = DN × 0.0001
− 0.1**, excluding no-data values. Scale and offset are embedded per band.
The true-colour file is for display, not quantitative reflectance calculations.

Elevation ranges from approximately **588.25 to 621.70 metres**, relative to
EGM2008. This is a surface model (DSM), **not a bare-earth DTM**. Its pixel
spacing is insufficient for individual-building heights. Likewise, 10 m satellite
imagery is context imagery, not a high-resolution cadastral orthophoto.
Footprint imagery dates are unknown, so cross-source differences do not establish
building construction or demolition dates.

Sources: [Earth Search / Element 84](https://github.com/Element84/earth-search),
[Copernicus DEM on AWS](https://registry.opendata.aws/copernicus-dem/).
Saved catalogue responses and selected-scene metadata are in `raw/`.
`rasters/manifest.json` records source asset URLs, crop quality and SHA-256 hashes.
Only required image blocks were downloaded using range requests; whole satellite
tiles were not copied locally.

## Availability checks and explicit substitutions

| Required layer | Finding | Provided substitute |
|---|---|---|
| Cadastral boundaries | Official Bhu Bharati GIS page was reachable. Public HTML has commented-out import/export controls. No supported reusable parcel export or redistribution terms were confirmed in this check. This does not prove that data cannot be obtained from the department. | 300 synthetic parcels |
| Revenue records | No personal ownership records acquired; fictional records were the agreed benchmark plan. | 300 fictional records |
| Official municipal GIS | No downloadable official AOI dataset confirmed. Existing OSM context is community mapping, not municipal authority data. | Existing real OSM roads, land use and amenities |
| Utility networks | Existing OSM extract has 13 real mapped objects, not comprehensive water/sewer topology. | A separate 60-segment synthetic water-network fixture |
| GNSS/CORS observations | Survey of India publishes registration/download procedures. No registered session or AOI field survey data available. Reference-station data alone would not establish parcel control points. | 30 simulated coordinate observations, not RINEX |
| Ground truth | No field visit or independent high-resolution imagery validation conducted. | 300 explicitly simulated verification records |
| Drone imagery | Excluded by project scope. | None |

Checks used the [Bhu Bharati GIS](https://bhubharati.telangana.gov.in/gis/),
[Bhuvan resource portal](https://bhuvanlite.nrsc.gov.in/kyrdemo/) and
[Survey of India CORS procedures](https://surveyofindia.gov.in/pages/continuously-operating-reference-stations-cors-).
The saved Bhu Bharati HTML/client files document the public-page inspection;
no owner records were collected. No claim of an exhaustive government-data search
or legal restriction is made.

## Synthetic benchmark files

`synthetic_benchmark/inputs/` contains:

- `parcels.geojson`: 300 invented parcel geometries with synthetic survey numbers.
- `revenue_records.csv`: 300 fictional owner IDs, areas and land-use attributes.
- `ground_truth_observations.csv`: 300 simulated verification records, explicitly not field verified.
- `gnss_observations.csv`: 30 simulated positional observations, with per-axis noise specifications.
- `utility_network_synthetic.geojson`: 60 fictional water-network segments.

Parcel cells are generated around representative points from 300 real interior
building footprints, cropped to the AOI and cut by **assumed**, not measured,
road buffers. These are simplified test cells, not recovered property boundaries.
They can split buildings or include multiple buildings. The fictional utility grid
does not follow actual pipes or road alignments.

Controlled errors: **30 parcels shifted by +5 m east / −3 m north** and
**20 revenue areas inflated by 20%**. Some cases overlap. Expected answers,
reference parcels, simulated control coordinates and 977 reference building/parcel
intersection pairs are in `synthetic_benchmark/evaluation_only/`. The pairs are
geometric intersections with invented parcels, not verified cadastral associations.
Keep this folder out of the matching engine's input.

The fixed generation seed is 20260924. The generator refuses to overwrite an
existing benchmark. No split/merge or temporal demolition/new-building benchmark
has been created in this acquisition step.

## Attribution, validation and use

Contains modified Copernicus Sentinel data (2025). Sentinel data terms:
https://dataspace.copernicus.eu/terms-and-conditions

Copernicus DEM usage is subject to its own licence, linked by the AWS registry:
https://registry.opendata.aws/copernicus-dem/

Microsoft source footprints retain CDLA Permissive 2.0 provenance. Road-derived
synthetic geometry also uses OpenStreetMap data: © OpenStreetMap contributors,
ODbL 1.0. See https://www.openstreetmap.org/copyright . Synthetic labels do not
remove upstream attribution or licence obligations.

Geometry validity, unique feature identifiers, synthetic labels, record links,
raster spatial metadata, finite data values and all manifest hashes were checked.
Results are saved in `validation_remaining.json`. A native-resolution satellite
preview is provided as `rasters/imagery_preview.png` and was visually inspected.

The application now loads this dataset by default, displays the imagery and
elevation overlays, and uses EPSG:32644 for metric processing. Synthetic answer
keys remain outside the app input pipeline. The legacy demo is selectable separately.
