"""Functions for converting between the wrapper interface and the service interface, and for turning service responses into DataFrames."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import cast

import pandas as pd

from .models import CepsResponseType
from .parsing import PRAGUE, Fields, Parsed, Rows, TimeSeries

# What the wrappers take as start and end.
DateLike = date | datetime | str
#----------------------------------------------------------------------------------------------------------------------------

def to_ceps_time(x: DateLike) -> str:
    """
    Accepts a date, datetime or ISO string ('YYYY-MM-DD', with a time or
    without), gives the timestamp ČEPS wants, which is Czech local time
    with no zone on it. One with a timezone is converted to Czech time
    first; a naive one is taken as Czech time already.

    The zone has to come off because the service does not read it: it
    answers '...T10:00:00Z' with the data of 10:00 Czech time.

    Local time cannot tell apart the two runs of the hour repeated when the
    clocks go back. The service takes such a time as the second run; a
    period that starts before 02:00 covers both. A time in the hour skipped
    in spring is moved an hour on.

    Raises ValueError for a string that is not a date or time.
    """
    if isinstance(x, str):
        try:
            # fromisoformat does not know the Z of UTC before Python 3.11.
            x = datetime.fromisoformat(x[:-1] + "+00:00" if x[-1:] in ("Z", "z") else x)
        except ValueError:
            raise ValueError(f"not a date or time: {x!r}, expected e.g. "
                             "'2026-09-14' or '2026-09-14T10:00:00'") from None
    if isinstance(x, datetime):
        if x.tzinfo is not None:
            x = x.astimezone(PRAGUE)
        return x.strftime("%Y-%m-%dT%H:%M:%S")
    return x.strftime("%Y-%m-%dT00:00:00")
#----------------------------------------------------------------------------------------------------------------------------

def _prague(values: Iterable[datetime]) -> pd.DatetimeIndex:
    """
    Datetimes with mixed +01:00/+02:00 offsets -> one Europe/Prague index.
    Through UTC, so the repeated hour of the DST change stays two hours.
    """
    return pd.DatetimeIndex(pd.to_datetime(list(values), utc=True)).tz_convert(PRAGUE)
#----------------------------------------------------------------------------------------------------------------------------

def to_dataframe(response_type: CepsResponseType, data: Parsed) -> pd.DataFrame:
    """
    What the parser returns -> a DataFrame:

      SERIES, ESTIMATED_PRICE  index "timestamp" (Europe/Prague), a column per series
      TABLE                    a row per row, date columns in Europe/Prague
      CODES                    index "code", column "description"
      MESSAGE                  one row, a column per field
    """
    # The response type decides the shape of data, which the casts tell the type checker.
    if response_type in (CepsResponseType.SERIES, CepsResponseType.ESTIMATED_PRICE):
        series = cast(TimeSeries, data)
        if not series:
            return pd.DataFrame(index=pd.DatetimeIndex([], tz=PRAGUE, name="timestamp"))
        df = pd.DataFrame(list(series.values()), index=_prague(series))
        df.index.name = "timestamp"
        return df.sort_index()
    if response_type is CepsResponseType.TABLE:
        df = pd.DataFrame(cast(Rows, data))
        for col in df.columns:
            # A column of dates only; one the parser left as text stays text.
            values = df[col].dropna()
            if len(values) and values.map(lambda v: isinstance(v, datetime)).all():
                df[col] = pd.Series(_prague(df[col]), index=df.index)
        if "date" in df.columns:
            df = df.sort_values("date", kind="stable", ignore_index=True)
        return df
    fields = cast(Fields, data)
    if response_type is CepsResponseType.CODES:
        return pd.DataFrame({"description": pd.Series(fields, dtype=object)}).rename_axis("code")
    # MESSAGE
    return pd.DataFrame([fields]) if fields else pd.DataFrame()
#----------------------------------------------------------------------------------------------------------------------------