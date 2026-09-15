"""5DR V2.2.2 Learning Lab governance helpers.

The Learning Lab may evaluate hypotheses and challenger eligibility autonomously,
but it never mutates production model configuration. A passing challenger may
only become a PENDING_USER_APPROVAL proposal.
"""

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class LearningThresholds:
    hypothesis_min_supporting_observations: int = 12
    hypothesis_min_support_ratio: float = 0.65
    promotion_min_backtest_target_dates: int = 40
    promotion_min_scoped_backtest_target_dates: int = 30
    promotion_min_shadow_target_dates: int = 15
    promotion_min_scoped_shadow_target_dates: int = 12
    promotion_min_directional_improvement_pp: float = 5.0
    promotion_min_brier_relative_improvement: float = 0.08
    promotion_max_primary_horizon_deterioration_pp: float = 3.0
    promotion_max_hit_rate_deterioration_pp: float = 3.0
    promotion_max_avg_r_deterioration: float = 0.10
    promotion_max_drawdown_relative_deterioration: float = 0.10


@dataclass(frozen=True)
class PromotionEvidence:
    backtest_target_dates: int
    shadow_target_dates: int
    scoped: bool
    directional_improvement_pp: float
    brier_relative_improvement: float
    primary_horizon_deltas_pp: Mapping[str, float]
    recommendation_hit_rate_delta_pp: float | None = None
    average_r_delta: float | None = None
    drawdown_relative_delta: float | None = None
    changes_execution_logic: bool = False
    data_quality_passed: bool = True
    anti_leakage_passed: bool = True
    concentrated_on_single_day_or_event: bool = False


@dataclass(frozen=True)
class PromotionDecision:
    eligible: bool
    reasons: tuple[str, ...]


def hypothesis_ready(supporting_observations: int, support_ratio: float,
                     thresholds: LearningThresholds = LearningThresholds()) -> bool:
    """Return whether a hypothesis may enter challenger testing, never production."""
    return (
        supporting_observations >= thresholds.hypothesis_min_supporting_observations
        and support_ratio >= thresholds.hypothesis_min_support_ratio
    )


def evaluate_promotion(evidence: PromotionEvidence,
                       thresholds: LearningThresholds = LearningThresholds()) -> PromotionDecision:
    """Evaluate challenger evidence; success means PENDING_USER_APPROVAL only."""
    failures: list[str] = []
    min_backtest = thresholds.promotion_min_scoped_backtest_target_dates if evidence.scoped else thresholds.promotion_min_backtest_target_dates
    min_shadow = thresholds.promotion_min_scoped_shadow_target_dates if evidence.scoped else thresholds.promotion_min_shadow_target_dates

    if evidence.backtest_target_dates < min_backtest:
        failures.append(f"backtest target dates {evidence.backtest_target_dates} < {min_backtest}")
    if evidence.shadow_target_dates < min_shadow:
        failures.append(f"shadow target dates {evidence.shadow_target_dates} < {min_shadow}")
    if not (
        evidence.directional_improvement_pp >= thresholds.promotion_min_directional_improvement_pp
        or evidence.brier_relative_improvement >= thresholds.promotion_min_brier_relative_improvement
    ):
        failures.append("neither directional accuracy nor Brier improvement clears the promotion threshold")

    if not evidence.primary_horizon_deltas_pp:
        failures.append("D+1/D+3/D+5 horizon deltas are missing")
    else:
        for horizon in ("D+1", "D+3", "D+5"):
            if horizon not in evidence.primary_horizon_deltas_pp:
                failures.append(f"{horizon} delta is missing")
                continue
            delta = evidence.primary_horizon_deltas_pp[horizon]
            if delta < -thresholds.promotion_max_primary_horizon_deterioration_pp:
                failures.append(f"{horizon} deteriorates beyond the allowed limit")
        if max(evidence.primary_horizon_deltas_pp.values()) < thresholds.promotion_min_directional_improvement_pp:
            failures.append("no primary D+1/D+3/D+5 horizon improves by the required amount")

    if evidence.changes_execution_logic:
        if evidence.recommendation_hit_rate_delta_pp is None:
            failures.append("recommendation hit-rate delta missing for execution challenger")
        elif evidence.recommendation_hit_rate_delta_pp < -thresholds.promotion_max_hit_rate_deterioration_pp:
            failures.append("recommendation hit rate deteriorates beyond the allowed limit")
        if evidence.average_r_delta is None:
            failures.append("average-R delta missing for execution challenger")
        elif evidence.average_r_delta < -thresholds.promotion_max_avg_r_deterioration:
            failures.append("average R deteriorates beyond the allowed limit")

    if evidence.drawdown_relative_delta is not None and evidence.drawdown_relative_delta > thresholds.promotion_max_drawdown_relative_deterioration:
        failures.append("maximum drawdown deterioration exceeds the allowed relative limit")
    if not evidence.data_quality_passed:
        failures.append("data-quality checks failed")
    if not evidence.anti_leakage_passed:
        failures.append("anti-leakage checks failed")
    if evidence.concentrated_on_single_day_or_event:
        failures.append("result is concentrated on one isolated day/event")

    if failures:
        return PromotionDecision(False, tuple(failures))
    return PromotionDecision(True, (
        "promotion-eligibility gate passed",
        "create proposal with status PENDING_USER_APPROVAL only",
        "production implementation remains prohibited until explicit user approval",
    ))


def day_normalized_mean(values_by_target_date: Mapping[str, Sequence[float]]) -> float | None:
    """Equal-weight target dates so repeated intraday samples cannot dominate learning."""
    daily_means = []
    for values in values_by_target_date.values():
        values = tuple(values)
        if values:
            daily_means.append(sum(values) / len(values))
    return sum(daily_means) / len(daily_means) if daily_means else None
