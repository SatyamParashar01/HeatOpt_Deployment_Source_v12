"""Energy prices, emission factors and backup heaters for Boston, Atlanta and Montreal.

Tables (in data/tables/):
  energy_prices.csv     USD per kWh of FUEL (before efficiency), by city, scenario and year.
                        scenario "historical" = annual values 2010-2025 (EIA, BLS, StatCan,
                        Hydro-Quebec); scenario "nov2026" = latest prices, one value per fuel.
  emission_factors.csv  g CO2e per kWh of FUEL or of delivered electricity (EPA 2025, eGRID2023,
                        Hydro-Quebec 2025). Electricity has an "average" and a "marginal" rate.
  backup_heaters.csv    backup type -> fuel, efficiency, emission factor key, and tariff rules
                        (Rate DT: forced switch temperature and heat pump electricity price).
  heat_pump_capex.csv   installed heat pump cost per ton, by city.

Everything is in USD and kWh, so the three cities compare directly.
Montreal prices were converted from CAD at each year's average exchange rate.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

TABLES = Path(__file__).parent / "tables"
City = Literal["Boston", "Atlanta", "Montreal"]
Scenario = Literal["historical", "nov2026"]
Grid = Literal["average", "marginal"]
CITIES: tuple[str, ...] = ("Boston", "Atlanta", "Montreal")


@dataclass(frozen=True)
class BackupHeater:
    name: str
    fuel: str
    efficiency: float  # kWh of heat per kWh of fuel
    emission_key: str  # row of emission_factors.csv
    forced_switch_c: float | None = None  # tariff forces the backup at and below this T
    hp_price_override: float | None = None  # USD/kWh for heat pump electricity (Rate DT)
    cities: tuple[str, ...] = CITIES


@lru_cache
def prices_table() -> pd.DataFrame:
    return pd.read_csv(TABLES / "energy_prices.csv")


@lru_cache
def emissions_table() -> pd.DataFrame:
    return pd.read_csv(TABLES / "emission_factors.csv")


@lru_cache
def backups_table() -> pd.DataFrame:
    return pd.read_csv(TABLES / "backup_heaters.csv")


@lru_cache
def capex_per_ton(city: City) -> float:
    t = pd.read_csv(TABLES / "heat_pump_capex.csv").set_index("city")
    return float(t.loc[city, "usd_per_ton"])


def _opt(x) -> float | None:
    return None if pd.isna(x) else float(x)


@lru_cache
def backup(name: str) -> BackupHeater:
    r = backups_table().set_index("backup").loc[name]
    return BackupHeater(name=name, fuel=r["fuel"], efficiency=float(r["efficiency"]),
                        emission_key=r["emission_key"], forced_switch_c=_opt(r["forced_switch_c"]),
                        hp_price_override=_opt(r["hp_price_override_usd_per_kwh"]),
                        cities=tuple(str(r["cities"]).split(";")))


def backup_names(city: City | None = None) -> list[str]:
    names = backups_table()["backup"].tolist()
    if city is None:
        return names
    return [n for n in names if city in backup(n).cities and has_price(city, backup(n).fuel)]


def has_price(city: City, fuel: str) -> bool:
    t = prices_table()
    return bool(((t.city == city) & (t.fuel == fuel)).any())


@lru_cache
def _price_lookup(city: str, fuel: str, scenario: str) -> tuple[tuple[int, ...], tuple[float, ...]]:
    t = prices_table()
    t = t[(t.city == city) & (t.fuel == fuel)]
    if t.empty:
        raise KeyError(f"no {fuel} price for {city}")
    hist = t[t.scenario == "historical"].sort_values("year")
    cur = t[t.scenario == "nov2026"]
    if scenario == "nov2026" or hist.empty:
        # current price; fuels with no current price (wood) take the latest historical year
        v = cur.usd_per_kwh_fuel.iloc[0] if len(cur) else hist.usd_per_kwh_fuel.iloc[-1]
        return (0,), (float(v),)
    return tuple(int(y) for y in hist.year), tuple(float(v) for v in hist.usd_per_kwh_fuel)


def price_by_year(city: City, fuel: str, years: np.ndarray, scenario: Scenario = "historical") -> np.ndarray:
    """USD per kWh of fuel for each entry of `years`.

    historical : each weather year gets that year's price (years outside 2010-2025 take the
                 nearest year). Fuels with no history (pellets) use their current price.
    nov2026    : one current price for every year.
    """
    y, p = (np.asarray(a) for a in _price_lookup(city, fuel, scenario))
    years = np.asarray(years)
    if len(y) == 1:
        return np.full(years.shape, float(p[0]))
    idx = np.clip(np.searchsorted(y, years), 0, len(y) - 1)
    lo = np.clip(idx - 1, 0, len(y) - 1)
    pick = np.where(np.abs(y[idx] - years) <= np.abs(y[lo] - years), idx, lo)
    return p[pick]


def emission_factor(city: City, key: str, grid: Grid = "average") -> float:
    """g CO2e per kWh of fuel (or per kWh of electricity delivered to the house).

    key: "electricity" or a fuel row of emission_factors.csv (natural_gas, heating_oil,
    propane, wood, wood_biogenic_excluded).
    """
    t = emissions_table()
    row = t[(t.city == city) & (t.fuel == "electricity")] if key == "electricity" else t[(t.city == "all") & (t.fuel == key)]
    if row.empty:
        raise KeyError(f"no emission factor for {key} in {city}")
    return float(row[f"g_co2e_per_kwh_{grid}"].iloc[0])
