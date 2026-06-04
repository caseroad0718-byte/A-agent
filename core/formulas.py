from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def calculate_max_position_pct(
    emotion: float,
    chaos: float,
    quant_dominance: float,
    base_max_position_pct: float = 60.0,
) -> float:
    value = base_max_position_pct * (emotion / 100.0) * (1 - chaos * 0.5 / 100.0)
    value *= 1 - quant_dominance * 0.3 / 100.0
    return round(clamp(value, 0.0, base_max_position_pct), 2)


def calculate_logic_score(
    growth: float,
    quality: float,
    valuation: float,
    catalyst_clarity: float,
    weights: dict[str, float],
) -> float:
    score = (
        growth * weights["growth"]
        + quality * weights["quality"]
        + valuation * weights["valuation"]
        + catalyst_clarity * weights["catalyst_clarity"]
    )
    return round(clamp(score), 2)


def calculate_alpha_score(
    logic_score: float,
    catalyst_clarity: float,
    narrative_strength: float,
    narrative_consistency: float,
    narrative_freshness: float,
) -> float:
    """High alpha means strong logic with hard catalyst and under-crowded narrative."""
    logic_component = logic_score * (catalyst_clarity / 100.0)
    crowding = (narrative_strength / 100.0) * (narrative_consistency / 100.0)
    freshness_component = narrative_freshness / 100.0
    discount = 1.0 - (crowding * (1.0 - freshness_component))
    return round(clamp(logic_component * discount), 2)


@dataclass(frozen=True)
class Scenario:
    name: str
    expected_return_pct: float
    probability: float
    invalidation_condition: str


def calculate_expected_value_pct(scenarios: list[Scenario]) -> float:
    return round(sum(item.expected_return_pct * item.probability for item in scenarios), 2)


def risk_grade_penalty(grade: str) -> float:
    return {"A": 0.0, "B": 8.0, "C": 25.0, "D": 100.0}.get(grade.upper(), 50.0)


def calculate_composite_score(
    signal_factor: float,
    style_weight: float,
    research_alpha: float,
    liquidity_quality: float,
    risk_grade: str,
    research_alpha_weight: float,
    liquidity_quality_weight: float,
) -> float:
    score = signal_factor * style_weight
    score += research_alpha * research_alpha_weight
    score += liquidity_quality * liquidity_quality_weight
    score -= risk_grade_penalty(risk_grade)
    return round(clamp(score), 2)


def scenario_to_dict(scenario: Scenario) -> dict[str, Any]:
    return {
        "name": scenario.name,
        "expected_return_pct": scenario.expected_return_pct,
        "probability": scenario.probability,
        "invalidation_condition": scenario.invalidation_condition,
    }

