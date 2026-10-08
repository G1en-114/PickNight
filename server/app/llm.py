"""Preference analysis layer.

The production implementation sends each member's free text to an LLM and
gets back structured Preferences. The stub below does deterministic keyword
extraction so the full flow works offline and tests stay hermetic. Swapping
in the real model must not change the matcher's contract.
"""

from __future__ import annotations

import re
from typing import Protocol

from .models import HardConstraints, Preferences, SoftPreferences

GENRE_SYNONYMS: dict[str, list[str]] = {
    "Horror": ["scary", "horror", "creepy", "gory"],
    "Thriller": ["thriller", "tense", "suspenseful"],
    "Romance": ["romance", "romantic", "love story", "mushy"],
    "Documentary": ["documentary", "docs"],
    "Drama": ["drama", "heavy", "sad"],
}

PREFERRED_SYNONYMS: dict[str, list[str]] = {
    "Comedy": ["funny", "comedy", "laugh", "silly", "hilarious"],
    "Animation": ["animated", "animation", "cartoon"],
    "Action": ["action", "exciting", "explosive"],
    "Sci-Fi": ["sci-fi", "scifi", "space", "future"],
    "Family": ["family", "kids", "kid", "children", "all-ages"],
    "Adventure": ["adventure", "adventurous"],
    "Mystery": ["mystery", "whodunit", "detective"],
    "Fantasy": ["fantasy", "magical", "magic"],
}

MOOD_TAGS = [
    "heartwarming", "funny", "cozy", "epic", "emotional", "dark",
    "scary", "stylish", "classic", "kid-safe", "twisty", "quirky",
]


class PreferenceAnalyzer(Protocol):
    async def extract(self, free_text: str) -> tuple[HardConstraints, SoftPreferences]:
        """Turn natural language into (hard, soft). Structured form input is
        merged by the caller BEFORE this step; free-text findings must not
        tighten constraints the member did not type."""
        ...


class StubAnalyzer:
    async def extract(self, free_text: str) -> tuple[HardConstraints, SoftPreferences]:
        text = free_text.lower()
        hard = HardConstraints()
        soft = SoftPreferences()

        for genre, words in GENRE_SYNONYMS.items():
            if any(re.search(rf"\b{w}\b", text) for w in words):
                if re.search(rf"\b(no|not|avoid|hate|without)\s+\w*(\s+\w+)?\b", text) or any(
                    re.search(rf"\bno\s+{w}s?\b", text) for w in words
                ):
                    hard.excluded_genres.append(genre)

        for genre, words in PREFERRED_SYNONYMS.items():
            if any(re.search(rf"\b{w}s?\b", text) for w in words):
                soft.preferred_genres.append(genre)

        if re.search(r"\bshort\b|\bunder (90|100)\b|\bquick\b", text):
            hard.max_runtime_min = 100
        if re.search(r"\bkids?\b|\bchildren\b|\blittle one", text):
            hard.max_content_rating = "PG"
        if re.search(r"\bclassic\b|\bold(?!.*new)\b", text):
            soft.era = "classic"
        if re.search(r"\bsomething new\b|\brecent\b|\bnew release", text):
            soft.era = "new"

        for tag in MOOD_TAGS:
            if re.search(rf"\b{tag}\b", text):
                soft.mood = tag
                break

        # Dedupe, keep order.
        hard.excluded_genres = list(dict.fromkeys(hard.excluded_genres))
        soft.preferred_genres = list(dict.fromkeys(soft.preferred_genres))
        return hard, soft


def merge_preferences(
    structured: Preferences, free_text_hard: HardConstraints, free_text_soft: SoftPreferences
) -> Preferences:
    """Merge form input with analyzer output. Form (explicit) values win;
    analyzer may only ADD preferences, and never tightens a constraint the
    member left open."""
    merged = structured.model_copy(deep=True)
    for g in free_text_hard.excluded_genres:
        if g not in merged.hard.excluded_genres:
            merged.hard.excluded_genres.append(g)
    if merged.hard.max_runtime_min is None:
        merged.hard.max_runtime_min = free_text_hard.max_runtime_min
    if merged.hard.max_content_rating is None:
        merged.hard.max_content_rating = free_text_hard.max_content_rating
    for g in free_text_soft.preferred_genres:
        if g not in merged.soft.preferred_genres:
            merged.soft.preferred_genres.append(g)
    if merged.soft.mood is None:
        merged.soft.mood = free_text_soft.mood
    if merged.soft.era is None:
        merged.soft.era = free_text_soft.era
    return merged


def get_analyzer() -> PreferenceAnalyzer:
    # TODO: pick by env (PICKNIGHT_ANALYZER=stub|llm) once the LLM adapter lands.
    return StubAnalyzer()
