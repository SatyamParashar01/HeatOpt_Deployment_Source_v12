"""Checks for the dispatch / cost / CO2 layer."""
import numpy as np
import pandas as pd
import pytest

from heatopt.data import energy
from heatopt.operation import annual_summary, annualized_capex, dispatch
from heatopt.systems.heat_pump import HeatPump


def _res(t_c: float, load_kw: float, hours: int = 48, year: int = 2024) -> pd.DataFrame:
    idx = pd.date_range(f"{year}-01-10", periods=hours, freq="h", tz="UTC")
    return pd.DataFrame({"t_out_c": t_c, "phi_hc_w": 1000.0 * load_kw}, index=idx)


def test_energy_balance():
    hp = HeatPump(rated_kw=5)
    for rule in ("hp_first", "economic", "switchover"):
        h = dispatch(_res(-20, 8), hp, 20, "natural_gas", "Boston", rule=rule, switchover_c=-10)
        assert np.allclose(h.hp_heat_kwh + h.backup_heat_kwh, h.heat_kwh)
        assert h.unserved_kwh.sum() == 0


def test_hp_first_uses_full_hp_capacity():
    hp = HeatPump(rated_kw=5, cycling_cd=0)
    h = dispatch(_res(-20, 8), hp, 20, "natural_gas", "Boston")
    assert np.allclose(h.hp_heat_kwh, hp.capacity_w(np.array([-20.0]))[0] / 1000)


def test_economic_matches_break_even_cop():
    """Boston, Nov 2026 prices: gas wins on cost below COP 0.3048 / (0.0839/0.95) = 3.45."""
    hp = HeatPump(rated_kw=10, cycling_cd=0)
    cold = dispatch(_res(-10, 4), hp, 20, "natural_gas", "Boston", scenario="nov2026", rule="economic")
    assert hp.cop(np.array([-10.0]))[0] < 3.45
    assert cold.hp_heat_kwh.sum() == 0  # gas cheaper -> backup carries everything
    # a high carbon price flips it back to the heat pump (cleaner below COP 1.34 break-even)
    green = dispatch(_res(-10, 4), hp, 20, "natural_gas", "Boston", scenario="nov2026",
                     rule="economic", carbon_price_usd_per_t=1000)
    assert green.backup_heat_kwh.sum() == 0


def test_resistance_never_beats_heat_pump():
    hp = HeatPump(rated_kw=10, cycling_cd=0)
    h = dispatch(_res(-25, 4), hp, 20, "electric_resistance", "Montreal", rule="economic")
    assert h.backup_heat_kwh.sum() == 0


def test_backup_too_small_hp_covers_rest():
    hp = HeatPump(rated_kw=10, cycling_cd=0)
    h = dispatch(_res(-10, 6), hp, 2, "natural_gas", "Boston", rule="switchover", switchover_c=0)
    assert np.allclose(h.backup_heat_kwh, 2) and np.allclose(h.hp_heat_kwh, 4)


def test_year_matched_prices():
    years = np.array([2010, 2022, 2025, 2030])
    p = energy.price_by_year("Boston", "electricity", years)
    assert np.allclose(p, [0.154, 0.2868, 0.3041, 0.3041])
    assert energy.price_by_year("Boston", "wood", years[:1], "nov2026")[0] == pytest.approx(0.0281)


def test_cost_and_co2_units():
    hp = HeatPump(rated_kw=10, cycling_cd=0)
    h = dispatch(_res(8, 3.2, hours=1), hp, 0, "electric_resistance", "Boston", scenario="nov2026")
    # COP 3.2 at 8 °C -> 1 kWh electricity -> 0.3048 USD, 256.2 g
    assert h.cost_usd.iloc[0] == pytest.approx(0.3048)
    assert h.co2_kg.iloc[0] == pytest.approx(0.2562)


def test_capex_annuity():
    assert annualized_capex(10000, 15, 0.05) == pytest.approx(963.42, abs=0.01)
    assert annual_summary(dispatch(_res(0, 3), HeatPump(5), 10, "natural_gas", "Atlanta"))["hp_share"] > 0
