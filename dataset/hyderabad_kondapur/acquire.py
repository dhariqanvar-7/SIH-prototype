"""Acquire the real vector baseline. Requires shapely and pyproj.

Run from any directory. Raw downloads are cached; derived files are reproducible.
The original synthetic demo dataset is not modified.
"""
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from shapely.geometry import shape, mapping, box, Point, LineString, Polygon
from pyproj import Geod

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
RAW.mkdir(exist_ok=True)
BBOX = [78.350, 17.450, 78.364, 17.462]
AOI = box(*BBOX)
INDEX = 'https://bfppub.blob.core.windows.net/%24web/2026-08-13/dataset-links.csv'


def fetch(url, path, data=None):
    if not path.exists():
        print('Downloading', url, flush=True)
        request = Request(url, data=data, headers={'User-Agent': 'BhuSetu-research-prototype/1.0'})
        partial = path.with_suffix(path.suffix + '.partial')
        with urlopen(request, timeout=150) as response, partial.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        partial.replace(path)
        path.with_suffix(path.suffix + '.source.json').write_text(json.dumps({
            'url': url, 'retrieved_at_utc': datetime.now(timezone.utc).isoformat()
        }, indent=2), encoding='utf-8')
    return path


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2), encoding='utf-8')


def collection(features):
    return {'type': 'FeatureCollection', 'features': features}


def quadkey(lon, lat):
    x = int((lon + 180) / 360 * 512)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 512)
    return ''.join(str(((x >> i) & 1) + 2 * ((y >> i) & 1)) for i in range(8, -1, -1))


def main():
    save('aoi.geojson', collection([{'type': 'Feature', 'properties': {
        'name': 'Kondapur, Hyderabad', 'bbox_order': 'west,south,east,north',
        'metric_crs': 'EPSG:32644'}, 'geometry': mapping(AOI)}]))
    index_path = fetch(INDEX, RAW / 'microsoft_dataset_links.csv')
    keys = {quadkey(x, y) for x in (BBOX[0], BBOX[2]) for y in (BBOX[1], BBOX[3])}
    rows = [row for row in csv.DictReader(index_path.read_text(encoding='utf-8-sig').splitlines())
            if row['Location'] == 'India' and row['QuadKey'] in keys]
    assert {row['QuadKey'] for row in rows} == keys, 'Missing Microsoft tiles'
    buildings, rejected = [], []
    scanned = 0
    for row in rows:
        path = fetch(row['Url'], RAW / f"microsoft_{row['QuadKey']}.geojsonl.gz")
        with gzip.open(path, 'rt', encoding='utf-8') as source:
            for number, line in enumerate(source, 1):
                feature = json.loads(line)
                geometry = shape(feature['geometry'])
                scanned += 1
                if not geometry.envelope.intersects(AOI):
                    continue
                feature['properties'] = dict(feature.get('properties') or {})
                feature['properties'].update(source='Microsoft GlobalMLBuildingFootprints', synthetic=False,
                    source_quadkey=row['QuadKey'], source_line=number)
                feature['id'] = f"MS-{row['QuadKey']}-{number}"
                if not geometry.is_valid:
                    rejected.append(feature)
                elif geometry.intersects(AOI):
                    feature['properties']['crosses_aoi_boundary'] = not AOI.covers(geometry)
                    buildings.append(feature)
    save('buildings.geojson', collection(buildings))
    save('buildings_invalid_candidates.geojson', collection(rejected))
    print('Microsoft buildings:', len(buildings), flush=True)

    bbox = ','.join(map(str, [BBOX[1], BBOX[0], BBOX[3], BBOX[2]]))
    query = '[out:json][timeout:90];(' + ''.join(
        f'nwr["{key}"]({bbox});' for key in
        ['highway', 'landuse', 'amenity', 'leisure', 'natural', 'waterway', 'power', 'pipeline', 'man_made', 'boundary']) + ');out body geom;'
    (RAW / 'osm_query.overpass').write_text(query, encoding='utf-8')
    osm_path = RAW / 'osm_response.json'
    errors = []
    for endpoint in ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']:
        try:
            fetch(endpoint, osm_path, urlencode({'data': query}).encode())
            osm = json.loads(osm_path.read_text(encoding='utf-8'))
            if 'remark' in osm:
                raise RuntimeError(osm['remark'])
            break
        except Exception as exc:
            errors.append(str(exc))
    else:
        raise RuntimeError('OSM acquisition incomplete: ' + '; '.join(errors))

    layers = {key: [] for key in ['roads', 'landuse', 'amenities', 'utilities', 'other_features']}
    unconverted = []
    for element in osm['elements']:
        tags = element.get('tags', {})
        if element['type'] == 'node':
            geometry = Point(element['lon'], element['lat'])
        elif element['type'] == 'way' and len(element.get('geometry', [])) >= 2:
            coords = [(point['lon'], point['lat']) for point in element['geometry']]
            area = coords[0] == coords[-1] and len(coords) >= 4 and tags.get('area') != 'no' and (
                tags.get('area') == 'yes' or any(key in tags for key in ['landuse', 'amenity', 'leisure'])
                or tags.get('natural') in ['water', 'wood', 'scrub', 'grassland', 'wetland']
                or tags.get('power') in ['substation', 'plant'])
            geometry = Polygon(coords) if area else LineString(coords)
        else:
            unconverted.append({'type': element['type'], 'id': element['id'], 'reason': 'relation or missing geometry; retained in raw response'})
            continue
        if not geometry.is_valid:
            unconverted.append({'type': element['type'], 'id': element['id'], 'reason': 'invalid geometry; retained in raw response'})
            continue
        if not geometry.intersects(AOI):
            continue
        properties = dict(tags, source='OpenStreetMap', synthetic=False, osm_type=element['type'], osm_id=element['id'])
        feature = {'type': 'Feature', 'id': f"{element['type']}/{element['id']}",
                   'properties': properties, 'geometry': mapping(geometry)}
        if 'highway' in tags and element['type'] == 'way':
            layer = 'roads'
        elif 'power' in tags or 'pipeline' in tags or tags.get('man_made') in ['pipeline', 'water_tower', 'water_works', 'wastewater_plant'] or tags.get('waterway') in ['drain', 'ditch']:
            layer = 'utilities'
        elif 'landuse' in tags:
            layer = 'landuse'
        elif 'amenity' in tags:
            layer = 'amenities'
        else:
            layer = 'other_features'
        layers[layer].append(feature)
    for name, features in layers.items():
        save(name + '.geojson', collection(features))
    save('osm_unconverted.json', unconverted)
    area = abs(Geod(ellps='WGS84').geometry_area_perimeter(AOI)[0]) / 1e6
    manifest = {
        'aoi': 'Kondapur, Hyderabad', 'bbox_wsen': BBOX, 'area_km2': area,
        'geometry_crs': 'EPSG:4326', 'metric_crs': 'EPSG:32644',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'selection': 'Full valid geometries intersecting AOI; boundary-crossing features are not clipped.',
        'microsoft': {'index_url': INDEX, 'tiles': rows, 'license': 'CDLA-Permissive-2.0',
            'scanned': scanned, 'buildings': len(buildings), 'invalid_bbox_candidates': len(rejected),
            'imagery_acquisition_date': 'unknown; upload date is not imagery acquisition date'},
        'osm': {'license': 'ODbL-1.0', 'attribution': '© OpenStreetMap contributors',
            'copyright_url': 'https://www.openstreetmap.org/copyright',
            'snapshot': osm.get('osm3s', {}), 'counts': {key: len(value) for key, value in layers.items()},
            'unconverted_count': len(unconverted), 'limitations': 'Relations retained only in raw response. Utilities are mapped features, not a complete connected network. Road counts are OSM ways, not unique named roads.'},
        'pending': ['satellite imagery', 'elevation raster', 'cadastral availability check', 'synthetic revenue, survey and evaluation layers'],
        'excluded': ['drone imagery'],
        'files': {}
    }
    for path in sorted(ROOT.rglob('*')):
        if path.is_file() and path.name not in ['manifest.json', 'README.md', 'acquire.py'] and not path.name.endswith('.partial'):
            manifest['files'][path.relative_to(ROOT).as_posix()] = {'bytes': path.stat().st_size, 'sha256': hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()}
    save('manifest.json', manifest)
    print(json.dumps({'area_km2': area, 'buildings': len(buildings), 'osm_counts': manifest['osm']['counts'], 'unconverted': len(unconverted)}, indent=2), flush=True)


if __name__ == '__main__':
    main()
