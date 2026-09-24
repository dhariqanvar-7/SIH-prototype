from pathlib import Path
import json
import tempfile
import geopandas as gpd
from shapely.geometry import box
from pipeline import run, normalize_id, compare_dates
from review import ReviewStore, export_geojson

ROOT = Path(__file__).resolve().parents[1]

def test_ids():
    assert {normalize_id(x) for x in ['P-023','023','P / 023']} == {'P-023'}
    assert normalize_id('invalid23text') is None

def test_spatial_changes_ignore_identifiers():
    a = gpd.GeoDataFrame({'extracted_id':['a','b','c']},geometry=[box(0,0,10,10),box(30,0,40,10),box(60,0,70,10)],crs=32643)
    b = gpd.GeoDataFrame({'extracted_id':['x','y','z']},geometry=[box(0,0,10,10),box(30,0,44,10),box(100,0,110,10)],crs=32643)
    changes = compare_dates(a,b)
    assert set(changes.change)=={'stable','extended','removed','added'}

def test_end_to_end_and_review_persistence(tmp_path):
    # A dataset containing only inputs + metadata must run without the answer key.
    import shutil
    shutil.copytree(ROOT/'dataset/inputs',tmp_path/'inputs')
    shutil.copy2(ROOT/'dataset/manifest.json',tmp_path/'manifest.json')
    result = run(tmp_path)
    assert len(result['originals']['parcels'])==100
    assert (~result['validation'].valid).sum()==3
    assert len(result['links'])==194
    assert result['quarantine']
    repair = next(p for p in result['proposals'] if p['kind']=='repair')
    store = ReviewStore(tmp_path/'reviews.sqlite')
    baseline = json.loads(export_geojson(result,{}))
    store.save(result['fingerprint'],repair['proposal_id'],'accepted','Test')
    reopened = ReviewStore(tmp_path/'reviews.sqlite')
    decisions = reopened.decisions(result['fingerprint'])
    accepted = json.loads(export_geojson(result,decisions))
    idx = next(i for i,f in enumerate(accepted['features']) if f['properties']['parcel_id']==repair['feature_id'])
    assert accepted['features'][idx]['properties']['geometry_status']=='accepted_repair'
    assert baseline['features'][idx]['geometry']!=accepted['features'][idx]['geometry']
    store.save(result['fingerprint'],repair['proposal_id'],'rejected','Test')
    assert json.loads(export_geojson(result,store.decisions(result['fingerprint'])))==baseline
    assert store.decisions('changed-dataset')=={}
    assert len(store.audit(result['fingerprint']))==2

def test_metadata_hashes_and_original_inputs():
    from generate_dataset import content_hash
    manifest = json.loads((ROOT/'dataset/manifest.json').read_text())
    old = json.loads((ROOT/'backups/pre-mvp/manifest.json').read_text())
    before = {e['path']:e for e in old['files']}
    for entry in manifest['files']:
        assert content_hash(ROOT/'dataset'/entry['path'])==entry['sha256_canonical']
        if entry['path'].startswith('inputs'):
            assert entry['sha256_canonical']==before[entry['path']]['sha256_canonical']
