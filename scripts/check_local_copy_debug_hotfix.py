from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
INIT_PATH = ROOT / "custom_components/streaming_top_fr/__init__.py"
source = INIT_PATH.read_text(encoding="utf-8")
tree = ast.parse(source)

target = None
for node in ast.walk(tree):
    if isinstance(node, ast.AsyncFunctionDef) and node.name == "find_local_copy":
        target = node
        break

assert target is not None, "find_local_copy handler not found"

# Compile only the handler body, without Home Assistant decorators/imports.
target.decorator_list = []
module = ast.Module(body=[target], type_ignores=[])
ast.fix_missing_locations(module)

MATRIX_LOCAL = {
    "local_id": "local:matrix",
    "title": "Matrix",
    "year": 1999,
    "imdb_id": "tt0133093",
    "canonical_media_key": "imdb:tt0133093",
}
INDEX = {
    "schema": "local-canonical-index-v1",
    "by_imdb": {"tt0133093": MATRIX_LOCAL},
    "by_canonical": {},
    "by_title_year": {},
}


class FakeStore:
    def get_metadata(self, key):
        return INDEX


class FakeConnection:
    def __init__(self):
        self.result = None
        self.error = None

    def send_result(self, msg_id, payload):
        self.result = payload

    def send_error(self, msg_id, code, message):
        self.error = (code, message)


class FakeLogger:
    def debug(self, *args, **kwargs):
        return None


def local_match_token(value):
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def find_match(item, index):
    imdb_id = str(item.get("imdb_id") or "").strip().casefold()
    return (index.get("by_imdb") or {}).get(imdb_id)


runtime = {
    "_PACKAGE_LOGGER": FakeLogger(),
    "_local_playback_payload": lambda settings: {"enabled": True, "players": []},
    "_local_match_token": local_match_token,
    "_find_local_index_match": find_match,
}
exec(compile(module, str(INIT_PATH), "exec"), runtime)
handler = runtime["find_local_copy"]


async def run_case(debug_enabled: bool):
    settings = {
        "debug": {"enabled": debug_enabled},
        "local_library": {"enabled": True},
    }
    data = {
        "coordinator": SimpleNamespace(settings=settings, data={"settings": settings}),
        "store": FakeStore(),
    }
    runtime["_entry_data"] = lambda hass, entry_id=None: data

    connection = FakeConnection()
    await handler(
        None,
        connection,
        {
            "id": 1,
            "item": {
                "media_type": "movie",
                "media_key": "jw:10",
                "imdb_id": "tt0133093",
                "title": "Matrix",
                "original_title": None,
                "subtitle": None,
                "year": 1999,
            },
        },
    )

    assert connection.error is None, connection.error
    assert connection.result is not None
    assert connection.result["match"]["local_id"] == "local:matrix"

    if debug_enabled:
        assert connection.result["diagnostic"] is not None
        assert connection.result["diagnostic"]["resolved_match"]["local_id"] == "local:matrix"
    else:
        assert connection.result["diagnostic"] is None


asyncio.run(run_case(False))
asyncio.run(run_case(True))

print("find_local_copy hotfix execution checks passed for Debug OFF/ON.")
