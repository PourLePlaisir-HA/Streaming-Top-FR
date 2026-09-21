from __future__ import annotations

from typing import Any, Iterable

from .sources import JustWatchClient


def iter_media_items(value: Any) -> Iterable[dict[str, Any]]:
    """Yield work-like dictionaries from coordinator payloads."""
    if isinstance(value, dict):
        if value.get("media_key") and (
            value.get("title")
            or value.get("original_title")
            or value.get("imdb_id")
        ):
            yield value
        for child in value.values():
            yield from iter_media_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_media_items(child)


async def annotate_local_items(
    raw_items: list[dict[str, Any]],
    registry,
    family: dict[str, Any],
    classification: dict[str, Any],
) -> list[dict[str, Any]]:
    """Attach view-only watched/family fields without mutating scanner data."""
    items = [dict(item) for item in raw_items]
    await registry.async_observe_items(items)

    family = family or {}
    classification = classification or {}
    family_enabled = bool(family.get("enabled", True))
    target_age = int(family.get("target_age", 11) or 11)
    allow_unrated = bool(family.get("allow_unrated", False))
    family_buckets = {
        "movies": bool(family.get("movies", True)),
        "series": bool(family.get("series", True)),
        "animation": bool(family.get("animation", True)),
    }

    for item in items:
        state = registry.state_for_item(item)
        item["canonical_watch_key"] = state.get("key")
        item["watch_state"] = bool(state.get("watched", False))
        item["watch_state_explicit"] = bool(state.get("explicit", False))
        item["watch_source"] = state.get("source")

        bucket = str(item.get("bucket") or "")
        allowed_category = family_buckets.get(bucket, False)
        if family_enabled and allowed_category:
            allowed, matched_value, matched_country = (
                JustWatchClient._family_age_allowed(
                    {
                        "fr": item.get("age_fr"),
                        "us": item.get("age_us"),
                    },
                    target_age,
                    allow_unrated,
                    classification,
                )
            )
            item["family_eligible"] = bool(allowed)
            item["family_match_certification"] = matched_value
            item["family_match_country"] = matched_country
        else:
            item["family_eligible"] = False
            item["family_match_certification"] = None
            item["family_match_country"] = None
        item["family_target_age"] = target_age

        if not item.get("media_key"):
            item["media_key"] = item.get("local_id")
        item.pop("local_path", None)

    return items


async def sync_historical_work(store, coordinator, registry, item, watched: bool) -> bool:
    """Mirror a Local work-level action to already-known streaming aliases.

    Episode/season actions never call this helper. The historical engine and its
    filtering remain unchanged; only its existing watched store is updated for
    aliases that are already known with a matching canonical identity.
    """
    candidates = [
        dict(candidate)
        for candidate in iter_media_items(coordinator.data or {})
        if isinstance(candidate, dict)
    ]
    historical_rows = store.watched_items()
    historical_items = [
        dict(row.get("item") or {})
        for row in historical_rows
        if isinstance(row, dict) and isinstance(row.get("item"), dict)
    ]
    await registry.async_observe_items([dict(item), *candidates, *historical_items])

    changed = False
    if watched:
        seen_keys: set[str] = set()
        for candidate in candidates:
            key = str(candidate.get("media_key") or "").strip()
            if not key or key.startswith("local:") or key in seen_keys:
                continue
            if not registry.same_work(item, candidate):
                continue
            seen_keys.add(key)
            if key not in store.watched_keys():
                await store.async_set_watched(key, True, candidate)
                changed = True
    else:
        for row in historical_rows:
            if not isinstance(row, dict) or not isinstance(row.get("item"), dict):
                continue
            if registry.same_work(item, row["item"]):
                key = str(row.get("key") or "").strip()
                if key:
                    await store.async_set_watched(key, False)
                    changed = True

    return changed
