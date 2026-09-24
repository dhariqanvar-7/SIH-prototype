"""Load only operational department inputs and generate review proposals."""
import json
from collections import defaultdict
from pathlib import Path
from entity_resolution import Resolver, proposal_id


def load_inputs(root, parcels):
    base=Path(root)/'departmental/inputs'
    directory=json.loads((base/'parcel_directory.json').read_text(encoding='utf-8'))
    records=json.loads((base/'records.json').read_text(encoding='utf-8'))
    geometries=dict(zip(parcels.parcel_id,parcels.geometry))
    entries=[dict(p,geometry=geometries[p['parcel_id']]) for p in directory if p['parcel_id'] in geometries]
    if len({r['record_id'] for r in records})!=len(records): raise ValueError('Duplicate record_id in department input')
    return entries,records


def run_departments(root, parcels):
    entries,records=load_inputs(root,parcels)
    resolver=Resolver(entries)
    results,stats=resolver.resolve(records)
    record_index={r['record_id']:r for r in records}
    by_parcel=defaultdict(list); proposals=[]
    for result in results:
        # Alternatives are reviewable too, rather than hiding a correct second choice.
        for rank,candidate in enumerate(result['candidates'],1):
            if candidate['score']<.45: continue
            pid=candidate['parcel_id']; rid=result['record_id']
            item=dict(proposal_id=proposal_id(rid,pid),kind='department_link',source=result['department'],
                      feature_id=rid,target_id=pid,score=candidate['score'],candidate_rank=rank,
                      matching_status=result['status'],margin=result['margin'],
                      evidence=candidate['evidence'],missing_evidence=candidate['missing_evidence'],
                      conflicts=candidate['conflicts'],retrieval_routes=candidate['retrieval_routes'],
                      duplicate_record_ids=result['duplicate_record_ids'],
                      algorithm_version=result['algorithm_version'],synthetic=True,record=record_index[rid])
            proposals.append(item); by_parcel[pid].append(item)
    return dict(results=results,stats=stats,records=record_index,by_parcel=dict(by_parcel),proposals=proposals)
