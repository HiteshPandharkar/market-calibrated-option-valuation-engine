import pytest

from pyoptionpricer import (
    BSMPricingEngine,
    BSM_PRODUCT_PRICERS,
    CashDigitalBSMProductPricer,
    OptionProduct,
    VanillaBSMProductPricer,
)


def test_bsm_products_are_dispatched_to_independent_strategies() -> None:
    assert isinstance(
        BSM_PRODUCT_PRICERS[OptionProduct.VANILLA], VanillaBSMProductPricer
    )
    assert isinstance(
        BSM_PRODUCT_PRICERS[OptionProduct.DIGITAL], CashDigitalBSMProductPricer
    )
    assert BSMPricingEngine.capabilities.products == frozenset(
        BSM_PRODUCT_PRICERS
    )


def test_bsm_product_strategy_catalogue_is_immutable() -> None:
    with pytest.raises(TypeError):
        BSM_PRODUCT_PRICERS[OptionProduct.ASIAN] = (  # type: ignore[index]
            VanillaBSMProductPricer()
        )
