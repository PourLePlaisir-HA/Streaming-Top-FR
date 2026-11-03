from __future__ import annotations

import asyncio
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]

# Mock homeassistant & dependencies
homeassistant = types.ModuleType("homeassistant")
core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.core"] = core
yaml = types.ModuleType("yaml")
sys.modules["yaml"] = yaml

# Package setup for relative imports
pkg = types.ModuleType("custom_components.streaming_top_fr")
pkg.__path__ = [str(ROOT / "custom_components/streaming_top_fr")]
sys.modules["custom_components"] = types.ModuleType("custom_components")
sys.modules["custom_components.streaming_top_fr"] = pkg

const_path = ROOT / "custom_components/streaming_top_fr/const.py"
spec_const = spec_from_file_location("custom_components.streaming_top_fr.const", const_path)
module_const = module_from_spec(spec_const)
sys.modules["custom_components.streaming_top_fr.const"] = module_const
spec_const.loader.exec_module(module_const)

settings_path = ROOT / "custom_components/streaming_top_fr/settings.py"
spec_settings = spec_from_file_location("custom_components.streaming_top_fr.settings", settings_path)
module_settings = module_from_spec(spec_settings)
sys.modules["custom_components.streaming_top_fr.settings"] = module_settings
spec_settings.loader.exec_module(module_settings)
normalize_settings = module_settings.normalize_settings

playback_path = ROOT / "custom_components/streaming_top_fr/playback.py"
spec_playback = spec_from_file_location("custom_components.streaming_top_fr.playback", playback_path)
module_playback = module_from_spec(spec_playback)
sys.modules["custom_components.streaming_top_fr.playback"] = module_playback
spec_playback.loader.exec_module(module_playback)
async_launch_android_tv = module_playback.async_launch_android_tv

# 1. Test normalize_settings preserves disney_pin
settings_raw = {
    "players": {
        "salon": {
            "name": "Salon",
            "type": "android_tv",
            "media_player": "media_player.salon",
            "remote": "remote.salon",
            "adb_player": "media_player.salon_adb",
            "disney_pin": "1234",
        },
        "etage": {
            "name": "Étage",
            "type": "android_tv",
            "media_player": "media_player.etage",
            "remote": "remote.etage",
            "adb_player": "media_player.etage_adb",
        },
    }
}
normalized = normalize_settings(settings_raw)
assert normalized["players"]["salon"]["disney_pin"] == "1234"
assert normalized["players"]["etage"]["disney_pin"] is None

# 2. Test public_settings sanitization (credential isolation)
public_players = {
    pid: {k: v for k, v in p.items() if k != "disney_pin"}
    if isinstance(p, dict)
    else p
    for pid, p in normalized["players"].items()
}
assert "disney_pin" not in public_players["salon"]
assert "disney_pin" not in public_players["etage"]

# 3. Test Disney+ playback sequence with and without disney_pin
class MockHass:
    def __init__(self):
        self.calls = []
        self.services = self

    async def async_call(self, domain, service, data, blocking=True):
        self.calls.append((domain, service, data))

async def _fake_sleep(s):
    pass

async def test_playback():
    module_playback.asyncio.sleep = _fake_sleep

    # Without PIN
    hass = MockHass()
    player_no_pin = normalized["players"]["etage"]
    await async_launch_android_tv(
        hass,
        provider="disney",
        player=player_no_pin,
        content_id="test-uuid-123",
    )
    commands = [c for c in hass.calls]
    assert commands[0] == ("remote", "turn_on", {"entity_id": "remote.etage"})
    assert commands[1] == ("androidtv", "adb_command", {"entity_id": "media_player.etage_adb", "command": "am force-stop com.disney.disneyplus"})
    assert commands[2] == ("remote", "turn_on", {"entity_id": "remote.etage", "activity": "https://www.disneyplus.com/fr-fr/browse/entity-test-uuid-123"})
    assert commands[3] == ("remote", "send_command", {"entity_id": "remote.etage", "command": "DPAD_CENTER"})
    assert commands[4] == ("remote", "send_command", {"entity_id": "remote.etage", "command": "DPAD_CENTER"})
    assert len(commands) == 5

    # With PIN
    hass_pin = MockHass()
    player_pin = normalized["players"]["salon"]
    await async_launch_android_tv(
        hass_pin,
        provider="disney",
        player=player_pin,
        content_id="test-uuid-123",
    )
    commands_pin = [c for c in hass_pin.calls]
    assert commands_pin[0] == ("remote", "turn_on", {"entity_id": "remote.salon"})
    assert commands_pin[1] == ("androidtv", "adb_command", {"entity_id": "media_player.salon_adb", "command": "am force-stop com.disney.disneyplus"})
    assert commands_pin[2] == ("remote", "turn_on", {"entity_id": "remote.salon", "activity": "https://www.disneyplus.com/fr-fr/browse/entity-test-uuid-123"})
    assert commands_pin[3] == ("remote", "send_command", {"entity_id": "remote.salon", "command": "DPAD_CENTER"})
    assert commands_pin[4] == ("androidtv", "adb_command", {"entity_id": "media_player.salon_adb", "command": "input text 1234"})
    assert commands_pin[5] == ("remote", "send_command", {"entity_id": "remote.salon", "command": "DPAD_CENTER"})
    assert len(commands_pin) == 6

asyncio.run(test_playback())
print("Disney+ PIN playback checks passed.")
