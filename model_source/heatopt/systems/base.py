"""Systèmes de chauffage : chacun répond à UNE question, "quelle puissance max
puis-je fournir à cette température extérieure ?". Le modèle thermique décide
ensuite de la puissance réellement demandée.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


class HeatingSystem(Protocol):
    def max_power_w(self, t_out_c: np.ndarray) -> np.ndarray:
        """Puissance thermique maximale délivrée [W] pour chaque t_out [°C]."""
        ...


@dataclass(frozen=True)
class IdealHeater:
    """Chauffage idéal à capacité constante. capacity_w=0 -> évolution libre."""

    capacity_w: float

    def max_power_w(self, t_out_c: np.ndarray) -> np.ndarray:
        return np.full_like(np.asarray(t_out_c, dtype=float), self.capacity_w)


@dataclass(frozen=True)
class TabulatedHeatPump:
    """PAC dont la capacité dépend de T_ext par interpolation (données constructeur).

    Exemple : t_points_c=(-15, -8, 8), capacity_w=(6000, 8000, 11000).
    En dessous/au-dessus des points, np.interp garde la valeur extrême (à raffiner
    avec la coupure basse température du constructeur). COP : à ajouter ici plus tard.
    """

    t_points_c: tuple[float, ...]
    capacity_w: tuple[float, ...]

    def max_power_w(self, t_out_c: np.ndarray) -> np.ndarray:
        return np.interp(t_out_c, self.t_points_c, self.capacity_w)
