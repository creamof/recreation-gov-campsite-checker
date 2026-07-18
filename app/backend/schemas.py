"""Pydantic models shared across the API."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    id: str
    name: str
    entity_type: str  # "campground" | "permit" | "recarea" | ...
    parent_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    reservable: Optional[bool] = None


class TimelineStep(BaseModel):
    """A single item on the booking timeline."""

    when: Optional[str] = Field(None, description="ISO date or datetime, or null for do-now items")
    title: str
    detail: str
    kind: Literal["prep", "reminder", "critical", "action", "info", "trip"]
    urgency: Literal["low", "medium", "high"] = "medium"
    verify_url: Optional[str] = None
    # Convenience flags for the frontend.
    is_past: bool = False


class TimelinePlan(BaseModel):
    target: SearchResult
    arrival: date
    departure: date
    strategy: Literal["campground", "lottery", "unknown"]
    headline: str
    rule_name: Optional[str] = None
    competitiveness: Optional[str] = None
    steps: list[TimelineStep]
    verify_url: Optional[str] = None


class TimelineRequest(BaseModel):
    id: str
    name: str
    entity_type: str = "campground"
    parent_name: Optional[str] = None
    arrival: date
    departure: date
    # Optional override so the UI can force a strategy when the API is offline.
    force_strategy: Optional[Literal["campground", "lottery"]] = None
