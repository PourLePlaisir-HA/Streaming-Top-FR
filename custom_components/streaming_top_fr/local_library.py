from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import unicodedata
from typing import Any
from urllib.parse import quote


DEFAULT_EXTENSIONS = {
    ".mkv",
    ".avi",
    ".mp4",
    ".m4v",
    ".ts",
    ".m2ts",
    ".mov",
    ".wmv",
}

_RELEASE_WORDS = re.compile(
    r"\b(?:2160p|1080p|720p|576p|4k|uhd|hdr10\+?|hdr|dolby[ ._-]?vision|dv|"
    r"bluray(?:2160p|1080p|720p|576p)?|blu[ ._-]?ray(?:2160p|1080p|720p|576p)?|"
    r"bdrip|brrip|web[ ._-]?dl|webrip|hdtv|remux|"
    r"x26[45]|h\.?26[45]|hevc|av1|aac|ac3|eac3|dts(?:-hd)?|truehd|"
    r"multi|french|truefrench|vostfr|vost|vof|vfq|vfi|vf2|vff|vo|dubbed|"
    r"subfrench|proper|repack|web|mhd)\b.*$",
    re.IGNORECASE,
)
_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_EPISODE = re.compile(
    r"(?i)\bS\s*(?P<season>\d{1,2})[ ._-]*E\s*(?P<episode>\d{1,3})\b"
)
_EPISODE_ALT = re.compile(
    r"(?i)\b(?P<season>\d{1,2})x(?P<episode>\d{1,3})\b"
)
_SEASON_FOLDER = re.compile(
    r"(?i)^(?:season|saison|s)[ ._-]*\d{1,2}$"
)
_COLLECTION_PREFIX = re.compile(
    r"(?i)^\s*(?:n\s*[°ºo]?|no\.?|nr\.?|#)\s*\d{1,4}\s*[-–—_:]\s*"
)
_STUDIO_PREFIX = re.compile(
    r"(?i)^\s*(?:walt\s+disney|disney|pixar|dreamworks(?:\s+animation)?|studio\s+ghibli)"
    r"\s*[-–—_:]\s*"
)
_LANGUAGE_QUOTED_SUBTITLE = re.compile(
    r"(?i)\b(?:vf|vff|vfq|vfi|vf2|french|truefrench)\s*"
    r"[\"“”«]\s*(?P<subtitle>[^\"“”»]+?)\s*[\"“”»]"
)
_CONTEXTUAL_RELEASE_PREFIX = re.compile(
    r"(?i)\b(?:hybrid)\b(?=\s+(?:multi|french|truefrench|vostfr|vost|"
    r"vof|vfq|vfi|vf2|vff|vf|vo|2160p|1080p|720p|4k|uhd|hdr|dv|"
    r"bluray|blu\s*ray|web|remux|x26[45]|h\.?26[45]))"
)
_LOOKUP_VOLUME_SUFFIX = re.compile(
    r"(?i)\s*(?:#\s*\d{1,3}|vol(?:ume)?\.?\s*\d{1,3}|tome\s*\d{1,3})\s*$"
)

DEFAULT_CATEGORY_FOLDERS = {
    "movies": ["Films"],
    "series": ["Series", "Séries"],
    "animation": ["Animation", "Animations", "Dessins Animés"],
    "documentaries": ["Documentaires", "Documentaries"],
}


@dataclass(slots=True)
class LocalScanResult:
    items: list[dict[str, Any]]
    errors: list[str]
    revision: int = 0


class LocalLibraryScanner:
    def __init__(self, hass):
        self.hass = hass
        self._last_result = LocalScanResult(items=[], errors=[], revision=0)
        self._scan_revision = 0
        self._scan_lock = asyncio.Lock()

    @property
    def last_result(self) -> LocalScanResult:
        return self._last_result

    async def async_scan(self, settings: dict[str, Any]) -> LocalScanResult:
        # Serialize scans so an older, slower filesystem walk can never
        # overwrite the result of a newer refresh request.
        async with self._scan_lock:
            previous = {
                str(item.get("relative_path") or ""): item
                for item in self._last_result.items
                if isinstance(item, dict) and item.get("relative_path")
            }
            result = await self.hass.async_add_executor_job(self._scan, settings)

            # Preserve validated metadata for files that are strictly unchanged.
            # Deleted/moved files are not present under the same relative path,
            # so stale artefacts still disappear correctly after a refresh.
            metadata_fields = {
                "title",
                "year",
                "poster",
                "poster_source",
                "description",
                "rating",
                "rating_source",
                "imdb_votes",
                "age_certification",
                "age_country",
                "age_fr",
                "age_us",
                "age_resolved",
                "imdb_id",
                "details_url",
                "providers",
                "canonical_media_key",
                "metadata_status",
                "match_score",
                "resolved_media_type",
            }
            for item in result.items:
                old_item = previous.get(str(item.get("relative_path") or ""))
                if not old_item:
                    continue
                if (
                    int(item.get("size") or -1) != int(old_item.get("size") or -2)
                    or int(item.get("mtime") or -1) != int(old_item.get("mtime") or -2)
                ):
                    continue

                # Keep only genuinely useful previous enrichment.
                # Old unmatched rows or rows without a poster must be retried;
                # otherwise a transient 403 can freeze a broken state forever.
                old_status = str(old_item.get("metadata_status") or "")
                old_poster = old_item.get("poster")
                if old_status not in {"matched", "imdb_only"} or not old_poster:
                    continue

                parsed_title = item.get("title")
                parsed_year = item.get("year")
                for field in metadata_fields:
                    if field in old_item and old_item.get(field) is not None:
                        item[field] = old_item.get(field)
                item["parsed_title"] = old_item.get("parsed_title") or parsed_title
                item["lookup_title"] = (
                    old_item.get("lookup_title") or item.get("lookup_title") or parsed_title
                )
                if item.get("year") is None:
                    item["year"] = parsed_year

            self._scan_revision += 1
            result.revision = self._scan_revision
            self._last_result = result
            return result

    def _scan(self, settings: dict[str, Any]) -> LocalScanResult:
        if not settings.get("enabled", False):
            return LocalScanResult(items=[], errors=[])

        raw_root = str(settings.get("root_path") or "").strip()
        if not raw_root:
            return LocalScanResult(items=[], errors=["Chemin local non configuré"])

        root = Path(raw_root).expanduser()
        if not root.exists():
            return LocalScanResult(items=[], errors=[f"Chemin introuvable : {root}"])
        if not root.is_dir():
            return LocalScanResult(items=[], errors=[f"Le chemin n'est pas un dossier : {root}"])

        extensions = {
            str(ext).strip().lower()
            if str(ext).strip().startswith(".")
            else f".{str(ext).strip().lower()}"
            for ext in (settings.get("extensions") or DEFAULT_EXTENSIONS)
            if str(ext).strip()
        }
        if not extensions:
            extensions = set(DEFAULT_EXTENSIONS)

        smb_base = str(settings.get("smb_base_uri") or "").strip().rstrip("/")
        scan_hidden = bool(settings.get("scan_hidden", False))
        items: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            paths = root.rglob("*")
            for path in paths:
                try:
                    if not path.is_file() or path.suffix.lower() not in extensions:
                        continue
                    rel = path.relative_to(root)
                    if not scan_hidden and any(part.startswith(".") for part in rel.parts):
                        continue
                    parsed = self._parse_media(path, rel, settings)
                    relative_posix = rel.as_posix()
                    parsed.update(
                        {
                            "local_id": "local:" + sha256(relative_posix.encode("utf-8")).hexdigest()[:24],
                            "local_path": str(path),
                            "relative_path": relative_posix,
                            "filename": path.name,
                            "size": path.stat().st_size,
                            "mtime": int(path.stat().st_mtime),
                            "smb_uri": self._smb_uri(smb_base, rel) if smb_base else None,
                        }
                    )
                    items.append(parsed)
                except OSError as err:
                    errors.append(f"{path}: {err}")
        except OSError as err:
            errors.append(str(err))

        items.sort(
            key=lambda item: (
                str(item.get("media_type") or ""),
                str(item.get("title") or "").casefold(),
                int(item.get("season") or 0),
                int(item.get("episode") or 0),
                str(item.get("relative_path") or "").casefold(),
            )
        )
        return LocalScanResult(items=items, errors=errors)

    @staticmethod
    def _smb_uri(base: str, relative: Path) -> str:
        encoded = "/".join(quote(part, safe="") for part in relative.parts)
        return f"{base}/{encoded}"

    @staticmethod
    def _strip_nested_video_extensions(value: str) -> str:
        cleaned = str(value or "")
        # Files occasionally end in chains such as ".mkv.mp4". Path.stem
        # removes only the last suffix, so remove any remaining video suffixes.
        while True:
            suffix = Path(cleaned).suffix.lower()
            if suffix not in DEFAULT_EXTENSIONS:
                break
            cleaned = Path(cleaned).stem
        return cleaned

    @staticmethod
    def _clean_name(value: str) -> str:
        cleaned = value.replace("_", " ").replace(".", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_.")
        return cleaned

    @staticmethod
    def _normalize_folder_name(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.replace("_", " ").replace(".", " ")
        return re.sub(r"\s+", " ", normalized).strip().casefold()

    @classmethod
    def _category_folders(cls, settings: dict[str, Any]) -> dict[str, set[str]]:
        configured = settings.get("category_folders") or {}
        out: dict[str, set[str]] = {}
        for category, defaults in DEFAULT_CATEGORY_FOLDERS.items():
            raw = configured.get(category, defaults) if isinstance(configured, dict) else defaults
            if isinstance(raw, str):
                raw = [part.strip() for part in raw.split(",") if part.strip()]
            if not isinstance(raw, list):
                raw = defaults
            out[category] = {
                cls._normalize_folder_name(value)
                for value in raw
                if str(value).strip()
            }
        return out

    @classmethod
    def _bucket_from_path(
        cls, relative: Path, settings: dict[str, Any], media_type: str
    ) -> str:
        folders = cls._category_folders(settings)
        # Prefer the most specific (deepest) matching parent folder.
        for part in reversed(relative.parts[:-1]):
            token = cls._normalize_folder_name(part)
            for category in ("documentaries", "animation", "series", "movies"):
                if token in folders.get(category, set()):
                    return category

        # Compatibility fallback for libraries configured before folder mapping.
        tokens = {cls._normalize_folder_name(part) for part in relative.parts[:-1]}
        if tokens & {"documentaires", "documentaries", "documentary"}:
            return "documentaries"
        if tokens & {"animation", "animations", "anime", "animes", "dessins animes"}:
            return "animation"
        return "series" if media_type == "tv" else "movies"

    @classmethod
    def _clean_local_title(cls, value: str) -> str:
        # Preserve a meaningful quoted subtitle that follows a language tag:
        #   Title VF "Subtitle" -> Title : Subtitle
        value = _LANGUAGE_QUOTED_SUBTITLE.sub(
            lambda match: f" : {match.group('subtitle').strip()} ",
            str(value or ""),
        )
        cleaned = cls._clean_name(value)
        previous = None
        while cleaned and cleaned != previous:
            previous = cleaned
            cleaned = _COLLECTION_PREFIX.sub("", cleaned).strip(" -_.")
            cleaned = _STUDIO_PREFIX.sub("", cleaned).strip(" -_.")
            # Removing a parsed year such as "(1994)" can leave empty
            # punctuation behind. Drop only empty bracket groups so meaningful
            # parenthetical title text is preserved.
            cleaned = re.sub(r"\(\s*\)|\[\s*\]|\{\s*\}", " ", cleaned)
            cleaned = re.sub(r"\s*[-–—_:]+\s*$", "", cleaned)
            cleaned = re.sub(r"\s*[:]+\s*", " : ", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_.! ")
        return cleaned

    @staticmethod
    def _episode_match(value: str):
        """Return a genuine episodic marker, excluding codec false positives."""
        text = str(value or "")
        standard = _EPISODE.search(text)
        if standard:
            return standard

        for match in _EPISODE_ALT.finditer(text):
            start = match.start()
            # Avoid interpreting audio-channel/codec strings such as
            # "5.1x264" or "7.1x265" as season/episode markers.
            if start >= 2 and re.fullmatch(r"\d[._]", text[start - 2 : start]):
                continue
            return match
        return None

    @classmethod
    def _lookup_title(cls, title: str) -> str:
        """Return a safer catalogue-search title while preserving display text.

        Explicit collection-volume suffixes are not usually part of the
        canonical work title. Bare sequel numbers are deliberately untouched.
        """
        value = str(title or "").strip()
        reduced = _LOOKUP_VOLUME_SUFFIX.sub("", value).strip(" -_.")
        return reduced or value

    def _parse_media(
        self, path: Path, relative: Path, settings: dict[str, Any]
    ) -> dict[str, Any]:
        stem = self._strip_nested_video_extensions(path.stem)
        episode_match = self._episode_match(stem)
        year_match = _YEAR.search(stem)

        media_type = "tv" if episode_match else "movie"
        season = int(episode_match.group("season")) if episode_match else None
        episode = int(episode_match.group("episode")) if episode_match else None

        title_source = stem
        franchise_title = None
        episode_title = None
        if episode_match:
            raw_episode_title = stem[: episode_match.start()]

            # Episodic media can live under Series, Animation or Documentaries.
            # Prefer the actual programme folder, never the category or
            # Season/Saison folder itself.
            category_tokens = set().union(
                *self._category_folders(settings).values()
            )
            parents = []
            for parent in relative.parts[:-1]:
                if _SEASON_FOLDER.match(parent.strip()):
                    continue
                if self._normalize_folder_name(parent) in category_tokens:
                    continue
                parents.append(parent)
            if parents:
                title_source = parents[-1]

            franchise_source = re.sub(r"[._]+", " ", title_source)
            franchise_title = (
                self._clean_local_title(franchise_source)
                or self._clean_name(title_source)
            )

            episode_source = re.sub(r"[._]+", " ", raw_episode_title)
            episode_source = _YEAR.sub("", episode_source)
            episode_source = self._clean_local_title(episode_source)

            # Common release pattern:
            #   Franchise.Episode.Title.S01E01...
            # Strip the franchise prefix only for display. Catalogue lookup
            # continues to use the franchise/show title.
            if franchise_title and episode_source:
                franchise_fold = franchise_title.casefold()
                episode_fold = episode_source.casefold()
                if episode_fold == franchise_fold:
                    episode_title = None
                elif episode_fold.startswith(franchise_fold + " "):
                    episode_title = episode_source[len(franchise_title):].strip(
                        " -–—_:."
                    )
                elif episode_fold.startswith(franchise_fold + " : "):
                    episode_title = episode_source[len(franchise_title):].strip(
                        " -–—_:."
                    )
                else:
                    episode_title = episode_source
                if not episode_title:
                    episode_title = None

        # Release names commonly use dots/underscores as separators.
        # Normalize them before looking for technical tags so tails such as
        # "_1080p_FR_EN_x264..." are reliably removed.
        title_source = re.sub(r"[._]+", " ", title_source)
        # Some release markers such as "Hybrid" are meaningful words in real
        # titles, so only treat them as release noise when followed by an
        # unmistakable technical/language tag.
        title_source = _CONTEXTUAL_RELEASE_PREFIX.sub("", title_source)
        title_source = _RELEASE_WORDS.sub("", title_source)
        title_source = _YEAR.sub("", title_source)
        title = self._clean_local_title(title_source) or self._clean_name(stem)
        lookup_title = self._lookup_title(title)
        year = int(year_match.group(1)) if year_match else None

        bucket = self._bucket_from_path(relative, settings, media_type)
        if bucket == "series":
            media_type = "tv"

        return {
            "media_key": None,
            "media_type": media_type,
            "bucket": bucket,
            "title": title,
            "lookup_title": lookup_title,
            "year": year,
            "season": season,
            "episode": episode,
            "episodic": bool(episode_match),
            "franchise_title": franchise_title if episode_match else None,
            "episode_title": episode_title if episode_match else None,
        }
