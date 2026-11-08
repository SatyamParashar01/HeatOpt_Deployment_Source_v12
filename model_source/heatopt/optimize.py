"""Exhaustive optimisation: heat pump brand x size x backup x control rule, per city and house.

    python -m heatopt.optimize --out outputs

Decision variables (all discrete, so the search is exhaustive and exact):
  brand        the city's commonly installed heat pumps (team sizing study)
  size_factor  heat pump max capacity at the city's 99 % design temperature / design load
               (0 = no heat pump, backup only = baseline)
  backup       electric resistance, gas, oil, propane, pellets, Hydro-Quebec Rate DT + gas
  rule         hp_first | cost_switch | carbon_switch | balanced_switch (carbon value 190 USD/t)
               (Rate DT forces gas at and below -12 C)

Objectives: total annual cost (energy + annualised heat pump capex) and annual CO2.
Outputs: every configuration, the Pareto front, and picks per city / house / scenario:
  cheapest, lowest CO2, and best at a carbon value (min cost + value x CO2).

One 5R1C run per house (16 years of ERA5): the backup is sized above the peak, so the heat
delivered does not depend on the heat pump. Every configuration is then costed hourly.
"""
from __future__ import annotations

import argparse
import math
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from heatopt.building.archetypes import LEVELS, build
from heatopt.data import energy
from heatopt.operation import annual_summary, annualized_capex, dispatch
from heatopt.study_sim import era5, simulate_archetype
from heatopt.systems import suz_ka
from heatopt.systems.heat_pump import (CITY_MODELS, NOMINAL_TONS, OVERSIZED_MODEL, OVERSIZED_UNITS, HeatPump,
                                      fixed_units, from_datasheet, tons)

SIZES = (0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4)
CARBON_VALUE = 190.0  # USD per tonne CO2 (EPA 2023 social cost of carbon estimate); change freely
RULES = {  # name -> (dispatch rule, carbon price for the hourly decision)
    "hp_first": ("hp_first", 0.0),
    "cost_switch": ("economic", 0.0),
    "carbon_switch": ("economic", 1e6),
    "balanced_switch": ("economic", CARBON_VALUE),
}
# Backups that would need a NEW stove (no install cost in the data): kept in all_configurations.csv,
# left out of the headline picks and Pareto fronts.
SENSITIVITY_ONLY = {"pellets", "pellets_biogenic", "wood"}


def evaluate_house(city: str, level: str, scenarios=("nov2026", "historical"), grids=("average",),
                   backups: list[str] | None = None, catalog: str = "brands") -> pd.DataFrame:
    """catalog "brands": each city's brands scaled to size factors (team sizing study).
    catalog "suz_ka": the Mitsubishi SUZ-KA line in every city, one or two real units.
    catalog "oversized": 1x and 2x Mitsubishi H2i 3-ton (real units); 2x is the oversized condition."""
    arch = build(city, level)
    res = simulate_archetype(arch, era5(city))
    q_design_kw = arch.steady_load_w(arch.design_t_99_c) / 1000.0
    backup_kw = math.ceil(res["phi_hc_w"].max() / 1000.0) + 1.0
    backups = backups or energy.backup_names(city)
    cpt = energy.capex_per_ton(city)

    systems = [("none", 0.0, HeatPump(rated_kw=0.0), 0.0)]
    if catalog == "oversized":
        for n in (1, OVERSIZED_UNITS):
            hp = fixed_units(OVERSIZED_MODEL, n)
            size = float(hp.capacity_w(np.array([arch.design_t_99_c]))[0]) / 1000.0 / q_design_kw
            systems.append((f"{n}x Mitsubishi_H2i_3ton", round(size, 3), hp, n * NOMINAL_TONS[OVERSIZED_MODEL]))
    elif catalog == "suz_ka":
        for name, units in suz_ka.systems():
            hp = suz_ka.combo_heat_pump(units)
            size = float(hp.capacity_w(np.array([arch.design_t_99_c]))[0]) / 1000.0 / q_design_kw
            systems.append((name, round(size, 3), hp, suz_ka.nominal_tons(units)))
    else:
        for m in CITY_MODELS[city]:
            for sf in SIZES:
                hp = from_datasheet(m, sf, q_design_kw, arch.design_t_99_c)
                systems.append((m, sf, hp, tons(hp)))
    rows = []
    for brand, size, hp, hp_tons in systems:
        capex = hp_tons * cpt
        capex_yr = annualized_capex(capex) if capex else 0.0
        for b in backups:
            forced = energy.backup(b).forced_switch_c is not None
            rule_names = ["hp_first"] if (size == 0 or forced) else list(RULES)
            for rn in rule_names:
                rule, lam = RULES[rn]
                for sc in scenarios:
                    for g in grids:
                        s = annual_summary(dispatch(res, hp, backup_kw, b, city, scenario=sc, grid=g,
                                                    rule=rule, carbon_price_usd_per_t=lam))
                        rows.append({"city": city, "house": level, "prices": sc, "grid": g, "brand": brand,
                                     "size_factor": size, "hp_kw_at_design": size * q_design_kw,
                                     "hp_tons": hp_tons, "backup": b,
                                     "rule": "rate_dt_forced" if forced and size > 0 else rn,
                                     "design_load_kw": q_design_kw, "backup_kw": backup_kw,
                                     "hp_capex_usd": capex, "hp_capex_per_yr_usd": capex_yr,
                                     "energy_cost_usd": s["cost_usd"], "total_cost_usd": s["cost_usd"] + capex_yr,
                                     "co2_kg": s["co2_kg"], "heat_kwh": s["heat_kwh"], "hp_share": s["hp_share"],
                                     "seasonal_cop": s["seasonal_cop"], "hp_elec_kwh": s["hp_elec_kwh"],
                                     "backup_fuel_kwh": s["backup_fuel_kwh"], "peak_elec_kw": s["peak_elec_kw"],
                                     "worst_year_energy_cost_usd": s["worst_year_cost_usd"],
                                     "backup_hours_per_yr": s["backup_hours_per_yr"],
                                     "unserved_kwh": s["unserved_kwh"]})
    return pd.DataFrame(rows)


def pareto(df: pd.DataFrame, x: str = "co2_kg", y: str = "total_cost_usd") -> pd.DataFrame:
    """Non-dominated rows (lower x and lower y are better)."""
    d = df.sort_values([x, y])
    best, keep = np.inf, []
    for i, v in zip(d.index, d[y].to_numpy()):
        if v < best - 1e-9:
            keep.append(i)
            best = v
    return d.loc[keep]


def picks(df: pd.DataFrame, carbon_value: float = CARBON_VALUE) -> pd.DataFrame:
    out = []
    for key, g in df[~df.backup.isin(SENSITIVITY_ONLY)].groupby(["city", "house", "prices", "grid"]):
        g = g.assign(cost_plus_carbon=g.total_cost_usd + carbon_value / 1000.0 * g.co2_kg)
        base = g[(g.size_factor == 0) & (g.backup == "natural_gas")].iloc[0]
        cheap = g.loc[g.total_cost_usd.idxmin()]
        clean = g.sort_values(["co2_kg", "total_cost_usd"]).iloc[0]
        bal = g.loc[g.cost_plus_carbon.idxmin()]
        for name, r in (("baseline_gas_only", base), ("cheapest", cheap), ("lowest_co2", clean),
                        (f"best_at_{carbon_value:.0f}_usd_per_t", bal)):
            out.append({"pick": name, **r.to_dict()})
        dc = clean.total_cost_usd - cheap.total_cost_usd
        dco2 = (cheap.co2_kg - clean.co2_kg) / 1000.0
        out[-1]["abatement_cost_cheapest_to_lowest_usd_per_t"] = dc / dco2 if dco2 > 0 else np.nan
    return pd.DataFrame(out)


def _job(args):
    city, level, catalog = args
    return evaluate_house(city, level, catalog=catalog)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs"))
    ap.add_argument("--cities", default="Boston,Atlanta,Montreal")
    ap.add_argument("--levels", default=",".join(LEVELS))
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--catalog", default="brands", choices=["brands", "suz_ka", "oversized"])
    ap.add_argument("--from-csv", action="store_true", help="skip simulation, recompute fronts/picks")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.from_csv:
        return summarise(pd.read_csv(a.out / "all_configurations.csv"), a.out)
    jobs = [(c, l, a.catalog) for c in a.cities.split(",") for l in a.levels.split(",")]
    with Pool(a.workers) as pool:
        frames = []
        for f in pool.imap_unordered(_job, jobs):
            frames.append(f)
            print(f"done {f.city.iloc[0]} {f.house.iloc[0]}: {len(f)} configurations", flush=True)
    df = pd.concat(frames, ignore_index=True)
    df.round(4).to_csv(a.out / "all_configurations.csv", index=False)
    summarise(df, a.out)


def summarise(df: pd.DataFrame, out: Path) -> None:
    front = pd.concat([pareto(g[~g.backup.isin(SENSITIVITY_ONLY)]).assign(front=True)
                       for _, g in df.groupby(["city", "house", "prices", "grid"])])
    front.round(4).to_csv(out / "pareto_fronts.csv", index=False)
    p = picks(df)
    p.round(4).to_csv(out / "picks.csv", index=False)
    print(p[(p.prices == "nov2026")][["city", "house", "pick", "brand", "size_factor", "backup", "rule",
                                        "total_cost_usd", "co2_kg", "hp_share"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
