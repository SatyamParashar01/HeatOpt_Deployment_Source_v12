"""Interface commune des modèles thermiques.

Un modèle (5R1C, plus tard 3R2C, multi-zone...) reçoit les mêmes entrées et rend
le même tableau : le reste du projet ne dépend que de ce fichier.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd

from heatopt.config import House
from heatopt.systems.base import HeatingSystem


@dataclass(frozen=True)
class BoundaryConditions:
    """Sollicitations horaires (tous les tableaux ont la même longueur N).

    t_out_c       : température extérieure [°C]
    solar_gain_w  : apports solaires à travers les vitrages [W]
    internal_w    : apports internes (personnes + appareils) [W]
    setpoint_c    : consigne de chauffage [°C]
    """

    index: pd.DatetimeIndex
    t_out_c: np.ndarray
    solar_gain_w: np.ndarray
    internal_w: np.ndarray
    setpoint_c: np.ndarray


class ThermalModel(Protocol):
    def run(self, bc: BoundaryConditions, system: HeatingSystem) -> pd.DataFrame:
        """Retourne un DataFrame (index = bc.index) avec au minimum :
        t_air_c, t_op_c, phi_hc_w (puissance fournie), phi_demand_w (puissance voulue)."""
        ...


class ThermalModelFactory(Protocol):
    def __call__(self, house: House) -> ThermalModel: ...
