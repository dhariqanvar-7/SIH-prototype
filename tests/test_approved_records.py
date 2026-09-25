from department_ui import approved_record_proposals, parcel_department_proposals
from review import ReviewStore, effective_decisions


def test_approved_records_include_manual_and_auto_but_exclude_reverted():
    proposals = [
        dict(proposal_id='auto', kind='department_link', source='water',
             feature_id='R1', target_id='P2'),
        dict(proposal_id='manual', kind='department_link', source='revenue',
             feature_id='R2', target_id='P1'),
        dict(proposal_id='direct', kind='record_link', source='revenue',
             feature_id='R3', target_id='P1'),
        dict(proposal_id='reverted', kind='department_link', source='municipal',
             feature_id='R4', target_id='P1'),
        dict(proposal_id='building', kind='building_link', source='buildings',
             feature_id='B1', target_id='P1'),
    ]
    decisions = dict(auto='auto_approved', manual='accepted', direct='accepted',
                     reverted='rejected', building='accepted')
    selected = approved_record_proposals(proposals, decisions)
    assert [p['proposal_id'] for p in selected] == ['manual', 'direct', 'auto']


def test_parcel_first_review_and_remove_mapping_keep_an_audit(tmp_path):
    top = dict(proposal_id='top', kind='department_link', source='water',
               feature_id='R1', target_id='P1', candidate_rank=1,
               matching_status='strong_proposal')
    alternative = dict(top, proposal_id='alternative', target_id='P2', candidate_rank=2)
    other = dict(top, proposal_id='other', source='revenue', feature_id='R2')
    proposals = [top, alternative, other]
    departments = {'proposals': proposals,
                   'by_parcel': {'P1': [top, other], 'P2': [alternative]}}
    store = ReviewStore(tmp_path / 'reviews.sqlite')
    decisions = effective_decisions(proposals, store.decisions('dataset'))
    assert {p['proposal_id'] for p in parcel_department_proposals(departments, 'P1', decisions)} == {'top', 'other'}

    store.save_proposal('dataset', top, 'rejected', 'Reviewer', 'Wrong parcel', proposals)
    decisions = effective_decisions(proposals, store.decisions('dataset'))
    assert decisions['top'] == 'rejected'
    assert top not in approved_record_proposals(proposals, decisions)
    assert len(store.audit('dataset')) == 1

    store.save_proposal('dataset', alternative, 'accepted', 'Reviewer', 'Verified alternative', proposals)
    decisions = effective_decisions(proposals, store.decisions('dataset'))
    assert 'top' not in {p['proposal_id'] for p in parcel_department_proposals(departments, 'P1', decisions)}
    assert 'alternative' in {p['proposal_id'] for p in parcel_department_proposals(departments, 'P2', decisions)}
