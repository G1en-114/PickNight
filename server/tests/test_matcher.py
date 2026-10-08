from app.catalog import CATALOG
from app.matcher import (
    apply_concession,
    build_candidates,
    conflict_proposals,
    passes_hard,
    survivors,
)
from app.models import HardConstraints, Preferences, SoftPreferences


def _pref(
    *,
    max_runtime=None,
    excluded_genres=(),
    max_rating=None,
    preferred=(),
    mood=None,
) -> Preferences:
    return Preferences(
        hard=HardConstraints(
            max_runtime_min=max_runtime,
            excluded_genres=list(excluded_genres),
            max_content_rating=max_rating,
        ),
        soft=SoftPreferences(preferred_genres=list(preferred), mood=mood),
    )


def test_hard_filtering_runtime_and_rating():
    hard = HardConstraints(max_runtime_min=100, max_content_rating="PG")
    toy_story = next(m for m in CATALOG if m.id == "m_toy_story")
    knives_out = next(m for m in CATALOG if m.id == "m_knives_out")
    assert passes_hard(toy_story, hard)
    assert not passes_hard(knives_out, hard)  # 130 min, PG-13


def test_survivors_intersection_of_all_members():
    prefs = {
        "m1": _pref(max_runtime=100),
        "m2": _pref(excluded_genres=["Animation", "Family"]),
    }
    alive = survivors(CATALOG, prefs)
    # Toy Story (81min) is animation -> excluded by m2. Duck Soup and
    # Grand Budapest (99 min, Comedy/Drama, R) survive both members.
    assert [m.title for m in alive] == ["Duck Soup", "The Grand Budapest Hotel"]


def test_candidates_ranked_with_reasons():
    prefs = {
        "m1": _pref(preferred=["Animation", "Family"]),
        "m2": _pref(preferred=["Animation"], mood="heartwarming"),
    }
    names = {"m1": "Dad", "m2": "Kid"}
    cands = build_candidates(CATALOG, prefs, names)
    assert 1 <= len(cands) <= 3
    top = cands[0]
    assert top.movie.id == "m_toy_story"
    reason_text = " ".join(r.text for r in top.reasons)
    assert "Animation" in reason_text


def test_conflict_proposal_targets_minimal_relaxation():
    # m1 wants <=90 min; m2 bans Animation/Family/Comedy -> nothing survives.
    prefs = {
        "m1": _pref(max_runtime=90),
        "m2": _pref(excluded_genres=["Animation", "Family", "Comedy"]),
    }
    assert survivors(CATALOG, prefs) == []
    proposals = conflict_proposals(CATALOG, prefs, {"m1": "A", "m2": "B"})
    assert proposals, "expected at least one concession proposal"
    applied = dict(prefs)
    for p in proposals:
        applied[p.member_id] = apply_concession(applied[p.member_id], p.field, p.value)
    assert survivors(CATALOG, applied), "applying proposals must unlock candidates"
    # The ask text must name concrete examples (explainability requirement).
    assert "e.g." in proposals[0].ask_text


def test_no_proposals_when_room_is_fine():
    prefs = {"m1": _pref(), "m2": _pref()}
    assert conflict_proposals(CATALOG, prefs, {"m1": "A", "m2": "B"}) == []
