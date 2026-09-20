from __future__ import annotations

import asyncio
import csv
import html
import json
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import logging
import re
import unicodedata
from typing import Any
from urllib.parse import quote

from .const import (
    NETFLIX_COUNTRIES_TSV,
    JUSTWATCH_GRAPHQL,
    JUSTWATCH_IMAGE_BASE,
    PROVIDER_NAMES,
    PROVIDER_DEFINITIONS,
    METADATA_CACHE_DAYS,
    METADATA_CACHE_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0 Safari/537.36"
)


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c)).casefold()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def _matching_slug(value: str, media_type: str | None = None) -> str:
    """Normalize harmless catalogue/title variants for matching only."""
    normalized = str(value or "")
    # Treat common conjunction spellings as equivalent for catalogue matching:
    # "Lilo and Stitch", "Lilo & Stitch" and "Lilo et Stitch".
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"(?i)\b(?:and|et)\b", " and ", normalized)
    slug = _slug(normalized)
    if media_type in {"tv", "show"}:
        for suffix in (
            "-la-serie",
            "-la-series",
            "-the-series",
            "-tv-series",
            "-serie",
            "-series",
        ):
            if slug.endswith(suffix) and len(slug) > len(suffix):
                slug = slug[: -len(suffix)].rstrip("-")
                break
    return slug


def _bare_sequel_number(slug: str) -> int | None:
    """Return a terminal sequel number, excluding explicit part/volume labels."""
    parts = [part for part in str(slug or "").split("-") if part]
    if not parts or not parts[-1].isdigit():
        return None
    if len(parts) >= 2 and parts[-2] in {
        "part", "partie", "chapter", "chapitre", "volume", "vol", "tome",
    }:
        return None
    value = int(parts[-1])
    return value if 1 <= value <= 99 else None


def _localized_title_alias(wanted_slug: str, candidate_slug: str) -> bool:
    """Recognize strong original/localized title variants.

    The caller must require an exact release year. This helper only accepts
    either a catalogue title of at least three tokens embedded in the local
    title, or a distinctive shared franchise prefix of at least two tokens.
    """
    wanted = [part for part in str(wanted_slug or "").split("-") if part]
    candidate = [part for part in str(candidate_slug or "").split("-") if part]
    if not wanted or not candidate:
        return False

    # Example:
    # "Indiana Jones and the Raiders of the Lost Ark"
    # -> "Raiders of the Lost Ark".
    if len(candidate) >= 3:
        needle = "-" + "-".join(candidate) + "-"
        haystack = "-" + "-".join(wanted) + "-"
        if needle in haystack:
            return True
    if len(wanted) >= 3:
        needle = "-" + "-".join(wanted) + "-"
        haystack = "-" + "-".join(candidate) + "-"
        if needle in haystack:
            return True

    # Example: original English franchise title vs localized French title
    # where only "Indiana Jones" remains identical.
    if len(wanted) >= 4 and len(candidate) >= 4:
        common = 0
        for left, right in zip(wanted, candidate):
            if left != right:
                break
            common += 1
        if common >= 2:
            prefix_chars = sum(len(part) for part in wanted[:common])
            if prefix_chars >= 8:
                return True

    return False


def _first_installment_base_slug(slug: str) -> str:
    """Return a base title when a filename only adds a first-part label."""
    value = str(slug or "").strip("-")
    for suffix in (
        "-partie-1",
        "-part-1",
        "-part-one",
        "-part-i",
        "-chapitre-1",
        "-chapter-1",
        "-chapter-one",
    ):
        if value.endswith(suffix) and len(value) > len(suffix) + 2:
            return value[: -len(suffix)].rstrip("-")
    return value


def _franchise_prefix_alias(wanted_slug: str, candidate_slug: str) -> bool:
    """Match localized franchise numbering against a descriptive local title.

    Examples:
      "largo-winch-le-prix-de-l-argent" <-> "largo-winch-3"
      "mission-impossible-dead-reckoning" <-> "mission-impossible-7"

    The caller must additionally require an exact release year. We require at
    least two meaningful leading tokens and a numeric sequel marker on one
    side, so this never acts as a generic same-franchise fuzzy match.
    """
    wanted = [p for p in str(wanted_slug or "").split("-") if p]
    candidate = [p for p in str(candidate_slug or "").split("-") if p]
    if len(wanted) < 2 or len(candidate) < 2:
        return False

    common = 0
    for left, right in zip(wanted, candidate):
        if left != right:
            break
        common += 1
    if common < 2:
        return False

    wanted_tail = wanted[common:]
    candidate_tail = candidate[common:]
    has_number = any(part.isdigit() for part in wanted_tail + candidate_tail)
    if not has_number:
        return False

    # One side must be substantially more descriptive than the numbered alias.
    return abs(len(wanted) - len(candidate)) >= 2


def fallback_key(media_type: str, title: str) -> str:
    return f"{media_type}:{_slug(title)}"


def poster_url(raw: str | None) -> str | None:
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if raw.startswith("/"):
        return JUSTWATCH_IMAGE_BASE + raw
    return JUSTWATCH_IMAGE_BASE + "/" + raw


def playback_id_from_url(provider: str, url: str | None) -> str | None:
    """Extract the provider-native content id from a direct offer URL."""
    if not url:
        return None

    if provider == "netflix":
        # Handles netflix.com/title/123, /watch/123 and localized paths such
        # as netflix.com/fr/title/123.
        match = re.search(r"/(?:title|watch)/(\d+)(?:[/?#]|$)", url, re.I)
        return match.group(1) if match else None

    if provider == "disney":
        match = re.search(
            r"entity-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
            url,
            re.I,
        )
        return match.group(1) if match else None

    return None


def normalize_fr_age_certification(value: str | None) -> str | None:
    """Normalize a French age certificate without converting foreign ratings."""
    if value is None:
        return None
    raw = str(value).strip().upper().replace(" ", "")
    aliases = {
        "TP": "TP",
        "TOUTPUBLIC": "TP",
        "TOUSPUBLICS": "TP",
        "ALL": "TP",
        "U": "TP",
        "0": "TP",
        "+0": "TP",
        "-10": "-10",
        "10": "-10",
        "10+": "-10",
        "+10": "-10",
        "-12": "-12",
        "12": "-12",
        "12+": "-12",
        "+12": "-12",
        "-16": "-16",
        "16": "-16",
        "16+": "-16",
        "+16": "-16",
        "-18": "-18",
        "18": "-18",
        "18+": "-18",
        "+18": "-18",
    }
    return aliases.get(raw)


def normalize_us_age_certification(value: str | None) -> str | None:
    """Keep the US certificate as-is; never convert it to a French rating."""
    if value is None:
        return None
    raw = re.sub(r"\s+", "", str(value).strip().upper())
    aliases = {
        "G": "G",
        "PG": "PG",
        "PG-13": "PG-13",
        "PG13": "PG-13",
        "R": "R",
        "NC-17": "NC-17",
        "NC17": "NC-17",
        "TV-Y": "TV-Y",
        "TV-Y7": "TV-Y7",
        "TV-G": "TV-G",
        "TV-PG": "TV-PG",
        "TV-14": "TV-14",
        "TV-MA": "TV-MA",
    }
    return aliases.get(raw)


def _find_imdb_id(value: Any) -> str | None:
    """Find an IMDb title id in a JustWatch detail payload."""
    if isinstance(value, str):
        match = re.search(r"\btt\d{7,10}\b", value, re.I)
        return match.group(0).lower() if match else None
    if isinstance(value, dict):
        for key in ("imdb_id", "imdbId", "imdbID", "imdb"):
            found = _find_imdb_id(value.get(key))
            if found:
                return found
        for child in value.values():
            found = _find_imdb_id(child)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for child in value:
            found = _find_imdb_id(child)
            if found:
                return found
    return None


DISNEY_RESOLUTION_CACHE_HOURS = 24
TOP_CATALOG_CACHE_HOURS = 12
PROVIDER_CACHE_HOURS = 2
JUSTWATCH_BLOCK_MINUTES = 30
IMDB_POSTER_CACHE_DAYS = 90
IMDB_POSTER_BATCH_SIZE = 20

# Family filtering thresholds are selection rules, not rating conversions.
# French certificates remain authoritative when available. US certificates are
# used only as a fallback when enabled in the classification settings.
FAMILY_FR_MIN_AGE = {
    "TP": 0,
    "-10": 10,
    "-12": 12,
    "-16": 16,
    "-18": 18,
}
FAMILY_US_MIN_AGE = {
    "G": 0,
    "PG": 10,
    "PG-13": 13,
    "R": 17,
    "NC-17": 18,
    "TV-Y": 0,
    "TV-Y7": 7,
    "TV-G": 0,
    "TV-PG": 10,
    "TV-14": 14,
    "TV-MA": 17,
}


def _cache_fresh_hours(value: dict[str, Any] | None, hours: int) -> bool:
    if not value or not value.get("cached_at"):
        return False
    try:
        dt = datetime.fromisoformat(value["cached_at"])
    except (TypeError, ValueError):
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - dt < timedelta(hours=max(1, int(hours)))


def _clean_html_text(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"(?is)<(?:script|style)\b.*?</(?:script|style)>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _disney_entity_ids(page: str, wanted_titles: list[str] | None = None) -> list[str]:
    """Extract Disney entity UUID candidates from an SEO/search page.

    Disney pages can expose entity ids either in hrefs or in embedded JSON.
    Search pages are intentionally treated only as candidate generators; every
    candidate is validated against its French entity page before use.
    """
    if not page:
        return []
    normalized = html.unescape(page).replace(r"\/", "/")
    uuid_re = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    out: list[str] = []

    # Prioritise UUIDs physically close to the requested title. Search/catalog
    # pages may contain dozens of unrelated entity hrefs; the relevant result
    # must therefore be placed before the generic href sweep.
    for title in wanted_titles or []:
        if not title:
            continue
        title_fold = html.unescape(str(title)).casefold()
        page_fold = normalized.casefold()
        start = 0
        while True:
            pos = page_fold.find(title_fold, start)
            if pos < 0:
                break
            window = normalized[max(0, pos - 2200): pos + len(title) + 2200]
            for match in re.finditer(uuid_re, window, re.I):
                value = match.group(0).lower()
                if value not in out:
                    out.append(value)
            start = pos + max(1, len(title_fold))

    for match in re.finditer(rf"(?:/fr-fr)?/browse/entity-({uuid_re})", normalized, re.I):
        value = match.group(1).lower()
        if value not in out:
            out.append(value)

    return out[:40]


def _disney_page_title_candidates(page: str) -> list[str]:
    if not page:
        return []
    candidates: list[str] = []
    patterns = (
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r'<h1[^>]*>(.*?)</h1>',
        r'<title[^>]*>(.*?)</title>',
        r'"title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"',
    )
    for pattern in patterns:
        for match in re.finditer(pattern, page, re.I | re.S):
            value = match.group(1)
            try:
                value = bytes(value, "utf-8").decode("unicode_escape") if "\\" in value else value
            except Exception:
                pass
            value = _clean_html_text(value)
            value = re.sub(r"\s*[|–—-]\s*(?:Disney\+|Watch on Disney\+).*$", "", value, flags=re.I).strip()
            value = re.sub(r"^(?:Regarder|Watch)\s+", "", value, flags=re.I).strip()
            if value and value not in candidates:
                candidates.append(value)
            if len(candidates) >= 12:
                return candidates
    return candidates


def _disney_page_unavailable(page: str) -> bool:
    """Detect a Disney entity page that resolves but is unavailable locally."""
    text = _slug(_clean_html_text(page))
    markers = (
        "contenu-n-est-pas-disponible-dans-votre-zone-geographique",
        "contenu-nest-pas-disponible-dans-votre-zone-geographique",
        "indisponible-dans-votre-zone-geographique",
        "content-is-not-available-in-your-region",
        "content-is-not-available-in-your-location",
        "not-available-in-your-region",
        "not-available-in-your-location",
    )
    return any(marker in text for marker in markers)


def _disney_match_score(page: str, wanted_titles: list[str], year: Any = None) -> float:
    candidates = _disney_page_title_candidates(page)
    if not candidates:
        return 0.0

    wanted = [x for x in wanted_titles if x]
    best = 0.0
    for actual in candidates:
        a = _slug(actual)
        if not a:
            continue
        for expected in wanted:
            b = _slug(expected)
            if not b:
                continue
            if a == b:
                score = 1.0
            elif a in b or b in a:
                score = 0.92
            else:
                score = SequenceMatcher(None, a, b).ratio()
            best = max(best, score)

    try:
        wanted_year = int(year) if year not in (None, "") else None
    except (TypeError, ValueError):
        wanted_year = None
    if wanted_year:
        years = {int(x) for x in re.findall(r"\b(?:19|20)\d{2}\b", _clean_html_text(page))}
        if wanted_year in years:
            best += 0.08
        elif years:
            best -= 0.08

    return max(0.0, min(best, 1.08))


def _cache_fresh(value: dict[str, Any] | None) -> bool:
    if not value or not value.get("cached_at"):
        return False

    # v0.2.4: force one metadata refresh for cache entries created by older
    # releases. Those entries often contained poster/title/year but no
    # synopsis/rating, so keeping them for 14 days hid data now requested.
    if value.get("cache_schema") != METADATA_CACHE_SCHEMA:
        return False

    try:
        dt = datetime.fromisoformat(value["cached_at"])
    except (TypeError, ValueError):
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - dt < timedelta(days=METADATA_CACHE_DAYS)


class NetflixOfficialClient:
    """Official weekly Netflix Top 10 for France."""

    def __init__(self, session):
        self.session = session

    async def async_fetch_france(self):
        headers = {"User-Agent": UA, "Accept": "text/tab-separated-values,*/*"}
        movies, tv = [], []
        header = None
        newest_week = None
        buffer = ""

        async with self.session.get(
            NETFLIX_COUNTRIES_TSV, headers=headers, timeout=90
        ) as resp:
            resp.raise_for_status()

            async for chunk in resp.content.iter_chunked(65536):
                buffer += chunk.decode("utf-8", "replace")
                lines = buffer.split("\n")
                buffer = lines.pop()

                for raw in lines:
                    raw = raw.rstrip("\r")
                    if not raw:
                        continue

                    if header is None:
                        header = next(csv.reader([raw], delimiter="\t"))
                        continue

                    vals = next(csv.reader([raw], delimiter="\t"))
                    if len(vals) != len(header):
                        continue

                    row = dict(zip(header, vals))
                    if row.get("country_iso2") != "FR":
                        continue

                    week = row.get("week") or ""
                    if newest_week is None:
                        newest_week = week
                    if week != newest_week:
                        return self._finish(newest_week, movies, tv)

                    cat = (row.get("category") or "").casefold()
                    title = (row.get("show_title") or "").strip()
                    if not title:
                        continue

                    media_type = "movie" if cat.startswith("film") else "tv"
                    subtitle = (row.get("season_title") or "").strip()
                    if subtitle.casefold() in {"n/a", "na", "null", "none", "-"}:
                        subtitle = None

                    item = {
                        "rank": int(row.get("weekly_rank") or 0),
                        "global_rank": int(row.get("weekly_rank") or 0),
                        "title": title,
                        "original_title": title,
                        "subtitle": subtitle or None,
                        "provider": "netflix",
                        "provider_name": "Netflix",
                        "media_type": media_type,
                        "media_key": fallback_key(media_type, title),
                        "poster": None,
                        "description": None,
                        "year": None,
                        "rating": None,
                        "rating_source": None,
                        "age_certification": None,
                        "age_country": None,
                        "age_fr": None,
                        "age_us": None,
                        "imdb_id": None,
                        "days_in_top": int(row.get("cumulative_weeks_in_top_10") or 0),
                        "trend": None,
                        "trend_difference": None,
                        "details_url": "https://www.netflix.com/tudum/top10/france",
                        "watch_url": None,
                        "source": "Netflix Top 10 officiel",
                    }
                    (movies if media_type == "movie" else tv).append(item)

                if newest_week and len(movies) >= 10 and len(tv) >= 10:
                    return self._finish(newest_week, movies, tv)

        return self._finish(newest_week, movies, tv)

    def _finish(self, week, movies, tv):
        movies.sort(key=lambda x: x["rank"])
        tv.sort(key=lambda x: x["rank"])
        return {
            "week": week,
            "movies": movies[:10],
            "tv": tv[:10],
            "error": None if movies or tv else "Aucune ligne France trouvée dans le fichier Netflix.",
            "source_mode": "netflix_official_tsv",
        }


class JustWatchClient:
    """JustWatch client for provider catalog popularity + localized metadata.

    Disney+ and Prime deliberately use provider-specific ``popularTitles`` rather
    than the global Streaming Charts ranking. This yields a meaningful local
    #1..#10 for the selected provider instead of global positions such as #5506.
    """

    PACKAGES_QUERY = r'''
    query Packages($country: Country!, $platform: Platform!) {
      packages(country: $country, platform: $platform) {
        id
        packageId
        clearName
        shortName
        technicalName
      }
    }
    '''

    POPULAR_QUERY = r'''
    query ProviderPopularTitles(
      $country: Country!,
      $language: Language!,
      $filter: TitleFilter,
      $first: Int!
    ) {
      popularTitles(
        country: $country,
        filter: $filter,
        first: $first,
        sortBy: POPULAR
      ) {
        totalCount
        edges {
          node {
            id
            objectId
            objectType
            ... on Movie {
              content(country: $country, language: $language) {
                title
                fullPath
                fullPosterUrl: posterUrl(profile: S166, format: JPG)
                originalReleaseYear
                shortDescription
                externalIds { imdbId }
                scoring {
                  imdbScore
                  jwRating
                  tmdbScore
                }
              }
              offers(country: $country, platform: WEB, filter: { preAffiliate: true }) {
                standardWebURL
                package { shortName clearName }
              }
            }
            ... on Show {
              content(country: $country, language: $language) {
                title
                fullPath
                fullPosterUrl: posterUrl(profile: S166, format: JPG)
                originalReleaseYear
                shortDescription
                externalIds { imdbId }
                scoring {
                  imdbScore
                  jwRating
                  tmdbScore
                }
              }
              offers(country: $country, platform: WEB, filter: { preAffiliate: true }) {
                standardWebURL
                package { shortName clearName }
              }
            }
          }
        }
      }
    }
    '''

    SEARCH_QUERY = r'''
    query SearchStreamingTitle(
      $country: Country!,
      $language: Language!,
      $filter: TitleFilter,
      $first: Int!
    ) {
      popularTitles(
        country: $country,
        filter: $filter,
        first: $first,
        sortBy: POPULAR
      ) {
        edges {
          node {
            id
            objectId
            objectType
            ... on Movie {
              content(country: $country, language: $language) {
                title
                fullPath
                fullPosterUrl: posterUrl(profile: S166, format: JPG)
                originalReleaseYear
                shortDescription
                externalIds { imdbId }
                scoring { imdbScore jwRating tmdbScore }
              }
              offers(country: $country, platform: WEB, filter: { preAffiliate: true }) {
                standardWebURL
                package { shortName clearName }
              }
            }
            ... on Show {
              content(country: $country, language: $language) {
                title
                fullPath
                fullPosterUrl: posterUrl(profile: S166, format: JPG)
                originalReleaseYear
                shortDescription
                externalIds { imdbId }
                scoring { imdbScore jwRating tmdbScore }
              }
              offers(country: $country, platform: WEB, filter: { preAffiliate: true }) {
                standardWebURL
                package { shortName clearName }
              }
            }
          }
        }
      }
    }
    '''


    TOP_CATALOG_QUERY = r'''
    query TopStreamingTitles(
      $popularityCountry: Country!,
      $availabilityCountry: Country!,
      $language: Language!,
      $filter: TitleFilter,
      $first: Int!,
      $sortBy: PopularTitlesSorting!
    ) {
      popularTitles(
        country: $popularityCountry,
        filter: $filter,
        first: $first,
        sortBy: $sortBy
      ) {
        totalCount
        edges {
          node {
            id
            objectId
            objectType
            ... on Movie {
              content(country: $availabilityCountry, language: $language) {
                title
                fullPath
                fullPosterUrl: posterUrl(profile: S166, format: JPG)
                originalReleaseYear
                shortDescription
                runtime
                genres { shortName }
                externalIds { imdbId }
                scoring { imdbScore imdbVotes tmdbScore }
              }
              offers(country: $availabilityCountry, platform: WEB, filter: { preAffiliate: true }) {
                standardWebURL
                monetizationType
                package { shortName clearName }
              }
            }
            ... on Show {
              content(country: $availabilityCountry, language: $language) {
                title
                fullPath
                fullPosterUrl: posterUrl(profile: S166, format: JPG)
                originalReleaseYear
                shortDescription
                runtime
                genres { shortName }
                externalIds { imdbId }
                scoring { imdbScore imdbVotes tmdbScore }
              }
              offers(country: $availabilityCountry, platform: WEB, filter: { preAffiliate: true }) {
                standardWebURL
                monetizationType
                package { shortName clearName }
              }
            }
          }
        }
      }
    }
    '''

    DETAIL_QUERY = r"""
    query StreamingTitleDetail(
      $id: ID!,
      $country: Country!,
      $language: Language!
    ) {
      node(id: $id) {
        id
        objectId
        objectType
        ... on Movie {
          content(country: $country, language: $language) {
            title
            fullPath
            fullPosterUrl: posterUrl(profile: S166, format: JPG)
            originalReleaseYear
            shortDescription
            externalIds { imdbId }
            scoring {
              imdbScore
              jwRating
              tmdbScore
            }
          }
        }
        ... on Show {
          content(country: $country, language: $language) {
            title
            fullPath
            fullPosterUrl: posterUrl(profile: S166, format: JPG)
            originalReleaseYear
            shortDescription
            externalIds { imdbId }
            scoring {
              imdbScore
              jwRating
              tmdbScore
            }
          }
        }
      }
    }
    """

    async def _async_title_detail(self, node_id):
        """Fetch localized detail by JustWatch GraphQL node id.

        Search results normally contain the same content fields, but the
        detail resolver is used as a fallback when shortDescription/scoring
        are absent from the search response.
        """
        if not node_id:
            return None

        payload = {
            "operationName": "StreamingTitleDetail",
            "variables": {
                "id": node_id,
                "country": "FR",
                "language": "fr",
            },
            "query": self.DETAIL_QUERY,
        }

        async with self._sem:
            data = await self._post(payload)

        node = data.get("node") or {}
        return node.get("content") or None

    def __init__(self, session, store=None):
        self.session = session
        self.store = store
        self._sem = asyncio.Semaphore(4)
        self._provider_packages: dict[str, list[str]] | None = None
        self._provider_package_names: dict[str, list[str]] = {}

    async def _async_disney_fetch_page(self, url: str) -> dict[str, str] | None:
        try:
            async with self._sem:
                async with self.session.get(
                    url,
                    headers={
                        "User-Agent": UA,
                        "Accept": "text/html,application/xhtml+xml",
                        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
                        "Referer": "https://www.disneyplus.com/fr-fr",
                    },
                    timeout=15,
                    allow_redirects=True,
                ) as resp:
                    if resp.status >= 400:
                        _LOGGER.debug("Disney+ FR HTTP %s for %s", resp.status, url)
                        return None
                    return {"text": await resp.text(), "url": str(resp.url)}
        except Exception as err:
            _LOGGER.debug("Disney+ FR fetch failed for %s: %s", url, err)
            return None

    async def async_resolve_disney_fr(
        self,
        title: str | None,
        original_title: str | None = None,
        year: Any = None,
        media_type: str | None = None,
        fallback_url: str | None = None,
    ) -> dict[str, Any] | None:
        """Resolve the current Disney+ France entity for a work.

        JustWatch is retained as the France availability source, but its Disney
        deep link can point at a generic/US entity. At launch time we query the
        public French Disney+ web surface, collect candidate entity UUIDs and
        validate the candidates by title/year on their /fr-fr entity page.
        The result is cached for only 24 hours and is therefore disposable.
        """
        wanted_titles: list[str] = []
        for value in (title, original_title):
            value = str(value or "").strip()
            if value and value.casefold() not in {x.casefold() for x in wanted_titles}:
                wanted_titles.append(value)
        if not wanted_titles:
            return None

        cache_key = (
            f"disney-fr-v1:{media_type or 'title'}:{year or ''}:"
            f"{_slug(wanted_titles[0])}"
        )
        if self.store:
            cached = self.store.get_metadata(cache_key)
            if _cache_fresh_hours(cached, DISNEY_RESOLUTION_CACHE_HOURS):
                if cached.get("watch_url") and cached.get("playback_id"):
                    return cached

        candidate_ids: list[str] = []

        def add_candidate(value: str | None) -> None:
            if not value:
                return
            value = value.lower()
            if value not in candidate_ids:
                candidate_ids.append(value)

        # First try the JustWatch UUID on the French route. This is cheap and
        # handles titles whose entity id is already region-compatible.
        fallback_id = playback_id_from_url("disney", fallback_url)
        add_candidate(fallback_id)

        # Disney's public search surface is used only to discover candidates.
        # Every UUID is subsequently checked against its French public page.
        search_urls: list[str] = []
        for query in wanted_titles:
            encoded = quote(query.strip(), safe="")
            search_urls.extend(
                [
                    f"https://www.disneyplus.com/fr-fr/search/{encoded}",
                    f"https://www.disneyplus.com/fr-fr/search?q={encoded}",
                    f"https://www.disneyplus.com/search/{encoded}",
                ]
            )

        search_pages = await asyncio.gather(
            *(self._async_disney_fetch_page(url) for url in search_urls),
            return_exceptions=True,
        )
        for page in search_pages:
            if isinstance(page, Exception) or not page:
                continue
            for entity_id in _disney_entity_ids(page.get("text") or "", wanted_titles):
                add_candidate(entity_id)

        # SEO landing pages expose many catalogue cards and are a useful
        # fallback when the /search route requires an authenticated session.
        if len(candidate_ids) <= (1 if fallback_id else 0):
            for landing in (
                "https://www.disneyplus.com/fr-fr",
                "https://www.disneyplus.com/fr-fr/browse/page-fceac21e-c678-45ec-bfa8-a9b60b45a086",
                "https://www.disneyplus.com/fr-fr/browse/page-bceb41c9-cfa9-41e3-b6d7-d547362ea1cd",
            ):
                page = await self._async_disney_fetch_page(landing)
                if not page:
                    continue
                for entity_id in _disney_entity_ids(page.get("text") or "", wanted_titles):
                    add_candidate(entity_id)
                if len(candidate_ids) > (1 if fallback_id else 0):
                    break

        if not candidate_ids:
            return None

        # Validate only a bounded set. A French page with an exact title/year
        # match wins; generic/US ids that fail on /fr-fr are discarded.
        urls = [
            f"https://www.disneyplus.com/fr-fr/browse/entity-{entity_id}"
            for entity_id in candidate_ids[:16]
        ]
        pages = await asyncio.gather(
            *(self._async_disney_fetch_page(url) for url in urls),
            return_exceptions=True,
        )

        best: tuple[float, str, str] | None = None
        for entity_id, url, page in zip(candidate_ids[:16], urls, pages):
            if isinstance(page, Exception) or not page:
                continue
            final_url = str(page.get("url") or "")
            if "/fr-fr/" not in final_url.casefold():
                _LOGGER.debug(
                    "Disney+ FR candidate %s rejected after redirect to %s",
                    entity_id, final_url,
                )
                continue
            page_text = page.get("text") or ""
            if _disney_page_unavailable(page_text):
                _LOGGER.debug(
                    "Disney+ FR candidate %s rejected: local-unavailability page",
                    entity_id,
                )
                continue
            score = _disney_match_score(page_text, wanted_titles, year)
            _LOGGER.debug(
                "Disney+ FR candidate %s score %.3f for %s (%s)",
                entity_id, score, wanted_titles[0], year,
            )
            if best is None or score > best[0]:
                best = (score, entity_id, url)

        if not best or best[0] < 0.78:
            _LOGGER.warning(
                "Disney+ FR resolver: no safe match for %s (%s); candidates=%s",
                wanted_titles[0], year, candidate_ids[:16],
            )
            return None

        result = {
            "provider": "disney",
            "provider_name": "Disney+",
            "region": "FR",
            "playback_id": best[1],
            "watch_url": best[2],
            "resolved_from": "disney_fr_public_catalog",
            "match_score": round(best[0], 3),
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.store:
            self.store.set_metadata(cache_key, result)
            await self.store.async_save()
        return result

    async def _post(self, payload):
        async with self.session.post(
            JUSTWATCH_GRAPHQL,
            json=payload,
            headers={
                "User-Agent": UA,
                "Origin": "https://www.justwatch.com",
                "Referer": "https://www.justwatch.com/fr/",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30,
        ) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"JustWatch HTTP {resp.status}: {text[:500]}")
            data = await resp.json()

        if data.get("errors"):
            raise RuntimeError(data["errors"][0].get("message", "Erreur GraphQL"))
        return data.get("data") or {}

    async def _async_imdb_id(self, title, year=None, media_type=None):
        """Resolve a title to a canonical IMDb id using IMDb autocomplete."""
        if not title:
            return None
        cache_key = f"imdb-id:{media_type or 'title'}:{year or ''}:{_slug(title)}"
        if self.store:
            cached = self.store.get_metadata(cache_key)
            if _cache_fresh(cached) and cached.get("imdb_id"):
                return cached.get("imdb_id")

        imdb_id = None
        try:
            url = (
                "https://v3.sg.media-imdb.com/suggestion/titles/x/"
                + quote(str(title).strip().lower(), safe="")
                + ".json"
            )
            async with self._sem:
                async with self.session.get(
                    url,
                    headers={"User-Agent": UA, "Accept": "application/json"},
                    timeout=20,
                ) as resp:
                    if resp.status < 400:
                        data = await resp.json()
                        hits = [
                            h for h in (data.get("d") or [])
                            if str(h.get("id") or "").startswith("tt")
                        ]

                        want_year = None
                        try:
                            want_year = int(year) if year else None
                        except (TypeError, ValueError):
                            pass
                        want_title = _slug(str(title))
                        want_tv = media_type in ("tv", "show")

                        def score(hit):
                            points = 0
                            hit_title = _slug(str(hit.get("l") or ""))
                            hit_year = hit.get("y")
                            qid = str(hit.get("qid") or "").lower()
                            if hit_title == want_title:
                                points += 8
                            elif want_title and (want_title in hit_title or hit_title in want_title):
                                points += 3
                            if want_year and hit_year == want_year:
                                points += 6
                            elif want_year and isinstance(hit_year, int) and abs(hit_year - want_year) <= 1:
                                points += 2
                            is_tv = qid in {"tvseries", "tvminiseries", "tvepisode", "tvmovie"}
                            if want_tv == is_tv:
                                points += 3
                            return points

                        if hits:
                            best = max(hits, key=score)
                            # Require at least a plausible title/type/year match.
                            if score(best) >= 3:
                                imdb_id = best.get("id")
                    else:
                        _LOGGER.debug("IMDb suggestion HTTP %s for %s", resp.status, title)
        except Exception as err:
            _LOGGER.debug("IMDb suggestion failed for %s: %s", title, err)

        if self.store:
            self.store.set_metadata(
                cache_key,
                {
                    "imdb_id": imdb_id,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "cache_schema": METADATA_CACHE_SCHEMA,
                },
            )
        return imdb_id

    @staticmethod
    def _normalize_imdb_id(imdb_id):
        value = str(imdb_id or "").strip().lower()
        return value if re.fullmatch(r"tt\d{7,10}", value) else None

    async def _async_imdb_local_detail(self, imdb_id):
        """Fetch poster + basic metadata for a verified local IMDb id."""
        imdb_id = self._normalize_imdb_id(imdb_id)
        if not imdb_id:
            return None

        cache_key = f"imdb-local-detail-v1:{imdb_id}"
        if self.store:
            cached = self.store.get_metadata(cache_key)
            if _cache_fresh_hours(cached, IMDB_POSTER_CACHE_DAYS * 24):
                return cached

        query = f"""
        query LocalTitleDetail {{
          title(id: "{imdb_id}") {{
            titleText {{ text }}
            releaseYear {{ year }}
            primaryImage {{ url width height }}
            ratingsSummary {{ aggregateRating voteCount }}
            plot {{ plotText {{ plainText }} }}
          }}
        }}
        """
        try:
            async with self._sem:
                async with self.session.post(
                    "https://caching.graphql.imdb.com/",
                    json={"query": query},
                    headers={
                        "User-Agent": UA,
                        "Accept": "application/graphql+json, application/json",
                        "Content-Type": "application/json",
                        "Origin": "https://www.imdb.com",
                        "Referer": "https://www.imdb.com/",
                        "x-imdb-client-name": "imdb-web-next",
                        "x-imdb-user-language": "fr-FR",
                        "x-imdb-user-country": "FR",
                    },
                    timeout=25,
                ) as resp:
                    if resp.status >= 400:
                        _LOGGER.debug(
                            "IMDb local detail HTTP %s for %s", resp.status, imdb_id
                        )
                        return None
                    payload = await resp.json()
        except Exception as err:
            _LOGGER.debug("IMDb local detail failed for %s: %s", imdb_id, err)
            return None

        title_data = ((payload.get("data") or {}).get("title") or {})
        image = title_data.get("primaryImage") or {}
        ratings = title_data.get("ratingsSummary") or {}
        plot = ((title_data.get("plot") or {}).get("plotText") or {})
        result = {
            "imdb_id": imdb_id,
            "title": ((title_data.get("titleText") or {}).get("text") or None),
            "year": ((title_data.get("releaseYear") or {}).get("year") or None),
            "poster": image.get("url"),
            "rating": ratings.get("aggregateRating"),
            "imdb_votes": ratings.get("voteCount"),
            "description": plot.get("plainText"),
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "cache_schema": METADATA_CACHE_SCHEMA,
        }
        if result["poster"] and not str(result["poster"]).startswith(("http://", "https://")):
            result["poster"] = None

        if self.store:
            self.store.set_metadata(cache_key, result)
        return result

    async def _async_imdb_posters(self, imdb_ids):
        """Return IMDb primary poster URLs keyed by canonical IMDb id.

        Posters are cached independently by IMDb id for 90 days. Requests are
        batched through IMDb GraphQL so a Top 100 does not generate 100 HTTP
        requests. A transient IMDb failure is never cached as a negative result;
        callers simply keep their JustWatch poster fallback for that refresh.
        """
        wanted = []
        for raw in imdb_ids or []:
            imdb_id = self._normalize_imdb_id(raw)
            if imdb_id and imdb_id not in wanted:
                wanted.append(imdb_id)
        if not wanted:
            return {}

        results = {}
        unresolved = []
        for imdb_id in wanted:
            cache_key = f"imdb-poster-v1:{imdb_id}"
            cached = self.store.get_metadata(cache_key) if self.store else None
            if _cache_fresh_hours(cached, IMDB_POSTER_CACHE_DAYS * 24):
                results[imdb_id] = cached.get("poster")
            else:
                unresolved.append(imdb_id)

        for start in range(0, len(unresolved), IMDB_POSTER_BATCH_SIZE):
            chunk = unresolved[start : start + IMDB_POSTER_BATCH_SIZE]
            aliases = []
            alias_map = {}
            for index, imdb_id in enumerate(chunk):
                alias = f"p{index}"
                alias_map[alias] = imdb_id
                aliases.append(
                    f'{alias}: title(id: "{imdb_id}") {{ primaryImage {{ url width height }} }}'
                )
            query = "query TitlePosters {\n" + "\n".join(aliases) + "\n}"
            try:
                async with self._sem:
                    async with self.session.post(
                        "https://caching.graphql.imdb.com/",
                        json={"query": query},
                        headers={
                            "User-Agent": UA,
                            "Accept": "application/graphql+json, application/json",
                            "Content-Type": "application/json",
                            "Origin": "https://www.imdb.com",
                            "Referer": "https://www.imdb.com/",
                            "x-imdb-client-name": "imdb-web-next",
                            "x-imdb-user-language": "fr-FR",
                            "x-imdb-user-country": "FR",
                        },
                        timeout=25,
                    ) as resp:
                        if resp.status >= 400:
                            _LOGGER.debug(
                                "IMDb poster HTTP %s for %s",
                                resp.status,
                                ",".join(chunk),
                            )
                            continue
                        payload = await resp.json()
                data = payload.get("data") or {}
                now = datetime.now(timezone.utc).isoformat()
                for alias, imdb_id in alias_map.items():
                    title_data = data.get(alias) or {}
                    image = title_data.get("primaryImage") or {}
                    poster = image.get("url")
                    if poster and not str(poster).startswith(("http://", "https://")):
                        poster = None
                    results[imdb_id] = poster
                    if self.store:
                        self.store.set_metadata(
                            f"imdb-poster-v1:{imdb_id}",
                            {
                                "poster": poster,
                                "width": image.get("width"),
                                "height": image.get("height"),
                                "cached_at": now,
                                "cache_schema": METADATA_CACHE_SCHEMA,
                            },
                        )
            except Exception as err:
                _LOGGER.debug(
                    "IMDb poster batch failed for %s: %s", ",".join(chunk), err
                )

        return results

    async def async_enrich_imdb_posters(self, items):
        """Make IMDb the canonical poster source for a list of work items.

        JustWatch remains the fallback when IMDb has no usable primary image or
        is temporarily unavailable. Missing IMDb ids are resolved by title/year.
        The input dictionaries are updated in place and also returned.
        """
        works = [item for item in (items or []) if isinstance(item, dict)]
        if not works:
            return works

        missing = [
            item for item in works
            if not self._normalize_imdb_id(item.get("imdb_id"))
        ]
        if missing:
            resolved = await asyncio.gather(
                *(
                    self._async_imdb_id(
                        item.get("title") or item.get("original_title"),
                        item.get("year"),
                        item.get("media_type"),
                    )
                    for item in missing
                ),
                return_exceptions=True,
            )
            for item, imdb_id in zip(missing, resolved):
                if isinstance(imdb_id, Exception):
                    continue
                imdb_id = self._normalize_imdb_id(imdb_id)
                if imdb_id:
                    item["imdb_id"] = imdb_id

        poster_map = await self._async_imdb_posters(
            [item.get("imdb_id") for item in works]
        )
        for item in works:
            imdb_id = self._normalize_imdb_id(item.get("imdb_id"))
            imdb_poster = poster_map.get(imdb_id) if imdb_id else None
            if imdb_poster:
                item["poster"] = imdb_poster
                item["poster_source"] = "imdb"
            elif item.get("poster"):
                # Preserve an already canonical IMDb poster. Otherwise record
                # that this refresh is using the JustWatch safety fallback.
                if item.get("poster_source") != "imdb":
                    item["poster_source"] = "justwatch"
            else:
                item["poster_source"] = None
        return works

    async def _async_imdb_certificates(self, imdb_id):
        """Return IMDb parental-guide certificates keyed by country.

        The simple ``title.certificate`` field exposes the title's primary
        certificate (often US) and is not a reliable way to ask for France.
        We therefore query IMDb's parental-guide certificate list and select
        FR first, US only as fallback.
        """
        if not imdb_id:
            return {}

        cache_key = f"imdb-certs-v2:{imdb_id}"
        if self.store:
            cached = self.store.get_metadata(cache_key)
            if _cache_fresh(cached):
                certs = cached.get("certificates")
                if isinstance(certs, dict):
                    return certs

        certs: dict[str, str] = {}

        # IMDb web app parental-guide persisted query. It returns every
        # country certificate for the title, allowing us to distinguish a
        # genuine French certificate from the US MPA rating.
        params = {
            "operationName": "TitleParentalGuideCertificates",
            "variables": json.dumps(
                {"locale": "en-US", "tconst": imdb_id, "total": 80},
                separators=(",", ":"),
            ),
            "extensions": json.dumps(
                {
                    "persistedQuery": {
                        "sha256Hash": "c0cf0d516020be5e214f0cd149fe256d16e5753f817bcefdb586aedef2a3c14b",
                        "version": 1,
                    }
                },
                separators=(",", ":"),
            ),
        }
        try:
            async with self._sem:
                async with self.session.get(
                    "https://caching.graphql.imdb.com/",
                    params=params,
                    headers={
                        "User-Agent": UA,
                        "Accept": "application/graphql+json, application/json",
                        "Origin": "https://www.imdb.com",
                        "Referer": "https://www.imdb.com/",
                        "x-imdb-client-name": "imdb-web-next",
                        "x-imdb-user-language": "en-US",
                        "x-imdb-user-country": "US",
                    },
                    timeout=20,
                ) as resp:
                    if resp.status < 400:
                        payload = await resp.json()
                        title_data = ((payload.get("data") or {}).get("title") or {})
                        edges = ((title_data.get("certificates") or {}).get("edges") or [])
                        for edge in edges:
                            node = (edge or {}).get("node") or {}
                            rating = str(node.get("rating") or "").strip()
                            country = node.get("country") or {}
                            country_parts = {
                                str(country.get("id") or "").strip().upper(),
                                str(country.get("code") or "").strip().upper(),
                                str(country.get("text") or "").strip().upper(),
                                str(country.get("name") or "").strip().upper(),
                            }
                            if not rating:
                                continue
                            if country_parts & {"FR", "FRA", "FRANCE"}:
                                certs.setdefault("FR", rating)
                            if country_parts & {
                                "US",
                                "USA",
                                "UNITED STATES",
                                "UNITED STATES OF AMERICA",
                            }:
                                certs.setdefault("US", rating)
                    else:
                        _LOGGER.debug(
                            "IMDb parental certificates HTTP %s for %s",
                            resp.status,
                            imdb_id,
                        )
        except Exception as err:
            _LOGGER.debug(
                "IMDb parental certificates failed for %s: %s", imdb_id, err
            )

        # HTML fallback: useful if IMDb changes/rejects the persisted query.
        if "FR" not in certs or "US" not in certs:
            try:
                async with self._sem:
                    async with self.session.get(
                        f"https://www.imdb.com/title/{imdb_id}/parentalguide/",
                        headers={
                            "User-Agent": UA,
                            "Accept": "text/html,application/xhtml+xml",
                            "Accept-Language": "en-US,en;q=0.9",
                        },
                        timeout=20,
                    ) as resp:
                        if resp.status < 400:
                            page = await resp.text()
                            section_match = re.search(
                                r'data-testid="certificates-container"(.*?)(?:</section>|<footer)',
                                page,
                                re.I | re.S,
                            )
                            section = section_match.group(0) if section_match else page
                            for block in re.split(
                                r'(?=data-testid="certificates-item")', section
                            ):
                                if "certificates-item" not in block:
                                    continue
                                cm = re.search(
                                    r'ipc-metadata-list-item__label[^>]*>([^<]+)',
                                    block,
                                    re.I,
                                )
                                if not cm:
                                    continue
                                country_name = html.unescape(cm.group(1)).strip().upper()
                                rm = re.search(
                                    r'ipc-metadata-list-item__list-content-item--link[^>]*>([^<]+)</a>',
                                    block,
                                    re.I | re.S,
                                )
                                if not rm:
                                    continue
                                rating = html.unescape(rm.group(1)).strip()
                                if country_name == "FRANCE":
                                    certs.setdefault("FR", rating)
                                elif country_name in {
                                    "UNITED STATES",
                                    "UNITED STATES OF AMERICA",
                                }:
                                    certs.setdefault("US", rating)
            except Exception as err:
                _LOGGER.debug(
                    "IMDb parental HTML fallback failed for %s: %s", imdb_id, err
                )

        # Last-resort US primary certificate. This is intentionally used only
        # for US fallback, never as a fake French certificate.
        if "US" not in certs:
            query = """
            query TitleCertificate($id: ID!) {
              title(id: $id) {
                certificate { rating }
              }
            }
            """
            try:
                async with self._sem:
                    async with self.session.post(
                        "https://caching.graphql.imdb.com/",
                        json={"query": query, "variables": {"id": imdb_id}},
                        headers={
                            "User-Agent": UA,
                            "Accept": "application/graphql+json, application/json",
                            "Content-Type": "application/json",
                            "Origin": "https://www.imdb.com",
                            "Referer": "https://www.imdb.com/",
                            "x-imdb-client-name": "imdb-web-next",
                            "x-imdb-user-language": "en-US",
                            "x-imdb-user-country": "US",
                        },
                        timeout=20,
                    ) as resp:
                        if resp.status < 400:
                            payload = await resp.json()
                            title_data = ((payload.get("data") or {}).get("title") or {})
                            primary = (title_data.get("certificate") or {}).get("rating")
                            if primary:
                                certs["US"] = primary
            except Exception as err:
                _LOGGER.debug("IMDb primary US certificate failed for %s: %s", imdb_id, err)

        if self.store:
            self.store.set_metadata(
                cache_key,
                {
                    "certificates": certs,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "cache_schema": METADATA_CACHE_SCHEMA,
                },
            )
        return certs

    @staticmethod
    def select_age(age_info, classification):
        """Select the displayed certificate according to the user policy."""
        classification = classification or {}
        if not classification.get("enabled", True):
            return None, None

        fr = (age_info or {}).get("fr")
        us = (age_info or {}).get("us")

        if fr:
            if classification.get("france", True):
                return fr, "FR"
            # US is a fallback only when no French certificate exists, not a
            # replacement for a deliberately hidden French certificate.
            return None, None

        if classification.get("us_fallback", True) and us:
            if str(us).upper().startswith("TV-") and not classification.get("us_tv", True):
                return None, None
            return us, "US"

        return None, None

    async def _async_age_certification(
        self, object_id, media_type, details_url=None, title=None, year=None
    ):
        """Resolve both FR and US age classifications without conversion."""
        kind = "movie" if media_type == "movie" else "show"
        cache_id = object_id if object_id is not None else details_url or title or "unknown"
        cache_key = f"age-v3:{kind}:{cache_id}"
        if self.store:
            cached = self.store.get_metadata(cache_key)
            if _cache_fresh(cached):
                return {
                    "fr": cached.get("age_fr"),
                    "us": cached.get("age_us"),
                    "imdb_id": cached.get("imdb_id"),
                }

        jw_fr_age = None
        imdb_id = None

        # JustWatch can expose a French age rating and sometimes the canonical IMDb id.
        if object_id is not None:
            url = (
                f"https://apis.justwatch.com/content/titles/{kind}/{object_id}"
                "/locale/fr_FR"
            )
            try:
                async with self._sem:
                    async with self.session.get(
                        url,
                        headers={
                            "User-Agent": UA,
                            "Accept": "application/json",
                            "Referer": "https://www.justwatch.com/fr/",
                        },
                        timeout=20,
                    ) as resp:
                        if resp.status < 400:
                            data = await resp.json()
                            imdb_id = _find_imdb_id(data)
                            jw_fr_age = normalize_fr_age_certification(
                                data.get("age_certification")
                                or data.get("ageCertification")
                            )
                        else:
                            _LOGGER.debug(
                                "JustWatch detail HTTP %s for %s/%s",
                                resp.status, kind, object_id,
                            )
            except Exception as err:
                _LOGGER.debug(
                    "JustWatch detail failed for %s/%s: %s", kind, object_id, err
                )

        # French JustWatch public-page fallback.
        if not jw_fr_age and details_url:
            try:
                async with self._sem:
                    async with self.session.get(
                        details_url,
                        headers={
                            "User-Agent": UA,
                            "Accept": "text/html,application/xhtml+xml",
                            "Accept-Language": "fr-FR,fr;q=0.9",
                            "Referer": "https://www.justwatch.com/fr/",
                        },
                        timeout=20,
                    ) as resp:
                        if resp.status < 400:
                            page = await resp.text()
                            match = re.search(
                                r'"(?:ageCertification|age_certification)"\s*:\s*"([^"]+)"',
                                page, re.I,
                            )
                            if match:
                                jw_fr_age = normalize_fr_age_certification(match.group(1))
                            if not jw_fr_age:
                                cleaned = re.sub(
                                    r"(?is)<(?:script|style)\b.*?</(?:script|style)>",
                                    " ", page,
                                )
                                cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
                                cleaned = html.unescape(cleaned)
                                cleaned = re.sub(r"\s+", " ", cleaned)
                                match = re.search(
                                    r"\b(TP|10|12|16|18)\s+Âge\b", cleaned, re.I
                                )
                                if match:
                                    jw_fr_age = normalize_fr_age_certification(match.group(1))
            except Exception as err:
                _LOGGER.debug(
                    "JustWatch French age fallback failed for %s: %s", details_url, err
                )

        if not imdb_id:
            imdb_id = await self._async_imdb_id(title, year, media_type)

        imdb_certs = await self._async_imdb_certificates(imdb_id) if imdb_id else {}
        imdb_fr = normalize_fr_age_certification(imdb_certs.get("FR")) if imdb_certs else None
        imdb_us = normalize_us_age_certification(imdb_certs.get("US")) if imdb_certs else None

        # IMDb France has priority, with JustWatch France as fallback.
        fr_age = imdb_fr or jw_fr_age
        us_age = imdb_us

        result = {"fr": fr_age, "us": us_age, "imdb_id": imdb_id}
        if self.store:
            self.store.set_metadata(
                cache_key,
                {
                    "age_fr": fr_age,
                    "age_us": us_age,
                    "imdb_id": imdb_id,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "cache_schema": METADATA_CACHE_SCHEMA,
                },
            )
        return result


    @staticmethod
    def _provider_name_key(value):
        value = unicodedata.normalize("NFKD", str(value or ""))
        value = "".join(c for c in value if not unicodedata.combining(c)).casefold()
        return re.sub(r"[^a-z0-9]+", "", value)

    async def async_resolve_provider_packages(self, force=False):
        if self._provider_packages is not None and not force:
            return self._provider_packages

        payload = {
            "operationName": "Packages",
            "variables": {"country": "FR", "platform": "WEB"},
            "query": self.PACKAGES_QUERY,
        }
        data = await self._post(payload)
        packages = data.get("packages") or []

        resolved = {provider: [] for provider in PROVIDER_DEFINITIONS}
        names = {provider: [] for provider in PROVIDER_DEFINITIONS}
        alias_keys = {
            provider: {
                self._provider_name_key(alias)
                for alias in definition.get("aliases", [])
            }
            for provider, definition in PROVIDER_DEFINITIONS.items()
        }

        for pkg in packages:
            clear = str(pkg.get("clearName") or "").strip()
            short = str(pkg.get("shortName") or "").strip()
            tech = str(pkg.get("technicalName") or "").strip()
            if not short:
                continue

            clear_key = self._provider_name_key(clear)
            tech_key = self._provider_name_key(tech)
            for provider, aliases in alias_keys.items():
                if clear_key in aliases or tech_key in aliases:
                    resolved[provider].append(short)
                    names[provider].append(clear or tech)
                    break

        # Defensive fallbacks only where the JustWatch short code is known.
        for provider, definition in PROVIDER_DEFINITIONS.items():
            if not resolved[provider]:
                resolved[provider] = list(definition.get("fallback_codes", []))

        # Preserve order but deduplicate aliases/plans.
        for provider in resolved:
            resolved[provider] = list(dict.fromkeys(resolved[provider]))
            names[provider] = list(dict.fromkeys(n for n in names[provider] if n))

        self._provider_packages = resolved
        self._provider_package_names = names
        _LOGGER.info("JustWatch FR packages resolved: %s", resolved)
        return resolved

    def package_names(self, provider):
        return self._provider_package_names.get(provider, [])

    @staticmethod
    def _rating(content):
        scoring = content.get("scoring") or {}
        if scoring.get("imdbScore") is not None:
            return scoring.get("imdbScore"), "IMDb"
        if scoring.get("tmdbScore") is not None:
            return scoring.get("tmdbScore"), "TMDB"
        return None, None

    @staticmethod
    def _watch_url(node, package_codes):
        codes = {c.casefold() for c in package_codes}
        for offer in node.get("offers") or []:
            pkg = offer.get("package") or {}
            if str(pkg.get("shortName") or "").casefold() in codes:
                if offer.get("standardWebURL"):
                    return offer["standardWebURL"]
        return None

    def _provider_offers(self, node):
        """Return provider-specific offer/playback metadata for one JustWatch work."""
        packages = self._provider_packages or {}
        offers = node.get("offers") or []
        result = {}
        for provider, package_codes in packages.items():
            codes = {str(code).casefold() for code in (package_codes or [])}
            if not codes:
                continue
            url = None
            matched = False
            for offer in offers:
                monetization = str(offer.get("monetizationType") or "").upper()
                if monetization and monetization not in {"FLATRATE", "FLATRATE_AND_BUY", "ADS", "FREE"}:
                    continue
                pkg = offer.get("package") or {}
                if str(pkg.get("shortName") or "").casefold() in codes:
                    matched = True
                    if not url and offer.get("standardWebURL"):
                        url = offer.get("standardWebURL")
            if matched:
                result[provider] = {
                    "provider": provider,
                    "provider_name": PROVIDER_NAMES.get(provider, provider),
                    "watch_url": url,
                    "playback_id": playback_id_from_url(provider, url),
                }
        return result

    async def _async_provider_candidates(self, provider, media_type, first):
        """Fetch a provider-local popularity slice from JustWatch."""
        packages = await self.async_resolve_provider_packages()
        package_codes = packages.get(provider) or []
        if not package_codes:
            raise RuntimeError(
                f"{PROVIDER_NAMES.get(provider, provider)} introuvable dans les services JustWatch France"
            )
        object_type = "MOVIE" if media_type == "movie" else "SHOW"

        payload = {
            "operationName": "ProviderPopularTitles",
            "variables": {
                "country": "FR",
                "language": "fr",
                "first": int(first),
                "filter": {
                    "objectTypes": [object_type],
                    "packages": package_codes,
                },
            },
            "query": self.POPULAR_QUERY,
        }
        data = await self._post(payload)
        edges = ((data.get("popularTitles") or {}).get("edges") or [])

        out = []
        seen = set()
        for edge in edges:
            node = edge.get("node") or {}
            if node.get("objectType") != object_type:
                continue
            content = node.get("content") or {}
            title = (content.get("title") or "").strip()
            if not title:
                continue

            oid = node.get("objectId")
            key = f"jw:{oid}" if oid is not None else fallback_key(media_type, title)
            if key in seen:
                continue
            seen.add(key)

            full_path = content.get("fullPath")
            rating, rating_source = self._rating(content)
            watch_url = self._watch_url(node, package_codes)
            ext = content.get("externalIds") or {}
            jw_poster = poster_url(content.get("fullPosterUrl"))
            out.append(
                {
                    "rank": len(out) + 1,
                    "global_rank": None,
                    "title": title,
                    "original_title": None,
                    "subtitle": None,
                    "provider": provider,
                    "provider_name": PROVIDER_NAMES[provider],
                    "media_type": media_type,
                    "media_key": key,
                    "poster": jw_poster,
                    "poster_source": "justwatch" if jw_poster else None,
                    "description": content.get("shortDescription"),
                    "year": content.get("originalReleaseYear"),
                    "rating": rating,
                    "rating_source": rating_source,
                    "age_certification": None,
                    "age_country": None,
                    "age_fr": None,
                    "age_us": None,
                    "imdb_id": ext.get("imdbId"),
                    "_jw_object_id": oid,
                    "days_in_top": None,
                    "trend": None,
                    "trend_difference": None,
                    "details_url": (
                        "https://www.justwatch.com" + full_path if full_path else None
                    ),
                    "watch_url": watch_url,
                    "playback_id": playback_id_from_url(provider, watch_url),
                    "providers": self._provider_offers(node),
                    "source": "JustWatch popularité plateforme",
                }
            )
        return out

    @staticmethod
    def _top_catalog_weighted_rank(items):
        """Rank quality inside a market-popularity pool using IMDb confidence.

        French-popularity candidates always remain ahead of US fallback
        candidates. IMDb score + vote volume only re-order works inside each
        market tier, so worldwide IMDb enthusiasm cannot define French relevance.
        """
        usable = [
            x for x in items
            if isinstance(x.get("rating"), (int, float))
            and isinstance(x.get("imdb_votes"), (int, float))
            and x.get("imdb_votes", 0) > 0
        ]
        if not usable:
            return []

        groups = {}
        for item in usable:
            market = str(item.get("popularity_market") or "FR").upper()
            groups.setdefault(market, []).append(item)

        for market, group in groups.items():
            ratings = [float(x["rating"]) for x in group]
            votes = sorted(float(x["imdb_votes"]) for x in group)
            c = sum(ratings) / len(ratings)
            idx = min(len(votes) - 1, max(0, int(round((len(votes) - 1) * 0.60))))
            m = max(1000.0, votes[idx])
            for item in group:
                r = float(item["rating"])
                v = float(item["imdb_votes"])
                item["ranking_score"] = round((v / (v + m)) * r + (m / (v + m)) * c, 4)
                item["ranking_prior"] = round(c, 4)
                item["ranking_vote_threshold"] = int(m)
                item["ranking_market"] = market

        priority = {"FR": 0, "US": 1}
        usable.sort(
            key=lambda x: (
                priority.get(str(x.get("popularity_market") or "FR").upper(), 9),
                -float(x.get("ranking_score") or 0),
                -int(x.get("imdb_votes") or 0),
                -float(x.get("rating") or 0),
            )
        )
        return usable

    async def _async_top_popular_edges(
        self,
        popularity_country,
        availability_country,
        title_filter,
        first,
    ):
        """Fetch POPULAR in one market while resolving content/offers in FR."""
        attempts = []
        base = dict(title_filter or {})
        attempts.append(("POPULAR", base))
        if "monetizationTypes" in base:
            relaxed = dict(base)
            relaxed.pop("monetizationTypes", None)
            attempts.append(("POPULAR_LOCAL_OFFER_FALLBACK", relaxed))
        if "genres" in base or "excludeGenres" in base:
            relaxed = dict(attempts[-1][1])
            relaxed.pop("genres", None)
            relaxed.pop("excludeGenres", None)
            attempts.append(("POPULAR_LOCAL_CATEGORY_FALLBACK", relaxed))

        last_error = None
        seen_signatures = set()
        for mode, current_filter in attempts:
            signature = repr(current_filter)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            payload = {
                "operationName": "TopStreamingTitles",
                "variables": {
                    "popularityCountry": str(popularity_country).upper(),
                    "availabilityCountry": str(availability_country).upper(),
                    "language": "fr",
                    "first": int(first),
                    "filter": current_filter,
                    "sortBy": "POPULAR",
                },
                "query": self.TOP_CATALOG_QUERY,
            }
            try:
                async with self._sem:
                    data = await self._post(payload)
                return ((data.get("popularTitles") or {}).get("edges") or []), mode
            except Exception as err:
                last_error = err
                _LOGGER.debug(
                    "JustWatch Top POPULAR %s (%s->%s) failed: %s",
                    mode,
                    popularity_country,
                    availability_country,
                    err,
                )
        if last_error:
            raise last_error
        return [], "POPULAR"

    async def async_top_catalog_category(
        self,
        enabled_providers,
        decade,
        category,
        top_count,
        min_imdb_votes=0,
        exclude_short_films=False,
        excluded_keys=None,
    ):
        """Build a France-first popularity pool, then rank quality with IMDb."""
        decade = int(decade)
        top_count = max(1, min(100, int(top_count)))
        min_imdb_votes = max(0, int(min_imdb_votes or 0))
        exclude_short_films = bool(exclude_short_films)
        excluded_keys = set(excluded_keys or ())
        category = str(category)
        packages = await self.async_resolve_provider_packages()
        package_codes = []
        for provider in enabled_providers:
            package_codes.extend(packages.get(provider) or [])
        package_codes = list(dict.fromkeys(package_codes))
        if not package_codes:
            return {"items": [], "error": "Aucun package JustWatch pour les services activés"}

        provider_signature = ",".join(sorted(enabled_providers))
        cache_key = (
            f"top-catalog-v5:{provider_signature}:{decade}:{category}:{top_count}:"
            f"votes{min_imdb_votes}:short{int(exclude_short_films)}"
        )
        if self.store:
            cached = self.store.get_metadata(cache_key)
            if _cache_fresh_hours(cached, TOP_CATALOG_CACHE_HOURS):
                ranked_pool = cached.get("ranked_pool")
                if isinstance(ranked_pool, list):
                    visible = [
                        dict(item)
                        for item in ranked_pool
                        if item.get("media_key") not in excluded_keys
                    ][:top_count]
                    await self.async_enrich_imdb_posters(visible)
                    for index, item in enumerate(visible, start=1):
                        item["rank"] = index
                    algorithm = dict(cached.get("algorithm") or {})
                    algorithm["excluded_count"] = len(excluded_keys)
                    algorithm["visible_count"] = len(visible)
                    return {
                        "items": visible,
                        "error": None if visible else cached.get("error"),
                        "cached": True,
                        "algorithm": algorithm,
                    }

        object_type = "SHOW" if category == "series" else "MOVIE"
        base_filter = {
            "objectTypes": [object_type],
            "releaseYear": {"min": decade, "max": decade + 9},
        }
        if category == "animation":
            base_filter["genres"] = ["ani"]
        elif category == "movies":
            base_filter["excludeGenres"] = ["ani"]

        fr_filter = dict(base_filter)
        fr_filter["packages"] = package_codes
        fr_filter["monetizationTypes"] = ["FLATRATE", "FLATRATE_AND_BUY", "ADS", "FREE"]

        # Up to 100 locally popular candidates gives a Top 65 enough reserve for
        # status exclusions without reopening the worldwide IMDb catalogue.
        candidate_count = min(100, max(40, top_count + 35))
        fr_edges, fr_sort_mode = await self._async_top_popular_edges(
            "FR", "FR", fr_filter, candidate_count
        )
        seen = set()

        def parse_edges(edges, popularity_market):
            parsed = []
            market = str(popularity_market).upper()
            for market_rank, edge in enumerate(edges, start=1):
                node = edge.get("node") or {}
                if node.get("objectType") != object_type:
                    continue
                content = node.get("content") or {}
                year = content.get("originalReleaseYear")
                try:
                    year_i = int(year)
                except (TypeError, ValueError):
                    continue
                if year_i < decade or year_i > decade + 9:
                    continue

                genre_codes = {
                    str(g.get("shortName") or "").casefold()
                    for g in (content.get("genres") or [])
                    if isinstance(g, dict)
                }
                if category == "animation" and "ani" not in genre_codes:
                    continue
                if category == "movies" and "ani" in genre_codes:
                    continue

                scoring = content.get("scoring") or {}
                try:
                    imdb_score = float(scoring.get("imdbScore"))
                    imdb_votes = int(scoring.get("imdbVotes"))
                except (TypeError, ValueError):
                    continue
                if imdb_votes <= 0 or imdb_votes < min_imdb_votes:
                    continue

                oid = node.get("objectId")
                title = str(content.get("title") or "").strip()
                if not title:
                    continue
                media_type = "tv" if object_type == "SHOW" else "movie"
                key = f"jw:{oid}" if oid is not None else fallback_key(media_type, title)
                if key in seen:
                    continue

                providers = self._provider_offers(node)
                enabled_offer_keys = [p for p in enabled_providers if p in providers]
                if not enabled_offer_keys:
                    continue

                runtime = content.get("runtime")
                try:
                    runtime_minutes = int(runtime) if runtime is not None else None
                except (TypeError, ValueError):
                    runtime_minutes = None
                if (
                    exclude_short_films
                    and category in {"movies", "animation"}
                    and runtime_minutes is not None
                    and runtime_minutes < 40
                ):
                    continue

                seen.add(key)
                full_path = content.get("fullPath")
                ext = content.get("externalIds") or {}
                parsed.append({
                    "rank": None,
                    "global_rank": None,
                    "title": title,
                    "original_title": None,
                    "subtitle": None,
                    "provider": enabled_offer_keys[0],
                    "provider_name": PROVIDER_NAMES.get(enabled_offer_keys[0], enabled_offer_keys[0]),
                    "media_type": media_type,
                    "media_key": key,
                    "poster": poster_url(content.get("fullPosterUrl")),
                    "poster_source": "justwatch" if content.get("fullPosterUrl") else None,
                    "description": content.get("shortDescription"),
                    "year": year_i,
                    "rating": imdb_score,
                    "rating_source": "IMDb",
                    "imdb_votes": imdb_votes,
                    "imdb_id": ext.get("imdbId"),
                    "runtime": runtime_minutes,
                    "age_certification": None,
                    "age_country": None,
                    "age_fr": None,
                    "age_us": None,
                    "jw_object_id": oid,
                    "days_in_top": None,
                    "trend": None,
                    "trend_difference": None,
                    "details_url": "https://www.justwatch.com" + full_path if full_path else None,
                    "providers": providers,
                    "popularity_market": market,
                    "popularity_rank": market_rank,
                    "fr_popularity_rank": market_rank if market == "FR" else None,
                    "us_popularity_rank": market_rank if market == "US" else None,
                    "source": (
                        "Top Streaming · popularité France → qualité IMDb"
                        if market == "FR"
                        else "Top Streaming · fallback popularité US → qualité IMDb · disponibilité France"
                    ),
                    "top_category": category,
                    "top_decade": decade,
                })
            return parsed

        fr_candidates = parse_edges(fr_edges, "FR")
        candidates = list(fr_candidates)
        us_candidates = []
        us_sort_mode = None

        # US is a last-resort reserve only. It never displaces a valid FR
        # candidate because the ranker keeps market tiers strictly ordered. We
        # complete the technical reserve pool (not the visible Top) so later
        # Vu/Pas intéressé exclusions can still refill without shrinking it.
        if len(fr_candidates) < candidate_count:
            us_filter = dict(base_filter)
            reserve_needed = candidate_count - len(fr_candidates)
            us_first = min(100, max(40, reserve_needed * 4))
            try:
                us_edges, us_sort_mode = await self._async_top_popular_edges(
                    "US", "FR", us_filter, us_first
                )
                us_candidates = parse_edges(us_edges, "US")[:reserve_needed]
                candidates.extend(us_candidates)
            except Exception as err:
                _LOGGER.debug("JustWatch US popularity fallback unavailable: %s", err)
                us_sort_mode = "UNAVAILABLE"

        ranked_pool = self._top_catalog_weighted_rank(candidates)
        ranked = [
            item for item in ranked_pool if item.get("media_key") not in excluded_keys
        ][:top_count]
        await self.async_enrich_imdb_posters(ranked)
        for index, item in enumerate(ranked, start=1):
            item["rank"] = index

        algorithm = {
            "name": "Popularité FR → IMDb Bayesian (US fallback)",
            "input_sort": fr_sort_mode,
            "fr_candidate_count": len(fr_candidates),
            "us_fallback_candidate_count": len(us_candidates),
            "us_fallback_used": bool(us_candidates),
            "us_input_sort": us_sort_mode,
            "candidate_count": len(candidates),
            "ranked_pool_count": len(ranked_pool),
            "top_count": top_count,
            "min_imdb_votes": min_imdb_votes,
            "exclude_short_films": exclude_short_films,
            "excluded_count": len(excluded_keys),
            "visible_count": len(ranked),
        }
        result = {
            "items": ranked,
            "error": None if ranked else "Aucun titre classable disponible sur les services activés",
            "cached": False,
            "algorithm": algorithm,
        }
        if self.store:
            self.store.set_metadata(
                cache_key,
                {
                    "ranked_pool": ranked_pool,
                    "error": result["error"],
                    "algorithm": algorithm,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        return result

    async def async_top_catalog(self, enabled_providers, config, excluded_keys=None):
        """Build configured decade × category branches for the second card."""
        if not (config or {}).get("enabled", True):
            return {"enabled": False, "decade_order": [], "decades": {}}
        excluded_keys = set(excluded_keys or ())
        raw_decades = (config or {}).get("decades") or {}
        min_imdb_votes = max(0, int((config or {}).get("min_imdb_votes", 0) or 0))
        exclude_short_films = bool((config or {}).get("exclude_short_films", False))
        tasks = []
        task_keys = []
        category_order = ("movies", "animation", "series")
        for decade in sorted(raw_decades, key=lambda x: int(x)):
            dc = raw_decades.get(decade) or {}
            if not dc.get("enabled", False):
                continue
            for category in category_order:
                if dc.get(category, False):
                    task_keys.append((str(decade), category, int(dc.get("top_count") or 1)))
                    tasks.append(
                        self.async_top_catalog_category(
                            enabled_providers,
                            int(decade),
                            category,
                            int(dc.get("top_count") or 1),
                            min_imdb_votes=min_imdb_votes,
                            exclude_short_films=exclude_short_films,
                            excluded_keys=excluded_keys,
                        )
                    )

        results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []
        decades = {}
        for (decade, category, top_count), result in zip(task_keys, results):
            decades.setdefault(decade, {"top_count": top_count, "categories": {}})
            if isinstance(result, Exception):
                decades[decade]["categories"][category] = {
                    "items": [], "error": str(result), "algorithm": None
                }
            else:
                decades[decade]["categories"][category] = result

        return {
            "enabled": True,
            "decade_order": list(decades.keys()),
            "category_order": list(category_order),
            "decades": decades,
            "source_label": (
                f"Popularité FR → qualité IMDb · min {min_imdb_votes:,} votes".replace(",", " ")
                + (" · courts métrages exclus" if exclude_short_films else "")
                + " · fallback US si nécessaire · disponibilité JustWatch France"
            ),
            "min_imdb_votes": min_imdb_votes,
            "exclude_short_films": exclude_short_films,
        }

    @staticmethod
    def _family_age_allowed(age_info, target_age, allow_unrated, classification):
        """Return whether an age certificate is suitable for the family branch.

        This intentionally does not convert a US certificate into a French one.
        The numeric thresholds are only conservative eligibility rules used by
        the Family filter. A genuine French certificate always has priority.
        """
        age_info = age_info or {}
        classification = classification or {}
        try:
            target_age = max(0, min(17, int(target_age)))
        except (TypeError, ValueError):
            target_age = 11

        fr = normalize_fr_age_certification(age_info.get("fr"))
        if fr:
            minimum = FAMILY_FR_MIN_AGE.get(fr)
            if minimum is None:
                return bool(allow_unrated), None, None
            return target_age >= minimum, fr, "FR"

        us = normalize_us_age_certification(age_info.get("us"))
        if us and classification.get("us_fallback", True):
            if us.startswith("TV-") and not classification.get("us_tv", True):
                return bool(allow_unrated), None, None
            minimum = FAMILY_US_MIN_AGE.get(us)
            if minimum is None:
                return bool(allow_unrated), None, None
            return target_age >= minimum, us, "US"

        return bool(allow_unrated), None, None

    async def async_top_family_category(
        self,
        enabled_providers,
        decade,
        category,
        top_count,
        family,
        classification,
        top_catalog=None,
        excluded_keys=None,
    ):
        """Build one lazily-loaded Family branch for a decade/category.

        We first build a deep IMDb-confidence pool, then resolve age certificates
        progressively. This keeps normal Top Streaming refreshes fast: expensive
        age lookups happen only when the user opens a Family branch.
        """
        category = str(category)
        if category not in {"movies", "animation", "series"}:
            raise ValueError(f"Catégorie Famille inconnue : {category}")

        decade = int(decade)
        top_count = max(1, min(100, int(top_count)))
        family = family or {}
        classification = classification or {}
        top_catalog = top_catalog or {}
        excluded_keys = set(excluded_keys or ())
        min_imdb_votes = max(0, int(top_catalog.get("min_imdb_votes", 0) or 0))
        exclude_short_films = bool(top_catalog.get("exclude_short_films", False))
        target_age = max(0, min(17, int(family.get("target_age", 11))))
        allow_unrated = bool(family.get("allow_unrated", False))
        provider_signature = ",".join(sorted(enabled_providers))
        us_fallback = bool(classification.get("us_fallback", True))
        us_tv = bool(classification.get("us_tv", True))
        cache_key = (
            f"top-family-v5:{provider_signature}:{decade}:{category}:{top_count}:"
            f"age{target_age}:unrated{int(allow_unrated)}:"
            f"us{int(us_fallback)}:ustv{int(us_tv)}:"
            f"votes{min_imdb_votes}:short{int(exclude_short_films)}"
        )
        if self.store:
            cached = self.store.get_metadata(cache_key)
            if _cache_fresh_hours(cached, TOP_CATALOG_CACHE_HOURS):
                eligible_pool = cached.get("eligible_pool")
                if isinstance(eligible_pool, list):
                    visible = [
                        dict(item)
                        for item in eligible_pool
                        if item.get("media_key") not in excluded_keys
                    ][:top_count]
                    for index, item in enumerate(visible, start=1):
                        item["rank"] = index
                    algorithm = dict(cached.get("algorithm") or {})
                    algorithm["excluded_count"] = len(excluded_keys)
                    algorithm["visible_count"] = len(visible)
                    return {
                        "items": visible,
                        "error": None if visible else cached.get("error"),
                        "cached": True,
                        "algorithm": algorithm,
                        "target_age": target_age,
                    }

        # Always start from the deepest supported ranked slice. This maximizes
        # the chance of filling a Family Top without weakening IMDb criteria.
        base = await self.async_top_catalog_category(
            enabled_providers,
            decade,
            category,
            100,
            min_imdb_votes=min_imdb_votes,
            exclude_short_films=exclude_short_films,
        )
        candidates = list(base.get("items") or [])
        if not candidates:
            return {
                "items": [],
                "error": base.get("error") or "Aucun titre classable disponible",
                "cached": False,
                "target_age": target_age,
                "algorithm": {
                    "name": "Popularité FR → IMDb Bayesian + filtre famille",
                    "candidate_count": 0,
                    "top_count": top_count,
                },
            }

        eligible_pool = []
        resolved_count = 0
        # Family remains lazy-loaded, but we now retain the eligible reserve pool
        # (up to the 100-candidate Top pool) so watched/rejected titles can leave
        # the flow without shrinking the configured Top.
        batch_size = 10
        for offset in range(0, len(candidates), batch_size):
            batch = candidates[offset : offset + batch_size]
            age_results = await asyncio.gather(
                *(
                    self._async_age_certification(
                        item.get("jw_object_id"),
                        item.get("media_type"),
                        item.get("details_url"),
                        item.get("title"),
                        item.get("year"),
                    )
                    for item in batch
                ),
                return_exceptions=True,
            )
            for item, age in zip(batch, age_results):
                resolved_count += 1
                if isinstance(age, Exception):
                    age = {}
                allowed, matched_value, matched_country = self._family_age_allowed(
                    age, target_age, allow_unrated, classification
                )
                if not allowed:
                    continue

                work = dict(item)
                work["age_fr"] = (age or {}).get("fr")
                work["age_us"] = (age or {}).get("us")
                if (age or {}).get("imdb_id"):
                    work["imdb_id"] = age.get("imdb_id")
                display_value, display_country = self.select_age(age, classification)
                work["age_certification"] = display_value
                work["age_country"] = display_country
                work["family_match_certification"] = matched_value
                work["family_match_country"] = matched_country
                work["family_target_age"] = target_age
                work["family_category"] = category
                work["top_category"] = "family"
                eligible_pool.append(work)

        selected = [
            item for item in eligible_pool if item.get("media_key") not in excluded_keys
        ][:top_count]
        for index, item in enumerate(selected, start=1):
            item["rank"] = index

        algorithm = {
            "name": "Popularité FR → IMDb Bayesian + filtre famille",
            "candidate_count": len(candidates),
            "eligible_pool_count": len(eligible_pool),
            "age_resolved_count": resolved_count,
            "top_count": top_count,
            "allow_unrated": allow_unrated,
            "us_fallback": us_fallback,
            "us_tv": us_tv,
            "min_imdb_votes": min_imdb_votes,
            "exclude_short_films": exclude_short_films,
            "excluded_count": len(excluded_keys),
            "visible_count": len(selected),
        }
        result = {
            "items": selected,
            "error": None if selected else (
                "Aucun contenu avec une classification compatible avec le filtre Famille"
            ),
            "cached": False,
            "target_age": target_age,
            "algorithm": algorithm,
        }
        if self.store:
            self.store.set_metadata(
                cache_key,
                {
                    "eligible_pool": eligible_pool,
                    "error": result["error"],
                    "algorithm": algorithm,
                    "target_age": target_age,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            await self.store.async_save()
        return result

    async def async_provider_pool(
        self,
        provider,
        media_type,
        target_count=20,
        max_depth=100,
        excluded_keys=None,
        classification=None,
        classification_limit=None,
    ):
        """Return an always-full active pool, deepening one-for-one as needed.

        The initial query asks exactly for ``target_count`` titles. If titles are
        excluded because the user marked them watched/not interested, the query
        is deepened only by the missing count, up to ``max_depth``.
        """
        target_count = max(1, int(target_count or 1))
        max_depth = max(target_count, min(100, int(max_depth or target_count)))
        excluded = set(excluded_keys or ())
        requested = min(target_count, max_depth)
        candidates = []

        while True:
            candidates = await self._async_provider_candidates(
                provider, media_type, requested
            )
            selected = [
                item for item in candidates if item.get("media_key") not in excluded
            ][:target_count]

            if len(selected) >= target_count or requested >= max_depth:
                break
            # If JustWatch returned less than requested there is no deeper page.
            if len(candidates) < requested:
                break

            missing = target_count - len(selected)
            requested = min(max_depth, requested + max(1, missing))

        selected = [
            item for item in candidates if item.get("media_key") not in excluded
        ][:target_count]

        classification = classification or {}
        include_age = bool(classification.get("enabled", True)) and (
            classification.get("france", True)
            or classification.get("us_fallback", True)
        )

        age_slice = selected
        if classification_limit is not None:
            try:
                age_slice = selected[: max(0, int(classification_limit))]
            except (TypeError, ValueError):
                age_slice = selected

        if include_age and age_slice:
            age_results = await asyncio.gather(
                *(
                    self._async_age_certification(
                        item.get("_jw_object_id"),
                        item.get("media_type"),
                        item.get("details_url"),
                        item.get("title"),
                        item.get("year"),
                    )
                    for item in age_slice
                ),
                return_exceptions=True,
            )
            for item, age in zip(age_slice, age_results):
                if isinstance(age, Exception) or not age:
                    continue
                item["age_fr"] = age.get("fr")
                item["age_us"] = age.get("us")
                item["imdb_id"] = age.get("imdb_id")
                value, country = self.select_age(age, classification)
                item["age_certification"] = value
                item["age_country"] = country

        await self.async_enrich_imdb_posters(selected)

        for item in selected:
            item.pop("_jw_object_id", None)

        return selected

    async def async_provider(
        self,
        provider,
        target_count=20,
        max_depth=100,
        excluded_keys=None,
        classification=None,
        classification_limit=None,
    ):
        movies_res, tv_res = await asyncio.gather(
            self.async_provider_pool(
                provider, "movie", target_count, max_depth, excluded_keys, classification,
                classification_limit=classification_limit,
            ),
            self.async_provider_pool(
                provider, "tv", target_count, max_depth, excluded_keys, classification,
                classification_limit=classification_limit,
            ),
            return_exceptions=True,
        )

        errors = []
        movies, tv = [], []
        if isinstance(movies_res, Exception):
            errors.append(f"Films: {movies_res}")
        else:
            movies = movies_res
        if isinstance(tv_res, Exception):
            errors.append(f"Séries: {tv_res}")
        else:
            tv = tv_res

        return {
            "movies": movies,
            "tv": tv,
            "error": " | ".join(errors) if errors else None,
            "source_mode": "justwatch_provider_popular",
            "packages": self.package_names(provider),
        }

    async def async_search_local_title(
        self, title, media_type, year=None, classification=None
    ):
        """Resolve a local-library filename to localized JustWatch/IMDb metadata.

        Matching is deliberately conservative. IMDb autocomplete supplies a
        canonical id when possible; JustWatch candidates are then scored by
        title, release year, media type and that IMDb id. When a reliable
        JustWatch match cannot be established, the local item is kept and an
        IMDb-only poster fallback is returned instead of forcing a wrong title.
        """
        title = str(title or "").strip()
        if not title:
            return None

        media_type = "tv" if str(media_type).lower() in {"tv", "show"} else "movie"
        object_type = "SHOW" if media_type == "tv" else "MOVIE"
        classification = classification or {}
        include_age = bool(classification.get("enabled", True)) and (
            classification.get("france", True)
            or classification.get("us_fallback", True)
        )

        try:
            wanted_year = int(year) if year not in (None, "") else None
        except (TypeError, ValueError):
            wanted_year = None

        cache_key = (
            f"local-title-v11:{media_type}:{wanted_year or ''}:{_slug(title)}"
        )
        wanted_slug_for_cache = _matching_slug(title, media_type)
        if self.store:
            cached = self.store.get_metadata(cache_key)
            if _cache_fresh(cached) and cached.get("metadata_status"):
                cached_slug = _matching_slug(
                    str(cached.get("title") or ""), media_type
                )
                wanted_sequel = _bare_sequel_number(wanted_slug_for_cache)
                cached_sequel = _bare_sequel_number(cached_slug)
                sequel_cache_valid = (
                    wanted_sequel == cached_sequel
                    or (wanted_sequel is None and cached_sequel is None)
                )
                cache_quality_valid = (
                    cached.get("metadata_status") in {"matched", "imdb_only"}
                    and bool(cached.get("poster"))
                )
                if sequel_cache_valid and cache_quality_valid:
                    if cached.get("age_resolved"):
                        age = {
                            "fr": cached.get("age_fr"),
                            "us": cached.get("age_us"),
                            "imdb_id": cached.get("imdb_id"),
                        }
                        value, country = self.select_age(age, classification)
                        cached["age_certification"] = value
                        cached["age_country"] = country
                    return cached

        expected_imdb = await self._async_imdb_id(
            title, wanted_year, media_type, strict=True
        )

        payload = {
            "operationName": "SearchStreamingTitle",
            "variables": {
                "country": "FR",
                "language": "fr",
                "first": 10,
                "filter": {
                    "searchQuery": title,
                    "objectTypes": [object_type],
                },
            },
            "query": self.SEARCH_QUERY,
        }

        edges = []
        search_error = None
        try:
            async with self._sem:
                data = await self._post(payload)
            edges = ((data.get("popularTitles") or {}).get("edges") or [])
        except Exception as err:
            search_error = err
            _LOGGER.warning("JustWatch local search failed for %s: %s", title, err)

        wanted_slug = _matching_slug(title, media_type)

        def candidate_score(node):
            if not isinstance(node, dict) or node.get("objectType") != object_type:
                return -999
            content = node.get("content") or {}
            candidate_title = str(content.get("title") or "").strip()
            candidate_slug = _matching_slug(candidate_title, media_type)

            candidate_year = content.get("originalReleaseYear")
            try:
                candidate_year = int(candidate_year) if candidate_year else None
            except (TypeError, ValueError):
                candidate_year = None

            if wanted_year and candidate_year:
                delta = abs(candidate_year - wanted_year)
                if delta > 1:
                    return -999

            ext = content.get("externalIds") or {}
            candidate_imdb = self._normalize_imdb_id(ext.get("imdbId"))
            imdb_bridge = bool(
                expected_imdb and candidate_imdb == expected_imdb
            )

            # A strictly resolved IMDb id is stronger than localized-title text.
            # This is essential when a local filename uses the original English
            # title while JustWatch FR returns a completely different French
            # title (e.g. Indiana Jones / Raiders of the Lost Ark).
            if imdb_bridge:
                points = 20
            else:
                if not wanted_slug or not candidate_slug:
                    return -999

                wanted_sequel = _bare_sequel_number(wanted_slug)
                candidate_sequel = _bare_sequel_number(candidate_slug)
                if (
                    wanted_sequel != candidate_sequel
                    and (wanted_sequel is not None or candidate_sequel is not None)
                ):
                    return -999

                similarity = SequenceMatcher(None, wanted_slug, candidate_slug).ratio()
                contains = wanted_slug in candidate_slug or candidate_slug in wanted_slug

                exact_year = bool(
                    wanted_year and candidate_year and candidate_year == wanted_year
                )
                expanded_title = bool(
                    exact_year
                    and len(wanted_slug) >= 7
                    and candidate_slug.startswith(wanted_slug + "-")
                )
                local_subtitle_alias = bool(
                    exact_year
                    and len(candidate_slug) >= 5
                    and wanted_slug.startswith(candidate_slug + "-")
                )
                first_installment_alias = bool(
                    exact_year
                    and wanted_slug != candidate_slug
                    and _first_installment_base_slug(wanted_slug)
                    == _first_installment_base_slug(candidate_slug)
                )
                franchise_number_alias = bool(
                    exact_year
                    and wanted_slug != candidate_slug
                    and _franchise_prefix_alias(wanted_slug, candidate_slug)
                )
                localized_title_alias = bool(
                    exact_year
                    and wanted_slug != candidate_slug
                    and _localized_title_alias(wanted_slug, candidate_slug)
                )

                if candidate_slug == wanted_slug:
                    points = 12
                elif similarity >= 0.94:
                    points = 10
                elif similarity >= 0.88:
                    points = 8
                elif contains and similarity >= 0.72:
                    points = 6
                elif expanded_title:
                    points = 9
                elif local_subtitle_alias:
                    points = 10
                elif first_installment_alias:
                    points = 10
                elif franchise_number_alias:
                    points = 10
                elif localized_title_alias:
                    points = 10
                else:
                    return -999

                if expected_imdb and candidate_imdb and candidate_imdb != expected_imdb:
                    points -= 2

            if wanted_year and candidate_year:
                points += 8 if candidate_year == wanted_year else 3

            return points

        candidates = [
            (candidate_score((edge or {}).get("node") or {}), (edge or {}).get("node") or {})
            for edge in edges
        ]
        candidates = [entry for entry in candidates if entry[0] > -999]
        candidates.sort(key=lambda entry: entry[0], reverse=True)

        selected = candidates[0][1] if candidates else None
        selected_score = candidates[0][0] if candidates else None
        minimum_score = 16 if wanted_year else 10

        # If two different works are effectively tied, fail closed instead of
        # selecting whichever JustWatch happened to return first.
        if (
            selected is not None
            and len(candidates) > 1
            and candidates[1][0] >= minimum_score
            and selected_score is not None
            and selected_score - candidates[1][0] <= 1
        ):
            first_id = selected.get("objectId") or selected.get("id")
            second = candidates[1][1]
            second_id = second.get("objectId") or second.get("id")
            if first_id != second_id:
                selected = None

        if selected is None or selected_score is None or selected_score < minimum_score:
            imdb_detail = (
                await self._async_imdb_local_detail(expected_imdb)
                if expected_imdb
                else None
            ) or {}
            result = {
                "title": imdb_detail.get("title") or title,
                "year": imdb_detail.get("year") or wanted_year,
                "poster": imdb_detail.get("poster"),
                "poster_source": "imdb" if imdb_detail.get("poster") else None,
                "description": imdb_detail.get("description"),
                "rating": imdb_detail.get("rating"),
                "rating_source": "IMDb" if imdb_detail.get("rating") is not None else None,
                "imdb_votes": imdb_detail.get("imdb_votes"),
                "age_certification": None,
                "age_country": None,
                "age_fr": None,
                "age_us": None,
                "age_resolved": False,
                "imdb_id": expected_imdb,
                "details_url": (
                    f"https://www.imdb.com/title/{expected_imdb}/"
                    if expected_imdb else None
                ),
                "providers": {},
                "canonical_media_key": (
                    f"imdb:{expected_imdb}" if expected_imdb else None
                ),
                "metadata_status": "imdb_only" if expected_imdb else "unmatched",
                "match_score": selected_score,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "cache_schema": METADATA_CACHE_SCHEMA,
            }
            useful_imdb_fallback = bool(
                expected_imdb
                and (
                    result.get("poster")
                    or result.get("rating") is not None
                    or result.get("description")
                )
            )
            if search_error and not useful_imdb_fallback:
                raise RuntimeError(str(search_error))
            if self.store:
                self.store.set_metadata(cache_key, result)
            return result

        content = selected.get("content") or {}
        scoring = content.get("scoring") or {}
        if (
            not content.get("shortDescription")
            or not any(
                scoring.get(key) is not None
                for key in ("imdbScore", "jwRating", "tmdbScore")
            )
        ) and selected.get("id"):
            try:
                detail = await self._async_title_detail(selected.get("id"))
            except Exception as err:
                _LOGGER.debug("Local title detail failed for %s: %s", title, err)
                detail = None
            if detail:
                merged = dict(content)
                for key, value in detail.items():
                    if value is not None and value != "":
                        merged[key] = value
                content = merged

        object_id = selected.get("objectId")
        localized_title = str(content.get("title") or title).strip() or title
        release_year = content.get("originalReleaseYear") or wanted_year
        full_path = content.get("fullPath")
        details_url = "https://www.justwatch.com" + full_path if full_path else None
        rating, rating_source = self._rating(content)

        ext = content.get("externalIds") or {}
        justwatch_imdb = self._normalize_imdb_id(ext.get("imdbId"))

        age_info = None
        if include_age:
            age_info = await self._async_age_certification(
                object_id,
                media_type,
                details_url,
                localized_title,
                release_year,
                preferred_imdb_id=justwatch_imdb,
            )
        age_info = age_info or {"fr": None, "us": None, "imdb_id": None}
        age_value, age_country = self.select_age(age_info, classification)

        # Canonical poster source remains IMDb. The crucial point is that for
        # a JustWatch-confirmed work, its explicit externalIds.imdbId is the
        # strongest binding to the correct IMDb title. Age-resolution and
        # autocomplete ids are only fallbacks.
        imdb_id = self._normalize_imdb_id(
            justwatch_imdb or age_info.get("imdb_id") or expected_imdb
        )
        poster_lookup = await self._async_imdb_posters([imdb_id]) if imdb_id else {}
        jw_poster = poster_url(content.get("fullPosterUrl"))
        imdb_poster = poster_lookup.get(imdb_id) if imdb_id else None

        result = {
            "title": localized_title,
            "year": release_year,
            "poster": imdb_poster or jw_poster,
            "poster_source": "imdb" if imdb_poster else ("justwatch" if jw_poster else None),
            "description": content.get("shortDescription"),
            "rating": rating,
            "rating_source": rating_source,
            "age_certification": age_value,
            "age_country": age_country,
            "age_fr": age_info.get("fr"),
            "age_us": age_info.get("us"),
            "age_resolved": include_age,
            "imdb_id": imdb_id,
            "details_url": details_url,
            "providers": self._provider_offers(selected),
            "canonical_media_key": (
                f"jw:{object_id}" if object_id is not None
                else (f"imdb:{imdb_id}" if imdb_id else None)
            ),
            "metadata_status": "matched",
            "match_score": selected_score,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "cache_schema": METADATA_CACHE_SCHEMA,
        }
        if self.store:
            self.store.set_metadata(cache_key, result)
        return result

    async def async_enrich_local_items(self, items, classification=None):
        """Enrich local-library items in place while preserving path identity."""
        works = [item for item in (items or []) if isinstance(item, dict)]
        if not works:
            return works

        unique = {}
        for item in works:
            lookup_title = str(
                item.get("lookup_title") or item.get("title") or ""
            ).strip()
            key = (
                "tv" if item.get("media_type") == "tv" else "movie",
                lookup_title,
                item.get("year"),
            )
            if key[1]:
                unique.setdefault(key, []).append(item)

        keys = list(unique)
        for start in range(0, len(keys), 4):
            if start:
                await asyncio.sleep(0.15)
            chunk = keys[start : start + 4]
            results = await asyncio.gather(
                *(
                    self.async_search_local_title(
                        title, media_type, year, classification
                    )
                    for media_type, title, year in chunk
                ),
                return_exceptions=True,
            )
            for key, metadata in zip(chunk, results):
                if isinstance(metadata, Exception) or not metadata:
                    continue

                media_type, title, year = key

                # Explicit collection-volume labels (#1, Vol. 1, Tome 1...)
                # can represent physical files/discs of a TV programme rather
                # than movie sequels. The scanner cannot infer that from the
                # filename alone because there is no SxxExx marker. If the
                # strict movie lookup fails, retry the same canonical lookup
                # title as a TV show. This keeps normal movies strict while
                # restoring TV compilations such as "La Télé des Inconnus #1".
                has_volume_lookup_alias = any(
                    str(item.get("lookup_title") or "").strip()
                    and str(item.get("lookup_title") or "").strip()
                    != str(item.get("title") or "").strip()
                    for item in unique[key]
                )
                if (
                    media_type == "movie"
                    and metadata.get("metadata_status") == "unmatched"
                    and has_volume_lookup_alias
                ):
                    try:
                        tv_metadata = await self.async_search_local_title(
                            title, "tv", year, classification
                        )
                    except Exception as err:
                        _LOGGER.debug(
                            "Local TV fallback failed for %s: %s", title, err
                        )
                        tv_metadata = None
                    if (
                        tv_metadata
                        and tv_metadata.get("metadata_status") != "unmatched"
                    ):
                        metadata = dict(tv_metadata)
                        metadata["resolved_media_type"] = "tv"

                for item in unique[key]:
                    local_id = item.get("local_id")
                    local_media_key = item.get("media_key") or local_id
                    parsed_title = item.get("title")
                    lookup_title = item.get("lookup_title") or parsed_title
                    for field, value in metadata.items():
                        if value is not None:
                            item[field] = value
                    item["parsed_title"] = parsed_title
                    item["lookup_title"] = lookup_title
                    item["local_id"] = local_id
                    item["media_key"] = local_media_key

        if self.store:
            await self.store.async_save()
        return works

    async def async_search_localized_netflix(
        self, original_title, media_type, classification=None
    ):
        cache_key = f"netflix:{media_type}:{_slug(original_title)}"
        classification = classification or {}
        include_age = bool(classification.get("enabled", True)) and (
            classification.get("france", True)
            or classification.get("us_fallback", True)
        )

        if self.store:
            cached = self.store.get_metadata(cache_key)
            if _cache_fresh(cached) and "poster_source" in cached:
                # A cache generated while classifications were disabled can be
                # reused only when the caller does not need classifications.
                # 0.6.2 Netflix cache rows have no poster_source, forcing one
                # refresh so the canonical IMDb poster can be attached.
                if not include_age or cached.get("age_resolved"):
                    if cached.get("age_resolved"):
                        age = {
                            "fr": cached.get("age_fr"),
                            "us": cached.get("age_us"),
                            "imdb_id": cached.get("imdb_id"),
                        }
                        value, country = self.select_age(age, classification)
                        cached["age_certification"] = value
                        cached["age_country"] = country
                    else:
                        cached["age_certification"] = None
                        cached["age_country"] = None
                    return cached

        packages = await self.async_resolve_provider_packages()
        netflix_codes = packages["netflix"]
        object_type = "MOVIE" if media_type == "movie" else "SHOW"

        payload = {
            "operationName": "SearchStreamingTitle",
            "variables": {
                "country": "FR",
                "language": "fr",
                "first": 5,
                "filter": {
                    "searchQuery": original_title,
                    "objectTypes": [object_type],
                    "packages": netflix_codes,
                },
            },
            "query": self.SEARCH_QUERY,
        }

        async with self._sem:
            data = await self._post(payload)

        edges = ((data.get("popularTitles") or {}).get("edges") or [])
        if not edges:
            return None

        selected = None
        for edge in edges:
            node = edge.get("node") or {}
            if node.get("objectType") == object_type:
                selected = node
                break
        if selected is None:
            selected = edges[0].get("node") or {}

        content = selected.get("content") or {}
        scoring = content.get("scoring") or {}
        needs_detail = (
            not content.get("shortDescription")
            or not any(
                scoring.get(key) is not None
                for key in ("imdbScore", "jwRating", "tmdbScore")
            )
        )

        if needs_detail and selected.get("id"):
            try:
                detail_content = await self._async_title_detail(selected.get("id"))
            except Exception as err:
                _LOGGER.debug(
                    "JustWatch detail fallback failed for %s: %s",
                    original_title, err,
                )
                detail_content = None

            if detail_content:
                merged = dict(content)
                for key, value in detail_content.items():
                    if value is not None and value != "":
                        merged[key] = value
                content = merged

        object_id = selected.get("objectId")
        full_path = content.get("fullPath")
        details_url = "https://www.justwatch.com" + full_path if full_path else None
        rating, rating_source = self._rating(content)
        watch_url = self._watch_url(selected, netflix_codes)
        localized_title = (content.get("title") or "").strip() or original_title
        release_year = content.get("originalReleaseYear")

        age_info = None
        if include_age:
            age_info = await self._async_age_certification(
                object_id, media_type, details_url, localized_title, release_year
            )
        age_info = age_info or {"fr": None, "us": None, "imdb_id": None}
        age_value, age_country = self.select_age(age_info, classification)

        ext = content.get("externalIds") or {}
        imdb_id = self._normalize_imdb_id(age_info.get("imdb_id") or ext.get("imdbId"))
        if not imdb_id:
            imdb_id = await self._async_imdb_id(localized_title, release_year, media_type)
        jw_poster = poster_url(content.get("fullPosterUrl"))
        poster_lookup = await self._async_imdb_posters([imdb_id]) if imdb_id else {}
        imdb_poster = poster_lookup.get(imdb_id) if imdb_id else None

        result = {
            "title": localized_title,
            "poster": imdb_poster or jw_poster,
            "poster_source": "imdb" if imdb_poster else ("justwatch" if jw_poster else None),
            "description": content.get("shortDescription"),
            "year": release_year,
            "rating": rating,
            "rating_source": rating_source,
            "age_certification": age_value,
            "age_country": age_country,
            "age_fr": age_info.get("fr"),
            "age_us": age_info.get("us"),
            "age_resolved": include_age,
            "imdb_id": imdb_id,
            "details_url": details_url,
            "watch_url": watch_url,
            "playback_id": playback_id_from_url("netflix", watch_url),
            "providers": self._provider_offers(selected),
            "media_key": (
                f"jw:{object_id}"
                if object_id is not None
                else fallback_key(media_type, original_title)
            ),
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "cache_schema": METADATA_CACHE_SCHEMA,
        }

        if self.store:
            self.store.set_metadata(cache_key, result)

        return result

    async def async_enrich_netflix(self, netflix, classification=None):
        classification = classification or {}
        pairs = []
        for bucket in ("movies", "tv"):
            for item in netflix.get(bucket, []):
                pairs.append(
                    (
                        item,
                        self.async_search_localized_netflix(
                            item["original_title"], item["media_type"], classification
                        ),
                    )
                )

        results = await asyncio.gather(
            *(coro for _, coro in pairs), return_exceptions=True
        )
        for (item, _), result in zip(pairs, results):
            if isinstance(result, Exception) or not result:
                continue
            item["title"] = result.get("title") or item["title"]
            item["poster"] = result.get("poster") or item.get("poster")
            item["poster_source"] = result.get("poster_source") or item.get("poster_source")
            item["description"] = result.get("description") or item.get("description")
            item["year"] = result.get("year") or item.get("year")
            item["rating"] = result.get("rating")
            item["rating_source"] = result.get("rating_source")
            item["age_certification"] = result.get("age_certification")
            item["age_country"] = result.get("age_country")
            item["age_fr"] = result.get("age_fr")
            item["age_us"] = result.get("age_us")
            item["imdb_id"] = result.get("imdb_id")
            item["details_url"] = result.get("details_url") or item.get("details_url")
            item["watch_url"] = result.get("watch_url")
            item["playback_id"] = result.get("playback_id")
            item["providers"] = result.get("providers") or {
                "netflix": {
                    "provider": "netflix",
                    "provider_name": "Netflix",
                    "watch_url": result.get("watch_url"),
                    "playback_id": result.get("playback_id"),
                }
            }
            item["media_key"] = result.get("media_key") or item["media_key"]

        if self.store:
            await self.store.async_save()

class LocalMetadataClient(JustWatchClient):
    """Metadata client dedicated to Streaming Local.

    It deliberately owns its concurrency, cooldown and cache namespace so a
    NAS scan can never throttle or alter the historical Streaming/Top engine.
    """

    def __init__(self, session, store=None):
        super().__init__(session, store)
        self._sem = asyncio.Semaphore(1)
        self._local_jw_blocked_until: datetime | None = None
        self._local_last_jw_request = 0.0

    async def _post(self, payload):
        # Local-only GraphQL path: strictly serialized and rate-limited.
        now = datetime.now(timezone.utc)
        loop = asyncio.get_running_loop()
        elapsed = loop.time() - self._local_last_jw_request
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        self._local_last_jw_request = loop.time()
        if self._local_jw_blocked_until and now < self._local_jw_blocked_until:
            remaining = max(
                1, int((self._local_jw_blocked_until - now).total_seconds() // 60) + 1
            )
            raise RuntimeError(
                f"JustWatch temporairement en pause après HTTP 403 ({remaining} min)"
            )

        async with self.session.post(
            JUSTWATCH_GRAPHQL,
            json=payload,
            headers={
                "User-Agent": UA,
                "Origin": "https://www.justwatch.com",
                "Referer": "https://www.justwatch.com/fr/",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30,
        ) as resp:
            text = await resp.text()
            if resp.status == 403:
                self._local_jw_blocked_until = now + timedelta(
                    minutes=JUSTWATCH_BLOCK_MINUTES
                )
                raise RuntimeError("JustWatch HTTP 403 — mise en pause temporaire")
            if resp.status >= 400:
                raise RuntimeError(f"JustWatch HTTP {resp.status}")
            data = await resp.json()

        self._local_jw_blocked_until = None
        if data.get("errors"):
            raise RuntimeError(data["errors"][0].get("message", "Erreur GraphQL"))
        return data.get("data") or {}

    async def _async_imdb_id(self, title, year=None, media_type=None, strict=False):
        """Resolve a title to a canonical IMDb id using IMDb autocomplete."""
        if not title:
            return None
        cache_prefix = (
            "local-imdb-id-strict-v1" if strict else "local-imdb-id-v1"
        )
        cache_key = f"{cache_prefix}:{media_type or 'title'}:{year or ''}:{_slug(title)}"
        wanted_title_for_cache = _matching_slug(str(title), media_type)
        if self.store:
            cached = self.store.get_metadata(cache_key)
            if _cache_fresh(cached) and cached.get("imdb_id"):
                if not strict:
                    return cached.get("imdb_id")
                cached_title = _matching_slug(
                    str(cached.get("resolved_title") or ""), media_type
                )
                wanted_sequel = _bare_sequel_number(wanted_title_for_cache)
                cached_sequel = _bare_sequel_number(cached_title)
                if (
                    cached_title
                    and wanted_sequel == cached_sequel
                ):
                    return cached.get("imdb_id")

        imdb_id = None
        resolved_title = None
        resolved_year = None
        try:
            url = (
                "https://v3.sg.media-imdb.com/suggestion/titles/x/"
                + quote(str(title).strip().lower(), safe="")
                + ".json"
            )
            async with self._sem:
                async with self.session.get(
                    url,
                    headers={"User-Agent": UA, "Accept": "application/json"},
                    timeout=20,
                ) as resp:
                    if resp.status < 400:
                        data = await resp.json()
                        hits = [
                            h for h in (data.get("d") or [])
                            if str(h.get("id") or "").startswith("tt")
                        ]

                        want_year = None
                        try:
                            want_year = int(year) if year else None
                        except (TypeError, ValueError):
                            pass
                        want_title = _matching_slug(str(title), media_type)
                        want_tv = media_type in ("tv", "show")

                        if strict:
                            def strict_score(hit):
                                hit_title = _matching_slug(
                                    str(hit.get("l") or ""), media_type
                                )
                                if not want_title or not hit_title:
                                    return -1000

                                want_sequel = _bare_sequel_number(want_title)
                                hit_sequel = _bare_sequel_number(hit_title)
                                if (
                                    want_sequel != hit_sequel
                                    and (want_sequel is not None or hit_sequel is not None)
                                ):
                                    return -1000

                                similarity = SequenceMatcher(
                                    None, want_title, hit_title
                                ).ratio()
                                contains = (
                                    want_title in hit_title
                                    or hit_title in want_title
                                )

                                hit_year = hit.get("y")
                                try:
                                    hit_year = int(hit_year) if hit_year else None
                                except (TypeError, ValueError):
                                    hit_year = None

                                exact_year = bool(
                                    want_year and hit_year and hit_year == want_year
                                )
                                expanded_title = bool(
                                    exact_year
                                    and len(want_title) >= 7
                                    and hit_title.startswith(want_title + "-")
                                )
                                local_subtitle_alias = bool(
                                    exact_year
                                    and len(hit_title) >= 5
                                    and want_title.startswith(hit_title + "-")
                                )
                                first_installment_alias = bool(
                                    exact_year
                                    and want_title != hit_title
                                    and _first_installment_base_slug(want_title)
                                    == _first_installment_base_slug(hit_title)
                                )
                                localized_title_alias = bool(
                                    exact_year
                                    and want_title != hit_title
                                    and _localized_title_alias(want_title, hit_title)
                                )

                                # Title similarity is mandatory. Year/type alone
                                # must never be enough to identify local media.
                                if hit_title == want_title:
                                    points = 14
                                elif similarity >= 0.94:
                                    points = 12
                                elif similarity >= 0.88:
                                    points = 9
                                elif contains and similarity >= 0.72:
                                    points = 8
                                elif expanded_title:
                                    points = 9
                                elif local_subtitle_alias:
                                    points = 10
                                elif first_installment_alias:
                                    points = 10
                                elif localized_title_alias:
                                    points = 10
                                else:
                                    return -1000

                                # A known conflicting year is a hard rejection.
                                if want_year and hit_year:
                                    delta = abs(hit_year - want_year)
                                    if delta > 1:
                                        return -1000
                                    points += 8 if delta == 0 else 3

                                qid = str(hit.get("qid") or "").casefold()
                                tv_show_types = {
                                    "tvseries", "tvminiseries", "tvshort"
                                }
                                rejected_non_movie_types = {
                                    "tvepisode", "videogame", "podcastseries",
                                    "podcastepisode", "musicvideo",
                                }
                                if want_tv:
                                    if qid and qid not in tv_show_types:
                                        return -1000
                                else:
                                    if qid in tv_show_types or qid in rejected_non_movie_types:
                                        return -1000
                                points += 2
                                return points

                            ranked = sorted(
                                (
                                    (strict_score(hit), hit)
                                    for hit in hits
                                ),
                                key=lambda entry: entry[0],
                                reverse=True,
                            )
                            ranked = [entry for entry in ranked if entry[0] > -1000]
                            minimum = 16 if want_year else 11
                            if ranked and ranked[0][0] >= minimum:
                                # If two different IMDb titles are essentially
                                # tied, fail closed instead of choosing a random
                                # poster. A future manual mapping can resolve it.
                                ambiguous = (
                                    len(ranked) > 1
                                    and ranked[1][0] >= minimum
                                    and ranked[0][0] - ranked[1][0] <= 1
                                    and ranked[0][1].get("id") != ranked[1][1].get("id")
                                )
                                if not ambiguous:
                                    imdb_id = ranked[0][1].get("id")
                        else:
                            def score(hit):
                                points = 0
                                hit_title = _slug(str(hit.get("l") or ""))
                                hit_year = hit.get("y")
                                qid = str(hit.get("qid") or "").lower()
                                if hit_title == want_title:
                                    points += 8
                                elif want_title and (
                                    want_title in hit_title
                                    or hit_title in want_title
                                ):
                                    points += 3
                                if want_year and hit_year == want_year:
                                    points += 6
                                elif (
                                    want_year
                                    and isinstance(hit_year, int)
                                    and abs(hit_year - want_year) <= 1
                                ):
                                    points += 2
                                is_tv = qid in {
                                    "tvseries", "tvminiseries", "tvepisode", "tvmovie"
                                }
                                if want_tv == is_tv:
                                    points += 3
                                return points

                            if hits:
                                best = max(hits, key=score)
                                if score(best) >= 3:
                                    imdb_id = best.get("id")
                                    resolved_title = best.get("l")
                                    resolved_year = best.get("y")
                    else:
                        _LOGGER.debug("IMDb suggestion HTTP %s for %s", resp.status, title)
        except Exception as err:
            _LOGGER.debug("IMDb suggestion failed for %s: %s", title, err)

        if self.store:
            self.store.set_metadata(
                cache_key,
                {
                    "imdb_id": imdb_id,
                    "resolved_title": resolved_title,
                    "resolved_year": resolved_year,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "cache_schema": METADATA_CACHE_SCHEMA,
                },
            )
        return imdb_id

    async def _async_age_certification(
        self,
        object_id,
        media_type,
        details_url=None,
        title=None,
        year=None,
        preferred_imdb_id=None,
    ):
        """Resolve both FR and US age classifications without conversion."""
        kind = "movie" if media_type == "movie" else "show"
        cache_id = object_id if object_id is not None else details_url or title or "unknown"
        cache_key = f"local-age-v1:{kind}:{cache_id}"
        if self.store:
            cached = self.store.get_metadata(cache_key)
            if _cache_fresh(cached):
                return {
                    "fr": cached.get("age_fr"),
                    "us": cached.get("age_us"),
                    "imdb_id": cached.get("imdb_id"),
                }

        jw_fr_age = None
        imdb_id = self._normalize_imdb_id(preferred_imdb_id)

        # JustWatch can expose a French age rating and sometimes the canonical IMDb id.
        if object_id is not None:
            url = (
                f"https://apis.justwatch.com/content/titles/{kind}/{object_id}"
                "/locale/fr_FR"
            )
            try:
                async with self._sem:
                    async with self.session.get(
                        url,
                        headers={
                            "User-Agent": UA,
                            "Accept": "application/json",
                            "Referer": "https://www.justwatch.com/fr/",
                        },
                        timeout=20,
                    ) as resp:
                        if resp.status < 400:
                            data = await resp.json()
                            if not imdb_id:
                                imdb_id = _find_imdb_id(data)
                            jw_fr_age = normalize_fr_age_certification(
                                data.get("age_certification")
                                or data.get("ageCertification")
                            )
                        else:
                            _LOGGER.debug(
                                "JustWatch detail HTTP %s for %s/%s",
                                resp.status, kind, object_id,
                            )
            except Exception as err:
                _LOGGER.debug(
                    "JustWatch detail failed for %s/%s: %s", kind, object_id, err
                )

        # French JustWatch public-page fallback.
        if not jw_fr_age and details_url:
            try:
                async with self._sem:
                    async with self.session.get(
                        details_url,
                        headers={
                            "User-Agent": UA,
                            "Accept": "text/html,application/xhtml+xml",
                            "Accept-Language": "fr-FR,fr;q=0.9",
                            "Referer": "https://www.justwatch.com/fr/",
                        },
                        timeout=20,
                    ) as resp:
                        if resp.status < 400:
                            page = await resp.text()
                            match = re.search(
                                r'"(?:ageCertification|age_certification)"\s*:\s*"([^"]+)"',
                                page, re.I,
                            )
                            if match:
                                jw_fr_age = normalize_fr_age_certification(match.group(1))
                            if not jw_fr_age:
                                cleaned = re.sub(
                                    r"(?is)<(?:script|style)\b.*?</(?:script|style)>",
                                    " ", page,
                                )
                                cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
                                cleaned = html.unescape(cleaned)
                                cleaned = re.sub(r"\s+", " ", cleaned)
                                match = re.search(
                                    r"\b(TP|10|12|16|18)\s+Âge\b", cleaned, re.I
                                )
                                if match:
                                    jw_fr_age = normalize_fr_age_certification(match.group(1))
            except Exception as err:
                _LOGGER.debug(
                    "JustWatch French age fallback failed for %s: %s", details_url, err
                )

        if not imdb_id:
            imdb_id = await self._async_imdb_id(title, year, media_type)

        imdb_certs = await self._async_imdb_certificates(imdb_id) if imdb_id else {}
        imdb_fr = normalize_fr_age_certification(imdb_certs.get("FR")) if imdb_certs else None
        imdb_us = normalize_us_age_certification(imdb_certs.get("US")) if imdb_certs else None

        # IMDb France has priority, with JustWatch France as fallback.
        fr_age = imdb_fr or jw_fr_age
        us_age = imdb_us

        result = {"fr": fr_age, "us": us_age, "imdb_id": imdb_id}
        if self.store:
            self.store.set_metadata(
                cache_key,
                {
                    "age_fr": fr_age,
                    "age_us": us_age,
                    "imdb_id": imdb_id,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "cache_schema": METADATA_CACHE_SCHEMA,
                },
            )
        return result



