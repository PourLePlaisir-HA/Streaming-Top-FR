from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PROVIDER_NAMES, SUPPORTED_PROVIDERS
from .settings import async_load_settings

_LOGGER = logging.getLogger(__name__)


class StreamingTopCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, netflix, justwatch, store, config_entry):
        update_hours = int(
            config_entry.options.get(
                "update_hours",
                config_entry.data.get("update_hours", 6),
            )
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=update_hours),
        )
        self.netflix = netflix
        self.justwatch = justwatch
        self.store = store
        self.config_entry = config_entry
        self.settings = None

    def _excluded_keys(self):
        # Watchlist deliberately stays discoverable. Only watched / rejected
        # titles consume the sliding discovery window.
        return self.store.watched_keys() | self.store.not_interested_keys()

    async def _build_netflix(self, classification, discovery, excluded):
        """Netflix official Top 10 + JustWatch continuation pool.

        Official #1..#10 keep their official rank. Any continuation title used
        to refill the sliding window has no fabricated Netflix rank.
        """
        official = await self.netflix.async_fetch_france()
        await self.justwatch.async_enrich_netflix(official, classification)

        target = discovery["prefetch_count"]
        max_depth = discovery["max_depth"]
        visible_count = discovery["visible_count"]

        async def one_bucket(bucket, media_type):
            raw_official = list(official.get(bucket, []))
            official_keys = {x.get("media_key") for x in raw_official if x.get("media_key")}
            visible_official = [
                x for x in raw_official if x.get("media_key") not in excluded
            ]
            selected = visible_official[:target]
            if len(selected) >= target:
                return selected

            needed = target - len(selected)
            # Only titles capable of becoming visible immediately need their
            # age metadata resolved now. Reserve titles are enriched when they
            # slide into the visible window on a later refresh.
            extra_visible_needed = max(0, visible_count - len(selected))
            extras = await self.justwatch.async_provider_pool(
                "netflix",
                media_type,
                target_count=needed,
                max_depth=max_depth,
                excluded_keys=set(excluded) | official_keys,
                classification=classification,
                classification_limit=extra_visible_needed,
            )
            for item in extras:
                item["rank"] = None
                item["global_rank"] = None
                item["days_in_top"] = None
                item["source"] = "JustWatch découverte Netflix"
            return (selected + extras)[:target]

        movies_res, tv_res = await asyncio.gather(
            one_bucket("movies", "movie"),
            one_bucket("tv", "tv"),
            return_exceptions=True,
        )

        errors = []
        movies = [] if isinstance(movies_res, Exception) else movies_res
        tv = [] if isinstance(tv_res, Exception) else tv_res
        if isinstance(movies_res, Exception):
            errors.append(f"Films: {movies_res}")
        if isinstance(tv_res, Exception):
            errors.append(f"Séries: {tv_res}")
        if official.get("error"):
            errors.append(str(official.get("error")))

        return {
            "week": official.get("week"),
            "movies": movies,
            "tv": tv,
            "error": " | ".join(errors) if errors else None,
            "source_mode": "netflix_official_plus_justwatch_discovery",
        }

    async def _async_refresh_stored_posters(self):
        """Self-heal posters already saved in global user libraries."""
        by_key = {}
        for getter in (
            self.store.watched_items,
            self.store.watchlist_items,
            self.store.not_interested_items,
        ):
            for row in getter():
                item = (row or {}).get("item") or {}
                key = str(item.get("media_key") or row.get("key") or "").strip()
                if not key or item.get("poster_source") == "imdb":
                    continue
                by_key.setdefault(key, item)

        if not by_key:
            return

        items = list(by_key.values())
        await self.justwatch.async_enrich_imdb_posters(items)
        for key, item in zip(by_key.keys(), items):
            self.store.merge_existing_item(key, item)

    @staticmethod
    def _safe(value, mode):
        if isinstance(value, Exception):
            return {
                "movies": [],
                "tv": [],
                "error": str(value),
                "source_mode": mode,
                "packages": [],
            }
        return value

    async def _async_update_data(self):
        try:
            self.settings = await async_load_settings(self.hass, self.config_entry)
            services = self.settings["services"]
            classification = self.settings["classification"]
            discovery = self.settings["discovery"]
            excluded = self._excluded_keys()

            enabled = [
                provider
                for provider in SUPPORTED_PROVIDERS
                if services.get(provider, False)
            ]

            try:
                await self.justwatch.async_resolve_provider_packages()
            except Exception as err:
                _LOGGER.warning("JustWatch package discovery failed: %s", err)

            tasks = []
            task_ids = []
            for provider in enabled:
                task_ids.append(provider)
                if provider == "netflix":
                    tasks.append(
                        self._build_netflix(classification, discovery, excluded)
                    )
                else:
                    tasks.append(
                        self.justwatch.async_provider(
                            provider,
                            target_count=discovery["prefetch_count"],
                            max_depth=discovery["max_depth"],
                            excluded_keys=excluded,
                            classification=classification,
                            classification_limit=discovery["visible_count"],
                        )
                    )

            results = []
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

            providers = {}
            for provider, result in zip(task_ids, results):
                if provider == "netflix":
                    value = self._safe(
                        result, "netflix_official_plus_justwatch_discovery"
                    )
                    source_label = (
                        "Top 10 officiel Netflix · suite de découverte JustWatch France"
                    )
                else:
                    value = self._safe(result, "justwatch_provider_popular")
                    source_label = (
                        f"Popularité {PROVIDER_NAMES.get(provider, provider)} · JustWatch France"
                    )
                providers[provider] = {
                    "name": PROVIDER_NAMES.get(provider, provider),
                    **value,
                    "source_label": source_label,
                }

            try:
                top_catalog = await self.justwatch.async_top_catalog(
                    enabled,
                    self.settings.get("top_catalog") or {},
                    excluded_keys=excluded,
                )
            except Exception as err:
                _LOGGER.warning("Top Streaming catalogue refresh failed: %s", err)
                top_catalog = {
                    "enabled": bool((self.settings.get("top_catalog") or {}).get("enabled", True)),
                    "decade_order": [],
                    "category_order": ["movies", "animation", "series"],
                    "decades": {},
                    "error": str(err),
                    "source_label": "IMDb note + volume de votes · disponibilité JustWatch France",
                }

            try:
                await self._async_refresh_stored_posters()
            except Exception as err:
                # Library poster migration is best-effort and must never block
                # the normal catalogue refresh.
                _LOGGER.debug("Stored IMDb poster refresh failed: %s", err)

            if self.justwatch.store:
                await self.justwatch.store.async_save()

            return {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "country": "France",
                "settings": self.settings,
                "provider_order": enabled,
                "providers": providers,
                "top_catalog": top_catalog,
            }
        except Exception as err:
            raise UpdateFailed(str(err)) from err
