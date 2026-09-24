"""Build explicitly synthetic land-record fixtures from real building locations.

Dependencies: shapely >=2.1, pyproj, numpy. No real ownership/survey data.
Evaluation answers are stored separately from inputs.
"""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from pyproj import Transformer
from shapely import voronoi_polygons, union_all
from shapely.geometry import shape, mapping, MultiPoint, LineString, box
from shapely.ops import transform
from shapely.affinity import translate

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'synthetic_benchmark'
INPUT = OUT/'inputs'
EVAL = OUT/'evaluation_only'
FWD = Transformer.from_crs(4326,32644,always_xy=True).transform
REV = Transformer.from_crs(32644,4326,always_xy=True).transform
SEED = 20260924


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2),encoding='utf-8')


def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def feature(geom,identifier,**properties):
    return {'type':'Feature','id':identifier,'geometry':mapping(transform(REV,geom)),
            'properties':dict(properties,synthetic=True,source='BhuSetu synthetic benchmark')}


def fc(features):
    return {'type':'FeatureCollection','features':features}


def main():
    if OUT.exists():
        raise FileExistsError('Refusing to overwrite an existing benchmark')
    INPUT.mkdir(parents=True); EVAL.mkdir()
    rng=np.random.default_rng(SEED)
    aoi=transform(FWD,shape(json.loads((ROOT/'aoi.geojson').read_text())['features'][0]['geometry']))
    buildings=json.loads((ROOT/'buildings.geojson').read_text())['features']
    candidates=[(f['id'],transform(FWD,shape(f['geometry']))) for f in buildings]
    candidates=[(bid,g) for bid,g in candidates if aoi.covers(g)]
    indices=sorted(rng.choice(len(candidates),size=min(300,len(candidates)),replace=False).tolist())
    selected=[candidates[i] for i in indices]
    seeds=[g.representative_point() for _,g in selected]
    cells=voronoi_polygons(MultiPoint(seeds),extend_to=aoi.envelope,ordered=True)
    roads=json.loads((ROOT/'roads.geojson').read_text())['features']
    corridors=union_all([transform(FWD,shape(f['geometry'])).buffer(3)
                         for f in roads if f['properties'].get('highway') not in ['footway','path','steps']])
    parcels=[]
    for i,cell in enumerate(cells.geoms):
        g=cell.intersection(aoi).difference(corridors)
        if g.geom_type=='GeometryCollection':
            g=union_all([p for p in g.geoms if p.geom_type in ['Polygon','MultiPolygon']])
        assert g.is_valid and not g.is_empty and g.area>0
        parcels.append(g)
    parcel_inputs=[]; parcel_truth=[]; records=[]; record_answers=[]; observations=[]
    shifted=set(rng.choice(len(parcels),size=30,replace=False).tolist())
    area_errors=set(rng.choice(len(parcels),size=20,replace=False).tolist())
    for i,g in enumerate(parcels):
        pid=f'SYN-P{i+1:04d}'; survey=f'SYN-SURVEY-{i+1:04d}'
        landuse=['residential','commercial','mixed_use'][i%3]
        parcel_truth.append(feature(g,pid,parcel_id=pid,survey_number=survey,area_m2=g.area,land_use=landuse))
        observed=translate(g,xoff=5,yoff=-3) if i in shifted else g
        parcel_inputs.append(feature(observed,pid,parcel_id=pid,survey_number=survey,land_use=landuse))
        records.append({'record_id':f'SYN-R{i+1:04d}','parcel_id':pid,'survey_number':survey,
                        'fictional_owner_id':f'FICTIONAL-OWNER-{i+1:04d}',
                        'recorded_area_m2':round(g.area*(1.2 if i in area_errors else 1),2),
                        'land_use':landuse,'record_date':'2026-01-01','synthetic':True})
        record_answers.append({'record_id':f'SYN-R{i+1:04d}','expected_parcel_id':pid,
                               'geometry_shifted':i in shifted,'shift_east_m':5 if i in shifted else 0,
                               'shift_north_m':-3 if i in shifted else 0,
                               'area_mismatch':i in area_errors,'true_area_m2':g.area,'synthetic':True})
        point=g.representative_point(); lon,lat=REV(point.x,point.y)
        observations.append({'observation_id':f'SYN-GT{i+1:04d}','parcel_id':pid,
                             'longitude':lon,'latitude':lat,'observed_land_use':landuse,
                             'verification_status':'SIMULATED_NOT_FIELD_VERIFIED','synthetic':True})
    write_json(INPUT/'parcels.geojson',fc(parcel_inputs))
    write_json(EVAL/'parcels_reference.geojson',fc(parcel_truth))
    write_csv(INPUT/'revenue_records.csv',records)
    write_csv(INPUT/'ground_truth_observations.csv',observations)
    write_csv(EVAL/'expected_record_matches.csv',record_answers)
    matches=[]
    for b in buildings:
        bg=transform(FWD,shape(b['geometry']))
        for i,g in enumerate(parcels):
            overlap=bg.intersection(g).area
            if overlap>1e-6:
                matches.append({'building_id':b['id'],'synthetic_parcel_id':f'SYN-P{i+1:04d}',
                                'intersection_m2':overlap,'building_overlap_fraction':overlap/bg.area,
                                'relation':'reference_geometry_intersection','synthetic':True})
    write_csv(EVAL/'expected_building_intersections.csv',matches)
    gnss=[]; gnss_truth=[]
    for n,i in enumerate(sorted(rng.choice(len(parcels),size=30,replace=False).tolist()),1):
        p=parcels[i].representative_point(); sigma=.05 if n<=24 else .5
        east=p.x+float(rng.normal(0,sigma)); north=p.y+float(rng.normal(0,sigma))
        lon,lat=REV(east,north)
        gnss.append({'observation_id':f'SYN-GNSS{n:03d}','control_id':f'SYN-CTRL{n:03d}',
                     'easting_m':east,'northing_m':north,'longitude':lon,'latitude':lat,
                     'crs':'EPSG:32644','simulated_sigma_per_axis_m':sigma,'survey_date':'',
                     'method':'SIMULATED_COORDINATE_OBSERVATION_NOT_RINEX','synthetic':True})
        gnss_truth.append({'control_id':f'SYN-CTRL{n:03d}','reference_easting_m':p.x,
                           'reference_northing_m':p.y,'crs':'EPSG:32644',
                           'reference_type':'synthetic_control_not_surveyed','synthetic':True})
    write_csv(INPUT/'gnss_observations.csv',gnss)
    write_csv(EVAL/'control_points_reference.csv',gnss_truth)
    # A fictional water distribution graph, deliberately separate from real OSM utilities.
    minx,miny,maxx,maxy=aoi.bounds
    lines=[]
    for i in range(1,6):
        x=minx+(maxx-minx)*i/6; y=miny+(maxy-miny)*i/6
        lines.extend([LineString([(x,miny),(x,maxy)]).intersection(aoi),
                      LineString([(minx,y),(maxx,y)]).intersection(aoi)])
    segments=union_all(lines)
    utilities=[feature(g,f'SYN-WATER-{i+1:04d}',utility_type='water',
                       layout='fictional_grid_not_actual_alignment') for i,g in enumerate(segments.geoms)]
    write_json(INPUT/'utility_network_synthetic.geojson',fc(utilities))
    union=union_all(parcels)
    assert abs(sum(g.area for g in parcels)-union.area)<.01, 'Overlapping reference parcels'
    report={'seed':SEED,'synthetic':True,'metric_crs':'EPSG:32644','geometry_crs':'EPSG:4326',
            'counts':{'parcels':len(parcels),'revenue_records':len(records),'ground_truth_observations':len(observations),
                      'gnss_observations':len(gnss),'utility_segments':len(utilities),'building_intersections':len(matches)},
            'controlled_errors':{'shifted_parcels':len(shifted),'area_mismatch_records':len(area_errors),
                                 'overlapping_error_cases':len(shifted&area_errors)},
            'method':'300 seeded Voronoi cells from interior real building representative points, clipped to AOI, subtracting assumed 3 m road buffers. Parcel boundaries, survey numbers, land use and owners are invented.',
            'limitations':['Cells may split buildings or contain multiple buildings; they are not reconstructed cadastral boundaries.',
                          'Assumed road buffers are not surveyed road widths.',
                          'No manual imagery or field validation; GT is synthetic.',
                          'Expected building intersections are geometric answers against invented parcels, not ownership matches.',
                          'Utility grid does not follow actual pipes or roads and is only a network-format test fixture.',
                          'Inputs contain controlled displacements; shifted parcels may overlap or cross AOI.',
                          'Evaluation files must not be supplied to the matching engine.'],
            'provenance':{'buildings':'../buildings.geojson','roads':'../roads.geojson',
                          'upstream_licenses':['Microsoft CDLA-Permissive-2.0','OpenStreetMap ODbL-1.0']},'files':{}}
    for path in sorted(OUT.rglob('*')):
        if path.is_file():
            with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            report['files'][path.relative_to(OUT).as_posix()]={'bytes':path.stat().st_size,'sha256':digest}
    write_json(OUT/'manifest.json',report)
    print(json.dumps(report['counts'],indent=2))


if __name__=='__main__':main()
