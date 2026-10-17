"""G-owned explicit model barrel. Domain manifests land before model imports.

Checkpoint intentionally registers no models. G replaces this empty export list
with explicit imports from A/B/C/D/E/P after reviewing their model manifests,
then imports this barrel from models.py alongside centrally authored migrations.
"""

__all__ = []
