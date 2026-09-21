from __future__ import annotations

import asyncio
import logging
import shlex
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

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


def add_smb_credentials(smb_uri: str, username: str, password: str) -> str:
    """Return an SMB URI with percent-encoded credentials for VLC only."""
    uri = str(smb_uri or "").strip()
    parsed = urlsplit(uri)
    if parsed.scheme.casefold() != "smb" or not parsed.netloc:
        raise ValueError("URI SMB invalide pour VLC")
    user = str(username or "").strip()
    if not user:
        raise ValueError("Utilisateur SMB manquant")
    # Keep the original host[:port] while removing any pre-existing userinfo.
    host = parsed.netloc.rsplit("@", 1)[-1]
    auth = f"{quote(user, safe='')}:{quote(str(password or ''), safe='')}@{host}"
    return urlunsplit((parsed.scheme, auth, parsed.path, parsed.query, parsed.fragment))


def build_vlc_adb_command(
    smb_uri: str,
    username: str | None = None,
    password: str | None = None,
) -> str:
    """Build a VLC ACTION_VIEW command from a scanner-owned SMB URI."""
    uri = str(smb_uri or "").strip()
    if not uri.lower().startswith("smb://"):
        raise ValueError("URI SMB invalide pour VLC")
    if username is not None:
        uri = add_smb_credentials(uri, username, password or "")
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
    smb_username: str | None = None,
    smb_password: str | None = None,
) -> None:
    """Wake an Android TV target and ask VLC to play a Local SMB item."""
    remote = _require_entity(player, "remote")
    adb_player = _require_entity(player, "adb_player")
    command = build_vlc_adb_command(smb_uri, smb_username, smb_password)

    await _call(hass, "remote", "turn_on", {"entity_id": remote})
    await asyncio.sleep(2)

    # Do not force-stop VLC here. The Local playback mode relies on VLC's
    # remembered SMB authentication context/keystore. Killing the app before
    # every ACTION_VIEW can force a fresh SMB authentication prompt.
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
