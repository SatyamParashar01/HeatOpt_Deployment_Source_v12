"""Fournisseurs de météo. Contrat : un DataFrame horaire indexé par temps UTC.

Colonnes obligatoires : temp_C, rel_humidity_pct, wind_10m_m_s, GHI_W_m2, DNI_W_m2,
DHI_W_m2, local_hour (0..23, heure standard locale).
Pour ajouter une autre source (NSRDB, ERA5...) : écrire une classe qui respecte
le protocole `WeatherProvider`, sans toucher au reste du code.
"""
from __future__ import annotations

from typing import Protocol

import pandas as pd

REQUIRED = ["temp_C", "rel_humidity_pct", "wind_10m_m_s", "GHI_W_m2", "DNI_W_m2", "DHI_W_m2", "local_hour"]


class WeatherProvider(Protocol):
    def load(self) -> pd.DataFrame: ...


class CsvWeather:
    """CSV avec colonnes : time_utc, time_local_standard, temp_C, rel_humidity_pct,
    wind_10m_m_s, GHI_W_m2, DNI_W_m2, DHI_W_m2."""

    def __init__(self, path: str):
        self.path = path

    def load(self) -> pd.DataFrame:
        df = pd.read_csv(self.path, parse_dates=["time_utc", "time_local_standard"])
        df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
        df["local_hour"] = pd.DatetimeIndex(df["time_local_standard"]).hour
        df = df.set_index("time_utc").sort_index()
        validate(df)
        return df


def validate(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"colonnes météo manquantes : {missing}")
    if not df.index.is_monotonic_increasing or df.index.tz is None:
        raise ValueError("l'index doit être un DatetimeIndex UTC croissant")
    if (df.index.to_series().diff().dropna() != pd.Timedelta(hours=1)).any():
        raise ValueError("pas de temps non horaire ou trous dans la série")
