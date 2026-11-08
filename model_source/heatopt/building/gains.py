"""Apports internes [W] à partir de l'occupation et des appareils."""
from __future__ import annotations

import numpy as np

from heatopt.config import Usage


def internal_gains_w(usage: Usage, local_hour: np.ndarray) -> np.ndarray:
    """Q_int(h) = n_people * w_per_person * occ(h) + appliances_mean * profil(h)   [W]."""
    h = np.asarray(local_hour, dtype=int)
    occ = np.asarray(usage.occupancy_profile)[h]
    app = np.asarray(usage.appliance_profile)[h]
    return usage.n_people * usage.w_per_person * occ + usage.appliances_w_mean * app
