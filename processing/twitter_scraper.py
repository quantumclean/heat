"""
Twitter/X Scraper for They Are Here
Ingests tweets from NJ-related accounts and hashtags via Twitter API v2.

Setup:
1. Create Twitter Developer account: https://developer.x.com
2. Create a Project and App
3. Generate credentials:
   - API Key (Consumer Key)
   - API Secret (Consumer Secret)
   - Bearer Token (recommended for v2 API)
   - Or: Access Token + Access Token Secret
4. Set environment variables:
   - X_BEARER_TOKEN (easiest - use this for read-only access)
   - Or: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
5. Free tier limits: 500k tweets/month (v2 Essential), 10k tweets/month (v2 Elevated)

Documentation:
- Developer Portal: https://developer.x.com/en/portal/dashboard
- API Reference: https://developer.x.com/en/docs/twitter-api
- Authentication: https://developer.x.com/en/docs/authentication/oauth-2-0
"""
import os
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
import time

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("ERROR: requests not installed. Install with: pip install requests")

from config import RAW_DIR, ZIP_CENTROIDS
from location_extractor import extract_all_locations

# Twitter accounts to monitor (NJ civic/news)
TWITTER_ACCOUNTS = [
    "ACLUnewjersey",        # ACLU NJ
    "ImmigrantJustNJ",      # NJ Alliance for Immigrant Justice
    "GovMurphy",            # NJ Governor
    "NewJerseyOAG",         # NJ Attorney General
    "TAPintoPlainfield",    # TAPinto Plainfield
    "njdotcom",             # NJ.com
    "plainfieldnj",         # City of Plainfield (if exists)
]

# Hashtags to monitor
TWITTER_HASHTAGS = [
    "#ImmigrationNJ",
    "#NJImmigrants",
    "#PlaintfieldNJ",
    "#NewJerseyICE",
    "#SanctuaryNJ",
]

# Keywords for filtering (must match at least one)
FILTER_KEYWORDS = [
    "ice", "immigration", "deportation", "enforcement",
    "sanctuary", "undocumented", "immigrant", "migrant",
    "plainfield", "union county", "new jersey",
]


def get_bearer_token():
    """Get Twitter Bearer Token from environment."""
    return os.getenv("X_BEARER_TOKEN") or os.getenv("TWITTER_BEARER_TOKEN")


def search_tweets(query: str, max_results: int = 10, days_back: int = 7) -> list:
    """
    Search recent tweets using Twitter API v2.
    
    Args:
        query: Search query (supports operators like OR, AND, #hashtag, from:user)
        max_results: Number of tweets to return (10-100)
        days_back: How many days back to search (max 7 for free tier)
    
    Returns:
        List of tweet dicts with text, author, created_at, etc.
    """
    if not REQUESTS_AVAILABLE:
        print("ERROR: requests library not installed")
        return []
    
    bearer_token = get_bearer_token()
    if not bearer_token:
        print("ERROR: X_BEARER_TOKEN not set. Get it from https://developer.x.com")
        return []
    
    # API endpoint
    url = "https://api.twitter.com/2/tweets/search/recent"
    
    # Calculate start_time (ISO 8601 format)
    start_time = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"
    
    # Parameters
    params = {
        "query": query,
        "max_results": min(max_results, 100),  # API limit
        "start_time": start_time,
        "tweet.fields": "created_at,author_id,public_metrics,entities,geo",
        "expansions": "author_id,geo.place_id,attachments.media_keys",
        "user.fields": "username,name,location",
        "place.fields": "full_name,geo",
        "media.fields": "url,preview_image_url,type",
    }
    
    # Headers
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent": "TheyAreHere/1.0 (Research Tool)",
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract tweets
        tweets = []
        if "data" in data:
            for tweet in data["data"]:
                # Find author info from includes
                author_info = {}
                if "includes" in data and "users" in data["includes"]:
                    for user in data["includes"]["users"]:
                        if user["id"] == tweet.get("author_id"):
                            author_info = user
                            break
                
                # Extract place info if available
                place_info = {}
                if "geo" in tweet and "place_id" in tweet["geo"]:
                    if "includes" in data and "places" in data["includes"]:
                        for place in data["includes"]["places"]:
                            if place["id"] == tweet["geo"]["place_id"]:
                                place_info = place
                                break

                # Extract media info if available
                media_urls = []
                media_count = 0
                if "includes" in data and "media" in data["includes"]:
                    # Map media_keys to media objects
                    media_map = {m.get("media_key", ""): m for m in data["includes"]["media"]}
                    # Entities may contain media keys in attachments
                    attachments = tweet.get("attachments", {})
                    keys = attachments.get("media_keys", []) if isinstance(attachments.get("media_keys", []), list) else []
                    for mk in keys:
                        m = media_map.get(mk)
                        if m:
                            url = m.get("url") or m.get("preview_image_url")
                            if url:
                                media_urls.append(url)
                    media_count = len(media_urls)
                
                # Compute location precision using text + place
                locs = extract_all_locations(tweet["text"])
                best_conf = locs[0].confidence if locs else 0.0
                # Slight boost if place is present
                if place_info.get("full_name"):
                    best_conf = max(best_conf, 0.6)

                tweets.append({
                    "id": tweet["id"],
                    "text": tweet["text"],
                    "created_at": tweet["created_at"],
                    "author_id": tweet.get("author_id"),
                    "author_username": author_info.get("username", ""),
                    "author_name": author_info.get("name", ""),
                    "author_location": author_info.get("location", ""),
                    "place": place_info.get("full_name", ""),
                    "retweet_count": tweet.get("public_metrics", {}).get("retweet_count", 0),
                    "like_count": tweet.get("public_metrics", {}).get("like_count", 0),
                    "reply_count": tweet.get("public_metrics", {}).get("reply_count", 0),
                    "url": f"https://twitter.com/{author_info.get('username', 'i')}/status/{tweet['id']}",
                    "media_urls": media_urls,
                    "media_count": media_count,
                    "location_precision": round(best_conf, 2),
                })
        
        print(f"✓ Found {len(tweets)} tweets for query: {query}")
        return tweets
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print("ERROR: Rate limit exceeded. Wait before retrying.")
        else:
            print(f"ERROR: HTTP {e.response.status_code}: {e.response.text}")
        return []
    except Exception as e:
        print(f"ERROR: Failed to search tweets: {e}")
        return []


def extract_zip_from_tweet(tweet: dict) -> str:
    """Attempt to extract ZIP code from tweet text or location."""
    # Check text for ZIP codes
    text = tweet.get("text", "")
    zip_match = re.search(r'\b(070[0-9]{2}|086[0-9]{2}|089[0-9]{2})\b', text)
    if zip_match:
        return zip_match.group(1)
    
    # Check author location
    location = tweet.get("author_location", "").lower()
    if "plainfield" in location:
        return "07060"  # Default Plainfield ZIP
    
    # Check place name
    place = tweet.get("place", "").lower()
    if "plainfield" in place:
        return "07060"
    elif "edison" in place:
        return "08817"
    elif "trenton" in place:
        return "08608"
    elif "hoboken" in place:
        return "07030"
    elif "new brunswick" in place:
        return "08901"
    
    # Default to unknown (will be filtered later)
    return "unknown"


def should_include_tweet(tweet: dict) -> bool:
    """Filter tweets based on keywords."""
    text = tweet.get("text", "").lower()
    
    # Check if any filter keyword is in text
    for keyword in FILTER_KEYWORDS:
        if keyword.lower() in text:
            return True
    
    return False


def normalize_tweets_to_csv(tweets: list) -> list:
    """
    Normalize tweets to HEAT CSV format (text, zip, date).
    
    Returns list of dicts ready for DataFrame.
    """
    records = []
    for tweet in tweets:
        # Filter
        if not should_include_tweet(tweet):
            continue
        
        # Extract ZIP
        zip_code = extract_zip_from_tweet(tweet)
        if zip_code == "unknown":
            # Skip tweets without clear location
            continue
        
        # Parse date
        created_at = datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00"))
        date_str = created_at.strftime("%Y-%m-%d")
        
        # Create record
        records.append({
            "text": tweet["text"],
            "zip": zip_code,
            "date": date_str,
            "source": f"twitter:{tweet.get('author_username', 'unknown')}",
            "category": "twitter",
            "tweet_id": tweet["id"],
            "tweet_url": tweet.get("url", ""),
            "author": tweet.get("author_name", ""),
            "engagement": tweet.get("like_count", 0) + tweet.get("retweet_count", 0),
            "location_precision": tweet.get("location_precision", 0.0),
            "media_count": tweet.get("media_count", 0),
        })
    
    return records


def scrape_twitter_feeds():
    """Main scraper: fetch tweets from monitored accounts and hashtags."""
    if not REQUESTS_AVAILABLE:
        print("ERROR: requests not installed")
        return
    
    if not get_bearer_token():
        print("ERROR: X_BEARER_TOKEN not set")
        print("\n" + "="*60)
        print("To set up Twitter/X API access:")
        print("1. Go to https://developer.x.com")
        print("2. Sign in with your Twitter account")
        print("3. Create a new Project and App")
        print("4. Generate a Bearer Token")
        print("5. Set environment variable:")
        print("   export X_BEARER_TOKEN='your_token_here'")
        print("="*60 + "\n")
        return
    
    all_tweets = []
    
    # Search by account
    for account in TWITTER_ACCOUNTS:
        query = f"from:{account} ({' OR '.join(FILTER_KEYWORDS)})"
        tweets = search_tweets(query, max_results=50, days_back=7)
        all_tweets.extend(tweets)
        time.sleep(2)  # Rate limit safety
    
    # Search by hashtag
    for hashtag in TWITTER_HASHTAGS:
        query = f"{hashtag} ({' OR '.join(FILTER_KEYWORDS)})"
        tweets = search_tweets(query, max_results=50, days_back=7)
        all_tweets.extend(tweets)
        time.sleep(2)
    
    # Deduplicate by tweet ID
    unique_tweets = {t["id"]: t for t in all_tweets}.values()
    
    print(f"\n✓ Collected {len(unique_tweets)} unique tweets")
    
    # Normalize to CSV format
    records = normalize_tweets_to_csv(list(unique_tweets))
    
    print(f"✓ Normalized {len(records)} tweets to records")
    
    # Save to CSV
    if records:
        import pandas as pd
        df = pd.DataFrame(records)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = RAW_DIR / f"twitter_{timestamp}.csv"
        df.to_csv(output_path, index=False)
        
        print(f"✓ Saved to {output_path}")
        
        # Print sample
        print("\nSample records:")
        for i, record in enumerate(records[:3]):
            print(f"\n[{i+1}] {record['text'][:100]}...")
            print(f"    ZIP: {record['zip']}, Date: {record['date']}, Author: {record['author']}")
    else:
        print("No records to save (all filtered out)")


if __name__ == "__main__":
    scrape_twitter_feeds()
