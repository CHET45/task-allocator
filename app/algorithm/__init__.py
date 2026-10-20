"""Algorithm module: filtering -> weighted scoring -> optimisation."""
from .contract import RecommendRequest, RecommendResponse, TaskResult
from .filtering import filter_candidates
from .optimization import optimal_assignment
from .scoring import score_candidate


def recommend(req: RecommendRequest) -> RecommendResponse:
    results: list[TaskResult] = []
    pair_scores: dict[tuple[str, str], float] = {}

    for task in req.tasks:
        eligible, excluded = filter_candidates(task, req.candidates)
        scored = [score_candidate(task, c, req.weights, req.workload_limit) for c in eligible]
        scored.sort(key=lambda s: (-s.score, s.name))
        for s in scored:
            pair_scores[(task.key, s.account_id)] = s.score
        results.append(TaskResult(
            key=task.key,
            status="ok" if scored else "no_candidates",
            recommended=None,
            candidates=scored[: req.top_n],
            excluded=excluded,
        ))

    assignment, total = optimal_assignment(
        req.tasks,
        [c.account_id for c in req.candidates],
        pair_scores,
        capacity=req.max_new_per_candidate,
    )
    for r in results:
        r.recommended = assignment[r.key]

    return RecommendResponse(results=results, assignment=assignment, total_score=total)


__all__ = ["recommend", "RecommendRequest", "RecommendResponse"]
