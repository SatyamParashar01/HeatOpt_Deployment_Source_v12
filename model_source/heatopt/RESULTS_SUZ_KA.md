# Optimisation with one heat pump line in every city: Mitsubishi SUZ-KA (NAHZ)

`python -m heatopt.optimize --catalog suz_ka --out outputs_suz_ka` then `python -m heatopt.plot_results --out outputs_suz_ka`

## Setup

- Same houses, weather, prices, backups and control rules as `RESULTS.md`.
- Heat pump choices: none, any one of SUZ-KA12/18/24/30/36, or any pair (20 systems). One 36k unit covers only ~75 % of the existing Boston and Montreal design load, hence pairs.
- Capex: nominal tons from the model number (12k BTU/h = 1 ton) × city cost per ton.
- 8,874 configurations, no unserved heat.

## Existing house, Nov 2026 prices

| City | Gas only | Best at 190 USD/t | Lowest CO2 | Cost of the cut |
|---|---|---|---|---|
| Boston | $3,028, 6.5 t | gas only (heat pump needs ≥ ~500 USD/t) | KA30 + KA30: $6,797, 3.0 t | ~1,063 USD/t |
| Atlanta | $491, 1.6 t | KA12 (63 % of design) + gas: $575, 1.1 t | KA30: $775, 1.1 t | ~548 USD/t |
| Montreal* | $1,315, 6.2 t | KA12 (29 %) + Rate DT gas: $1,430, 2.3 t | KA30 + KA30 + resistance: $4,366, 0.1 t | ~497 USD/t |

\* Montreal capex = Boston proxy. At 3,500 USD/ton, KA12 + Rate DT is cheapest outright ($1,119, 2.3 t); at 1,419 USD/ton, two KA12 on Rate DT ($902, 1.1 t).

Carbon value at which a heat pump first enters the best design (Existing): Boston ~500 USD/t, Atlanta ~190 USD/t, Montreal ~100 USD/t (Rate DT).

## Findings

1. **Smallest unit wins.** Whenever a heat pump is worth adding, it is the KA12 (1 ton), at 29–74 % of the design load, with the existing backup in the coldest hours. Undersizing holds even more strongly than with the brand curves.
2. **This line is less efficient than the best city brands.** Seasonal COP for a near-100 % heat pump system: SUZ-KA 2.9–3.0 vs Daikin FIT 3.6–3.8 (Boston, Atlanta); 2.2 vs 2.8 for Bosch in Montreal. That raises the energy bill and the CO2, so heat pumps look worse than in `RESULTS.md`: Atlanta no longer pays without a carbon value; Boston needs ~500 USD/t.
3. **Montreal still favours a small heat pump + Rate DT** at any carbon value ≥ 100 USD/t.

## Data caveats (SUZ-KA tables)

- COP is published only at −15 °C (5 °F); colder and warmer values are extrapolated. KA12 and KA18 fall to COP 1.0 below about −19 °C and −24 °C (no better than resistance).
- KA30's COP is out of family (2.27 at −15 °C vs 1.57–1.76 for the others, 2.1 at −27 °C). It drives every "lowest CO2" pick; check the source.
- COP appears to be at maximum capacity. Inverter units run more efficiently at part load, so seasonal COP is probably understated. A cross-check against the units' rated HSPF2 would size the error.
- Below −27 °C (end of data) capacity is set to 0. Montreal's coldest ERA5 hour is −29.2 °C.
