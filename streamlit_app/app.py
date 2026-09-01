"""Streamlit page for the provider-neutral single-contract workflow."""

from datetime import UTC, date, datetime, time
import os
from pathlib import Path
import sys


# Streamlit executes this file as a script, so an uninstalled ``src`` layout is
# not automatically importable. Keep this source-checkout bootstrap at the UI
# composition root; the core package remains independent of the presentation.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
for import_root in (PROJECT_ROOT, SOURCE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import streamlit as st

from pyoptionpricer.application import MarketDataProviderName, VolatilitySource
from pyoptionpricer.domain import ExerciseStyle, OptionType
from streamlit_app.flow import (
    InstrumentChoice,
    ValuationForm,
    ValuationUIFlow,
    present_valuation,
    user_facing_failure,
)


st.set_page_config(page_title="PyOptionPricer", layout="wide")
st.title("PyOptionPricer")
st.caption("Market-calibrated CRR valuation through canonical application services")


@st.cache_resource(show_spinner=False)
def _provider(provider_name: str, csv_directory: str):
    return ValuationUIFlow().create_provider(
        MarketDataProviderName(provider_name),
        csv_data_directory=(Path(csv_directory) if csv_directory else None),
        environment=os.environ,
    )


def _render_results(data: dict[str, object]) -> None:
    valuation = data["valuation"]
    assert isinstance(valuation, dict)
    columns = st.columns(4)
    columns[0].metric("Theoretical value", f"{valuation['Theoretical value']:.4f}")
    columns[1].metric("Market midpoint", f"{valuation['Market midpoint']:.4f}")
    columns[2].metric("Absolute difference", f"{valuation['Absolute difference']:.4f}")
    columns[3].metric("Difference", f"{valuation['Percentage difference']:.2f}%")

    for title, key in (
        ("Contract", "contract"),
        ("Market snapshot", "market"),
        ("Model assumptions", "model"),
        ("Greeks", "greeks"),
    ):
        st.subheader(title)
        st.json(data[key])

    st.subheader("Diagnostics")
    st.dataframe(data["diagnostics"], use_container_width=True, hide_index=True)
    st.subheader("Data provenance")
    st.dataframe(data["provenance"], use_container_width=True, hide_index=True)


def _upstox_selection(flow: ValuationUIFlow, provider) -> InstrumentChoice | None:
    query = st.text_input("Find underlying", placeholder="e.g. RELIANCE or NIFTY")
    if not query.strip():
        return None
    underlyings = flow.search_underlyings(provider, query)
    if not underlyings:
        st.info("No canonical underlying matched that search.")
        return None
    underlying = st.selectbox(
        "Underlying", underlyings, format_func=lambda item: item.label
    )
    contracts = flow.contracts_for_underlying(provider, underlying.instrument_id)
    if not contracts:
        st.info("No listed option contracts were available for this underlying.")
        return None
    expiries = sorted({item.expiry for item in contracts if item.expiry is not None})
    expiry = st.selectbox("Expiry", expiries)
    by_expiry = [item for item in contracts if item.expiry == expiry]
    strikes = sorted({item.strike for item in by_expiry if item.strike is not None})
    strike = st.selectbox("Strike", strikes)
    by_strike = [item for item in by_expiry if item.strike == strike]
    option_types = sorted(
        {item.option_type for item in by_strike if item.option_type is not None},
        key=lambda item: item.value,
    )
    option_type = st.selectbox(
        "Call or put", option_types, format_func=lambda item: item.value.title()
    )
    return next(item for item in by_strike if item.option_type is option_type)


flow = ValuationUIFlow()
with st.sidebar:
    st.header("Market data")
    provider_name = MarketDataProviderName(
        st.selectbox(
            "Provider",
            [item.value for item in MarketDataProviderName],
            format_func=str.title,
        )
    )
    csv_directory = (
        st.text_input("CSV data directory", "tests/fixtures/market_data")
        if provider_name is MarketDataProviderName.CSV
        else ""
    )

try:
    provider = _provider(provider_name.value, csv_directory)
except Exception as error:
    failure = user_facing_failure(error)
    st.error(f"{failure.title}: {failure.message}")
    st.stop()

st.header("Contract")
selected_contract: InstrumentChoice | None = None
if provider_name is MarketDataProviderName.UPSTOX:
    try:
        selected_contract = _upstox_selection(flow, provider)
    except Exception as error:
        failure = user_facing_failure(error)
        st.error(f"{failure.title}: {failure.message}")
else:
    first, second = st.columns(2)
    underlying_id = first.text_input("Underlying identifier", "ACME")
    contract_id = second.text_input("Contract identifier", "ACME-20261231-1400-C")
    expiry = first.date_input("Expiry", date(2026, 12, 31))
    strike = second.number_input("Strike", min_value=0.01, value=1400.0)
    option_type = first.selectbox(
        "Call or put", list(OptionType), format_func=lambda item: item.value.title()
    )
    exchange = second.text_input("Exchange", "SAMPLE_EXCHANGE")

st.header("Valuation settings")
left, middle, right = st.columns(3)
valuation_date = left.date_input("Valuation date", datetime.now(UTC).date())
valuation_clock = left.time_input("Valuation time (UTC)", time(10, 0))
steps = middle.number_input("Tree steps", min_value=2, value=200, step=10)
exercise_style = middle.selectbox(
    "Exercise style",
    list(ExerciseStyle),
    format_func=lambda item: item.value.title(),
)
volatility_source = VolatilitySource(
    right.selectbox(
        "Volatility source",
        [item.value for item in VolatilitySource],
        format_func=str.title,
    )
)
fallback_value = right.selectbox(
    "Market IV fallback",
    ["none", VolatilitySource.HISTORICAL.value, VolatilitySource.EWMA.value],
    disabled=volatility_source is not VolatilitySource.PROVIDER,
)
lookback = right.number_input("Volatility lookback", min_value=2, value=60)

if provider_name is MarketDataProviderName.UPSTOX:
    st.caption(
        "Upstox does not supply curves in V1; enter explicit annualized assumptions."
    )
    rate_column, dividend_column = st.columns(2)
    risk_free_rate = rate_column.number_input(
        "Risk-free rate", value=0.065, format="%.4f"
    )
    dividend_yield = dividend_column.number_input(
        "Dividend yield", value=0.012, format="%.4f"
    )
else:
    risk_free_rate = None
    dividend_yield = None

if st.button(
    "Price",
    type="primary",
    disabled=(
        provider_name is MarketDataProviderName.UPSTOX
        and selected_contract is None
    ),
):
    valuation_datetime = datetime.combine(valuation_date, valuation_clock, tzinfo=UTC)
    if selected_contract is not None:
        underlying_id = selected_contract.underlying_id or ""
        contract_id = selected_contract.instrument_id
        strike = expiry = option_type = exchange = None
    form = ValuationForm(
        provider=provider_name,
        underlying_id=underlying_id,
        contract_id=contract_id,
        valuation_datetime=valuation_datetime,
        steps=int(steps),
        volatility_source=volatility_source,
        volatility_fallback=(
            None if fallback_value == "none" else VolatilitySource(fallback_value)
        ),
        lookback=int(lookback),
        exercise_style=exercise_style,
        risk_free_rate=risk_free_rate,
        dividend_yield=dividend_yield,
        strike=strike,
        expiry=expiry,
        option_type=option_type,
        exchange=exchange,
    )
    try:
        with st.spinner("Valuing contract..."):
            completed = flow.value(provider, form)
        _render_results(present_valuation(completed))
    except Exception as error:
        failure = user_facing_failure(error)
        st.error(f"{failure.title}: {failure.message}")
