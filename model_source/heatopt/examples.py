"""Maison et météo d'exemple, pour tester sans données réelles.
(Valeurs illustratives, à remplacer par l'archétype ResStock.)"""
from __future__ import annotations

import numpy as np
import pandas as pd

from heatopt.config import Construction, House, Layer, Location, Surface, Usage, Ventilation, WindowSpec

BRICK = Layer(name="brique", thickness_m=0.20, conductivity=0.8, density=1800, specific_heat=900)
CELLULOSE = Layer(name="cellulose", thickness_m=0.09, conductivity=0.04, density=50, specific_heat=1600)
PLASTER = Layer(name="plâtre", thickness_m=0.013, conductivity=0.25, density=900, specific_heat=1000)
WOOD_ROOF = Layer(name="isolant toit", thickness_m=0.15, conductivity=0.045, density=40, specific_heat=1400)
CONCRETE = Layer(name="dalle béton", thickness_m=0.10, conductivity=1.4, density=2200, specific_heat=880)

WALL = Construction(name="mur", layers=(BRICK, CELLULOSE, PLASTER))
ROOF = Construction(name="toit", layers=(WOOD_ROOF, PLASTER))
FLOOR = Construction(name="plancher", layers=(CONCRETE,))
DOUBLE = WindowSpec(name="double vitrage", u_w=2.8, g=0.6)


def demo_house(n_people: int = 4) -> House:
    walls = [
        Surface(name=f"mur_{n}", kind="wall", area_m2=40.0, construction=WALL, azimuth_deg=az, tilt_deg=90,
                window=DOUBLE, window_fraction=0.15)
        for n, az in (("N", 0), ("E", 90), ("S", 180), ("O", 270))
    ]
    roof = Surface(name="toit", kind="roof", area_m2=100.0, construction=ROOF, tilt_deg=0, b_tr=0.9)
    floor = Surface(name="plancher", kind="floor", area_m2=100.0, construction=FLOOR, tilt_deg=0, b_tr=0.5)
    return House(
        name="demo", location=Location(), floor_area_m2=200.0, n_levels=2, storey_height_m=2.5,
        surfaces=(*walls, roof, floor), ventilation=Ventilation(ach50=6.0),
        usage=Usage(n_people=n_people),
    )


def synthetic_weather(days: int = 30, t_c: float = -5.0, ghi: float = 0.0) -> pd.DataFrame:
    """Météo horaire constante (utile pour les tests analytiques)."""
    idx = pd.date_range("2026-01-01", periods=24 * days, freq="h", tz="UTC")
    z = np.zeros(len(idx))
    return pd.DataFrame(
        {"temp_C": t_c, "rel_humidity_pct": 70.0, "wind_10m_m_s": 3.0,
         "GHI_W_m2": ghi, "DNI_W_m2": z, "DHI_W_m2": ghi,
         "local_hour": ((idx.hour - 5) % 24)}, index=idx)
