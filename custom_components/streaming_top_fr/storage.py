from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORE_KEY, STORE_VERSION


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_payload(item: dict[str, Any]) -> dict[str, Any] | None:
    provider = str(item.get("provider") or "").strip()
    if not provider:
        return None
    return {
        "provider": provider,
        "provider_name": item.get("provider_name"),
        "watch_url": item.get("watch_url"),
        "playback_id": item.get("playback_id"),
        "details_url": item.get("details_url"),
    }


def normalize_work_item(item: Any) -> dict[str, Any]:
    """Normalize a stored title into a provider-agnostic work record.

    Statuses are global by media_key. Provider-specific playback metadata is kept
    under ``providers`` so one work can later be launched from any known service.
    Older 0.5.0 records that only contain ``provider`` are upgraded on read.
    """
    if not isinstance(item, dict):
        return {}

    out = deepcopy(item)
    providers: dict[str, dict[str, Any]] = {}

    raw_providers = out.get("providers")
    if isinstance(raw_providers, dict):
        for provider, value in raw_providers.items():
            if not provider:
                continue
            if isinstance(value, dict):
                entry = deepcopy(value)
            else:
                entry = {}
            entry["provider"] = str(entry.get("provider") or provider)
            providers[str(provider)] = entry

    legacy = _provider_payload(out)
    if legacy:
        provider = legacy["provider"]
        current = providers.get(provider, {})
        merged = {**current}
        for key, value in legacy.items():
            if value not in (None, "") or key not in merged:
                merged[key] = value
        providers[provider] = merged

    out["providers"] = providers
    return out


def merge_work_items(*items: Any) -> dict[str, Any]:
    """Merge title metadata and provider availability without duplicating a work."""
    valid = [normalize_work_item(x) for x in items if isinstance(x, dict)]
    valid = [x for x in valid if x]
    if not valid:
        return {}

    # The newest/incoming item is last and wins for non-empty general metadata.
    out = deepcopy(valid[0])
    provider_map: dict[str, dict[str, Any]] = {}
    imdb_poster = None

    for item in valid:
        if item.get("poster_source") == "imdb" and item.get("poster"):
            imdb_poster = item.get("poster")
        for key, value in item.items():
            if key == "providers":
                continue
            if value not in (None, "", [], {}):
                out[key] = deepcopy(value)
            elif key not in out:
                out[key] = deepcopy(value)

        for provider, pdata in (item.get("providers") or {}).items():
            current = provider_map.get(provider, {})
            merged = {**current}
            if isinstance(pdata, dict):
                for key, value in pdata.items():
                    if value not in (None, "") or key not in merged:
                        merged[key] = deepcopy(value)
            merged["provider"] = str(merged.get("provider") or provider)
            provider_map[provider] = merged

    out["providers"] = provider_map
    # A canonical IMDb poster must never be overwritten by an older stored
    # JustWatch poster when provider/library variants are merged.
    if imdb_poster:
        out["poster"] = imdb_poster
        out["poster_source"] = "imdb"
    return out


class StreamingTopStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
        self.data = {
            "watched": {},
            "watchlist": {},
            "not_interested": {},
            "metadata": {},
        }

    async def async_load(self) -> None:
        loaded = await self._store.async_load()
        if isinstance(loaded, dict):
            self.data["watched"] = loaded.get("watched", {}) or {}
            self.data["watchlist"] = loaded.get("watchlist", {}) or {}
            self.data["not_interested"] = loaded.get("not_interested", {}) or {}
            self.data["metadata"] = loaded.get("metadata", {}) or {}

        # In-memory migration of pre-0.5.1 records. The next status change/cache
        # save persists the normalized provider map without losing user data.
        for bucket in ("watched", "watchlist", "not_interested"):
            for row in self.data[bucket].values():
                if isinstance(row, dict):
                    row["item"] = normalize_work_item(row.get("item") or {})

    async def async_save(self) -> None:
        await self._store.async_save(self.data)

    def watched_keys(self):
        return set(self.data["watched"])

    def watchlist_keys(self):
        return set(self.data["watchlist"])

    def not_interested_keys(self):
        return set(self.data["not_interested"])

    def _items(self, bucket: str, date_field: str):
        rows = list(self.data[bucket].values())
        rows.sort(key=lambda x: x.get(date_field, ""), reverse=True)
        copied = deepcopy(rows)
        for row in copied:
            if isinstance(row, dict):
                row["item"] = normalize_work_item(row.get("item") or {})
        return copied

    def watched_items(self):
        return self._items("watched", "watched_at")

    def watchlist_items(self):
        return self._items("watchlist", "added_at")

    def not_interested_items(self):
        return self._items("not_interested", "hidden_at")

    def _existing_item(self, key: str) -> dict[str, Any]:
        items = []
        for bucket in ("watched", "watchlist", "not_interested"):
            row = self.data[bucket].get(key)
            if isinstance(row, dict) and isinstance(row.get("item"), dict):
                items.append(row["item"])
        return merge_work_items(*items)

    def _merged_for_status(self, key: str, item: Any) -> dict[str, Any]:
        return merge_work_items(self._existing_item(key), item or {"media_key": key})

    async def async_set_watched(self, key, enabled, item=None):
        if enabled:
            merged = self._merged_for_status(key, item)
            self.data["watched"][key] = {
                "key": key,
                "watched_at": _now_iso(),
                "item": merged,
            }
            self.data["watchlist"].pop(key, None)
            self.data["not_interested"].pop(key, None)
        else:
            self.data["watched"].pop(key, None)
        await self.async_save()

    async def async_set_watchlist(self, key, enabled, item=None):
        if enabled:
            merged = self._merged_for_status(key, item)
            self.data["watchlist"][key] = {
                "key": key,
                "added_at": _now_iso(),
                "item": merged,
            }
            # Adding to a watchlist means the title is interesting again.
            self.data["not_interested"].pop(key, None)
        else:
            self.data["watchlist"].pop(key, None)
        await self.async_save()

    async def async_set_not_interested(self, key, enabled, item=None):
        if enabled:
            merged = self._merged_for_status(key, item)
            self.data["not_interested"][key] = {
                "key": key,
                "hidden_at": _now_iso(),
                "item": merged,
            }
            # This is an exclusive disposition bucket.
            self.data["watched"].pop(key, None)
            self.data["watchlist"].pop(key, None)
        else:
            self.data["not_interested"].pop(key, None)
        await self.async_save()

    def merge_existing_item(self, key: str, item: Any) -> bool:
        """Merge refreshed metadata into every stored status row for a work."""
        changed = False
        for bucket in ("watched", "watchlist", "not_interested"):
            row = self.data[bucket].get(key)
            if not isinstance(row, dict) or not isinstance(row.get("item"), dict):
                continue
            merged = merge_work_items(row.get("item") or {}, item or {})
            if merged != row.get("item"):
                row["item"] = merged
                changed = True
        return changed

    def get_metadata(self, key):
        value = self.data["metadata"].get(key)
        return deepcopy(value) if isinstance(value, dict) else None

    def set_metadata(self, key, value):
        self.data["metadata"][key] = deepcopy(value)
