"""Automatic Lovelace resource management for Streaming Top FR."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from homeassistant.components import frontend
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

CARD_RESOURCE_PATH = "/streaming_top_fr/streaming-top-fr-card.js"
CARD_RESOURCE_TYPE = "module"


def _resource_path(url: str | None) -> str:
    """Return the path part of a Lovelace resource URL."""
    try:
        return urlsplit(str(url or "")).path.rstrip("/")
    except ValueError:
        return ""


def _is_streaming_top_resource(item: dict) -> bool:
    """Return True for any historical/current Streaming Top FR resource URL."""
    return _resource_path(item.get("url")) == CARD_RESOURCE_PATH


async def _async_upsert_storage_resource(resources, target_url: str) -> bool:
    """Create/update the resource and collapse duplicates in storage mode."""
    # Explicitly trigger the ResourceStorageCollection lazy-load guard before
    # inspecting its items. This also makes the helper safe across HA versions
    # where the collection may not have been read from disk yet.
    await resources.async_get_info()

    matches = [
        item
        for item in resources.async_items()
        if isinstance(item, dict) and _is_streaming_top_resource(item)
    ]

    changed = False
    if not matches:
        await resources.async_create_item(
            {"res_type": CARD_RESOURCE_TYPE, "url": target_url}
        )
        _LOGGER.info("Registered Lovelace resource %s", target_url)
        return True

    primary = matches[0]
    updates = {}
    if str(primary.get("url") or "") != target_url:
        updates["url"] = target_url
    if str(primary.get("type") or "").casefold() != CARD_RESOURCE_TYPE:
        updates["res_type"] = CARD_RESOURCE_TYPE

    if updates:
        await resources.async_update_item(primary["id"], updates)
        changed = True
        _LOGGER.info("Updated Lovelace resource to %s", target_url)

    # Older releases required a manual resource. If a user accidentally has
    # more than one matching entry, retain the first one and remove only exact
    # Streaming Top FR duplicates.
    for duplicate in matches[1:]:
        resource_id = duplicate.get("id")
        if resource_id:
            await resources.async_delete_item(resource_id)
            changed = True
            _LOGGER.info("Removed duplicate Streaming Top FR Lovelace resource")

    return changed


async def async_register_lovelace_resource(hass: HomeAssistant) -> bool:
    """Ensure the bundled card is available without manual resource setup."""
    integration = await async_get_integration(hass, DOMAIN)
    version = str(integration.version or "0")
    target_url = f"{CARD_RESOURCE_PATH}?v={version}"

    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None:
        _LOGGER.warning(
            "Lovelace is not loaded; cannot register %s automatically",
            target_url,
        )
        return False

    resources = lovelace.resources

    if isinstance(resources, ResourceStorageCollection):
        return await _async_upsert_storage_resource(resources, target_url)

    # YAML resources cannot be persisted by an integration. Avoid loading the
    # same card twice when the user already declared it. Otherwise register it
    # for the current frontend session so YAML users do not need a second
    # manual step just to use the bundled cards.
    await resources.async_get_info()
    if any(
        isinstance(item, dict) and _is_streaming_top_resource(item)
        for item in resources.async_items()
    ):
        return False

    frontend.add_extra_js_url(hass, target_url)
    _LOGGER.info(
        "Loaded %s as an extra JS module because Lovelace resources are YAML-managed",
        target_url,
    )
    return True


async def async_remove_lovelace_resource(hass: HomeAssistant) -> bool:
    """Remove the managed resource when the integration entry is deleted."""
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None:
        return False

    resources = lovelace.resources
    if not isinstance(resources, ResourceStorageCollection):
        return False

    await resources.async_get_info()
    matches = [
        item
        for item in resources.async_items()
        if isinstance(item, dict) and _is_streaming_top_resource(item)
    ]

    changed = False
    for item in matches:
        resource_id = item.get("id")
        if resource_id:
            await resources.async_delete_item(resource_id)
            changed = True

    if changed:
        _LOGGER.info("Removed Streaming Top FR Lovelace resource")
    return changed
