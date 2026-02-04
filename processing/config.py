"""
HEAT Configuration
Central config for all pipeline components.
"""
from pathlib import Path
from datetime import timedelta

# ============================================
# Paths
# ============================================
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
BUILD_DIR = BASE_DIR / "build"
EXPORTS_DIR = BUILD_DIR / "exports"

# Ensure directories exist
for d in [RAW_DIR, PROCESSED_DIR, BUILD_DIR, EXPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================
# Geographic Bounds - Multi-City Coverage
# ============================================
# Primary focus cities with their regions
TARGET_CITIES = {
    "plainfield": {
        "state": "NJ",
        "zips": ["07060", "07062", "07063"],
        "center": (40.6137, -74.4154),
        "radius_km": 5,
    },
    "edison": {
        "state": "NJ",
        "zips": ["08817", "08820", "08837"],
        "center": (40.5300, -74.3930),
        "radius_km": 6,
    },
    "hoboken": {
        "state": "NJ",
        "zips": ["07030"],
        "center": (40.7350, -74.0303),
        "radius_km": 3,
    },
    "trenton": {
        "state": "NJ",
        "zips": ["08608", "08609", "08610", "08611", "08618", "08619"],
        "center": (40.2206, -74.7597),
        "radius_km": 5,
    },
    "new_brunswick": {
        "state": "NJ",
        "zips": ["08901", "08902", "08903", "08906"],
        "center": (40.4862, -74.4518),
        "radius_km": 4,
    },
}

# Primary focus location (default)
TARGET_LOCATION = "Plainfield, NJ"
TARGET_ZIPS = ["07060", "07062", "07063"]
TARGET_CENTER = (40.6137, -74.4154)
TARGET_RADIUS_KM = 10

# Comprehensive ZIP code centroids (all regions)
ZIP_CENTROIDS = {
    # Plainfield
    "07060": (40.6137, -74.4154),  # Central Plainfield
    "07062": (40.6280, -74.4050),  # North Plainfield
    "07063": (40.5980, -74.4280),  # South Plainfield
    # Edison
    "08817": (40.5300, -74.3930),  # Edison (Vineyard Rd / Route 1 area)
    "08820": (40.5800, -74.3600),  # North Edison
    "08837": (40.5290, -74.3370),  # Raritan Center / Edison
    # Hoboken
    "07030": (40.7350, -74.0303),  # Hoboken
    # Trenton
    "08608": (40.2206, -74.7597),  # Central Trenton
    "08609": (40.2250, -74.7520),  # Trenton
    "08610": (40.2180, -74.7650),  # Trenton
    "08611": (40.2280, -74.7450),  # Trenton
    "08618": (40.2120, -74.7750),  # Trenton
    "08619": (40.2340, -74.7350),  # Trenton
    # New Brunswick
    "08901": (40.4862, -74.4518),  # Central New Brunswick
    "08902": (40.4950, -74.4400),  # New Brunswick
    "08903": (40.4750, -74.4600),  # New Brunswick
    "08906": (40.4950, -74.4700),  # New Brunswick
}

# ============================================
# Location Extraction Settings
# ============================================
LOCATION_CONFIDENCE_THRESHOLD = 0.5  # Minimum confidence to include location
MANUAL_REVIEW_THRESHOLD = 0.7        # Below this needs human review

# Location extraction is used to enrich records with geographic data
# and ensure proper ZIP code assignment for clusters. Low-confidence
# extractions are flagged for manual verification to prevent
# misinformation about specific locations.

# ============================================
# RSS Feeds (Expanded Multi-City Coverage)
# ============================================
RSS_FEEDS = {
    # ===== PLAINFIELD, NJ =====
    "nj_com_union": {
        "url": "https://www.nj.com/arc/outboundfeeds/rss/category/news/union-county/?outputType=xml",
        "source": "NJ.com",
        "category": "news",
        "cities": ["plainfield"],
    },
    "tapinto_plainfield": {
        "url": "https://www.tapinto.net/towns/plainfield/sections/government/articles.rss",
        "source": "TAPinto Plainfield",
        "category": "news",
        "cities": ["plainfield"],
    },
    "tapinto_plainfield_police": {
        "url": "https://www.tapinto.net/towns/plainfield/sections/police-and-fire/articles.rss",
        "source": "TAPinto Plainfield",
        "category": "news",
        "cities": ["plainfield"],
    },
    "plainfield_city": {
        "url": "https://www.plainfieldnj.gov/feed/",
        "source": "City of Plainfield",
        "category": "government",
        "cities": ["plainfield"],
    },
    "patch_plainfield": {
        "url": "https://patch.com/new-jersey/plainfield/rss",
        "source": "Patch Plainfield",
        "category": "news",
        "cities": ["plainfield"],
    },

    # ===== HOBOKEN, NJ =====
    "tapinto_hoboken": {
        "url": "https://www.tapinto.net/towns/hoboken/sections/government/articles.rss",
        "source": "TAPinto Hoboken",
        "category": "news",
        "cities": ["hoboken"],
    },
    "hoboken_official": {
        "url": "https://hobokennj.gov/news/feed/",
        "source": "City of Hoboken",
        "category": "government",
        "cities": ["hoboken"],
    },
    "patch_hoboken": {
        "url": "https://patch.com/new-jersey/hoboken/rss",
        "source": "Patch Hoboken",
        "category": "news",
        "cities": ["hoboken"],
    },

    # ===== TRENTON, NJ =====
    "tapinto_trenton": {
        "url": "https://www.tapinto.net/towns/trenton/sections/government/articles.rss",
        "source": "TAPinto Trenton",
        "category": "news",
        "cities": ["trenton"],
    },
    "nj_com_mercer": {
        "url": "https://www.nj.com/arc/outboundfeeds/rss/category/news/mercer-county/?outputType=xml",
        "source": "NJ.com",
        "category": "news",
        "cities": ["trenton"],
    },
    "trenton_official": {
        "url": "https://www.trentonnj.gov/feed/",
        "source": "City of Trenton",
        "category": "government",
        "cities": ["trenton"],
    },
    "patch_trenton": {
        "url": "https://patch.com/new-jersey/trenton/rss",
        "source": "Patch Trenton",
        "category": "news",
        "cities": ["trenton"],
    },

    # ===== NEW BRUNSWICK, NJ =====
    "tapinto_new_brunswick": {
        "url": "https://www.tapinto.net/towns/new-brunswick/sections/government/articles.rss",
        "source": "TAPinto New Brunswick",
        "category": "news",
        "cities": ["new_brunswick"],
    },
    "nj_com_middlesex": {
        "url": "https://www.nj.com/arc/outboundfeeds/rss/category/news/middlesex-county/?outputType=xml",
        "source": "NJ.com",
        "category": "news",
        "cities": ["new_brunswick"],
    },
    "patch_new_brunswick": {
        "url": "https://patch.com/new-jersey/newbrunswick/rss",
        "source": "Patch New Brunswick",
        "category": "news",
        "cities": ["new_brunswick"],
    },

    # ===== MULTI-REGION COVERAGE =====
    "google_news_nj_immigration": {
        "url": "https://news.google.com/rss/search?q=New+Jersey+immigration&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "google_news_ice_nj": {
        "url": "https://news.google.com/rss/search?q=ICE+New+Jersey&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "google_news_ice_raids": {
        "url": "https://news.google.com/rss/search?q=ICE+raids+NJ&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "google_news_nj_sanctuary": {
        "url": "https://news.google.com/rss/search?q=New+Jersey+sanctuary+city&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "google_news_nj_deportation": {
        "url": "https://news.google.com/rss/search?q=New+Jersey+deportation&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== SPANISH-LANGUAGE NEWS =====
    "univision_nj": {
        "url": "https://www.univision.com/rss/noticias/new-jersey",
        "source": "Univision NJ",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "telemundo_nj": {
        "url": "https://www.telemundo47.com/rss/noticias/new-jersey",
        "source": "Telemundo 47 NJ",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== ADDITIONAL NJ NEWS =====
    "north_jersey": {
        "url": "https://www.northjersey.com/arc/outboundfeeds/rss/",
        "source": "North Jersey",
        "category": "news",
        "cities": ["hoboken", "plainfield", "new_brunswick"],
    },
    "app_news": {
        "url": "https://www.app.com/arc/outboundfeeds/rss/",
        "source": "Asbury Park Press",
        "category": "news",
        "cities": ["new_brunswick", "trenton"],
    },
    "politico_nj": {
        "url": "https://www.politico.com/rss/new-jersey.xml",
        "source": "Politico NJ",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "nj_spotlight": {
        "url": "https://www.njspotlightnews.org/feed/",
        "source": "NJ Spotlight News",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
}

# Civic keywords for filtering
CIVIC_KEYWORDS = [
    "immigration", "ice", "deportation", "enforcement",
    "sanctuary", "undocumented", "immigrant", "migrant",
    "detention", "raid", "checkpoint", "visa",
    "asylum", "border", "daca", "dreamers",
    "community", "council", "hearing", "resolution",
    "legal aid", "know your rights", "advocacy",
    "plainfield", "union county", "new jersey",
]

# ============================================
# Time Settings
# ============================================
# Public tier delay (Tier 0)
PUBLIC_DELAY_HOURS = 72  # 3 days for public

# Contributor tier delay (Tier 1)
CONTRIBUTOR_DELAY_HOURS = 24  # 1 day for opt-in contributors

# Time decay for scoring
HALF_LIFE_HOURS = 168  # 7 days

# Alert thresholds
ALERT_SPIKE_THRESHOLD = 2.0  # Standard deviations for Class A
ALERT_SUSTAINED_HOURS = 24   # Hours above threshold for Class B
ALERT_DECAY_THRESHOLD = 0.5  # Below baseline for Class C

# ============================================
# Safety Thresholds (Buffer Stage)
# ============================================
MIN_CLUSTER_SIZE = 3      # Minimum signals per cluster
MIN_SOURCES = 2           # Minimum distinct sources
MIN_VOLUME_SCORE = 1.0    # Minimum weighted score

# ============================================
# Digest Settings
# ============================================
DIGEST_FREQUENCY = "weekly"  # weekly, daily
DIGEST_DAY = "sunday"        # Day to generate weekly digest

# ============================================
# Tier Definitions
# ============================================
TIERS = {
    0: {
        "name": "Public",
        "delay_hours": PUBLIC_DELAY_HOURS,
        "sees": ["heatmap", "concept_cards", "historical_timeline"],
        "hidden": ["alerts", "recent_spikes", "raw_text", "timestamps"],
    },
    1: {
        "name": "Contributor",
        "delay_hours": CONTRIBUTOR_DELAY_HOURS,
        "sees": ["pattern_alerts", "trend_direction", "weekly_digest"],
        "hidden": ["raw_submissions", "exact_counts", "exact_times"],
    },
    2: {
        "name": "Moderator",
        "delay_hours": 0,
        "sees": ["raw_submissions", "source_metadata", "diagnostics"],
        "hidden": [],  # Sees everything, but doesn't auto-publish
    },
    3: {
        "name": "System",
        "delay_hours": 0,
        "sees": ["embeddings", "scores", "logs", "thresholds"],
        "hidden": [],  # Internal only, never exposed
    },
}

# ============================================
# Safe Alert Copy Templates (Verbatim)
# ============================================
ALERT_TEMPLATES = {
    "class_a": {
        "title": "Community Attention Update",
        "body": (
            "ICE-related discussion intensity increased in your area today "
            "compared to recent baseline.\n\n"
            "This reflects a change in public conversation, not confirmation "
            "of specific events or locations."
        ),
        "trigger": "rate_spike",
    },
    "class_b": {
        "title": "Sustained Civic Focus Detected",
        "body": (
            "ICE-related topics have remained elevated in your area over "
            "the past day.\n\n"
            "Patterns are based on aggregated public information and opt-in reports."
        ),
        "trigger": "sustained_threshold",
    },
    "class_c": {
        "title": "Attention Update",
        "body": (
            "ICE-related discussion in your area has returned toward "
            "recent baseline levels."
        ),
        "trigger": "decay_below_baseline",
    },
}

# Forbidden words in alerts (hard rule)
FORBIDDEN_ALERT_WORDS = [
    "presence", "sighting", "activity", "raid", "operation",
    "spotted", "seen", "located", "arrest", "detained",
    "vehicle", "van", "agent", "officer", "uniform",
]

# ============================================
# Scraper Settings
# ============================================
SCRAPER_USER_AGENT = "HEAT-CivicSignalMap/1.0 (Research; https://github.com/heat-map)"
SCRAPER_REQUEST_DELAY = 2.0  # Seconds between requests
SCRAPER_TIMEOUT = 30         # Request timeout in seconds
SCRAPER_MAX_RETRIES = 3      # Retry failed requests
