"""Colle les couches : (maison, météo, système) -> résultats horaires.

C'est la seule fonction qui connaît à la fois les données, la météo, le solaire
et le modèle. Pour changer de modèle thermique, passer un autre `model_factory`.
"""
from __future__ import annotations

import pandas as pd

from heatopt.building.base import BoundaryConditions, ThermalModelFactory
from heatopt.building.gains import internal_gains_w
from heatopt.building.rc_5r1c import FiveR1C
from heatopt.building.solar import window_gains_w
from heatopt.config import House
from heatopt.systems.base import HeatingSystem


def build_boundary(house: House, weather: pd.DataFrame) -> BoundaryConditions:
    lh = weather["local_hour"].to_numpy()
    return BoundaryConditions(
        index=weather.index,
        t_out_c=weather["temp_C"].to_numpy(float),
        solar_gain_w=window_gains_w(house, weather)["total"].to_numpy(float) if _has_windows(house) else 0 * lh.astype(float),
        internal_w=internal_gains_w(house.usage, lh),
        setpoint_c=house.usage.setpoint_series(lh),
    )


def _has_windows(house: House) -> bool:
    return any(s.window and s.window_area_m2 > 0 for s in house.surfaces)


def simulate(
    house: House,
    weather: pd.DataFrame,
    system: HeatingSystem,
    model_factory: ThermalModelFactory = FiveR1C,
) -> pd.DataFrame:
    """Résultats horaires : t_air_c, t_op_c, phi_hc_w, phi_demand_w, + t_out_c, setpoint_c."""
    bc = build_boundary(house, weather)
    res = model_factory(house).run(bc, system)
    res["t_out_c"], res["setpoint_c"] = bc.t_out_c, bc.setpoint_c
    return res
