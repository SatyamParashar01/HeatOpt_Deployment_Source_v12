"""Full-year totals from the design-day lines (slide method), hour by hour.

    python -m heatopt.annual_totals --out heatopt/outputs_annual

For every hour of 2010-2025 (ERA5, each city), then averaged per year:
  load            = 0.30 x (21 - T) kW, 0 when T >= 21 C
  small capacity  = 3.6 + 0.06 x T kW        (undersized heat pump line)
  large capacity  = 16.2 + 0.27 x T kW       (oversized heat pump line)
  COP(T)          = Mitsubishi Hyper-Heat H2i 3-ton datasheet (team sizing study), linear between
                    points, held flat outside -30..+18 C. Same COP for both sizes.
  hp heat         = min(load, capacity)
  backup heat     = load - hp heat
  electricity     = hp heat / COP(T)
  backup fuel     = backup heat / efficiency (gas 0.95, oil 0.85, propane 0.95, wood 0.70, resistance 1.0)
  annual cost     = sum(electricity x electricity price + backup fuel x fuel price)
  annual CO2      = sum(electricity x grid rate + backup fuel x fuel factor)
Each hour is 1 h long, so kW summed over hours = kWh.

Prices: "avg2023_2025" (2023-2025 average, the slide numbers) and "nov2026" (latest), USD per kWh
of fuel, from data/tables/energy_prices.csv. CO2: average grid rate and EPA fuel factors from
data/tables/emission_factors.csv (wood counted with all CO2).

Two totals: annual_cost_usd = energy only; total_cost_incl_capex_usd adds the heat pump's installed
cost spread over 15 years at 5 % (tons = capacity at 47 F / 3.517 kW; USD per ton from
data/tables/heat_pump_capex.csv; Montreal uses the Boston value, a data gap). Backup assumed installed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

TABLES = Path(__file__).parent / "data" / "tables"
WEATHER = {
    "Boston": "Boston_hourly_2010-2025_ERA5.csv",
    "Atlanta": "Atlanta_hourly_2010-2025_ERA5.csv",
    "Montreal": "Montreal_hourly_2010-2025_ERA5 - Montreal_hourly_2010-2025_ERA5.csv",
}
UA_KW_PER_K, T_SET = 0.30, 21.0
SIZES = {"none": (0.0, 0.0), "small": (3.6, 0.06), "large": (16.2, 0.27)}  # capacity = a + b x T
BACKUPS = {  # name -> (fuel in price table, efficiency, emission key)
    "electric_resistance": ("electricity", 1.00, "electricity"),
    "natural_gas": ("natural_gas", 0.95, "natural_gas"),
    "heating_oil": ("heating_oil", 0.85, "heating_oil"),
    "propane": ("propane", 0.95, "propane"),
    "wood": ("wood", 0.70, "wood"),
}
COP_MODEL = "Mitsubishi Hyper-Heat H2i 3-ton (current, R-454B)"


def cop_curve(model: str = COP_MODEL):
    c = pd.read_csv(TABLES / "heat_pump_curves_1C.csv")
    c = c[(c.model == model) & c.COP_linear_interp.notna()].sort_values("T_out_C")
    t, cop = c.T_out_C.to_numpy(float), c.COP_linear_interp.to_numpy(float)
    return lambda temp: np.interp(temp, t, cop)


def prices(city: str, scenario: str) -> dict[str, float]:
    p = pd.read_csv(TABLES / "energy_prices.csv")
    p = p[p.city == city]
    out = {}
    for fuel, g in p.groupby("fuel"):
        if scenario == "nov2026":
            cur = g[g.scenario == "nov2026"]
            out[fuel] = float(cur.usd_per_kwh_fuel.iloc[0]) if len(cur) else np.nan
        else:
            h = g[(g.scenario == "historical") & g.year.between(2023, 2025)]
            out[fuel] = float(h.usd_per_kwh_fuel.mean()) if len(h) else np.nan
    return out


def emission_factors(city: str) -> dict[str, float]:
    e = pd.read_csv(TABLES / "emission_factors.csv")
    out = {r.fuel: r.g_co2e_per_kwh_average for r in e[e.city == "all"].itertuples()}
    out["electricity"] = float(e[(e.city == city) & (e.fuel == "electricity")].g_co2e_per_kwh_average.iloc[0])
    return out  # g CO2e per kWh of fuel


def capex_per_year(city: str, size: str, lifetime: float = 15.0, rate: float = 0.05) -> tuple[float, float]:
    a, b = SIZES[size]
    tons = max(a + b * 8.33, 0.0) / 3.517
    usd_per_ton = float(pd.read_csv(TABLES / "heat_pump_capex.csv").set_index("city").loc[city, "usd_per_ton"])
    crf = rate * (1 + rate) ** lifetime / ((1 + rate) ** lifetime - 1)
    return tons, tons * usd_per_ton * crf


def annual_totals(city: str, cop=None) -> pd.DataFrame:
    cop = cop or cop_curve()
    w = pd.read_csv(TABLES / WEATHER[city], usecols=["time_utc", "temp_C"])
    t = w.temp_C.to_numpy(float)
    years = len(t) / 8766.0  # 16 years incl. leap days
    load = np.maximum(UA_KW_PER_K * (T_SET - t), 0.0)  # kW = kWh per hour
    ef = emission_factors(city)
    rows = []
    for size, (a, b) in SIZES.items():
        cap = np.maximum(a + b * t, 0.0)
        hp = np.minimum(load, cap)
        bk = load - hp
        elec = np.divide(hp, cop(t), out=np.zeros_like(hp), where=hp > 0)
        tons, capex_yr = capex_per_year(city, size)
        for backup, (fuel, eff, ekey) in BACKUPS.items():
            fuel_kwh = bk / eff
            for scen in ("avg2023_2025", "nov2026"):
                p = prices(city, scen)
                if np.isnan(p.get(fuel, np.nan)):
                    continue  # no price for this fuel in this city
                cost_el, cost_bk = elec.sum() * p["electricity"], fuel_kwh.sum() * p[fuel]
                rows.append({
                    "city": city, "heat_pump": size, "backup": backup, "prices": scen,
                    "heat_load_kwh": load.sum() / years,
                    "hp_heat_kwh": hp.sum() / years, "backup_heat_kwh": bk.sum() / years,
                    "hp_share_pct": 100 * hp.sum() / load.sum(),
                    "hp_electricity_kwh": elec.sum() / years, "backup_fuel_kwh": fuel_kwh.sum() / years,
                    "seasonal_cop": hp.sum() / elec.sum() if elec.sum() else np.nan,
                    "backup_hours_per_yr": (bk > 1e-6).sum() / years,
                    "cost_hp_electricity_usd": cost_el / years, "cost_backup_usd": cost_bk / years,
                    "annual_cost_usd": (cost_el + cost_bk) / years,
                    "hp_tons": tons, "hp_capex_per_yr_usd": capex_yr,
                    "total_cost_incl_capex_usd": (cost_el + cost_bk) / years + capex_yr,
                    "annual_co2_kg": (elec.sum() * ef["electricity"] + fuel_kwh.sum() * ef[ekey]) / 1000 / years,
                    "price_electricity_usd_per_kwh": p["electricity"], "price_fuel_usd_per_kwh": p[fuel],
                    "efficiency": eff, "design_load_kw_at_coldest": load.max(),
                })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs_annual"))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    df = pd.concat([annual_totals(c) for c in WEATHER], ignore_index=True)
    df.round(2).to_csv(a.out / "annual_totals.csv", index=False)
    v = df[df.prices == "avg2023_2025"]
    print(v.pivot_table(index=["city", "backup"], columns="heat_pump", values=["annual_cost_usd", "total_cost_incl_capex_usd", "annual_co2_kg"])
          .round(0).to_string())
    print(f"\n{a.out / 'annual_totals.csv'}")


if __name__ == "__main__":
    main()
