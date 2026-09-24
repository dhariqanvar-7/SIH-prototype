"""One-time metadata correction; never modifies input or answer-key data."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
EXTRA = '''
## Ingestion notes
- legacy_parcels_no_crs.geojson is an intentionally nonstandard GeoJSON fixture:
  projected coordinates with unknown source CRS. Quarantine until explicit confirmation.
- Ground-truth observations are polygon observation areas (0.5 m buffers), not points.
- GNSS easting/northing use EPSG:32643 and metres. Survey date is unknown.
- Extracted building acquisition dates: T1 2024-11-15; T2 2025-11-20.
- GNSS reported accuracy is not an independently measured absolute accuracy.
'''

def main():
    path = ROOT / 'generate_dataset.py'
    src = path.read_text(encoding='utf-8')
    src = src.replace('GT point id', 'Observation-area polygon id')
    src = src.replace('Projected easting (m)', 'EPSG:32643 easting (metres); survey date unknown')
    src = src.replace('Projected northing (m)', 'EPSG:32643 northing (metres); survey date unknown')
    marker = '        man["files"].append(entry)'
    correction = '''        if p.name == "legacy_parcels_no_crs.geojson":
            entry["crs"] = None
            entry["crs_status"] = "unknown; quarantine pending explicit confirmation"
            entry["note"] = "Intentionally nonstandard GeoJSON with projected coordinates"
        if p.name == "gnss_observations.csv":
            entry.update(crs=CRS_PROJ, units="metres", acquisition_date=None)
        if p.name == "ground_truth_observations.geojson":
            entry["note"] = "Polygon observation areas, 0.5 metre buffers; not points"
        if p.name in {"extracted_buildings_t1.geojson", "extracted_buildings_t2.geojson"}:
            entry["acquisition_date"] = T1_DATE if "t1" in p.name else T2_DATE
'''
    if correction not in src:
        src = src.replace(marker, correction + marker)
        src = src.replace('def write_data_dictionary(root: Path) -> None:',
            'def write_data_dictionary(root: Path) -> None:')
        src = src.replace('\n\ndef write_data_dictionary',
            '\n    with (root / "README.md").open("a", encoding="utf-8") as f:\n        f.write(' + repr(EXTRA) + ')\n\ndef write_data_dictionary')
    # Avoid the generator's destructive overwrite behavior on an existing dataset.
    src = src.replace('    if root.exists():\n        shutil.rmtree(root)',
        '    if root.exists():\n        raise FileExistsError("Choose a new output directory; existing datasets are preserved")')
    path.write_text(src, encoding='utf-8')
    shutil.copy2(path, ROOT / 'dataset/generate_dataset.py')
    import importlib.util
    spec = importlib.util.spec_from_file_location('generator', path)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    dataset = ROOT / 'dataset'
    old = json.loads((dataset / 'manifest.json').read_text())
    gen.write_readme(dataset)
    gen.write_data_dictionary(dataset)
    gen.write_manifest(dataset, gen.dataset_signature(dataset), old['expected_counts'])
    updated = json.loads((dataset / 'manifest.json').read_text())
    updated['generated_utc'] = old['generated_utc']
    updated['metadata_correction'] = 'CRS, observation geometry, units and acquisition dates corrected; inputs unchanged'
    (dataset / 'manifest.json').write_text(json.dumps(updated, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
