from __future__ import annotations

import re
import unicodedata
from typing import Any


_IMDB_RE = re.compile(r"^tt\d{7,10}$", re.I)


def normalize_imdb_id(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text if _IMDB_RE.fullmatch(text) else None


def _slug(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _media_type(item: dict[str, Any]) -> str:
    raw = str(item.get("media_type") or "").strip().casefold()
    if raw in {"tv", "show", "series"} or item.get("episodic") is True:
        return "tv"
    return "movie"


def work_title(item: dict[str, Any]) -> str:
    if item.get("episodic") is True:
        return str(
            item.get("franchise_title")
            or item.get("title")
            or item.get("parsed_title")
            or ""
        ).strip()
    return str(
        item.get("title")
        or item.get("original_title")
        or item.get("parsed_title")
        or ""
    ).strip()


def strict_fallback_key(item: dict[str, Any]) -> str | None:
    """Return the strict title/year/type identity, even when IMDb is known."""
    if not isinstance(item, dict):
        return None
    title = work_title(item)
    year = item.get("year")
    try:
        year_i = int(year)
    except (TypeError, ValueError):
        year_i = 0
    title_slug = _slug(title)
    if title_slug and 1800 <= year_i <= 2200:
        return f"fallback:{_media_type(item)}:{year_i}:{title_slug}"
    return None


def canonical_work_key(item: dict[str, Any]) -> str | None:
    """Return a conservative provider-independent identity for one work."""
    if not isinstance(item, dict):
        return None

    imdb_id = normalize_imdb_id(item.get("imdb_id"))
    if imdb_id:
        return f"imdb:{imdb_id}"

    fallback = strict_fallback_key(item)
    if fallback:
        return fallback

    # Unmatched Local items remain trackable without being automatically
    # associated with an unrelated streaming title.
    local_id = str(item.get("local_id") or "").strip()
    if local_id:
        return local_id if local_id.startswith("local:") else f"local:{local_id}"

    media_key = str(item.get("media_key") or "").strip()
    return media_key or None


def item_aliases(item: dict[str, Any], extra: str | None = None) -> set[str]:
    aliases: set[str] = set()
    if isinstance(item, dict):
        for field in ("media_key", "local_id", "canonical_media_key"):
            value = str(item.get(field) or "").strip()
            if value:
                aliases.add(value)
        imdb_id = normalize_imdb_id(item.get("imdb_id"))
        if imdb_id:
            aliases.add(f"imdb:{imdb_id}")
    if extra:
        value = str(extra).strip()
        if value:
            aliases.add(value)
    return aliases


def episode_code(item: dict[str, Any]) -> str | None:
    if not isinstance(item, dict):
        return None
    season = item.get("season")
    episode = item.get("episode")
    if season is None or episode is None:
        return None
    try:
        season_i = int(season)
        episode_i = int(episode)
    except (TypeError, ValueError):
        return None
    if season_i < 0 or episode_i < 0:
        return None
    return f"S{season_i:02d}E{episode_i:02d}"
