from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "custom_components/streaming_top_fr/local_playback.py"

homeassistant = types.ModuleType("homeassistant")
core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.core"] = core

spec = spec_from_file_location("local_playback_test_module", PATH)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

build = module.build_vlc_adb_command
add_credentials = module.add_smb_credentials

uri = "smb://192.168.0.200/medias/videos/Films/Mon%20Film%20%282024%29.mkv"
cmd = build(uri)
assert "android.intent.action.VIEW" in cmd
assert "org.videolan.vlc" in cmd
assert "video/*" in cmd
assert uri in cmd
assert "am force-stop" not in cmd

# Configured credentials are inserted only into the launch URI and are
# percent-encoded so reserved characters cannot break the SMB URI.
secure_uri = add_credentials(
    uri,
    "media user",
    "p@ss:word/with?chars",
)
assert secure_uri.startswith("smb://media%20user:p%40ss%3Aword%2Fwith%3Fchars@192.168.0.200/")
secure_cmd = build(uri, "media user", "p@ss:word/with?chars")
assert "media%20user:p%40ss%3Aword%2Fwith%3Fchars@" in secure_cmd

# The scanner-owned URI remains credential-free.
assert "@" not in uri.split("://", 1)[1].split("/", 1)[0]

# Reject anything that is not an SMB URI.
try:
    build("https://example.com/video.mkv")
except ValueError:
    pass
else:
    raise AssertionError("Non-SMB URI must be rejected")

source = PATH.read_text(encoding="utf-8")
assert "am force-stop" not in source
assert "remembered SMB authentication context" in source

print("Local VLC playback command checks passed.")


# Frontend regression guard: a VLC backend without visible Local controls must
# never be released again.
card = (ROOT / "custom_components/streaming_top_fr/www/streaming-top-fr-card.js").read_text(encoding="utf-8")
manifest = (ROOT / "custom_components/streaming_top_fr/manifest.json").read_text(encoding="utf-8")
assert "_vlcControls" in card
assert "data-local-play-player" in card
assert 'type:"streaming_top_fr/play_local"' in card
assert 'const STFR_VERSION = "0.9.2-beta.2";' in card
assert '"version": "0.9.2-beta.2"' in manifest

print("Local VLC frontend checks passed.")
