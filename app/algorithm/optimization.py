"""Assignment optimisation with the Hungarian algorithm (SciPy linear_sum_assignment)."""
import numpy as np
from scipy.optimize import linear_sum_assignment

from .contract import PRIORITY_WEIGHT, TaskIn

INELIGIBLE = 1e6


def optimal_assignment(
    tasks: list[TaskIn],
    account_ids: list[str],
    scores: dict[tuple[str, str], float],
    capacity: int = 1,
) -> tuple[dict[str, str | None], float]:
    """Return {task key: account id or None} maximising the priority-weighted total score.

    `scores` holds (task key, account id) -> score only for eligible pairs. Each candidate is
    repeated `capacity` times as a column so one person can take several new tasks in batch mode.
    Higher-priority tasks weigh more, so they win when two tasks compete for the same person.
    """
    result: dict[str, str | None] = {t.key: None for t in tasks}
    if not tasks or not account_ids:
        return result, 0.0

    columns = [acc for acc in account_ids for _ in range(capacity)]
    cost = np.full((len(tasks), len(columns)), INELIGIBLE)
    for i, task in enumerate(tasks):
        w = PRIORITY_WEIGHT[task.priority]
        for j, acc in enumerate(columns):
            s = scores.get((task.key, acc))
            if s is not None:
                cost[i, j] = -w * s

    rows, cols = linear_sum_assignment(cost)
    total = 0.0
    for i, j in zip(rows, cols):
        if cost[i, j] < INELIGIBLE:
            key, acc = tasks[i].key, columns[j]
            result[key] = acc
            total += scores[(key, acc)]
    return result, round(total, 1)
