# Data gap map (team data, 7 Nov 2026)

Status: **filled** = in the model now · **partial** = used with an assumption · **gap** = missing · **conflict** = two team sources disagree.

## Weather

| Need | Status | Source / note |
|---|---|---|
| Hourly weather 2010–2025, all 3 cities | filled | `Weather/*_ERA5.csv`; 140,256 h each, no missing hours |
| Station design temps, typical year | filled | `climate.csv`, TMY3 (Boston, Atlanta), CWEC2020 (Montreal). ERA5 1 % temps are 0.3–1.0 °C milder than ASHRAE 99 % |
| Humidity / defrost | partial | RH is in ERA5, but COP comes from datasheets only (defrost only as far as datasheets include it) |

## House

| Need | Status | Source / note |
|---|---|---|
| Envelope U, airtightness, ventilation, mass (3 levels × 3 cities) | filled | `scenarios.csv`, `geometry.csv`, `usage.csv`; 5R1C matches workbook UA within 0.2 %, design load within 2–5 %, TMY heat within 2–8 % |
| Ground losses | filled | workbook ground UA + ground temperature |
| Renovation cost (Existing → Code → High-perf) | **gap** | energy and CO2 savings computed, payback cannot be |
| One house definition | **conflict** | sizing study uses UA 333 W/K (Manual J, MassCEC); workbook Boston Existing is ~417 W/K. Model uses the workbook archetypes |

## Heat pumps

| Need | Status | Source / note |
|---|---|---|
| Capacity and COP vs T, 8 brands | filled | datasheets (`heat_pump_curves_1C.csv`); some points estimated (Bosch COPs, Carrier below 17 °F, Fujitsu below 5 °F) |
| Part-load COP | **gap** | datasheets give COP at max capacity; model assumes a cycling penalty (Cd 0.25 below 30 % load) |
| Installed cost | partial | Boston $6,723/ton (MassCEC), Atlanta $1,419/ton (Angi); **Montreal gap** (Boston value used as proxy) |
| Backup and ductwork cost | **gap** | backup assumed already installed (cost 0); ducted vs ductless install differences not captured |

## Prices

| Need | Status | Source / note |
|---|---|---|
| Electricity, gas, oil, propane 2010–2025 + Nov 2026 | filled | EIA, BLS, MA DOER, StatCan, Hydro-Québec |
| Montreal gas | filled | Energir all-in bill (incl. fixed charges) replaces the StatCan value |
| Pellets | partial | US national average $250/ton, no history, same for all cities |
| Heat pump / time-of-use rates | **gap** | only Hydro-Québec Rate DT modelled; Mass Save heat pump rate, Georgia Power winter rate, Hydro-Québec Flex D missing |
| Boston gas | **conflict** | $2.46/therm (EIA winter, delivered, used here) vs $2.03 (DOER, sizing study): cost break-even COP 3.45 vs 4.18 |
| Atlanta electricity | **conflict** | 15.9 ¢ (EIA Aug 2026, used here) vs 14.5 ¢ (sizing study) |

## Emissions

| Need | Status | Source / note |
|---|---|---|
| Fuel factors, grid average and marginal | filled | EPA 2025, eGRID2023, Hydro-Québec 2025 |
| Montreal marginal (winter imports) | **gap** | only the average rate |
| Hourly grid intensity | **gap** | annual rates only |
| Upstream methane, refrigerant leakage | **gap** | combustion only; would make gas worse and heat pumps slightly worse |
| Grid factors | **conflict** | Boston 256 g (CO2e + line losses, used here) vs 245 g; Montreal 7.8 g vs 1.8 g (ISO-NE import rate) |
