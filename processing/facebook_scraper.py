"""
Facebook Group Crowdsource Integration for HEAT
Scrapes public Facebook posts from community groups for civic signal aggregation.

NOTE: This uses the Facebook Graph API or public page scraping.
For private groups, you must be an admin and use proper API access.
"""
import re
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import hashlib

# Try importing facebook-sdk or fallback to requests
try:
    import facebook
    HAS_FB_SDK = True
except ImportError:
    HAS_FB_SDK = False

import requests
from bs4 import BeautifulSoup

from config import (
    BASE_DIR, RAW_DIR, PROCESSED_DIR,
    TARGET_ZIPS, FORBIDDEN_ALERT_WORDS
)


class FacebookCrowdsource:
    """
    Collect community signals from Facebook groups.
    Supports: Public pages, Groups (with admin access token), Manual CSV import.
    """
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token
        self.output_dir = RAW_DIR
        self.collected_posts = []
        
        # Keywords to identify relevant posts
        self.relevance_keywords = [
            # General civic terms
            "community", "neighborhood", "plainfield", "NJ", "new jersey",
            # Immigration-related (public terms only, no forbidden words)
            "immigration", "immigrant", "DACA", "TPS", "visa", "citizenship",
            "deportation", "asylum", "refugee", "undocumented",
            # Community safety
            "safety", "alert", "warning", "report", "happening",
            "downtown", "north plainfield", "south plainfield",
            # Spanish equivalents
            "comunidad", "vecindario", "inmigración", "inmigrante",
            "seguridad", "alerta", "aviso",
            # Portuguese equivalents
            "comunidade", "bairro", "imigração", "imigrante",
            "segurança", "alerta", "aviso"
        ]
        
        # ZIP code detection patterns
        self.zip_patterns = [
            r'\b(07060|07062|07063)\b',
            r'plainfield\s*,?\s*nj',
            r'north\s+plainfield',
            r'south\s+plainfield',
        ]
    
    def scrape_public_page(self, page_url: str) -> List[Dict]:
        """
        Scrape public Facebook page posts (no API required).
        Uses BeautifulSoup for basic extraction.
        Note: This is rate-limited and may break if Facebook changes HTML.
        """
        print(f"Scraping public page: {page_url}")
        posts = []
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(page_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                print(f"Failed to fetch page: {response.status_code}")
                return posts
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract text from post-like elements
            # Note: Facebook's HTML structure changes frequently
            for element in soup.find_all(['p', 'span', 'div'], limit=100):
                text = element.get_text(strip=True)
                if len(text) > 50 and self._is_relevant(text):
                    post_id = hashlib.md5(text[:100].encode()).hexdigest()[:12]
                    posts.append({
                        "id": f"fb_{post_id}",
                        "text": self._sanitize_text(text[:500]),
                        "source": "facebook_public",
                        "date": datetime.now().isoformat(),
                        "zip": self._extract_zip(text),
                        "url": page_url
                    })
            
        except Exception as e:
            print(f"Error scraping page: {e}")
        
        # Convert to DataFrame and save
        if posts:
            df = pd.DataFrame(posts)
            output_path = self.output_dir / f"facebook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(output_path, index=False)
            print(f"Saved {len(posts)} posts to: {output_path}")
            return df
        
        print("No posts found (page may require login or no relevant content)")
        return pd.DataFrame()
    
    def fetch_from_graph_api(self, page_id: str, limit: int = 50) -> List[Dict]:
        """
        Fetch posts using Facebook Graph API (requires access token).
        """
        if not self.access_token:
            print("No access token provided. Use scrape_public_page() instead.")
            return []
        
        if not HAS_FB_SDK:
            print("facebook-sdk not installed. Run: pip install facebook-sdk")
            return []
        
        print(f"Fetching from Graph API: {page_id}")
        posts = []
        
        try:
            graph = facebook.GraphAPI(access_token=self.access_token, version="3.1")
            
            # Get page posts
            page_posts = graph.get_connections(
                id=page_id,
                connection_name='posts',
                fields='message,created_time,id,permalink_url',
                limit=limit
            )
            
            for post in page_posts.get('data', []):
                text = post.get('message', '')
                if text and self._is_relevant(text):
                    posts.append({
                        "id": f"fb_{post['id']}",
                        "text": self._sanitize_text(text[:500]),
                        "source": "facebook_api",
                        "date": post.get('created_time', datetime.now().isoformat()),
                        "zip": self._extract_zip(text),
                        "url": post.get('permalink_url', '')
                    })
                    
        except Exception as e:
            print(f"Graph API error: {e}")
        
        # Convert to DataFrame and save
        if posts:
            df = pd.DataFrame(posts)
            output_path = self.output_dir / f"facebook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(output_path, index=False)
            print(f"Saved {len(posts)} posts to: {output_path}")
            return df
        
        return pd.DataFrame()
    
    def import_from_csv(self, csv_path: str) -> List[Dict]:
        """
        Import Facebook posts from manually exported CSV.
        Expected columns: text, date, zip (optional)
        
        How to export from Facebook:
        1. Go to your Facebook group
        2. Use browser extension like "Social Book Post Manager"
        3. Export to CSV
        4. Save as facebook_export.csv
        """
        print(f"Importing from CSV: {csv_path}")
        posts = []
        
        try:
            df = pd.read_csv(csv_path)
            
            # Normalize column names
            df.columns = df.columns.str.lower().str.strip()
            
            # Find text column
            text_col = None
            for col in ['text', 'message', 'content', 'post', 'body']:
                if col in df.columns:
                    text_col = col
                    break
            
            if not text_col:
                print("No text column found in CSV")
                return posts
            
            # Find date column
            date_col = None
            for col in ['date', 'created_time', 'timestamp', 'posted_at']:
                if col in df.columns:
                    date_col = col
                    break
            
            for idx, row in df.iterrows():
                text = str(row[text_col])
                if len(text) > 20 and self._is_relevant(text):
                    post_id = hashlib.md5(text[:100].encode()).hexdigest()[:12]
                    
                    # Parse date
                    date_str = row.get(date_col, '') if date_col else ''
                    try:
                        date = pd.to_datetime(date_str).isoformat()
                    except:
                        date = datetime.now().isoformat()
                    
                    posts.append({
                        "id": f"fb_csv_{post_id}",
                        "text": self._sanitize_text(text[:500]),
                        "source": "facebook_csv",
                        "date": date,
                        "zip": row.get('zip', self._extract_zip(text)),
                        "url": row.get('url', '')
                    })
                    
        except Exception as e:
            print(f"CSV import error: {e}")
        
        # Convert to DataFrame and save processed version
        if posts:
            df = pd.DataFrame(posts)
            output_path = self.output_dir / f"facebook_processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(output_path, index=False)
            print(f"Processed {len(posts)} posts and saved to: {output_path}")
            return df
        
        print("No relevant posts found in CSV")
        return pd.DataFrame()
    
    def _is_relevant(self, text: str) -> bool:
        """Check if text contains relevant keywords"""
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.relevance_keywords)
    
    def _extract_zip(self, text: str) -> str:
        """Extract ZIP code from text or default to main ZIP"""
        # Direct ZIP match
        for pattern in self.zip_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.group(0).startswith('0'):
                    return match.group(0)
                # Location name match
                if 'north' in match.group(0).lower():
                    return "07062"
                elif 'south' in match.group(0).lower():
                    return "07063"
                return "07060"
        
        return "07060"  # Default to central Plainfield
    
    def _sanitize_text(self, text: str) -> str:
        """Remove forbidden words and PII"""
        result = text
        
        # Remove forbidden words
        for word in FORBIDDEN_ALERT_WORDS:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            result = pattern.sub("[topic]", result)
        
        # Remove potential PII patterns
        result = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[phone]', result)  # Phone
        result = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[email]', result)  # Email
        result = re.sub(r'@\w+', '', result)  # @mentions
        
        return result.strip()
    
    def collect_all(self, sources: List[Dict]) -> pd.DataFrame:
        """
        Collect from multiple sources.
        
        sources format:
        [
            {"type": "public_page", "url": "https://facebook.com/PlainfieldNJ"},
            {"type": "graph_api", "page_id": "123456789"},
            {"type": "csv", "path": "data/raw/facebook_export.csv"}
        ]
        """
        all_posts = []
        
        for source in sources:
            source_type = source.get("type", "")
            
            if source_type == "public_page":
                posts = self.scrape_public_page(source["url"])
            elif source_type == "graph_api":
                posts = self.fetch_from_graph_api(source["page_id"])
            elif source_type == "csv":
                posts = self.import_from_csv(source["path"])
            else:
                print(f"Unknown source type: {source_type}")
                continue
            
            print(f"  → Collected {len(posts)} posts from {source_type}")
            all_posts.extend(posts)
        
        # Deduplicate by ID
        seen_ids = set()
        unique_posts = []
        for post in all_posts:
            if post["id"] not in seen_ids:
                seen_ids.add(post["id"])
                unique_posts.append(post)
        
        print(f"Total unique posts: {len(unique_posts)}")
        
        # Convert to DataFrame
        if unique_posts:
            df = pd.DataFrame(unique_posts)
            
            # Save to raw data
            output_path = self.output_dir / f"facebook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(output_path, index=False)
            print(f"Saved to: {output_path}")
            
            return df
        
        return pd.DataFrame()


def run_facebook_scraper():
    """Run Facebook scraper with configured sources or CLI args"""
    import argparse
    
    parser = argparse.ArgumentParser(description="HEAT Facebook Crowdsource Scraper")
    parser.add_argument("--url", help="Public Facebook page/group URL to scrape")
    parser.add_argument("--csv", help="Path to CSV file with exported posts")
    parser.add_argument("--group-id", help="Facebook group ID for Graph API")
    parser.add_argument("--token", help="Facebook API access token")
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("HEAT Facebook Crowdsource Scraper")
    print("=" * 50)
    
    scraper = FacebookCrowdsource(access_token=args.token if args.token else None)
    sources = []
    
    # Handle CLI arguments
    if args.url:
        print(f"\n📄 Scraping public page/group: {args.url}")
        df = scraper.scrape_public_page(args.url)
        if not df.empty:
            print(f"✓ Collected {len(df)} posts from {args.url}")
        else:
            print("⚠ No posts found (page may require login)")
        return
    
    if args.csv:
        print(f"\n📁 Importing from CSV: {args.csv}")
        df = scraper.import_from_csv(args.csv)
        if not df.empty:
            print(f"✓ Imported {len(df)} posts from CSV")
        return
    
    if args.group_id and args.token:
        print(f"\n🔐 Fetching from Graph API: Group {args.group_id}")
        df = scraper.fetch_from_graph_api(args.group_id)
        if not df.empty:
            print(f"✓ Collected {len(df)} posts from group")
        return
    
    # Default: Check for existing CSV exports
    csv_files = list(RAW_DIR.glob("facebook*.csv"))
    
    if csv_files:
        print(f"\nFound {len(csv_files)} existing CSV export(s)")
        for csv_file in csv_files:
            df = scraper.import_from_csv(str(csv_file))
            if not df.empty:
                print(f"✓ Processed {len(df)} posts from {csv_file.name}")
        return
    
    print("\nNo sources provided. Usage:")
    print("  python facebook_scraper.py --url <facebook_url>")
    print("  python facebook_scraper.py --csv <path_to_csv>")
    print("  python facebook_scraper.py --group-id <id> --token <token>")


if __name__ == "__main__":
    run_facebook_scraper()
