import copy
import json
from pathlib import Path
from shapely.geometry import box
from entity_resolution import Resolver, survey_key
from departmental import run_departments
from review import ReviewStore


def parcels():
    return [dict(parcel_id='A',district='D',village='V',survey_number='12/A',address='Plot 1 Alpha Street',geometry=box(0,0,10,10)),
            dict(parcel_id='B',district='D',village='V',survey_number='12/B',address='Plot 2 Beta Street',geometry=box(15,0,25,10)),
            dict(parcel_id='C',district='D',village='OTHER',survey_number='12/A',address='Plot 1 Alpha Street',geometry=box(100,0,110,10))]


def record(**updates):
    return dict(dict(record_id='R',department='municipal',account_id='ACCOUNT',district='D',village='V',
        survey_number='12/A',address='Plot 1 Alpha St.',easting_m=5,northing_m=5,recorded_area_m2=100,
        crs='EPSG:32644',synthetic=True),**updates)


def test_normalization_preserves_subdivisions_and_scope():
    assert survey_key('Survey No. 12 / A')=='12/A'
    assert survey_key('12/A')!=survey_key('12/B')
    engine=Resolver(parcels())
    r=engine.match(record())
    assert r['status']=='strong_proposal' and r['proposed_parcel_id']=='A'
    assert 'C' not in r['candidate_ids']
    assert engine.match(record(village=''))['status']=='unmatched'


def test_wrong_identifier_cannot_override_contradictions_and_missing_not_agreement():
    engine=Resolver(parcels())
    r=engine.match(record(survey_number='12/B'))
    assert 'A' in r['candidate_ids']  # spatial/address recovery despite wrong ID
    assert r['status']!='strong_proposal'
    r=engine.match(record(address='',easting_m=None,northing_m=None,recorded_area_m2=None))
    assert r['status']=='needs_review'
    assert set(r['candidates'][0]['missing_evidence'])=={'address','spatial','area'}


def test_missing_id_recovers_and_ambiguous_ids_abstain():
    engine=Resolver(parcels())
    r=engine.match(record(survey_number=''))
    assert r['status']=='strong_proposal' and r['proposed_parcel_id']=='A'
    ps=parcels();ps[1]['survey_number']='12/A'
    r=Resolver(ps).match(record(address='',easting_m=None,northing_m=None,recorded_area_m2=None))
    assert r['status']=='needs_review' and r['margin']==0


def test_multiple_accounts_and_duplicate_warning():
    results,_=Resolver(parcels()).resolve([record(record_id='R1'),record(record_id='R2',account_id='SECOND'),record(record_id='R3')])
    assert all(r['proposed_parcel_id']=='A' for r in results)
    assert results[1]['status']=='strong_proposal' and not results[1]['duplicate_record_ids']
    assert results[0]['status']=='needs_review' and set(results[0]['duplicate_record_ids'])=={'R1','R3'}


def test_review_switch_is_atomic_and_does_not_remove_other_records(tmp_path):
    store=ReviewStore(tmp_path/'audit.sqlite')
    a=dict(proposal_id='a',kind='department_link',source='water',feature_id='R',target_id='A')
    b=dict(a,proposal_id='b',target_id='B')
    c=dict(a,proposal_id='c',feature_id='OTHER')
    proposals=[a,b,c]
    for p in [a,c,b]: store.save_proposal('data',p,'accepted','Reviewer','check',proposals)
    assert store.decisions('data')=={'a':'rejected','c':'accepted','b':'accepted'}
    assert len(store.audit('data'))==4
    store.save_proposal('data',b,'pending','Reviewer','undo',proposals)
    assert store.decisions('data')['b']=='pending'


def test_exhaustive_small_comparison_and_distant_unmatched():
    engine=Resolver(parcels())
    for r in [record(),record(survey_number=''),record(address='Plot 1 Alpha Stret'),record(survey_number='12/B')]:
        assert engine.match(r)['proposed_parcel_id']==engine.match(r,exhaustive=True)['proposed_parcel_id']
    result=engine.match(record(survey_number='99/Z',address='Unknown',easting_m=1000,northing_m=1000))
    assert result['status']=='unmatched' and result['candidate_count']==0
