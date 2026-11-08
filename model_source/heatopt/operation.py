"""From hourly heat delivered to hourly energy, cost and CO2.

    simulate(house, weather, HybridSystem(hp, backup_kw))   -> res (5R1C, hourly heat)
    dispatch(res, hp, backup_kw, backup, prices...)          -> hourly split + cost + CO2
    annual_summary(hourly)                                   -> one average year

Dispatch rules (`rule`):
  "hp_first"   the heat pump supplies all it can, the backup covers the rest.
  "economic"   each hour, use whichever source is cheaper per kWh of HEAT, where
               cost = price + carbon_price * CO2. With carbon_price = 0 this is the
               cost break-even COP rule; raising carbon_price traces the cost/CO2
               trade-off. Electric resistance never wins against a heat pump with COP > 1.
  "switchover" backup only below `switchover_c` (a decision variable for the optimiser).

When the backup takes over but is too small, the heat pump covers what is left.
Delivered heat never changes with the rule, so one thermal run serves every rule,
backup fuel, price scenario and carbon price.
"""
from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from heatopt.data import energy
from heatopt.systems.heat_pump import HeatPump

Rule = Literal["hp_first", "economic", "switchover"]


def dispatch(
    res: pd.DataFrame,
    hp: HeatPump,
    backup_kw: float,
    backup_name: str,
    city: energy.City,
    scenario: energy.Scenario = "historical",
    grid: energy.Grid = "average",
    rule: Rule = "hp_first",
    carbon_price_usd_per_t: float = 0.0,
    switchover_c: float = -100.0,
) -> pd.DataFrame:
    """Hourly results. `res` must contain phi_hc_w and t_out_c (output of simulate).

    Tariff backups (Rate DT) override the rule: the backup is forced at and below their
    switch temperature, and heat pump electricity is billed at the tariff price.
    """
    bk = energy.backup(backup_name)
    t = res["t_out_c"].to_numpy(float)
    q = np.clip(res["phi_hc_w"].to_numpy(float), 0.0, None)  # delivered heat [W] = [Wh] per hour
    years = res.index.year.to_numpy()

    p_el = energy.price_by_year(city, "electricity", years, scenario)  # USD/kWh, resistance backup
    p_hp = np.full_like(p_el, bk.hp_price_override) if bk.hp_price_override is not None else p_el
    p_bk = energy.price_by_year(city, bk.fuel, years, scenario)
    ef_el = energy.emission_factor(city, "electricity", grid)  # g/kWh
    ef_bk = energy.emission_factor(city, bk.emission_key, grid)
    if bk.forced_switch_c is not None:
        rule, switchover_c = "switchover", bk.forced_switch_c + 1e-9  # backup at and below the switch T

    cap_hp = hp.capacity_w(t)
    cap_bk = 1000.0 * backup_kw
    hp_heat = np.minimum(q, cap_hp)  # hp_first

    if rule != "hp_first":
        if rule == "economic":
            lam = carbon_price_usd_per_t / 1e6  # USD per g
            cop_full = hp.effective_cop(t, hp_heat)
            hp_cost = (p_hp + lam * ef_el) / np.maximum(cop_full, 1e-6)  # per kWh heat
            bk_cost = (p_bk + lam * ef_bk) / bk.efficiency
            use_backup = (bk_cost < hp_cost) | (cap_hp <= 0)
        elif rule == "switchover":
            use_backup = t < switchover_c
        else:
            raise ValueError(rule)
        hp_when_backup = np.minimum(np.maximum(q - cap_bk, 0.0), cap_hp)
        hp_heat = np.where(use_backup, hp_when_backup, hp_heat)

    bk_heat = q - hp_heat
    unserved_w = np.maximum(bk_heat - cap_bk, 0.0)  # should be ~0 if the thermal run used this system
    bk_heat = bk_heat - unserved_w

    cop_eff = hp.effective_cop(t, hp_heat)
    hp_el = np.divide(hp_heat, cop_eff, out=np.zeros_like(hp_heat), where=hp_heat > 0) / 1000.0  # kWh
    bk_fuel = bk_heat / bk.efficiency / 1000.0  # kWh of fuel (electricity if resistance)

    out = pd.DataFrame(index=res.index)
    out["t_out_c"] = t
    out["heat_kwh"] = q / 1000.0
    out["hp_heat_kwh"] = hp_heat / 1000.0
    out["backup_heat_kwh"] = bk_heat / 1000.0
    out["hp_elec_kwh"] = hp_el
    out["backup_fuel_kwh"] = bk_fuel
    out["cop_eff"] = np.where(hp_heat > 0, cop_eff, np.nan)
    out["cost_usd"] = hp_el * p_hp + bk_fuel * p_bk
    out["co2_kg"] = (hp_el * ef_el + bk_fuel * ef_bk) / 1000.0
    out["elec_kw"] = hp_el + (bk_fuel if bk.fuel == "electricity" else 0.0)  # grid draw [kW]
    out["unserved_kwh"] = unserved_w / 1000.0
    for c in ("t_air_c", "setpoint_c", "phi_demand_w"):
        if c in res:
            out[c] = res[c].to_numpy(float)
    return out


def annual_summary(hourly: pd.DataFrame) -> dict:
    """Averages per year over the simulated period, plus worst-year cost."""
    n_years = len(hourly) / 8766.0
    by_year = hourly.groupby(hourly.index.year)
    s = {k: hourly[k].sum() / n_years for k in
         ("heat_kwh", "hp_heat_kwh", "backup_heat_kwh", "hp_elec_kwh", "backup_fuel_kwh", "cost_usd", "co2_kg", "unserved_kwh")}
    s["hp_share"] = s["hp_heat_kwh"] / s["heat_kwh"] if s["heat_kwh"] else np.nan
    s["seasonal_cop"] = s["hp_heat_kwh"] / s["hp_elec_kwh"] if s["hp_elec_kwh"] else np.nan
    s["worst_year_cost_usd"] = by_year["cost_usd"].sum().max()
    s["peak_elec_kw"] = hourly["elec_kw"].max()
    s["backup_hours_per_yr"] = (hourly["backup_heat_kwh"] > 0.01).sum() / n_years
    if "t_air_c" in hourly:
        gap = hourly["setpoint_c"] - hourly["t_air_c"]
        s["cold_hours_per_yr"] = (gap > 1.0).sum() / n_years
        s["degree_hours_per_yr"] = gap.clip(lower=0).sum() / n_years
    return s


def annualized_capex(capex_usd: float, lifetime_yr: float = 15.0, discount_rate: float = 0.05) -> float:
    """Capital recovery factor: equal yearly payment that repays capex over the lifetime."""
    r, n = discount_rate, lifetime_yr
    return capex_usd * r * (1 + r) ** n / ((1 + r) ** n - 1)
