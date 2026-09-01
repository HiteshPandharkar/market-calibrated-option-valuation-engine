from datetime import UTC, date, datetime
from pathlib import Path

from pyoptionpricer.application import MarketDataProviderName, VolatilitySource
from pyoptionpricer.domain import ExerciseStyle, OptionType
from pyoptionpricer.market import MarketDataAuthenticationError, MarketObservation
from pyoptionpricer.market.data import (
    InstrumentReference,
    InstrumentReferenceProvider,
    InstrumentType,
    MarketDataProvider,
    MarketSegment,
)
from streamlit_app.flow import (
    ValuationForm,
    ValuationUIFlow,
    present_valuation,
    user_facing_failure,
)


FIXTURES = Path(__file__).parents[2] / "fixtures" / "market_data"
VALUATION_TIME = datetime(2026, 8, 28, 15, 30, tzinfo=UTC)


class LookupProvider(MarketDataProvider, InstrumentReferenceProvider):
    def __init__(self) -> None:
        self.underlying = InstrumentReference(
            instrument_id="EQUITY_CASH:NSE:ACME",
            instrument_type=InstrumentType.EQUITY,
            symbol="ACME",
            display_symbol="Acme Limited",
            exchange="NSE",
            segment=MarketSegment.EQUITY_CASH,
            currency="INR",
            vendor="UPSTOX",
            vendor_instrument_id="NSE_EQ|SECRET1",
        )
        self.contract = InstrumentReference(
            instrument_id="EQUITY_DERIVATIVES:NSE:ACME 31 DEC 26 1400 CE",
            instrument_type=InstrumentType.OPTION,
            symbol="ACME 31 DEC 26 1400 CE",
            display_symbol="Acme 31 Dec 2026 1400 Call",
            exchange="NSE",
            segment=MarketSegment.EQUITY_DERIVATIVES,
            currency="INR",
            vendor="UPSTOX",
            vendor_instrument_id="NSE_FO|SECRET2",
            underlying_id=self.underlying.instrument_id,
            option_type=OptionType.CALL,
            strike=1400.0,
            expiry=date(2026, 12, 31),
        )

    def get_instrument(self, instrument_id: str) -> InstrumentReference:
        return self.underlying

    def search_instruments(self, query: str) -> tuple[InstrumentReference, ...]:
        return (self.underlying, self.contract)

    def get_spot(self, symbol, timestamp):
        raise NotImplementedError

    def get_option_quote(self, contract_id, timestamp):
        raise NotImplementedError

    def get_price_history(self, symbol, start, end):
        raise NotImplementedError

    def get_yield_curve(self, currency, timestamp):
        raise NotImplementedError

    def get_dividend_data(self, symbol, timestamp):
        raise NotImplementedError

    def get_volatility_input(self, symbol, timestamp) -> MarketObservation[float]:
        raise NotImplementedError


def _csv_form() -> ValuationForm:
    return ValuationForm(
        provider=MarketDataProviderName.CSV,
        underlying_id="ACME",
        contract_id="ACME-20261231-1400-C",
        valuation_datetime=VALUATION_TIME,
        steps=200,
        volatility_source=VolatilitySource.PROVIDER,
        exercise_style=ExerciseStyle.EUROPEAN,
        strike=1400.0,
        expiry=date(2026, 12, 31),
        option_type=OptionType.CALL,
        exchange="SAMPLE_EXCHANGE",
    )


def test_ui_flow_delegates_complete_csv_valuation_to_application_service() -> None:
    flow = ValuationUIFlow()
    provider = flow.create_provider(
        MarketDataProviderName.CSV, csv_data_directory=FIXTURES
    )

    valuation = flow.value(provider, _csv_form())
    presented = present_valuation(valuation)

    assert valuation.pricing_result.price == 83.41348229842129
    assert presented["valuation"]["Market midpoint"] == 35.35
    assert presented["model"]["Tree steps"] == 200
    assert presented["greeks"]["delta"] > 0
    assert presented["diagnostics"]
    assert {item["Input"] for item in presented["provenance"]} == {
        "Spot",
        "Strike",
        "Maturity",
        "Risk Free Rate",
        "Dividend Yield",
        "Volatility",
    }


def test_csv_request_requires_canonical_contract_terms() -> None:
    form = _csv_form()
    incomplete = ValuationForm(
        provider=form.provider,
        underlying_id=form.underlying_id,
        contract_id=form.contract_id,
        valuation_datetime=form.valuation_datetime,
    )

    try:
        ValuationUIFlow.build_request(incomplete)
    except ValueError as error:
        assert str(error) == "CSV valuations require strike, expiry, and option type"
    else:
        raise AssertionError("incomplete CSV contract was accepted")


def test_authentication_failure_is_sanitized_for_display() -> None:
    failure = user_facing_failure(
        MarketDataAuthenticationError("access_token=do-not-display")
    )

    assert failure.title == "Provider authentication failed"
    assert "do-not-display" not in failure.message
    assert "credentials" in failure.message.lower()


def test_lookup_exposes_canonical_labels_without_vendor_identifiers() -> None:
    provider = LookupProvider()

    underlyings = ValuationUIFlow.search_underlyings(provider, "ACME")
    contracts = ValuationUIFlow.contracts_for_underlying(
        provider, underlyings[0].instrument_id
    )

    assert underlyings[0].label == "Acme Limited - NSE"
    assert contracts[0].label == "Acme 31 Dec 2026 1400 Call - NSE"
    assert "SECRET" not in underlyings[0].label + contracts[0].label
    assert contracts[0].option_type is OptionType.CALL
