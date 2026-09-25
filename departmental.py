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


INTEGRATED_DEPARTMENTS = ('revenue', 'municipal', 'electricity', 'water', 'sewer')


def load_integrated_inputs(package, parcels):
    """Load only synthetic_integrated_v1/inputs. Never reads evaluation_only.

    Added for the integrated v1 benchmark. It is additive: existing datasets are
    unaffected. Sewer records reuse the water evidence weights in the resolver.
    """
    base = Path(package)/'inputs'
    entries = [dict(parcel_id=r.parcel_id, district=r.district, village=r.village,
                    survey_number=r.survey_number, address=r.address, geometry=r.geometry)
               for _, r in parcels.iterrows()]
    records = []
    for department in INTEGRATED_DEPARTMENTS:
        rows = json.loads((base/f'{department}_records.json').read_text(encoding='utf-8'))
        for row in rows:
            record = dict(row)
            record['recorded_area_m2'] = row.get('recorded_area_sqm')
            records.append(record)
    if len({r['record_id'] for r in records}) != len(records):
        raise ValueError('Duplicate record_id in integrated inputs')
    return entries, records


def run_departments(root, parcels, integrated=False):
    entries,records=(load_integrated_inputs(root,parcels) if integrated else load_inputs(root,parcels))
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
                      evidence_coverage=candidate.get('coverage'),
                      evidence=candidate['evidence'],missing_evidence=candidate['missing_evidence'],
                      conflicts=candidate['conflicts'],retrieval_routes=candidate['retrieval_routes'],
                      duplicate_record_ids=result['duplicate_record_ids'],
                      same_type_record_ids=result['same_type_record_ids'],
                      algorithm_version=result['algorithm_version'],
                      review_policy_version=stats['review_policy_version'],
                      synthetic=True,record=record_index[rid])
            proposals.append(item); by_parcel[pid].append(item)
    return dict(results=results,stats=stats,records=record_index,by_parcel=dict(by_parcel),proposals=proposals)
