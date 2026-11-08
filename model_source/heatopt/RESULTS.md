# Optimisation results (7 Nov 2026)

Full pipeline: `bash heatopt/run_all.sh`. Outputs: `outputs_brands/`, `outputs_oversized/`, `outputs_compare/`, `outputs_suz_ka/`.

## Setup

- 9 houses: Existing / Code / High-perf × Boston, Atlanta, Montreal (team house tables, calibrated 5R1C).
- Weather: ERA5 hourly 2010–2025, one thermal run per house.
- 14,436 configurations: no heat pump or each city's brands × size 0.2–1.4 of design load × backup × control rule × 2 price scenarios.
- Size factor 1.0 = heat pump alone meets the design load at the ASHRAE 99 % temperature.
- Objectives: total annual cost (energy + heat pump capex over 15 yr at 5 %) and annual CO2.
- Headline picks use backups a home already has (gas, oil, propane, resistance, Rate DT). Pellets need a new stove with no cost data, so they are a sensitivity only.
- Carbon value for the "balanced" pick: 190 USD/t (EPA 2023 estimate). Results are also given from 0 to 500 USD/t.

## Existing house, Nov 2026 prices

| City | Gas only | Cheapest | Best at 190 USD/t | Lowest CO2 | Cost of the cut |
|---|---|---|---|---|---|
| Boston | $3,028, 6.5 t | gas only | Daikin FIT ×0.2 + gas, balanced switch: $3,351, 4.8 t (40 % HP heat) | Daikin FIT ×1.0: $5,175, 2.5 t | ~526 USD/t |
| Atlanta | $491, 1.6 t | Daikin FIT ×0.2 + gas, cost switch: $474, 1.3 t | Daikin FIT ×0.6 + gas: $501, 0.9 t (91 %) | Daikin FIT ×1.0: $592, 0.9 t | ~287 USD/t |
| Montreal* | $1,315, 6.2 t | gas only | Goodman ×0.2 + Rate DT gas: $1,745, 2.0 t (69 %) | Bosch IDS Ultra ×1.0 + resistance: $4,033, 0.1 t | ~442 USD/t |

\* Montreal heat pump capex uses the Boston value (data gap). At 3,500 USD/ton a Bosch ×0.2–0.4 on Rate DT becomes the cheapest option outright; at Atlanta's 1,419 USD/ton the cheapest is Bosch ×0.4 on Rate DT ($911, 1.6 t).

## Main findings

1. **Undersize.** At any carbon value up to ~300 USD/t, the best heat pump covers 20–60 % of the design load and leans on the existing backup in the coldest hours. Sizing for the design day (×1.0) only wins if CO2 is the sole goal.
2. **Climate and prices decide whether a heat pump pays at all.** Atlanta: yes, even with no carbon value. Boston: not at 0–100 USD/t (30.5 ¢/kWh electricity and 6,723 USD/ton installed). Montreal: depends on installed cost, which the data lacks.
3. **Control matters as much as size.** Switching to gas when the heat pump is the costlier source per kWh of heat (cost switch) or the dirtier one (carbon switch) moves Boston and Montreal along the trade-off curve at no extra capex. In Montreal, Hydro-Québec's dual-energy Rate DT is the strongest lever.
4. **Brand.** Daikin FIT wins in Boston and Atlanta (best COP; peak capacity at 17 °F, so fewer tons are needed at the design temperature). Bosch IDS Ultra and Goodman lead in Montreal.
5. **Reducing demand beats any heat pump in Boston.** A Code-level Boston house with gas only (2.1 t, $981) emits less than the best heat pump option on the Existing house (4.8 t at 190 USD/t). Renovation cost is a data gap, so payback is not computed.

## Undersized vs oversized (the challenge question)

Oversized condition: **2 × Mitsubishi Hyper-Heat H2i 3-ton (PUZ-AK36NLHZ)** in every city and house,
heat pump first (backup only when the heat pumps cannot meet the load). It is ≥ 125 % of the 99.6 %
design load in every existing house (Boston 145 %, Montreal 131 %, Atlanta 273 %) and runs to −30 °C.
Undersized = best heat pump design with size factor < 1 from the brand optimisation (best at 190 USD/t).
Source: `outputs_compare/sizing_comparison.csv` and `.png` (Nov 2026 prices).

| Existing house | Gas only | Best undersized | Oversized: 2 units |
|---|---|---|---|
| Boston | $3,028, 6.5 t | Daikin FIT ×0.2 + gas, balanced switch: $3,351, 4.8 t | $7,270, 2.8 t (backup 0.4 h/yr) |
| Atlanta | $491, 1.6 t | Daikin FIT ×0.6 + gas: $501, 0.9 t | $1,245, 1.1 t |
| Montreal | $1,315, 6.2 t | Goodman ×0.2 + Rate DT: $1,745, 2.0 t | $5,017, 0.1 t (electric backup, never used) |
| Cost per tonne avoided vs gas | | Boston 189, Atlanta 15, Montreal 102 USD/t | Boston 1,149, Atlanta 1,407, Montreal 603 USD/t |

- Oversizing cuts CO2 most in Boston and Montreal, but each extra tonne beyond the undersized design
  costs ~2,000 USD in Boston and ~1,700 USD in Montreal.
- In Atlanta the oversized system is **worse on both** cost and CO2 than the undersized Daikin
  (lower COP and more cycling at part load: seasonal COP 3.15 vs 3.91).
- The same holds for Code and High-perf houses: oversized costs 2.6–21× the gas baseline, because
  6 tons of heat pump serve a house that needs 3–8 kW at design.

## Sensitivities

- **Historical prices (2010–2025, year-matched):** Boston → gas only at every carbon value up to 190; Atlanta unchanged (Daikin ×0.4–0.6); Montreal at 190 USD/t → Bosch ×0.2 + resistance (0.2 t).
- **Carbon value sweep (Existing):** Boston adopts a heat pump from ~190 USD/t (×0.2) and ×0.4 from 300 USD/t; Atlanta always; Montreal from ~100 USD/t with Rate DT, and all-electric at 500 USD/t.
- **Not yet run:** marginal grid CO2 (Boston, Atlanta), Boston gas at DOER's $2.03/therm, incremental capex if the heat pump also replaces an AC.

## Caveats

See `DATA_GAPS.md`. Biggest: Montreal capex, part-load COP, renovation cost, time-of-use heat pump tariffs (except Rate DT), and size grid floor of 0.2 (the true optimum may be smaller).
