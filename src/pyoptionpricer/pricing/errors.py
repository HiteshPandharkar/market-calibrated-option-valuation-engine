"""Model-neutral pricing failures."""


class PricingError(RuntimeError):
    """Raised when a valid request cannot be priced numerically."""
