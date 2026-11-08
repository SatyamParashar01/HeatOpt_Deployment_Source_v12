"""City house archetypes (Existing / Code / High-perf) from the team's house tables.

Tables (data/tables/houses/): scenarios.csv (U-values, airtightness, ventilation, heat
capacity per city and level), geometry.csv, usage.csv, climate.csv (ground temperature,
design temperatures), workbook_results.csv (team spreadsheet: volume, ground UA, design
loads and TMY annual heat, used here for calibration checks).

Same box in every city: 12 m (E-W) x 7.75 m (N-S), 2 storeys of 2.6 m, window-to-wall
ratio S 0.20 / N 0.10 / E,W 0.15, 4 m2 door on the north wall. Boston and Montreal have a
basement (0.6 m above grade); Atlanta is slab on grade.

Choices that make the 5R1C model match the team workbook:
  * each envelope part gets an equivalent single-layer construction with the target U;
  * thermal bridges = 0 (the workbook has none);
  * infiltration: ach50 is set to 20 x ach_natural, so the model's ach50/20 gives ach_natural;
    mechanical ventilation rate is recovered from the workbook ventilation UA;
  * thermal mass: ISO 13790 simple method, C_m = heat_capacity x A_f, A_m = 2.5 x A_f;
  * ground: constant loss UA_ground x (21 C - ground temperature), taken off the internal
    gains every hour (the 5R1C model only has an outdoor boundary).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from heatopt.building.base import BoundaryConditions
from heatopt.building.rc_5r1c import H_MS, FiveR1C, FiveR1CParams
from heatopt.config import Construction, House, Layer, Location, Surface, Usage, Ventilation, WindowSpec

HOUSES = Path(__file__).resolve().parent.parent / "data" / "tables" / "houses"
LEVELS = ("Existing", "Code", "High-perf")
SETPOINT_C = 21.0
_R_SURF = 0.17  # r_si + r_se [m2.K/W]


@lru_cache
def _tables():
    sc = pd.read_csv(HOUSES / "scenarios.csv").set_index("id")
    geo = pd.read_csv(HOUSES / "geometry.csv").set_index("parameter")["value"].astype(float)
    use = pd.read_csv(HOUSES / "usage.csv").set_index("parameter")["value"].astype(float)
    clim = pd.read_csv(HOUSES / "climate.csv").set_index("city")
    wb = pd.read_csv(HOUSES / "workbook_results.csv").set_index("id")
    return sc, geo, use, clim, wb


def archetype_id(city: str, level: str) -> str:
    return f"{city[:3].upper()}-{level}"


def _u_construction(name: str, u: float, kappa_layer: bool = True) -> Construction:
    """Single layer with total U = u (incl. surface resistances)."""
    r_layer = 1.0 / u - _R_SURF
    if r_layer <= 0:
        raise ValueError(f"U={u} too high for {name}")
    d = 0.10
    return Construction(name=name, layers=(Layer(name=name, thickness_m=d, conductivity=d / r_layer,
                                                 density=1000.0, specific_heat=1000.0),))


@dataclass(frozen=True)
class Archetype:
    id: str
    city: str
    level: str
    house: House
    c_m_j_k: float
    a_m_m2: float
    ground_loss_w: float  # constant loss to the ground at the setpoint
    design_t_99_c: float  # ASHRAE 99 % heating dry-bulb
    design_t_996_c: float

    def model_factory(self):
        arch = self

        class CalibratedFiveR1C(FiveR1C):
            def __init__(self, house: House):
                super().__init__(house)
                p = self.p
                h_tr_ms = H_MS * arch.a_m_m2
                h_tr_em = 1.0 / (1.0 / p.h_tr_op - 1.0 / h_tr_ms)
                self.p = dataclasses.replace(p, c_m=arch.c_m_j_k, a_m=arch.a_m_m2, h_tr_ms=h_tr_ms, h_tr_em=h_tr_em)

        return CalibratedFiveR1C

    def adjust_boundary(self, bc: BoundaryConditions) -> BoundaryConditions:
        return dataclasses.replace(bc, internal_w=bc.internal_w - self.ground_loss_w)

    def steady_load_w(self, t_out_c: float, with_gains: bool = False) -> float:
        """Steady-state heat load at a fixed outdoor temperature (Manual J style without gains)."""
        h = FiveR1CParams.from_house(self.house).h_total
        q = h * (SETPOINT_C - t_out_c) + self.ground_loss_w
        if with_gains:
            u = self.house.usage
            q -= u.n_people * u.w_per_person * u.occupancy_profile[0] + u.appliances_w_mean
        return max(q, 0.0)


def build(city: str, level: str) -> Archetype:
    sc, geo, use, clim, wb = _tables()
    aid = archetype_id(city, level)
    s, w, c = sc.loc[aid], wb.loc[aid], clim.loc[city]

    L, D = geo["length_ew_m"], geo["depth_ns_m"]
    h_wall = geo["storeys"] * geo["storey_height_m"]
    door = geo["door_area_m2"]
    window = WindowSpec(name="window", u_w=float(s.window_u_w_m2k), g=float(s.window_g),
                        frame_fraction=0.0, shading_factor=float(s.window_frame_shading_factor))
    wall = _u_construction("wall", float(s.wall_u_w_m2k))
    surfaces = []
    for name, az, length, wwr_key in (("S", 180, L, "wwr_south"), ("N", 0, L, "wwr_north"),
                                       ("E", 90, D, "wwr_east"), ("W", 270, D, "wwr_west")):
        gross = length * h_wall
        win_area = geo[wwr_key] * gross
        if name == "N":
            gross -= door  # door modelled as its own surface
        surfaces.append(Surface(name=f"wall_{name}", kind="wall", area_m2=gross, construction=wall,
                                azimuth_deg=az, window=window, window_fraction=win_area / gross))
    surfaces.append(Surface(name="door", kind="wall", area_m2=door, azimuth_deg=0,
                            construction=_u_construction("door", float(s.door_u_w_m2k))))
    surfaces.append(Surface(name="roof", kind="roof", area_m2=L * D, tilt_deg=0,
                            construction=_u_construction("roof", float(s.roof_u_w_m2k))))
    if bool(s.has_basement):
        above = geo["basement_height_m"] - geo["basement_depth_below_grade_m"]
        surfaces.append(Surface(name="basement_wall", kind="wall", area_m2=above * 2 * (L + D),
                                construction=_u_construction("basement", float(s.basement_wall_above_grade_u_w_m2k))))

    floors = geo["storeys"] + (1 if bool(s.has_basement) else 0)
    a_f = L * D * floors
    volume = float(w.volume_m3)
    eta = float(s.heat_recovery_eff)
    mech_ach = float(w.ua_ventilation_w_k) * 3600 / (1200 * volume * (1 - eta)) if w.ua_ventilation_w_k > 0 else 0.0
    vent = Ventilation(ach50=20 * float(s.ach_natural), mech_ach=mech_ach, heat_recovery=eta)

    occ = use["fraction_hours_home"]
    devices = sum(v for k, v in use.items() if k.startswith("device_"))
    usage = Usage(n_people=int(use["occupants"]), w_per_person=use["sensible_w_per_person"],
                  appliances_w_mean=devices, occupancy_profile=(occ,) * 24, appliance_profile=(1.0,) * 24,
                  day_setpoint_c=SETPOINT_C, night_setpoint_c=SETPOINT_C)

    loc = Location(latitude=float(c.lat), longitude=float(c.lon), altitude_m=0.0)
    house = House(name=aid, location=loc, floor_area_m2=a_f, n_levels=int(floors), storey_height_m=volume / a_f,
                  surfaces=tuple(surfaces), ventilation=vent, usage=usage, thermal_bridge_uplift=0.0)
    ground = float(w.ua_ground_w_k) * (SETPOINT_C - float(c.ground_temp_c))
    return Archetype(id=aid, city=city, level=level, house=house,
                     c_m_j_k=float(s.heat_capacity_kj_m2k) * 1000 * a_f, a_m_m2=2.5 * a_f,
                     ground_loss_w=ground, design_t_99_c=float(c.ashrae_99_c), design_t_996_c=float(c.ashrae_996_c))


def workbook_row(city: str, level: str) -> pd.Series:
    return _tables()[4].loc[archetype_id(city, level)]
