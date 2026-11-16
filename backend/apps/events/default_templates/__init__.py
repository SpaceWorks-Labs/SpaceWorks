"""Packaged design data only; E validates/copies it and G owns installation."""

from .badge_seeds import BADGE_SEEDS, badge_seed, iter_badge_stock_seeds
from .certificate_seeds import CERTIFICATE_SEEDS, certificate_seed

__all__ = [
    "BADGE_SEEDS", "CERTIFICATE_SEEDS", "badge_seed", "certificate_seed",
    "iter_badge_stock_seeds",
]
