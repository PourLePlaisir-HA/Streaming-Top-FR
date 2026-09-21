from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "custom_components/streaming_top_fr/watch_identity.py"
spec = spec_from_file_location("watch_identity_test_module", PATH)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

canonical_work_key = module.canonical_work_key
episode_code = module.episode_code

local = {
    "media_key": "local:abc",
    "local_id": "local:abc",
    "media_type": "movie",
    "title": "Indiana Jones et la Dernière Croisade",
    "year": 1989,
    "imdb_id": "tt0097576",
}
streaming = {
    "media_key": "jw:12345",
    "media_type": "movie",
    "title": "Indiana Jones et la Dernière Croisade",
    "year": 1989,
    "imdb_id": "tt0097576",
}
assert canonical_work_key(local) == "imdb:tt0097576"
assert canonical_work_key(streaming) == canonical_work_key(local)

fallback_local = {
    "local_id": "local:def",
    "media_type": "movie",
    "title": "Exemple Film",
    "year": 2024,
}
fallback_streaming = {
    "media_key": "jw:999",
    "media_type": "movie",
    "title": "Exemple Film",
    "year": 2024,
}
assert canonical_work_key(fallback_local) == canonical_work_key(fallback_streaming)
assert canonical_work_key({**fallback_streaming, "year": 2023}) != canonical_work_key(
    fallback_local
)

unmatched_a = {"local_id": "local:a", "media_type": "movie", "title": "Sans année"}
unmatched_b = {"local_id": "local:b", "media_type": "movie", "title": "Sans année"}
assert canonical_work_key(unmatched_a) != canonical_work_key(unmatched_b)

episode = {
    "media_type": "tv",
    "episodic": True,
    "franchise_title": "Blake et Mortimer",
    "season": 1,
    "episode": 4,
    "imdb_id": "tt1234567",
}
assert canonical_work_key(episode) == "imdb:tt1234567"
assert episode_code(episode) == "S01E04"

print("Canonical watched identity checks passed.")
