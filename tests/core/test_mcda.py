"""MCDA primitives: normalization, weighted sum, TOPSIS, Pareto filtering."""
from __future__ import annotations

from core.mcda import Criterion, normalize, pareto_front, topsis, weighted_sum

# cost & crowd minimize, weather maximizes.
CRITERIA = [
    Criterion("cost", 0.5, maximize=False),
    Criterion("crowd", 0.3, maximize=False),
    Criterion("weather", 0.2, maximize=True),
]
ROWS = [
    {"cost": 5169.44, "crowd": 30, "weather": 0.8},   # A
    {"cost": 5669.44, "crowd": 10, "weather": 0.6},   # B
    {"cost": 4969.44, "crowd": 50, "weather": 0.9},   # C
]


def test_normalize_higher_is_better():
    # minimize: the lowest raw value normalizes to 1.0
    assert normalize([10, 20, 30], maximize=False) == [1.0, 0.5, 0.0]
    # maximize: the highest raw value normalizes to 1.0
    assert normalize([10, 20, 30], maximize=True) == [0.0, 0.5, 1.0]
    # degenerate column → neutral
    assert normalize([7, 7, 7], maximize=False) == [1.0, 1.0, 1.0]


def test_weighted_sum_ranks_C_over_A_over_B():
    scores = weighted_sum(ROWS, CRITERIA)
    # C wins (best cost + weather), then A, then B.
    assert scores[2] > scores[0] > scores[1]


def test_weights_reweight_the_ranking():
    crowd_heavy = [
        Criterion("cost", 0.1, maximize=False),
        Criterion("crowd", 0.8, maximize=False),
        Criterion("weather", 0.1, maximize=True),
    ]
    scores = weighted_sum(ROWS, crowd_heavy)
    # B has the best crowd, so it now tops the ranking.
    assert scores[1] == max(scores)


def test_topsis_in_unit_interval():
    scores = topsis(ROWS, CRITERIA)
    assert all(0.0 <= s <= 1.0 for s in scores)
    # B is worst-cost and only wins on crowd → farthest from the ideal, ranked last.
    # (TOPSIS need not agree with weighted sum on the winner — it rewards balance.)
    assert scores[1] == min(scores)


def test_pareto_front_excludes_dominated():
    rows = [
        {"cost": 100, "crowd": 10, "weather": 0.9},  # 0 — great everywhere
        {"cost": 200, "crowd": 20, "weather": 0.5},  # 1 — dominated by 0
        {"cost": 90, "crowd": 40, "weather": 0.95},  # 2 — cheaper/better weather, worse crowd
    ]
    front = set(pareto_front(rows, CRITERIA))
    assert 1 not in front          # strictly dominated by row 0
    assert 0 in front and 2 in front
