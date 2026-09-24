"""Answer-key evaluation, called only AFTER input-only pipeline output exists."""
import json
from pathlib import Path
import pandas as pd
from pipeline import run

def evaluate(result, root):
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
    root = Path(__file__).resolve().parent/'dataset'
    outputs = run(root)
    print(json.dumps(evaluate(outputs,root),indent=2))
