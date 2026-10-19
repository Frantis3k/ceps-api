# ČEPS-api

[![PyPI](https://img.shields.io/pypi/v/ceps-api)](https://pypi.org/project/ceps-api/)
[![Python](https://img.shields.io/pypi/pyversions/ceps-api)](https://pypi.org/project/ceps-api/)
[![tests](https://github.com/Frantis3k/ceps-api/actions/workflows/tests.yml/badge.svg)](https://github.com/Frantis3k/ceps-api/actions/workflows/tests.yml)

<p align="center">
  <img src="https://raw.githubusercontent.com/Frantis3k/ceps-api/main/docs/ceps-api-demo.gif" alt="ceps-api demo" width="700">
</p>

[Jump to English version](#english)


Neoficiální Python klient webové služby [ČEPS](https://www.ceps.cz/cs/webove-sluzby), provozovatele české
přenosové soustavy. Stahuje systémovou odchylku, aktivovanou regulační energii a její ceny, odhad ceny
odchylky, výrobu, zatížení, přeshraniční toky a další data. Každá metoda služby má na třídě `Ceps`
stejnojmennou metodu, která vrací pandas DataFrame.

Projekt je neoficiální, podrobnosti viz [Disclaimer](#disclaimer).

### Instalace

```
pip install ceps-api
```

Vyžaduje Python 3.10 nebo novější. Služba nepotřebuje žádný klíč ani registraci.

### Rychlý start

```python
from ceps_api import Ceps

ceps = Ceps()
df = ceps.AktualniSystemovaOdchylkaCR("2026-10-16", "2026-10-16T23:59", aggregation="QH")
print(df.head())
```

```
                           Aktuální odchylka [MW]
timestamp
2026-10-16 00:00:00+02:00               -56.98927
2026-10-16 00:15:00+02:00               -70.02203
2026-10-16 00:30:00+02:00               -63.87983
2026-10-16 00:45:00+02:00               -75.59872
2026-10-16 01:00:00+02:00               -23.32196
```

Datum jde zadat i jako `datetime`, například `datetime(2026, 10, 16, 23, 59)`.

### Dostupné metody a jejich parametry

Seznam metod je v [tabulce na konci](#metody--methods). `Ceps.parameters()` vypíše všechny dostupné metody
a jejich argumenty. S názvem metody ukáže i povolené hodnoty: agregace (např. `QH`, `HR`), funkce
(`AVG`, `MIN`, `MAX`, `SUM`), verze dat a speciální parametry jako `param1`.

```python
print(Ceps.parameters())  # všechny metody a jejich argumenty
print(Ceps.parameters("AktualniSystemovaOdchylkaCR"))  # parametry a povolené hodnoty jedné metody
```

### Čas a časová pásma

- `start` a `end` jsou český místní čas: `date`, `datetime` nebo ISO řetězec (`"2026-10-16"`,
  `"2026-10-16T10:00"`). Čas s časovou zónou se nejdřív převede na český čas.
- Oba konce se počítají: celý den je `start="2026-10-16"`, `end="2026-10-16T23:59"`.
- Časové řady mají index `timestamp`, tedy začátek kroku v pásmu `Europe/Prague`. Index zůstává
  jednoznačný i přes změnu času: den, kdy se čas posouvá zpět, má 100 čtvrthodin a hodina 02:00–03:00
  je v něm dvakrát, jednou s posunem `+02:00` a jednou s `+01:00`.
- `aggregation` je délka kroku (`MI` minuta, `QH` čtvrthodina, `HR` hodina, …) a `function` způsob,
  jak se hodnoty v kroku kombinují (`AVG` výchozí, `MIN`, `MAX`, `SUM`).

### Aktuálnost dat

Ne všechna data jsou v reálném čase. Každá metoda je zveřejňuje s jiným zpožděním, takže pokud pro
poslední minuty nebo čtvrthodiny nic nepřijde, nemusí jít o chybu, data jen ještě nejsou k dispozici.

Nejčerstvější data má minutová řada `AktualniSystemovaOdchylkaCR` (bez `aggregation`), zpožděná
obvykle jen o minutu nebo dvě. Například odchylka za posledních 15 minut:

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

now = datetime.now(ZoneInfo("Europe/Prague"))
df = ceps.AktualniSystemovaOdchylkaCR(now - timedelta(minutes=15), now)
print(df.tail())
```

Zpoždění se může měnit, ČEPS ho nijak nezaručuje.

### Chyby

Neznámou metodu, agregaci nebo hodnotu filtru odmítne `ValueError` ještě před odesláním požadavku.
Služba totiž na neznámou hodnotu často neodpoví chybou, ale vrátí prázdná nebo nefiltrovaná data.
Chybu služby nebo sítě hlásí `CepsError`.

### Jak to funguje

Třída `Ceps` v `client.py` pošle každé volání přes tyto moduly:

1. `convert.py` převede data na český místní čas a `validation.py` zkontroluje parametry podle `catalog.py`,
2. `soap.py` pošle SOAP požadavek a vrátí syrové XML,
3. `parsing.py` z XML udělá pythonní data, která `convert.py` převede na DataFrame.

### Alternativy

Pokud vám tato knihovna nevyhovuje, data ČEPS jsou dostupná i jinak:

- [Keboola konektor ČEPS](https://help.keboola.com/components/extractors/other/ceps/), extraktor
  pro platformu Keboola,
- [ceps-ote](https://github.com/whipeeer-creator/ceps-ote) od progrunners, další Python wrapper,
- [data na ceps.cz](https://www.ceps.cz/cs/data), původní zdroj přímo od ČEPS.

### Licence

Kód je pod licencí [MIT](https://github.com/Frantis3k/ceps-api/blob/main/LICENSE). Na co se licence vztahuje, viz [Disclaimer](#disclaimer).

### Disclaimer

Projekt je neoficiální. Nemá žádnou vazbu na společnost ČEPS, a.s., která ho nevyvíjí,
nepodporuje ani neschvaluje. Název ČEPS je použit pouze k označení webové služby,
se kterou knihovna komunikuje.

Data poskytuje a vlastní ČEPS, a.s. Tento balíček je jen volá přes veřejnou webovou službu a nic
z nich neukládá. Licence MIT se vztahuje pouze na kód této knihovny, nikoli na data. Podmínky užití
dat stanovuje ČEPS, a.s., a za dodržení podmínek užití webové služby i publikovaných dat odpovídá
uživatel.

Knihovna je poskytována „tak, jak je“, bez jakékoli záruky. Autor neodpovídá za správnost,
úplnost ani aktuálnost stažených dat a nenese odpovědnost za škody vzniklé jejich použitím.
Data mohou být chybná, zpožděná nebo neúplná, například kvůli změnám ve webové službě
nebo chybám v této knihovně. Pokud data používáte k obchodování, vyúčtování nebo jiným
závazným účelům, ověřte je u primárního zdroje.

Buďte ke službě ohleduplní: nestahujte velké objemy paralelně a delší období si raději ukládejte.

---

## English

Unofficial Python client for the web service of [ČEPS](https://www.ceps.cz/en/web-services), the Czech
transmission system operator. It downloads system imbalance, activated balancing energy and its prices,
the estimated imbalance price, generation, load, cross-border flows and more. Every method of the
service has a method of the same name on `Ceps`, which returns a pandas DataFrame.

This project is unofficial, see the [Disclaimer](#disclaimer-1) for details.

### Installation

```
pip install ceps-api
```

Requires Python 3.10 or newer. The service needs no key and no registration.

### Quick start

```python
from ceps_api import Ceps

ceps = Ceps()
df = ceps.AktualniSystemovaOdchylkaCR("2026-10-16", "2026-10-16T23:59", aggregation="QH")
print(df.head())
```

```
                           Aktuální odchylka [MW]
timestamp
2026-10-16 00:00:00+02:00               -56.98927
2026-10-16 00:15:00+02:00               -70.02203
2026-10-16 00:30:00+02:00               -63.87983
2026-10-16 00:45:00+02:00               -75.59872
2026-10-16 01:00:00+02:00               -23.32196
```

A date can also be given as a `datetime`, for example `datetime(2026, 10, 16, 23, 59)`.

### Available methods and their parameters

The methods are listed in the [table at the end](#metody--methods). `Ceps.parameters()` shows every
available method and its arguments. Given a method name, it also shows the allowed values: aggregations
(e.g. `QH`, `HR`), functions (`AVG`, `MIN`, `MAX`, `SUM`), data versions and special parameters such
as `param1`.

```python
print(Ceps.parameters())  # all methods and their arguments
print(Ceps.parameters("AktualniSystemovaOdchylkaCR"))  # parameters and allowed values of one method
```

### Time and time zones

- `start` and `end` are Czech local time: a `date`, a `datetime` or an ISO string (`"2026-10-16"`,
  `"2026-10-16T10:00"`). A time with a time zone is converted to Czech time first.
- Both ends are included: a whole day is `start="2026-10-16"`, `end="2026-10-16T23:59"`.
- Time series are indexed by `timestamp`, the start of the step in `Europe/Prague`. The index stays
  unique across the clock change: the day the clocks go back has 100 quarter hours, with 02:00–03:00
  twice, once at `+02:00` and once at `+01:00`.
- `aggregation` is the time step (`MI` minute, `QH` quarter hour, `HR` hour, …) and `function` how
  the values within it are combined (`AVG` by default, `MIN`, `MAX`, `SUM`).

### How recent the data is

Not all data is real time. Each method publishes its data with a different delay, so if nothing
comes back for the last few minutes or quarter hours, it is not necessarily an error: the data is
just not available yet.

The freshest data comes from the per-minute series of `AktualniSystemovaOdchylkaCR` (without
`aggregation`), usually only a minute or two behind. For example, the imbalance over the last
15 minutes:

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

now = datetime.now(ZoneInfo("Europe/Prague"))
df = ceps.AktualniSystemovaOdchylkaCR(now - timedelta(minutes=15), now)
print(df.tail())
```

The delays can change; ČEPS does not guarantee them.

### Errors

An unknown method, aggregation or filter value raises `ValueError` before any request is sent, since
the service often answers an unknown value with empty or unfiltered data instead of an error. A failure
of the service or the network raises `CepsError`.

### How it works

The `Ceps` class in `client.py` passes every call through these modules:

1. `convert.py` converts the dates to Czech local time and `validation.py` checks the parameters against `catalog.py`,
2. `soap.py` sends the SOAP request and returns the raw XML,
3. `parsing.py` turns the XML into plain Python, which `convert.py` turns into a DataFrame.

### Alternatives

If this library does not suit you, the ČEPS data is also available elsewhere:

- [Keboola ČEPS connector](https://help.keboola.com/components/extractors/other/ceps/), an extractor
  for the Keboola platform,
- [ceps-ote](https://github.com/whipeeer-creator/ceps-ote) by progrunners, another Python wrapper,
- [data on ceps.cz](https://www.ceps.cz/en/all-data), the original source straight from ČEPS.

### Licence

The code is under the [MIT licence](https://github.com/Frantis3k/ceps-api/blob/main/LICENSE). For what it covers, see the [Disclaimer](#disclaimer-1).

### Disclaimer

This project is unofficial. It is not affiliated with ČEPS, a.s., which does not develop,
support or endorse it. The name ČEPS is used only to identify the web service the library
communicates with.

The data is provided and owned by ČEPS, a.s. This package only calls the public web service and stores
nothing. The MIT licence covers only the code of this library, not the data. The terms of use of the
data are set by ČEPS, a.s., and you are responsible for complying with the terms of use of the web
service and the data it publishes.

The library is provided "as is", without warranty of any kind. The author is not responsible
for the accuracy, completeness or timeliness of the downloaded data and accepts no liability
for any damage arising from its use. The data may be wrong, delayed or incomplete, for example
because of changes to the web service or bugs in this library. If you use the data for trading,
settlement or other binding purposes, verify it against the primary source.

Please be gentle with the service: do not download large volumes in parallel, and store longer
periods rather than downloading them again.

---

## Metody / Methods

Popisy jsou kvůli přehlednosti zkrácené. Úplný popis metod je v dokumentaci ČEPS na
[ceps.cz/cs/webove-sluzby](https://www.ceps.cz/cs/webove-sluzby), v souboru
*ČEPSVIP_Popis rozhraní strukturovaná data 3.2.docx*.

The descriptions are shortened for an overview. The full description of the methods is in the ČEPS
documentation at [ceps.cz/cs/webove-sluzby](https://www.ceps.cz/cs/webove-sluzby), in the file
*ČEPSVIP_Popis rozhraní strukturovaná data 3.2.docx*.

| Method | Data | Arguments |
|---|---|---|
| `AktivaceSVRvCR` | Activated balancing energy (aFRR+/-, mFRR+/-, mFRR5), [MW] | start, end, aggregation, function, param1 |
| `AktualniCenaRE` | Price of activated regulating energy (aFRR, mFRR+/-, mFRR5), [EUR/MWh] | start, end, param1 |
| `AktualniSystemovaOdchylkaCR` | Current system imbalance of the Czech control area, [MW] | start, end, aggregation, function |
| `CrossborderPowerFlows` | Actual and planned flows per neighbouring operator, [MW] | start, end, aggregation, function, version |
| `DataAgregation` | Lists the aggregation codes. Not a time series |  |
| `DataVersion` | Lists the version codes. Not a time series |  |
| `EmergencyExchange` | Emergency assistance, redispatch and regulating energy from abroad, a row per border and direction. Only has rows when something happened | start, end, aggregation, function, version, param1, param2 |
| `EmergencyExchangeACER` | Emergency exchange as an ACER message. Not a time series | start, end, param1, param2 |
| `Emise` | CO2 intensity of generation, [g CO2/kWh]. Always per quarter hour, the service ignores the aggregation | start, end, aggregation, function, version, param1 |
| `ExportImportSVR` | Exchange with the European balancing platforms (imbalance netting, MARI, PICASSO) | start, end, aggregation, function, param1 |
| `ExportImportVykonu` | Export (+) and import (-) of power within the European platforms and foreign assistance, [MW]. Data from 2022-05-20 to 2023-08-25, then ExportImportSVR | start, end, aggregation, function |
| `Frekvence` | System frequency, [Hz] | start, end |
| `Generation` | Gross generation by plant type, [MW] | start, end, aggregation, function, version, param1 |
| `GenerationPlan` | Planned gross generation, [MW] | start, end, aggregation, function, version |
| `GenerationRES` | Estimated wind and solar generation, [MW] | start, end, aggregation, function, version, param1 |
| `Load` | Load with and without pumping, [MW]; load is gross generation + import - export - pumping. The forecast versions have it without pumping only | start, end, aggregation, function, version |
| `MaximalniCenySVRnaDT` | Maximum prices of balancing services on the day-ahead market, a row per day and currency. Data from 2022-08-26 to 2024-07-04 | start, end |
| `NepredvidatelneOdmitnuteNabidky` | Unforeseeably rejected bids of one product (aFRR+ if none is given): per hour and bid the price offered [Kč] and the power not accepted [MW] | start, end, param1 |
| `OdhadovanaCenaOdchylky` | Estimated imbalance price, [Kč/MWh]. Not a plain time series | start, end |
| `OfferPrices` | Offer prices of regulating energy: per hour and bid the price [Kč] and the power [MW]. Data from November 2017 to 2022-03-31 | start, end, version, param1 |
| `PowerBalance` | Yearly forecast of the power balance: domestic sources, outages, reserve of ancillary services and load, [MW] | start, end, aggregation, function, version, param1 |

## Vývoj / Development

```
git clone https://github.com/Frantis3k/ceps-api.git
cd ceps-api
uv sync
uv run ruff check .
uv run mypy
uv run pytest -m "not live"   # offline, against responses saved in tests/data
uv run pytest -m live         # calls the real service
```

When ČEPS changes the service, `uv run scripts/ceps_catalog.py` writes a fresh catalog to
`scripts/ceps_methods_generated.py` for review; it is copied over `CEPS_METHODS` in
`src/ceps_api/catalog.py` by hand.
