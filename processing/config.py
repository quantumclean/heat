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

# Primary focus location (default) - dynamically set from TARGET_CITIES
# To change primary location, set PRIMARY_CITY environment variable
import os
PRIMARY_CITY = os.getenv("PRIMARY_CITY", "plainfield")  # Default to first city if not set

if PRIMARY_CITY in TARGET_CITIES:
    _primary = TARGET_CITIES[PRIMARY_CITY]
    TARGET_LOCATION = f"{PRIMARY_CITY.replace('_', ' ').title()}, {_primary['state']}"
    TARGET_ZIPS = _primary["zips"]
    TARGET_CENTER = _primary["center"]
    TARGET_RADIUS_KM = _primary["radius_km"]
else:
    # Fallback to first city in TARGET_CITIES
    _first_city = list(TARGET_CITIES.keys())[0]
    _primary = TARGET_CITIES[_first_city]
    TARGET_LOCATION = f"{_first_city.replace('_', ' ').title()}, {_primary['state']}"
    TARGET_ZIPS = _primary["zips"]
    TARGET_CENTER = _primary["center"]
    TARGET_RADIUS_KM = _primary["radius_km"]

# Get all ZIP codes from all cities for validation
ALL_ZIPS = []
for city_data in TARGET_CITIES.values():
    ALL_ZIPS.extend(city_data["zips"])

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
        "urls": [
            "https://www.tapinto.net/towns/plainfield/sections/government/articles.rss",
            "https://news.google.com/rss/search?q=site:tapinto.net+plainfield+NJ&hl=en-US&gl=US&ceid=US:en",
        ],
        "source": "TAPinto Plainfield",
        "category": "news",
        "cities": ["plainfield"],
    },
    "tapinto_plainfield_police": {
        "url": "https://www.tapinto.net/towns/plainfield/sections/police-and-fire/articles.rss",
        "urls": [
            "https://www.tapinto.net/towns/plainfield/sections/police-and-fire/articles.rss",
            "https://news.google.com/rss/search?q=site:tapinto.net+plainfield+police+fire&hl=en-US&gl=US&ceid=US:en",
        ],
        "source": "TAPinto Plainfield",
        "category": "news",
        "cities": ["plainfield"],
    },
    # "plainfield_city" removed — plainfieldnj.gov/feed/ not returning valid RSS
    "patch_plainfield": {
        "url": "https://patch.com/new-jersey/plainfield/rss",
        "urls": [
            "https://patch.com/new-jersey/plainfield/rss",
            "https://news.google.com/rss/search?q=site:patch.com+plainfield+NJ&hl=en-US&gl=US&ceid=US:en",
        ],
        "source": "Patch Plainfield",
        "category": "news",
        "cities": ["plainfield"],
    },

    # ===== HOBOKEN, NJ =====
    "tapinto_hoboken": {
        "url": "https://www.tapinto.net/towns/hoboken/sections/government/articles.rss",
        "urls": [
            "https://www.tapinto.net/towns/hoboken/sections/government/articles.rss",
            "https://news.google.com/rss/search?q=site:tapinto.net+hoboken+NJ&hl=en-US&gl=US&ceid=US:en",
        ],
        "source": "TAPinto Hoboken",
        "category": "news",
        "cities": ["hoboken"],
    },
    # "hoboken_official" removed — hobokennj.gov/news/feed/ not returning valid RSS
    "patch_hoboken": {
        "url": "https://patch.com/new-jersey/hoboken/rss",
        "urls": [
            "https://patch.com/new-jersey/hoboken/rss",
            "https://news.google.com/rss/search?q=site:patch.com+hoboken+NJ&hl=en-US&gl=US&ceid=US:en",
        ],
        "source": "Patch Hoboken",
        "category": "news",
        "cities": ["hoboken"],
    },

    # ===== TRENTON, NJ =====
    "tapinto_trenton": {
        "url": "https://www.tapinto.net/towns/trenton/sections/government/articles.rss",
        "urls": [
            "https://www.tapinto.net/towns/trenton/sections/government/articles.rss",
            "https://news.google.com/rss/search?q=site:tapinto.net+trenton+NJ&hl=en-US&gl=US&ceid=US:en",
        ],
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
    # "trenton_official" removed — trentonnj.gov/feed/ not returning valid RSS
    "patch_trenton": {
        "url": "https://patch.com/new-jersey/trenton/rss",
        "urls": [
            "https://patch.com/new-jersey/trenton/rss",
            "https://news.google.com/rss/search?q=site:patch.com+trenton+NJ&hl=en-US&gl=US&ceid=US:en",
        ],
        "source": "Patch Trenton",
        "category": "news",
        "cities": ["trenton"],
    },

    # ===== NEW BRUNSWICK, NJ =====
    "tapinto_new_brunswick": {
        "url": "https://www.tapinto.net/towns/new-brunswick/sections/government/articles.rss",
        "urls": [
            "https://www.tapinto.net/towns/new-brunswick/sections/government/articles.rss",
            "https://news.google.com/rss/search?q=site:tapinto.net+new+brunswick+NJ&hl=en-US&gl=US&ceid=US:en",
        ],
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
        "urls": [
            "https://patch.com/new-jersey/newbrunswick/rss",
            "https://news.google.com/rss/search?q=site:patch.com+new+brunswick+NJ&hl=en-US&gl=US&ceid=US:en",
        ],
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
    # "univision_nj" removed — univision.com/rss/noticias/new-jersey not returning valid RSS
    # "telemundo_nj" removed — telemundo47.com/rss/noticias/new-jersey not returning valid RSS
    "google_news_nj_ice_spanish": {
        "url": "https://news.google.com/rss/search?q=ICE+inmigraci%C3%B3n+Nueva+Jersey&hl=es-US&gl=US&ceid=US:es",
        "source": "Google News (ES)",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== ADDITIONAL NJ NEWS =====
    "north_jersey": {
        "url": "https://www.northjersey.com/arc/outboundfeeds/rss/",
        "urls": [
            "https://www.northjersey.com/arc/outboundfeeds/rss/",
            "https://news.google.com/rss/search?q=site:northjersey.com+New+Jersey&hl=en-US&gl=US&ceid=US:en",
        ],
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

    # ===== NEWS12 NJ =====
    "news12_nj": {
        "url": "https://newjersey.news12.com/rss",
        "source": "News 12 New Jersey",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== REDDIT r/newjersey (RSS — no API credentials needed) =====
    "reddit_newjersey_immigration": {
        "url": "https://www.reddit.com/r/newjersey/search.rss?q=ICE+OR+immigration+OR+deportation+OR+sanctuary&restrict_sr=on&sort=new",
        "source": "Reddit r/newjersey",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "reddit_newjersey_enforcement": {
        "url": "https://www.reddit.com/r/newjersey/search.rss?q=ICE+OR+raid+OR+checkpoint+OR+enforcement&restrict_sr=on&sort=new",
        "source": "Reddit r/newjersey",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "reddit_newjersey_general": {
        "url": "https://www.reddit.com/r/newjersey/.rss",
        "source": "Reddit r/newjersey",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== ADDITIONAL GOOGLE NEWS TARGETED SEARCHES =====
    "google_news_ice_plainfield": {
        "url": "https://news.google.com/rss/search?q=ICE+Plainfield+NJ&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["plainfield"],
    },
    "google_news_ice_students_nj": {
        "url": "https://news.google.com/rss/search?q=ICE+students+protest+New+Jersey&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "google_news_ice_surveillance": {
        "url": "https://news.google.com/rss/search?q=ICE+surveillance+New+Jersey&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== ACLU / LEGAL ADVOCACY (Free RSS) =====
    "aclu_nj": {
        "url": "https://www.aclu-nj.org/feed/",
        "source": "ACLU-NJ",
        "category": "advocacy",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "aclu_national_immigrants": {
        "url": "https://www.aclu.org/issues/immigrants-rights/feed/",
        "urls": [
            "https://www.aclu.org/issues/immigrants-rights/feed/",
            "https://news.google.com/rss/search?q=site:aclu.org+immigration+New+Jersey&hl=en-US&gl=US&ceid=US:en",
        ],
        "source": "ACLU National",
        "category": "advocacy",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== ADDITIONAL REDDIT SUBS (RSS — no credentials needed) =====
    "reddit_immigration": {
        "url": "https://www.reddit.com/r/immigration/search.rss?q=New+Jersey+OR+NJ&restrict_sr=on&sort=new",
        "source": "Reddit r/immigration",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "reddit_hoboken": {
        "url": "https://www.reddit.com/r/Hoboken/search.rss?q=ICE+OR+immigration+OR+sanctuary&restrict_sr=on&sort=new",
        "source": "Reddit r/Hoboken",
        "category": "community",
        "cities": ["hoboken"],
    },
    "reddit_newbrunswick": {
        "url": "https://www.reddit.com/r/NewBrunswickNJ/search.rss?q=ICE+OR+immigration+OR+sanctuary&restrict_sr=on&sort=new",
        "source": "Reddit r/NewBrunswickNJ",
        "category": "community",
        "cities": ["new_brunswick"],
    },
    "reddit_newark": {
        "url": "https://www.reddit.com/r/Newark/search.rss?q=ICE+OR+immigration+OR+sanctuary&restrict_sr=on&sort=new",
        "source": "Reddit r/Newark",
        "category": "community",
        "cities": ["plainfield", "hoboken"],
    },
    "reddit_jerseycity": {
        "url": "https://www.reddit.com/r/jerseycity/search.rss?q=ICE+OR+immigration+OR+sanctuary&restrict_sr=on&sort=new",
        "source": "Reddit r/jerseycity",
        "category": "community",
        "cities": ["hoboken"],
    },
    "reddit_nj_politics": {
        "url": "https://www.reddit.com/r/nj_politics/search.rss?q=ICE+OR+immigration+OR+deportation+OR+sanctuary&restrict_sr=on&sort=new",
        "source": "Reddit r/nj_politics",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "reddit_newjersey_daca": {
        "url": "https://www.reddit.com/r/newjersey/search.rss?q=DACA+OR+dreamers+OR+undocumented+OR+asylum&restrict_sr=on&sort=new",
        "source": "Reddit r/newjersey",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== GOOGLE NEWS — CITY-SPECIFIC IMMIGRATION =====
    "google_news_ice_hoboken": {
        "url": "https://news.google.com/rss/search?q=ICE+immigration+Hoboken+NJ&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["hoboken"],
    },
    "google_news_ice_trenton": {
        "url": "https://news.google.com/rss/search?q=ICE+immigration+Trenton+NJ&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["trenton"],
    },
    "google_news_ice_new_brunswick": {
        "url": "https://news.google.com/rss/search?q=ICE+immigration+%22New+Brunswick%22+NJ&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["new_brunswick"],
    },
    "google_news_nj_daca": {
        "url": "https://news.google.com/rss/search?q=DACA+dreamers+New+Jersey&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "google_news_nj_detention": {
        "url": "https://news.google.com/rss/search?q=immigration+detention+New+Jersey&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "google_news_nj_know_your_rights": {
        "url": "https://news.google.com/rss/search?q=%22know+your+rights%22+immigration+New+Jersey&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== SPANISH-LANGUAGE — ADDITIONAL QUERIES =====
    "google_news_nj_deportacion_es": {
        "url": "https://news.google.com/rss/search?q=deportaci%C3%B3n+Nueva+Jersey&hl=es-US&gl=US&ceid=US:es",
        "source": "Google News (ES)",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "google_news_nj_redadas_es": {
        "url": "https://news.google.com/rss/search?q=redadas+ICE+Nueva+Jersey&hl=es-US&gl=US&ceid=US:es",
        "source": "Google News (ES)",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== NJ LEGISLATURE / GOVERNMENT (Free) =====
    "nj_legislature": {
        "url": "https://news.google.com/rss/search?q=site:njleg.state.nj.us+immigration&hl=en-US&gl=US&ceid=US:en",
        "source": "NJ Legislature",
        "category": "government",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== UNION COUNTY NEWS (Free) =====
    "tapinto_union_county": {
        "url": "https://www.tapinto.net/towns/union/sections/government/articles.rss",
        "urls": [
            "https://www.tapinto.net/towns/union/sections/government/articles.rss",
            "https://news.google.com/rss/search?q=site:tapinto.net+union+county+NJ&hl=en-US&gl=US&ceid=US:en",
        ],
        "source": "TAPinto Union County",
        "category": "news",
        "cities": ["plainfield"],
    },
    "patch_scotch_plains": {
        "url": "https://patch.com/new-jersey/scotchplains/rss",
        "source": "Patch Scotch Plains",
        "category": "news",
        "cities": ["plainfield"],
    },

    # ===== COURTLISTENER (Free — Federal Immigration Court) =====
    "google_news_nj_immigration_court": {
        "url": "https://news.google.com/rss/search?q=%22immigration+court%22+New+Jersey&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News",
        "category": "legal",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== MASTODON HASHTAG RSS (Atom — no auth needed) =====
    # Mastodon feeds are Atom format with <content> (not <summary>).
    # The scraper's parse_atom_entry handles this via the content fallback.
    "mastodon_immigration": {
        "url": "https://mastodon.social/tags/immigration.rss",
        "source": "Mastodon #immigration",
        "category": "community",
        "feed_format": "mastodon_rss",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "mastodon_ice": {
        "url": "https://mastodon.social/tags/ICE.rss",
        "source": "Mastodon #ICE",
        "category": "community",
        "feed_format": "mastodon_rss",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "mastodon_sanctuary": {
        "url": "https://mastodon.social/tags/sanctuary.rss",
        "source": "Mastodon #sanctuary",
        "category": "community",
        "feed_format": "mastodon_rss",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "mastodon_deportation": {
        "url": "https://mastodon.social/tags/deportation.rss",
        "source": "Mastodon #deportation",
        "category": "community",
        "feed_format": "mastodon_rss",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "mastodon_abolishice": {
        "url": "https://mastodon.social/tags/AbolishICE.rss",
        "source": "Mastodon #AbolishICE",
        "category": "community",
        "feed_format": "mastodon_rss",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== MEDIUM (via Google News — personal blogs & opinion) =====
    "medium_nj_immigration": {
        "url": "https://news.google.com/rss/search?q=site:medium.com+immigration+%22New+Jersey%22&hl=en-US&gl=US&ceid=US:en",
        "source": "Medium (via Google News)",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "medium_ice_sanctuary": {
        "url": "https://news.google.com/rss/search?q=site:medium.com+ICE+OR+sanctuary+OR+deportation+NJ&hl=en-US&gl=US&ceid=US:en",
        "source": "Medium (via Google News)",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== SUBSTACK (via Google News — independent newsletters) =====
    "substack_nj_immigration": {
        "url": "https://news.google.com/rss/search?q=site:substack.com+immigration+%22New+Jersey%22+OR+NJ&hl=en-US&gl=US&ceid=US:en",
        "source": "Substack (via Google News)",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== CHANGE.ORG (via Google News — civic petitions) =====
    "changeorg_nj_immigration": {
        "url": "https://news.google.com/rss/search?q=site:change.org+immigration+%22New+Jersey%22+OR+NJ&hl=en-US&gl=US&ceid=US:en",
        "source": "Change.org (via Google News)",
        "category": "advocacy",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== DAILY TARGUM — Rutgers student journalism =====
    "daily_targum": {
        "url": "https://dailytargum.com/feed/",
        "urls": [
            "https://dailytargum.com/feed/",
            "https://news.google.com/rss/search?q=site:dailytargum.com+immigration+OR+ICE+OR+undocumented&hl=en-US&gl=US&ceid=US:en",
        ],
        "source": "Daily Targum",
        "category": "news",
        "cities": ["new_brunswick"],
    },

    # ===== DOCUMENTED NY — immigrant-community-first journalism =====
    "documented_ny": {
        "url": "https://documentedny.com/feed/",
        "urls": [
            "https://documentedny.com/feed/",
            "https://news.google.com/rss/search?q=site:documentedny.com+New+Jersey+OR+Newark&hl=en-US&gl=US&ceid=US:en",
        ],
        "source": "Documented NY",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== NJ MONITOR — nonprofit civic journalism =====
    "nj_monitor": {
        "url": "https://newjerseymonitor.com/feed/",
        "urls": [
            "https://newjerseymonitor.com/feed/",
            "https://news.google.com/rss/search?q=site:newjerseymonitor.com+immigration&hl=en-US&gl=US&ceid=US:en",
        ],
        "source": "NJ Monitor",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== WNYC NJ — NPR community reporting =====
    "wnyc_nj": {
        "url": "https://feeds.wnyc.org/nj-news",
        "urls": [
            "https://feeds.wnyc.org/nj-news",
            "https://news.google.com/rss/search?q=site:wnyc.org+New+Jersey+immigration&hl=en-US&gl=US&ceid=US:en",
        ],
        "source": "WNYC NJ",
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
    # Grassroots / community-signal keywords (for Mastodon, Medium, petitions)
    "petition", "organizing", "solidarity", "rally",
    "protest", "march", "abolish", "resist",
    "campus", "students", "rutgers", "documented",
    "newsletter", "immigration court", "newark",
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
# Safety Thresholds (Buffer Stage) - PRODUCTION SETTINGS
# ============================================
MIN_CLUSTER_SIZE = 2      # Production minimum for data quality
MIN_SOURCES = 2           # Production minimum for source corroboration
MIN_VOLUME_SCORE = 1.0    # Production minimum volume threshold
MIN_QUALITY_SCORE = 0.4   # Composite quality floor (0-1) from signal_quality.py

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
        "title": "Sustained Community Focus",
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

# ============================================
# CONSOLIDATED THRESHOLD CONFIGURATION
# ============================================
"""
All safety and detection thresholds centralized in this section.
Each threshold is calibrated to balance community safety awareness with
responsible information handling for ICE activity tracking.
"""

# --- Clustering Thresholds ---

MIN_CLUSTER_SIZE_PRODUCTION = 1
"""
Minimum number of signals required to form a valid cluster - MAXIMUM SENSITIVITY.

UPDATED: Lowered to 1 to show ALL activity and match other apps with high visibility.
Shows single signals, pairs, and all patterns for comprehensive coverage.
"""

MIN_SOURCE_CORROBORATION = 2
"""
Minimum number of distinct sources required to validate a cluster.

WHY 2: Ensures cross-validation between independent reporting channels. A single
source (even with multiple posts) could reflect rumor propagation rather than
verified activity. Two independent sources provide basic corroboration while
remaining achievable for legitimate signals in our monitoring scope.
"""

# --- Safety Delay Thresholds ---

SAFETY_DELAY_HOURS_CONTRIBUTOR = 24
"""
Time delay (in hours) before Tier 1 contributors see aggregated patterns.

WHY 24: Provides a 1-day buffer to allow for:
1. Signal validation and clustering
2. Cross-source verification
3. Removal of false positives or speculation
4. Pattern stabilization vs. immediate reactive posts

This delay ensures contributors receive higher-confidence information while
still providing timely community awareness.
"""

SAFETY_DELAY_HOURS_PUBLIC = 72
"""
Time delay (in hours) before Tier 0 public users see heatmap data.

WHY 72: The 3-day public delay serves multiple safety purposes:
1. Allows full pattern verification across multiple news cycles
2. Prevents real-time surveillance or tactical use of the data
3. Ensures temporal decoupling from specific operational timeframes
4. Reduces risk of location-specific targeting or harassment
5. Aligns with responsible disclosure practices for sensitive civic data

The 72-hour window is the minimum necessary to convert "live intelligence"
into "historical pattern awareness" while maintaining community value.
"""

# --- Temporal Analysis Thresholds ---

TIME_DECAY_HALF_LIFE_HOURS = 72
"""
Half-life (in hours) for exponential time decay scoring.

WHY 72: Matches the public safety delay window. Signals older than 3 days begin
losing relevance for current awareness while remaining valuable for historical
pattern analysis. This decay rate ensures:
1. Recent patterns carry more weight in current assessments
2. Historical data doesn't artificially inflate current threat perception
3. Seasonal or cyclical patterns emerge over multi-week analysis

The 72-hour half-life creates a natural "attention decay" that parallels
community memory and news cycle rhythms.
"""

# --- Statistical Detection Thresholds ---

BURST_DETECTION_STD_THRESHOLD = 2.0
"""
Standard deviations above rolling mean to trigger burst detection.

WHY 2.0: Represents approximately 95th percentile (95% confidence interval).
This threshold captures genuinely anomalous spikes while filtering normal
variation in reporting volume. For ICE activity tracking:
- Too low (1.0-1.5): Excessive false alarms from normal news cycles
- Too high (2.5+): Misses significant community attention shifts
- 2.0: Industry standard for anomaly detection, balances sensitivity/specificity
"""

SPIKE_DETECTION_STD_THRESHOLD = 2.0
"""
Standard deviations above baseline for spike alert classification (Class A).

WHY 2.0: Identical to burst detection for consistency. Class A alerts indicate
rapid-onset attention changes that may reflect breaking news or community concerns.
The 2-sigma threshold ensures alerts represent statistically significant deviations,
not random fluctuations, maintaining alert credibility and preventing fatigue.
"""

SUSTAINED_THRESHOLD_STD = 1.5
"""
Standard deviations above baseline for sustained pattern classification (Class B).

WHY 1.5: Lower than spike threshold (2.0) because sustained patterns are validated
over time rather than instantaneous. A moderate elevation (1.5σ ≈ 87th percentile)
maintained over 24+ hours indicates persistent community attention without requiring
extreme volume spikes. This allows detection of:
- Ongoing policy debates
- Prolonged community responses
- Multi-day event coverage

The lower threshold compensates for temporal validation—persistence itself is evidence.
"""

ATTENTION_DECAY_MULTIPLIER = 0.5
"""
Multiplier for baseline comparison to trigger Class C decay alerts.

WHY 0.5: Class C alerts signal when attention drops below 50% of recent baseline,
indicating a "return to normal" after elevated periods. This threshold:
1. Avoids alert spam during normal low-activity periods
2. Marks clear transitions from heightened to baseline attention
3. Provides closure signals after sustained elevated patterns

The 0.5 multiplier is conservative—only triggers when attention clearly recedes,
not just minor downward fluctuations.
"""

# --- Source Reliability Weights ---

SOURCE_RELIABILITY = {
    "official_government": 1.0,   # Maximum weight: official records, FOIA responses
    "credentialed_news": 0.9,     # Professional journalism with editorial oversight
    "local_news": 0.8,            # Regional outlets, Patch, TAPinto with local verification
    "community_verified": 0.7,    # Community reporters with established credibility
    "social_corroborated": 0.5,   # Social media posts with 2+ independent confirmations
    "single_report": 0.3,         # Unverified single-source claims (flagged for review)
    "anonymous": 0.1,             # Anonymous tips (lowest weight, requires heavy corroboration)
}
"""
Source reliability weights for signal scoring.

Official government sources (1.0) include FOIA responses, court records, official statements.
Credentialed news (0.9) includes outlets with professional journalism standards.
Local news (0.8) captures regional outlets with community verification.
Community verified (0.7) represents trusted community reporters with track records.
Social corroborated (0.5) requires multi-source social media confirmation.
Single reports (0.3) and anonymous tips (0.1) receive minimal weight until corroborated.

These weights ensure multi-source professional journalism clusters rise above
unverified social media speculation while still capturing grassroots signals.
"""

# --- Severity Classification Bands ---

SEVERITY_BANDS = {
    "minimal": {
        "score_range": (0.0, 0.3),
        "label": "Baseline Community Attention",
        "description": "Normal background discussion levels. No unusual patterns detected.",
        "color": "#E8F5E9",  # Light green
        "action": None,
    },
    "moderate": {
        "score_range": (0.3, 0.5),
        "label": "Moderate Community Discussion",
        "description": "Slightly elevated attention. May reflect local news coverage or community conversations.",
        "color": "#FFF9C4",  # Light yellow
        "action": "Monitor for pattern development",
    },
    "elevated": {
        "score_range": (0.5, 0.7),
        "label": "Elevated Community Focus",
        "description": "Sustained attention above baseline. Multiple sources reporting related topics.",
        "color": "#FFE0B2",  # Light orange
        "action": "Review sources and verify clustering",
    },
    "high": {
        "score_range": (0.7, 0.85),
        "label": "High Community Attention",
        "description": "Significant multi-source discussion. Pattern likely reflects notable community concerns or events.",
        "color": "#FFCCBC",  # Peach
        "action": "Verify contributor tier release; monitor for misinformation",
    },
    "very_high": {
        "score_range": (0.85, 1.0),
        "label": "Very High Community Attention",
        "description": "Exceptional discussion levels. Wide-scale coverage across multiple verified sources.",
        "color": "#FFCDD2",  # Light red
        "action": "Full verification required; consider early contributor notification",
    },
}
"""
Severity bands for visual heatmap display and alert classification.

These bands translate raw statistical scores into human-readable community attention levels.
Labels deliberately avoid enforcement language ("raid", "operation") and focus on
discussion/attention metrics rather than claiming specific ICE activities.

Color palette uses warm gradients (green→yellow→orange→red) following standard
heatmap conventions while avoiding alarm-inducing saturation levels.

Actions provide internal guidance for moderators on appropriate responses at each level.
Public-facing descriptions emphasize that scores reflect *discussion patterns*, not
confirmed enforcement activities, maintaining epistemic humility.
"""

# --- Data Quality Flags ---

DATA_QUALITY_FLAGS = {
    "HIGH_CONFIDENCE": "verified_multi_source",      # 3+ sources, 2+ source types
    "MODERATE_CONFIDENCE": "corroborated",          # 2 sources, credible outlets
    "LOW_CONFIDENCE": "single_source",              # 1 source, needs verification
    "UNVERIFIED": "unconfirmed",                    # No corroboration, flagged
    "DISPUTED": "conflicting_reports",              # Contradictory signals
    "TEMPORAL_MISMATCH": "time_discrepancy",        # Signals span >72 hours
    "GEOGRAPHIC_AMBIGUITY": "location_unclear",     # ZIP/location confidence <0.5
    "REQUIRES_REVIEW": "manual_verification_needed", # Flagged for human oversight
}
"""
Data quality flags for cluster validation and display filtering.

HIGH_CONFIDENCE: Displays on contributor tier (Tier 1) without additional warnings
MODERATE_CONFIDENCE: Displays with "developing pattern" caveat
LOW_CONFIDENCE: Contributor tier only, marked "preliminary"
UNVERIFIED: Held for moderator review (Tier 2), never auto-released
DISPUTED: Flagged for investigation, may indicate misinformation
TEMPORAL_MISMATCH: Signals cluster geographically but not temporally—likely unrelated
GEOGRAPHIC_AMBIGUITY: Location extraction below confidence threshold
REQUIRES_REVIEW: Catch-all for automated filters triggering manual review queue

These flags enable tiered release logic: HIGH→Contributor, MODERATE→Delayed, LOW→Held.
"""
