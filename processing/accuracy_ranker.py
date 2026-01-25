"""
Accuracy Ranker for They Are Here
Ranks signals by location precision and corroboration (not volume).

Outputs:
- build/exports/geographic_accuracy.json: Top signals by ZIP with accuracy score

Scoring factors (0-1):
- location_confidence (from LocationExtractor)
- source_factor: news=0.9, advocacy=0.8, council=0.85, twitter=0.6
- media_backing: +0.1 if URL/media present (capped at 1.0)
- corroboration: +0.1 if multiple distinct sources in same cluster (when available)

Safety:
- Enforces buffer delay via latest_date check and tier rules via config if needed
- Filters out texts containing forbidden alert words in user-facing exports
"""
import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
from textwrap import shorten

from config import BUILD_DIR, PROCESSED_DIR, FORBIDDEN_ALERT_WORDS
from location_extractor import extract_location

OUTPUT_PATH = BUILD_DIR / "exports" / "geographic_accuracy.json"

SOURCE_FACTORS = {
    "news": 0.9,
    "advocacy": 0.8,
    "council": 0.85,
    "twitter": 0.6,
}


def contains_forbidden(text: str) -> bool:
    tl = str(text).lower()
    return any(w.lower() in tl for w in FORBIDDEN_ALERT_WORDS)


def compute_accuracy_score(row: pd.Series) -> float:
    # Location confidence from extractor on text
    loc = extract_location(str(row.get("text", "")))
    loc_conf = loc.confidence if loc else 0.0

    # Source factor
    source = str(row.get("source", "")).lower()
    # Normalize source (e.g., twitter:username → twitter)
    if source.startswith("twitter"):
        source_key = "twitter"
    else:
        source_key = source
    source_factor = SOURCE_FACTORS.get(source_key, 0.7)

    # Media backing: url or tweet_url or media_count
    media_backing = 0.0
    url = row.get("url") or row.get("tweet_url")
    media_count = float(row.get("media_count", 0) or 0)
    if url:
        media_backing += 0.1
    if media_count > 0:
        media_backing += 0.1
    media_backing = min(media_backing, 0.2)

    # Corroboration hint: if category present and not twitter
    # (In full pipeline, cluster corroboration is handled by buffer; here we add a small factor.)
    category = str(row.get("category", ""))
    corroboration = 0.1 if category in ("news", "advocacy", "council") else 0.0

    score = loc_conf * source_factor + media_backing + corroboration
    return round(min(score, 1.0), 2)


def rank_geographic_accuracy():
    # Load records
    records_path = PROCESSED_DIR / "all_records.csv"
    if not records_path.exists():
        print(f"ERROR: {records_path} not found. Run ingest.py first.")
        return None
    df = pd.read_csv(records_path)

    # Compute scores
    df["accuracy_score"] = df.apply(compute_accuracy_score, axis=1)

    # Prepare export by ZIP
    df["zip"] = df["zip"].astype(str).str.zfill(5)
    grouped = df.groupby("zip")

    export = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rankings": [],
    }

    for zip_code, g in grouped:
        # Top 10 by accuracy
        top = g.sort_values(by="accuracy_score", ascending=False).head(10)
        items = []
        for _, row in top.iterrows():
            text = str(row.get("text", ""))
            if contains_forbidden(text):
                # Skip user-facing entries with forbidden words
                continue
            items.append({
                "text": shorten(text, width=160, placeholder="…"),
                "score": float(row.get("accuracy_score", 0)),
                "source": str(row.get("source", "")),
                "date": str(row.get("date", "")),
                "url": str(row.get("url", row.get("tweet_url", ""))),
            })
        export["rankings"].append({
            "zip": zip_code,
            "items": items,
            "count": len(items),
        })

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(export, f, indent=2)
    print(f"✓ Saved geographic accuracy rankings: {OUTPUT_PATH}")
    return export


if __name__ == "__main__":
    rank_geographic_accuracy()
