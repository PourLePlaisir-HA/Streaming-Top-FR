from pathlib import Path
import importlib.util
import sys


MODULE = Path("custom_components/streaming_top_fr/local_library.py")
spec = importlib.util.spec_from_file_location("streaming_top_fr_local_library", MODULE)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)

scanner = module.LocalLibraryScanner(None)
settings = {
    "category_folders": {
        "movies": ["Movies", "Films"],
        "series": ["Series", "Séries"],
        "animation": ["Animation", "Dessins Animés"],
        "documentaries": ["Documentaires"],
    }
}

cases = [
    (
        "Documentaires/Planete Terre/Saison 1/Planete.Terre.S01.E01.mkv",
        "documentaries", 1, 1, "Planete Terre",
    ),
    (
        "Documentaires/Planete Terre/Saison 1/Planete.Terre.S01-E06.mkv",
        "documentaries", 1, 6, "Planete Terre",
    ),
    (
        "Documentaires/Planete Terre/Saison 1/Planete.Terre.S01 E07.mkv",
        "documentaries", 1, 7, "Planete Terre",
    ),
    (
        "Documentaires/Planete Terre/S01/Planete.Terre.S01_E12.mkv",
        "documentaries", 1, 12, "Planete Terre",
    ),
    (
        "Animation/Bluey/Season 2/Bluey.S02E03.mkv",
        "animation", 2, 3, "Bluey",
    ),
    (
        "Series/Ma Serie/Saison 3/Ma.Serie.3x04.mp4",
        "series", 3, 4, "Ma Serie",
    ),
    (
        "Series/Blake et Mortimer/Blake.et.Mortimer.le.mystere.du.tresor.disparu.S01E01.DOC.FRENCH.1080p.WEB.H264.mkv",
        "series", 1, 1, "Blake et Mortimer",
    ),
]

for raw, bucket, season, episode, title in cases:
    relative = Path(raw)
    result = scanner._parse_media(relative, relative, settings)
    assert result["bucket"] == bucket, (raw, result)
    assert result["media_type"] == "tv", (raw, result)
    assert result["episodic"] is True, (raw, result)
    assert result["season"] == season, (raw, result)
    assert result["episode"] == episode, (raw, result)
    assert result["title"] == title, (raw, result)
    assert result["franchise_title"] == title, (raw, result)

blake = scanner._parse_media(
    Path(
        "Series/Blake et Mortimer/"
        "Blake.et.Mortimer.le.mystere.du.tresor.disparu."
        "S01E01.DOC.FRENCH.1080p.WEB.H264.mkv"
    ),
    Path(
        "Series/Blake et Mortimer/"
        "Blake.et.Mortimer.le.mystere.du.tresor.disparu."
        "S01E01.DOC.FRENCH.1080p.WEB.H264.mkv"
    ),
    settings,
)
assert blake["franchise_title"] == "Blake et Mortimer", blake
assert blake["episode_title"] == "le mystere du tresor disparu", blake

print("Streaming Local episodic parser checks passed.")
