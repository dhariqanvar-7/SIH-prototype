"""Generate fictional departmental records; reference answers never enter inputs."""
import hashlib
import json
import random
from pathlib import Path
import geopandas as gpd

ROOT=Path(__file__).resolve().parent/'dataset/hyderabad_kondapur'
OUT=ROOT/'departmental'
SEED=260130924


def main():
    if OUT.exists(): raise FileExistsError('Use a new directory for a new benchmark version')
    (OUT/'inputs').mkdir(parents=True); (OUT/'evaluation_only').mkdir()
    rng=random.Random(SEED)
    truth=gpd.read_file(ROOT/'synthetic_benchmark/evaluation_only/parcels_reference.geojson').to_crs(32644)
    survey_numbers=rng.sample(range(1000,9000),len(truth))
    plots=rng.sample(range(100,9500),len(truth))
    directory=[]
    for i,p in truth.iterrows():
        survey=f'{survey_numbers[i]}/{chr(65+i%3)}'
        if i>0 and i%17==0: survey=directory[i-1]['survey_number']
        directory.append(dict(parcel_id=p.parcel_id,district='DEMO-RANGAREDDY',village='DEMO-KONDAPUR',
            survey_number=survey,address=f'Plot {plots[i]}, Demo Street {i%12+1}, Kondapur',synthetic=True))
    cases=['clean','format_variation','missing_identifier','missing_geometry','address_typo',
           'wrong_identifier','area_error','identifier_only','old_record','location_shift','missing_scope']
    test_parcels=set(rng.sample(list(truth.parcel_id),240))
    records=[]; answers=[]
    def emit(record,pid,case):
        record['record_id']='SYN-'+format(rng.getrandbits(64),'016X')
        records.append(record)
        answers.append(dict(record_id=record['record_id'],expected_parcel_id=pid,scenario=case,
                            split='test' if pid in test_parcels or not pid else 'development'))
    for d,department in enumerate(['revenue','municipal','electricity','water','survey']):
        for i,p in truth.iterrows():
            meta=directory[i]; loc=p.geometry.representative_point()
            case=cases[(i+d*3)%len(cases)]
            row=dict(department=department,account_id='DEMO-'+format(rng.getrandbits(48),'012X'),
                     district=meta['district'],village=meta['village'],survey_number=meta['survey_number'],
                     address=meta['address'],recorded_area_m2=round(p.geometry.area,2),
                     easting_m=loc.x+rng.gauss(0,.3),northing_m=loc.y+rng.gauss(0,.3),
                     crs='EPSG:32644',record_date='2025-12-01',synthetic=True,
                     source=f'Fictional {department} department benchmark')
            if case=='format_variation':
                row['survey_number']='Survey No. '+row['survey_number'].replace('/',' / ')
                row['address']=row['address'].lower().replace('street','st.')
            elif case=='missing_identifier': row['survey_number']=''
            elif case=='missing_geometry': row['easting_m']=row['northing_m']=None
            elif case=='address_typo': row['address']=row['address'].replace('Street','Stret')
            elif case=='wrong_identifier': row['survey_number']=directory[(i+1)%len(directory)]['survey_number']
            elif case=='area_error': row['recorded_area_m2']*=1.35
            elif case=='identifier_only':
                row.update(address='',easting_m=None,northing_m=None,recorded_area_m2=None)
            elif case=='old_record': row['record_date']='2016-05-01'
            elif case=='location_shift': row['easting_m']+=45; row['northing_m']-=25
            elif case=='missing_scope': row['village']=''
            emit(row,p.parcel_id,case)
            if department in ['electricity','water'] and i%15==0:
                extra=dict(row,account_id='DEMO-'+format(rng.getrandbits(48),'012X'))
                emit(extra,p.parcel_id,'additional_account')
    for i in range(50):
        emit(dict(department=list(['revenue','municipal','electricity','water','survey'])[i%5],
                  account_id='OUTSIDE-'+str(i),district='DEMO-RANGAREDDY',village='DEMO-KONDAPUR',
                  survey_number=f'UNLISTED/{i}',address=f'Plot {900000+i} Other Township',
                  easting_m=500000+i*10,northing_m=2500000,recorded_area_m2=100,
                  crs='EPSG:32644',record_date='2025-12-01',synthetic=True,
                  source='Fictional unmatched departmental record'),None,'no_parcel_in_study_area')
    for i in rng.sample(range(1500),20):
        emit(dict(records[i]),answers[i]['expected_parcel_id'],'duplicate_account')
    rng.shuffle(records); rng.shuffle(answers)
    for path,value in [('inputs/parcel_directory.json',directory),('inputs/records.json',records),
                       ('evaluation_only/answers.json',answers)]:
        (OUT/path).write_text(json.dumps(value,indent=2),encoding='utf-8')
    manifest={'synthetic':True,'seed':SEED,'records':len(records),'parcels':len(directory),
              'schema_version':1,'metric_crs':'EPSG:32644','departments':['revenue','municipal','electricity','water','survey'],
              'notice':'All departmental identities, addresses and associations are invented. No real owner, service account or field measurement.',
              'evaluation':'Parcel-separated development/test split. Fixed rules are not trained or calibrated. Do not supply answers to matcher.',
              'provenance':'Synthetic parcel reference on Microsoft/OSM geography; retain upstream CDLA-Permissive-2.0 and ODbL attribution.',
              'files':{}}
    for path in OUT.rglob('*.json'):
        manifest['files'][path.relative_to(OUT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'records':len(records),'parcels':len(directory),'seed':SEED}))


if __name__=='__main__':main()
