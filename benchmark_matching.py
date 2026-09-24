"""Measured synthetic scale experiment, separate from accuracy evaluation.

Run one size per fresh process for meaningful peak process memory.
Example: python benchmark_matching.py --size 100000
"""
import argparse
import ctypes
from ctypes import wintypes
import json
import math
import platform
import sys
import time
from pathlib import Path
from shapely.geometry import box
from entity_resolution import Resolver, VERSION


def peak_memory_mb():
    if sys.platform!='win32':
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024 if sys.platform!='darwin' else 1024**2)
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in
            ['PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
             'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage']]
    data=Counters();data.cb=ctypes.sizeof(data)
    kernel=ctypes.windll.kernel32;kernel.GetCurrentProcess.restype=wintypes.HANDLE
    fn=ctypes.windll.psapi.GetProcessMemoryInfo
    fn.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    if not fn(kernel.GetCurrentProcess(),ctypes.byref(data),data.cb): return None
    return data.PeakWorkingSetSize/1024**2


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--size',type=int,default=1000)
    args=parser.parse_args();n=args.size
    if n<=0: raise ValueError('size must be positive')
    width=math.ceil(math.sqrt(n));parcels=[]
    for i in range(n):
        x=200000+(i%width)*40;y=1900000+(i//width)*40
        parcels.append(dict(parcel_id=f'P{i}',district='SCALE',village=f'V{i//1000}',
            survey_number=f'{i%1000}/A',address=f'Plot {i+1} Scale Street',geometry=box(x,y,x+30,y+30)))
    engine=Resolver(parcels);started=time.perf_counter();pairs=0;maximum=0;counts={};correct=0
    for i,p in enumerate(parcels):
        pos=p['geometry'].centroid
        record=dict(record_id=f'R{i}',department='municipal',district=p['district'],village=p['village'],
            survey_number=p['survey_number'] if i%3 else '',address=p['address'].replace('Street','Stret' if i%7==0 else 'Street'),
            easting_m=pos.x+(12 if i%11==0 else 0),northing_m=pos.y,
            recorded_area_m2=900,crs='EPSG:32644',synthetic=True)
        result=engine.match(record)
        pairs+=result['candidate_count'];maximum=max(maximum,result['candidate_count'])
        counts[result['status']]=counts.get(result['status'],0)+1
        correct+=result['proposed_parcel_id']==p['parcel_id']
    seconds=time.perf_counter()-started
    report={'algorithm_version':VERSION,'parcels':n,'records':n,'index_seconds':engine.index_seconds,
            'streaming_query_seconds':seconds,'records_per_second':n/seconds,'candidate_pairs':pairs,
            'exhaustive_pairs':n*n,'average_candidates':pairs/n,'max_candidates':maximum,
            'pair_reduction_fraction':1-pairs/(n*n),'peak_process_working_set_mb':peak_memory_mb(),
            'status_counts':counts,'top1_correct':correct,'python':platform.python_version(),'platform':platform.platform(),
            'workload':'Synthetic 30 m grid parcels on 40 m spacing, administrative blocks of 1000 parcels; missing IDs, address typos and displaced points.',
            'limits':'Measures one-process index construction and streaming record matching only. Excludes file/database I/O, UI, audit writes and cross-record duplicate checks. Not a crore-scale or production benchmark.'}
    out=Path(__file__).resolve().parent/'reports';out.mkdir(exist_ok=True)
    (out/f'scale_{n}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
