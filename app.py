from pathlib import Path
import json
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from pipeline import run, fingerprint
from review import ReviewStore, export_geojson

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='BhuSetu | Urban land integration',page_icon='🌐',layout='wide')
st.title('BhuSetu')
st.caption('SIH 26013 · Urban land integration · Synthetic demonstration')

@st.cache_data
def load(signature):
    return run(ROOT/'dataset')

result = load(fingerprint(ROOT/'dataset'))
store = ReviewStore(ROOT/'state/reviews.sqlite')
decisions = store.decisions(result['fingerprint'])
st.sidebar.header('Workspace')
st.sidebar.caption('EPSG:32643 · distances and areas in metres')
st.sidebar.info(result['quarantine'][0])
st.sidebar.caption('To admit the legacy fixture, obtain a source CRS confirmation and add a documented ingestion rule. No CRS is inferred.')
st.sidebar.warning('Heuristic scores are evidence rankings, not probabilities. Accepted repairs do not establish legal cadastral accuracy.')
a,b,c,d = st.columns(4)
a.metric('Parcels',len(result['originals']['parcels']))
b.metric('Conflicts',len(result['conflicts']))
c.metric('Review proposals',len(result['proposals']))
d.metric('Accepted',sum(v=='accepted' for v in decisions.values()))
maptab, reviewtab, changetab, datatab, exporttab = st.tabs(['Map & evidence','Review queue','Building changes','Validation','Export'])
with maptab:
    selected = st.selectbox('Inspect parcel',result['originals']['parcels'].parcel_id)
    shown = st.multiselect('Visible layers',list(result['layers']),default=['parcels','t2','utilities','observations'])
    p = result['originals']['parcels']
    center = p.to_crs(4326).geometry.union_all().centroid if p.geometry.is_valid.all() else p.to_crs(4326).geometry.iloc[0].centroid
    m = folium.Map(location=[center.y,center.x],zoom_start=17,tiles=None)
    folium.TileLayer('OpenStreetMap',show=False).add_to(m)
    colors = dict(parcels='#64748b',t1='#f59e0b',t2='#0d9488',observations='#a855f7',utilities='#ef4444',gnss='#2563eb')
    for name in shown:
        frame = result['originals'].get(name,result['layers'][name]).to_crs(4326)
        fields = [x for x in frame.columns if x!='geometry']
        folium.GeoJson(json.loads(frame.to_json()),name=name,
            marker=folium.CircleMarker(radius=5),
            style_function=lambda feature,color=colors[name]:{'color':color,'weight':2,'fillOpacity':.18},
            tooltip=folium.GeoJsonTooltip(fields=fields)).add_to(m)
    focus = p[p.parcel_id.eq(selected)].to_crs(4326)
    folium.GeoJson(json.loads(focus.to_json()),name='Selected parcel',style_function=lambda f:{'color':'#f43f5e','weight':4,'fillOpacity':.05}).add_to(m)
    folium.LayerControl().add_to(m)
    st_folium(m,height=520,use_container_width=True,returned_objects=[])
    st.caption('Hover for feature properties. Select a parcel above for linked evidence. Basemap is optional; local vector layers load without map tiles.')
    st.dataframe(p[p.parcel_id.eq(selected)].drop(columns='geometry'),hide_index=True)
    st.dataframe(result['candidates'][result['candidates'].parcel_id.eq(selected)],hide_index=True)
    st.dataframe(result['evidence'][result['evidence'].parcel_id.eq(selected)],hide_index=True)
    st.caption('GNSS points have no corresponding reference-point IDs; their reported accuracy does not measure absolute positional accuracy.')
with reviewtab:
    st.dataframe(result['conflicts'],hide_index=True,use_container_width=True)
    kind = st.selectbox('Proposal type',sorted({p['kind'] for p in result['proposals']}))
    status = st.selectbox('Review status',['all','pending','accepted','rejected'])
    items = [p for p in result['proposals'] if p['kind']==kind and (status=='all' or decisions.get(p['proposal_id'],'pending')==status)]
    if items:
        item = st.selectbox('Proposal',items,format_func=lambda p:f"{p['source']} / {p['feature_id']} → {p['target_id']} [{decisions.get(p['proposal_id'],'pending')}]")
        st.json(item)
        st.caption('Building score = 75% overlap + 15% proximity within 15 m + 10% area fit. Record score 1 means exact normalized ID. Invalid parcels are excluded from candidate matching.')
        with st.form('review'):
            reviewer = st.text_input('Reviewer name',value='Demo reviewer')
            decision = st.radio('Decision',['accepted','rejected','pending'],horizontal=True)
            note = st.text_input('Review note')
            if st.form_submit_button('Save decision'):
                if reviewer.strip():
                    store.save(result['fingerprint'],item['proposal_id'],decision,reviewer,note)
                    st.rerun()
                else: st.error('Enter a reviewer name.')
    else: st.info('No proposals match this filter.')
with changetab:
    st.subheader('2024-11-15 → 2025-11-20')
    st.dataframe(result['changes'],hide_index=True,use_container_width=True)
    st.caption('Spatial one-to-one greedy matching uses overlap, centroid distance and area similarity. Extension threshold: >15% area growth. Unmatched detections are possible additions/removals; extraction errors can mimic change.')
with datatab:
    st.dataframe(result['validation'],hide_index=True,use_container_width=True)
    st.subheader('Quarantined sources')
    st.write(result['quarantine'])
    st.caption('Original source files remain unchanged. Repairs are proposed via Shapely make_valid. No ownership or legal boundary correction is automatic.')
with exporttab:
    st.download_button('Integrated parcels · GeoJSON',export_geojson(result,decisions),'integrated_parcels.geojson','application/geo+json')
    st.download_button('Review audit · CSV',store.audit(result['fingerprint']).to_csv(index=False),'review_audit.csv','text/csv')
    proposal_rows = [{**p,'decision':decisions.get(p['proposal_id'],'pending')} for p in result['proposals']]
    st.download_button('Proposals & decisions · JSON',json.dumps(proposal_rows,indent=2,default=str),'proposals.json','application/json')
    st.download_button('Building changes · CSV',result['changes'].to_csv(index=False),'building_changes.csv','text/csv')
    st.caption('Integrated export preserves original geometry unless its repair is accepted; accepted record/building links include evidence and provenance. Invalid unaccepted boundaries remain marked original_invalid. Change decisions are exported in proposals.json. Audit is scoped to the input fingerprint.')
