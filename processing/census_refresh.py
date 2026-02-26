"""
Census ACS 5-Year Data Refresh
==============================
Pulls latest ACS 5-Year estimates from the Census Bureau API for
the 17 HEAT target ZCTAs, computes derived vulnerability indicators,
and writes build/data/census_acs.json.

Tables used:
  B01003  — Total Population
  B19013  — Median Household Income
  B16004  — Language Spoken at Home (for Linguistic Isolation proxy)
  B05002  — Place of Birth (foreign-born %)
  B25003  — Tenure (owner vs renter, for renter %)
  B08141  — Means of Transportation by Vehicles Available (no-vehicle %)
  B17001  — Poverty Status (poverty rate %)

Usage:
  python processing/census_refresh.py              # auto-detect latest vintage
  python processing/census_refresh.py --vintage 2022
  python processing/census_refresh.py --api-key YOUR_KEY  # optional, higher rate limit
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = BASE_DIR / "build" / "data" / "census_acs.json"

# ---------------------------------------------------------------------------
# Target ZCTAs (ZIP Code Tabulation Areas)
# ---------------------------------------------------------------------------
TARGET_ZCTAS = [
    "07060", "07062", "07063",                    # Plainfield
    "08817", "08820", "08837",                    # Edison
    "07030",                                       # Hoboken
    "08608", "08609", "08610", "08611",            # Trenton
    "08618", "08619",
    "08901", "08902", "08903", "08906",            # New Brunswick
]

# Friendly display names (fallback if API doesn't return them)
ZIP_NAMES = {
    "07060": "Plainfield (Central)",
    "07062": "North Plainfield",
    "07063": "South Plainfield",
    "08817": "Edison (Central)",
    "08820": "Edison (North)",
    "08837": "Edison (Raritan Center)",
    "07030": "Hoboken",
    "08608": "Trenton (Central)",
    "08609": "Trenton",
    "08610": "Trenton",
    "08611": "Trenton",
    "08618": "Trenton",
    "08619": "Trenton",
    "08901": "New Brunswick (Central)",
    "08902": "New Brunswick",
    "08903": "New Brunswick",
    "08906": "New Brunswick",
}

# ---------------------------------------------------------------------------
# ACS API Configuration
# ---------------------------------------------------------------------------
ACS_BASE = "https://api.census.gov/data/{vintage}/acs/acs5"

# Variables to fetch (ACS table codes)
#   B01003_001E  — Total Population
#   B19013_001E  — Median Household Income
#   B16004_001E  — Total (lang spoken) 5+; _067E = speak English "not well/not at all" etc.
#   B05002_001E  — Total (nativity); B05002_013E = foreign born
#   B25003_001E  — Total (tenure); B25003_003E = renter occupied
#   B08141_001E  — Total workers 16+; B08141_002E = no vehicle available
#   B17001_001E  — Total (poverty status); B17001_002E = below poverty

VARIABLES = {
    "B01003_001E": "total_population",
    "B19013_001E": "median_income",
    # Linguistic isolation: use C16002 (household limited English speaking status)
    # Sum of limited-English households across all language groups
    "C16002_001E": "ling_hh_total",
    "C16002_004E": "ling_hh_spanish_limited",
    "C16002_007E": "ling_hh_indoeuro_limited",
    "C16002_010E": "ling_hh_asian_limited",
    "C16002_013E": "ling_hh_other_limited",
    # Foreign-born
    "B05002_001E": "nativity_total",
    "B05002_013E": "foreign_born",
    # Tenure (renter)
    "B25003_001E": "tenure_total",
    "B25003_003E": "renter_occupied",
    # No vehicle
    "B08141_001E": "transport_total",
    "B08141_002E": "no_vehicle",
    # Poverty
    "B17001_001E": "poverty_total",
    "B17001_002E": "below_poverty",
}

# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("census_refresh")


def _safe_float(val, default: float = 0.0) -> float:
    """Convert Census API value to float, handling nulls and negatives."""
    if val is None or val == "" or val == "null":
        return default
    try:
        v = float(val)
        # Census uses negative values (e.g. -666666666) for missing/suppressed
        return default if v < 0 else v
    except (ValueError, TypeError):
        return default


def _safe_pct(numerator: float, denominator: float, decimals: int = 1) -> float:
    """Compute percentage safely."""
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, decimals)


def detect_latest_vintage() -> int:
    """Try vintages from current year down to 2019 to find the latest available."""
    current_year = datetime.now().year
    # ACS 5-year data lags ~2 years (e.g., 2023 data releases late 2024)
    for vintage in range(current_year - 1, 2018, -1):
        url = f"https://api.census.gov/data/{vintage}/acs/acs5.json"
        try:
            req = Request(url, headers={"User-Agent": "HEAT-CensusRefresh/1.0"})
            resp = urlopen(req, timeout=10)
            if resp.status == 200:
                logger.info("Latest available ACS 5-Year vintage: %d", vintage)
                return vintage
        except (HTTPError, URLError, OSError):
            continue
    logger.warning("Could not detect latest vintage, defaulting to 2022")
    return 2022


def fetch_acs_data(
    vintage: int,
    zctas: list[str],
    api_key: Optional[str] = None,
) -> dict:
    """
    Fetch ACS 5-Year data from Census API for the given ZCTAs.

    Returns dict: {zcta_code: {variable_name: value, ...}, ...}
    """
    var_list = ",".join(VARIABLES.keys())
    zcta_filter = ",".join(zctas)
    url = f"{ACS_BASE.format(vintage=vintage)}?get=NAME,{var_list}&for=zip%20code%20tabulation%20area:{zcta_filter}"
    if api_key:
        url += f"&key={api_key}"

    logger.info("Fetching ACS %d data for %d ZCTAs ...", vintage, len(zctas))
    logger.info("  URL: %s", url[:120] + "...")

    req = Request(url, headers={"User-Agent": "HEAT-CensusRefresh/1.0"})

    try:
        resp = urlopen(req, timeout=30)
        raw = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        logger.error("Census API HTTP error %d: %s", e.code, e.reason)
        if e.code == 404:
            logger.error("Vintage %d may not be available for ACS 5-Year.", vintage)
        raise
    except URLError as e:
        logger.error("Network error reaching Census API: %s", e.reason)
        raise

    if not raw or len(raw) < 2:
        logger.error("Empty response from Census API")
        return {}

    # First row is header, remaining rows are data
    headers = raw[0]
    results = {}

    # Build column index → variable name mapping
    col_map = {}
    for i, h in enumerate(headers):
        if h in VARIABLES:
            col_map[i] = VARIABLES[h]
        elif h == "NAME":
            col_map[i] = "_name"
        elif h == "zip code tabulation area":
            col_map[i] = "_zcta"

    for row in raw[1:]:
        record = {}
        zcta = None
        for i, val in enumerate(row):
            if i in col_map:
                key = col_map[i]
                if key == "_zcta":
                    zcta = str(val).zfill(5)
                elif key == "_name":
                    record["api_name"] = val
                else:
                    record[key] = _safe_float(val)

        if zcta:
            results[zcta] = record
            logger.info("  %s: pop=%s income=$%s",
                        zcta,
                        int(record.get("total_population", 0)),
                        int(record.get("median_income", 0)))

    return results


def compute_derived_fields(raw_data: dict) -> dict:
    """
    Compute the derived percentage fields that vulnerability_overlay.py needs.

    Returns dict in the same format as the existing census_acs.json.
    """
    zips_out = {}
    for zcta, data in sorted(raw_data.items()):
        # Sum limited-English households across all language groups
        limited_english_hh = sum([
            data.get("ling_hh_spanish_limited", 0),
            data.get("ling_hh_indoeuro_limited", 0),
            data.get("ling_hh_asian_limited", 0),
            data.get("ling_hh_other_limited", 0),
        ])
        zips_out[zcta] = {
            "name": ZIP_NAMES.get(zcta, data.get("api_name", zcta)),
            "median_income": int(data.get("median_income", 0)),
            "linguistic_isolation_pct": _safe_pct(
                limited_english_hh,
                data.get("ling_hh_total", 0),
            ),
            "foreign_born_pct": _safe_pct(
                data.get("foreign_born", 0),
                data.get("nativity_total", 0),
            ),
            "renter_pct": _safe_pct(
                data.get("renter_occupied", 0),
                data.get("tenure_total", 0),
            ),
            "no_vehicle_pct": _safe_pct(
                data.get("no_vehicle", 0),
                data.get("transport_total", 0),
            ),
            "total_population": int(data.get("total_population", 0)),
            "poverty_rate_pct": _safe_pct(
                data.get("below_poverty", 0),
                data.get("poverty_total", 0),
            ),
        }
    return zips_out


def write_census_json(
    zips_data: dict,
    vintage: int,
    output_path: Path = OUTPUT_PATH,
) -> None:
    """Write the census_acs.json file."""
    output = {
        "metadata": {
            "source": "U.S. Census Bureau American Community Survey (ACS) 5-Year Estimates",
            "vintage": str(vintage),
            "table_ids": ["B01003", "B19013", "C16002", "B05002", "B25003", "B08141", "B17001"],
            "description": "ACS data for HEAT vulnerability overlay — refreshed via Census API",
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "refresh_method": "census_refresh.py",
        },
        "zips": zips_data,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    logger.info("Wrote %d ZIPs to %s", len(zips_data), output_path)


def main():
    parser = argparse.ArgumentParser(description="Refresh Census ACS data for HEAT")
    parser.add_argument("--vintage", type=int, default=0,
                        help="ACS vintage year (default: auto-detect latest)")
    parser.add_argument("--api-key", type=str, default=None,
                        help="Census API key (optional, for higher rate limits)")
    parser.add_argument("--output", type=str, default=str(OUTPUT_PATH),
                        help="Output JSON path")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print data without writing file")
    args = parser.parse_args()

    vintage = args.vintage or detect_latest_vintage()
    output_path = Path(args.output)

    try:
        raw_data = fetch_acs_data(vintage, TARGET_ZCTAS, api_key=args.api_key)
    except (HTTPError, URLError) as e:
        logger.error("Failed to fetch Census data: %s", e)
        sys.exit(1)

    if not raw_data:
        logger.error("No data returned from Census API")
        sys.exit(1)

    # Report missing ZCTAs
    missing = set(TARGET_ZCTAS) - set(raw_data.keys())
    if missing:
        logger.warning("Missing ZCTAs (not in ACS data): %s", ", ".join(sorted(missing)))
        # Try to fill from existing census_acs.json (carry forward old data)
        if output_path.exists():
            try:
                with open(output_path, encoding="utf-8") as f:
                    old = json.load(f)
                old_zips = old.get("zips", {})
                for z in missing:
                    if z in old_zips:
                        logger.info("  Carrying forward %s from previous vintage", z)
                        raw_data[z] = {
                            "_carried_forward": True,
                            "total_population": old_zips[z].get("total_population", 0),
                            "median_income": old_zips[z].get("median_income", 0),
                            "ling_hh_total": 100,  # placeholder for pct calc
                            "ling_hh_spanish_limited": old_zips[z].get("linguistic_isolation_pct", 0),
                            "ling_hh_indoeuro_limited": 0,
                            "ling_hh_asian_limited": 0,
                            "ling_hh_other_limited": 0,
                            "nativity_total": 100,
                            "foreign_born": old_zips[z].get("foreign_born_pct", 0),
                            "tenure_total": 100,
                            "renter_occupied": old_zips[z].get("renter_pct", 0),
                            "transport_total": 100,
                            "no_vehicle": old_zips[z].get("no_vehicle_pct", 0),
                            "poverty_total": 100,
                            "below_poverty": old_zips[z].get("poverty_rate_pct", 0),
                        }
            except (json.JSONDecodeError, KeyError):
                logger.warning("  Could not read existing census_acs.json for fallback")

    zips_data = compute_derived_fields(raw_data)

    if args.dry_run:
        print(json.dumps({"vintage": vintage, "zips": zips_data}, indent=2))
        return

    # Back up existing file
    if output_path.exists():
        backup = output_path.with_suffix(f".{vintage}_backup.json")
        import shutil
        shutil.copy2(output_path, backup)
        logger.info("Backed up existing file to %s", backup.name)

    write_census_json(zips_data, vintage, output_path)

    # Summary
    print(f"\n{'='*50}")
    print(f"Census ACS {vintage} refresh complete")
    print(f"  ZIPs: {len(zips_data)} / {len(TARGET_ZCTAS)} target")
    print(f"  Output: {output_path}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
