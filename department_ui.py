"""Parcel-centred departmental evidence and reversible human review."""
import json
import pandas as pd
import streamlit as st


def rows_for_parcel(departments, parcel_id, decisions):
    return [dict(department=p['source'],record_id=p['feature_id'],account_id=p['record']['account_id'],
                 association=p['matching_status'] if p['candidate_rank']==1 else 'alternative_candidate',
                 score=p['score'],review=decisions.get(p['proposal_id'],'pending'),
                 evidence=', '.join(p['evidence']),conflicts='; '.join(p['conflicts']),
                 duplicate_account=bool(p['duplicate_record_ids']),synthetic=True)
            for p in departments['by_parcel'].get(parcel_id,[])
            if p['candidate_rank']==1 or decisions.get(p['proposal_id'])=='accepted']


def review_record(result, match, store, decisions, prefix):
    departments=result['departments'];record=departments['records'][match['record_id']]
    st.write(f"**{match['department'].title()} · {match['record_id']}**")
    st.caption('Fictional departmental record. Scores rank evidence; they are not probabilities. Nothing is confirmed until reviewed.')
    st.json(record,expanded=False)
    if match['duplicate_record_ids']:
        st.warning('This account occurs in multiple source records. Review the duplicates before confirming an association.')
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
    st.caption('Accepting another parcel for this record supersedes its previous accepted association. Other records on the same parcel are retained.')


def profile(result, parcel_id, store, decisions):
    departments=result['departments']
    if not departments:
        st.info('Select the Kondapur workspace for cross-department matching.');return
    st.subheader(f'Land profile · {parcel_id}')
    parcel=result['originals']['parcels'].query('parcel_id == @parcel_id')
    st.dataframe(parcel[['parcel_id','district','village','survey_number','address']],hide_index=True)
    rows=rows_for_parcel(departments,parcel_id,decisions)
    st.caption('Proposed and reviewed records for the land selected on the map. Multiple accounts per parcel are supported. These are synthetic associations, not official ownership records.')
    if not rows:
        st.info('No departmental record currently ranks this parcel first or has an accepted link.');return
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    for department in ['revenue','municipal','electricity','water','survey']:
        subset=[r for r in rows if r['department']==department]
        if not subset: st.caption(f'{department.title()}: no supported record association.')
    rid=st.selectbox('Inspect departmental record',list(dict.fromkeys(r['record_id'] for r in rows)),key='profile_record')
    match=next(r for r in departments['results'] if r['record_id']==rid)
    review_record(result,match,store,decisions,'parcel_review')
    with st.expander('Building and observation evidence'):
        st.dataframe(result['candidates'][result['candidates'].parcel_id.eq(parcel_id)],hide_index=True)
        st.dataframe(result['evidence'][result['evidence'].parcel_id.eq(parcel_id)],hide_index=True)
    st.download_button('Download this parcel profile',json.dumps({'parcel_id':parcel_id,'synthetic_parcel':True,
        'dataset_fingerprint':result['fingerprint'],'associations':rows},indent=2),f'{parcel_id}_profile.json','application/json')


def queue(result,store,decisions):
    departments=result['departments']
    if not departments:
        st.info('Select the Kondapur workspace for departmental records.');return
    stats=departments['stats'];a,b,c=st.columns(3)
    a.metric('Departmental records',stats['records'])
    b.metric('Need review',stats['status_counts'].get('needs_review',0))
    c.metric('Unmatched',stats['status_counts'].get('unmatched',0))
    department=st.selectbox('Department',['all','revenue','municipal','electricity','water','survey'])
    status=st.selectbox('Matching outcome',['all','strong_proposal','needs_review','unmatched'])
    items=[r for r in departments['results'] if (department=='all' or r['department']==department)
           and (status=='all' or r['status']==status)]
    st.dataframe(pd.DataFrame([{k:r[k] for k in ['record_id','department','status','proposed_parcel_id','score','margin','candidate_count']} for r in items]),hide_index=True)
    if items:
        chosen=st.selectbox('Departmental record',items,format_func=lambda r:f"{r['department']} / {r['record_id']} · {r['status']}")
        review_record(result,chosen,store,decisions,'queue_review')
    st.download_button('Download matching results',json.dumps(departments['results'],indent=2),
                       'department_matching.json','application/json')
