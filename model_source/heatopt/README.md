# HeatOpt: heat pump sizing for Boston, Atlanta and Montreal

MIT Energy & Climate Hack 2026, COMSOL heat pump track.

**Question:** is it better to undersize a heat pump and rely on backup heat, or to size it for the
coldest weather? Which strategy gives the best balance of cost and CO2, and how does it change
with climate?

**Answer (from this model):** undersize. In every city, the best design at any realistic carbon value
is a heat pump covering 20–60 % of the design load plus the existing backup in the coldest hours.
The oversized condition (2 × Mitsubishi H2i 3-ton) cuts CO2 further but costs 2–4 times more: in the existing
houses, 600–1,400 USD per tonne avoided versus gas, against 15–190 USD/t for the best undersized design. In Atlanta it is worse on both cost and CO2 than a smaller, more
efficient unit. Details: `RESULTS.md`.

## What the model does

1. **House** (`building/`): ISO 13790 5R1C hourly thermal model (Owen's code). Nine houses from the
   team tables: Existing / Code / High-perf in each city (`building/archetypes.py`), calibrated to the
   team workbook (UA within 0.2 %, design load within 2–5 %).
2. **Weather** (`data/`, `study_sim.py`): ERA5 hourly 2010–2025 for each city (16 winters, no gaps);
   TMY/CWEC typical years for checks.
3. **Heat pumps** (`systems/`):
   - `heat_pump.py`: 8 brand datasheets (capacity and COP vs outdoor temperature), scaled to a size
     factor = capacity at the 99 % design temperature / design load; real unscaled units for the
     oversized condition; cycling penalty below 30 % load.
   - `suz_ka.py`: Mitsubishi SUZ-KA line (5 sizes), single units or pairs, same line in every city.
4. **Dispatch, cost, CO2** (`operation.py`, `data/energy.py`): each hour, heat pump vs backup
   (resistance, gas, oil, propane, pellets, Hydro-Québec Rate DT). Rules: heat pump first, switch on
   cost, switch on CO2, or switch at a carbon value. Prices by year (2010–2025) or Nov 2026; CO2
   from EPA, eGRID and Hydro-Québec.
5. **Optimisation** (`optimize.py`): exhaustive search of heat pump × size × backup × rule for
   each house (thousands of options, exact). One thermal run per house is enough because the
   backup is sized above the peak, so delivered heat does not depend on the heat pump choice.
   Objectives: total annual cost (energy + capex over 15 years at 5 %) and CO2. Outputs every
   configuration, the Pareto front and the picks (cheapest, lowest CO2, best at 190 USD/t).
6. **Full-year totals, slide method** (`annual_totals.py`): the design-day lines (load 0.30 × (21 − T),
   small 3.6 + 0.06 T, large 16.2 + 0.27 T) run for every hour of 2010–2025 with the H2i COP curve;
   annual cost (energy only and with heat pump capex) and CO2 for every backup fuel.
7. **Undersized vs oversized** (`compare_sizing.py`): gas only vs best undersized design vs the
   oversized condition (2 × Mitsubishi H2i 3-ton, heat pump first).

## Run

The package folder must be named `heatopt`. From the folder above it:

```
pip install -r heatopt/requirements.txt
bash heatopt/run_all.sh          # ~25 min on 2 cores; writes the four outputs_* folders
python -m pytest heatopt/tests   # 32 checks
```

Single steps:

```
python -m heatopt.optimize --catalog brands    --out heatopt/outputs_brands      # per-city brands
python -m heatopt.optimize --catalog suz_ka    --out heatopt/outputs_suz_ka      # one product line
python -m heatopt.optimize --catalog oversized --out heatopt/outputs_oversized   # 1x and 2x H2i 3-ton
python -m heatopt.compare_sizing --brands heatopt/outputs_brands --oversized heatopt/outputs_oversized --out heatopt/outputs_compare
python -m heatopt.plot_results --out heatopt/outputs_brands
```

## Outputs

| Folder | Files |
|---|---|
| `outputs_brands/` | `all_configurations.csv`, `pareto_fronts.csv`, `picks.csv`, `pareto_<house>.png` |
| `outputs_suz_ka/` | same, Mitsubishi SUZ-KA line only |
| `outputs_oversized/` | same, 1x and 2x Mitsubishi H2i 3-ton |
| `outputs_annual/` | `annual_totals.csv`: full-year totals from the slide lines, per city × size × backup × prices |
| `outputs_compare/` | `sizing_comparison.csv`, `sizing_comparison.png`: the challenge answer |

Key columns: `total_cost_usd` (energy + annualised heat pump capex), `co2_kg`, `hp_share` (share of
heat from the heat pump), `seasonal_cop`, `backup_hours_per_yr`, `peak_elec_kw`.

## Documents

- `RESULTS.md`: findings, tables, sensitivities.
- `RESULTS_SUZ_KA.md`: the single-product-line run.
- `DATA_GAPS.md`: what data is filled, partial, missing or conflicting.
- `ENERGY_LAYER.md`: how the cost/CO2 layer plugs into the thermal model.

## Main assumptions

- Same box house in every city; three envelope levels per city from the team house tables.
- Backup already installed (no backup capex); pellets and wood need a new stove, so they are
  sensitivity only.
- Heat pump capex per ton: Boston 6,723 USD (MassCEC), Atlanta 1,419 USD (Angi), Montreal uses the
  Boston value (data gap). Capex basis: capacity at 47 °F / 3.517 kW (brand run), nominal tons
  (SUZ-KA and oversized runs).
- COP from datasheets at maximum capacity; part-load gains of inverter units not included.
- Carbon value for the balanced pick: 190 USD/t (EPA 2023 estimate); results also from 0 to 500 USD/t.

## Credits

Thermal model, weather loader and house configuration: Owen (original repo). Energy, cost, CO2,
archetypes, heat pump data layers and optimisation added on top. Data: team folders (house modelling,
weather, energy cost, CO2, heat pump sizing study).
