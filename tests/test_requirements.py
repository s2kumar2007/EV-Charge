"""
Tests for charger requirements sizing, Erlang C queueing, and Monte Carlo estimation.
All tests use deterministic closed-form or in-memory fixtures.
"""
import pytest
import numpy as np
import pandas as pd

from requirements_model import (
    erlang_c_probability,
    erlang_c_waiting_time,
    size_ports_erlang_c,
    calculate_net_charger_requirements,
    monte_carlo_charger_requirements,
)


@pytest.mark.xfail(raises=NotImplementedError, reason="Implementation pending in feat(requirements)")
def test_erlang_c_hand_computed_values():
    """Verify Erlang C probability and expected wait against exact hand-calculated solutions."""
    # Scenario: lambda = 2 arrivals/hr, mu = 2 services/hr (avg 30 min duration), traffic A = 1.0 Erlang
    # Hand solution for c = 2:
    # rho = 1/2, sum_{k=0..1} A^k/k! = 1 + 1 = 2
    # last term = (1/2) * (1 / (1 - 0.5)) = 1
    # P_C = 1 / (2 + 1) = 1/3 ~ 0.333333
    prob_c2 = erlang_c_probability(c=2, traffic_erlangs=1.0)
    assert pytest.approx(prob_c2, rel=1e-4) == 1.0 / 3.0

    # Wait time: Wq = P_C / (c*mu - lambda) = (1/3) / (4 - 2) = 1/6 hours (~10 min)
    wait_c2 = erlang_c_waiting_time(c=2, arrival_rate=2.0, service_rate=2.0)
    assert pytest.approx(wait_c2, rel=1e-4) == 1.0 / 6.0

    # Hand solution for c = 3:
    # rho = 1/3, sum_{k=0..2} A^k/k! = 1 + 1 + 0.5 = 2.5
    # last term = (1/6) * (1 / (1 - 1/3)) = (1/6) * (3/2) = 0.25
    # P_C = 0.25 / (2.5 + 0.25) = 0.25 / 2.75 = 1/11 ~ 0.090909
    prob_c3 = erlang_c_probability(c=3, traffic_erlangs=1.0)
    assert pytest.approx(prob_c3, rel=1e-4) == 1.0 / 11.0

    # Wait time: Wq = (1/11) / (6 - 2) = 1/44 hours (~1.36 min)
    wait_c3 = erlang_c_waiting_time(c=3, arrival_rate=2.0, service_rate=2.0)
    assert pytest.approx(wait_c3, rel=1e-4) == 1.0 / 44.0


@pytest.mark.xfail(raises=NotImplementedError, reason="Implementation pending in feat(requirements)")
def test_erlang_c_boundary_conditions():
    """Verify Erlang C stability condition rho >= 1 and zero traffic."""
    # Zero traffic has 0 probability of queueing
    assert erlang_c_probability(c=2, traffic_erlangs=0.0) == 0.0

    # Overloaded system (rho >= 1): queue explodes, probability is 1.0
    assert erlang_c_probability(c=2, traffic_erlangs=2.5) == 1.0
    assert erlang_c_waiting_time(c=2, arrival_rate=5.0, service_rate=2.0) == float("inf")
