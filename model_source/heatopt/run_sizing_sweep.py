"""Heat pump size x backup fuel sweep: annual cost and CO2 for one city.

Run from the folder ABOVE the package:
    python -m heatopt.run_sizing_sweep --city Montreal
    python -m heatopt.run_sizing_sweep --city Boston --weather path/to/Boston_hourly_2010-2025.csv

Weather CSV format: same as the Montreal ERA5 file (see data/weather.py).
Writes sweep_<city>.csv and sweep_<city>.png to --out (default: ./outputs).

One thermal run per heat pump size (backup sized to cover the peak), then every
backup fuel, price scenario and dispatch rule is costed from that run.

PLACEHOLDER capital costs (no catalog in the repo yet): heat pump installed =
5,000 USD + 1,500 USD per rated kW, 15 years, 5 %. The backup is assumed to exist
already (retrofit). Replace with real catalog values before quoting totals.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from heatopt.config import Location
from heatopt.data import energy
from heatopt.data.weather import CsvWeather
from heatopt.examples import demo_house
from heatopt.operation import annual_summary, annualized_capex, dispatch
from heatopt.simulate import simulate
from heatopt.systems.heat_pump import HeatPump, HybridSystem

LOCATIONS = {
    "Montreal": Location(latitude=45.5, longitude=-73.57, altitude_m=36.0),
    "Boston": Location(latitude=42.37, longitude=-71.01, altitude_m=6.0),
    "Atlanta": Location(latitude=33.64, longitude=-84.43, altitude_m=308.0),
}
DEFAULT_WEATHER = {
    "Montreal": Path(__file__).parent / "data/tables/Montreal_hourly_2010-2025_ERA5 - Montreal_hourly_2010-2025_ERA5.csv",
}
HP_FIXED_USD, HP_PER_KW_USD = 5000.0, 1500.0  # PLACEHOLDER


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="Montreal", choices=list(LOCATIONS))
    ap.add_argument("--weather", type=Path, default=None)
    ap.add_argument("--sizes", default="3:20:1", help="start:stop:step, rated kW at 8.3 °C")
    ap.add_argument("--backup-kw", type=float, default=20.0)
    ap.add_argument("--out", type=Path, default=Path("outputs"))
    a = ap.parse_args()

    weather = CsvWeather(str(a.weather or DEFAULT_WEATHER[a.city])).load()
    house = demo_house().model_copy(update={"location": LOCATIONS[a.city]})
    lo, hi, st = (float(x) for x in a.sizes.split(":"))
    sizes = [lo + i * st for i in range(int(round((hi - lo) / st)) + 1)]
    backups = [b for b in energy.backup_names() if energy.has_price(a.city, energy.backup(b).fuel)]

    rows = []
    for kw in sizes:
        hp = HeatPump(rated_kw=kw)
        res = simulate(house, weather, HybridSystem(hp, a.backup_kw))
        capex_yr = annualized_capex(HP_FIXED_USD + HP_PER_KW_USD * kw)
        for b in backups:
            for scenario in ("historical", "nov2026"):
                for rule in ("hp_first", "economic"):
                    s = annual_summary(dispatch(res, hp, a.backup_kw, b, a.city, scenario=scenario, rule=rule))
                    rows.append({"city": a.city, "hp_rated_kw": kw, "backup": b, "prices": scenario, "rule": rule,
                                 "hp_capex_per_yr_usd": capex_yr, "total_cost_per_yr_usd": capex_yr + s["cost_usd"], **s})
        print(f"{kw:5.1f} kW done")

    df = pd.DataFrame(rows)
    a.out.mkdir(parents=True, exist_ok=True)
    csv = a.out / f"sweep_{a.city}.csv"
    df.round(4).to_csv(csv, index=False)
    plot(df, a.city, a.out / f"sweep_{a.city}.png")

    view = df[(df.prices == "nov2026") & (df.rule == "economic")]
    best = view.loc[view.groupby("backup").total_cost_per_yr_usd.idxmin()]
    cols = ["backup", "hp_rated_kw", "total_cost_per_yr_usd", "cost_usd", "co2_kg", "hp_share", "seasonal_cop", "cold_hours_per_yr"]
    print("\nCheapest heat pump size per backup (Nov 2026 prices, economic dispatch):")
    print(best[cols].round(2).to_string(index=False))
    print(f"\n{csv}\n{a.out / f'sweep_{a.city}.png'}")


def plot(df: pd.DataFrame, city: str, path: Path) -> None:
    v = df[(df.prices == "nov2026") & (df.rule == "economic")]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    for b, g in v.groupby("backup"):
        g = g.sort_values("hp_rated_kw")
        ax1.plot(g.co2_kg, g.total_cost_per_yr_usd, marker="o", ms=3, label=b)
        for _, r in g.iloc[::3].iterrows():
            ax1.annotate(f"{r.hp_rated_kw:.0f}", (r.co2_kg, r.total_cost_per_yr_usd), fontsize=7, alpha=0.7)
        ax2.plot(g.hp_rated_kw, g.total_cost_per_yr_usd, marker="o", ms=3, label=b)
    ax1.set_xlabel("CO2 [kg/yr]")
    ax1.set_ylabel("Total cost [USD/yr] (placeholder capex + energy)")
    ax1.set_title(f"{city}: cost vs CO2, labels = heat pump kW")
    ax2.set_xlabel("Heat pump rated capacity at 8.3 °C [kW]")
    ax2.set_ylabel("Total cost [USD/yr]")
    ax2.set_title("Total cost vs heat pump size")
    for ax in (ax1, ax2):
        ax.grid(alpha=0.3)
        ax.legend()
    fig.suptitle("Nov 2026 prices, economic dispatch (carbon price 0)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


if __name__ == "__main__":
    main()
