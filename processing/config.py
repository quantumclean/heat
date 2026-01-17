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
# Geographic Bounds (Plainfield, NJ)
# ============================================
TARGET_LOCATION = "Plainfield, NJ"
TARGET_ZIPS = ["07060", "07062", "07063"]
TARGET_CENTER = (40.6137, -74.4154)
TARGET_RADIUS_KM = 10

# ZIP code centroids
ZIP_CENTROIDS = {
    "07060": (40.6137, -74.4154),  # Central Plainfield
    "07062": (40.6280, -74.4050),  # North Plainfield
    "07063": (40.5980, -74.4280),  # South Plainfield
}

# ============================================
# RSS Feeds (Verified Sources)
# ============================================
RSS_FEEDS = {
    # Local News
    "nj_com_union": {
        "url": "https://www.nj.com/arc/outboundfeeds/rss/category/news/union-county/?outputType=xml",
        "source": "NJ.com",
        "category": "news",
    },
    "tapinto_plainfield": {
        "url": "https://www.tapinto.net/towns/plainfield/sections/government/articles.rss",
        "source": "TAPinto Plainfield",
        "category": "news",
    },
    "tapinto_plainfield_police": {
        "url": "https://www.tapinto.net/towns/plainfield/sections/police-and-fire/articles.rss",
        "source": "TAPinto Plainfield",
        "category": "news",
    },
    # Google News (multiple searches for broader coverage)
    "google_news_plainfield": {
        "url": "https://news.google.com/rss/search?q=Plainfield+NJ+immigration&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
    },
    "google_news_ice_nj": {
        "url": "https://news.google.com/rss/search?q=ICE+New+Jersey&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
    },
    "google_news_ice_raids": {
        "url": "https://news.google.com/rss/search?q=ICE+raids+NJ&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
    },
    "google_news_union_county": {
        "url": "https://news.google.com/rss/search?q=Union+County+NJ+immigration&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
    },
    "google_news_nj_deportation": {
        "url": "https://news.google.com/rss/search?q=New+Jersey+deportation&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
    },
    "google_news_nj_sanctuary": {
        "url": "https://news.google.com/rss/search?q=New+Jersey+sanctuary+city&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
    },
    # Government
    "plainfield_city": {
        "url": "https://www.plainfieldnj.gov/feed/",
        "source": "City of Plainfield",
        "category": "government",
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
