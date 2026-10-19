"""
Czech Electrical Power Transmission system data from ČEPS.

ČEPS publishes system imbalance, activated balancing energy, load and
generation over a SOAP service. It needs no key, and is not pleasant
to call directly. This wraps it: every method of the service has a
wrapper of the same name on Ceps, which returns a pandas DataFrame.

    from ceps_api import Ceps

    ceps = Ceps()
    df = ceps.AktualniSystemovaOdchylkaCR("2026-09-14", "2026-09-15", aggregation="QH")

    Ceps.parameters()              # the methods
    Ceps.parameters("Generation")  # what one of them accepts
"""
from importlib.metadata import version

from .catalog import CEPS_AGGREGATIONS, CEPS_DATA_VERSIONS, CEPS_FUNCTIONS, CEPS_METHODS
from .client import Ceps
from .models import CepsMethod, CepsResponseType
from .soap import CEPS_NS, CEPS_URL, CepsError

# The version in pyproject.toml, as installed.
__version__ = version("ceps-api")

__all__ = ["__version__", "Ceps", "CepsError", "CEPS_NS", "CEPS_URL",
           "CEPS_METHODS", "CepsMethod", "CepsResponseType", "CEPS_AGGREGATIONS",
           "CEPS_FUNCTIONS", "CEPS_DATA_VERSIONS"]
