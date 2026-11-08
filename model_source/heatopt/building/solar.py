"""Apports solaires à travers les vitrages (pvlib).

Q_sol,k = A_w,k * (1 - f_cadre) * g * F_w * F_ombrage * G_poa,k      [W]
  G_poa,k : irradiance sur le plan de la façade k [W/m2] (transposition de
            GHI/DNI/DHI avec position du soleil et albédo).
  F_w = 0.9 : correction d'incidence non normale (ISO 13790).
Les apports par absorption des parois opaques sont négligés (extension possible).
"""
from __future__ import annotations

import pandas as pd
from pvlib import irradiance, solarposition

from heatopt.config import House

F_W = 0.9


def window_gains_w(house: House, weather: pd.DataFrame) -> pd.DataFrame:
    """Apports solaires par surface vitrée [W]. Colonnes = nom des surfaces, + 'total'."""
    loc = house.location
    sun = solarposition.get_solarposition(weather.index, loc.latitude, loc.longitude, altitude=loc.altitude_m)
    out = {}
    for s in house.surfaces:
        if s.window is None or s.window_area_m2 == 0:
            continue
        poa = irradiance.get_total_irradiance(
            surface_tilt=s.tilt_deg,
            surface_azimuth=s.azimuth_deg,
            solar_zenith=sun["apparent_zenith"],
            solar_azimuth=sun["azimuth"],
            dni=weather["DNI_W_m2"],
            ghi=weather["GHI_W_m2"],
            dhi=weather["DHI_W_m2"],
            albedo=loc.albedo,
        )["poa_global"].fillna(0.0)
        w = s.window
        out[s.name] = s.window_area_m2 * (1 - w.frame_fraction) * w.g * F_W * w.shading_factor * poa
    df = pd.DataFrame(out, index=weather.index)
    df["total"] = df.sum(axis=1)
    return df
