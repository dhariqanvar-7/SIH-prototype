# Kondapur real vector baseline

Study boundary: **78.350 west, 17.450 south, 78.364 east, 17.462 north**.
GeoJSON coordinates use longitude/latitude (EPSG:4326). Use **EPSG:32644**
(UTM zone 44N) for metric operations in this area. The existing synthetic
demo uses a different metric CRS. This dataset is now the default app workspace;
the earlier demo remains available from the dataset selector.

## Acquired baseline

Measured geodesic area: **1.975070 km²**. The download contains:

| Layer | Exported features |
|---|---:|
| Microsoft building footprints | 480 |
| OSM road/path ways | 251 |
| OSM land-use polygons | 6 |
| OSM amenities | 38 |
| OSM utility features | 13 |
| Other OSM context features | 20 |

71 buildings cross the study boundary and are retained whole. The 480 building
geometries have no exact duplicates after normalization. All exported features
have unique IDs within their layer, valid geometry and intersection with the AOI;
all recorded file hashes were independently checked after acquisition.

The OSM response reports a base timestamp of **2026-09-22T08:45:51Z**.
Two relations remain in the raw response rather than the converted exports.
The utility layer contains nine power towers, two power lines, one water-tower
feature and one wastewater-plant feature. This does not establish water, sewer
or other underground network coverage.

## Files

- `aoi.geojson`: selected study boundary.
- `buildings.geojson`: valid Microsoft footprints intersecting the boundary.
- `roads.geojson`: OSM highway ways, including paths and service roads.
- `landuse.geojson`, `amenities.geojson`, `other_features.geojson`: mapped OSM context.
- `utilities.geojson`: mapped power, pipelines, water infrastructure and drains where present.
- `buildings_invalid_candidates.geojson`: invalid Microsoft geometries whose bounding boxes intersect the AOI, quarantined for review.
- `osm_unconverted.json`: relations or other objects not converted; original content remains in the raw response.
- `raw/`: cached original index, footprint tile, OSM response, query and retrieval metadata.
- `manifest.json`: measured counts, source URLs, licenses, retrieval details and SHA-256 hashes.

Full intersecting geometries are retained to avoid cutting buildings or roads at
the boundary. Therefore some coordinates extend outside the AOI. Microsoft
footprints are model predictions, not independently verified buildings. The tile
upload date is not the date of its underlying imagery. Missing footprints do not
prove that buildings do not exist.

OSM data are community mapping, not authoritative municipal GIS. Road counts
count ways rather than named streets. OSM relations are preserved in the raw
response but are not assembled into polygons in these exports. Bounding-box
queries can omit a way that crosses the box with no vertex inside it. Features
are assigned to one thematic export, so the raw response is the complete source
for overlapping classifications. Mapped utility objects do not establish a
complete connected utility network; absence from OSM does not mean absence on
the ground.

## Sources and attribution

Microsoft GlobalMLBuildingFootprints: CDLA Permissive 2.0.
Source and license: https://github.com/microsoft/GlobalMLBuildingFootprints

© OpenStreetMap contributors. OpenStreetMap data are available under ODbL 1.0.
Attribution and license: https://www.openstreetmap.org/copyright
Keep attribution when displaying or redistributing these layers and review the
linked terms for derived databases. Microsoft and OSM exports remain separate.

## Reproduction

Run `python dataset/hyderabad_kondapur/acquire.py` with Python 3.11+,
Shapely and pyproj installed. The script reuses cached raw files and regenerates
derived exports. To acquire a new snapshot, use a new directory rather than
silently replacing the raw baseline. The Microsoft index is pinned to the
2026-08-13 release; OSM reflects the timestamp recorded in the response.

## Additional datasets

Satellite imagery and elevation rasters have now been acquired. Synthetic parcel,
revenue, survey, verification and utility fixtures are also available, with answer
keys separated from inputs. See [REMAINING_DATA.md](REMAINING_DATA.md) for files,
measured quality, source availability checks and limitations. Real cadastral
exports and field/CORS observations remain unconfirmed or unacquired; the
synthetic files are explicit substitutes. Drone imagery remains excluded.
