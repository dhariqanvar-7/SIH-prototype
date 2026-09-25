from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_app_load_and_filters():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=60)
    assert not app.exception
    assert app.selectbox(key='workspace').value == 'Kondapur · Integrated synthetic v1'
    next(w for w in app.selectbox if w.label=='Inspect parcel').select('SYN-P0023').run(timeout=60)
    assert not app.exception
    assert any(t.label=='Parcel profile' for t in app.tabs)
    assert any(t.label=='Department matching' for t in app.tabs)
    assert any(t.label=='Approved Records' for t in app.tabs)
    assert any(w.label=='Approved parcel ID' for w in app.selectbox)
    assert any(w.label=='Record mapped to this parcel' for w in app.selectbox)
    assert any(w.label=='Review parcel ID' for w in app.selectbox)
    assert any(w.label=='Department record on this parcel' for w in app.selectbox)
    next(w for w in app.selectbox if w.label=='Matching outcome').select('unmatched').run(timeout=60)
    assert not app.exception
    next(w for w in app.selectbox if w.label=='Matching outcome').select('all').run(timeout=60)
    assert any('one Microsoft footprint snapshot' in item.value for item in app.info)
    next(w for w in app.multiselect if w.label=='Raster layers').set_value(['Surface elevation']).run(timeout=60)
    assert not app.exception
    app.selectbox(key='workspace').select('Kondapur, Hyderabad · Earlier demo').run(timeout=60)
    assert not app.exception
    app.selectbox(key='workspace').select('Legacy synthetic demo').run(timeout=60)
    next(w for w in app.selectbox if w.label=='Inspect parcel').select('P-023').run(timeout=60)
    assert not app.exception
    assert app.title[0].value=='BhuSetu'
