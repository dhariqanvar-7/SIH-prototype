"""Answer-key evaluation, called only AFTER input-only pipeline output exists."""
import json
from pathlib import Path
import pandas as pd
from pipeline import run
from data_sources import is_kondapur

def evaluate(result, root):
    if is_kondapur(root):
        truth = pd.read_csv(Path(root)/'synthetic_benchmark/evaluation_only/expected_record_matches.csv')
        predicted = result['links'].query("source == 'revenue'")
        merged = predicted.merge(truth, left_on='feature_id', right_on='record_id')
        expected_area = set(truth.loc[truth.area_mismatch, 'record_id'])
        found_area = set(result['conflicts'].loc[result['conflicts'].kind.eq('area_disagreement'),'feature_id'])
        return {'benchmark':'Kondapur synthetic record benchmark on real geography',
                'record_links_predicted':len(predicted),'record_links_truth':len(truth),
                'correct_record_links':int(merged.parcel_id.eq(merged.expected_parcel_id).sum()),
                'area_mismatch_true_positives':len(expected_area & found_area),
                'area_mismatch_false_positives':len(found_area - expected_area),
                'area_mismatch_false_negatives':len(expected_area - found_area),
                'temporal_evaluation':'Unavailable: one footprint snapshot with unknown imagery dates',
                'note':'Synthetic identifier/area checks do not establish real cadastral accuracy. Building association and positional correction accuracy are not scored.'}
    truth = pd.read_csv(Path(root)/'evaluation_only/record_links.csv',keep_default_na=False)
    truth['source'] = truth.source_file.str.replace('inputs/','',regex=False).str.replace('.csv','',regex=False)
    merged = result['links'].merge(truth,left_on=['source','feature_id'],right_on=['source','source_feature_id'],suffixes=('_predicted','_truth'))
    expected = pd.read_csv(Path(root)/'evaluation_only/expected_changes.csv')
    return {'record_links_predicted':len(result['links']), 'record_links_truth':len(truth),
            'correct_record_links':int(merged.parcel_id_predicted.eq(merged.parcel_id_truth).sum()),
            'predicted_change_counts':result['changes'].change.value_counts().to_dict(),
            'expected_change_counts':expected.change_type.value_counts().to_dict(),
            'note':'Change counts are descriptive, not precision/recall; spatial truth association is not scored.',
            'invalid_input_geometries':int((~result['validation'].valid).sum()),
            'conflicts':result['conflicts'].kind.value_counts().to_dict()}

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--legacy', action='store_true', help='Evaluate the earlier synthetic demonstration')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent/'dataset'
    if not args.legacy:
        root = root/'hyderabad_kondapur'
    outputs = run(root)
    print(json.dumps(evaluate(outputs,root),indent=2))
