"""Explicit dataset adapters. Never read evaluation_only files."""
import json
from pathlib import Path
import geopandas as gpd
import pandas as pd

KONDAPUR_INPUTS = [
    'departmental/inputs/parcel_directory.json', 'departmental/inputs/records.json',
    'aoi.geojson', 'buildings.geojson', 'roads.geojson', 'landuse.geojson',
    'amenities.geojson', 'utilities.geojson', 'other_features.geojson',
    'synthetic_benchmark/inputs/parcels.geojson',
    'synthetic_benchmark/inputs/revenue_records.csv',
    'synthetic_benchmark/inputs/ground_truth_observations.csv',
    'synthetic_benchmark/inputs/gnss_observations.csv',
    'synthetic_benchmark/inputs/utility_network_synthetic.geojson',
    'rasters/manifest.json', 'rasters/imagery_truecolor_10m.tif',
    'rasters/surface_elevation_glo30.tif',
]

INTEGRATED_INPUTS = [
    'synthetic_integrated_v1/inputs/parcels.geojson',
    'synthetic_integrated_v1/inputs/revenue_records.json',
    'synthetic_integrated_v1/inputs/municipal_records.json',
    'synthetic_integrated_v1/inputs/electricity_records.json',
    'synthetic_integrated_v1/inputs/water_records.json',
    'synthetic_integrated_v1/inputs/sewer_records.json',
    'synthetic_integrated_v1/inputs/utility_points.geojson',
    'synthetic_integrated_v1/inputs/utility_lines.geojson',
    'aoi.geojson', 'buildings.geojson', 'roads.geojson', 'landuse.geojson',
    'amenities.geojson', 'utilities.geojson', 'other_features.geojson',
    'synthetic_benchmark/inputs/ground_truth_observations.csv',
    'synthetic_benchmark/inputs/gnss_observations.csv',
    'rasters/manifest.json', 'rasters/imagery_truecolor_10m.tif',
    'rasters/surface_elevation_glo30.tif',
]


def is_kondapur(root):
    return (Path(root)/'aoi.geojson').exists()


def is_integrated(root):
    root = Path(root)
    return (root/'inputs/parcels.geojson').exists() and (root.parent/'aoi.geojson').exists()


def load_kondapur(root, integrated_package=None):
    root = Path(root)
    base = root/'synthetic_benchmark/inputs'
    integrated = integrated_package is not None
    package = Path(integrated_package) if integrated else None
    frames = {}
    paths = {'parcels': (package/'inputs/parcels.geojson' if integrated else base/'parcels.geojson'),
             'buildings': root/'buildings.geojson',
             'roads': root/'roads.geojson', 'landuse': root/'landuse.geojson',
             'amenities': root/'amenities.geojson', 'utilities': root/'utilities.geojson',
             'other_features': root/'other_features.geojson'}
    if integrated:
        paths.update(utility_points=package/'inputs/utility_points.geojson',
                     utility_lines=package/'inputs/utility_lines.geojson')
    else:
        paths['synthetic_utilities'] = base/'utility_network_synthetic.geojson'
    for name, path in paths.items():
        frames[name] = gpd.read_file(path)
    if not integrated:
        directory = pd.read_json(root/'departmental/inputs/parcel_directory.json')
        # Retain the old fixture reference while displaying the departmental registry
        # fields that the matcher actually compares. Original files are untouched.
        frames['parcels'] = frames['parcels'].rename(columns={'survey_number':'fixture_survey_number'}).merge(
            directory[['parcel_id','district','village','survey_number','address']],on='parcel_id',validate='one_to_one')
    frames['buildings']['extracted_id'] = frames['buildings']['id']
    observations = pd.read_csv(base/'ground_truth_observations.csv')
    observations['observed_use'] = observations.observed_land_use
    frames['observations'] = gpd.GeoDataFrame(observations,
        geometry=gpd.points_from_xy(observations.longitude, observations.latitude), crs=4326)
    gnss = pd.read_csv(base/'gnss_observations.csv')
    if set(gnss.crs) != {'EPSG:32644'}:
        raise ValueError('Unconfirmed GNSS coordinate reference system')
    gnss = gpd.GeoDataFrame(gnss, geometry=gpd.points_from_xy(gnss.easting_m, gnss.northing_m), crs=32644)
    records = pd.DataFrame() if integrated else pd.read_csv(base/'revenue_records.csv', dtype=str, keep_default_na=False)
    provenance = [
        ('parcels', 'Synthetic', 'Invented test parcels; 30 have controlled displacements'),
        ('buildings', 'Real · model-derived', 'Microsoft footprints; imagery dates unknown'),
        ('roads', 'Real · community mapped', 'OpenStreetMap road and path segments'),
        ('landuse', 'Real · community mapped', 'OpenStreetMap land use'),
        ('amenities', 'Real · community mapped', 'OpenStreetMap amenities'),
        ('utilities', 'Real · incomplete', '13 mapped OSM utility objects; not a complete network'),
        ('other_features', 'Real · community mapped', 'Other OpenStreetMap context'),
        ('synthetic_utilities', 'Synthetic', 'Fictional water network; no actual pipe alignment'),
        ('observations', 'Simulated', 'Not field verified'),
        ('gnss', 'Simulated', 'Coordinate observations, not a real GNSS/CORS survey'),
    ]
    if integrated:
        provenance = [row for row in provenance if row[0] != 'synthetic_utilities']
        provenance.extend([
            ('utility_points', 'Synthetic', 'Fictional electricity, water and sewer service points'),
            ('utility_lines', 'Synthetic', 'Fictional electricity, water and sewer lines'),
            ('department_records', 'Synthetic', '1,580 fictional records across five departments'),
        ])
    labels = {name: f'{name.replace("_", " ").title()} · {kind}' for name, kind, _ in provenance}
    return dict(frames=frames, gnss=gnss, records=records, labels=labels,
                provenance=pd.DataFrame(provenance, columns=['layer','data_type','description']),
                raster_metadata=json.loads((root/'rasters/manifest.json').read_text()),
                raster_paths={name: str(root/'rasters'/filename) for name, filename in
                    [('Satellite imagery','imagery_truecolor_10m.tif'), ('Surface elevation','surface_elevation_glo30.tif')]})
