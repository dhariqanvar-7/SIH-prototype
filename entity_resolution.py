"""Input-only indexed geospatial entity resolution. No evaluation imports.

One departmental record has at most one reviewed parcel, but a parcel can have
many records. Scores are evidence rankings, never calibrated probabilities.
"""
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import hashlib
import math
import re
import time
from shapely.geometry import Point
from shapely.strtree import STRtree

VERSION = 'iges-er-1.0'
REVIEW_POLICY_VERSION = 'same-department-parcel-v1'
RADIUS_M = 35
WEIGHTS = {
    'revenue': dict(identifier=.45, spatial=.25, address=.15, area=.15),
    'municipal': dict(identifier=.25, spatial=.35, address=.30, area=.10),
    'electricity': dict(identifier=.20, spatial=.35, address=.40, area=.05),
    'water': dict(identifier=.20, spatial=.35, address=.40, area=.05),
    'sewer': dict(identifier=.20, spatial=.35, address=.40, area=.05),
    'survey': dict(identifier=.40, spatial=.45, address=.10, area=.05),
}
POLICY = {'strong_threshold':.80, 'review_threshold':.45, 'margin':.12,
          'minimum_coverage':.50, 'minimum_agreeing_groups':2}


def survey_key(value):
    # Only the documented demo convention treats hyphen and slash as equivalent.
    text = re.sub(r'^(?:SURVEY\s*(?:NO\.?|NUMBER)?|S\.?\s*NO\.?)\s*', '', str(value or '').upper())
    return re.sub(r'\s+', '', text).replace('-', '/')


def address_key(value):
    text = re.sub(r'[^A-Z0-9 ]', ' ', str(value or '').upper())
    for long, short in [('ROAD','RD'),('STREET','ST'),('NUMBER','NO')]:
        text = re.sub(r'\b'+long+r'\b',short,text)
    return ' '.join(text.split())


def tokens(value):
    return set(address_key(value).split()) - {'PLOT','NO','RD','ST','DEMO','KONDAPUR'}


def scope(row):
    return tuple(str(row.get(k) or '').strip().upper() for k in ['district','village'])


def point(row):
    try:
        x,y = float(row['easting_m']), float(row['northing_m'])
        return Point(x,y) if math.isfinite(x) and math.isfinite(y) else None
    except (KeyError,TypeError,ValueError):
        return None


def proposal_id(record_id, parcel_id):
    return hashlib.sha256(f'{VERSION}|{record_id}|{parcel_id}'.encode()).hexdigest()[:20]


class Resolver:
    def __init__(self, parcels):
        started=time.perf_counter()
        self.parcels=[]
        self.quarantine=[]
        seen=set()
        for p in parcels:
            if p['parcel_id'] in seen:
                raise ValueError('Duplicate parcel identity')
            seen.add(p['parcel_id'])
            g=p['geometry']
            if g is None or g.is_empty or not g.is_valid or g.area<=0:
                self.quarantine.append(p['parcel_id']); continue
            item=dict(p)
            item['_scope']=scope(p); item['_survey']=survey_key(p.get('survey_number'))
            item['_address']=address_key(p.get('address')); item['_tokens']=tokens(p.get('address'))
            self.parcels.append(item)
        self.tree=STRtree([p['geometry'] for p in self.parcels])
        self.ids=defaultdict(set); self.addresses=defaultdict(set); self.words=defaultdict(set)
        self.scope_sizes=Counter(p['_scope'] for p in self.parcels)
        for i,p in enumerate(self.parcels):
            if p['_survey']: self.ids[(p['_scope'],p['_survey'])].add(i)
            if p['_address']: self.addresses[(p['_scope'],p['_address'])].add(i)
            for token in p['_tokens']: self.words[(p['_scope'],token)].add(i)
        self.index_seconds=time.perf_counter()-started

    def retrieve(self, record):
        context=scope(record)
        if not all(context):
            return {}  # Do not silently equate unidentified administrative scopes.
        routes=defaultdict(set)
        for i in self.ids.get((context,survey_key(record.get('survey_number'))),()): routes[i].add('scoped_identifier')
        pos=point(record)
        if pos is not None:
            for i in self.tree.query(pos.buffer(RADIUS_M)):
                p=self.parcels[int(i)]
                if p['_scope']==context and p['geometry'].distance(pos)<=RADIUS_M:
                    routes[int(i)].add('spatial')
        address=address_key(record.get('address'))
        for i in self.addresses.get((context,address),()): routes[i].add('exact_address')
        # Ignore common postings; rare-token union gives typo tolerance without
        # returning an entire town for a token such as a locality name.
        for token in tokens(address):
            posting=self.words.get((context,token),())
            if len(posting)<=max(10,self.scope_sizes[context]*.05):
                for i in posting: routes[i].add('address_token')
        return dict(routes)

    def score(self, record, i, routes=()):
        p=self.parcels[i]; weights=WEIGHTS[record['department']]
        values={}; conflicts=[]; severe=[]
        sid=survey_key(record.get('survey_number'))
        if sid and p['_survey']:
            values['identifier']=float(sid==p['_survey'])
            if not values['identifier']: severe.append('Survey references disagree')
        pos=point(record)
        distance=None
        if pos is not None:
            distance=p['geometry'].distance(pos)
            values['spatial']=max(0.,1-distance/RADIUS_M)
            if distance>RADIUS_M: severe.append('Location outside search tolerance')
        address=address_key(record.get('address'))
        if address and p['_address']:
            rt=tokens(address); pt=p['_tokens']
            jaccard=len(rt&pt)/max(1,len(rt|pt))
            values['address']=.6*jaccard+.4*SequenceMatcher(None,address,p['_address']).ratio()
            plot_r=re.search(r'\bPLOT\s+(?:NO\s+)?(\d+)\b',address)
            plot_p=re.search(r'\bPLOT\s+(?:NO\s+)?(\d+)\b',p['_address'])
            if plot_r and plot_p and plot_r[1]!=plot_p[1]:
                values['address']*=.2; severe.append('Plot numbers disagree')
        try: area=float(record.get('recorded_area_m2') or 0)
        except (ValueError,TypeError): area=0
        if area>0:
            delta=abs(area-p['geometry'].area)/p['geometry'].area
            values['area']=max(0.,1-delta)
            if delta>.10: conflicts.append(f'Area differs by {delta:.0%}')
        if record.get('record_date') and str(record['record_date'])<'2020-01-01':
            conflicts.append('Old record: date precedes 2020; no historical parcel version available')
        coverage=sum(weights[k] for k in values)
        weighted=sum(weights[k]*v for k,v in values.items())/coverage if coverage else 0.
        score=max(0.,weighted-.15*len(severe))
        agreeing=sum(v>=.7 for v in values.values())
        return dict(parcel_id=p['parcel_id'],score=round(score,6),coverage=round(coverage,3),
                    agreeing_groups=agreeing, evidence={k:round(v,4) for k,v in values.items()},
                    missing_evidence=[k for k in weights if k not in values], conflicts=severe+conflicts,
                    blocking_conflicts=severe, distance_m=round(distance,3) if distance is not None else None,
                    retrieval_routes=sorted(routes))

    def match(self, record, exhaustive=False):
        if record.get('department') not in WEIGHTS: raise ValueError('Unknown department')
        if record.get('crs')!='EPSG:32644': raise ValueError('Expected metric coordinates in EPSG:32644')
        retrieved=({i:{'exhaustive'} for i,p in enumerate(self.parcels) if p['_scope']==scope(record)}
                   if exhaustive else self.retrieve(record))
        scored=[self.score(record,i,routes) for i,routes in retrieved.items()]
        scored.sort(key=lambda c:(-c['score'],c['parcel_id']))
        top=scored[0] if scored else None
        margin=top['score']-scored[1]['score'] if len(scored)>1 else top['score'] if top else 0.
        status='unmatched'
        if top and top['score']>=POLICY['review_threshold']:
            status='needs_review'
            if (top['score']>=POLICY['strong_threshold'] and margin>=POLICY['margin']
                and top['coverage']>=POLICY['minimum_coverage'] and top['agreeing_groups']>=POLICY['minimum_agreeing_groups']
                and not top['blocking_conflicts']):
                status='strong_proposal'
        return dict(record_id=record['record_id'],department=record['department'],status=status,
                    proposed_parcel_id=top['parcel_id'] if top and status!='unmatched' else None,
                    score=top['score'] if top else 0.,margin=round(margin,6),candidate_count=len(scored),
                    candidate_ids=[c['parcel_id'] for c in scored],candidates=scored[:5],
                    reason='Missing district/village scope' if not all(scope(record)) else 'No sufficiently supported association' if status=='unmatched' else 'Human confirmation required',
                    algorithm_version=VERSION,synthetic=bool(record.get('synthetic')))

    def resolve(self, records):
        started=time.perf_counter(); results=[self.match(r) for r in records]
        signatures=defaultdict(list)
        for r in records:
            # Different service accounts are legitimate; same department/account
            # appearing twice is flagged rather than silently deduplicated.
            if r.get('account_id'): signatures[(r['department'],r['account_id'])].append(r['record_id'])
        duplicates={rid:group for group in signatures.values() if len(group)>1 for rid in group}
        by_parcel_type=defaultdict(list)
        for result in results:
            if result['proposed_parcel_id']:
                by_parcel_type[(result['proposed_parcel_id'],result['department'])].append(result['record_id'])
        for r in results:
            r['duplicate_record_ids']=duplicates.get(r['record_id'],[])
            same_type=by_parcel_type.get((r['proposed_parcel_id'],r['department']),[])
            r['same_type_record_ids']=[rid for rid in same_type if rid!=r['record_id']]
            if r['same_type_record_ids']:
                reason=f"Multiple {r['department']} records proposed for parcel {r['proposed_parcel_id']}; human review required"
                r['reason']=reason
                if r['candidates'] and r['candidates'][0]['parcel_id']==r['proposed_parcel_id']:
                    r['candidates'][0]['conflicts'].append(reason)
            if (r['duplicate_record_ids'] or r['same_type_record_ids']) and r['status']=='strong_proposal':
                r['status']='needs_review'
        return results, dict(algorithm_version=VERSION,review_policy_version=REVIEW_POLICY_VERSION,
            index_seconds=self.index_seconds,
            query_seconds=time.perf_counter()-started,records=len(records),parcels=len(self.parcels),
            candidate_pairs=sum(r['candidate_count'] for r in results),
            exhaustive_pairs=len(records)*len(self.parcels), quarantined_parcels=self.quarantine,
            status_counts=dict(Counter(r['status'] for r in results)),
            same_type_review_records=sum(bool(r['same_type_record_ids']) for r in results))
