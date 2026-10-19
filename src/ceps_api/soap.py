"""SOAP transport for the ČEPS service: envelope out, raw XML back."""
from __future__ import annotations

import http.client
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

# SOAP endpoint (ASMX web service) that every request is POSTed to
CEPS_URL = "https://www.ceps.cz/_layouts/CepsData.asmx"
# XML namespace of the service; identifies the method elements in the envelope and the SOAPAction prefix
CEPS_NS = "https://www.ceps.cz/CepsData/"

#----------------------------------------------------------------------------------------------------------------------------
class CepsError(RuntimeError):
    pass
#----------------------------------------------------------------------------------------------------------------------------

def call(method: str, params: dict[str, object], timeout: int = 30) -> bytes:
    """
    Posts one SOAP call and returns the response body for method in CEPS_METHODS.
    Parameters that are None or empty are left out of the envelope.
    timeout is in seconds.

    Raises CepsError if the service answers with an error or with something
    that is not XML (e.g. an HTML page during an outage), or cannot be
    reached in time.
    """
    # Build the request; passing data makes urllib send it as a POST.
    request = urllib.request.Request(
        CEPS_URL,
        # The XML envelope, converted from str to bytes.
        data=_envelope(method, params).encode("utf-8"),
        # SOAPAction tells the server which method is being called.
        headers={"Content-Type": "text/xml; charset=utf-8",
                 "SOAPAction"  : f'"{CEPS_NS}{method}"'})
    try:
        # Send it and return the raw XML response.
        with urllib.request.urlopen(request, timeout=timeout) as r:
            # The service answers in text/xml; anything else is not its answer,
            # e.g. a maintenance page, which may even parse as XML.
            content_type = r.headers.get("Content-Type", "")
            if "xml" not in content_type:
                raise CepsError(f"{method}: unexpected answer from ČEPS ({content_type or 'no Content-Type'})")
            body: bytes = r.read()
            return body
    except urllib.error.HTTPError as e:
        # The server answered with an error status: raise its SOAP fault
        # message if it sent one, otherwise just the HTTP code.
        # "from None" hides the original urllib traceback.
        message = _fault(e.read()) or f"HTTP {e.code}"
        raise CepsError(f"{method}: {message}") from None
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as e:
        # No answer at all: DNS, connection refused, timeout, or an answer cut
        # off (HTTPException). URLError wraps the real cause in .reason.
        reason = getattr(e, "reason", None) or e
        raise CepsError(f"{method}: could not reach ČEPS ({reason})") from None
#----------------------------------------------------------------------------------------------------------------------------
def _envelope(method: str, params: dict[str, object]) -> str:
    """
    Builds the SOAP request XML for one method call.
    Each parameter becomes a <name>value</name> element inside the
    method element; parameters that are None or empty are skipped.
    Values are XML-escaped.
    """
    # One <name>value</name> line per parameter; None/empty ones are dropped
    # and values are escaped so characters like & or < cannot break the XML.
    inner = "".join(f"  <{k}>{escape(str(v))}</{k}>\n"
                    for k, v in params.items() if v not in (None, ""))
    return (
    # XML declaration.
    '<?xml version="1.0" encoding="utf-8"?>\n'
    # SOAP 1.1 envelope; the soap prefix is bound to the standard namespace.
    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soap:Body>'
            # Method element in the ČEPS namespace, wrapping the parameters.
            f'<{method} xmlns="{CEPS_NS}">\n{inner}'
            f'</{method}>'
        '</soap:Body>'
    '</soap:Envelope>'
    )
#----------------------------------------------------------------------------------------------------------------------------
def _fault(body: bytes) -> str:
    """
    Pulls the error message out of a SOAP fault response.
    Returns "" if the body is not XML or holds no message.
    """
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        # Not XML at all, e.g. an HTML error page.
        return ""
    # Walk every element; endswith ignores the namespace prefix on the tag.
    for e in root.iter():
        if e.tag.endswith("faultstring") and e.text:
            return e.text
    return ""
#----------------------------------------------------------------------------------------------------------------------------