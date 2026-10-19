"""Turns a ČEPS response document into plain Python."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .models import CepsResponseType
from .soap import CepsError

#----------------------------------------------------------------------------------------------------------------------------
PRAGUE = ZoneInfo("Europe/Prague")

# The attributes of a row that hold a date. The ČEPS schema
# (StructuredData.xsd) types the columns by their id: value13, value14 and
# value21 are dates, like the date of the row itself.
_DATE_IDS = ("date", "value13", "value14", "value21")

# One value of a row, as _value reads it.
Value = datetime | float | str
# What the parsers return: {timestamp: {series name: value}}, one dict per
# row, and {name: text}.
TimeSeries = dict[datetime, dict[str, Value]]
Rows = list[dict[str, Value]]
Fields = dict[str, str]
Parsed = TimeSeries | Rows | Fields
#----------------------------------------------------------------------------------------------------------------------------

def _local(tag: str) -> str:
    """The tag without the namespace prefix ElementTree puts on it."""
    return tag.rsplit("}", 1)[-1]
#----------------------------------------------------------------------------------------------------------------------------

def _value(key: str, text: str) -> Value:
    """
    One attribute of a row: a datetime for a date column, else a float if
    the text reads as a number, else the text itself.
    """
    if key in _DATE_IDS:
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return text
    try:
        return float(text)
    except ValueError:
        pass
    # The schema warns that numbers in the text columns have a decimal comma.
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return text
#----------------------------------------------------------------------------------------------------------------------------

def parse_rows(raw: bytes) -> Rows:
    """
    Parses a raw ČEPS SOAP response into one dict per row.

    Every report other than the two code lists and the ACER message is the
    same document. It describes its columns once and then lists the rows:

        <serie id="value3" name="mFRR5 [MW]" />
        <serie id="value15" name="Unit" />
        <item date="2024-06-01T00:00:00+02:00" value3="2579" value15="LIMIT_PRICE_CZK" />

    which becomes

        [{"date": datetime(2024, 6, 1, 0, 0, tzinfo=+02:00),
          "mFRR5 [MW]": 2579.0,
          "Unit": "LIMIT_PRICE_CZK"}]

    A row has "date" only if the report gives it one, and several rows may
    share it, which is why this is a list. A report with one row per
    timestamp is easier to read with parse_series.

    Dates come back with the Czech UTC offset attached, so they are
    timezone-aware and safe to compare across the DST change. The schema
    lists the columns value1 to value21; the service goes beyond that, so
    the ids are taken as they come.

    Raises CepsError when two columns share a name, which would lose values.
    """
    root = ET.fromstring(raw)
    # Column lookup: attribute name used in the rows -> readable series name.
    names = {s.attrib["id"]: s.attrib["name"]
             for s in root.iter() if _local(s.tag) == "serie" and s.get("id") and s.get("name")}
    # date keeps its own name, so a series may not take it either.
    taken = {"date"}
    for name in names.values():
        if name in taken:
            raise CepsError(f"two columns are named {name!r}")
        taken.add(name)
    # Every attribute is one value; use the readable name, falling back to
    # the raw attribute name (date has no series).
    return [{names.get(key, key): _value(key, text) for key, text in item.attrib.items()}
            for item in root.iter() if _local(item.tag) == "item"]
#----------------------------------------------------------------------------------------------------------------------------

def parse_series(raw: bytes) -> TimeSeries:
    """
    Parses a raw ČEPS SOAP response into {timestamp: {series name: value}}.

    The response describes its columns once and then lists the rows:

        <serie id="value1" name="aFRR [EUR/MWh]" />
        <item date="2026-09-14T00:00:00+02:00" value1="196.1663" />

    which becomes

        {datetime(2026, 9, 14, 0, 0, tzinfo=+02:00): {"aFRR [EUR/MWh]": 196.1663}}

    Values are floats; one that is not a number is kept as the original
    string. A response with no rows gives an empty dict.

    Timestamps come back with the Czech UTC offset attached, so they
    are timezone-aware and safe to compare across the DST change.

    Raises CepsError for a report that is not one row per timestamp, where
    this shape would lose rows: a row without a date or two rows with the
    same one. parse_rows reads those.
    """
    out: TimeSeries = {}
    for row in parse_rows(raw):
        when = row.pop("date", None)
        if not isinstance(when, datetime):
            raise CepsError("a row has no date, so this is not a time series")
        if when in out:
            raise CepsError(f"more than one row for {when.isoformat()}")
        out[when] = row
    return out

#----------------------------------------------------------------------------------------------------------------------------
def parse_estimated_price(raw: bytes) -> TimeSeries:
    """
    Parses an OdhadovanaCenaOdchylky response into
    {timestamp: {"Estimated price [Kč/MWh]": price}}, the shape of
    parse_series.

    Its rows have no date attribute, which is why parse_series does not
    read it. The time is split over two columns instead:

        <serie id="value2" name="Estimated price [Kč/MWh]" />
        <serie id="value13" name="Date" />
        <serie id="value15" name="Interval" />
        <item value2="3934.46" value13="2026-10-05T02:00:00+02:00"
              value15="00:00-00:15" />

    Only the day of Date is meaningful (it is UTC midnight shown in Czech
    time) and Interval is Czech wall-clock time, so the timestamp is that
    day plus the start of the interval, with the Czech UTC offset attached
    like the timestamps of parse_series.

    On the day the clocks go back the 02:00-03:00 intervals are listed
    twice; the second run gets the winter offset.

    Raises CepsError, like parse_series, where this shape would lose rows:
    a row without its day, interval or price, or two rows for the same
    time.
    """
    out: TimeSeries = {}
    seen: set[datetime] = set()
    for row in parse_rows(raw):
        day, interval = row.pop("Date", None), row.pop("Interval", None)
        # The price is the one remaining column.
        if not isinstance(day, datetime) or not isinstance(interval, str) or not interval or not row:
            raise CepsError("a row has no Date, Interval or price")
        hour, minute = interval.split("-")[0].split(":")
        local = datetime(day.year, day.month, day.day, int(hour), int(minute))
        # A wall-clock time seen before is the repeated hour: fold=1 picks
        # its second occurrence.
        aware = local.replace(tzinfo=PRAGUE, fold=1 if local in seen else 0)
        seen.add(local)
        # Fixed offset rather than the zone itself, because two datetimes
        # in the same zone compare equal regardless of fold and the
        # repeated hour would overwrite itself as a dict key.
        offset = aware.utcoffset()
        assert offset is not None  # aware has a zone
        when = local.replace(tzinfo=timezone(offset))
        if when in out:
            raise CepsError(f"more than one row for {when.isoformat()}")
        out[when] = row
    return out
#----------------------------------------------------------------------------------------------------------------------------

def parse_codes(raw: bytes) -> Fields:
    """
    Parses a DataVersion or DataAgregation response into {code: description}.

    The response is a plain list:

        <version name="RT " description="Reálná data" />

    which becomes {"RT": "Reálná data"}. The service pads the codes with
    spaces to three characters, so they are stripped.
    """
    root = ET.fromstring(raw)
    return {e.attrib["name"].strip(): e.attrib["description"]
            for e in root.iter() if e.get("name") and e.get("description")}
#----------------------------------------------------------------------------------------------------------------------------

def parse_message(raw: bytes) -> Fields:
    """
    Parses an EmergencyExchangeACER response into {field: text}.

    The response is one message, however long the period asked for, with
    one element per field:

        <eventStatus>Active</eventStatus>
        <eventStart>2025-02-09T00:00:00</eventStart>

    which becomes {"eventStatus": "Active", "eventStart": "2025-02-09T00:00:00"}.
    Everything stays text, as ČEPS sent it. The remarks field holds the
    exchanges themselves, one "Direction-Type-MWh|" line each.
    """
    root = ET.fromstring(raw)
    # The fields are the elements without children that carry text; the
    # wrappers around them have children.
    return {_local(e.tag): e.text.strip()
            for e in root.iter() if len(e) == 0 and e.text and e.text.strip()}
#----------------------------------------------------------------------------------------------------------------------------

# The parser for each CepsMethod.response_type.
_PARSERS: dict[CepsResponseType, Callable[[bytes], Parsed]] = {
    CepsResponseType.SERIES: parse_series,
    CepsResponseType.ESTIMATED_PRICE: parse_estimated_price,
    CepsResponseType.TABLE: parse_rows,
    CepsResponseType.CODES: parse_codes,
    CepsResponseType.MESSAGE: parse_message,
}
#----------------------------------------------------------------------------------------------------------------------------

def parse(response_type: CepsResponseType, raw: bytes) -> Parsed:
    """
    Parses a raw ČEPS SOAP response with the parser of its response type:

      SERIES           parse_series
      ESTIMATED_PRICE  parse_estimated_price
      TABLE            parse_rows
      CODES            parse_codes
      MESSAGE          parse_message

    Raises CepsError as the parser does, and for a response it cannot read:
    one that is not XML (cut off, say) or has a value in a form it does not
    know (an Interval that is not "HH:MM-HH:MM").
    """
    try:
        return _PARSERS[response_type](raw)
    except (ET.ParseError, ValueError) as e:
        raise CepsError(f"unreadable response ({e})") from None
#----------------------------------------------------------------------------------------------------------------------------