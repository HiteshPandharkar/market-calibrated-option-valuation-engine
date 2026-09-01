from datetime import date, time
from pathlib import Path

import pytest


streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest


APP = Path(__file__).parents[3] / "streamlit_app" / "app.py"


def test_streamlit_page_starts_with_csv_flow_separate_from_core() -> None:
    page = AppTest.from_file(str(APP)).run(timeout=20)

    assert not page.exception
    assert page.title[0].value == "PyOptionPricer"
    assert page.sidebar.selectbox[0].label == "Provider"
    assert page.button[0].label == "Price"
    assert page.button[0].disabled is False

    page.date_input[1].set_value(date(2026, 8, 28))
    page.time_input[0].set_value(time(15, 30))
    page.button[0].click().run(timeout=20)

    assert not page.exception
    assert [metric.label for metric in page.metric] == [
        "Theoretical value",
        "Market midpoint",
        "Absolute difference",
        "Difference",
    ]
    assert page.metric[0].value == "83.4135"
