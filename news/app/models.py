"""Data models for scraped articles."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class Article:
    """A single news item scraped from Onet.pl."""

    title: str
    url: str
    image: Optional[str] = None
    source: Optional[str] = None
    section: Optional[str] = None
    category: Optional[str] = None
    site: str = "onet"  # aggregator source: "onet" | "wp"
    kind: str = "article"
    is_premium: bool = False
    summary: Optional[str] = None
    authors: list = field(default_factory=list)
    reading_time: Optional[str] = None
    hardness: Optional[float] = None
    reactions: int = 0
    published: Optional[str] = None
    breaking: bool = False
    feed_uuid: Optional[str] = None
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
