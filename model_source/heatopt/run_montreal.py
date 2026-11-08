"""Simulation de la maison d'exemple avec la météo ERA5 de Montréal (2010-2025).

Chauffage idéal (capacité illimitée) : on obtient le besoin de chauffage brut.
Lancer depuis le dossier parent du paquet : `python -m heatopt.run_montreal`.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # pas d'affichage graphique dans WSL
import matplotlib.pyplot as plt

from heatopt.config import Location
from heatopt.data.weather import CsvWeather
from heatopt.examples import demo_house
from heatopt.simulate import simulate
from heatopt.systems.base import IdealHeater

CSV = "/home/owens/old_projet/hhack/heatopt/data/tables/Montreal_hourly_2010-2025_ERA5 - Montreal_hourly_2010-2025_ERA5.csv"
OUT = "/mnt/c/Users/owens/Desktop/montreal_temperatures.png"

weather = CsvWeather(CSV).load()
house = demo_house().model_copy(update={"location": Location(latitude=45.5, longitude=-73.57, altitude_m=36.0)})
res = simulate(house, weather, IdealHeater(1e9))

# Énergie de chauffage [kWh] : phi_hc_w est en W sur des pas d'1 h.
kwh = res["phi_hc_w"].clip(lower=0) / 1000
annual = kwh.groupby(kwh.index.year).sum()
print("Consommation de chauffage par année [kWh] :")
print(annual.round(0).to_string())
print(f"Moyenne : {annual.mean():.0f} kWh/an | puissance de pointe : {res['phi_hc_w'].max() / 1000:.1f} kW")

# Mois le plus froid de la période
coldest = res["t_out_c"].groupby([res.index.year, res.index.month]).mean().idxmin()
m = res[(res.index.year == coldest[0]) & (res.index.month == coldest[1])]

fig, (ax, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True, height_ratios=(2, 1))
ax.plot(m.index, m["t_out_c"], label="Extérieure", color="tab:blue", lw=1)
ax.plot(m.index, m["t_air_c"], label="Intérieure (air)", color="tab:red", lw=1.5)
ax.set_ylabel("Température [°C]")
ax.set_title(f"Maison demo, Montréal — mois le plus froid ({coldest[0]}-{coldest[1]:02d})")
ax.legend()
ax.grid(alpha=0.3)
ax2.plot(m.index, m["phi_hc_w"] / 1000, color="tab:orange", lw=1)
ax2.set_ylabel("Puissance de chauffage [kW]")
ax2.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(OUT, dpi=150)
print(f"Figure : {OUT}")
