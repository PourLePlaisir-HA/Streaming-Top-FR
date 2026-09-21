from __future__ import annotations

import asyncio
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "custom_components/streaming_top_fr"
PKG = "custom_components.streaming_top_fr"

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(ROOT / "custom_components")]
sys.modules.setdefault("custom_components", custom_components)

package = types.ModuleType(PKG)
package.__path__ = [str(PKG_DIR)]
sys.modules[PKG] = package

homeassistant = types.ModuleType("homeassistant")
core = types.ModuleType("homeassistant.core")
helpers = types.ModuleType("homeassistant.helpers")
storage = types.ModuleType("homeassistant.helpers.storage")
core.HomeAssistant = object


class DummyStore:
    def __init__(self, *args, **kwargs):
        self.saved = None

    async def async_load(self):
        return None

    async def async_save(self, data):
        self.saved = data


storage.Store = DummyStore
sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.core"] = core
sys.modules["homeassistant.helpers"] = helpers
sys.modules["homeassistant.helpers.storage"] = storage


def load(name: str, filename: str):
    spec = spec_from_file_location(name, PKG_DIR / filename)
    module = module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


identity = load(f"{PKG}.watch_identity", "watch_identity.py")
registry_module = load(f"{PKG}.watch_registry", "watch_registry.py")


async def main():
    Registry = registry_module.CanonicalWatchRegistry
    registry = Registry(object())

    streaming_without_imdb = {
        "media_key": "jw:42",
        "media_type": "movie",
        "title": "Exemple Film",
        "year": 2024,
    }
    local_with_imdb = {
        "media_key": "local:42",
        "local_id": "local:42",
        "media_type": "movie",
        "title": "Exemple Film",
        "year": 2024,
        "imdb_id": "tt1234567",
    }

    await registry.async_set_work(
        streaming_without_imdb, True, source="streaming", alias_key="jw:42"
    )
    assert registry.state_for_item(streaming_without_imdb)["watched"] is True

    # IMDb discovered later must migrate the strict fallback watched state.
    await registry.async_observe_items([local_with_imdb])
    local_state = registry.state_for_item(local_with_imdb)
    assert local_state["key"] == "imdb:tt1234567"
    assert local_state["watched"] is True
    assert registry.same_work(local_with_imdb, streaming_without_imdb)

    # Explicitly returning the work to "not watched" is reversible globally.
    await registry.async_set_work(local_with_imdb, False, source="local")
    assert registry.state_for_item(local_with_imdb)["watched"] is False
    assert registry.state_for_item(streaming_without_imdb)["watched"] is False

    # The reverse observation order must also preserve the IMDb bridge.
    reverse = Registry(object())
    await reverse.async_set_work(local_with_imdb, True, source="local")
    await reverse.async_observe_items([streaming_without_imdb])
    assert reverse.same_work(local_with_imdb, streaming_without_imdb)
    assert reverse.state_for_item(streaming_without_imdb)["watched"] is True

    series = {
        "media_key": "jw:series",
        "media_type": "tv",
        "title": "Série Test",
        "year": 2020,
        "imdb_id": "tt7654321",
    }
    ep1 = {
        "local_id": "local:ep1",
        "media_key": "local:ep1",
        "media_type": "tv",
        "title": "Série Test",
        "franchise_title": "Série Test",
        "year": 2020,
        "imdb_id": "tt7654321",
        "episodic": True,
        "season": 1,
        "episode": 1,
    }
    ep2 = {**ep1, "local_id": "local:ep2", "media_key": "local:ep2", "episode": 2}

    await registry.async_set_work(series, True, source="streaming")
    await registry.async_observe_items([ep1, ep2])
    assert registry.state_for_item(ep1)["watched"] is True
    assert registry.state_for_item(ep2)["watched"] is True

    # Episode override wins over the global series state.
    await registry.async_set_episode(ep1, False, source="local")
    assert registry.state_for_item(ep1)["watched"] is False
    assert registry.state_for_item(ep2)["watched"] is True

    # A whole Local season can be moved back to not watched without clearing
    # the global series record; explicit episode overrides have priority.
    await registry.async_set_episodes([ep1, ep2], False, source="local")
    assert registry.state_for_item(ep1)["watched"] is False
    assert registry.state_for_item(ep2)["watched"] is False

    print("Canonical watch registry checks passed.")


asyncio.run(main())
