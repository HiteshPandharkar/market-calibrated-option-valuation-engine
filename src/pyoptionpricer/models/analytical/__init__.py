"""Configuration for closed-form analytical pricing models."""

from pyoptionpricer.models.analytical.parameters import (
    BSMModelParameters,
    InvalidBSMParametersError,
)

__all__ = ["BSMModelParameters", "InvalidBSMParametersError"]
