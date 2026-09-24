import json
import shutil
from pathlib import Path
import numpy as np
from data_sources import KONDAPUR_INPUTS
from pipeline import run, fingerprint
from raster_layers import overlay
from review import export_geojson
from evaluate import evaluate

ROOT = Path(__file__).resolve().parents[1]/'dataset/hyderabad_kondapur'


def test_new_dataset_without_answers_and_export_provenance(tmp_path):
    for relative in KONDAPUR_INPUTS:
        target = tmp_path/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/relative,target)
    result = run(tmp_path)
    assert len(result['layers']['parcels']) == 300
    assert len(result['layers']['buildings']) == 480
    assert len(result['links']) == 300
    assert len(result['departments']['results'])==1610
    assert result['departments']['stats']['candidate_pairs']<10000
    assert 'expected_parcel_id' not in next(iter(result['departments']['records'].values()))
    assert result['metric_crs'] == 'EPSG:32644'
    assert all(str(g.crs) == 'EPSG:32644' for g in result['layers'].values())
    assert result['changes'].empty and not result['temporal_available']
    assert not any(p['kind']=='change' for p in result['proposals'])
    assert result['conflicts'].kind.eq('area_disagreement').sum() == 20
    link = next(p for p in result['proposals'] if p['kind']=='record_link')
    exported = json.loads(export_geojson(result,{link['proposal_id']:'accepted'}))
    parcel = next(f for f in exported['features'] if f['properties']['parcel_id']==link['target_id'])
    assert parcel['properties']['synthetic']
    assert parcel['properties']['source']=='synthetic_benchmark/inputs/parcels.geojson'
    assert json.loads(parcel['properties']['accepted_links'])[0]['feature_id']==link['feature_id']
    before = fingerprint(tmp_path)
    (tmp_path/'evaluation_only').mkdir()
    (tmp_path/'evaluation_only/answer.json').write_text('{"ignored":true}')
    assert fingerprint(tmp_path)==before
    path = tmp_path/'synthetic_benchmark/inputs/revenue_records.csv'
    path.write_text(path.read_text()+'\n')
    assert fingerprint(tmp_path)!=before


def test_raster_overlays_preserve_geographic_extent_and_transparency():
    for name,elevation in [('imagery_truecolor_10m.tif',False),('surface_elevation_glo30.tif',True)]:
        rgba,bounds,note=overlay(ROOT/'rasters'/name,elevation)
        assert rgba.shape[2]==4 and rgba.dtype==np.uint8
        assert rgba[:,:,3].max()==255 and rgba[:,:,3].min()==0
        assert bounds[0][0] <= 17.45 and bounds[1][0] >= 17.462
        assert bounds[0][1] <= 78.35 and bounds[1][1] >= 78.364
        assert note


def test_synthetic_evaluation_is_explicit_and_detects_injected_areas():
    metrics=evaluate(run(ROOT),ROOT)
    assert metrics['correct_record_links']==300
    assert metrics['area_mismatch_true_positives']==20
    assert metrics['area_mismatch_false_positives']==0
    assert metrics['area_mismatch_false_negatives']==0
