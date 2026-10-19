"""
Catalog of the ČEPS service: its methods, their parameters and the aggregation, function and version values
they take.

What the parameters mean is described in the interface description that
ČEPS publishes at https://www.ceps.cz/cs/webove-sluzby ("Popis rozhraní pro
poskytování strukturovaných dat", version 3.2). Unfortunately the ČEPS service itself does
not strictly follow their own document; see the notes below.

Every available ČEPS method has a wrapper of the same name, which returns
a DataFrame; Ceps.parameters() lists what each of them accepts.

scripts/ceps_catalog.py writes a fresh version of this dict (for when the
service changes) to a separate file, to be reviewed and copied over by hand:
required_params and optional_params come from the WSDL and were verified by
trying.

Note the WSDL spells para1 without the "m" for PowerBalance, Generation
and GenerationRES, and spells aggregation as "agregation", so beware.

A value the ČEPS service does not know is not an error: everything comes back,
or nothing does, so the wrappers check the value.

Points in the ČEPS documentation which are not followed, because the
service does not adhere to them:
  - it gives EmergencyExchangeACER an aggregation and a function, which
    the method does not seem to take
  - it has mFFR+ for the mFRR+ of AktualniCenaRE (the latter is correct, a typo of F for R)
  - it allows only AVG for CrossborderPowerFlows and ExportImportSVR; however
    other functions work too
  - its tables of the aggregations allowed per period are not enforced
    (see CEPS_AGGREGATIONS). They leave out QH for GenerationPlan and YR
    for EmergencyExchange, which both return data, and have the peak and
    off-peak variants for PowerBalance, which return nothing
  - it has OdhadovanaCenaOdchylky per hour; it is per quarter hour now
  - it does not describe Emise and OfferPrices at all
"""

from __future__ import annotations

from .models import CepsMethod, CepsResponseType

#----------------------------------------------------------------------------------------------------------------------------
CEPS_METHODS = {
    "AktivaceSVRvCR": CepsMethod(
        "Activated balancing energy (aFRR+/-, mFRR+/-, mFRR5), [MW]",
        optional_params=("agregation", "function", "param1"),
        aggregations=("MI", "QH", "HR", "DY"),
        param_values={"param1": ("all", "aFRR+", "aFRR-", "mFRR+", "mFRR-", "RR+", "RR-", "mFRR5")},
    ),
    "AktualniCenaRE": CepsMethod(
        "Price of activated regulating energy (aFRR, mFRR+/-, mFRR5), [EUR/MWh]",
        optional_params=("param1",),
        param_values={"param1": ("All", "aFRR", "mFRR+", "mFRR-", "mFRR5")},
    ),
    "AktualniSystemovaOdchylkaCR": CepsMethod(
        "Current system imbalance of the Czech control area, [MW]",
        optional_params=("agregation", "function"),
        aggregations=("MI", "QH", "HR"),
    ),
    "CrossborderPowerFlows": CepsMethod(
        "Actual and planned flows per neighbouring operator, [MW]",
        optional_params=("agregation", "function", "version"),
        needed_params=("agregation", "function"),
        aggregations=("MI", "QH", "HR", "DY", "WE", "MO", "YR"),
        versions=("RT",),
    ),
    "DataAgregation": CepsMethod(
        "Lists the aggregation codes. Not a time series",
        required_params=(),
        response_type=CepsResponseType.CODES,
    ),
    "DataVersion": CepsMethod(
        "Lists the version codes. Not a time series",
        required_params=(),
        response_type=CepsResponseType.CODES,
    ),
    "EmergencyExchange": CepsMethod(
        "Emergency assistance, redispatch and regulating energy from abroad, a row per border and direction. Only has rows when something happened",
        optional_params=("agregation", "function", "version", "param1", "param2"),
        needed_params=("agregation", "function", "version"),
        aggregations=("QH", "HR", "DY", "DYO", "DYP", "WE", "WEO", "WEP", "MO", "MOO", "MOP", "YR", "YRO", "YRP"),
        versions=("RT",),
        param_values={"param1": ("All", "E", "R"), "param2": ("All", "APG", "SEPS", "TenneT", "PSE", "50HzT")},
        response_type=CepsResponseType.TABLE,
    ),
    "EmergencyExchangeACER": CepsMethod(
        "Emergency exchange as an ACER message. Not a time series",
        optional_params=("param1", "param2"),
        param_values={"param1": ("All", "E", "R"), "param2": ("All", "APG", "SEPS", "TenneT", "PSE", "50HzT")},
        response_type=CepsResponseType.MESSAGE,
    ),
    "Emise": CepsMethod(
        "CO2 intensity of generation, [g CO2/kWh]. Always per quarter hour, the service ignores the aggregation",
        optional_params=("agregation", "function", "version", "param1"),
        needed_params=("version",),
        aggregations=("QH",),
        versions=("RT",),
    ),
    "ExportImportSVR": CepsMethod(
        "Exchange with the European balancing platforms (imbalance netting, MARI, PICASSO)",
        optional_params=("agregation", "function", "param1"),
        aggregations=("MI", "QH", "HR", "DY"),
        param_values={"param1": ("PcorrHVNCER", "PcorrImbalanceNetting", "PcorrMari", "PcorrPicasso", "VYKON")},
    ),
    "ExportImportVykonu": CepsMethod(
        "Export (+) and import (-) of power within the European platforms and foreign assistance, [MW]. Data from 2022-05-20 to 2023-08-25, then ExportImportSVR",
        optional_params=("agregation", "function"),
        aggregations=("MI", "QH", "HR", "DY"),
    ),
    "Frekvence": CepsMethod(
        "System frequency, [Hz]",
    ),
    "Generation": CepsMethod(
        "Gross generation by plant type, [MW]",
        optional_params=("agregation", "function", "version", "para1"),
        needed_params=("agregation", "function", "version", "para1"),
        aggregations=("QH", "HR", "DY", "DYO", "DYP", "WE", "WEO", "WEP", "MO", "MOO", "MOP", "YR", "YRO", "YRP"),
        versions=("RT",),
        param_values={"para1": ("all", "AE", "JE", "PE", "PPE", "PVE", "VE", "ZE", "VTE", "FVE")},
    ),
    "GenerationPlan": CepsMethod(
        "Planned gross generation, [MW]",
        optional_params=("agregation", "function", "version"),
        needed_params=("agregation", "function", "version"),
        aggregations=("QH", "HR", "DY", "DYO", "DYP", "WE", "WEO", "WEP", "MO", "MOO", "MOP", "YR", "YRO", "YRP"),
        versions=("RT",),
    ),
    "GenerationRES": CepsMethod(
        "Estimated wind and solar generation, [MW]",
        optional_params=("agregation", "function", "version", "para1"),
        needed_params=("agregation", "function", "version", "para1"),
        aggregations=("MI", "QH", "HR", "DY", "DYO", "DYP", "WE", "WEO", "WEP", "MO", "MOO", "MOP", "YR", "YRO", "YRP"),
        versions=("RT",),
        param_values={"para1": ("all", "VTE", "FVE")},
    ),
    "Load": CepsMethod(
        "Load with and without pumping, [MW]; load is gross generation + import - export - pumping. The forecast versions have it without pumping only",
        optional_params=("agregation", "function", "version"),
        needed_params=("agregation", "function", "version"),
        aggregations=("MI", "QH", "HR", "DY", "DYO", "DYP", "WE", "WEO", "WEP", "MO", "MOO", "MOP", "YR", "YRO", "YRP"),
        versions=("RT", "DR", "DF", "WF", "MF", "YF"),
    ),
    "MaximalniCenySVRnaDT": CepsMethod(
        "Maximum prices of balancing services on the day-ahead market, a row per day and currency. Data from 2022-08-26 to 2024-07-04",
        response_type=CepsResponseType.TABLE,
    ),
    "NepredvidatelneOdmitnuteNabidky": CepsMethod(
        "Unforeseeably rejected bids of one product (aFRR+ if none is given): per hour and bid the price offered [Kč] and the power not accepted [MW]",
        optional_params=("param1",),
        param_values={"param1": ("FCR", "aFRR+", "aFRR-", "mFRR+", "mFRR-", "mFRR5")},
        response_type=CepsResponseType.TABLE,
    ),
    "OdhadovanaCenaOdchylky": CepsMethod(
        "Estimated imbalance price, [Kč/MWh]. Not a plain time series",
        response_type=CepsResponseType.ESTIMATED_PRICE,
    ),
    "OfferPrices": CepsMethod(
        "Offer prices of regulating energy: per hour and bid the price [Kč] and the power [MW]. Data from November 2017 to 2022-03-31",
        optional_params=("version", "param1"),
        response_type=CepsResponseType.TABLE,
    ),
    "PowerBalance": CepsMethod(
        "Yearly forecast of the power balance: domestic sources, outages, reserve of ancillary services and load, [MW]",
        optional_params=("agregation", "function", "version", "para1"),
        needed_params=("agregation", "function", "version", "para1"),
        aggregations=("WE", "YR"),
        versions=("YF",),
        param_values={"para1": ("all", "BALANCE", "TDGENCAP", "TOUTAGES", "SYSSERVR", "LOAD")},
    ),
}
#----------------------------------------------------------------------------------------------------------------------------
"""
Values for aggregation.
Which codes a method supports differs, see CepsMethod.aggregations; a code it does
not support gives an empty document, not an error.

A time step comes back when it starts between dateFrom and dateTo, both
included, and it always covers the whole step, whichever part of it the
period asks for. So a period has to hold the start of a step to get it:
1 January for YR, the first of the month for MO.

WE and WEO are wrong around the clock changes. For the week in which the
clocks go forward the service returns several rows, none of them the mean
of that week, which the wrappers refuse with a CepsError; the week after
lacks its first hour and the week of the change in autumn is slightly off
too. The days and months there (DY, MO) are right.
"""
CEPS_AGGREGATIONS = {
    "MI": "minute",
    "QH": "quarter hour",
    "HR": "hour",
    "DY": "day",
    "DYO": "day off-peak",
    "DYP": "day peak",
    "WE": "week",
    "WEO": "week off-peak",
    "WEP": "week peak",
    "MO": "month",
    "MOO": "month off-peak",
    "MOP": "month peak",
    "YR": "year",
    "YRO": "year off-peak",
    "YRP": "year peak",
}
#----------------------------------------------------------------------------------------------------------------------------
"""
Values for function: how the raw values are combined within one
aggregation step.

An aggregation needs a function with it: without one the service fails
or returns rows that hold no values.
"""
CEPS_FUNCTIONS = ("AVG", "MIN", "MAX", "SUM")
#----------------------------------------------------------------------------------------------------------------------------
"""Labels for version, as listed by the DataVersion method. See ČEPS documentation for meaning"""
CEPS_DATA_VERSIONS = {
    "RT": "real data",
    "DF": "daily forecast",
    "DR": "daily revision",
    "IDF": "intraday forecast",
    "WF": "weekly forecast",
    "WR": "weekly revision",
    "MF": "monthly forecast",
    "MR": "monthly revision",
    "QF": "quarterly forecast",
    "QR": "quarterly revision",
    "YF": "yearly forecast",
    "YR": "yearly revision",
}
#----------------------------------------------------------------------------------------------------------------------------