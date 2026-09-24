from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_app_load_and_filters():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=60)
    assert not app.exception
    app.selectbox[0].select('P-023').run(timeout=60)
    assert not app.exception
    assert app.title[0].value=='BhuSetu'
