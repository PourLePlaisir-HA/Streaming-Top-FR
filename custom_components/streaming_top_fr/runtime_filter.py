from __future__ import annotations

import asyncio
import re
import unicodedata
from typing import Any

from .const import JUSTWATCH_GRAPHQL
from .sources import UA


RUNTIME_CACHE_PREFIX = "runtime-v1"


def _token(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def _request_key(item: dict[str, Any]) -> str:
    return str(
        item.get("runtime_key")
        or item.get("local_id")
        or item.get("media_key")
        or ""
    ).strip()


def _cache_identity(item: dict[str, Any]) -> str:
    imdb_id = str(item.get("imdb_id") or "").strip().casefold()
    if imdb_id:
        return f"imdb:{imdb_id}"
    canonical = str(
        item.get("canonical_media_key") or item.get("media_key") or ""
    ).strip()
    if canonical:
        return canonical
    title = _token(item.get("title") or item.get("parsed_title"))
    year = str(item.get("year") or "")
    return f"title:{year}:{title}" if title else ""


class RuntimeMetadataClient:
    """Optional runtime lookup isolated from the validated catalogue engines."""

    QUERY = r"""
    query RuntimeLookup(
      $country: Country!,
      $language: Language!,
      $filter: TitleFilter!,
      $first: Int!
    ) {
      popularTitles(
        country: $country,
        filter: $filter,
        first: $first,
        sortBy: POPULAR
      ) {
        edges {
          node {
            objectId
            objectType
            ... on Movie {
              content(country: $country, language: $language) {
                title
                originalReleaseYear
                runtime
                externalIds { imdbId }
              }
            }
          }
        }
      }
    }
    """

    def __init__(self, session, store) -> None:
        self.session = session
        self.store = store
        self._sem = asyncio.Semaphore(4)

    @staticmethod
    def _runtime_value(value: Any) -> int | None:
        try:
            runtime = int(value)
        except (TypeError, ValueError):
            return None
        return runtime if runtime > 0 else None

    def _cached_runtime(self, item: dict[str, Any]) -> int | None:
        direct = self._runtime_value(item.get("runtime"))
        if direct is not None:
            return direct
        identity = _cache_identity(item)
        if not identity:
            return None
        cached = self.store.get_metadata(f"{RUNTIME_CACHE_PREFIX}:{identity}")
        if not isinstance(cached, dict):
            return None
        return self._runtime_value(cached.get("runtime"))

    async def _lookup_runtime(self, item: dict[str, Any]) -> int | None:
        direct = self._cached_runtime(item)
        if direct is not None:
            return direct

        title = str(
            item.get("title")
            or item.get("parsed_title")
            or item.get("original_title")
            or ""
        ).strip()
        if not title:
            return None

        target_imdb = str(item.get("imdb_id") or "").strip().casefold()
        try:
            target_year = int(item.get("year"))
        except (TypeError, ValueError):
            target_year = None
        target_title = _token(title)

        payload = {
            "operationName": "RuntimeLookup",
            "variables": {
                "country": "FR",
                "language": "fr",
                "first": 8,
                "filter": {
                    "searchQuery": title,
                    "objectTypes": ["MOVIE"],
                },
            },
            "query": self.QUERY,
        }

        try:
            async with self._sem:
                async with self.session.post(
                    JUSTWATCH_GRAPHQL,
                    json=payload,
                    headers={
                        "User-Agent": UA,
                        "Origin": "https://www.justwatch.com",
                        "Referer": "https://www.justwatch.com/fr/",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    timeout=25,
                ) as response:
                    if response.status >= 400:
                        return None
                    body = await response.json()
        except Exception:
            return None

        if body.get("errors"):
            return None

        edges = (
            ((body.get("data") or {}).get("popularTitles") or {}).get("edges")
            or []
        )
        candidates: list[dict[str, Any]] = []
        for edge in edges:
            node = (edge or {}).get("node") or {}
            if str(node.get("objectType") or "").upper() != "MOVIE":
                continue
            data = node.get("content") or {}
            runtime = self._runtime_value(data.get("runtime"))
            if runtime is None:
                continue
            ext = data.get("externalIds") or {}
            candidates.append(
                {
                    "runtime": runtime,
                    "imdb_id": str(ext.get("imdbId") or "").strip().casefold(),
                    "title": str(data.get("title") or "").strip(),
                    "year": data.get("originalReleaseYear"),
                }
            )

        selected = None
        if target_imdb:
            selected = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.get("imdb_id") == target_imdb
                ),
                None,
            )

        if selected is None:
            strict = []
            for candidate in candidates:
                if _token(candidate.get("title")) != target_title:
                    continue
                try:
                    candidate_year = int(candidate.get("year"))
                except (TypeError, ValueError):
                    candidate_year = None
                if target_year is not None and candidate_year != target_year:
                    continue
                strict.append(candidate)
            if len(strict) == 1:
                selected = strict[0]

        if selected is None:
            return None

        runtime = self._runtime_value(selected.get("runtime"))
        identity = _cache_identity(item)
        if runtime is not None and identity:
            self.store.set_metadata(
                f"{RUNTIME_CACHE_PREFIX}:{identity}",
                {"runtime": runtime},
            )
        return runtime

    async def async_resolve_many(
        self, items: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Return request-key -> runtime minutes for movie items only."""
        candidates = [
            dict(item)
            for item in (items or [])
            if isinstance(item, dict)
            and str(item.get("media_type") or "").casefold() in {"movie", "film"}
            and _request_key(item)
        ]
        if not candidates:
            return {}

        results = await asyncio.gather(
            *(self._lookup_runtime(item) for item in candidates),
            return_exceptions=True,
        )
        output: dict[str, int] = {}
        changed = False
        for item, runtime in zip(candidates, results):
            if isinstance(runtime, Exception):
                continue
            value = self._runtime_value(runtime)
            if value is None:
                continue
            output[_request_key(item)] = value
            if item.get("runtime") is None:
                changed = True

        if changed:
            await self.store.async_save()
        return output
