"""Crop public Sentinel-2 and Copernicus DEM COGs using HTTP range reads.

Requires rasterio, numpy, shapely, pyproj. Uses the saved catalogue responses.
"""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds, Window
from rasterio.warp import transform_bounds, transform_geom
from rasterio.features import geometry_mask
from shapely.geometry import shape, box, mapping

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'rasters'
OUT.mkdir(exist_ok=True)
BBOX = [78.350, 17.450, 78.364, 17.462]
AOI = box(*BBOX)


def crop(url, name):
    print('Reading AOI pixels:', name, flush=True)
    with rasterio.open(url) as src:
        bounds = transform_bounds('EPSG:4326', src.crs, *BBOX, densify_pts=21)
        w = from_bounds(*bounds, transform=src.transform)
        left, top = math.floor(w.col_off), math.floor(w.row_off)
        right, bottom = math.ceil(w.col_off + w.width), math.ceil(w.row_off + w.height)
        window = Window(left, top, right-left, bottom-top)
        assert left >= 0 and top >= 0 and right <= src.width and bottom <= src.height
        data = src.read(window=window)
        transform = src.window_transform(window)
        inside = geometry_mask([transform_geom('EPSG:4326', src.crs, mapping(AOI))],
                               out_shape=data.shape[1:], transform=transform, invert=True)
        nodata = src.nodata if src.nodata is not None else -9999
        data[:, ~inside] = nodata
        profile = dict(driver='GTiff', height=data.shape[1], width=data.shape[2],
                       count=src.count, dtype=src.dtypes[0], crs=src.crs, transform=transform,
                       nodata=nodata, compress='deflate')
        with rasterio.open(OUT / name, 'w', **profile) as dst:
            dst.write(data)
            dst.update_tags(source_url=url, synthetic='false')
        valid = inside & np.all(np.isfinite(data) & (data != nodata), axis=0)
        result = {'source_url': url, 'crs': str(src.crs), 'resolution': list(src.res),
                  'width': profile['width'], 'height': profile['height'], 'bands': src.count,
                  'nodata': nodata, 'valid_aoi_fraction': float(valid.sum()/inside.sum())}
        return data, profile, inside, result


def main():
    features = json.loads((ROOT/'raw/sentinel_search.json').read_text(encoding='utf-8-sig'))['features']
    candidates = sorted([f for f in features if f['properties'].get('proj:epsg') == 32644
                         and shape(f['geometry']).covers(AOI)], key=lambda f:f['properties']['eo:cloud_cover'])
    assert candidates, 'No candidate scene fully covers AOI'
    attempts = []
    for scene in candidates[:5]:
        scl_key = 'scl' if 'scl' in scene['assets'] else next(k for k,v in scene['assets'].items() if 'SCL' in v['href'])
        scl, scl_profile, inside, scl_meta = crop(scene['assets'][scl_key]['href'], 'scene_classification_20m.tif')
        bad = np.isin(scl[0], [0,1,3,8,9,10,11]) & inside
        bad_fraction = float(bad.sum()/inside.sum())
        attempts.append({'id':scene['id'], 'bad_scl_aoi_fraction':bad_fraction})
        if bad_fraction <= .01:
            break
    else:
        raise RuntimeError('No sufficiently clear AOI found in first five candidates')
    (ROOT/'raw/sentinel_selected_item.json').write_text(json.dumps(scene,indent=2), encoding='utf-8')
    scl_counts = {str(int(v)): int(n) for v,n in zip(*np.unique(scl[0][inside], return_counts=True))}
    outputs = {'scene_classification_20m.tif': scl_meta}
    bands = []
    reference = None
    for band in ['red','green','blue','nir']:
        asset = scene['assets'][band]
        data, profile, _, meta = crop(asset['href'], f'sentinel_{band}_10m.tif')
        if reference is not None:
            assert profile['transform'] == reference['transform'] and data.shape == bands[0].shape
        reference = profile
        rb = asset['raster:bands'][0]
        with rasterio.open(OUT/f'sentinel_{band}_10m.tif', 'r+') as dst:
            dst.scales = (rb.get('scale',1),)
            dst.offsets = (rb.get('offset',0),)
            dst.set_band_description(1, band)
        meta.update(scale=rb.get('scale',1), offset=rb.get('offset',0))
        assert meta['valid_aoi_fraction'] == 1, f'Missing {band} pixels'
        outputs[f'sentinel_{band}_10m.tif'] = meta
        bands.append(data)
    profile = dict(reference, count=4)
    with rasterio.open(OUT/'imagery_rgbnir_10m.tif','w',**profile) as dst:
        dst.write(np.concatenate(bands,axis=0))
        dst.scales = tuple(outputs[f'sentinel_{b}_10m.tif']['scale'] for b in ['red','green','blue','nir'])
        dst.offsets = tuple(outputs[f'sentinel_{b}_10m.tif']['offset'] for b in ['red','green','blue','nir'])
        dst.descriptions = ('red','green','blue','nir')
        dst.update_tags(scene_id=scene['id'], acquisition_datetime=scene['properties']['datetime'],
                        attribution='Contains modified Copernicus Sentinel data (2025)', synthetic='false')
    _, _, _, meta = crop(scene['assets']['visual']['href'], 'imagery_truecolor_10m.tif')
    outputs['imagery_truecolor_10m.tif'] = meta
    dem = json.loads((ROOT/'raw/dem_search.json').read_text(encoding='utf-8-sig'))['features'][0]
    url = dem['assets']['data']['href'].replace('s3://copernicus-dem-30m/', 'https://copernicus-dem-30m.s3.amazonaws.com/')
    data, profile, inside, meta = crop(url, 'surface_elevation_glo30.tif')
    assert meta['valid_aoi_fraction'] == 1, 'Missing elevation pixels'
    values = data[0][inside]
    meta.update(min_m=float(values.min()), max_m=float(values.max()),
                surface_model='DSM, not bare-earth DTM', vertical_datum='EGM2008 orthometric height',
                source_release='AWS Copernicus DEM 2021 release', nominal_resolution_m=30)
    outputs['surface_elevation_glo30.tif'] = meta
    report = {'retrieved_at_utc':datetime.now(timezone.utc).isoformat(), 'bbox_wsen':BBOX,
              'scene_id':scene['id'], 'acquisition_datetime':scene['properties']['datetime'],
              'scene_cloud_percent':scene['properties']['eo:cloud_cover'],
              'selection_attempts':attempts,
              'selection_note':'Lowest scene cloud score among first catalogue page of dry-season 2025-11 through 2026-03 scenes in EPSG:32644 covering AOI; AOI quality independently checked with SCL.',
              'bad_scl_aoi_fraction':bad_fraction,
              'scl_classes':scl_counts,
              'processing':'Native pixel grids retained, exterior pixel centers masked. No upsampling. Physical reflectance = DN * scale + offset; nodata excluded.',
              'outputs':outputs,
              'sources':{'sentinel':'https://github.com/Element84/earth-search',
                         'dem':'https://registry.opendata.aws/copernicus-dem/'},
              'limitations':['10 m imagery cannot validate individual cadastral/building boundaries.',
                             '30 m DSM cannot provide reliable individual building heights.',
                             'Dates differ from footprint imagery whose acquisition dates are unknown.'], 'files':{}}
    for path in sorted(OUT.glob('*.tif')):
        with path.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
        report['files'][path.name]={'bytes':path.stat().st_size,'sha256':digest}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'scene':report['scene_id'],'bad_scl_fraction':bad_fraction,'elevation':meta,'files':list(report['files'])},indent=2),flush=True)


if __name__ == '__main__':
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', GDAL_HTTP_TIMEOUT='60',
                      GDAL_HTTP_MAX_RETRY='2', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif'):
        main()
