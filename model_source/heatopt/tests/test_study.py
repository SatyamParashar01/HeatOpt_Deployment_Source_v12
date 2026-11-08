"""Checks for the city archetypes, datasheet heat pumps, Rate DT and the optimiser."""
import numpy as np
import pandas as pd
import pytest

from heatopt.building.archetypes import LEVELS, build, workbook_row
from heatopt.building.rc_5r1c import FiveR1CParams
from heatopt.operation import dispatch
from heatopt.optimize import pareto
from heatopt.systems.heat_pump import CITY_MODELS, from_datasheet


@pytest.mark.parametrize("city", ["Boston", "Atlanta", "Montreal"])
@pytest.mark.parametrize("level", LEVELS)
def test_archetype_matches_workbook_ua(city, level):
    a, w = build(city, level), workbook_row(city, level)
    p = FiveR1CParams.from_house(a.house)
    assert p.h_tr_w + p.h_tr_op + p.h_ve == pytest.approx(w.ua_air_total_w_k, rel=0.01)
    assert a.ground_loss_w == pytest.approx(w.q_ground_w, rel=0.01)


@pytest.mark.parametrize("city", ["Boston", "Atlanta", "Montreal"])
def test_size_factor_one_meets_design_load(city):
    a = build(city, "Existing")
    q = a.steady_load_w(a.design_t_99_c) / 1000
    for m in CITY_MODELS[city]:
        hp = from_datasheet(m, 1.0, q, a.design_t_99_c)
        assert hp.capacity_w(np.array([a.design_t_99_c]))[0] / 1000 == pytest.approx(q, rel=1e-6)


def _res(temps, load_kw=5.0):
    idx = pd.date_range("2025-01-10", periods=len(temps), freq="h", tz="UTC")
    return pd.DataFrame({"t_out_c": temps, "phi_hc_w": 1000.0 * load_kw}, index=idx)


def test_rate_dt_forces_gas_below_minus_12():
    hp = from_datasheet("Fujitsu_KZAH", 1.0, 13.0, -20.2, cycling_cd=0)
    h = dispatch(_res([-15.0, -12.0, -5.0]), hp, 20, "rate_dt_gas", "Montreal", scenario="nov2026")
    assert np.allclose(h.backup_heat_kwh, [5, 5, 0]) and np.allclose(h.hp_heat_kwh, [0, 0, 5])
    # heat pump electricity at the Rate DT price, not Rate D
    assert h.cost_usd.iloc[2] == pytest.approx(5 / hp.cop(np.array([-5.0]))[0] * 0.0422)


def test_pellets_biogenic_uses_low_factor():
    hp = from_datasheet("Daikin_FIT", 0.2, 10.0, -10.9)
    a = dispatch(_res([-29.5]), hp, 20, "pellets", "Boston", scenario="nov2026")
    b = dispatch(_res([-29.5]), hp, 20, "pellets_biogenic", "Boston", scenario="nov2026")
    assert b.co2_kg.iloc[0] < 0.02 * a.co2_kg.iloc[0]


def test_pareto_front():
    d = pd.DataFrame({"co2_kg": [1, 2, 3, 2.5], "total_cost_usd": [10, 8, 9, 7]})
    assert list(pareto(d).index) == [0, 1, 3]


def test_suz_ka_pair_adds_capacity_and_keeps_cop():
    from heatopt.systems.suz_ka import combo_heat_pump
    t = np.array([-15.0, 0.0, 8.0])
    one = combo_heat_pump(("SUZ-KA36NAHZ",))
    two = combo_heat_pump(("SUZ-KA36NAHZ", "SUZ-KA36NAHZ"))
    assert np.allclose(two.capacity_w(t), 2 * one.capacity_w(t))
    assert np.allclose(two.cop(t), one.cop(t))
    assert one.capacity_w(np.array([-28.0]))[0] == 0  # below the data range


@pytest.mark.parametrize("city", ["Boston", "Atlanta", "Montreal"])
def test_oversized_two_units_exceed_design_load(city):
    """The oversized condition is >= 125 % of the 99.6 % design load in every city (existing house)."""
    from heatopt.systems.heat_pump import OVERSIZED_MODEL, OVERSIZED_UNITS, fixed_units
    a = build(city, "Existing")
    hp = fixed_units(OVERSIZED_MODEL, OVERSIZED_UNITS)
    assert hp.capacity_w(np.array([a.design_t_996_c]))[0] >= 1.25 * a.steady_load_w(a.design_t_996_c)


def test_annual_totals_one_hour_by_hand():
    """Boston, -10 C, small unit, gas: load 9.3 kW, HP 3.0 kW, gas 6.3/0.95 kWh."""
    from heatopt.annual_totals import cop_curve
    cop = cop_curve()
    load, cap = 0.30 * (21 - (-10)), 3.6 + 0.06 * (-10)
    hp = min(load, cap)
    assert load == pytest.approx(9.3) and cap == pytest.approx(3.0)
    assert (load - hp) / 0.95 == pytest.approx(6.6316, rel=1e-3)
    assert hp / cop(np.array([-10.0]))[0] == pytest.approx(3.0 / 2.05, rel=0.05)
