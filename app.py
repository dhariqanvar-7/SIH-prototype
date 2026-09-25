from pathlib import Path
import json
import re
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from pipeline import run, fingerprint
from entity_resolution import REVIEW_POLICY_VERSION
from review import ReviewStore, effective_decisions, export_geojson
from raster_layers import overlay
from department_ui import profile, queue, approved_records, review_parcel_departments

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='BhuSetu | Urban land integration',page_icon='🌐',layout='wide')
st.title('BhuSetu')
st.caption('SIH 26013 · Urban land integration')
workspace = st.sidebar.selectbox('Dataset',
    ['Kondapur · Integrated synthetic v1', 'Kondapur, Hyderabad · Earlier demo', 'Legacy synthetic demo'],
    key='workspace')
root = (ROOT/'dataset/hyderabad_kondapur/synthetic_integrated_v1'
        if workspace == 'Kondapur · Integrated synthetic v1' else
        ROOT/'dataset/hyderabad_kondapur'
        if workspace == 'Kondapur, Hyderabad · Earlier demo' else ROOT/'dataset')

@st.cache_data
def load(path, signature, review_policy_version):
    return run(Path(path))

result = load(str(root), fingerprint(root), REVIEW_POLICY_VERSION)
st.caption(result['dataset_name'])
if result['raster_paths']:
    st.info('Real Microsoft buildings and OpenStreetMap features, with synthetic parcels and fictional records. Survey and verification observations are simulated.')
store = ReviewStore(ROOT/'state/reviews.sqlite')
decisions = effective_decisions(result['proposals'], store.decisions(result['fingerprint']))
st.sidebar.header('Workspace')
st.sidebar.caption(f"{result['metric_crs']} · distances and areas in metres")
for message in result['quarantine']:
    st.sidebar.info(message)
if result['quarantine']:
    st.sidebar.caption('Legacy geometry stays excluded until its source coordinate system is confirmed.')
st.sidebar.warning('Heuristic scores are evidence rankings, not probabilities. Accepted repairs do not establish legal cadastral accuracy.')
a,b,c,d = st.columns(4)
a.metric('Parcels',len(result['originals']['parcels']))
b.metric('Conflicts',len(result['conflicts']))
c.metric('Review proposals',len(result['proposals']))
d.metric('Approved',sum(v in {'accepted','auto_approved'} for v in decisions.values()))
maptab, profiletab, departmenttab, approvedtab, reviewtab, changetab, datatab, exporttab = st.tabs(['Map & evidence','Parcel profile','Department matching','Approved Records','Review queue','Building changes','Validation','Export'])
with maptab:
    ids = list(result['originals']['parcels'].parcel_id)
    pending = st.session_state.pop('pending_parcel',None)
    if pending in ids:
        st.session_state['selected_parcel'] = pending
    if st.session_state.get('selected_parcel') not in ids:
        st.session_state['selected_parcel'] = ids[0]
    selected = st.selectbox('Inspect parcel',ids,key='selected_parcel')
    shown = st.multiselect('Visible layers',list(result['layers']),default=['parcels','buildings','roads'] if result['raster_paths'] else ['parcels','t2','utilities','observations'], format_func=lambda k:result['layer_labels'].get(k,k))
    raster_shown = st.multiselect('Raster layers',list(result['raster_paths']),default=['Satellite imagery']) if result['raster_paths'] else []
    p = result['originals']['parcels']
    center = p.to_crs(4326).geometry.union_all().centroid if p.geometry.is_valid.all() else p.to_crs(4326).geometry.iloc[0].centroid
    m = folium.Map(location=[center.y,center.x],zoom_start=17,tiles=None)
    folium.TileLayer('OpenStreetMap',show=False).add_to(m)
    for name in raster_shown:
        image, bounds, note = overlay(result['raster_paths'][name], elevation=name=='Surface elevation')
        folium.raster_layers.ImageOverlay(image, bounds=bounds, name=name, opacity=.8, mercator_project=True,
            attribution='Contains modified Copernicus Sentinel data (2025) / Copernicus DEM').add_to(m)
        st.caption(note)
    colors = dict(parcels='#64748b',t1='#f59e0b',t2='#0d9488',buildings='#0d9488',
                  roads='#f59e0b',landuse='#22c55e',amenities='#e879f9',other_features='#38bdf8',
                  observations='#a855f7',utilities='#ef4444',synthetic_utilities='#fb7185',
                  utility_points='#fb7185',utility_lines='#fb7185',gnss='#2563eb')
    for name in shown:
        frame = result['originals'].get(name,result['layers'][name]).to_crs(4326)
        fields = [x for x in frame.columns if x!='geometry']
        if frame.empty:
            continue
        folium.GeoJson(json.loads(frame.to_json()),name=result['layer_labels'].get(name,name),
            marker=folium.CircleMarker(radius=5),
            style_function=lambda feature,color=colors.get(name, '#0d9488'):{'color':color,'weight':2,'fillOpacity':.18},
            tooltip=folium.GeoJsonTooltip(fields=fields)).add_to(m)
    focus = p[p.parcel_id.eq(selected)].to_crs(4326)
    folium.GeoJson(json.loads(focus.to_json()),name='Selected parcel',style_function=lambda f:{'color':'#f43f5e','weight':4,'fillOpacity':.05}).add_to(m)
    folium.LayerControl().add_to(m)
    clicked = st_folium(m,height=520,use_container_width=True,key='land-map-'+workspace, returned_objects=['last_object_clicked_tooltip','last_object_clicked'])
    tooltip = (clicked or {}).get('last_object_clicked_tooltip') or ''
    match = re.search(r'SYN-P[0-9]{4}',tooltip)
    click_signature = json.dumps([(clicked or {}).get('last_object_clicked'),tooltip])
    if match and click_signature != st.session_state.get('last_parcel_click'):
        st.session_state['last_parcel_click'] = click_signature
        if match[0] in ids and match[0] != selected:
            st.session_state['pending_parcel'] = match[0]
            st.rerun()
    st.caption('Click a parcel boundary or choose its ID above, then open Parcel profile for departmental records and evidence. Basemap is optional.')
    st.dataframe(p[p.parcel_id.eq(selected)].drop(columns='geometry'),hide_index=True)
    st.dataframe(result['candidates'][result['candidates'].parcel_id.eq(selected)],hide_index=True)
    st.dataframe(result['evidence'][result['evidence'].parcel_id.eq(selected)],hide_index=True)
    st.caption('GNSS coordinates and verification records are simulated. Reference answers are reserved for offline evaluation.' if result['raster_paths'] else 'GNSS points have no corresponding reference-point IDs; reported accuracy does not measure absolute positional accuracy.')
    if result['raster_paths']:
        st.caption('Buildings: Microsoft, CDLA Permissive 2.0. Map features: © OpenStreetMap contributors, ODbL. Imagery: modified Copernicus Sentinel data (2025). Elevation: Copernicus DEM. Synthetic layers retain upstream provenance.')
with profiletab:
    profile(result,selected,store,decisions)
with departmenttab:
    queue(result,store,decisions)
with approvedtab:
    approved_records(result,store,decisions,selected)
with reviewtab:
    review_parcel_departments(result,selected,store,decisions)
    with st.expander('Other proposals and conflicts'):
        st.dataframe(result['conflicts'],hide_index=True,use_container_width=True)
        kind = st.selectbox('Proposal type',sorted({p['kind'] for p in result['proposals']}))
        status = st.selectbox('Review status',['all','pending','auto_approved','accepted','rejected'])
        items = [p for p in result['proposals'] if p['kind']==kind and (status=='all' or decisions.get(p['proposal_id'],'pending')==status)]
        if items:
            item = st.selectbox('Proposal',items,format_func=lambda p:f"{p['source']} / {p['feature_id']} → {p['target_id']} [{decisions.get(p['proposal_id'],'pending')}]")
            st.json(item)
            st.caption('Building scores combine overlap, proximity and area fit. Baseline record links use exact normalized IDs; departmental links use multiple evidence fields and contradiction checks. Scores are not probabilities.')
            with st.form('review'):
                reviewer = st.text_input('Reviewer name',value='Demo reviewer')
                decision = st.radio('Decision',['accepted','rejected','pending'],horizontal=True)
                note = st.text_input('Review note')
                if st.form_submit_button('Save decision'):
                    if reviewer.strip():
                        store.save_proposal(result['fingerprint'],item,decision,reviewer,note,result['proposals'])
                        st.rerun()
                    else: st.error('Enter a reviewer name.')
        else: st.info('No proposals match this filter.')
with changetab:
    if result['temporal_available']:
        st.subheader('2024-11-15 → 2025-11-20')
        st.dataframe(result['changes'],hide_index=True,use_container_width=True)
        st.caption('Spatial matching compares two synthetic snapshots. Unmatched detections are possible additions/removals; extraction errors can mimic change.')
    else:
        st.info('Building change analysis is unavailable: this dataset contains one Microsoft footprint snapshot with unknown imagery dates. A second comparable dated snapshot is required.')
with datatab:
    st.dataframe(result['validation'],hide_index=True,use_container_width=True)
    if not result['provenance'].empty:
        st.subheader('Sources and data status')
        st.dataframe(result['provenance'],hide_index=True)
        st.caption('Official cadastral exports, actual field observations and complete utility networks have not been acquired. Synthetic substitutes support benchmark testing only.')
        st.caption('Imagery and the 30 m surface model provide context; they cannot validate precise parcel boundaries or individual-building heights.')
        st.subheader('Raster coverage')
        st.write(f"Satellite acquisition: {result['raster_metadata']['acquisition_datetime']}")
        st.caption('All AOI pixel centres contain valid imagery and elevation. The scene quality mask flags no cloud or shadow pixels inside the study boundary; this is not independent field validation.')
    if result['departments']:
        st.subheader('Indexed matching performance')
        stats = result['departments']['stats']
        st.write(f"Scored {stats['candidate_pairs']:,} candidate pairs instead of {stats['exhaustive_pairs']:,} exhaustive pairs.")
        st.caption('Scoped identifier indexes + spatial R-tree + address-token retrieval. Department-specific evidence scoring. Timings measure this local dataset, not crore-scale operation.')
        st.json(stats,expanded=False)
    st.subheader('Quarantined sources')
    st.write(result['quarantine'])
    st.caption('Original source files remain unchanged. Repairs are proposed via Shapely make_valid. No ownership or legal boundary correction is automatic.')
with exporttab:
    st.download_button('Integrated parcels · GeoJSON',export_geojson(result,decisions),'integrated_parcels.geojson','application/geo+json')
    st.download_button('Review audit · CSV',store.audit(result['fingerprint']).to_csv(index=False),'review_audit.csv','text/csv')
    proposal_rows = [{**p,'decision':decisions.get(p['proposal_id'],'pending')} for p in result['proposals']]
    st.download_button('Proposals & decisions · JSON',json.dumps(proposal_rows,indent=2,default=str),'proposals.json','application/json')
    if result['temporal_available']:
        st.download_button('Building changes · CSV',result['changes'].to_csv(index=False),'building_changes.csv','text/csv')
    if not result['provenance'].empty:
        st.download_button('Source status · CSV',result['provenance'].to_csv(index=False),'source_status.csv','text/csv')
    st.caption('Integrated export preserves original geometry unless its repair is accepted; accepted record/building links include evidence and provenance. Invalid unaccepted boundaries remain marked original_invalid. Change decisions are exported in proposals.json. Audit is scoped to the input fingerprint.')
