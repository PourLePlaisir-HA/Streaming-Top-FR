from pathlib import Path

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, PLATFORMS, CONF_UPDATE_HOURS, DEFAULT_UPDATE_HOURS
from .storage import StreamingTopStore
from .sources import NetflixOfficialClient, JustWatchClient
from .coordinator import StreamingTopCoordinator
from .playback import SUPPORTED_PLAYBACK_PROVIDERS, async_launch, log_launch_failure
from .local_library import LocalLibraryScanner
from .settings import async_load_legacy_settings, normalize_settings


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})

    # v0.7.1 replaces the legacy text sensor with a Home Assistant-native
    # problem binary sensor. Remove the old registry entry once so users do
    # not keep an unavailable sensor.streaming_top_fr after upgrading.
    registry = er.async_get(hass)
    legacy_status_entity = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_status"
    )
    if legacy_status_entity:
        registry.async_remove(legacy_status_entity)

    # v0.7 migrates the v0.6.x YAML configuration into native ConfigEntry
    # options once, while leaving the YAML file untouched as a rollback path.
    if "settings" not in entry.options or CONF_UPDATE_HOURS not in entry.options:
        options = dict(entry.options)
        if "settings" not in options:
            options["settings"] = normalize_settings(
                await async_load_legacy_settings(hass)
            )
        options.setdefault(
            CONF_UPDATE_HOURS,
            entry.data.get(CONF_UPDATE_HOURS, DEFAULT_UPDATE_HOURS),
        )
        hass.config_entries.async_update_entry(
            entry,
            options=options,
            minor_version=1,
        )

    store = StreamingTopStore(hass)
    await store.async_load()
    session = async_get_clientsession(hass)
    coordinator = StreamingTopCoordinator(
        hass,
        NetflixOfficialClient(session),
        JustWatchClient(session, store),
        store,
        entry,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "store": store,
        "local_library": LocalLibraryScanner(hass),
    }
    await _register_frontend(hass)
    _register_ws(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok


async def _register_frontend(hass):
    if hass.data[DOMAIN].get("_static_registered"):
        return
    path = Path(__file__).parent / "www" / "streaming-top-fr-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/streaming_top_fr/streaming-top-fr-card.js", str(path), False)]
    )
    hass.data[DOMAIN]["_static_registered"] = True


def _entry_data(hass, entry_id=None):
    data = {
        key: value
        for key, value in hass.data.get(DOMAIN, {}).items()
        if not key.startswith("_") and isinstance(value, dict)
    }
    return data.get(entry_id) if entry_id else next(iter(data.values()), None)


def _register_ws(hass):
    if hass.data[DOMAIN].get("_ws_registered"):
        return

    @websocket_api.websocket_command(
        {vol.Required("type"): f"{DOMAIN}/get_data", vol.Optional("entry_id"): str}
    )
    @websocket_api.async_response
    async def get_data(hass, connection, msg):
        data = _entry_data(hass, msg.get("entry_id"))
        if not data:
            connection.send_error(msg["id"], "not_loaded", "Streaming Top FR not loaded")
            return
        payload = dict(data["coordinator"].data or {})
        store = data["store"]
        payload.update(
            {
                "watched_keys": list(store.watched_keys()),
                "watchlist_keys": list(store.watchlist_keys()),
                "not_interested_keys": list(store.not_interested_keys()),
                "watched": store.watched_items(),
                "watchlist": store.watchlist_items(),
                "not_interested": store.not_interested_items(),
                "playback_providers": sorted(SUPPORTED_PLAYBACK_PROVIDERS),
            }
        )
        connection.send_result(msg["id"], payload)

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/set_status",
            vol.Optional("entry_id"): str,
            vol.Required("key"): str,
            vol.Required("status"): vol.In(["watched", "watchlist", "not_interested"]),
            vol.Required("enabled"): bool,
            vol.Optional("item"): dict,
        }
    )
    @websocket_api.async_response
    async def set_status(hass, connection, msg):
        data = _entry_data(hass, msg.get("entry_id"))
        if not data:
            connection.send_error(msg["id"], "not_loaded", "Streaming Top FR not loaded")
            return
        store = data["store"]
        if msg["status"] == "watched":
            await store.async_set_watched(msg["key"], msg["enabled"], msg.get("item"))
        elif msg["status"] == "watchlist":
            await store.async_set_watchlist(msg["key"], msg["enabled"], msg.get("item"))
        else:
            await store.async_set_not_interested(msg["key"], msg["enabled"], msg.get("item"))

        # Watched / not-interested titles leave discovery globally. Refresh the
        # backend immediately so every enabled provider restores prefetch_count.
        if msg["status"] in ("watched", "not_interested"):
            await data["coordinator"].async_request_refresh()

        connection.send_result(
            msg["id"],
            {
                "watched_keys": list(store.watched_keys()),
                "watchlist_keys": list(store.watchlist_keys()),
                "not_interested_keys": list(store.not_interested_keys()),
            },
        )

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/enrich_item",
            vol.Optional("entry_id"): str,
            vol.Required("item"): dict,
        }
    )
    @websocket_api.async_response
    async def enrich_item(hass, connection, msg):
        data = _entry_data(hass, msg.get("entry_id"))
        if not data:
            connection.send_error(msg["id"], "not_loaded", "Streaming Top FR not loaded")
            return
        item = dict(msg.get("item") or {})
        settings = data["coordinator"].settings or (data["coordinator"].data or {}).get("settings") or {}
        classification = settings.get("classification") or {}
        if classification.get("enabled", True):
            object_id = item.get("jw_object_id")
            if object_id is None:
                key = str(item.get("media_key") or "")
                if key.startswith("jw:"):
                    try:
                        object_id = int(key.split(":", 1)[1])
                    except (TypeError, ValueError):
                        object_id = None
            try:
                age = await data["coordinator"].justwatch._async_age_certification(
                    object_id,
                    item.get("media_type"),
                    item.get("details_url"),
                    item.get("title"),
                    item.get("year"),
                )
                if age:
                    item["age_fr"] = age.get("fr")
                    item["age_us"] = age.get("us")
                    if age.get("imdb_id"):
                        item["imdb_id"] = age.get("imdb_id")
                    value, country = data["coordinator"].justwatch.select_age(age, classification)
                    item["age_certification"] = value
                    item["age_country"] = country
            except Exception:
                # Detail enrichment is optional: never prevent opening a popup.
                pass

        try:
            await data["coordinator"].justwatch.async_enrich_imdb_posters([item])
            key = str(item.get("media_key") or "").strip()
            if key:
                data["store"].merge_existing_item(key, item)
            await data["store"].async_save()
        except Exception:
            # IMDb poster enrichment is also optional; keep the JustWatch
            # fallback and never prevent opening a popup.
            pass

        connection.send_result(msg["id"], item)

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/get_family_catalog",
            vol.Optional("entry_id"): str,
            vol.Required("decade"): vol.Coerce(int),
            vol.Required("category"): vol.In(["movies", "animation", "series"]),
        }
    )
    @websocket_api.async_response
    async def get_family_catalog(hass, connection, msg):
        data = _entry_data(hass, msg.get("entry_id"))
        if not data:
            connection.send_error(msg["id"], "not_loaded", "Streaming Top FR not loaded")
            return

        coordinator = data["coordinator"]
        settings = coordinator.settings or (coordinator.data or {}).get("settings") or {}
        family = settings.get("family") or {}
        if not family.get("enabled", True):
            connection.send_error(msg["id"], "family_disabled", "La branche Famille est désactivée")
            return

        decade = str(msg.get("decade"))
        category = str(msg.get("category"))
        top_catalog = settings.get("top_catalog") or {}
        decade_cfg = (top_catalog.get("decades") or {}).get(decade) or {}
        if not decade_cfg.get("enabled", False):
            connection.send_error(msg["id"], "decade_disabled", f"Décennie {decade} désactivée")
            return
        if not decade_cfg.get(category, False) or not family.get(category, True):
            connection.send_error(
                msg["id"], "family_category_disabled", f"Catégorie Famille {category} désactivée"
            )
            return

        services = settings.get("services") or {}
        enabled = [
            provider for provider, is_enabled in services.items() if is_enabled
        ]
        try:
            result = await coordinator.justwatch.async_top_family_category(
                enabled,
                int(decade),
                category,
                int(decade_cfg.get("top_count") or 1),
                family,
                settings.get("classification") or {},
                top_catalog,
                excluded_keys=coordinator._excluded_keys(),
            )
        except Exception as err:
            connection.send_error(msg["id"], "family_catalog_error", str(err))
            return
        connection.send_result(msg["id"], result)

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/get_local_library",
            vol.Optional("entry_id"): str,
            vol.Optional("refresh", default=False): bool,
        }
    )
    @websocket_api.async_response
    async def get_local_library(hass, connection, msg):
        data = _entry_data(hass, msg.get("entry_id"))
        if not data:
            connection.send_error(msg["id"], "not_loaded", "Streaming Top FR not loaded")
            return

        settings = (
            data["coordinator"].settings
            or (data["coordinator"].data or {}).get("settings")
            or {}
        )
        local_settings = settings.get("local_library") or {}
        scanner = data["local_library"]

        if msg.get("refresh") or (
            local_settings.get("enabled", False)
            and not scanner.last_result.items
            and not scanner.last_result.errors
        ):
            result = await scanner.async_scan(local_settings)
        else:
            result = scanner.last_result

        items = [dict(item) for item in result.items]
        for item in items:
            if not item.get("media_key"):
                item["media_key"] = item.get("local_id")
            # The Home Assistant mount path is backend-only. The frontend only
            # needs the relative path and future VLC SMB URI.
            item.pop("local_path", None)

        enriched_count = sum(
            1 for item in items if item.get("metadata_status")
        )
        connection.send_result(
            msg["id"],
            {
                "enabled": bool(local_settings.get("enabled", False)),
                "root_path": local_settings.get("root_path") or "",
                "smb_base_uri": local_settings.get("smb_base_uri") or "",
                "count": len(items),
                "enriched_count": enriched_count,
                "metadata_complete": bool(items) and enriched_count == len(items),
                "items": items,
                "errors": list(result.errors),
            },
        )

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/enrich_local_library",
            vol.Optional("entry_id"): str,
        }
    )
    @websocket_api.async_response
    async def enrich_local_library(hass, connection, msg):
        data = _entry_data(hass, msg.get("entry_id"))
        if not data:
            connection.send_error(msg["id"], "not_loaded", "Streaming Top FR not loaded")
            return

        coordinator = data["coordinator"]
        settings = coordinator.settings or (coordinator.data or {}).get("settings") or {}
        local_settings = settings.get("local_library") or {}
        scanner = data["local_library"]

        if not local_settings.get("enabled", False):
            connection.send_error(
                msg["id"], "local_disabled", "Streaming Local est désactivé"
            )
            return

        result = scanner.last_result
        if not result.items and not result.errors:
            result = await scanner.async_scan(local_settings)

        if result.errors and not result.items:
            connection.send_result(
                msg["id"],
                {
                    "ok": False,
                    "count": 0,
                    "enriched_count": 0,
                    "metadata_complete": False,
                    "items": [],
                    "errors": list(result.errors),
                },
            )
            return

        await coordinator.justwatch.async_enrich_local_items(
            result.items,
            settings.get("classification") or {},
        )

        items = [dict(item) for item in result.items]
        for item in items:
            if not item.get("media_key"):
                item["media_key"] = item.get("local_id")
            item.pop("local_path", None)

        enriched_count = sum(
            1 for item in items if item.get("metadata_status")
        )
        connection.send_result(
            msg["id"],
            {
                "ok": True,
                "enabled": True,
                "count": len(items),
                "enriched_count": enriched_count,
                "metadata_complete": bool(items) and enriched_count == len(items),
                "items": items,
                "errors": list(result.errors),
            },
        )

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/refresh_local_library",
            vol.Optional("entry_id"): str,
        }
    )
    @websocket_api.async_response
    async def refresh_local_library(hass, connection, msg):
        data = _entry_data(hass, msg.get("entry_id"))
        if not data:
            connection.send_error(msg["id"], "not_loaded", "Streaming Top FR not loaded")
            return

        settings = (
            data["coordinator"].settings
            or (data["coordinator"].data or {}).get("settings")
            or {}
        )
        result = await data["local_library"].async_scan(
            settings.get("local_library") or {}
        )
        connection.send_result(
            msg["id"],
            {
                "ok": not result.errors,
                "count": len(result.items),
                "errors": list(result.errors),
            },
        )

    @websocket_api.websocket_command(
        {vol.Required("type"): f"{DOMAIN}/refresh", vol.Optional("entry_id"): str}
    )
    @websocket_api.async_response
    async def refresh(hass, connection, msg):
        data = _entry_data(hass, msg.get("entry_id"))
        if not data:
            connection.send_error(msg["id"], "not_loaded", "Streaming Top FR not loaded")
            return
        await data["coordinator"].async_request_refresh()
        connection.send_result(msg["id"], {"ok": True})

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/play",
            vol.Optional("entry_id"): str,
            vol.Required("provider"): str,
            vol.Required("player"): str,
            vol.Optional("content_id"): str,
            vol.Optional("watch_url"): str,
            vol.Optional("title"): str,
            vol.Optional("original_title"): str,
            vol.Optional("year"): vol.Any(str, int),
            vol.Optional("media_type"): str,
        }
    )
    @websocket_api.async_response
    async def play(hass, connection, msg):
        data = _entry_data(hass, msg.get("entry_id"))
        if not data:
            connection.send_error(msg["id"], "not_loaded", "Streaming Top FR not loaded")
            return

        provider = str(msg.get("provider") or "").strip()
        if provider not in SUPPORTED_PLAYBACK_PROVIDERS:
            connection.send_error(
                msg["id"],
                "unsupported_provider",
                f"Lecture automatisée non validée pour {provider}",
            )
            return

        settings = data["coordinator"].settings or (data["coordinator"].data or {}).get("settings") or {}
        players = settings.get("players") or {}
        player_id = str(msg.get("player") or "").strip()
        player = players.get(player_id)
        if not isinstance(player, dict):
            connection.send_error(
                msg["id"], "unknown_player", f"Destination inconnue : {player_id}"
            )
            return

        if str(player.get("type") or "android_tv").casefold() != "android_tv":
            connection.send_error(
                msg["id"],
                "unsupported_player_type",
                f"Type de destination non pris en charge : {player.get('type')}",
            )
            return
        if not player.get("remote") or not player.get("adb_player"):
            connection.send_error(
                msg["id"],
                "incomplete_player",
                "La destination doit définir remote et adb_player pour les lancements Android TV.",
            )
            return

        content_id = msg.get("content_id")
        watch_url = msg.get("watch_url")

        # Disney+ uses different entity UUIDs for some regional catalogues.
        # Resolve the current French entity at launch time instead of trusting
        # the generic JustWatch deep link. The resolver uses only a short-lived
        # technical cache and revalidates from Disney's French public catalogue.
        if provider == "disney":
            resolved = await data["coordinator"].justwatch.async_resolve_disney_fr(
                msg.get("title"),
                msg.get("original_title"),
                msg.get("year"),
                msg.get("media_type"),
                watch_url,
            )
            if not resolved:
                connection.send_error(
                    msg["id"],
                    "disney_fr_unresolved",
                    "Impossible de résoudre de façon sûre la fiche Disney+ France pour ce titre.",
                )
                return
            content_id = resolved.get("playback_id")
            watch_url = resolved.get("watch_url")

        task = hass.async_create_task(
            async_launch(hass, provider, player, content_id, watch_url),
            f"{DOMAIN}_play_{provider}_{player_id}",
        )
        task.add_done_callback(log_launch_failure)
        connection.send_result(
            msg["id"],
            {
                "ok": True,
                "provider": provider,
                "player": player_id,
                "media_player": player.get("media_player"),
            },
        )

    websocket_api.async_register_command(hass, get_data)
    websocket_api.async_register_command(hass, set_status)
    websocket_api.async_register_command(hass, enrich_item)
    websocket_api.async_register_command(hass, get_family_catalog)
    websocket_api.async_register_command(hass, get_local_library)
    websocket_api.async_register_command(hass, enrich_local_library)
    websocket_api.async_register_command(hass, refresh_local_library)
    websocket_api.async_register_command(hass, refresh)
    websocket_api.async_register_command(hass, play)
    hass.data[DOMAIN]["_ws_registered"] = True
