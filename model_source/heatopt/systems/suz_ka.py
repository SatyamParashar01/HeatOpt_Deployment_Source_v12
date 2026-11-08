"""Mitsubishi SUZ-KA (NAHZ) heat pump line: one product family used in every city.

Tables (data/tables/): suz_ka_capacity_kW.csv and suz_ka_cop.csv, max heating capacity and COP
for 5 sizes (12k-36k BTU/h nominal) from -27 C to +15 C. Values below -15 C and above +8 C are
extrapolated in the source; capacity is set to 0 below -27 C (end of data = assumed cutoff) and
held flat above +15 C.

Systems: no heat pump, any single unit, or any pair of units (same or different sizes), because
one 36k unit covers only ~75 % of the existing Boston / Montreal design load.
Two units share the load in proportion to their capacity, so the pair's COP is the
capacity-weighted harmonic mean of the two units' COPs.
Capex basis: nominal tons from the model number (12k BTU/h = 1 ton) x city cost per ton.
"""
from __future__ import annotations

from functools import lru_cache
from itertools import combinations_with_replacement
from pathlib import Path

import numpy as np
import pandas as pd

from heatopt.systems.heat_pump import HeatPump

TABLES = Path(__file__).resolve().parent.parent / "data" / "tables"
UNITS = ("SUZ-KA12NAHZ", "SUZ-KA18NAHZ", "SUZ-KA24NAHZ", "SUZ-KA30NAHZ", "SUZ-KA36NAHZ")
NOMINAL_TONS = {u: int(u[6:8]) / 12 for u in UNITS}
T_RATING_C = 8.33


@lru_cache
def _tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    cap = pd.read_csv(TABLES / "suz_ka_capacity_kW.csv").set_index("outdoor_temp_C")
    cop = pd.read_csv(TABLES / "suz_ka_cop.csv").set_index("outdoor_temp_C")
    return cap, cop


def combo_heat_pump(units: tuple[str, ...], **kw) -> HeatPump:
    """One HeatPump object for one or more outdoor units running together."""
    cap, cop = _tables()
    t = cap.index.to_numpy(float)
    q = sum(cap[u].to_numpy(float) for u in units)
    elec = sum(cap[u].to_numpy(float) / cop[u].to_numpy(float) for u in units)
    q_rate = float(np.interp(T_RATING_C, t, q))
    return HeatPump(rated_kw=q_rate, cap_t_c=tuple(t), cap_frac=tuple(q / q_rate),
                    cop_t_c=tuple(t), cop_values=tuple(q / elec), cutout_c=float(t.min()), **kw)


def systems(max_units: int = 2) -> list[tuple[str, tuple[str, ...]]]:
    out = []
    for n in range(1, max_units + 1):
        for combo in combinations_with_replacement(UNITS, n):
            out.append(("+".join(u.replace("NAHZ", "") for u in combo), combo))
    return out


def nominal_tons(units: tuple[str, ...]) -> float:
    return sum(NOMINAL_TONS[u] for u in units)
