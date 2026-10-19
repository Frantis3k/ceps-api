"""
Writes a fresh CEPS_METHODS for src/ceps_api/catalog.py, built from the ČEPS
service, to scripts/ceps_methods_generated.py.

    uv run scripts/ceps_catalog.py            # parameters from the WSDL
    uv run scripts/ceps_catalog.py --probe    # and try the aggregations again

Run it when ČEPS changes the service. It does not touch catalog.py: it
prints which methods differ from the catalog, and the dict in the generated
file is to be reviewed and copied over CEPS_METHODS by hand.

Each method keeps the fields written by hand in the catalog (description,
needed_params, versions, param_values and response_type). required_params
and optional_params are read from the WSDL. aggregations are kept as they
are, unless --probe is given.

The service does not say which aggregations a method supports. An
unsupported one comes back empty, or the service ignores it and returns the
rows in some other step. So --probe calls every method that takes an
aggregation with every aggregation and keeps the ones whose rows are in
that step (see applied). The call is put together from the catalog: the
method gets its first version and, for a filter it does not work without,
the value that leaves nothing out. The period is a fixed past one, or the
one in PERIODS for a method that has no data then. It makes about 15
requests per method and takes a few minutes.

A method new in the WSDL is added with the name the WSDL gives its report
as the description, as a plain time series; one that is gone from the WSDL
is dropped with a warning.
"""
import dataclasses
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timedelta
from enum import Enum
from itertools import pairwise
from pathlib import Path

# The package is installed in the project environment (uv sync).
from ceps_api import CEPS_AGGREGATIONS, CEPS_METHODS, CEPS_URL, CepsMethod, soap
from ceps_api.parsing import parse_rows

OUTPUT = Path(__file__).resolve().parent / "ceps_methods_generated.py"
XSD = "{http://www.w3.org/2001/XMLSchema}"
WSDL = "{http://schemas.xmlsoap.org/wsdl/}"

# Fine steps over one ordinary day; coarse ones over two whole years, since
# a step only comes back if the period holds its start.
FINE = {"MI": timedelta(minutes=1), "QH": timedelta(minutes=15), "HR": timedelta(hours=1)}
DAY = ("2025-06-11T00:00:00", "2025-06-11T23:59:00")
YEARS = ("2024-01-01T00:00:00", "2025-12-31T00:00:00")
# The day and the years for the methods with no data in the usual ones:
# ExportImportVykonu ended in 2023 and EmergencyExchange only has rows when
# something happened.
PERIODS = {
    "ExportImportVykonu": (("2023-06-14T00:00:00", "2023-06-14T23:59:00"),
                           ("2022-01-01T00:00:00", "2023-12-31T00:00:00")),
    "EmergencyExchange": (("2025-02-09T00:00:00", "2025-02-09T23:59:00"), YEARS),
}


def wsdl() -> tuple:
    """
    What the WSDL lists: {method: (required, optional)} and
    {method: the name of its report}.
    """
    with urllib.request.urlopen(CEPS_URL + "?WSDL", timeout=30) as r:
        root = ET.fromstring(r.read())
    params = {}
    # Top level schema elements are the requests and their ...Response.
    for schema in root.iter(XSD + "schema"):
        for method in schema.findall(XSD + "element"):
            name = method.get("name")
            if name.endswith("Response"):
                continue
            required, optional = [], []
            for p in method.iter(XSD + "element"):
                if p is method:
                    continue
                # minOccurs="0" marks an optional parameter.
                (optional if p.get("minOccurs") == "0" else required).append(p.get("name"))
            params[name] = (tuple(required), tuple(optional))
    # The operations of the port type carry the name of their report.
    names = {}
    for operation in root.iter(WSDL + "operation"):
        text = operation.findtext(WSDL + "documentation")
        if text:
            names[operation.get("name")] = text.strip()
    return params, names


def rows(method: str, params: dict) -> list:
    """The rows of one call. A server error is printed and gives no rows."""
    try:
        return parse_rows(soap.call(method, params, 120))
    except soap.CepsError as e:
        # The message starts with the method already.
        print(f"  {params['agregation']}: {e}", file=sys.stderr)
        return []


def applied(code: str, times: list) -> bool:
    """
    Whether rows at these times are in the step of the aggregation. Having
    rows is not enough, because the service returns them in another step
    for an aggregation it ignores. The closest two rows of a fine step have
    to be one step apart; a coarse step has to start at midnight, MO on the
    first of the month and YR on 1 January.
    """
    if code in FINE:
        gaps = [b - a for a, b in pairwise(times) if b > a]
        return bool(gaps) and min(gaps) == FINE[code]
    return bool(times) and all(
        (t.hour, t.minute, t.second) == (0, 0, 0)
        and (t.day == 1 or code[:2] not in ("MO", "YR"))
        and (t.month == 1 or code[:2] != "YR")
        for t in times)


def probe(name: str, info: CepsMethod):
    """The aggregations the method returns rows in, None if in none."""
    # The first version of the method and, for a filter it does not work
    # without, the value that leaves nothing out.
    extra = {}
    if "version" in info.optional_params:
        extra["version"] = (info.versions or ("RT",))[0]
    for p in info.needed_params:
        if p in info.param_values:
            values = info.param_values[p]
            extra[p] = next((v for v in values if v.lower() == "all"), values[0])
    day, years = PERIODS.get(name, (DAY, YEARS))
    codes = []
    for code in CEPS_AGGREGATIONS:
        start, end = day if code in FINE else years
        params = dict(dateFrom=start, dateTo=end, agregation=code, function="AVG", **extra)
        times = sorted(r["date"] for r in rows(name, params) if "date" in r)
        if applied(code, times):
            codes.append(code)
    print(f"  {name}: {codes or 'nothing'}", file=sys.stderr)
    return tuple(codes) or None


def literal(value) -> str:
    """Python source for a field value, with double quotes."""
    if isinstance(value, Enum):
        return f"{type(value).__name__}.{value.name}"
    if isinstance(value, tuple):
        inner = ", ".join(json.dumps(v) for v in value)
        return f"({inner},)" if len(value) == 1 else f"({inner})"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{json.dumps(k)}: {literal(v)}" for k, v in value.items()) + "}"
    return json.dumps(value, ensure_ascii=False)


def render(methods: dict) -> str:
    """The CEPS_METHODS block; fields at their default are left out."""
    default = CepsMethod("")
    lines = ["CEPS_METHODS = {"]
    for name, info in methods.items():
        lines.append(f'    "{name}": CepsMethod(')
        lines.append(f"        {literal(info.description)},")
        # Every field after the description, so a new one is not left out.
        for field in dataclasses.fields(CepsMethod)[1:]:
            value = getattr(info, field.name)
            if value != getattr(default, field.name):
                lines.append(f"        {field.name}={literal(value)},")
        lines.append("    ),")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main():
    again = "--probe" in sys.argv[1:]
    params, names = wsdl()
    for name in CEPS_METHODS:
        if name not in params:
            print(f"dropped, no longer in the WSDL: {name}", file=sys.stderr)
    # Alphabetical, like CEPS_METHODS and the table in README.md.
    order = sorted(params)
    methods = {}
    for name in order:
        old = CEPS_METHODS.get(name)
        if old is None:
            print(f"new in the WSDL: {name}", file=sys.stderr)
            old = CepsMethod(names.get(name, "TODO: describe"))
        required, optional = params[name]
        # replace keeps the fields written by hand, whichever they are.
        new = dataclasses.replace(old, required_params=required, optional_params=optional)
        if again and "agregation" in optional:
            new = dataclasses.replace(new, aggregations=probe(name, new))
        methods[name] = new

    changed = [n for n in methods if n in CEPS_METHODS and methods[n] != CEPS_METHODS[n]]
    print(f"changed: {', '.join(changed) or 'nothing'}", file=sys.stderr)

    header = ("# Generated by scripts/ceps_catalog.py. Not used by any code: review it and\n"
              "# copy the dict over CEPS_METHODS in src/ceps_api/catalog.py by hand.\n")
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + render(methods))
    print(f"wrote {len(methods)} methods to {OUTPUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
