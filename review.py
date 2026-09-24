import json
import sqlite3
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

def export_geojson(result, decisions):
    """Keep original boundaries unless a specific repair was accepted."""
    parcels = result['originals']['parcels'].copy()
    parcels['source'] = 'inputs/cadastral.gpkg'
    parcels['dataset_fingerprint'] = result['fingerprint']
    parcels['geometry_status'] = ['original_valid' if g.is_valid else 'original_invalid' for g in parcels.geometry]
    for i,r in parcels.iterrows():
        accepted = [p for p in result['proposals'] if decisions.get(p['proposal_id'])=='accepted']
        repair = next((p for p in accepted if p['kind']=='repair' and p['source']=='parcels' and p['feature_id']==r.parcel_id),None)
        if repair:
            parcels.at[i,'geometry'] = from_wkt(repair['proposed_wkt'])
            parcels.at[i,'geometry_status'] = 'accepted_repair'
        links = [p for p in accepted if p['target_id']==r.parcel_id and p['kind'] in {'record_link','building_link'}]
        parcels.at[i,'accepted_links'] = json.dumps(links)
    return parcels.to_crs('EPSG:4326').to_json()
