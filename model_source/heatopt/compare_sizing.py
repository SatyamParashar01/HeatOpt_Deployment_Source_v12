"""Undersized vs oversized: the challenge question, answered per city and house.

    python -m heatopt.compare_sizing --brands outputs --oversized outputs_oversized --out outputs_compare

Three designs per city / house / price scenario:
  gas_only            no heat pump, existing gas furnace (baseline)
  undersized_best     best heat pump design with size factor < 1 from the brand optimisation
                      (lowest total cost + carbon value x CO2; brand, size, backup and rule chosen)
  oversized_2_units   2 x Mitsubishi Hyper-Heat H2i 3-ton (PUZ-AK36NLHZ), real units, heat pump first:
                      the backup only runs when the heat pumps cannot meet the load (backup type chosen
                      at the carbon value; Rate DT excluded because it forces gas below -12 C)
Writes sizing_comparison.csv and sizing_comparison.png (cost and CO2, Nov 2026 prices).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from heatopt.optimize import CARBON_VALUE, SENSITIVITY_ONLY

DESIGNS = ("gas_only", "undersized_best", "oversized_2_units")
LABELS = {"gas_only": "Gas only", "undersized_best": "Best undersized heat pump", "oversized_2_units": "Oversized: 2 units"}
COLORS = {"gas_only": "#2a78d6", "undersized_best": "#eb6834", "oversized_2_units": "#1baf7a"}  # categorical slots 1-3
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e6e5e0"
CITIES, HOUSES = ("Boston", "Atlanta", "Montreal"), ("Existing", "Code", "High-perf")


def _best(g: pd.DataFrame, carbon_value: float) -> pd.Series:
    return g.loc[(g.total_cost_usd + carbon_value / 1000 * g.co2_kg).idxmin()]


def compare(brands: pd.DataFrame, over: pd.DataFrame, carbon_value: float = CARBON_VALUE) -> pd.DataFrame:
    brands = brands[~brands.backup.isin(SENSITIVITY_ONLY) & (brands.grid == "average")]
    over = over[~over.backup.isin(SENSITIVITY_ONLY) & (over.grid == "average")]
    rows = []
    for (city, house, prices), g in brands.groupby(["city", "house", "prices"]):
        o = over[(over.city == city) & (over.house == house) & (over.prices == prices)]
        picks = {
            "gas_only": g[(g.size_factor == 0) & (g.backup == "natural_gas")].iloc[0],
            "undersized_best": _best(g[(g.size_factor > 0) & (g.size_factor < 1)], carbon_value),
            # oversized = the heat pump carries the load; backup only when it cannot (no switching,
            # no tariff-forced backup such as Rate DT)
            "oversized_2_units": _best(o[o.brand.str.startswith("2x") & (o.rule == "hp_first")], carbon_value),
        }
        gas = picks["gas_only"]
        for name, r in picks.items():
            rows.append({"city": city, "house": house, "prices": prices, "design": name,
                         "system": "none" if r.size_factor == 0 else r.brand, "size_factor": r.size_factor,
                         "backup": r.backup, "rule": r.rule, "hp_capex_usd": r.hp_capex_usd,
                         "hp_capex_per_yr_usd": r.hp_capex_per_yr_usd, "energy_cost_usd": r.energy_cost_usd,
                         "total_cost_usd": r.total_cost_usd, "co2_kg": r.co2_kg, "hp_share": r.hp_share,
                         "seasonal_cop": r.seasonal_cop, "peak_elec_kw": r.peak_elec_kw,
                         "backup_hours_per_yr": r.get("backup_hours_per_yr", np.nan),
                         "extra_cost_vs_gas_usd": r.total_cost_usd - gas.total_cost_usd,
                         "co2_cut_vs_gas_kg": gas.co2_kg - r.co2_kg,
                         "usd_per_t_avoided_vs_gas": (r.total_cost_usd - gas.total_cost_usd) / ((gas.co2_kg - r.co2_kg) / 1000)
                         if gas.co2_kg - r.co2_kg > 1 else np.nan,
                         "cost_plus_carbon_usd": r.total_cost_usd + carbon_value / 1000 * r.co2_kg})
    return pd.DataFrame(rows)


def plot(cmp: pd.DataFrame, path: Path, prices: str = "nov2026") -> None:
    c = cmp[cmp.prices == prices]
    fig, axes = plt.subplots(2, 3, figsize=(16, 8.5), sharey="row")
    w = 0.26
    for j, house in enumerate(HOUSES):
        for i, (metric, unit, scale) in enumerate((("total_cost_usd", "Total cost [USD/yr]", 1.0),
                                                    ("co2_kg", "CO2 [t/yr]", 1000.0))):
            ax = axes[i, j]
            for k, d in enumerate(DESIGNS):
                vals = [c[(c.city == city) & (c.house == house) & (c.design == d)][metric].iloc[0] / scale for city in CITIES]
                x = np.arange(len(CITIES)) + (k - 1) * w
                bars = ax.bar(x, vals, width=w - 0.02, color=COLORS[d], label=LABELS[d], zorder=2)
                for b, v in zip(bars, vals):
                    ax.annotate(f"{v:,.0f}" if scale == 1 else f"{v:.1f}", (b.get_x() + b.get_width() / 2, v),
                                textcoords="offset points", xytext=(0, 2), ha="center", fontsize=7, color=MUTED)
            ax.set_xticks(np.arange(len(CITIES)), CITIES)
            ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            ax.tick_params(colors=MUTED)
            if j == 0:
                ax.set_ylabel(unit, color=MUTED)
            if i == 0:
                ax.set_title(f"{house} house", loc="left", color=INK, fontsize=12)
    axes[0, 0].legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle(f"Undersize or oversize? {prices} prices; undersized picks its best backup and rule, oversized runs "
                 f"heat pump first; carbon value of {CARBON_VALUE:.0f} USD/t", fontsize=10, color=MUTED)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brands", type=Path, default=Path("outputs"))
    ap.add_argument("--oversized", type=Path, default=Path("outputs_oversized"))
    ap.add_argument("--out", type=Path, default=Path("outputs_compare"))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    cmp = compare(pd.read_csv(a.brands / "all_configurations.csv"), pd.read_csv(a.oversized / "all_configurations.csv"))
    cmp.round(3).to_csv(a.out / "sizing_comparison.csv", index=False)
    plot(cmp, a.out / "sizing_comparison.png")
    v = cmp[cmp.prices == "nov2026"]
    print(v[["city", "house", "design", "system", "size_factor", "backup", "rule", "total_cost_usd", "co2_kg",
             "hp_share", "seasonal_cop", "backup_hours_per_yr", "usd_per_t_avoided_vs_gas"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
