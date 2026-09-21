from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .watch_identity import (
    canonical_work_key,
    episode_code,
    item_aliases,
    strict_fallback_key,
)


STORE_VERSION = 1
STORE_KEY = "streaming_top_fr.watch_registry"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_newer(candidate: str | None, current: str | None) -> bool:
    if not current:
        return True
    if not candidate:
        return False
    return str(candidate) > str(current)


class CanonicalWatchRegistry:
    """Provider-independent watched state.

    The historical StreamingTopStore remains untouched. This registry only
    bridges equivalent works through IMDb (or a strict title/year/type fallback)
    and stores explicit episode overrides for Streaming Local.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, STORE_KEY
        )
        self.data: dict[str, Any] = {"works": {}, "aliases": {}}

    async def async_load(self) -> None:
        loaded = await self._store.async_load()
        if isinstance(loaded, dict):
            works = loaded.get("works")
            aliases = loaded.get("aliases")
            if isinstance(works, dict):
                self.data["works"] = works
            if isinstance(aliases, dict):
                self.data["aliases"] = aliases

    async def async_save(self) -> None:
        await self._store.async_save(self.data)

    def _resolve_alias(self, alias: str | None) -> str | None:
        value = str(alias or "").strip()
        if not value:
            return None
        seen: set[str] = set()
        while value in self.data["aliases"] and value not in seen:
            seen.add(value)
            value = str(self.data["aliases"].get(value) or value)
        return value or None

    def _merge_rows(self, old_key: str, new_key: str) -> bool:
        if not old_key or not new_key or old_key == new_key:
            return False
        works = self.data["works"]
        old = works.get(old_key)
        if not isinstance(old, dict):
            return False
        new = works.get(new_key)
        if not isinstance(new, dict):
            works[new_key] = deepcopy(old)
        else:
            if _is_newer(old.get("updated_at"), new.get("updated_at")):
                for field in ("watched", "updated_at", "source"):
                    if field in old:
                        new[field] = deepcopy(old[field])
            old_eps = old.get("episodes") or {}
            new_eps = new.setdefault("episodes", {})
            if isinstance(old_eps, dict) and isinstance(new_eps, dict):
                for code, state in old_eps.items():
                    if not isinstance(state, dict):
                        continue
                    current = new_eps.get(code)
                    if not isinstance(current, dict) or _is_newer(
                        state.get("updated_at"), current.get("updated_at")
                    ):
                        new_eps[code] = deepcopy(state)
        works.pop(old_key, None)
        for alias, target in list(self.data["aliases"].items()):
            if target == old_key:
                self.data["aliases"][alias] = new_key
        return True

    def observe_item(self, item: dict[str, Any], extra_alias: str | None = None) -> bool:
        if not isinstance(item, dict):
            return False
        desired = canonical_work_key(item)
        aliases = item_aliases(item, extra_alias)
        if not desired:
            for alias in aliases:
                desired = self._resolve_alias(alias)
                if desired:
                    break
        if not desired:
            return False

        changed = False
        if desired.startswith("imdb:"):
            fallback = strict_fallback_key(item)
            if fallback and fallback != desired:
                fallback_target = self._resolve_alias(fallback) or fallback
                if fallback_target in self.data["works"]:
                    changed |= self._merge_rows(fallback_target, desired)
                if self.data["aliases"].get(fallback) != desired:
                    self.data["aliases"][fallback] = desired
                    changed = True

        # IMDb is the strongest identity. If an alias was previously attached
        # to a fallback/local key, migrate that state to the IMDb work.
        for alias in aliases:
            old_target = self._resolve_alias(alias)
            if old_target and old_target != desired:
                if desired.startswith("imdb:"):
                    changed |= self._merge_rows(old_target, desired)
                elif old_target.startswith("imdb:"):
                    desired = old_target

        for alias in aliases | {desired}:
            if self.data["aliases"].get(alias) != desired:
                self.data["aliases"][alias] = desired
                changed = True
        return changed

    async def async_observe_items(self, items: list[dict[str, Any]]) -> None:
        changed = False
        for item in items or []:
            changed |= self.observe_item(item)
        if changed:
            await self.async_save()

    def key_for_item(
        self, item: dict[str, Any], extra_alias: str | None = None
    ) -> str | None:
        aliases = item_aliases(item, extra_alias)
        for alias in aliases:
            resolved = self._resolve_alias(alias)
            if resolved and resolved in self.data["works"]:
                # IMDb on the incoming item wins over a stale fallback mapping.
                desired = canonical_work_key(item)
                if desired and desired.startswith("imdb:"):
                    return desired
                return resolved
        desired = canonical_work_key(item)
        return self._resolve_alias(desired) or desired

    async def async_set_work(
        self,
        item: dict[str, Any],
        watched: bool,
        *,
        source: str,
        alias_key: str | None = None,
        when: str | None = None,
        only_if_newer: bool = False,
    ) -> str | None:
        changed = self.observe_item(item, alias_key)
        key = self.key_for_item(item, alias_key)
        if not key:
            return None

        works = self.data["works"]
        row = works.setdefault(key, {"episodes": {}})
        timestamp = when or _now_iso()
        if only_if_newer and not _is_newer(timestamp, row.get("updated_at")):
            if changed:
                await self.async_save()
            return key

        row["watched"] = bool(watched)
        row["updated_at"] = timestamp
        row["source"] = str(source)
        row.setdefault("episodes", {})
        await self.async_save()
        return key

    async def async_set_episode(
        self,
        item: dict[str, Any],
        watched: bool,
        *,
        source: str,
        when: str | None = None,
    ) -> str | None:
        changed = self.observe_item(item)
        key = self.key_for_item(item)
        code = episode_code(item)
        if not key or not code:
            if changed:
                await self.async_save()
            return key

        row = self.data["works"].setdefault(key, {"episodes": {}})
        episodes = row.setdefault("episodes", {})
        episodes[code] = {
            "watched": bool(watched),
            "updated_at": when or _now_iso(),
            "source": str(source),
        }
        await self.async_save()
        return key

    async def async_set_episodes(
        self,
        items: list[dict[str, Any]],
        watched: bool,
        *,
        source: str,
    ) -> None:
        timestamp = _now_iso()
        changed = False
        for item in items or []:
            if not isinstance(item, dict):
                continue
            changed |= self.observe_item(item)
            key = self.key_for_item(item)
            code = episode_code(item)
            if not key or not code:
                continue
            row = self.data["works"].setdefault(key, {"episodes": {}})
            episodes = row.setdefault("episodes", {})
            episodes[code] = {
                "watched": bool(watched),
                "updated_at": timestamp,
                "source": str(source),
            }
            changed = True
        if changed:
            await self.async_save()

    def state_for_item(self, item: dict[str, Any]) -> dict[str, Any]:
        key = self.key_for_item(item)
        row = self.data["works"].get(key) if key else None
        if not isinstance(row, dict):
            return {
                "key": key,
                "watched": False,
                "explicit": False,
                "source": None,
            }

        code = episode_code(item)
        episodes = row.get("episodes") or {}
        if code and isinstance(episodes, dict):
            episode_state = episodes.get(code)
            if isinstance(episode_state, dict) and "watched" in episode_state:
                return {
                    "key": key,
                    "watched": bool(episode_state.get("watched")),
                    "explicit": True,
                    "source": episode_state.get("source"),
                    "episode": code,
                }

        if "watched" in row:
            return {
                "key": key,
                "watched": bool(row.get("watched")),
                "explicit": True,
                "source": row.get("source"),
                "episode": code,
            }
        return {
            "key": key,
            "watched": False,
            "explicit": False,
            "source": None,
            "episode": code,
        }

    async def async_import_historical(self, rows: list[dict[str, Any]]) -> None:
        changed = False
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            item = row.get("item")
            if not isinstance(item, dict):
                continue
            alias = str(row.get("key") or item.get("media_key") or "").strip() or None
            changed |= self.observe_item(item, alias)
            key = self.key_for_item(item, alias)
            if not key:
                continue
            work = self.data["works"].setdefault(key, {"episodes": {}})
            when = str(row.get("watched_at") or "")
            if not work.get("updated_at") or _is_newer(when, work.get("updated_at")):
                work["watched"] = True
                work["updated_at"] = when or _now_iso()
                work["source"] = "streaming_legacy"
                work.setdefault("episodes", {})
                changed = True
        if changed:
            await self.async_save()

    def same_work(self, first: dict[str, Any], second: dict[str, Any]) -> bool:
        a = self.key_for_item(first)
        b = self.key_for_item(second)
        if a and b and a == b:
            return True
        # A streaming item may not have its IMDb id yet. In that case allow
        # only the same strict title + year + type fallback.
        fallback_a = strict_fallback_key(first)
        fallback_b = strict_fallback_key(second)
        return bool(fallback_a and fallback_b and fallback_a == fallback_b)

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self.data)
