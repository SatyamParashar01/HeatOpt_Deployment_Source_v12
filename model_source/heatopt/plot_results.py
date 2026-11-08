"""Charts from optimize.py outputs.

    python -m heatopt.plot_results --out outputs

pareto_<house>.png : one panel per city. Grey dots = every configuration, blue line = Pareto
                     front, labelled points = baseline (gas only), cheapest, lowest CO2 and
                     best at the carbon value.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from heatopt.optimize import SENSITIVITY_ONLY, pareto

BLUE, INK, MUTED, GRID, DOT = "#2a78d6", "#1f1f1e", "#6b6a64", "#e6e5e0", "#c9c8c1"
PICK_LABEL = {"baseline_gas_only": "Gas only", "cheapest": "Cheapest", "lowest_co2": "Lowest CO2"}


def label(r) -> str:
    if r.size_factor == 0:
        return f"no HP + {r.backup}"
    if str(r.brand).startswith("SUZ"):
        return f"{r.brand} ({r.size_factor:.0%} of design load) + {r.backup}"
    return f"{r.brand} x{r.size_factor:.1f} + {r.backup}"


def plot_house(df: pd.DataFrame, picks: pd.DataFrame, house: str, prices: str, path: Path) -> None:
    cities = [c for c in ("Boston", "Atlanta", "Montreal") if c in set(df.city)]
    fig, axes = plt.subplots(1, len(cities), figsize=(6.2 * len(cities), 5.6))
    axes = [axes] if len(cities) == 1 else axes
    for ax, city in zip(axes, cities):
        g = df[(df.city == city) & (df.house == house) & (df.prices == prices) & (df.grid == "average")
               & ~df.backup.isin(SENSITIVITY_ONLY)]
        f = pareto(g)
        ax.scatter(g.co2_kg / 1000, g.total_cost_usd, s=9, color=DOT, lw=0, label="All configurations (some off-scale)", zorder=1)
        ax.plot(f.co2_kg / 1000, f.total_cost_usd, color=BLUE, lw=2, marker="o", ms=4, label="Pareto front", zorder=2)
        p = picks[(picks.city == city) & (picks.house == house) & (picks.prices == prices) & (picks.grid == "average")]
        # merge picks that are the same configuration (e.g. gas only = cheapest)
        merged = {}
        for _, r in p.iterrows():
            k = (round(r.co2_kg, 1), round(r.total_cost_usd, 1))
            name = PICK_LABEL.get(r.pick, "Best at carbon value")
            merged.setdefault(k, [r, []])[1].append(name)
        place = {"Lowest CO2": (10, 28), "Best at carbon value": (-12, -34), "Gas only": (-14, 34), "Cheapest": (16, -32)}
        for r, names in merged.values():
            dx, dy = place[names[0]]
            ax.scatter(r.co2_kg / 1000, r.total_cost_usd, s=70, facecolor="white", edgecolor=INK, lw=1.5, zorder=3)
            ax.annotate(f"{' = '.join(names)}\n{label(r)}\n${r.total_cost_usd:,.0f}/yr, {r.co2_kg / 1000:.1f} t",
                        (r.co2_kg / 1000, r.total_cost_usd), textcoords="offset points", xytext=(dx, dy),
                        fontsize=7.5, color=INK, va="center", ha="left" if dx > 0 else "right",
                        arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6),
                        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.85))
        ymin, ymax = f.total_cost_usd.min(), f.total_cost_usd.max()
        ax.set_ylim(ymin - 0.25 * (ymax - ymin), ymax + 0.45 * (ymax - ymin))
        ax.set_xlim(0, max(g.co2_kg.quantile(0.98), p.co2_kg.max()) / 1000 * 1.12)
        ax.set_title(f"{city}", fontsize=12, color=INK, loc="left")
        ax.set_xlabel("CO2 [t/yr]", color=MUTED)
        ax.set_ylabel("Total cost [USD/yr] (energy + heat pump capex)", color=MUTED)
        ax.grid(color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors=MUTED)
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    fig.suptitle(f"{house} house, {prices} prices: cost vs CO2 of every heat pump size, brand, backup and control rule",
                 fontsize=10, color=MUTED)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs"))
    a = ap.parse_args()
    df = pd.read_csv(a.out / "all_configurations.csv")
    picks = pd.read_csv(a.out / "picks.csv")
    for house in df.house.unique():
        plot_house(df, picks, house, "nov2026", a.out / f"pareto_{house}.png")
        print(a.out / f"pareto_{house}.png")


if __name__ == "__main__":
    main()
