"""Shared domain models for PickNight.

The server is the single source of truth for room state. Clients receive
role-scoped snapshots: the TV gets the public view, each phone gets the
public view plus its own private fields (preferences, pending concession
requests, vote). See docs/protocol.md.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

RATING_ORDER = {"G": 0, "PG": 1, "PG-13": 2, "R": 3}


class Phase(str, Enum):
    LOBBY = "lobby"
    PREFERENCES = "preferences"
    MATCHING = "matching"
    NEGOTIATION = "negotiation"
    VOTING = "voting"
    RESULT = "result"


class HardConstraints(BaseModel):
    """Bottom lines. Never relaxed automatically - only by the member's own
    confirmed concession."""

    max_runtime_min: Optional[int] = None
    excluded_genres: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    max_content_rating: Optional[str] = None  # "G" | "PG" | "PG-13" | "R"


class SoftPreferences(BaseModel):
    """Nice-to-haves. Used for ranking and explanation, never for vetoing."""

    preferred_genres: list[str] = Field(default_factory=list)
    mood: Optional[str] = None  # free text, matched against movie tags
    era: Optional[str] = None  # "new" | "classic"


class Preferences(BaseModel):
    hard: HardConstraints
    soft: SoftPreferences
    free_text: str = ""


class Movie(BaseModel):
    id: str
    title: str
    year: int
    runtime_min: int
    genres: list[str]
    tags: list[str]  # mood keywords: "heartwarming", "thriller", "kid-safe"...
    content_rating: str
    providers: list[str]
    logline: str

    @property
    def rating_index(self) -> int:
        return RATING_ORDER.get(self.content_rating, 3)


class CandidateReason(BaseModel):
    for_member: Optional[str] = None  # None = applies to the whole group
    text: str


class Candidate(BaseModel):
    movie: Movie
    score: float
    reasons: list[CandidateReason]


class ConcessionRequest(BaseModel):
    id: str
    member_id: str
    ask_text: str
    relax_summary: str  # e.g. "max runtime 90 -> 140 min"
    deadline_ms: Optional[int] = None  # epoch ms when auto-declined


class TallyEntry(BaseModel):
    candidate_id: str
    title: str
    votes: int


class Result(BaseModel):
    no_pick: bool = False
    winner: Optional[Candidate] = None
    tally: list[TallyEntry] = Field(default_factory=list)
    explanation: str = ""
