from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sources = (ROOT / "custom_components/streaming_top_fr/sources.py").read_text(encoding="utf-8")
local_library = (ROOT / "custom_components/streaming_top_fr/local_library.py").read_text(encoding="utf-8")
init_source = (ROOT / "custom_components/streaming_top_fr/__init__.py").read_text(encoding="utf-8")
card = (ROOT / "custom_components/streaming_top_fr/www/streaming-top-fr-card.js").read_text(encoding="utf-8")

assert "def normalize_genres(" in sources
assert '"science_fiction": "Science-fiction"' in sources
assert '"act": ("action", "adventure")' in sources
assert sources.count("genres { shortName }") >= 6
assert "genres { genres { text } }" in sources
assert '"genres_raw"' in sources
assert '"genre_labels"' in sources
assert '"genre_source"' in sources
assert '"genres_raw",' in local_library
assert '"genre_source",' in local_library
assert '"debug": dict(settings.get("debug") or {})' in init_source

assert "const STFR_GENRE_ORDER=[" in card
assert "function stfrGenreFilter(card,items)" in card
assert "function stfrInstallGenreFilter(card)" in card
assert "Détails techniques — genres" in card
assert "genre_filter_label" in card
assert "genre_match" in card

print("Genre metadata, debug diagnostics and frontend guards passed.")
