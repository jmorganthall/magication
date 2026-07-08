"""magication moat — Phase 0 accumulation layer (PRD §17).

Stands up perishable-observation capture (wait times, with schema stubs for
offers/prices/DVC availability) before the application core exists.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("magication-moat")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0+unknown"
