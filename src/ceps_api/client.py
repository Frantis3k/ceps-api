"""Client for the ČEPS SOAP service, with a wrapper for each of its methods."""
from __future__ import annotations

import inspect
from typing import Any

import pandas as pd

from . import soap
from .catalog import CEPS_AGGREGATIONS, CEPS_DATA_VERSIONS, CEPS_FUNCTIONS, CEPS_METHODS
from .convert import DateLike, to_ceps_time, to_dataframe
from .parsing import parse
from .soap import CepsError
from .validation import service_name, validate


class Ceps:
    """
    The ČEPS service

    Every method of the service has a wrapper of the same name as
    the ČEPS calls the method. The wrapper returns a DataFrame.

    *Ceps.parameters()* lists the methods and
    e.g. *Ceps.parameters("Generation")* lists the parameters it accepts.

    *start* and *end* are Czech local time (see convert.to_ceps_time) and both are included:
    with an *aggregation*, the steps that start between them come back, the
    one that starts at end too. So a whole day is start="2026-10-05",
    end="2026-10-05T23:59:00". A step that start cuts into is left out; one
    that end cuts into comes back whole. The latest step keeps changing for
    a few minutes after it is over, until all its minutes are in.

    *aggregation* is the time step (see CEPS_AGGREGATIONS) and *function* is how
    the values within it are combined (see CEPS_FUNCTIONS); function is only
    sent with an aggregation.

    Time series come back indexed by "timestamp", the start of the step in
    Europe/Prague time, with a column per series as ČEPS names it.

    A wrapper raises ValueError for arguments the service would not accept
    (see validation.validate), before anything is sent, and CepsError if
    the service fails or a SERIES method returns something that is not one
    row per timestamp.
    """
    #----------------------------------------------------------------------------------------------------------------------------
    def __init__(self, timeout: int = 30):
        self.timeout = timeout # timeout in seconds
    #----------------------------------------------------------------------------------------------------------------------------
    def _fetch(self, method: str, **args: Any) -> pd.DataFrame:
        """
        Calls a method with the arguments of its wrapper: renames them to
        what the service calls them, checks them, sends the request and
        parses the answer. None arguments are left out, and so is function
        without an aggregation.

        The check gets the wrapper's names along, so that an error names
        the argument of the wrapper (param1), not the service's (para1).
        """
        params: dict[str, Any] = {}
        shown: dict[str, str] = {}
        for name, value in args.items():
            service = service_name(method, name)
            # Every argument is named, a left out one is still reported as missing.
            shown[service] = name
            if value is not None:
                params[service] = value
        validate(method, params, shown)
        # Dropped only after the check, which would otherwise report the
        # function missing too when a needed aggregation is.
        if "agregation" not in params:
            params.pop("function", None)
        for key in ("dateFrom", "dateTo"):
            if key in params:
                params[key] = to_ceps_time(params[key])
        response_type = CEPS_METHODS[method].response_type
        raw = soap.call(method, params, self.timeout)
        try:
            data = parse(response_type, raw)
        except CepsError as e:
            # The parser does not know which method it reads.
            raise CepsError(f"{method}: {e}") from None
        return to_dataframe(response_type, data)
    #----------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def parameters(method: str | None = None) -> pd.DataFrame:
        """
        What the wrappers accept, for all methods or for just one.

        Without *method* it gives an overview, a row per method of
        CEPS_METHODS, indexed by "method", with the columns:

          - description: what the method returns, as in the catalog
          - arguments: the arguments of its wrapper, comma separated
          - response_type: the shape of the answer (see CepsResponseType)

        With *method* it gives a row per argument of that wrapper, indexed
        by "parameter", with the columns:

          - required: True if the wrapper has no default for it
          - default: the wrapper's default, None for a required one
          - allowed: the values the service accepts, comma separated, or
            "not known" where the catalog does not list them

        The arguments are read off the wrapper's signature, so they are
        named as the wrapper names them (param1, aggregation), not as the
        service does (para1, agregation). A method that takes no arguments,
        e.g. DataAgregation, gives an empty frame.

        Raises ValueError for a method that is not in CEPS_METHODS.

        >>> Ceps.parameters()                  # every method
        >>> Ceps.parameters("Generation")      # the arguments of one
        """
        if method is None:
            # The wrapper is looked up by name, Ceps has one for every
            # method of the catalog.
            return pd.DataFrame(
                [{"method": name,
                  "description": info.description,
                  "arguments": ", ".join(p for p in inspect.signature(getattr(Ceps, name)).parameters
                                         if p != "self"),
                  "response_type": info.response_type.value}
                 for name, info in CEPS_METHODS.items()]).set_index("method")
        if method not in CEPS_METHODS:
            raise ValueError(f"Unknown ČEPS method {method!r}, "
                             f"expected one of {', '.join(CEPS_METHODS)}")
        info = CEPS_METHODS[method]
        rows = []
        for name, p in inspect.signature(getattr(Ceps, method)).parameters.items():
            # Reached through the class, the wrapper still lists self.
            if name == "self":
                continue
            if name in ("start", "end"):
                # Anything convert.to_ceps_time takes.
                allowed = "date, datetime or ISO string, Czech local time"
            elif name == "aggregation":
                # A method without its own list in the catalog takes any
                # aggregation of the service.
                allowed = ", ".join(info.aggregations or CEPS_AGGREGATIONS)
            elif name == "function":
                # The same for every method.
                allowed = ", ".join(CEPS_FUNCTIONS)
            elif name == "version":
                # As with aggregation, no list of its own means all of them.
                allowed = ", ".join(info.versions or CEPS_DATA_VERSIONS)
            else:
                # param1, param2, ...: the catalog keys their values by the
                # service's name, which for some methods is para1, so the
                # wrapper's name is translated first.
                values = info.param_values.get(service_name(method, name))
                allowed = ", ".join(values) if values else "not known"
            # An argument without a default has to be given.
            required = p.default is inspect.Parameter.empty
            rows.append({"parameter": name,
                         "required": required,
                         "default": None if required else p.default,
                         "allowed": allowed})
        return pd.DataFrame(rows, columns=["parameter", "required", "default", "allowed"]).set_index("parameter")
    #----------------------------------------------------------------------------------------------------------------------------
    #----------------------------------------------------------------------------------------------------------------------------

    # START OF WRAPPERS FOR THE SERVICE METHODS

    #----------------------------------------------------------------------------------------------------------------------------
    #----------------------------------------------------------------------------------------------------------------------------
    def AktivaceSVRvCR(self, start: DateLike, end: DateLike, aggregation: str | None = None,
                       function: str = "AVG", param1: str | None = None) -> pd.DataFrame:
        """
        Activated balancing energy in the Czech area, MW.

        A column per product (aFRR+, aFRR-, mFRR+, mFRR-, mFRR5); the
        downward ones (aFRR-, mFRR-) are negative. param1 picks one
        product. Without an aggregation it is per minute.
        """
        return self._fetch("AktivaceSVRvCR", start=start, end=end, aggregation=aggregation,
                           function=function, param1=param1)
    #----------------------------------------------------------------------------------------------------------------------------
    def AktualniCenaRE(self, start: DateLike, end: DateLike, param1: str | None = None) -> pd.DataFrame:
        """
        Price of activated regulating energy, EUR/MWh.

        A column per product (aFRR, mFRR+, mFRR-, mFRR5); param1 picks
        one.

        Always per minute: the method takes no aggregation. Resample the
        frame for quarter hours.
        """
        return self._fetch("AktualniCenaRE", start=start, end=end, param1=param1)
    #----------------------------------------------------------------------------------------------------------------------------
    def AktualniSystemovaOdchylkaCR(self, start: DateLike, end: DateLike, aggregation: str | None = None,
                                    function: str = "AVG") -> pd.DataFrame:
        """
        System imbalance of the Czech control area, MW. Negative means the
        system is short (generation below consumption).

        Without an aggregation it is per minute; the minute series has
        gaps of a few minutes a day.
        """
        return self._fetch("AktualniSystemovaOdchylkaCR", start=start, end=end,
                           aggregation=aggregation, function=function)
    #----------------------------------------------------------------------------------------------------------------------------
    def CrossborderPowerFlows(self, start: DateLike, end: DateLike, aggregation: str = "QH",
                              function: str = "AVG", version: str | None = None) -> pd.DataFrame:
        """Actual and planned flows per neighbouring operator, MW."""
        return self._fetch("CrossborderPowerFlows", start=start, end=end, aggregation=aggregation,
                           function=function, version=version)
    #----------------------------------------------------------------------------------------------------------------------------
    def DataAgregation(self) -> pd.DataFrame:
        """The aggregation codes of the service and their descriptions."""
        return self._fetch("DataAgregation")
    #----------------------------------------------------------------------------------------------------------------------------
    def DataVersion(self) -> pd.DataFrame:
        """The data version codes of the service and their descriptions."""
        return self._fetch("DataVersion")
    #----------------------------------------------------------------------------------------------------------------------------
    def EmergencyExchange(self, start: DateLike, end: DateLike, aggregation: str = "QH", function: str = "AVG",
                          version: str = "RT", param1: str | None = None,
                          param2: str | None = None) -> pd.DataFrame:
        """
        Emergency assistance, redispatch and regulating energy from abroad,
        a row per step, border and direction; only has rows when something
        happened. param1 picks the kind (E, R), param2 the operator.
        """
        return self._fetch("EmergencyExchange", start=start, end=end, aggregation=aggregation,
                           function=function, version=version, param1=param1, param2=param2)
    #----------------------------------------------------------------------------------------------------------------------------
    def EmergencyExchangeACER(self, start: DateLike, end: DateLike, param1: str | None = None,
                              param2: str | None = None) -> pd.DataFrame:
        """
        The emergency exchange as an ACER message: one row however long
        the period, a column per field, all text. The remarks field holds
        the exchanges themselves, one "Direction-Type-MWh|" line each.
        """
        return self._fetch("EmergencyExchangeACER", start=start, end=end, param1=param1, param2=param2)
    #----------------------------------------------------------------------------------------------------------------------------
    def Emise(self, start: DateLike, end: DateLike, aggregation: str | None = None, function: str = "AVG",
              version: str = "RT", param1: str | None = None) -> pd.DataFrame:
        """
        CO2 intensity of generation, g CO2/kWh. Always per quarter hour,
        the service ignores the aggregation. The values of param1 are not
        known.
        """
        return self._fetch("Emise", start=start, end=end, aggregation=aggregation, function=function,
                           version=version, param1=param1)
    #----------------------------------------------------------------------------------------------------------------------------
    def ExportImportSVR(self, start: DateLike, end: DateLike, aggregation: str | None = None,
                        function: str = "AVG", param1: str | None = None) -> pd.DataFrame:
        """
        Exchange with the European balancing platforms (imbalance netting,
        MARI, PICASSO), MW. param1 picks one series.
        """
        return self._fetch("ExportImportSVR", start=start, end=end, aggregation=aggregation,
                           function=function, param1=param1)
    #----------------------------------------------------------------------------------------------------------------------------
    def ExportImportVykonu(self, start: DateLike, end: DateLike, aggregation: str | None = None,
                           function: str = "AVG") -> pd.DataFrame:
        """
        Export (+) and import (-) of power within the European platforms
        and foreign assistance, MW. Data from 2022-05-20 to 2023-08-25,
        then ExportImportSVR.
        """
        return self._fetch("ExportImportVykonu", start=start, end=end, aggregation=aggregation,
                           function=function)
    #----------------------------------------------------------------------------------------------------------------------------
    def Frekvence(self, start: DateLike, end: DateLike) -> pd.DataFrame:
        """System frequency, Hz."""
        return self._fetch("Frekvence", start=start, end=end)
    #----------------------------------------------------------------------------------------------------------------------------
    def Generation(self, start: DateLike, end: DateLike, aggregation: str = "QH", function: str = "AVG",
                   version: str = "RT", param1: str = "all") -> pd.DataFrame:
        """Gross generation by plant type, MW. param1 picks one type."""
        return self._fetch("Generation", start=start, end=end, aggregation=aggregation, function=function,
                           version=version, param1=param1)
    #----------------------------------------------------------------------------------------------------------------------------
    def GenerationPlan(self, start: DateLike, end: DateLike, aggregation: str = "QH", function: str = "AVG",
                       version: str = "RT") -> pd.DataFrame:
        """Planned gross generation, MW."""
        return self._fetch("GenerationPlan", start=start, end=end, aggregation=aggregation,
                           function=function, version=version)
    #----------------------------------------------------------------------------------------------------------------------------
    def GenerationRES(self, start: DateLike, end: DateLike, aggregation: str = "QH", function: str = "AVG",
                      version: str = "RT", param1: str = "all") -> pd.DataFrame:
        """Estimated wind (VTE) and solar (FVE) generation, MW. param1 picks one."""
        return self._fetch("GenerationRES", start=start, end=end, aggregation=aggregation,
                           function=function, version=version, param1=param1)
    #----------------------------------------------------------------------------------------------------------------------------
    def Load(self, start: DateLike, end: DateLike, aggregation: str = "QH", function: str = "AVG",
             version: str = "RT") -> pd.DataFrame:
        """
        Load with and without pumping, MW; load is gross generation +
        import - export - pumping. The forecast versions have it without
        pumping only.
        """
        return self._fetch("Load", start=start, end=end, aggregation=aggregation, function=function,
                           version=version)
    #----------------------------------------------------------------------------------------------------------------------------
    def MaximalniCenySVRnaDT(self, start: DateLike, end: DateLike) -> pd.DataFrame:
        """
        Maximum prices of balancing services on the day-ahead market, a row
        per day and currency. Data from 2022-08-26 to 2024-07-04.
        """
        return self._fetch("MaximalniCenySVRnaDT", start=start, end=end)
    #----------------------------------------------------------------------------------------------------------------------------
    def NepredvidatelneOdmitnuteNabidky(self, start: DateLike, end: DateLike,
                                        param1: str | None = None) -> pd.DataFrame:
        """
        Unforeseeably rejected bids of one product (param1, aFRR+ if none
        is given): per hour and bid the price offered (Kč) and the power
        not accepted (MW).
        """
        return self._fetch("NepredvidatelneOdmitnuteNabidky", start=start, end=end, param1=param1)
    #----------------------------------------------------------------------------------------------------------------------------
    def OdhadovanaCenaOdchylky(self, start: DateLike, end: DateLike) -> pd.DataFrame:
        """
        ČEPS's estimate of the imbalance price, Kč/MWh, per quarter hour
        (per hour for older data, e.g. 2020). A range in the future or with
        end before start gives an empty frame.

        A price of exactly 0 is common (about one interval in five) and is
        a real value. The service ignores aggregation and function here.
        """
        return self._fetch("OdhadovanaCenaOdchylky", start=start, end=end)
    #----------------------------------------------------------------------------------------------------------------------------
    def OfferPrices(self, start: DateLike, end: DateLike, version: str | None = None,
                    param1: str | None = None) -> pd.DataFrame:
        """
        Offer prices of regulating energy: per hour and bid the price (Kč)
        and the power (MW). Data from November 2017 to 2022-03-31.
        """
        return self._fetch("OfferPrices", start=start, end=end, version=version, param1=param1)
    #----------------------------------------------------------------------------------------------------------------------------
    def PowerBalance(self, start: DateLike, end: DateLike, aggregation: str = "WE", function: str = "AVG",
                     version: str = "YF", param1: str = "all") -> pd.DataFrame:
        """
        Yearly forecast of the power balance: domestic sources, outages,
        reserve of ancillary services and load, MW. param1 picks one part.
        """
        return self._fetch("PowerBalance", start=start, end=end, aggregation=aggregation,
                           function=function, version=version, param1=param1)
#----------------------------------------------------------------------------------------------------------------------------

# A method added to the catalog needs its wrapper too.
_missing = [m for m in CEPS_METHODS if not callable(getattr(Ceps, m, None))]
if _missing:
    raise ImportError(f"Ceps has no wrapper for {', '.join(_missing)}")
