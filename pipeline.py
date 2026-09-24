"""Input-only harmonization. No answer keys are accessed here."""
from pathlib import Path
import hashlib
import json
import re
import geopandas as gpd
import pandas as pd
from shapely import make_valid
from shapely.validation import explain_validity

CRS = 'EPSG:32643'
VERSION = '1'

def normalize_id(value):
    match = re.fullmatch(r'(?:P\s*[-/]?\s*)?(\d+)', str(value).strip().upper())
    return f'P-{int(match[1]):03d}' if match else None

def normalize_use(value):
    return str(value).strip().lower().replace(' ', '_').replace('mixed_use', 'mixed')

def fingerprint(root):
    h = hashlib.sha256(VERSION.encode())
    for p in sorted((Path(root) / 'inputs').iterdir()):
        h.update(p.name.encode()); h.update(p.read_bytes())
    h.update((Path(root) / 'manifest.json').read_bytes())
    return h.hexdigest()

def compare_dates(t1, t2):
    candidates = []
    for i, a in t1.iterrows():
        for j in t2.sindex.query(a.geometry.buffer(12)):
            b = t2.iloc[j].geometry
            inter = a.geometry.intersection(b).area
            union = a.geometry.union(b).area
            iou = inter / union if union else 0
            distance = a.geometry.centroid.distance(b.centroid)
            ratio = min(a.geometry.area, b.area) / max(a.geometry.area, b.area)
            score = .65 * iou + .2 * max(0, 1-distance/12) + .15 * ratio
            if iou >= .15 or (distance <= 5 and ratio >= .65):
                candidates.append((score, i, int(j), iou, distance))
    used1, used2, rows = set(), set(), []
    for score, i, j, iou, distance in sorted(candidates, reverse=True):
        if i in used1 or j in used2:
            continue
        used1.add(i); used2.add(j)
        a, b = t1.loc[i], t2.iloc[j]
        growth = b.geometry.area / a.geometry.area - 1
        kind = 'extended' if growth > .15 else 'reduced' if growth < -.15 else 'stable'
        rows.append(dict(t1_id=a.extracted_id, t2_id=b.extracted_id, change=kind,
                         score=score, iou=iou, centroid_distance_m=distance, area_change_pct=100*growth))
    for frame, used, kind in [(t1, used1, 'removed'), (t2, used2, 'added')]:
        for i, r in frame.iterrows():
            if i not in used:
                rows.append(dict(t1_id=r.extracted_id if kind=='removed' else '',
                                 t2_id=r.extracted_id if kind=='added' else '', change=kind,
                                 score=0, iou=0, centroid_distance_m=None, area_change_pct=None))
    return pd.DataFrame(rows)

def run(root):
    root = Path(root)
    layers, proposals, conflicts, validation = {}, [], [], []
    def proposal(kind, source, feature, target='', **evidence):
        key = '|'.join([kind, source, str(feature), str(target)])
        item = dict(proposal_id=hashlib.sha256(key.encode()).hexdigest()[:20], kind=kind,
                    source=source, feature_id=str(feature), target_id=str(target), **evidence)
        proposals.append(item)
        return item
    manifest = json.loads((root/'manifest.json').read_text())
    meta = {Path(e['path'].replace('\\','/')).name:e for e in manifest['files']}
    specs = [('parcels','cadastral.gpkg','parcel_id'), ('t1','extracted_buildings_t1.geojson','extracted_id'),
             ('t2','extracted_buildings_t2.geojson','extracted_id'),
             ('observations','ground_truth_observations.geojson','observation_id'), ('utilities','utilities.geojson','utility_id')]
    originals = {}
    for name, filename, idcol in specs:
        g = gpd.read_file(root/'inputs'/filename)
        if not meta[filename].get('crs') or g.crs is None:
            raise ValueError(f'Unconfirmed CRS: {filename}')
        g = g.to_crs(CRS)
        originals[name] = g.copy()
        good = []
        for i, r in g.iterrows():
            geom = r.geometry
            valid = geom is not None and not geom.is_empty and geom.is_valid
            validation.append(dict(source=filename, feature_id=r[idcol], valid=valid,
                                   reason=explain_validity(geom) if geom is not None else 'Missing geometry'))
            if not valid:
                repair = make_valid(geom) if geom is not None else None
                proposal('repair',name,r[idcol], reason=validation[-1]['reason'],
                         original_wkt=geom.wkt if geom is not None else '',
                         proposed_wkt=repair.wkt if repair is not None else '')
                conflicts.append(dict(kind='invalid_geometry',source=name,feature_id=r[idcol],detail=validation[-1]['reason']))
            else:
                good.append(i)
        layers[name] = g.loc[good].reset_index(drop=True)
    parcels = layers['parcels']
    for i, a in parcels.iterrows():
        for j in parcels.sindex.query(a.geometry, predicate='intersects'):
            if j <= i: continue
            b = parcels.iloc[j]
            area = a.geometry.intersection(b.geometry).area
            if area > .1:
                conflicts.append(dict(kind='parcel_overlap',source='parcels',feature_id=a.parcel_id,
                                      detail=f'{b.parcel_id}: {area:.2f} m²'))
    links = []
    for source, idcol, refcol in [('revenue','record_id','survey_no'),('municipal','property_id','plot_ref')]:
        records = pd.read_csv(root/'inputs'/f'{source}.csv',dtype=str,keep_default_na=False)
        records['parcel_id'] = records[refcol].map(normalize_id)
        if source == 'municipal': records['normalized_use'] = records.use_type.map(normalize_use)
        for _, r in records.iterrows():
            pid = r.parcel_id
            if pid not in set(originals['parcels'].parcel_id):
                conflicts.append(dict(kind='unmatched_record',source=source,feature_id=r[idcol],detail=r[refcol])); continue
            proposal('record_link',source,r[idcol],pid,score=1.0,reason='Exact normalized parcel identifier',record=r.to_dict())
            links.append(dict(source=source,feature_id=r[idcol],parcel_id=pid))
            if records.parcel_id.eq(pid).sum()>1:
                conflicts.append(dict(kind='duplicate_record',source=source,feature_id=r[idcol],detail=f'Multiple records for {pid}'))
            p = parcels[parcels.parcel_id.eq(pid)]
            if not p.empty and source == 'revenue':
                area = p.iloc[0].geometry.area
                delta = abs(float(r.recorded_area_m2)-area)/area
                if delta > .10:
                    conflicts.append(dict(kind='area_disagreement',source=source,feature_id=r[idcol],detail=f'{pid}: {delta:.1%} difference'))
            if not p.empty and source == 'municipal' and r.normalized_use != normalize_use(p.iloc[0].land_use):
                conflicts.append(dict(kind='use_disagreement',source=source,feature_id=r[idcol],detail=f'{pid}: {r.normalized_use} / {p.iloc[0].land_use}'))
        for pid in sorted(set(originals['parcels'].parcel_id)-set(records.parcel_id)):
            conflicts.append(dict(kind='missing_record',source=source,feature_id=pid,detail='No normalized reference'))
    candidates = []
    for date in ['t1','t2']:
        for _, b in layers[date].iterrows():
            matches = []
            for j in parcels.sindex.query(b.geometry.buffer(15)):
                p = parcels.iloc[j]
                overlap = b.geometry.intersection(p.geometry).area/b.geometry.area
                distance = b.geometry.distance(p.geometry)
                fit = min(1, p.geometry.area/b.geometry.area)
                score = .75*overlap + .15*max(0,1-distance/15) + .10*fit
                matches.append(dict(source=date,feature_id=b.extracted_id,parcel_id=p.parcel_id,
                                    score=score,overlap_fraction=overlap,distance_m=distance,area_fit=fit))
            matches.sort(key=lambda r:r['score'],reverse=True)
            candidates.extend(matches)
            if matches:
                best = matches[0]
                margin = best['score']-matches[1]['score'] if len(matches)>1 else best['score']
                proposal('building_link',date,b.extracted_id,best['parcel_id'],score=best['score'],
                         overlap_fraction=best['overlap_fraction'],distance_m=best['distance_m'],area_fit=best['area_fit'],margin=margin)
                if best['overlap_fraction'] < .8 or margin < .1:
                    conflicts.append(dict(kind='ambiguous_building',source=date,feature_id=b.extracted_id,detail='Low overlap or competing candidate'))
            else:
                conflicts.append(dict(kind='unmatched_building',source=date,feature_id=b.extracted_id,detail='No valid parcel within 15 m'))
    evidence = []
    for _, o in layers['observations'].iterrows():
        for j in parcels.sindex.query(o.geometry,predicate='intersects'):
            p = parcels.iloc[j]
            evidence.append(dict(parcel_id=p.parcel_id,observation_id=o.observation_id,
                                 observed_use=o.observed_use,verification_status=o.verification_status))
            if normalize_use(o.observed_use)!=normalize_use(p.land_use):
                conflicts.append(dict(kind='observation_disagreement',source='observations',feature_id=o.observation_id,detail=p.parcel_id))
    gnss = pd.read_csv(root/'inputs/gnss_observations.csv')
    layers['gnss'] = gpd.GeoDataFrame(gnss,geometry=gpd.points_from_xy(gnss.easting,gnss.northing),crs=meta['gnss_observations.csv']['crs']).to_crs(CRS)
    changes = compare_dates(layers['t1'],layers['t2'])
    for row in changes.to_dict('records'):
        if row['change']!='stable':
            proposal('change', 't1_t2',row['t1_id'] or row['t2_id'],row['t2_id'],**row)
    return dict(fingerprint=fingerprint(root), layers=layers, originals=originals, proposals=proposals,
                conflicts=pd.DataFrame(conflicts),validation=pd.DataFrame(validation),
                candidates=pd.DataFrame(candidates),links=pd.DataFrame(links),changes=changes,
                evidence=pd.DataFrame(evidence),quarantine=['legacy_parcels_no_crs.geojson: source CRS unknown; 100 features excluded'])
