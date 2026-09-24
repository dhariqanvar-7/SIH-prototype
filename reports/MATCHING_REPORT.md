# BhuSetu: cross-department parcel matching

## Implemented workflow

Select **Kondapur, Hyderabad**. Click a synthetic parcel boundary on the map or
choose its ID, then open **Parcel profile**. It shows registry context and proposed
or reviewed revenue, municipal, electricity, water and survey records. Choose a
record to see its source fields, competing parcels, supporting evidence, missing
fields and contradictions. Accept, reject or leave the association pending.

**Department matching** provides the full record queue, including unmatched
records. Alternative associations above the review threshold can be accepted.
One record has at most one accepted parcel through the app review workflow;
a parcel can have many records. Accepting a different candidate supersedes the
previous acceptance in the same SQLite transaction and appends an audit entry.
Actual parcel geometry is unchanged. Exports carry synthetic flags, source records,
algorithm version, evidence and the dataset fingerprint.

The original 300 exact-ID revenue links remain a separate basic integration
fixture. They are not the evidence for the new matcher accuracy claims below.

## Dataset

1,610 fictional departmental records for 300 synthetic parcels on Kondapur's real
geographic base. Departmental addresses, accounts and survey references are
invented. Record IDs are random and do not encode the target parcel. Records do
not contain a parcel foreign key or scenario label. A parcel directory supplies the
candidate registry's survey/address attributes. Original fixture survey numbers
are retained separately in the displayed parcel data.

Cases include formatting differences, missing identifiers, missing coordinates,
address typos, wrong survey references, inflated areas, identifier-only evidence,
old records, displaced coordinates, missing village scope, outside-area records,
additional legitimate service accounts and duplicate accounts. All real-source
and synthetic labels from the geographic package remain in effect.

`departmental/inputs/` is consumed by the matcher. `departmental/evaluation_only/`
is consumed only by offline evaluation after inference. Splits are separated by
parcel (60 development / 240 test parcels); outside-area negative examples are
in test. Thresholds were fixed before evaluation and were not fitted to test data.
This is a deterministic engineering benchmark, not independent real-world validation.

## Algorithm: indexed geospatial entity resolution, version iges-er-1.0

1. Standardize administrative names, documented survey separators and address
   abbreviations. Preserve survey subdivisions. This demo's separator convention
   is not assumed universally valid across Indian jurisdictions.
2. Build scoped survey hash indexes, exact-address/rare-token inverted indexes,
   and a Shapely STRtree (packed R-tree) over valid parcel geometry.
3. For each record, union survey, address and spatial candidate sets. The spatial
   route requires actual distance within 35 m, not just intersecting bounding boxes.
   Missing district/village context is deliberately left unmatched. Common address
   tokens are ignored in token retrieval; exact address and survey postings remain.
   The retrieved set is fully scored; only the top five alternatives are displayed.
4. Score each candidate using the department weights below. Coordinate evidence
   uses point-to-parcel distance, not an inference that nearby infrastructure serves
   the land. Address evidence combines token Jaccard similarity (60%) and character
   sequence similarity (40%). Numeric plot disagreements reduce address agreement
   and block a strong proposal. Area agreement is 1 minus relative area difference,
   floored at zero. Unknown fields contribute neither agreement nor disagreement.
5. Weighted agreement is divided by the sum of available weights. Each explicit
   survey, plot or out-of-tolerance location contradiction subtracts 0.15. The score
   is floored at zero. Expose both evidence coverage and contradictions.
6. A strong proposal needs score >=0.80, lead over second place >=0.12, available
   weight >=0.50, at least two evidence groups scoring >=0.70, and no blocking
   contradiction. Score >=0.45 otherwise goes to review; lower/no candidates are
   unmatched. Identifier-only evidence can score 1.0 yet still require review.
7. Duplicate department/account keys downgrade strong proposals to review.
   Old dates and area differences remain visible warnings. Dates are not used to
   invent historical parcel geometry. Every proposed link still requires human
   acceptance before it becomes an accepted association.

| Department | Identifier | Spatial | Address | Area |
|---|---:|---:|---:|---:|
| Revenue | .45 | .25 | .15 | .15 |
| Municipal | .25 | .35 | .30 | .10 |
| Electricity / water | .20 | .35 | .40 | .05 |
| Survey | .40 | .45 | .10 | .05 |

These are explainable heuristic rankings, not probabilities or a trained AI model.
No Hungarian assignment is used because multiple records per parcel are valid.
The engineering contribution is the combined candidate routes, departmental
evidence rules, explicit abstention, and reviewable many-records-to-one-parcel
associations. The underlying indexing and similarity techniques are established;
no claim of a newly invented R-tree or scientific algorithm novelty is made.

## Measured accuracy

Held-out synthetic test: **1,294 records**, including **1,244** with a known parcel.

- Candidate recall: **90.84%**. Missing administrative scope intentionally prevents retrieval.
- Strong-proposal precision: **100.00%**, with **832** strong proposals.
- Strong-proposal recall: **66.88%** of linkable records.
- Top-ranked proposed association recall, including review cases: **88.42%**.
- Needs review: **275**; unmatched: **187**.

| Test method | Precision | Recall |
|---|---:|---:|
| id only | 89.65% | 64.07% |
| proximity only | 89.15% | 64.71% |
| Strong proposals from combined matcher | 100.00% | 66.88% |

Precision/recall trade-offs are explicit: the combined matcher abstains more
conservatively. The baselines use the same administrative scope. Their comparison
is not a proof that the combined method will generalize. An exhaustive full-score
comparison on 100 deterministic sample records produced the same top proposed
parcel decisions for all 100. See `department_accuracy.json` for per-scenario
errors, timings and denominators. A wrong identifier can still put the correct
parcel second; those cases must remain visible for review.

## Measured scale

Each size ran once in a separate process on this Windows machine. Peak working
set is whole-process resident memory, including native geometry allocations.

| Parcels | Records | Index build | Streaming scoring | Scored pairs | Peak process memory |
|---|---|---|---|---|---|
| 1,000 | 1,000 | 0.05 s | 0.86 s | 4,956 | 36.3 MB |
| 10,000 | 10,000 | 0.48 s | 8.67 s | 48,520 | 62.2 MB |
| 100,000 | 100,000 | 6.05 s | 151.17 s | 439,095 | 317.7 MB |

The 100,000 × 100,000 workload scored 439,095 pairs instead of 10 billion possible
pairs (99.9956% fewer pair scores). This is a comparison-count reduction, not a
measured speedup against running 10 billion comparisons.

The workload is a synthetic grid, scoped in groups of 1,000 parcels, with missing
IDs, typos and coordinate displacements. It is easier than the Kondapur accuracy
benchmark and does not represent irregular real records. Results measure index
construction and streaming matching, excluding file/database I/O, UI rendering,
audit writes and batch duplicate-account checks. Single runs, concurrent machine
load and cache effects limit timing comparisons. Crore-scale operation was NOT tested.

Typical per-record work is index retrieval plus scoring/sorting a candidate set,
rather than all parcels. Dense overlapping geometry or very common identifiers
can still generate large candidate sets; there is no worst-case constant bound.
The UI caches a complete small-dataset result and is not the million-record backend.

## Production deployment design (not implemented)

- Store parcel geometry in PostGIS with GiST spatial indexes; index scoped survey
  references and departmental account keys with B-trees. Add address token/trigram
  search using validated jurisdiction-specific normalization.
- Partition operational jobs by administrative area. Handle cross-boundary records
  with spatial halo queries and a reconciliation queue rather than discarding them.
- Process records in bounded batches and persist candidate/evidence results.
- Use source-version/change events to invalidate affected associations incrementally.
- Add a database constraint or association table enforcing one active parcel per
  departmental record, with audit transactions and concurrent-worker protection.
- Validate on independently labelled departmental records, calibrate thresholds by
  department, and measure candidate recall and memory under skewed/dense workloads.

## Reproduce

With the project Python environment active:

```powershell
python -m pytest -q
python evaluate_departments.py
python benchmark_matching.py --size 1000
python benchmark_matching.py --size 10000
python benchmark_matching.py --size 100000
```

`generate_departments.py` refuses to overwrite the existing benchmark. Keep the
source package and its attribution. The application can be started with `start.ps1`.
