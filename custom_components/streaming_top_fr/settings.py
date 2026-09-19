from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import re
import yaml

from .const import SUPPORTED_PROVIDERS

CONFIG_FILENAME = "streaming_top_fr.yaml"

DEFAULT_PLAYERS: dict[str, dict[str, Any]] = {}


DEFAULT_TOP_CATALOG: dict[str, Any] = {
    "enabled": True,
    "default_decade": "1990",
    "min_imdb_votes": 20000,
    "exclude_short_films": True,
    "decades": {
        "1920": {"enabled": False, "top_count": 3, "movies": True, "animation": True, "series": False},
        "1930": {"enabled": False, "top_count": 5, "movies": True, "animation": True, "series": False},
        "1940": {"enabled": False, "top_count": 5, "movies": True, "animation": True, "series": False},
        "1950": {"enabled": False, "top_count": 15, "movies": True, "animation": True, "series": True},
        "1960": {"enabled": False, "top_count": 5, "movies": True, "animation": True, "series": True},
        "1970": {"enabled": True, "top_count": 12, "movies": True, "animation": True, "series": True},
        "1980": {"enabled": True, "top_count": 20, "movies": True, "animation": True, "series": True},
        "1990": {"enabled": True, "top_count": 65, "movies": True, "animation": True, "series": True},
        "2000": {"enabled": True, "top_count": 65, "movies": True, "animation": True, "series": True},
        "2010": {"enabled": True, "top_count": 65, "movies": True, "animation": True, "series": True},
        "2020": {"enabled": True, "top_count": 65, "movies": True, "animation": True, "series": True},
    },
}


DEFAULT_FAMILY: dict[str, Any] = {
    "enabled": True,
    "target_age": 11,
    "allow_unrated": False,
    "movies": True,
    "animation": True,
    "series": True,
}


DEFAULT_SETTINGS: dict[str, Any] = {
    "services": {
        "netflix": True,
        "disney": True,
        "prime": True,
        "hbo_max": False,
        "apple_tv": False,
        "paramount": False,
        "canal": False,
        "crunchyroll": False,
        "mubi": False,
        "adn": False,
    },
    "players": deepcopy(DEFAULT_PLAYERS),
    "top_catalog": deepcopy(DEFAULT_TOP_CATALOG),
    "family": deepcopy(DEFAULT_FAMILY),
    "classification": {
        "enabled": True,
        "france": True,
        "us_fallback": True,
        "us_tv": True,
    },
    "discovery": {
        "visible_count": 10,
        "prefetch_count": 20,
        "max_depth": 100,
    },
}

DEFAULT_CONFIG_TEXT = """# Streaming Top FR legacy YAML (v0.7 migration support)
# Ce fichier est relu à chaque rafraîchissement de la source (bouton ↻ inclus).
# Les booléens acceptent true/false, yes/no, oui/non.
#
# Services :
# - true  = service visible dans le sélecteur et ses carrousels Films / Séries sont chargés
# - false = service totalement ignoré
#
# Destinations :
# - le nombre de players n'est pas limité ; ajoutez autant de blocs que nécessaire
# - `name` est le libellé affiché dans la popup
# - pour `type: android_tv`, Netflix/Disney+/Prime utilisent `remote` + `adb_player`
# - `media_player` identifie la destination Home Assistant et prépare les futurs modes de lecture
#
# HBO Max, Apple TV+, Paramount+, CANAL+, Crunchyroll, MUBI et ADN utilisent
# les catalogues/popularités JustWatch France. La lecture automatisée reste
# activée uniquement pour les plateformes dont le lancement a été validé.

services:
  netflix: true
  disney: true
  prime: true
  hbo_max: false
  apple_tv: false
  paramount: false
  canal: false
  crunchyroll: false
  mubi: false
  adn: false

players:
  salon:
    name: Salon
    type: android_tv
    media_player: media_player.android_tv_salon
    remote: remote.android_tv_salon
    adb_player: media_player.android_tv_salon_adb

  etage:
    name: Étage
    type: android_tv
    media_player: media_player.android_tv_etage
    remote: remote.android_tv_etage
    adb_player: media_player.android_tv_etage_adb


# Deuxième carte : custom:streaming-top-fr-catalog-card
# `top_count` s'applique séparément à chaque catégorie activée.
# Les décennies désactivées ne génèrent aucune requête catalogue.
top_catalog:
  enabled: true
  default_decade: "1990"       # Décennie affichée par défaut dans la carte Top Streaming
  min_imdb_votes: 20000      # Seuil IMDb minimal ; 0 désactive ce filtre
  exclude_short_films: true  # Exclut les films/animations de moins de 40 min
  decades:
    "1920": { enabled: false, top_count: 3, movies: true, animation: true, series: false }
    "1930": { enabled: false, top_count: 5, movies: true, animation: true, series: false }
    "1940": { enabled: false, top_count: 5, movies: true, animation: true, series: false }
    "1950": { enabled: false, top_count: 15, movies: true, animation: true, series: true }
    "1960": { enabled: false, top_count: 5, movies: true, animation: true, series: true }
    "1970": { enabled: true, top_count: 12, movies: true, animation: true, series: true }
    "1980": { enabled: true, top_count: 20, movies: true, animation: true, series: true }
    "1990": { enabled: true, top_count: 65, movies: true, animation: true, series: true }
    "2000": { enabled: true, top_count: 65, movies: true, animation: true, series: true }
    "2010": { enabled: true, top_count: 65, movies: true, animation: true, series: true }
    "2020": { enabled: true, top_count: 65, movies: true, animation: true, series: true }

# Branche Famille de la carte Top Streaming.
# `target_age: 11` = contenus adaptés à un enfant de 11 ans (donc moins de 12 ans).
# La classification FR est prioritaire pour le filtrage ; US uniquement en fallback.
# `allow_unrated: false` exclut par prudence les œuvres sans classification exploitable.
family:
  enabled: true
  target_age: 11
  allow_unrated: false
  movies: true
  animation: true
  series: true

classification:
  enabled: true          # Afficher les classifications d'âge
  france: true           # Priorité à la classification française
  us_fallback: true      # Si aucune FR exploitable, afficher la classification US
  us_tv: true            # Autoriser les classifications TV-Y, TV-PG, TV-14, TV-MA...

discovery:
  visible_count: 10      # Nombre de tuiles visibles dans « À découvrir » (pas de 1)
  prefetch_count: 20     # Fenêtre active totale : visibles + réserve, toujours maintenue pleine
  max_depth: 100         # Profondeur maximale explorée pour reconstituer la fenêtre active
"""


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "y", "1", "on", "oui", "o"}:
            return True
        if normalized in {"false", "no", "n", "0", "off", "non"}:
            return False
    return default


def _as_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    return max(minimum, min(maximum, result))


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_players(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return deepcopy(DEFAULT_PLAYERS)

    out: dict[str, dict[str, Any]] = {}
    for raw_id, raw in value.items():
        player_id = str(raw_id or "").strip()
        if not player_id or not isinstance(raw, dict):
            continue

        name = _clean_string(raw.get("name")) or player_id
        player_type = (_clean_string(raw.get("type")) or "android_tv").casefold()
        out[player_id] = {
            "name": name,
            "type": player_type,
            "media_player": _clean_string(raw.get("media_player")),
            "remote": _clean_string(raw.get("remote")),
            "adb_player": _clean_string(raw.get("adb_player")),
        }

    return out


def normalize_settings(raw: Any) -> dict[str, Any]:
    settings = deepcopy(DEFAULT_SETTINGS)
    if not isinstance(raw, dict):
        return settings

    services = raw.get("services") or {}
    if isinstance(services, dict):
        defaults = DEFAULT_SETTINGS["services"]
        normalized = {}
        for provider in SUPPORTED_PROVIDERS:
            normalized[provider] = _as_bool(
                services.get(provider), defaults.get(provider, False)
            )
        # Common aliases accepted for convenience.
        alias_keys = {
            "hbo_max": ("hbo", "hbomax", "max"),
            "apple_tv": ("apple", "apple_tv_plus"),
            "paramount": ("paramount_plus",),
            "canal": ("canal_plus",),
        }
        for provider, aliases in alias_keys.items():
            if provider not in services:
                for alias in aliases:
                    if alias in services:
                        normalized[provider] = _as_bool(
                            services.get(alias), normalized[provider]
                        )
                        break
        settings["services"] = normalized

    settings["players"] = _normalize_players(raw.get("players"))

    top_catalog = raw.get("top_catalog") or {}
    if isinstance(top_catalog, dict):
        settings["top_catalog"]["enabled"] = _as_bool(
            top_catalog.get("enabled"), DEFAULT_TOP_CATALOG["enabled"]
        )
        default_decade = str(
            top_catalog.get("default_decade", DEFAULT_TOP_CATALOG["default_decade"])
        )
        if default_decade not in DEFAULT_TOP_CATALOG["decades"]:
            default_decade = DEFAULT_TOP_CATALOG["default_decade"]
        settings["top_catalog"]["default_decade"] = default_decade
        settings["top_catalog"]["min_imdb_votes"] = _as_int(
            top_catalog.get("min_imdb_votes"),
            DEFAULT_TOP_CATALOG["min_imdb_votes"],
            0,
            10000000,
        )
        settings["top_catalog"]["exclude_short_films"] = _as_bool(
            top_catalog.get("exclude_short_films"),
            DEFAULT_TOP_CATALOG["exclude_short_films"],
        )
        raw_decades = top_catalog.get("decades") or {}
        normalized_decades: dict[str, dict[str, Any]] = {}
        for decade, defaults in DEFAULT_TOP_CATALOG["decades"].items():
            entry = raw_decades.get(decade, raw_decades.get(int(decade), {})) if isinstance(raw_decades, dict) else {}
            if not isinstance(entry, dict):
                entry = {}
            normalized_decades[decade] = {
                "enabled": _as_bool(entry.get("enabled"), defaults["enabled"]),
                "top_count": _as_int(entry.get("top_count", entry.get("nombreTop", entry.get("NombreTop"))), defaults["top_count"], 1, 100),
                "movies": _as_bool(entry.get("movies"), defaults["movies"]),
                "animation": _as_bool(entry.get("animation"), defaults["animation"]),
                "series": _as_bool(entry.get("series"), defaults["series"]),
            }
        settings["top_catalog"]["decades"] = normalized_decades

    family = raw.get("family") or {}
    if isinstance(family, dict):
        defaults = DEFAULT_FAMILY
        settings["family"] = {
            "enabled": _as_bool(family.get("enabled"), defaults["enabled"]),
            "target_age": _as_int(family.get("target_age"), defaults["target_age"], 0, 17),
            "allow_unrated": _as_bool(family.get("allow_unrated"), defaults["allow_unrated"]),
            "movies": _as_bool(family.get("movies"), defaults["movies"]),
            "animation": _as_bool(family.get("animation"), defaults["animation"]),
            "series": _as_bool(family.get("series"), defaults["series"]),
        }

    classification = raw.get("classification") or {}
    if isinstance(classification, dict):
        defaults = DEFAULT_SETTINGS["classification"]
        settings["classification"] = {
            "enabled": _as_bool(classification.get("enabled"), defaults["enabled"]),
            "france": _as_bool(classification.get("france"), defaults["france"]),
            "us_fallback": _as_bool(classification.get("us_fallback"), defaults["us_fallback"]),
            "us_tv": _as_bool(classification.get("us_tv"), defaults["us_tv"]),
        }

    discovery = raw.get("discovery") or {}
    if isinstance(discovery, dict):
        defaults = DEFAULT_SETTINGS["discovery"]
        visible = _as_int(discovery.get("visible_count"), defaults["visible_count"], 1, 100)
        prefetch = _as_int(discovery.get("prefetch_count"), defaults["prefetch_count"], 1, 100)
        max_depth = _as_int(discovery.get("max_depth"), defaults["max_depth"], 1, 100)

        prefetch = max(prefetch, visible)
        max_depth = max(max_depth, prefetch)
        settings["discovery"] = {
            "visible_count": visible,
            "prefetch_count": prefetch,
            "max_depth": max_depth,
        }

    return settings


def _ensure_and_load(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
        return deepcopy(DEFAULT_SETTINGS)

    try:
        original_text = config_path.read_text(encoding="utf-8")
        raw = yaml.safe_load(original_text)
    except Exception:
        return deepcopy(DEFAULT_SETTINGS)

    # Upgrade old configuration files in place. Existing user values stay intact.
    additions = []
    if isinstance(raw, dict) and "services" not in raw:
        additions.append("""# Services de streaming affichés dans le sélecteur
services:
  netflix: true
  disney: true
  prime: true
  hbo_max: false
  apple_tv: false
  paramount: false
  canal: false
  crunchyroll: false
  mubi: false
  adn: false

""")

    if isinstance(raw, dict) and "players" not in raw:
        additions.append("""# Destinations de lecture affichées dynamiquement dans les popups
players:
  salon:
    name: Salon
    type: android_tv
    media_player: media_player.android_tv_salon
    remote: remote.android_tv_salon
    adb_player: media_player.android_tv_salon_adb
  etage:
    name: Étage
    type: android_tv
    media_player: media_player.android_tv_etage
    remote: remote.android_tv_etage
    adb_player: media_player.android_tv_etage_adb

""")

    if isinstance(raw, dict) and "top_catalog" not in raw:
        additions.append("""# Classement historique disponible sur les services activés
top_catalog:
  enabled: true
  min_imdb_votes: 20000
  exclude_short_films: true
  decades:
    "1920": { enabled: false, top_count: 3, movies: true, animation: true, series: false }
    "1930": { enabled: false, top_count: 5, movies: true, animation: true, series: false }
    "1940": { enabled: false, top_count: 5, movies: true, animation: true, series: false }
    "1950": { enabled: false, top_count: 15, movies: true, animation: true, series: true }
    "1960": { enabled: false, top_count: 5, movies: true, animation: true, series: true }
    "1970": { enabled: true, top_count: 12, movies: true, animation: true, series: true }
    "1980": { enabled: true, top_count: 20, movies: true, animation: true, series: true }
    "1990": { enabled: true, top_count: 65, movies: true, animation: true, series: true }
    "2000": { enabled: true, top_count: 65, movies: true, animation: true, series: true }
    "2010": { enabled: true, top_count: 65, movies: true, animation: true, series: true }
    "2020": { enabled: true, top_count: 65, movies: true, animation: true, series: true }

""")

    # Upgrade an existing Top Streaming block without replacing user values/comments.
    if isinstance(raw, dict) and isinstance(raw.get("top_catalog"), dict):
        tc = raw.get("top_catalog") or {}
        missing_top_keys = []
        if "min_imdb_votes" not in tc:
            missing_top_keys.append("  min_imdb_votes: 20000      # Seuil IMDb minimal ; 0 désactive ce filtre")
        if "exclude_short_films" not in tc:
            missing_top_keys.append("  exclude_short_films: true  # Exclut les films/animations de moins de 40 min")
        if missing_top_keys:
            try:
                upgraded_text = re.sub(
                    r"(?m)^top_catalog:\s*$",
                    "top_catalog:\n" + "\n".join(missing_top_keys),
                    original_text,
                    count=1,
                )
                if upgraded_text != original_text:
                    original_text = upgraded_text
                    config_path.write_text(original_text, encoding="utf-8")
                    raw = yaml.safe_load(original_text)
            except Exception:
                pass

    if isinstance(raw, dict) and "family" not in raw:
        additions.append("""# Filtre Famille de la carte Top Streaming
family:
  enabled: true
  target_age: 11
  allow_unrated: false
  movies: true
  animation: true
  series: true

""")

    if additions:
        try:
            upgraded = "".join(additions) + original_text.lstrip()
            config_path.write_text(upgraded, encoding="utf-8")
            raw = yaml.safe_load(upgraded)
        except Exception:
            pass

    return normalize_settings(raw)


def _load_legacy_if_present(path: str) -> dict[str, Any]:
    """Load legacy YAML without creating it for new UI-based installs."""
    if not Path(path).exists():
        return deepcopy(DEFAULT_SETTINGS)
    return _ensure_and_load(path)


async def async_load_legacy_settings(hass) -> dict[str, Any]:
    """Load v0.6.x YAML settings when present, otherwise return defaults."""
    path = hass.config.path(CONFIG_FILENAME)
    return await hass.async_add_executor_job(_load_legacy_if_present, path)


async def async_load_settings(hass, config_entry=None) -> dict[str, Any]:
    """Load settings, preferring the native Home Assistant config entry UI."""
    if config_entry is not None:
        options = dict(config_entry.options)
        raw = options.get("settings") or config_entry.data.get("settings")
        if isinstance(raw, dict):
            return normalize_settings(raw)

    return await async_load_legacy_settings(hass)
