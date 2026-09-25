"""Parcel-centred departmental evidence and reversible human review."""
import json
import pandas as pd
import streamlit as st


def approved_record_proposals(proposals, decisions):
    """Only active, approved record associations, ordered by parcel."""
    return sorted((p for p in proposals
                   if p['kind'] in {'department_link', 'record_link'}
                   and decisions.get(p['proposal_id']) in {'accepted', 'auto_approved'}),
                  key=lambda p: (p['target_id'], p['source'], p['feature_id']))


def parcel_department_proposals(departments, parcel_id, decisions):
    """Show top proposals and accepted alternatives for one selected parcel."""
    accepted_targets = {(p['source'], p['feature_id']): p['target_id']
                        for p in departments['proposals']
                        if decisions.get(p['proposal_id']) == 'accepted'}
    return sorted((p for p in departments['by_parcel'].get(parcel_id, [])
                   if (p['candidate_rank'] == 1
                       and accepted_targets.get((p['source'], p['feature_id']), parcel_id) == parcel_id)
                   or decisions.get(p['proposal_id']) in {'accepted', 'auto_approved'}),
                  key=lambda p: (p['source'], p['feature_id'], p['candidate_rank']))


def review_parcel_departments(result, current_parcel, store, decisions):
    departments = result['departments']
    st.subheader('Review department records by parcel')
    if not departments:
        st.info('This workspace has no departmental matching records.')
        return
    parcel_ids = sorted(result['originals']['parcels'].parcel_id.tolist())
    if st.session_state.get('review_last_map_parcel') != current_parcel:
        st.session_state['review_last_map_parcel'] = current_parcel
        if current_parcel in parcel_ids:
            st.session_state['review_parcel'] = current_parcel
    parcel_id = st.selectbox('Review parcel ID', parcel_ids,
        index=parcel_ids.index(current_parcel) if current_parcel in parcel_ids else 0,
        key='review_parcel')
    matches = parcel_department_proposals(departments, parcel_id, decisions)
    if not matches:
        st.info(f'No department record is currently proposed for {parcel_id}.')
        return
    rows = [dict(department=p['source'], record_id=p['feature_id'],
                 account_id=p['record'].get('account_id', ''),
                 score=p['score'], match_status=p['matching_status'],
                 decision=decisions.get(p['proposal_id'], 'pending'),
                 conflicts='; '.join(p['conflicts'])) for p in matches]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    chosen = st.selectbox('Department record on this parcel', matches,
        format_func=lambda p: f"{p['source'].title()} · {p['feature_id']} · {decisions.get(p['proposal_id'], 'pending')}",
        key='review_parcel_record')
    st.write(f"**{chosen['source'].title()} record {chosen['feature_id']} → {parcel_id}**")
    st.write(f"Current decision: **{decisions.get(chosen['proposal_id'], 'pending')}** · "
             f"Match score: **{chosen['score']}** · Evidence coverage: **{chosen.get('evidence_coverage', '—')}**")
    st.caption('Scores rank available evidence; they are not probabilities. Removing a mapping rejects this association and preserves the source record and audit history.')
    if chosen.get('same_type_record_ids'):
        st.warning('Other records of this department are proposed for this parcel: '
                   + ', '.join(chosen['same_type_record_ids']))
    if chosen['conflicts']:
        st.warning('Conflicts: ' + '; '.join(chosen['conflicts']))
    st.write('Matching evidence', chosen['evidence'])
    st.json(chosen['record'], expanded=False)
    with st.form('review_parcel_department_form'):
        reviewer = st.text_input('Parcel reviewer name')
        decision = st.radio('Parcel record decision', ['accepted', 'rejected', 'pending'],
                            horizontal=True)
        note = st.text_input('Parcel review note')
        save = st.form_submit_button('Save parcel record decision')
        remove = st.form_submit_button('Remove mapping')
        if save or remove:
            if not reviewer.strip():
                st.error('Enter a reviewer name.')
            elif remove and not note.strip():
                st.error('Enter a reason for removing the mapping.')
            else:
                store.save_proposal(result['fingerprint'], chosen,
                                    'rejected' if remove else decision,
                                    reviewer, note, result['proposals'])
                st.rerun()


def approved_records(result, store, decisions, current_parcel):
    approved = approved_record_proposals(result['proposals'], decisions)
    st.subheader('Approved Records')
    if not approved:
        st.info('No approved records in this workspace yet.')
        return

    rows = [dict(parcel_id=p['target_id'], department=p['source'],
                 record_id=p['feature_id'], account_id=p.get('record', {}).get('account_id', ''),
                 approval=decisions[p['proposal_id']], score=p.get('score'),
                 evidence_coverage=p.get('evidence_coverage')) for p in approved]
    st.caption('Each row is one approved record-to-parcel association. Match scores rank evidence; they are not calibrated probabilities.')
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    parcel_ids = sorted(result['originals']['parcels'].parcel_id.tolist())
    counts = pd.Series([p['target_id'] for p in approved]).value_counts().to_dict()
    if st.session_state.get('approved_last_map_parcel') != current_parcel:
        st.session_state['approved_last_map_parcel'] = current_parcel
        if current_parcel in parcel_ids:
            st.session_state['approved_parcel'] = current_parcel
    left, right = st.columns(2)
    with left:
        parcel_id = st.selectbox('Approved parcel ID', parcel_ids,
            index=parcel_ids.index(current_parcel) if current_parcel in parcel_ids else 0,
            format_func=lambda pid: f'{pid} · {counts.get(pid, 0)} approved record(s)',
            key='approved_parcel')
    parcel_records = [p for p in approved if p['target_id'] == parcel_id]
    if not parcel_records:
        with right:
            st.info(f'No approved records are mapped to {parcel_id}.')
        return
    with right:
        chosen = st.selectbox('Record mapped to this parcel', parcel_records,
            format_func=lambda p: f"{p['source'].title()} · {p['feature_id']} · {decisions[p['proposal_id']]}",
            key='approved_record')

    st.write(f"**{chosen['source'].title()} record {chosen['feature_id']} → {parcel_id}**")
    st.write(f"Approval: **{decisions[chosen['proposal_id']]}** · Match score: **{chosen.get('score', '—')}**")
    if chosen.get('evidence_coverage') is not None:
        st.write(f"Available evidence coverage: **{chosen['evidence_coverage']}**")
    if chosen.get('evidence'):
        st.write('Evidence scores', chosen['evidence'])
    if chosen.get('missing_evidence'):
        st.write('Missing evidence:', ', '.join(chosen['missing_evidence']))
    if chosen.get('conflicts'):
        st.warning('Conflicts: ' + '; '.join(chosen['conflicts']))
    if chosen.get('reason'):
        st.write('Matching reason:', chosen['reason'])
    st.write('Source record')
    st.json(chosen.get('record', {}), expanded=False)
    st.caption('These synthetic associations do not verify legal ownership. If you find a discrepancy, record an override below.')
    with st.form('approved_override'):
        reviewer = st.text_input('Reviewer name')
        decision = st.radio('Override approval', ['pending', 'rejected'], horizontal=True)
        note = st.text_input('Reason for override')
        if st.form_submit_button('Save override'):
            if not reviewer.strip() or not note.strip():
                st.error('Enter your name and the reason for the override.')
            else:
                store.save_proposal(result['fingerprint'], chosen, decision, reviewer, note,
                                    result['proposals'])
                st.rerun()


def rows_for_parcel(departments, parcel_id, decisions):
    return [dict(department=p['source'],record_id=p['feature_id'],account_id=p['record']['account_id'],
                 association=p['matching_status'] if p['candidate_rank']==1 else 'alternative_candidate',
                 score=p['score'],evidence_coverage=p.get('evidence_coverage'),
                 review=decisions.get(p['proposal_id'],'pending'),
                 evidence=', '.join(p['evidence']),conflicts='; '.join(p['conflicts']),
                 duplicate_account=bool(p['duplicate_record_ids']),
                 same_type_records=bool(p.get('same_type_record_ids')),synthetic=True)
            for p in departments['by_parcel'].get(parcel_id,[])
            if p['candidate_rank']==1 or decisions.get(p['proposal_id'])=='accepted']


def review_record(result, match, store, decisions, prefix):
    departments=result['departments'];record=departments['records'][match['record_id']]
    st.write(f"**{match['department'].title()} · {match['record_id']}**")
    top_approval=next((decisions.get(p['proposal_id'],'pending') for p in departments['proposals']
                       if p['feature_id']==match['record_id'] and p['candidate_rank']==1),'pending')
    if top_approval == 'auto_approved':
        st.success('Strong match automatically approved. Review the evidence below and use the decision form to revert or override it if you find a discrepancy.')
    elif match['status'] == 'strong_proposal':
        st.info(f'Strong algorithm proposal; current decision: {top_approval}. The automatic approval was overridden.')
    else:
        st.caption('Fictional departmental record. Scores rank evidence; they are not probabilities. Needs-review and unmatched records require human attention.')
    st.json(record,expanded=False)
    if match['duplicate_record_ids']:
        st.warning('This account occurs in multiple source records. Review the duplicates before confirming an association.')
    if match.get('same_type_record_ids'):
        st.warning(f"Another {match['department']} record is proposed for this parcel: "
                   + ', '.join(match['same_type_record_ids']) + '. A reviewer must decide which associations are valid.')
    if not match['candidates']:
        st.info(match['reason']+'. Correct the source data or supply administrative context before matching again.')
        return
    options=[p for p in departments['proposals'] if p['feature_id']==match['record_id']]
    st.subheader('Candidate Parcel Matches')
    st.dataframe(pd.DataFrame([{'parcel':c['parcel_id'],'score':c['score'],'available_evidence':c['coverage'],
        'evidence':json.dumps(c['evidence']),'missing':', '.join(c['missing_evidence']),
        'conflicts':'; '.join(c['conflicts']),'found_by':', '.join(c['retrieval_routes'])}
        for c in match['candidates']]),hide_index=True)
    if not options:
        st.info('Candidate evidence is below the review threshold. No association is proposed.')
        return
    selected=st.selectbox('Association to review',options,key=prefix+'_candidate',
        format_func=lambda p:f"{p['target_id']} · rank {p['candidate_rank']} · {decisions.get(p['proposal_id'],'pending')}")
    with st.form(prefix+'_form'):
        reviewer=st.text_input('Reviewer',key=prefix+'_reviewer')
        decision=st.radio('Association decision',['accepted','rejected','pending'],horizontal=True,key=prefix+'_decision')
        note=st.text_input('Evidence / review note',key=prefix+'_note')
        if st.form_submit_button('Save association decision'):
            if not reviewer.strip(): st.error('Enter your reviewer name.')
            else:
                store.save_proposal(result['fingerprint'],selected,decision,reviewer,note,result['proposals'])
                st.rerun()
    st.caption('A strong top-ranked match is auto-approved. If you find a discrepancy, choose rejected or pending and save an override. Accepting another parcel for this record supersedes its previous accepted association. Other records on the same parcel are retained.')


def profile(result, parcel_id, store, decisions):
    departments=result['departments']
    if not departments:
        st.info('Select the Kondapur workspace for cross-department matching.');return
    st.subheader(f'Land profile · {parcel_id}')
    parcel=result['originals']['parcels'].query('parcel_id == @parcel_id')
    st.dataframe(parcel[['parcel_id','district','village','survey_number','address']],hide_index=True)
    rows=rows_for_parcel(departments,parcel_id,decisions)
    st.caption('Department records mapped to this parcel, including automatically approved strong matches. Scores rank evidence; they are not probabilities. Multiple accounts per parcel are supported. These are synthetic associations, not official ownership records.')
    if not rows:
        st.info('No departmental record currently ranks this parcel first or has an accepted link.');return
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    for department in sorted({r['department'] for r in departments['results']}):
        subset=[r for r in rows if r['department']==department]
        if not subset: st.caption(f'{department.title()}: no supported record association.')
    rid=st.selectbox('Inspect departmental record',list(dict.fromkeys(r['record_id'] for r in rows)),key='profile_record')
    match=next(r for r in departments['results'] if r['record_id']==rid)
    review_record(result,match,store,decisions,'parcel_review')
    with st.expander('Building and observation evidence'):
        st.dataframe(result['candidates'][result['candidates'].parcel_id.eq(parcel_id)],hide_index=True)
        st.dataframe(result['evidence'][result['evidence'].parcel_id.eq(parcel_id)],hide_index=True)
    if not result['utility_evidence'].empty:
        with st.expander('Nearby synthetic utility features'):
            st.caption('Spatial context only. Utility feature connection IDs do not join the fictional departmental account IDs, so proximity does not confirm service to this parcel.')
            st.dataframe(result['utility_evidence'][result['utility_evidence'].parcel_id.eq(parcel_id)],hide_index=True)
    st.download_button('Download this parcel profile',json.dumps({'parcel_id':parcel_id,'synthetic_parcel':True,
        'dataset_fingerprint':result['fingerprint'],'associations':rows},indent=2),f'{parcel_id}_profile.json','application/json')


def queue(result,store,decisions):
    departments=result['departments']
    if not departments:
        st.info('Select the Kondapur workspace for departmental records.');return
    stats=departments['stats'];a,b,c,d=st.columns(4)
    a.metric('Departmental records',stats['records'])
    b.metric('Need review',stats['status_counts'].get('needs_review',0))
    c.metric('Unmatched',stats['status_counts'].get('unmatched',0))
    d.metric('Auto-approved',sum(v=='auto_approved' for v in decisions.values()))
    departments_available=sorted({r['department'] for r in departments['results']})
    department=st.selectbox('Department',['all',*departments_available])
    status=st.selectbox('Matching outcome',['all','strong_proposal','needs_review','unmatched'])
    items=[r for r in departments['results'] if (department=='all' or r['department']==department)
           and (status=='all' or r['status']==status)]
    top_proposals={p['feature_id']:p['proposal_id'] for p in departments['proposals'] if p['candidate_rank']==1}
    st.dataframe(pd.DataFrame([{**{k:r[k] for k in ['record_id','department','status','proposed_parcel_id','score','margin','candidate_count']},
                                'review_decision': decisions.get(top_proposals.get(r['record_id'],''),'pending')}
                               for r in items]),hide_index=True)
    if items:
        chosen=st.selectbox('Departmental record',items,format_func=lambda r:f"{r['department']} / {r['record_id']} · {r['status']}")
        review_record(result,chosen,store,decisions,'queue_review')
    st.download_button('Download matching results',json.dumps(departments['results'],indent=2),
                       'department_matching.json','application/json')
