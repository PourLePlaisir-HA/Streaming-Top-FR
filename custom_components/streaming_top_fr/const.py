DOMAIN = "streaming_top_fr"
PLATFORMS = ["binary_sensor"]
CONF_UPDATE_HOURS = "update_hours"
DEFAULT_UPDATE_HOURS = 6
NETFLIX_COUNTRIES_TSV = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"
JUSTWATCH_GRAPHQL = "https://apis.justwatch.com/graphql"
JUSTWATCH_IMAGE_BASE = "https://images.justwatch.com"

# Supported subscription services. Package resolution is performed dynamically
# against JustWatch France. Fallback short codes are only used where known.
PROVIDER_DEFINITIONS = {
    "netflix": {
        "name": "Netflix",
        "aliases": ["netflix"],
        "fallback_codes": ["nfx"],
    },
    "disney": {
        "name": "Disney+",
        "aliases": ["disney+", "disney plus"],
        "fallback_codes": ["dnp"],
    },
    "prime": {
        "name": "Prime Video",
        "aliases": ["amazon prime video", "prime video"],
        "fallback_codes": ["amp"],
    },
    "hbo_max": {
        "name": "HBO Max",
        "aliases": ["hbo max", "max"],
        "fallback_codes": [],
    },
    "apple_tv": {
        "name": "Apple TV+",
        "aliases": ["apple tv+", "apple tv plus"],
        "fallback_codes": [],
    },
    "paramount": {
        "name": "Paramount+",
        "aliases": ["paramount+", "paramount plus"],
        "fallback_codes": [],
    },
    "canal": {
        "name": "CANAL+",
        "aliases": ["canal+", "canal plus"],
        "fallback_codes": [],
    },
    "crunchyroll": {
        "name": "Crunchyroll",
        "aliases": ["crunchyroll"],
        "fallback_codes": [],
    },
    "mubi": {
        "name": "MUBI",
        "aliases": ["mubi"],
        "fallback_codes": [],
    },
    "adn": {
        "name": "ADN",
        "aliases": ["animation digital network", "adn"],
        "fallback_codes": [],
    },
}

PROVIDER_NAMES = {key: value["name"] for key, value in PROVIDER_DEFINITIONS.items()}
SUPPORTED_PROVIDERS = tuple(PROVIDER_DEFINITIONS.keys())

STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}.store"

METADATA_CACHE_DAYS = 14

# Increment when cached metadata shape/quality requirements change.
METADATA_CACHE_SCHEMA = 9
