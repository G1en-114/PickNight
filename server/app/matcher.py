"""Deterministic candidate matching and conflict analysis.

Division of labor (a core project principle): the LLM extracts preferences,
asks questions and explains; THIS module decides what is watchable, ranks
candidates, detects conflicts and computes minimal concessions. Facts and
hard constraints are enforced by code, not by model output.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from .models import (
    Candidate,
    CandidateReason,
    HardConstraints,
    Movie,
    Preferences,
    RATING_ORDER,
)

TOP_N = 3
ERA_CLASSIC_BEFORE_YEAR = 2000


def passes_hard(movie: Movie, hard: HardConstraints) -> bool:
    if hard.max_runtime_min is not None and movie.runtime_min > hard.max_runtime_min:
        return False
    if (
        hard.max_content_rating is not None
        and RATING_ORDER.get(movie.content_rating, 3)
        > RATING_ORDER.get(hard.max_content_rating, 3)
    ):
        return False
    movie_genres = set(movie.genres)
    if any(g in movie_genres for g in hard.excluded_genres):
        return False
    movie_tokens = {t.lower() for t in movie.tags} | {g.lower() for g in movie.genres}
    if any(kw.lower() in movie_tokens for kw in hard.excluded_keywords):
        return False
    return True


def survivors(catalog: list[Movie], prefs: dict[str, Preferences]) -> list[Movie]:
    """Movies that pass EVERY member's hard constraints."""
    return [
        m for m in catalog if all(passes_hard(m, p.hard) for p in prefs.values())
    ]


def soft_score(movie: Movie, pref: Preferences) -> float:
    score = 0.0
    genres = set(movie.genres)
    score += 2.0 * len(genres & set(pref.soft.preferred_genres))
    if pref.soft.mood:
        tokens = {t.lower() for t in movie.tags}
        if pref.soft.mood.lower() in tokens:
            score += 1.0
    if pref.soft.era == "classic" and movie.year < ERA_CLASSIC_BEFORE_YEAR:
        score += 0.5
    if pref.soft.era == "new" and movie.year >= ERA_CLASSIC_BEFORE_YEAR:
        score += 0.5
    return score


def build_candidates(
    catalog: list[Movie], prefs: dict[str, Preferences], names: dict[str, str]
) -> list[Candidate]:
    """Rank survivors by group soft-preference score, with per-member reasons."""
    alive = survivors(catalog, prefs)
    scored: list[tuple[float, Movie]] = []
    for movie in alive:
        total = 0.0
        for p in prefs.values():
            total += soft_score(movie, p)
        # Secondary sort keys baked into the tuple: shorter runtime first.
        scored.append((total, movie))
    scored.sort(key=lambda t: (-t[0], t[1].runtime_min, t[1].title))

    candidates: list[Candidate] = []
    for total, movie in scored[:TOP_N]:
        reasons: list[CandidateReason] = [
            CandidateReason(
                text=f"Clears everyone's bottom lines ({movie.runtime_min} min, {movie.content_rating})."
            )
        ]
        for member_id, p in prefs.items():
            hits = set(movie.genres) & set(p.soft.preferred_genres)
            bits = []
            if hits:
                bits.append("matches " + "/".join(sorted(hits)))
            if p.soft.mood and p.soft.mood.lower() in {t.lower() for t in movie.tags}:
                bits.append(f"feels {p.soft.mood}")
            if bits:
                reasons.append(
                    CandidateReason(for_member=names.get(member_id), text="; ".join(bits))
                )
        if len(reasons) == 1:
            reasons.append(CandidateReason(text="A neutral crowd-pleaser for tonight."))
        candidates.append(Candidate(movie=movie, score=round(total, 2), reasons=reasons))
    return candidates


@dataclass
class ConcessionProposal:
    """A minimal, targeted relaxation ONE member could make to unlock candidates."""

    member_id: str
    field: str  # "max_runtime_min" | "max_content_rating" | "excluded_genres" | "excluded_keywords"
    current: str
    suggested: str
    value: object  # new value for the field
    unlocked: list[Movie]
    ask_text: str


def _relaxation_options(hard: HardConstraints) -> list[tuple[str, str, str, object]]:
    """(field, current_display, suggested_display, new_value) options for one member."""
    options: list[tuple[str, str, str, object]] = []
    if hard.max_runtime_min is not None:
        for step in (140, 170, 1000):
            if step > hard.max_runtime_min:
                label = f"up to {step} min" if step < 1000 else "any length"
                options.append(
                    (
                        "max_runtime_min",
                        f"max {hard.max_runtime_min} min",
                        label,
                        None if step >= 1000 else step,
                    )
                )
                break
    if hard.max_content_rating is not None:
        order = ["G", "PG", "PG-13", "R"]
        idx = RATING_ORDER.get(hard.max_content_rating, 0)
        if idx + 1 < len(order):
            options.append(
                (
                    "max_content_rating",
                    f"rating up to {hard.max_content_rating}",
                    f"rating up to {order[idx + 1]}",
                    order[idx + 1],
                )
            )
    for g in hard.excluded_genres:
        remaining = [x for x in hard.excluded_genres if x != g]
        options.append(
            (
                "excluded_genres",
                f"no {g}",
                f"{g} is OK",
                remaining,
            )
        )
    for kw in hard.excluded_keywords:
        remaining = [x for x in hard.excluded_keywords if x != kw]
        options.append(
            (
                "excluded_keywords",
                f"no '{kw}' movies",
                f"'{kw}' is OK",
                remaining,
            )
        )
    return options


def _apply(member_pref: Preferences, field: str, value: object) -> Preferences:
    new_pref = copy.deepcopy(member_pref)
    setattr(new_pref.hard, field, value)
    return new_pref


def conflict_proposals(
    catalog: list[Movie],
    prefs: dict[str, Preferences],
    names: dict[str, str],
    max_proposals: int = 2,
) -> list[ConcessionProposal]:
    """When nothing survives, find the smallest set of single-member relaxations
    (at most one per member) that unlocks at least one candidate.

    Greedy: repeatedly pick the relaxation that unlocks the most movies, then
    search again allowing one more member to bend. Hard constraints are only
    ever changed on the member's copy after their explicit confirmation.
    """
    if survivors(catalog, prefs):
        return []

    proposals: list[ConcessionProposal] = []
    working = {mid: copy.deepcopy(p) for mid, p in prefs.items()}

    for _ in range(max_proposals):
        best: ConcessionProposal | None = None
        for member_id, pref in working.items():
            # Members already featured in a proposal don't get a second one.
            if any(p.member_id == member_id for p in proposals):
                continue
            for field, current, suggested, value in _relaxation_options(pref.hard):
                trial = dict(working)
                trial[member_id] = _apply(pref, field, value)
                unlocked = survivors(catalog, trial)
                if unlocked and (
                    best is None or len(unlocked) > len(best.unlocked)
                ):
                    titles = ", ".join(m.title for m in unlocked[:3])
                    best = ConcessionProposal(
                        member_id=member_id,
                        field=field,
                        current=current,
                        suggested=suggested,
                        value=value,
                        unlocked=unlocked,
                        ask_text=(
                            f"With everyone's bottom lines, no movie works for the group. "
                            f"If you allow {suggested} (instead of {current}), "
                            f"{len(unlocked)} movies become possible - e.g. {titles}. "
                            f"Totally your call: decline and we'll try someone else."
                        ),
                    )
        if best is None:
            break
        proposals.append(best)
        working[best.member_id] = _apply(
            working[best.member_id], best.field, best.value
        )
        if survivors(catalog, working):
            break

    return proposals


def apply_concession(pref: Preferences, field: str, value: object) -> Preferences:
    """Return the member's preferences with a confirmed concession applied."""
    return _apply(pref, field, value)
