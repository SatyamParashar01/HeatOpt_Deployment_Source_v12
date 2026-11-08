"""Heat pump with capacity AND COP curves, plus a hybrid system (heat pump + backup).

Default curves (placeholders, replace with a manufacturer datasheet when available):
  Capacity: shape of the "undersized heat pump" line on the COMSOL challenge slide,
            normalised to 1.0 at the 8.3 °C (47 °F) rating point. Linear fit of the
            digitised slide points: 0.513 at -25 °C, 0.586 at -20 °C, 0.879 at 0 °C.
            Scaling `rated_kw` moves the whole line up or down.
  COP:      3.2 at +8 °C and 1.6 at -25 °C (team assumption), linear between.
  Cut-out:  below `cutout_c` the heat pump delivers nothing.
  Part load: cycling penalty when the unit runs below its minimum modulation
            (PLF = 1 - Cd * (1 - PLR / min_modulation)). This is what makes an
            oversized unit less efficient in mild weather. Cd = 0 switches it off.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CAP_T_C = (-30.0, -25.0, -20.0, -15.0, -10.0, -5.0, 0.0, 8.3, 15.0)
CAP_FRAC = (0.440, 0.513, 0.586, 0.659, 0.732, 0.805, 0.879, 1.000, 1.098)
COP_T_C = (-25.0, 8.0, 15.0)
COP = (1.6, 3.2, 3.54)


@dataclass(frozen=True)
class HeatPump:
    rated_kw: float  # heating capacity at 8.3 °C [kW]
    cap_t_c: tuple[float, ...] = CAP_T_C
    cap_frac: tuple[float, ...] = CAP_FRAC
    cop_t_c: tuple[float, ...] = COP_T_C
    cop_values: tuple[float, ...] = COP
    cutout_c: float = -30.0
    min_modulation: float = 0.30  # lowest steady output as a share of capacity
    cycling_cd: float = 0.25  # degradation coefficient (AHRI default 0.25)

    def capacity_w(self, t_out_c: np.ndarray) -> np.ndarray:
        t = np.asarray(t_out_c, dtype=float)
        cap = 1000.0 * self.rated_kw * np.interp(t, self.cap_t_c, self.cap_frac)
        return np.where(t < self.cutout_c, 0.0, cap)

    def cop(self, t_out_c: np.ndarray) -> np.ndarray:
        """Steady-state COP (no part-load penalty)."""
        return np.interp(np.asarray(t_out_c, dtype=float), self.cop_t_c, self.cop_values)

    def effective_cop(self, t_out_c: np.ndarray, heat_w: np.ndarray) -> np.ndarray:
        """COP including the cycling penalty at low part-load ratio."""
        cap = self.capacity_w(t_out_c)
        plr = np.divide(heat_w, cap, out=np.zeros_like(cap), where=cap > 0)
        plf = np.where(plr < self.min_modulation, 1.0 - self.cycling_cd * (1.0 - plr / self.min_modulation), 1.0)
        return self.cop(t_out_c) * plf

    # HeatingSystem protocol (heat pump alone)
    def max_power_w(self, t_out_c: np.ndarray) -> np.ndarray:
        return self.capacity_w(t_out_c)


@dataclass(frozen=True)
class HybridSystem:
    """Heat pump + backup heater. The thermal model only sees the combined maximum;
    how the heat is split between the two is decided afterwards (operation.dispatch)."""

    heat_pump: HeatPump
    backup_kw: float

    def max_power_w(self, t_out_c: np.ndarray) -> np.ndarray:
        return self.heat_pump.capacity_w(t_out_c) + 1000.0 * self.backup_kw


# --------------------------------------------------------------------------- #
# Manufacturer datasheet curves (team sizing study, data/tables/heat_pump_curves_1C.csv)
# --------------------------------------------------------------------------- #
from functools import lru_cache as _lru_cache
from pathlib import Path as _Path

import pandas as _pd

_CURVES = _Path(__file__).resolve().parent.parent / "data" / "tables" / "heat_pump_curves_1C.csv"
T_RATING_C = 8.33  # 47 F
KW_PER_TON = 3.517

# Short names -> datasheet model names. City lists follow the team study (commonly installed there).
MODELS = {
    "Mitsubishi_H2i_R454B": "Mitsubishi Hyper-Heat H2i 3-ton (current, R-454B)",
    "Mitsubishi_H2i_R410A": "Mitsubishi Hyper-Heat H2i 3-ton (previous gen, R-410A)",
    "Fujitsu_XLTH": "Fujitsu XLTH 2-ton wall ductless",
    "Fujitsu_KZAH": "Fujitsu AIRSTAGE KZAH 2-ton wall ductless (R-32)",
    "Bosch_IDS_Ultra": "Bosch IDS Ultra 3-ton",
    "Daikin_FIT": "Daikin FIT 3-ton (reference curve, fully published)",
    "Goodman_GSZV9": "Goodman GSZV9 3-ton variable-speed (R-410A)",
    "Carrier_25HPA5": "Carrier Performance 25HPA5 3-ton single-stage (standard, R-410A)",
}
CITY_MODELS = {
    "Boston": ("Mitsubishi_H2i_R454B", "Mitsubishi_H2i_R410A", "Fujitsu_XLTH", "Bosch_IDS_Ultra", "Daikin_FIT"),
    "Atlanta": ("Carrier_25HPA5", "Goodman_GSZV9", "Daikin_FIT", "Mitsubishi_H2i_R454B"),
    "Montreal": ("Fujitsu_KZAH", "Mitsubishi_H2i_R454B", "Fujitsu_XLTH", "Bosch_IDS_Ultra", "Goodman_GSZV9"),
}


@_lru_cache
def datasheet(short_name: str) -> _pd.DataFrame:
    c = _pd.read_csv(_CURVES)
    c = c[c.model == MODELS[short_name]].sort_values("T_out_C")
    return c[["T_out_C", "Qmax_kW", "COP_linear_interp"]].reset_index(drop=True)


def from_datasheet(short_name: str, size_factor: float, q_design_kw: float, t_design_c: float, **kw) -> HeatPump:
    """Heat pump whose max capacity at the design temperature = size_factor x design load.

    Capacity shape and COP(T) come from the brand datasheet (COP at max capacity, held
    constant above 18 C, zero capacity below the unit's cutoff).
    """
    d = datasheet(short_name)
    on = d[d.Qmax_kW > 0]
    q_rate = float(_np_interp(T_RATING_C, d.T_out_C, d.Qmax_kW))
    q_des = float(_np_interp(t_design_c, d.T_out_C, d.Qmax_kW))
    if q_des <= 0:
        raise ValueError(f"{short_name} is below cutoff at the design temperature {t_design_c} C")
    rated_kw = size_factor * q_design_kw * q_rate / q_des
    return HeatPump(rated_kw=rated_kw,
                    cap_t_c=tuple(on.T_out_C), cap_frac=tuple(on.Qmax_kW / q_rate),
                    cop_t_c=tuple(on.T_out_C), cop_values=tuple(on.COP_linear_interp),
                    cutout_c=float(on.T_out_C.min()), **kw)


def tons(hp: HeatPump) -> float:
    """Nominal size used for capex: max capacity at 47 F / 3.517 kW (team study basis)."""
    return float(hp.capacity_w(_np_asarray([T_RATING_C]))[0]) / 1000.0 / KW_PER_TON


def _np_interp(x, xp, fp):
    return np.interp(x, np.asarray(xp, float), np.asarray(fp, float))


def _np_asarray(x):
    return np.asarray(x, dtype=float)


# --------------------------------------------------------------------------- #
# Real, unscaled units (used for the oversized condition)
# --------------------------------------------------------------------------- #
OVERSIZED_MODEL = "Mitsubishi_H2i_R454B"  # Mitsubishi Hyper-Heat H2i 3-ton, PUZ-AK36NLHZ (R-454B)
OVERSIZED_UNITS = 2
NOMINAL_TONS = {"Mitsubishi_H2i_R454B": 3.0, "Mitsubishi_H2i_R410A": 3.0, "Bosch_IDS_Ultra": 3.0,
                "Daikin_FIT": 3.0, "Goodman_GSZV9": 3.0, "Carrier_25HPA5": 3.0,
                "Fujitsu_XLTH": 2.0, "Fujitsu_KZAH": 2.0}


def fixed_units(short_name: str, n_units: int, **kw) -> HeatPump:
    """n identical outdoor units of a datasheet model at their real (unscaled) capacity.
    Identical units share the load equally, so COP(T) is the single unit's COP."""
    d = datasheet(short_name)
    on = d[d.Qmax_kW > 0]
    q_rate = float(_np_interp(T_RATING_C, d.T_out_C, d.Qmax_kW)) * n_units
    return HeatPump(rated_kw=q_rate, cap_t_c=tuple(on.T_out_C), cap_frac=tuple(n_units * on.Qmax_kW / q_rate),
                    cop_t_c=tuple(on.T_out_C), cop_values=tuple(on.COP_linear_interp),
                    cutout_c=float(on.T_out_C.min()), **kw)
