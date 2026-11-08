"""Modèle 5R1C horaire, ISO 13790 (méthode simple horaire, annexe C).

Nœuds : θ_e (extérieur), θ_air, θ_s (surface intérieure), θ_m (masse). Un seul état : θ_m.

Conductances [W/K]
  H_ve    = rho_c * V * (n_inf + n_mech*(1-eta)) / 3600     ventilation + infiltrations
  H_tr_w  = sum(U_w * A_w)                                   fenêtres
  H_tr_op = (1+ponts) * sum(b * U * A_opaque)                parois opaques (global)
  H_tr_ms = 9.1 * A_m                                        masse <-> surface
  H_tr_is = 3.45 * A_t, A_t = 4.5 * A_f                      surface <-> air
  H_tr_em = 1 / (1/H_tr_op - 1/H_tr_ms)                      masse <-> extérieur
Capacité : C_m = sum(kappa_j * A_j) [J/K] ; A_m = C_m^2 / sum(kappa_j^2 * A_j) [m2]

Charge idéale : le modèle est linéaire en Phi_HC, donc on résout pour 0 et 10*A_f
et on interpole pour atteindre la consigne (ISO 13790 C.4), puis on plafonne à la
capacité du système. Si la capacité est insuffisante, la température descend.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from heatopt.building.base import BoundaryConditions
from heatopt.config import House
from heatopt.systems.base import HeatingSystem

RHO_C_AIR = 1200.0  # rho*c de l'air [J/(m3.K)]
H_MS = 9.1  # [W/(m2.K)]
H_IS = 3.45  # [W/(m2.K)]
A_T_FACTOR = 4.5  # A_t = 4.5 * A_f


@dataclass(frozen=True)
class FiveR1CParams:
    h_ve: float
    h_tr_w: float
    h_tr_op: float
    h_tr_ms: float
    h_tr_is: float
    h_tr_em: float
    c_m: float
    a_m: float
    a_t: float
    a_f: float

    @classmethod
    def from_house(cls, house: House) -> "FiveR1CParams":
        v = house.ventilation
        n_eff = v.ach50 / 20.0 + v.mech_ach * (1.0 - v.heat_recovery)  # [1/h]
        h_ve = RHO_C_AIR * house.volume_m3 * n_eff / 3600.0

        h_tr_w = sum(s.window.u_w * s.window_area_m2 for s in house.surfaces if s.window)
        h_tr_op = (1.0 + house.thermal_bridge_uplift) * sum(
            s.b_tr * s.construction.u_value() * s.opaque_area_m2 for s in house.surfaces
        )

        kappa_a = [(s.construction.kappa_internal(), s.opaque_area_m2) for s in house.surfaces]
        c_m = sum(k * a for k, a in kappa_a)
        a_m = c_m**2 / sum(k**2 * a for k, a in kappa_a)

        a_t = A_T_FACTOR * house.floor_area_m2
        h_tr_ms = H_MS * a_m
        if h_tr_op >= h_tr_ms:
            raise ValueError("H_tr_op >= H_tr_ms : H_tr_em serait négatif (masse trop faible ?)")
        h_tr_em = 1.0 / (1.0 / h_tr_op - 1.0 / h_tr_ms)
        return cls(h_ve, h_tr_w, h_tr_op, h_tr_ms, H_IS * a_t, h_tr_em, c_m, a_m, a_t, house.floor_area_m2)

    @property
    def h_total(self) -> float:
        """Déperdition globale vue depuis l'air, en régime établi [W/K].

        H = H_ve + [ 1/H_tr_is + 1/(H_tr_w + H_tr_op) ]^-1
        Fenêtres et parois sont reliées au nœud de SURFACE, pas à l'air : la
        résistance d'échange H_tr_is est donc en série. (Elle vaut H_ve + H_tr_w
        + H_tr_op seulement si H_tr_is -> infini.)
        """
        h_env = self.h_tr_w + self.h_tr_op
        return self.h_ve + 1.0 / (1.0 / self.h_tr_is + 1.0 / h_env)


class FiveR1C:
    def __init__(self, house: House):
        self.house = house
        self.p = FiveR1CParams.from_house(house)

    # -- un pas de temps, état -> état ------------------------------------------------
    def _solve(self, theta_m_prev, te, phi_int, phi_sol, phi_hc):
        """Retourne (θ_m, θ_s, θ_air) à la fin du pas. Flux en [W], θ en [°C]."""
        p = self.p
        phi_ia = 0.5 * phi_int
        phi_m = p.a_m / p.a_t * (0.5 * phi_int + phi_sol)
        phi_st = (1 - p.a_m / p.a_t - p.h_tr_w / (H_MS * p.a_t)) * (0.5 * phi_int + phi_sol)

        h1 = 1.0 / (1.0 / p.h_ve + 1.0 / p.h_tr_is) if p.h_ve > 0 else 0.0
        h2 = h1 + p.h_tr_w
        h3 = 1.0 / (1.0 / h2 + 1.0 / p.h_tr_ms)
        te_sup = te  # l'effet de la récupération est déjà dans H_ve

        phi_air_term = (phi_ia + phi_hc) / p.h_ve + te_sup if p.h_ve > 0 else 0.0
        phi_mtot = (
            phi_m + p.h_tr_em * te
            + h3 * (phi_st + p.h_tr_w * te + h1 * phi_air_term) / h2
        )
        cm_h = p.c_m / 3600.0
        theta_m = (theta_m_prev * (cm_h - 0.5 * (h3 + p.h_tr_em)) + phi_mtot) / (cm_h + 0.5 * (h3 + p.h_tr_em))
        theta_m_avg = 0.5 * (theta_m + theta_m_prev)
        theta_s = (p.h_tr_ms * theta_m_avg + phi_st + p.h_tr_w * te + h1 * phi_air_term) / (
            p.h_tr_ms + p.h_tr_w + h1
        )
        theta_air = (p.h_tr_is * theta_s + p.h_ve * te_sup + phi_ia + phi_hc) / (p.h_tr_is + p.h_ve)
        return theta_m, theta_s, theta_air

    # -- simulation complète -----------------------------------------------------------
    def run(self, bc: BoundaryConditions, system: HeatingSystem, theta_m0: float | None = None) -> pd.DataFrame:
        p = self.p
        n = len(bc.t_out_c)
        cap = system.max_power_w(bc.t_out_c)
        theta_m = bc.setpoint_c[0] if theta_m0 is None else theta_m0
        probe = 10.0 * p.a_f

        out = {k: np.empty(n) for k in ("t_air_c", "t_op_c", "t_mass_c", "phi_hc_w", "phi_demand_w")}
        for k in range(n):
            te, pi, ps = bc.t_out_c[k], bc.internal_w[k], bc.solar_gain_w[k]
            t0 = self._solve(theta_m, te, pi, ps, 0.0)[2]
            if t0 >= bc.setpoint_c[k]:
                demand = 0.0
            else:
                t10 = self._solve(theta_m, te, pi, ps, probe)[2]
                demand = probe * (bc.setpoint_c[k] - t0) / (t10 - t0)
            phi = min(demand, cap[k])
            theta_m, theta_s, theta_air = self._solve(theta_m, te, pi, ps, phi)
            out["t_air_c"][k] = theta_air
            out["t_op_c"][k] = 0.3 * theta_air + 0.7 * theta_s
            out["t_mass_c"][k] = theta_m
            out["phi_hc_w"][k] = phi
            out["phi_demand_w"][k] = demand
        return pd.DataFrame(out, index=bc.index)
