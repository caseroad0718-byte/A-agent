from core.formulas import (
    Scenario,
    calculate_alpha_score,
    calculate_expected_value_pct,
    calculate_max_position_pct,
)


def test_max_position_formula_matches_plan():
    value = calculate_max_position_pct(emotion=72, chaos=44, quant_dominance=58)
    expected = 60 * 0.72 * (1 - 44 * 0.5 / 100) * (1 - 58 * 0.3 / 100)
    assert value == round(expected, 2)


def test_alpha_rewards_fresh_uncrowded_logic():
    uncrowded = calculate_alpha_score(90, 90, 20, 30, 90)
    crowded = calculate_alpha_score(90, 90, 90, 90, 20)
    assert uncrowded > crowded


def test_expected_value_pct():
    scenarios = [
        Scenario("A", 20, 0.5, "base invalid"),
        Scenario("B", 40, 0.25, "bull invalid"),
        Scenario("C", -12, 0.25, "bear invalid"),
    ]
    assert calculate_expected_value_pct(scenarios) == 17.0

