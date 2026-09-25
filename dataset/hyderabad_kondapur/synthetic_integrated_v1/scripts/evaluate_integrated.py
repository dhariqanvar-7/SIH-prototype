"""Departmental matching evaluation for synthetic_integrated_v1.

Inference reads ONLY `inputs/`. The answer key in `evaluation_only/` is opened
after inference finishes, exactly as in `evaluate_departments.py`.

    python dataset/hyderabad_kondapur/synthetic_integrated_v1/scripts/evaluate_integrated.py

Writes reports/integrated_accuracy.json (repo-level reports directory).
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import geopandas as gpd

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[2]
sys.path.insert(0, str(REPO))

from departmental import load_integrated_inputs  # noqa: E402
from entity_resolution import Resolver  # noqa: E402

METRIC_CRS = "EPSG:32644"


def main() -> None:
    started = time.perf_counter()
    parcels = gpd.read_file(PACKAGE / "inputs/parcels.geojson").to_crs(METRIC_CRS)
    entries, records = load_integrated_inputs(PACKAGE, parcels)
    engine = Resolver(entries)
    results, stats = engine.resolve(records)  # Inputs first; answers only afterward.

    answers = json.loads((PACKAGE / "evaluation_only/answers.json").read_text(encoding="utf-8"))
    truth = {row["record_id"]: row for row in answers}
    records_by_id = {r["record_id"]: r for r in records}

    metrics = {}
    for split in ("development", "test"):
        selected = [r for r in results if truth[r["record_id"]]["split"] == split]
        linkable = [r for r in selected if truth[r["record_id"]]["expected_parcel_id"]]
        strong = [r for r in selected if r["status"] == "strong_proposal"]
        correct = sum(r["proposed_parcel_id"] == truth[r["record_id"]]["expected_parcel_id"]
                      for r in strong)
        metrics[split] = {
            "records": len(selected),
            "linkable_records": len(linkable),
            "strong_proposals": len(strong),
            "candidate_recall": round(sum(truth[r["record_id"]]["expected_parcel_id"] in r["candidate_ids"]
                                          for r in linkable) / max(1, len(linkable)), 6),
            "strong_precision": round(correct / max(1, len(strong)), 6),
            "strong_recall": round(correct / max(1, len(linkable)), 6),
            "top1_recall": round(sum(r["proposed_parcel_id"] == truth[r["record_id"]]["expected_parcel_id"]
                                     for r in linkable) / max(1, len(linkable)), 6),
            "review_records": sum(r["status"] == "needs_review" for r in selected),
            "unmatched_records": sum(r["status"] == "unmatched" for r in selected),
        }

    per_department = {}
    for department in sorted({r["department"] for r in records}):
        selected = [r for r in results if r["department"] == department]
        linkable = [r for r in selected if truth[r["record_id"]]["expected_parcel_id"]]
        strong = [r for r in selected if r["status"] == "strong_proposal"]
        correct = sum(r["proposed_parcel_id"] == truth[r["record_id"]]["expected_parcel_id"]
                      for r in strong)
        per_department[department] = {
            "records": len(selected),
            "strong_proposals": len(strong),
            "strong_precision": round(correct / max(1, len(strong)), 6),
            "strong_recall": round(correct / max(1, len(linkable)), 6),
            "top1_recall": round(sum(r["proposed_parcel_id"] == truth[r["record_id"]]["expected_parcel_id"]
                                     for r in linkable) / max(1, len(linkable)), 6),
            "unmatched": sum(r["status"] == "unmatched" for r in selected),
        }

    scenarios = defaultdict(lambda: dict(records=0, retrieved=0, top1_correct=0, strong_wrong=0))
    for result in results:
        label = truth[result["record_id"]]["scenario"]
        bucket = scenarios[label]
        expected = truth[result["record_id"]]["expected_parcel_id"]
        bucket["records"] += 1
        bucket["retrieved"] += int(bool(expected) and expected in result["candidate_ids"])
        bucket["top1_correct"] += int(bool(expected) and result["proposed_parcel_id"] == expected)
        bucket["strong_wrong"] += int(result["status"] == "strong_proposal"
                                      and result["proposed_parcel_id"] != expected)

    account_keys = defaultdict(list)
    for record in records:
        if record.get("account_id"):
            account_keys[(record["department"], record["account_id"])].append(record["record_id"])
    duplicate_accounts = sum(len(g) - 1 for g in account_keys.values() if len(g) > 1)

    corrupted = sum(
        truth[r["record_id"]]["scenario"] not in
        {"clean_exact_match", "multiple_accounts_one_parcel"}
        for r in results)

    report = {
        "dataset": "dataset/hyderabad_kondapur/synthetic_integrated_v1",
        "workload": "Synthetic parcels and fictional departmental records; not real departmental accuracy",
        "policy": "Fixed engineering thresholds, not trained or probability-calibrated. Test split not used for tuning.",
        "runtime": {**stats, "wall_seconds": round(time.perf_counter() - started, 3),
                    "algorithm_version": stats["algorithm_version"]},
        "splits": metrics,
        "per_department": per_department,
        "test_scenarios": dict(scenarios),
        "duplicates": {"duplicate_account_records": duplicate_accounts,
                       "duplicate_account_scenario": sum(bool(truth[r["record_id"]]["scenario"] ==
                                                              "duplicate_account") for r in results)},
        "intentionally_corrupted_records": corrupted,
        "unmatched_records": sum(r["status"] == "unmatched" for r in results),
        "candidate_pairs_after_blocking": stats["candidate_pairs"],
        "exhaustive_pairs": stats["exhaustive_pairs"],
        "recordless_parcels": len(json.loads(
            (PACKAGE / "evaluation_only/parcels_without_records.json").read_text(encoding="utf-8"))),
        "records_without_operational_parcel_id": all(
            "parcel_id" not in records_by_id[r["record_id"]] for r in results),
        "notice": "Synthetic demonstration data for TRL 3 evaluation; not official cadastral or ownership data.",
    }
    out = REPO / "reports"
    out.mkdir(exist_ok=True)
    (out / "integrated_accuracy.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
