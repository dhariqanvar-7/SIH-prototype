"""Offline evaluation. This is the ONLY matcher evaluation code reading answers."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time
import geopandas as gpd
from departmental import load_inputs
from entity_resolution import Resolver, scope, survey_key, point

ROOT=Path(__file__).resolve().parent/'dataset/hyderabad_kondapur'


def main():
    parcels=gpd.read_file(ROOT/'synthetic_benchmark/inputs/parcels.geojson').to_crs(32644)
    entries,records=load_inputs(ROOT,parcels)
    engine=Resolver(entries)
    results,stats=engine.resolve(records)  # Inputs first, answers only afterward.
    truth={r['record_id']:r for r in json.loads((ROOT/'departmental/evaluation_only/answers.json').read_text())}
    by_id={r['record_id']:r for r in records}
    metrics={}
    for split in ['development','test']:
        selected=[r for r in results if truth[r['record_id']]['split']==split]
        linked=[r for r in selected if truth[r['record_id']]['expected_parcel_id']]
        strong=[r for r in selected if r['status']=='strong_proposal']
        correct=sum(r['proposed_parcel_id']==truth[r['record_id']]['expected_parcel_id'] for r in strong)
        metrics[split]={'records':len(selected),'linkable_records':len(linked),'strong_proposals':len(strong),
            'candidate_recall':sum(truth[r['record_id']]['expected_parcel_id'] in r['candidate_ids'] for r in linked)/max(1,len(linked)),
            'strong_precision':correct/max(1,len(strong)),'strong_recall':correct/max(1,len(linked)),
            'top1_recall':sum(r['proposed_parcel_id']==truth[r['record_id']]['expected_parcel_id'] for r in linked)/max(1,len(linked)),
            'review_records':sum(r['status']=='needs_review' for r in selected),
            'unmatched_records':sum(r['status']=='unmatched' for r in selected)}
    test=[r for r in results if truth[r['record_id']]['split']=='test']
    baselines={}
    for mode in ['id_only','proximity_only']:
        predictions={}
        for result in test:
            r=by_id[result['record_id']]; predicted=None
            if mode=='id_only':
                found=engine.ids.get((scope(r),survey_key(r.get('survey_number'))),())
                if len(found)==1: predicted=engine.parcels[next(iter(found))]['parcel_id']
            else:
                pt=point(r)
                if pt is not None:
                    found=[(p['geometry'].distance(pt),p['parcel_id']) for p in engine.parcels if p['_scope']==scope(r)]
                    found.sort()
                    if found and found[0][0]<=35: predicted=found[0][1]
            predictions[r['record_id']]=predicted
        made={rid:pid for rid,pid in predictions.items() if pid}
        correct=sum(pid==truth[rid]['expected_parcel_id'] for rid,pid in made.items())
        baselines[mode]={'predictions':len(made),'correct':correct,'precision':correct/max(1,len(made)),
                         'recall':correct/max(1,sum(bool(truth[rid]['expected_parcel_id']) for rid in predictions))}
    # Deterministic spread through shuffled inputs, including hard cases.
    sample=records[::max(1,len(records)//100)][:100]
    started=time.perf_counter(); exhaustive=[engine.match(r,exhaustive=True) for r in sample]
    exhaustive_seconds=time.perf_counter()-started
    indexed_by_id={r['record_id']:r for r in results}
    same=sum(r['proposed_parcel_id']==indexed_by_id[r['record_id']]['proposed_parcel_id'] for r in exhaustive)
    scenarios=defaultdict(lambda:dict(records=0,retrieved=0,top1_correct=0,strong_wrong=0))
    for r in test:
        t=truth[r['record_id']]; s=scenarios[t['scenario']]; s['records']+=1
        s['retrieved']+=int(bool(t['expected_parcel_id']) and t['expected_parcel_id'] in r['candidate_ids'])
        s['top1_correct']+=int(r['proposed_parcel_id']==t['expected_parcel_id'])
        s['strong_wrong']+=int(r['status']=='strong_proposal' and r['proposed_parcel_id']!=t['expected_parcel_id'])
    report={'workload':'Fictional records on Kondapur synthetic parcels; not real departmental accuracy',
            'policy':'Fixed engineering thresholds, not trained or probability-calibrated. Test split not used for tuning.',
            'runtime':stats,'splits':metrics,'test_baselines':baselines,'test_scenarios':dict(scenarios),
            'exhaustive_comparison':{'sample_records':len(sample),'same_top1_decision':same,'seconds':exhaustive_seconds,
              'note':'Full scorer against all scoped parcels; differences expose retrieval limitations. Duplicate-account review downgrade is applied only in batch resolution.'}}
    out=Path(__file__).resolve().parent/'reports';out.mkdir(exist_ok=True)
    (out/'department_accuracy.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
