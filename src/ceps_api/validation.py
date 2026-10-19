"""The parameters of a call checked against the catalog, before a request goes out."""
from __future__ import annotations

from collections.abc import Iterable

from .catalog import CEPS_AGGREGATIONS, CEPS_DATA_VERSIONS, CEPS_FUNCTIONS, CEPS_METHODS

# The argument names of the wrappers that the service spells differently.
# param1 is para1 for the methods whose catalog entry says so.
_SERVICE_NAMES = {"start": "dateFrom", "end": "dateTo", "aggregation": "agregation"}
#----------------------------------------------------------------------------------------------------------------------------

def service_name(method: str, name: str) -> str:
    """The service's name for an argument of a wrapper (param1 -> para1 where the catalog says so)."""
    if name == "param1" and "para1" in CEPS_METHODS[method].optional_params:
        return "para1"
    return _SERVICE_NAMES.get(name, name)
#----------------------------------------------------------------------------------------------------------------------------

def validate(method: str, params: dict[str, object], shown: dict[str, str] | None = None) -> None:
    """
    Raises ValueError for a method, parameter, aggregation, function,
    version or filter value the service does not have and for a missing
    parameter it needs, instead of letting a request go out that would
    fail or come back empty.

    shown maps the service's parameter names to the ones the messages
    use instead; the wrappers pass their argument names, so an error
    says param1 where the service calls it para1.
    """
    def names(params: Iterable[str]) -> str:
        return ", ".join((shown or {}).get(p, p) for p in params)

    if method not in CEPS_METHODS:
        raise ValueError(f"Unknown ČEPS method {method!r}")
    info = CEPS_METHODS[method]
    # A parameter that is None or empty is left out of the request, so
    # it is missing too.
    missing = [p for p in info.required_params + info.needed_params
               if params.get(p) in (None, "")]
    if missing:
        raise ValueError(f"{method} needs {names(missing)}")
    allowed = info.required_params + info.optional_params
    unknown = [p for p in params if p not in allowed]
    if unknown:
        raise ValueError(f"{method} does not take {names(unknown)}, "
                         f"expected {names(allowed) or 'no parameters'}")
    agregation = params.get("agregation")
    if agregation is not None and agregation not in CEPS_AGGREGATIONS:
        raise ValueError(f"unknown aggregation {agregation!r}, "
                         f"expected one of {', '.join(CEPS_AGGREGATIONS)}")
    supported = info.aggregations
    if agregation is not None and supported is not None and agregation not in supported:
        raise ValueError(f"{method} has no data for aggregation {agregation!r}, "
                         f"expected one of {', '.join(supported)}")
    function = params.get("function")
    if function is not None and function not in CEPS_FUNCTIONS:
        raise ValueError(f"unknown function {function!r}, "
                         f"expected one of {', '.join(CEPS_FUNCTIONS)}")
    # Without a function the service fails or returns rows with no values.
    if agregation is not None and function is None:
        raise ValueError(f"{method}: an aggregation needs a function, "
                         f"one of {', '.join(CEPS_FUNCTIONS)}")
    version = params.get("version")
    if version is not None and version not in CEPS_DATA_VERSIONS:
        raise ValueError(f"unknown version {version!r}, "
                         f"expected one of {', '.join(CEPS_DATA_VERSIONS)}")
    if version is not None and info.versions is not None and version not in info.versions:
        raise ValueError(f"{method} has no data version {version!r}, "
                         f"expected one of {', '.join(info.versions)}")
    # The service does not report a filter value it does not know.
    for name, values in info.param_values.items():
        value = params.get(name)
        if value is not None and value not in values:
            raise ValueError(f"{method} has no {names([name])} {value!r}, "
                             f"expected one of {', '.join(values)}")
#----------------------------------------------------------------------------------------------------------------------------