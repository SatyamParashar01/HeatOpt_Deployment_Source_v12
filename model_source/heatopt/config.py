"""Paramètres du projet (modèles pydantic). Tout est en unités SI.

Ces classes ne contiennent AUCUNE physique de simulation : seulement des données
validées + quelques calculs géométriques/matériaux simples (U, kappa).
Un modèle thermique (5R1C, nRmC...) lit ces objets, il ne les modifie jamais.
"""
from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


# --------------------------------------------------------------------------- #
# Matériaux et parois
# --------------------------------------------------------------------------- #
class Layer(_Frozen):
    """Une couche de matériau.

    thickness_m [m], conductivity [W/(m.K)], density [kg/m3], specific_heat [J/(kg.K)].
    """

    name: str
    thickness_m: float = Field(gt=0)
    conductivity: float = Field(gt=0)
    density: float = Field(gt=0)
    specific_heat: float = Field(gt=0)


class Construction(_Frozen):
    """Paroi multicouche. `layers` est ordonné de l'EXTÉRIEUR vers l'INTÉRIEUR.

    r_si, r_se : résistances d'échange superficielles [m2.K/W] (ISO 6946, flux horizontal).
    """

    name: str
    layers: tuple[Layer, ...]
    r_si: float = 0.13
    r_se: float = 0.04

    def r_total(self) -> float:
        """R = R_si + sum(d/lambda) + R_se  [m2.K/W]."""
        return self.r_si + sum(l.thickness_m / l.conductivity for l in self.layers) + self.r_se

    def u_value(self) -> float:
        """U = 1/R [W/(m2.K)]."""
        return 1.0 / self.r_total()

    def kappa_internal(self, depth_m: float = 0.10) -> float:
        """Capacité thermique surfacique côté intérieur [J/(m2.K)].

        Simplification de l'ISO 13786 : on somme rho*c*d des couches en partant de
        l'intérieur, jusqu'à `depth_m` d'épaisseur cumulée (10 cm par défaut).
        """
        remaining, kappa = depth_m, 0.0
        for layer in reversed(self.layers):  # intérieur -> extérieur
            d = min(layer.thickness_m, remaining)
            kappa += layer.density * layer.specific_heat * d
            remaining -= d
            if remaining <= 0:
                break
        return kappa


class WindowSpec(_Frozen):
    """Type de vitrage. u_w inclut le cadre. g = facteur solaire du vitrage."""

    name: str
    u_w: float = Field(gt=0)  # [W/(m2.K)]
    g: float = Field(gt=0, le=1)  # [-]
    frame_fraction: float = Field(0.2, ge=0, lt=1)  # part de cadre dans la baie [-]
    shading_factor: float = Field(1.0, ge=0, le=1)  # 1 = aucun ombrage [-]


class Surface(_Frozen):
    """Une paroi de l'enveloppe, avec éventuellement une fenêtre dedans.

    area_m2 = surface BRUTE (fenêtre comprise). La surface opaque nette est déduite.
    azimuth_deg : 0 = Nord, 90 = Est, 180 = Sud, 270 = Ouest (convention pvlib).
    tilt_deg    : 90 = vertical, 0 = horizontal face vers le haut (convention pvlib).
    b_tr        : facteur de réduction de température (ISO 13789). 1 = extérieur,
                  ~0.5 pour un plancher sur sol/vide sanitaire, 0.7 pour des combles.
    """

    name: str
    kind: Literal["wall", "roof", "floor"]
    area_m2: float = Field(gt=0)
    construction: Construction
    azimuth_deg: float = 0.0
    tilt_deg: float = 90.0
    b_tr: float = Field(1.0, ge=0, le=1)
    window: WindowSpec | None = None
    window_fraction: float = Field(0.0, ge=0, lt=1)  # part de la surface brute vitrée

    @property
    def window_area_m2(self) -> float:
        return self.area_m2 * self.window_fraction if self.window else 0.0

    @property
    def opaque_area_m2(self) -> float:
        return self.area_m2 - self.window_area_m2


# --------------------------------------------------------------------------- #
# Air, usage, lieu
# --------------------------------------------------------------------------- #
class Ventilation(_Frozen):
    """Ventilation + infiltrations.

    ach50          : étanchéité (renouvellements/h à 50 Pa). Infiltration moyenne ≈ ach50/20.
    mech_ach       : débit d'air neuf mécanique [1/h] (0 si aucune ventilation mécanique).
    heat_recovery  : rendement de récupération (0 = extraction simple) [-].
    """

    ach50: float = Field(ge=0)
    mech_ach: float = Field(0.0, ge=0)
    heat_recovery: float = Field(0.0, ge=0, le=1)


class Usage(_Frozen):
    """Occupation et apports internes.

    Les profils sont définis par heure LOCALE (24 valeurs, 0..1).
    """

    n_people: int = Field(ge=0)
    w_per_person: float = 80.0  # apport sensible par personne présente [W]
    appliances_w_mean: float = 300.0  # puissance moyenne des appareils [W]
    occupancy_profile: tuple[float, ...] = (1,) * 7 + (0.5,) * 10 + (1,) * 7
    appliance_profile: tuple[float, ...] = (0.5,) * 6 + (1.2,) * 3 + (0.7,) * 8 + (1.6,) * 4 + (0.8,) * 3

    day_setpoint_c: float = 20.0
    night_setpoint_c: float = 17.0
    night_start_h: int = 23
    night_end_h: int = 6

    def setpoint_series(self, local_hour: np.ndarray) -> np.ndarray:
        """Consigne [°C] pour chaque heure locale."""
        h = np.asarray(local_hour)
        night = (h >= self.night_start_h) | (h < self.night_end_h)
        return np.where(night, self.night_setpoint_c, self.day_setpoint_c).astype(float)


class Location(_Frozen):
    """Boston Logan par défaut."""

    latitude: float = 42.37
    longitude: float = -71.01
    altitude_m: float = 6.0
    albedo: float = 0.2  # 0.6-0.8 avec neige


# --------------------------------------------------------------------------- #
# La maison
# --------------------------------------------------------------------------- #
class House(_Frozen):
    name: str
    location: Location
    floor_area_m2: float = Field(gt=0)  # surface de plancher chauffée A_f
    n_levels: int = Field(ge=1)
    storey_height_m: float = Field(gt=0)
    surfaces: tuple[Surface, ...]
    ventilation: Ventilation
    usage: Usage
    thermal_bridge_uplift: float = Field(0.10, ge=0)  # majoration de H_tr_op [-]

    @property
    def volume_m3(self) -> float:
        return self.floor_area_m2 * self.storey_height_m  # A_f est déjà cumulée sur les niveaux
