import json
import shutil
from pathlib import Path

from data_sources import INTEGRATED_INPUTS
from pipeline import fingerprint, run
from review import effective_decisions, export_geojson


SOURCE = Path(__file__).resolve().parents[1] / 'dataset/hyderabad_kondapur'


def test_integrated_workspace_uses_inputs_without_answer_keys(tmp_path):
    for relative in INTEGRATED_INPUTS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / relative, target)
    package = tmp_path / 'synthetic_integrated_v1'
    result = run(package)

    assert len(result['originals']['parcels']) == 300
    assert len(result['departments']['results']) == 1580
    assert set(result['departments']['records'][rid]['department']
               for rid in result['departments']['records']) == {
                   'revenue', 'municipal', 'electricity', 'water', 'sewer'}
    assert result['departments']['stats']['candidate_pairs'] < 10000
    assert not any('parcel_id' in r for r in result['departments']['records'].values())
    assert len(result['layers']['utility_points']) == 900
    assert len(result['layers']['utility_lines']) == 140
    assert not result['utility_evidence'].empty
    assert len(result['links']) == 0  # No direct parcel IDs were supplied by departments.
    assert result['parcel_source'] == 'synthetic_integrated_v1/inputs/parcels.geojson'

    decisions = effective_decisions(result['proposals'], {})
    assert sum(v == 'auto_approved' for v in decisions.values()) < 1014
    assert all(p['proposal_id'] not in decisions for p in result['departments']['proposals']
               if p.get('same_type_record_ids') and p['candidate_rank'] == 1)
    first = next(p for p in result['proposals']
                 if decisions.get(p['proposal_id']) == 'auto_approved')
    decisions[first['proposal_id']] = 'rejected'
    assert first['proposal_id'] not in {
        link['proposal_id'] for feature in json.loads(export_geojson(result, decisions))['features']
        for link in json.loads(feature['properties']['accepted_links'])}

    before = fingerprint(package)
    (package / 'evaluation_only').mkdir()
    (package / 'evaluation_only/answers.json').write_text('[]')
    assert fingerprint(package) == before
