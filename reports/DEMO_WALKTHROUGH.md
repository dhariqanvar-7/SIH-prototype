# SIH demonstration: select land and reconcile departmental records

Open http://127.0.0.1:8501/ and keep **Kondapur, Hyderabad** selected.
All departmental records in this demonstration are clearly labelled synthetic.

1. **Unified profile and a strong association**
   Select `SYN-P0060` in Map & evidence, then open Parcel profile.
   Inspect `SYN-0461BE42FA7DBEBD` (water). Explain the available
   evidence and that a strong proposal is still pending human review. Show the
   original record, candidate explanations and review controls.
2. **Ambiguity rather than a forced link**
   Open Department matching, choose `revenue` and `needs_review`,
   then find `SYN-C2FE862275B593D9`. The top candidates have equal scores.
   A score alone is insufficient: the margin and evidence requirements prevent
   automatic confidence claims.
3. **Reject a contradictory association**
   Find `SYN-B1D235CEF5D793AC` (water) in the review queue.
   Inspect its candidate table; choose an association whose evidence contradicts
   the record. A reviewer can reject it with a reason. Decisions are reversible
   and appended to the audit. Do not portray a rejection as an ownership ruling.
4. **Multiple accounts on one parcel**
   Select `SYN-P0001` and open Parcel profile. The generator includes extra
   electricity/water accounts on this parcel. Different accounts can coexist;
   same-account duplicate source records are separately flagged for review.
5. **No supported association**
   Filter for unmatched and inspect `SYN-49655225731EB48F`.
   Explain the stated reason rather than inventing a parcel match.
6. **Review and export**
   After a deliberate test review, export the parcel profile, integrated GeoJSON
   and audit. Accepting a different parcel for the same record replaces its prior
   accepted association while keeping unrelated departmental records intact.

## Algorithm answer for reviewers

“We use indexed geospatial entity resolution: scoped identifier hash indexes,
a spatial R-tree and address-token candidate retrieval, followed by explicit
per-department evidence scoring, contradiction checks and human review.
A parcel may have multiple departmental records. We avoid exhaustive pairwise
comparison and preserve an auditable explanation for every proposed link.”

## Claims supported by measurements

- 1,610 synthetic records, 300 parcels: 7,118 scored pairs versus 483,000 possible.
- Held-out synthetic strong-proposal precision 100%, recall 66.88%; candidate
  recall 90.84%. Missing scope and ambiguous evidence remain unresolved.
- One local scale experiment: 100,000 records × 100,000 synthetic grid parcels,
  439,095 scored pairs, approximately 6 s indexing + 151 s streaming matching,
  approximately 318 MB peak process working set.
- Fourteen tests passed. No real departmental accuracy, calibrated probability,
  new scientific algorithm, automated ownership decision, or crore-scale result
  is claimed. Scale timing excludes database I/O, UI, audit and batch duplicates.

The proposed production design uses PostGIS, administrative partitioning,
batches and incremental updates. Those production components are not implemented.
See MATCHING_REPORT.md and the JSON reports for exact methods and limitations.
