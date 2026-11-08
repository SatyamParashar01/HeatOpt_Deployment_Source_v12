"""Juges analytiques du modèle 5R1C."""
import numpy as np

from heatopt.building.rc_5r1c import FiveR1CParams
from heatopt.examples import demo_house, synthetic_weather
from heatopt.simulate import simulate
from heatopt.systems.base import IdealHeater
from heatopt.config import Usage


def _no_gain_house():
    h = demo_house(n_people=0)
    usage = Usage(n_people=0, appliances_w_mean=0.0, day_setpoint_c=20.0, night_setpoint_c=20.0)
    return h.model_copy(update={"usage": usage})


def test_steady_state_Q_equals_H_dT():
    """En régime établi sans apports : Phi = H_total * (T_cons - T_ext), à 0,1 %."""
    house = _no_gain_house()
    res = simulate(house, synthetic_weather(days=60, t_c=-5.0), IdealHeater(1e9))
    h = FiveR1CParams.from_house(house).h_total
    expected = h * (20.0 - (-5.0))
    assert abs(res["phi_hc_w"].iloc[-1] - expected) / expected < 1e-3


def test_free_floating_converges_to_outdoor():
    """Sans chauffage ni apports, T_int tend vers T_ext."""
    res = simulate(_no_gain_house(), synthetic_weather(days=120, t_c=-5.0), IdealHeater(0.0))
    assert abs(res["t_air_c"].iloc[-1] - (-5.0)) < 0.05


def test_undersized_heater_leaves_room_cold():
    house = _no_gain_house()
    res = simulate(house, synthetic_weather(days=30, t_c=-15.0), IdealHeater(2000.0))
    assert res["t_air_c"].iloc[-1] < 20.0 - 1.0


def test_more_insulation_never_increases_demand():
    house = demo_house()
    from heatopt.config import Layer
    thicker = house.model_copy(update={"surfaces": tuple(
        s.model_copy(update={"construction": s.construction.model_copy(update={"layers": (
            Layer(name="iso+", thickness_m=0.10, conductivity=0.04, density=50, specific_heat=1600), *s.construction.layers)})})
        if s.kind == "wall" else s for s in house.surfaces)})
    w = synthetic_weather(days=30, t_c=-5.0)
    a = simulate(house, w, IdealHeater(1e9))["phi_hc_w"].sum()
    b = simulate(thicker, w, IdealHeater(1e9))["phi_hc_w"].sum()
    assert b <= a
