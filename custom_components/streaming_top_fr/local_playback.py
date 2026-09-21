from __future__ import annotations

import asyncio
import logging
import shlex
from typing import Any

from homeassistant.core import HomeAssistant


_LOGGER = logging.getLogger(__name__)
VLC_ANDROID_PACKAGE = "org.videolan.vlc"


def _require_entity(player: dict[str, Any], key: str) -> str:
    value = str(player.get(key) or "").strip()
    if not value:
        raise ValueError(f"Destination incomplète : `{key}` manquant")
    return value


async def _call(
    hass: HomeAssistant,
    domain: str,
    service: str,
    data: dict[str, Any],
) -> None:
    await hass.services.async_call(domain, service, data, blocking=True)


def build_vlc_adb_command(smb_uri: str) -> str:
    """Build a VLC ACTION_VIEW command from a scanner-owned SMB URI."""
    uri = str(smb_uri or "").strip()
    if not uri.lower().startswith("smb://"):
        raise ValueError("URI SMB invalide pour VLC")
    return (
        "am start -W "
        "-a android.intent.action.VIEW "
        f"-d {shlex.quote(uri)} "
        "-t 'video/*' "
        f"-p {VLC_ANDROID_PACKAGE}"
    )


async def async_launch_vlc_local(
    hass: HomeAssistant,
    player: dict[str, Any],
    smb_uri: str,
) -> None:
    """Wake an Android TV target and ask VLC to play a Local SMB item."""
    remote = _require_entity(player, "remote")
    adb_player = _require_entity(player, "adb_player")
    command = build_vlc_adb_command(smb_uri)

    await _call(hass, "remote", "turn_on", {"entity_id": remote})
    await asyncio.sleep(2)

    # Start each requested file from a clean VLC task so an old playback
    # session cannot swallow the new ACTION_VIEW intent.
    await _call(
        hass,
        "androidtv",
        "adb_command",
        {
            "entity_id": adb_player,
            "command": f"am force-stop {VLC_ANDROID_PACKAGE}",
        },
    )
    await asyncio.sleep(1)

    await _call(
        hass,
        "androidtv",
        "adb_command",
        {"entity_id": adb_player, "command": command},
    )


def log_local_launch_failure(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:
        _LOGGER.exception("Streaming Top FR Local VLC playback failed")
