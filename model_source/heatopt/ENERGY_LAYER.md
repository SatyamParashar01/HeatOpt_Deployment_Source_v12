# Energy, cost and CO2 layer

Adds what the thermal model needs to answer the challenge: heat pump COP, backup
dispatch, prices and emissions for Boston, Atlanta and Montreal.

## New files

| File | What it does |
|---|---|
| `data/tables/energy_prices.csv` | USD per kWh of fuel, by city, year (2010–2025) and a `nov2026` scenario |
| `data/tables/emission_factors.csv` | g CO2e per kWh of fuel; grid electricity average and marginal per city |
| `data/tables/backup_heaters.csv` | Backup types and efficiencies (gas 0.95, oil 0.85, propane 0.95, wood 0.70, resistance 1.0) |
| `data/energy.py` | Loaders: `price_by_year`, `emission_factor`, `backup` |
| `systems/heat_pump.py` | `HeatPump` (capacity + COP curves, cycling penalty) and `HybridSystem` (HP + backup, for the 5R1C model) |
| `operation.py` | `dispatch` (hourly split, cost, CO2), `annual_summary`, `annualized_capex` |
| `run_sizing_sweep.py` | Sweep heat pump size × backup × price scenario × dispatch rule |
| `tests/test_operation.py` | Energy balance, break-even logic, units |

Existing files are unchanged.

## How it fits

```python
res = simulate(house, weather, HybridSystem(HeatPump(rated_kw=8), backup_kw=20))
hourly = dispatch(res, hp, 20, "natural_gas", "Boston", scenario="nov2026", rule="economic",
                  carbon_price_usd_per_t=0)
summary = annual_summary(hourly)   # cost_usd, co2_kg, hp_share, seasonal_cop, cold_hours...
```

The heat delivered does not depend on the backup fuel, the prices or the dispatch rule.
Hence **one thermal run per (house, heat pump size, backup size)** serves every fuel,
scenario and carbon price. For NSGA-II, cache the thermal run on those three and cost
the rest in vectorised numpy (milliseconds).

## Dispatch rules

- `hp_first`: heat pump first, backup covers the rest.
- `economic`: each hour, whichever is cheaper per kWh of heat, with
  cost = price + carbon_price × CO2. Carbon price 0 = cost break-even COP rule.
  Sweep the carbon price to trace the cost/CO2 trade-off.
- `switchover`: backup only below `switchover_c` (use as a GA decision variable).

## Price scenarios

- `historical`: each weather year uses that year's prices (year-matched with ERA5 2010–2025).
- `nov2026`: latest prices for every year. Wood has no current price; latest year is used.

## Placeholders to replace

- Heat pump capacity shape: fitted to the COMSOL slide's undersized curve (1.0 at 8.3 °C).
- COP: 3.2 at +8 °C, 1.6 at −25 °C, linear.
- Cycling penalty: Cd = 0.25 below 30 % of capacity.
- Capex in `run_sizing_sweep.py`: 5,000 USD + 1,500 USD/kW, 15 yr, 5 %. Backup assumed already installed.

## Known data caveats

- Montreal electricity (`nov2026`) includes GST+QST; Montreal gas likely excludes them. This favours gas.
- Fixed gas connection charges are not included. This also favours gas.
- Historical Montreal electricity is the 1,000 kWh/month bill average; heating kWh are billed at the higher Rate D tier.
- Boston and Atlanta need their own 2010–2025 hourly weather CSV in the same format as the Montreal ERA5 file.

## Run

From the folder above the package (the package folder must be named `heatopt`):

```
python -m heatopt.run_sizing_sweep --city Montreal --out outputs
python -m pytest heatopt/tests
```

## Update: team data wired in (7 Nov 2026)

- `building/archetypes.py`: Existing / Code / High-perf houses for the 3 cities from `data/tables/houses/`, calibrated to the team workbook (UA within 0.2 %).
- `systems/heat_pump.py`: `from_datasheet(brand, size_factor, design_load_kw, design_t_c)` uses the 8 brand datasheets; replaces the placeholder curves.
- `study_sim.py`: ERA5 (2010–2025) and TMY loaders for all 3 cities; `simulate_archetype`.
- New backups: pellets, Hydro-Québec Rate DT dual energy. Capex per ton by city (`heat_pump_capex.csv`).
- `optimize.py` (exhaustive search, Pareto fronts, picks) and `plot_results.py`.
- See `DATA_GAPS.md` and `RESULTS.md`.
