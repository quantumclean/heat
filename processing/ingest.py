"""
Normalize raw data sources into unified format.
Runs locally. Never touches production.
"""
import pandas as pd
from pathlib import Path
from datetime import datetime

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"


def normalize_record(text: str, source: str, zip_code: str, date: str) -> dict:
    """Standardize a single record."""
    return {
        "text": str(text).strip(),
        "source": source,
        "zip": str(zip_code).strip(),
        "date": pd.to_datetime(date).isoformat(),
        "ingested_at": datetime.utcnow().isoformat(),
    }


def ingest_csv(path: Path, source_name: str) -> list[dict]:
    """
    Expects CSV with columns: text, zip, date
    """
    df = pd.read_csv(path)
    records = []
    
    for _, row in df.iterrows():
        try:
            records.append(normalize_record(
                text=row["text"],
                source=source_name,
                zip_code=row.get("zip", "07060"),  # Default to Plainfield
                date=row["date"],
            ))
        except Exception as e:
            print(f"Skipping row: {e}")
    
    return records


def run_ingestion():
    """Ingest all raw sources into single processed file."""
    all_records = []
    
    # Original sample CSVs
    sources = {
        "news": RAW_DIR / "news.csv",
        "advocacy": RAW_DIR / "advocacy.csv",
        "council": RAW_DIR / "council.csv",
    }
    
    for source_name, path in sources.items():
        if path.exists():
            print(f"Ingesting {source_name}...")
            records = ingest_csv(path, source_name)
            all_records.extend(records)
            print(f"  → {len(records)} records")
        else:
            print(f"Skipping {source_name} (file not found: {path})")
    
    # Scraped RSS files
    scraped_files = list(RAW_DIR.glob("scraped_*.csv"))
    if scraped_files:
        print(f"\nIngesting {len(scraped_files)} scraped file(s)...")
        for scraped_path in scraped_files:
            print(f"  Processing {scraped_path.name}...")
            try:
                df = pd.read_csv(scraped_path)
                for _, row in df.iterrows():
                    try:
                        # Scraped files have more fields
                        record = normalize_record(
                            text=row.get("text", row.get("title", "")),
                            source=row.get("source", "scraped"),
                            zip_code=row.get("zip", "07060"),
                            date=row.get("date", datetime.now().isoformat()),
                        )
                        # Preserve additional fields from scraper
                        if "id" in row:
                            record["id"] = row["id"]
                        if "category" in row:
                            record["category"] = row["category"]
                        if "url" in row:
                            record["url"] = row["url"]
                        all_records.append(record)
                    except Exception as e:
                        print(f"    Skipping row: {e}")
                print(f"    → {len(df)} records")
            except Exception as e:
                print(f"    Error reading {scraped_path.name}: {e}")
    
    # Twitter files
    twitter_files = list(RAW_DIR.glob("twitter_*.csv"))
    if twitter_files:
        print(f"\nIngesting {len(twitter_files)} twitter file(s)...")
        for tw_path in twitter_files:
            print(f"  Processing {tw_path.name}...")
            try:
                df = pd.read_csv(tw_path)
                for _, row in df.iterrows():
                    try:
                        record = normalize_record(
                            text=row.get("text", ""),
                            source=row.get("source", "twitter"),
                            zip_code=row.get("zip", "07060"),
                            date=row.get("date", datetime.now().isoformat()),
                        )
                        # Preserve additional twitter fields
                        for extra in [
                            "id","category","url","tweet_id","tweet_url","author",
                            "engagement","location_precision","media_count"
                        ]:
                            if extra in row:
                                record[extra] = row[extra]
                        all_records.append(record)
                    except Exception as e:
                        print(f"    Skipping row: {e}")
                print(f"    → {len(df)} records")
            except Exception as e:
                print(f"    Error reading {tw_path.name}: {e}")

    # Historical data files
    historical_files = list(RAW_DIR.glob("historical_*.csv"))
    if historical_files:
        print(f"\nIngesting {len(historical_files)} historical file(s)...")
        for hist_path in historical_files:
            print(f"  Processing {hist_path.name}...")
            try:
                df = pd.read_csv(hist_path)
                for _, row in df.iterrows():
                    try:
                        record = normalize_record(
                            text=row.get("text", row.get("title", "")),
                            source=row.get("source", "historical"),
                            zip_code=row.get("zip", "07060"),
                            date=row.get("date", datetime.now().isoformat()),
                        )
                        if "id" in row:
                            record["id"] = row["id"]
                        if "category" in row:
                            record["category"] = row["category"]
                        if "url" in row:
                            record["url"] = row["url"]
                        all_records.append(record)
                    except Exception as e:
                        print(f"    Skipping row: {e}")
                print(f"    → {len(df)} records")
            except Exception as e:
                print(f"    Error reading {hist_path.name}: {e}")

    # NJ AG press releases
    nj_ag_files = list(RAW_DIR.glob("nj_ag_*.csv"))
    if nj_ag_files:
        print(f"\nIngesting {len(nj_ag_files)} NJ AG file(s)...")
        for ag_path in nj_ag_files:
            print(f"  Processing {ag_path.name}...")
            try:
                df = pd.read_csv(ag_path)
                for _, row in df.iterrows():
                    try:
                        record = normalize_record(
                            text=row.get("text", row.get("title", "")),
                            source=row.get("source", "NJ Attorney General"),
                            zip_code=row.get("zip", "07060"),
                            date=row.get("date", datetime.now().isoformat()),
                        )
                        for extra in ["id", "category", "url", "title"]:
                            if extra in row:
                                record[extra] = row[extra]
                        all_records.append(record)
                    except Exception as e:
                        print(f"    Skipping row: {e}")
                print(f"    → {len(df)} records")
            except Exception as e:
                print(f"    Error reading {ag_path.name}: {e}")

    # Reddit posts
    reddit_files = list(RAW_DIR.glob("reddit_*.csv"))
    if reddit_files:
        print(f"\nIngesting {len(reddit_files)} Reddit file(s)...")
        for reddit_path in reddit_files:
            print(f"  Processing {reddit_path.name}...")
            try:
                df = pd.read_csv(reddit_path)
                for _, row in df.iterrows():
                    try:
                        record = normalize_record(
                            text=row.get("text", row.get("title", "")),
                            source=row.get("source", "Reddit"),
                            zip_code=row.get("zip", "07060"),
                            date=row.get("date", datetime.now().isoformat()),
                        )
                        for extra in ["id", "category", "url", "title"]:
                            if extra in row:
                                record[extra] = row[extra]
                        all_records.append(record)
                    except Exception as e:
                        print(f"    Skipping row: {e}")
                print(f"    → {len(df)} records")
            except Exception as e:
                print(f"    Error reading {reddit_path.name}: {e}")

    # Council minutes
    council_files = list(RAW_DIR.glob("council_minutes_*.csv"))
    if council_files:
        print(f"\nIngesting {len(council_files)} council minutes file(s)...")
        for council_path in council_files:
            print(f"  Processing {council_path.name}...")
            try:
                df = pd.read_csv(council_path)
                for _, row in df.iterrows():
                    try:
                        record = normalize_record(
                            text=row.get("text", row.get("title", "")),
                            source=row.get("source", "City Council"),
                            zip_code=row.get("zip", "07060"),
                            date=row.get("date", datetime.now().isoformat()),
                        )
                        for extra in ["id", "category", "url", "title"]:
                            if extra in row:
                                record[extra] = row[extra]
                        all_records.append(record)
                    except Exception as e:
                        print(f"    Skipping row: {e}")
                print(f"    → {len(df)} records")
            except Exception as e:
                print(f"    Error reading {council_path.name}: {e}")
    
    # Deduplicate by text hash
    seen_texts = set()
    unique_records = []
    for record in all_records:
        text_hash = hash(record["text"][:100])  # First 100 chars
        if text_hash not in seen_texts:
            seen_texts.add(text_hash)
            unique_records.append(record)
    
    print(f"\nDeduplicated: {len(all_records)} -> {len(unique_records)} records")
    
    # Save
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(unique_records)
    df.to_csv(PROCESSED_DIR / "all_records.csv", index=False)
    print(f"Total: {len(df)} records saved to {PROCESSED_DIR / 'all_records.csv'}")
    
    return df


if __name__ == "__main__":
    run_ingestion()
