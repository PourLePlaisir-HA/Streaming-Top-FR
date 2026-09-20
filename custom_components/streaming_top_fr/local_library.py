from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
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
    r"bluray|blu[ ._-]?ray|bdrip|brrip|web[ ._-]?dl|webrip|hdtv|remux|"
    r"x26[45]|h\.?26[45]|hevc|av1|aac|ac3|eac3|dts(?:-hd)?|truehd|"
    r"multi|french|vostfr|vf2|vff|vo|proper|repack)\b.*$",
    re.IGNORECASE,
)
_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_EPISODE = re.compile(r"(?i)\bS(?P<season>\d{1,2})[ ._-]*E(?P<episode>\d{1,3})\b")
_EPISODE_ALT = re.compile(r"(?i)\b(?P<season>\d{1,2})x(?P<episode>\d{1,3})\b")


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
            result = await self.hass.async_add_executor_job(self._scan, settings)
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
                    parsed = self._parse_media(path, rel)
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
    def _clean_name(value: str) -> str:
        cleaned = value.replace("_", " ").replace(".", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_.")
        return cleaned

    def _parse_media(self, path: Path, relative: Path) -> dict[str, Any]:
        stem = path.stem
        episode_match = _EPISODE.search(stem) or _EPISODE_ALT.search(stem)
        year_match = _YEAR.search(stem)

        media_type = "tv" if episode_match else "movie"
        season = int(episode_match.group("season")) if episode_match else None
        episode = int(episode_match.group("episode")) if episode_match else None

        title_source = stem
        if episode_match:
            title_source = stem[: episode_match.start()]
            # For TV libraries the parent show directory is usually a better title.
            parents = [p for p in relative.parts[:-1] if not re.match(r"(?i)^season[ ._-]*\d+$", p)]
            if parents:
                title_source = parents[-1]

        title_source = _RELEASE_WORDS.sub("", title_source)
        title_source = _YEAR.sub("", title_source)
        title = self._clean_name(title_source) or self._clean_name(stem)
        year = int(year_match.group(1)) if year_match else None

        bucket = "series" if media_type == "tv" else "movies"
        path_tokens = {part.casefold() for part in relative.parts}
        if any(token in path_tokens for token in {"animation", "animations", "anime", "animes"}):
            bucket = "animation"

        return {
            "media_key": None,
            "media_type": media_type,
            "bucket": bucket,
            "title": title,
            "year": year,
            "season": season,
            "episode": episode,
        }
