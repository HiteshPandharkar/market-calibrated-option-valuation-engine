"""Thin command-line entry point for the single-contract valuation service."""

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date, datetime
import json
from pathlib import Path

from pyoptionpricer.application import (
    ContractSelection,
    MarketDataProviderConfiguration,
    MarketDataProviderFactory,
    MarketDataProviderName,
    SingleContractValuationRequest,
    SingleContractValuationService,
    VolatilitySelection,
    VolatilitySource,
)
from pyoptionpricer.domain import (
    AssetClass,
    Currency,
    ExerciseStyle,
    OptionContract,
    OptionType,
)
from pyoptionpricer.market import (
    ContinuousDividendYield,
    FlatYieldCurve,
    MarketObservation,
)
from pyoptionpricer.models.tree import CRRModelParameters


def main(
    arguments: Sequence[str] | None = None,
    *,
    provider_factory: MarketDataProviderFactory | None = None,
    environment: Mapping[str, str] | None = None,
) -> int:
    """Run one valuation and print a stable JSON summary."""
    parser = _parser()
    values = parser.parse_args(arguments)
    valuation_time = _datetime(values.valuation_time)
    provider_name = MarketDataProviderName(values.provider)
    provider = (provider_factory or MarketDataProviderFactory()).create(
        MarketDataProviderConfiguration(
            provider=provider_name,
            csv_data_directory=values.data_directory,
            environment=environment,
        )
    )
    contract = _contract(values)
    assumption_source = "CLI_ASSUMPTION"
    yield_curve = (
        FlatYieldCurve(
            values.risk_free_rate,
            MarketObservation(
                values.risk_free_rate,
                valuation_time,
                assumption_source,
                "continuous_zero_rate",
            ),
        )
        if values.risk_free_rate is not None
        else None
    )
    dividend_data = (
        ContinuousDividendYield(
            values.dividend_yield,
            MarketObservation(
                values.dividend_yield,
                valuation_time,
                assumption_source,
                "continuous_dividend_yield",
            ),
        )
        if values.dividend_yield is not None
        else None
    )
    workflow_request = SingleContractValuationRequest(
        selection=ContractSelection(
            values.underlying_id,
            values.contract_id,
            contract=contract,
            exercise_style=ExerciseStyle(values.exercise_style),
        ),
        valuation_datetime=valuation_time,
        model_parameters=CRRModelParameters(values.steps),
        volatility=VolatilitySelection(
            source=VolatilitySource(values.volatility_source),
            lookback=values.lookback,
            ewma_decay=values.ewma_decay,
            fallback_source=(
                VolatilitySource(values.volatility_fallback)
                if values.volatility_fallback is not None
                else None
            ),
        ),
        yield_curve=yield_curve,
        dividend_data=dividend_data,
    )
    valuation = SingleContractValuationService(provider).value(workflow_request)
    result = valuation.pricing_result
    output = {
        "contract": {
            "underlying": valuation.contract.underlying,
            "symbol": valuation.contract.contract_symbol,
            "strike": valuation.contract.strike,
            "expiry": valuation.contract.expiry,
            "option_type": valuation.contract.option_type,
        },
        "valuation_datetime": result.valuation_datetime,
        "model": result.model_name,
        "price": result.price,
        "currency": result.currency,
        "greeks": asdict(result.greeks),
        "market_comparison": asdict(valuation.market_comparison),
        "implied_volatility": {
            "value": valuation.implied_volatility.implied_volatility,
            "market_midpoint": valuation.implied_volatility.market_midpoint,
            "calibrated_price": valuation.implied_volatility.model_price,
            "pricing_residual": valuation.implied_volatility.pricing_residual,
            "iterations": valuation.implied_volatility.iterations,
        },
        "market_iv_surface": {
            "point_count": (
                len(valuation.volatility_surface.points)
                if valuation.volatility_surface is not None
                else 0
            ),
            "selected_volatility": result.inputs.volatility.value,
            "used_volatility_fallback": valuation.used_volatility_fallback,
        },
        "diagnostic_status": valuation.diagnostics.overall_status,
        "inputs": asdict(result.inputs),
    }
    print(json.dumps(output, default=_json_value, indent=2, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pyoptionpricer",
        description=(
            "Value one listed option through the provider-neutral CRR workflow."
        ),
    )
    parser.add_argument(
        "--provider",
        choices=[item.value for item in MarketDataProviderName],
        default=MarketDataProviderName.CSV.value,
    )
    parser.add_argument("--data-directory", type=Path)
    parser.add_argument("--underlying-id", required=True)
    parser.add_argument("--contract-id", required=True)
    parser.add_argument("--valuation-time", required=True)
    parser.add_argument("--strike", type=float)
    parser.add_argument("--expiry")
    parser.add_argument("--type", choices=[item.value for item in OptionType])
    parser.add_argument(
        "--exercise-style",
        choices=[item.value for item in ExerciseStyle],
        default=ExerciseStyle.EUROPEAN.value,
    )
    parser.add_argument(
        "--asset-class",
        choices=[item.value for item in AssetClass],
        default=AssetClass.EQUITY.value,
    )
    parser.add_argument(
        "--currency",
        choices=[item.value for item in Currency],
        default=Currency.INR.value,
    )
    parser.add_argument("--exchange")
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument(
        "--volatility-source",
        choices=[item.value for item in VolatilitySource],
        default=VolatilitySource.PROVIDER.value,
    )
    parser.add_argument("--lookback", type=int, default=60)
    parser.add_argument("--ewma-decay", type=float, default=0.94)
    parser.add_argument(
        "--volatility-fallback",
        choices=[
            VolatilitySource.HISTORICAL.value,
            VolatilitySource.EWMA.value,
        ],
    )
    parser.add_argument("--risk-free-rate", type=float)
    parser.add_argument("--dividend-yield", type=float)
    return parser


def _contract(values: argparse.Namespace) -> OptionContract | None:
    supplied = (values.strike, values.expiry, values.type)
    if all(value is None for value in supplied):
        if values.provider == MarketDataProviderName.CSV.value:
            raise ValueError(
                "CSV valuations require --strike, --expiry, and --type"
            )
        return None
    if any(value is None for value in supplied):
        raise ValueError("--strike, --expiry, and --type must be supplied together")
    return OptionContract(
        underlying=values.underlying_id,
        strike=values.strike,
        expiry=date.fromisoformat(values.expiry),
        option_type=OptionType(values.type),
        exercise_style=ExerciseStyle(values.exercise_style),
        asset_class=AssetClass(values.asset_class),
        exchange=values.exchange,
        contract_symbol=values.contract_id,
        currency=Currency(values.currency),
    )


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--valuation-time must be timezone-aware")
    return parsed


def _json_value(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "value"):
        return str(getattr(value, "value"))
    raise TypeError(f"cannot encode {type(value).__name__}")
