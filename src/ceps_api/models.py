"""
Types describing the methods of the ČEPS service used in catalog.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


#----------------------------------------------------------------------------------------------------------------------------
class CepsResponseType(Enum):
    """The shape of a method's response, which decides the parser the wrappers use."""

    # A plain time series: rows with a date and one value per series.
    SERIES = "series"
    # A time series whose rows have no date attribute (OdhadovanaCenaOdchylky).
    ESTIMATED_PRICE = "estimated_price"
    # Rows that are not one per timestamp: several share a date or they have
    # none at all (EmergencyExchange, OfferPrices).
    TABLE = "table"
    # A list of codes with their descriptions (DataVersion, DataAgregation).
    CODES = "codes"
    # A single message of text fields (EmergencyExchangeACER).
    MESSAGE = "message"
#----------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CepsMethod:
    """What is known about one method of the ČEPS service."""

    # The method description is by personal understanding, check the ČEPS documentation
    # to see full description (it is in Czech and too long to put here).
    description: str

    # Parameters the WSDL marks as compulsory.
    # Most methods need the dates; a few require nothing.
    required_params: tuple[str, ...] = ("dateFrom", "dateTo")

    # Parameters the WSDL marks as optional.
    optional_params: tuple[str, ...] = ()

    # Needed parameters the service does not work without: it answers
    # with a server error instead of data.
    needed_params: tuple[str, ...] = ()

    # The aggregations the method returns data for, from the ČEPS documentation and
    # checked by trying. None means not known, so any aggregation is let through.
    aggregations: tuple[str, ...] | None = None

    # The data versions the method has, from the ČEPS documentation and
    # checked by trying; any other comes back empty. None means not known,
    # so any version is let through.
    versions: tuple[str, ...] | None = None

    # The values a filter parameter (param1, para1, param2) takes, from the
    # ČEPS documentation and checked by trying. What they stand for is
    # listed above CEPS_METHODS.
    param_values: dict[str, tuple[str, ...]] = field(default_factory=dict)

    # The shape of the response, which decides the parser the wrappers use.
    # Found out by experiment (the service does not say).
    response_type: CepsResponseType = CepsResponseType.SERIES
#----------------------------------------------------------------------------------------------------------------------------
