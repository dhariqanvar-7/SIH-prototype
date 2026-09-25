import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
from shapely import from_wkt

class ReviewStore:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, dataset TEXT, proposal TEXT, decision TEXT, reviewer TEXT, note TEXT, at TEXT)')
    def connect(self): return sqlite3.connect(self.path)
    def save(self, fingerprint, proposal, decision, reviewer, note=''):
        if decision not in {'accepted','rejected','pending'}: raise ValueError(decision)
        if not reviewer.strip(): raise ValueError('Reviewer name is required')
        with self.connect() as db:
            db.execute('INSERT INTO audit(dataset,proposal,decision,reviewer,note,at) VALUES(?,?,?,?,?,?)',
                       (fingerprint,proposal,decision,reviewer.strip(),note,datetime.now(timezone.utc).isoformat()))
    def audit(self, fingerprint):
        with self.connect() as db:
            return pd.read_sql_query('SELECT * FROM audit WHERE dataset=? ORDER BY id',db,params=[fingerprint])
    def decisions(self, fingerprint):
        df = self.audit(fingerprint)
        return dict(zip(df.proposal,df.decision))

    def save_proposal(self, fingerprint, proposal, decision, reviewer, note, proposals):
        """A record may have one accepted parcel; a parcel may have many records."""
        if proposal['kind']!='department_link' or decision!='accepted':
            return self.save(fingerprint,proposal['proposal_id'],decision,reviewer,note)
        if not reviewer.strip(): raise ValueError('Reviewer name is required')
        alternatives={p['proposal_id'] for p in proposals if p['kind']=='department_link'
                      and p['source']==proposal['source'] and p['feature_id']==proposal['feature_id']
                      and p['proposal_id']!=proposal['proposal_id']}
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=dict(db.execute('SELECT proposal,decision FROM audit WHERE dataset=? ORDER BY id',(fingerprint,)).fetchall())
            at=datetime.now(timezone.utc).isoformat()
            for pid in sorted(alternatives):
                if current.get(pid)=='accepted':
                    db.execute('INSERT INTO audit(dataset,proposal,decision,reviewer,note,at) VALUES(?,?,?,?,?,?)',
                               (fingerprint,pid,'rejected',reviewer.strip(),'Superseded by reviewed alternative '+proposal['proposal_id'],at))
            db.execute('INSERT INTO audit(dataset,proposal,decision,reviewer,note,at) VALUES(?,?,?,?,?,?)',
                       (fingerprint,proposal['proposal_id'],'accepted',reviewer.strip(),note,at))


def effective_decisions(proposals, recorded=None):
    """Return recorded decisions plus safe automatic approvals.

    Only the winning candidate of a strong departmental match is automatically
    approved.  An explicit reviewer decision always takes precedence, so a
    reviewer can reject or re-open an automatically approved association.
    """
    decisions = dict(recorded or {})
    proposed_by_type = defaultdict(set)
    accepted_by_type = defaultdict(set)
    for p in proposals:
        if p.get('kind') != 'department_link':
            continue
        key = (p.get('target_id'), p.get('source'))
        if p.get('candidate_rank') == 1:
            proposed_by_type[key].add(p.get('feature_id'))
        if decisions.get(p['proposal_id']) == 'accepted':
            accepted_by_type[key].add(p.get('feature_id'))
    explicit_accepts = {
        (p.get('source'), p.get('feature_id')): p['proposal_id']
        for p in proposals
        if decisions.get(p['proposal_id']) == 'accepted'
        and p.get('kind') == 'department_link'
    }
    for proposal in proposals:
        if (proposal.get('kind') == 'department_link'
                and proposal.get('matching_status') == 'strong_proposal'
                and proposal.get('candidate_rank') == 1):
            key = (proposal.get('source'), proposal.get('feature_id'))
            parcel_type = (proposal.get('target_id'), proposal.get('source'))
            if (len(proposed_by_type[parcel_type]) == 1
                    and not (accepted_by_type[parcel_type] - {proposal.get('feature_id')})
                    and (key not in explicit_accepts or explicit_accepts[key] == proposal['proposal_id'])):
                decisions.setdefault(proposal['proposal_id'], 'auto_approved')
    return decisions

def export_geojson(result, decisions):
    """Keep original boundaries unless a specific repair was accepted."""
    parcels = result['originals']['parcels'].copy()
    parcels['source'] = result.get('parcel_source', 'inputs/cadastral.gpkg')
    parcels['dataset_fingerprint'] = result['fingerprint']
    parcels['geometry_status'] = ['original_valid' if g.is_valid else 'original_invalid' for g in parcels.geometry]
    for i,r in parcels.iterrows():
        accepted = [p for p in result['proposals']
                    if decisions.get(p['proposal_id']) in {'accepted','auto_approved'}]
        repair = next((p for p in accepted if p['kind']=='repair' and p['source']=='parcels' and p['feature_id']==r.parcel_id),None)
        if repair:
            parcels.at[i,'geometry'] = from_wkt(repair['proposed_wkt'])
            parcels.at[i,'geometry_status'] = 'accepted_repair'
        links = [p for p in accepted if p['target_id']==r.parcel_id and p['kind'] in {'record_link','building_link','department_link'}]
        parcels.at[i,'accepted_links'] = json.dumps(links)
    return parcels.to_crs('EPSG:4326').to_json()
