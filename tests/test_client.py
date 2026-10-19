"""
Tests of Ceps against responses of the real service saved in tests/data
(the raw bytes of soap.call, saved on 2026-10-17).

The offline tests replace soap.call, or urllib.request.urlopen for the
failures of the service, so they need no network. The one marked live
calls ČEPS; CI leaves it out with pytest -m "not live".
"""
import http.client
import io
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from ceps_api import Ceps, CepsError, soap
from ceps_api.convert import to_ceps_time
from ceps_api.models import CepsResponseType
from ceps_api.parsing import parse
from ceps_api.validation import validate

DATA = Path(__file__).parent / "data"
# 2025-10-26, the clocks went back: 02:00-03:00 twice, so 25 hours, 100 quarter hours.
DST_DAY = ("2025-10-26", "2025-10-26T23:59:00")
#----------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def service(monkeypatch):
    """
    Replaces the network: soap.call answers with the saved file given by
    service.answer, and service.calls records what was sent.
    """
    class Service:
        def __init__(self):
            self.answer = None
            self.calls = []

        def call(self, method, params, timeout=30):
            self.calls.append((method, dict(params)))
            if self.answer is None:
                raise AssertionError(f"{method} should not have been sent")
            return (DATA / self.answer).read_bytes()

    fake = Service()
    monkeypatch.setattr(soap, "call", fake.call)
    return fake
#----------------------------------------------------------------------------------------------------------------------------

def assert_quarter_hours(df: pd.DataFrame, rows: int) -> None:
    """A Europe/Prague index named timestamp, rows of it, 15 minutes apart in real time."""
    assert df.index.name == "timestamp"
    assert str(df.index.tz) == "Europe/Prague"
    assert len(df) == rows
    assert df.index.is_unique and df.index.is_monotonic_increasing
    assert (df.index.to_series().diff().dropna() == timedelta(minutes=15)).all()
#----------------------------------------------------------------------------------------------------------------------------

def test_series_over_the_dst_change(service):
    """
    A time series over the day the clocks went back: 100 quarter hours with the
    repeated hour in both offsets, and the arguments as they go out to ČEPS.
    """
    service.answer = "series_imbalance_qh_dst.xml"
    df = Ceps().AktualniSystemovaOdchylkaCR(*DST_DAY, aggregation="QH")

    assert_quarter_hours(df, 100)
    assert list(df.columns) == ["Aktuální odchylka [MW]"]
    # The repeated hour comes back twice, summer time first.
    assert [str(t) for t in df.index[8:13]] == ["2025-10-26 02:00:00+02:00", "2025-10-26 02:15:00+02:00",
                                                "2025-10-26 02:30:00+02:00", "2025-10-26 02:45:00+02:00",
                                                "2025-10-26 02:00:00+01:00"]
    # The arguments go out under the service's names, the dates as Czech local time.
    assert service.calls == [("AktualniSystemovaOdchylkaCR",
                              {"dateFrom": "2025-10-26T00:00:00", "dateTo": "2025-10-26T23:59:00",
                               "agregation": "QH", "function": "AVG"})]
#----------------------------------------------------------------------------------------------------------------------------

def test_estimated_price_over_the_dst_change(service):
    """The estimated price of the imbalance over the same day: 100 quarter hours from midnight."""
    service.answer = "estimated_price_dst.xml"
    df = Ceps().OdhadovanaCenaOdchylky(*DST_DAY)

    assert_quarter_hours(df, 100)
    assert list(df.columns) == ["Estimated price [Kč/MWh]"]
    assert df.index[0] == pd.Timestamp("2025-10-26 00:00", tz="Europe/Prague")
#----------------------------------------------------------------------------------------------------------------------------

def test_codes(service):
    """A list of codes (DataVersion): indexed by the code, with its description."""
    service.answer = "codes_data_version.xml"
    df = Ceps().DataVersion()

    assert df.index.name == "code"
    assert list(df.columns) == ["description"]
    # The service pads the codes with spaces; they come back stripped.
    assert "RT" in df.index and "DF" in df.index
    assert df.loc["IDF", "description"] == "Vnitrodenní predpoved"
#----------------------------------------------------------------------------------------------------------------------------

def test_table_of_rows_sharing_a_date(service):
    """
    A table whose rows share dates (EmergencyExchange): a date column instead
    of an index, sorted by date, the numbers as floats.
    """
    service.answer = "table_emergency_exchange.xml"
    df = Ceps().EmergencyExchange("2025-02-09", "2025-02-09T23:59:00")

    assert list(df.columns) == ["date", "Border and direction", "Type of exchange", "Power [MW] / Energy [MWh]*"]
    assert len(df) == 84
    # The service lists the rows border by border; they come back in order of date.
    assert str(df["date"].dt.tz) == "Europe/Prague"
    assert df["date"].is_monotonic_increasing
    assert df["date"].iloc[0] == pd.Timestamp("2025-02-09 00:00", tz="Europe/Prague")
    assert df["Power [MW] / Energy [MWh]*"].dtype == float
    # param1 and param2 are None, so they are left out.
    assert service.calls == [("EmergencyExchange",
                              {"dateFrom": "2025-02-09T00:00:00", "dateTo": "2025-02-09T23:59:00",
                               "agregation": "QH", "function": "AVG", "version": "RT"})]
#----------------------------------------------------------------------------------------------------------------------------

def test_message(service):
    """A message (EmergencyExchangeACER): its fields as one row of text."""
    service.answer = "message_emergency_exchange_acer.xml"
    df = Ceps().EmergencyExchangeACER("2025-02-09", "2025-02-09T23:59:00")

    # One row however long the period, all of it text as ČEPS sent it.
    assert len(df) == 1
    assert list(df.columns) == ["messageId", "eventStatus", "publicationDate", "eventStart", "eventStop",
                                "marketParticipant", "marketParticipantCode", "remarks"]
    assert all(isinstance(v, str) for v in df.iloc[0])
    assert df.loc[0, "eventStart"] == "2025-02-09T00:00:00"
    assert df.loc[0, "remarks"].startswith("Direction-Type-MWh|")
#----------------------------------------------------------------------------------------------------------------------------

class Answer(io.BytesIO):
    """What urlopen returns: the body and its headers."""
    def __init__(self, body: bytes, content_type: str):
        super().__init__(body)
        self.headers = {"Content-Type": content_type}


@pytest.mark.parametrize("answer, message", [
    # A SOAP fault comes with HTTP 500 and its message is passed on.
    pytest.param(urllib.error.HTTPError(soap.CEPS_URL, 500, "Internal Server Error", None,
                                        io.BytesIO((DATA / "fault_generation.xml").read_bytes())),
                 "Server was unable to process request.", id="fault"),
    # A maintenance page may well parse as XML, so it is told apart by its Content-Type.
    pytest.param(Answer(b"<html><body><p>Maintenance</p></body></html>", "text/html; charset=utf-8"),
                 "unexpected answer from ČEPS (text/html", id="html-page"),
    # XML cut off before its end does not parse.
    pytest.param(Answer((DATA / "series_imbalance_qh_dst.xml").read_bytes()[:-200], "text/xml; charset=utf-8"),
                 "unreadable response", id="cut-off-xml"),
    # The connection dropped while the body was being read.
    pytest.param(http.client.IncompleteRead(b"<?xml"), "could not reach ČEPS", id="incomplete-read"),
    # No connection at all; the reason is passed on.
    pytest.param(urllib.error.URLError(ConnectionRefusedError("refused")), "could not reach ČEPS (refused)",
                 id="unreachable"),
])
def test_failures_of_the_service_raise_ceps_error(monkeypatch, answer, message):
    """Every way the service can fail ends in a CepsError, not in an error of urllib or of the XML parser."""
    # urlopen raises the exception, or returns the answer.
    def urlopen(request, timeout):
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    # The message starts with the method.
    with pytest.raises(CepsError, match=re.escape(f"Generation: {message}")):
        Ceps().Generation(*DST_DAY)
#----------------------------------------------------------------------------------------------------------------------------

PRICE_SERIES = ('<serie id="value2" name="Estimated price [Kč/MWh]" /><serie id="value13" name="Date" />'
                '<serie id="value15" name="Interval" />')


@pytest.mark.parametrize("response_type, body, message", [
    # The same quarter hour twice, outside the hour the clocks go back.
    pytest.param(CepsResponseType.ESTIMATED_PRICE, PRICE_SERIES
                 + '<item value2="1" value13="2026-10-05T02:00:00+02:00" value15="10:00-10:15" />' * 2,
                 "more than one row for 2026-10-05T10:00:00+02:00", id="price-twice"),
    pytest.param(CepsResponseType.ESTIMATED_PRICE, PRICE_SERIES
                 + '<item value13="2026-10-05T02:00:00+02:00" value15="10:00-10:15" />',
                 "a row has no Date, Interval or price", id="price-missing"),
    pytest.param(CepsResponseType.TABLE, '<serie id="value1" name="Price" /><serie id="value2" name="Price" />'
                 '<item date="2026-10-05T00:00:00+02:00" value1="1" value2="2" />',
                 "two columns are named 'Price'", id="same-name"),
])
def test_rows_that_would_be_lost_raise_ceps_error(response_type, body, message):
    """A response that would lose rows or values in its shape is refused, not read in part."""
    with pytest.raises(CepsError, match=re.escape(message)):
        parse(response_type, f"<data>{body}</data>".encode())
#----------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("given, sent", [
    # A date alone means its midnight; a time without seconds gets them.
    ("2026-09-14", "2026-09-14T00:00:00"),
    ("2026-09-14T10:30", "2026-09-14T10:30:00"),
    (date(2026, 9, 14), "2026-09-14T00:00:00"),
    # A time with a zone is converted to Czech time, summer and winter.
    ("2026-09-14T08:00:00Z", "2026-09-14T10:00:00"),
    (datetime(2026, 1, 14, 8, 0, tzinfo=timezone.utc), "2026-01-14T09:00:00"),
])
def test_dates_are_sent_as_czech_local_time(given, sent):
    """to_ceps_time turns strings, dates and datetimes into the Czech local time the service expects."""
    assert to_ceps_time(given) == sent


def test_a_date_that_is_not_one():
    """A string that is not an ISO date or time is refused, not guessed at."""
    with pytest.raises(ValueError, match="not a date or time"):
        to_ceps_time("14.9.2026")
#----------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("call, message", [
    (lambda c: c.AktualniSystemovaOdchylkaCR(*DST_DAY, aggregation="XX"), "unknown aggregation 'XX'"),
    (lambda c: c.AktualniSystemovaOdchylkaCR(*DST_DAY, aggregation="DY"), "no data for aggregation 'DY'"),
    # Generation's filter is para1 to the service; the message says param1 as the wrapper does.
    (lambda c: c.Generation(*DST_DAY, param1="coal"), "Generation has no param1 'coal'"),
])
def test_invalid_calls_are_refused_before_sending(service, call, message):
    """Wrong arguments and unknown methods raise ValueError and nothing goes out to ČEPS."""
    with pytest.raises(ValueError, match=message):
        call(Ceps())
    assert service.calls == []
#----------------------------------------------------------------------------------------------------------------------------

def test_unknown_method_is_refused():
    """A method that is not in CEPS_METHODS is refused by the check."""
    with pytest.raises(ValueError, match="Unknown ČEPS method"):
        validate("NoSuchMethod", {})
#----------------------------------------------------------------------------------------------------------------------------

@pytest.mark.live
def test_live_imbalance_of_yesterday():
    """The real service still answers in the format the saved files have: yesterday's imbalance, a whole day of it."""
    yesterday = datetime.now(ZoneInfo("Europe/Prague")).date() - timedelta(days=1)
    df = Ceps().AktualniSystemovaOdchylkaCR(yesterday, f"{yesterday}T23:59:00", aggregation="QH")

    assert str(df.index.tz) == "Europe/Prague"
    # 92, 96 or 100 quarter hours, depending on the clocks.
    assert len(df) in (92, 96, 100)
