"""Run the 5R1C model for a city archetype (house tables + ground loss + calibrated mass)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from heatopt.building.archetypes import Archetype
from heatopt.data.weather import CsvWeather, validate
from heatopt.simulate import build_boundary
from heatopt.systems.base import HeatingSystem, IdealHeater

TABLES = Path(__file__).parent / "data" / "tables"
ERA5 = {
    "Boston": TABLES / "Boston_hourly_2010-2025_ERA5.csv",
    "Atlanta": TABLES / "Atlanta_hourly_2010-2025_ERA5.csv",
    "Montreal": TABLES / "Montreal_hourly_2010-2025_ERA5 - Montreal_hourly_2010-2025_ERA5.csv",
}


@lru_cache
def era5(city: str) -> pd.DataFrame:
    return CsvWeather(str(ERA5[city])).load()


@lru_cache
def tmy(city: str) -> pd.DataFrame:
    """Typical year (TMY3 for Boston/Atlanta, CWEC2020 for Montreal) in the weather contract format."""
    t = pd.read_csv(TABLES / "weather_tmy_hourly_all_cities.csv")
    t = t[t.city == city].copy()
    local = pd.to_datetime(t.time_local_std)
    t.index = pd.DatetimeIndex(local + pd.Timedelta(hours=5)).tz_localize("UTC")  # all three are UTC-5 standard
    t = t.rename(columns={"temp_c": "temp_C", "rh_pct": "rel_humidity_pct", "wind_m_s": "wind_10m_m_s",
                          "ghi_w_m2": "GHI_W_m2", "dni_w_m2": "DNI_W_m2", "dhi_w_m2": "DHI_W_m2"})
    t["local_hour"] = local.dt.hour.to_numpy()
    t = t.sort_index()
    validate(t)
    return t


def simulate_archetype(arch: Archetype, weather: pd.DataFrame, system: HeatingSystem | None = None) -> pd.DataFrame:
    """Hourly 5R1C results. Default system = unlimited heater (gives the heat demand)."""
    system = system or IdealHeater(1e9)
    bc = arch.adjust_boundary(build_boundary(arch.house, weather))
    res = arch.model_factory()(arch.house).run(bc, system)
    res["t_out_c"], res["setpoint_c"] = bc.t_out_c, bc.setpoint_c
    return res
