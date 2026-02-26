"""
Community Input Handler for HEAT Pipeline.

Structured intake for community-submitted civic signals. Validates,
sanitizes, and normalizes submissions before writing to the raw data
layer for downstream ingestion.

Output: data/raw/community_input.csv
"""

import re
import sys
import csv
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    BASE_DIR,
    RAW_DIR,
    ALL_ZIPS,
    ZIP_CENTROIDS,
    FORBIDDEN_ALERT_WORDS,
    SOURCE_RELIABILITY,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Community] %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "community_input.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OUTPUT_PATH: Path = RAW_DIR / "community_input.csv"
PIPELINE_COLUMNS = ["text", "source", "zip", "date"]

# Text constraints
MIN_TEXT_LENGTH = 10
MAX_TEXT_LENGTH = 2000

# Rate limiting (per session/IP placeholder)
MAX_SIGNALS_PER_HOUR = 10
_rate_tracker: dict[str, list[datetime]] = defaultdict(list)

# PII patterns to strip before storage
_PII_PATTERNS: list[tuple[str, str]] = [
    # Phone numbers (US formats)
    (r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE_REDACTED]"),
    # Email addresses
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL_REDACTED]"),
    # SSN
    (r"\b\d{3}[-]?\d{2}[-]?\d{4}\b", "[SSN_REDACTED]"),
    # Street addresses (basic — number + street name)
    (r"\b\d{1,5}\s+[A-Z][a-zA-Z]+\s+(St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Ln|Lane|Rd|Road|Ct|Court|Pl|Place|Way)\b",
     "[ADDRESS_REDACTED]"),
    # License plates (basic US)
    (r"\b[A-Z]{1,3}[-\s]?\d{3,4}[-\s]?[A-Z]{0,3}\b", "[PLATE_REDACTED]"),
    # Names preceded by common identifiers (Mr./Mrs./Dr. + Capitalized)
    (r"\b(?:Mr|Mrs|Ms|Dr|Officer|Agent)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b",
     "[NAME_REDACTED]"),
]

# Pre-compile PII regexes
_PII_COMPILED = [(re.compile(pat, re.IGNORECASE), repl) for pat, repl in _PII_PATTERNS]

# Pre-compile forbidden word pattern (whole-word, case-insensitive)
_FORBIDDEN_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in FORBIDDEN_ALERT_WORDS) + r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Enums & Dataclass
# ---------------------------------------------------------------------------

class SignalType(str, Enum):
    """Allowed community signal categories."""
    CONCERN = "concern"
    RESOURCE = "resource"
    EVENT = "event"
    TESTIMONY = "testimony"


# Map signal types → SOURCE_RELIABILITY weight keys
_SIGNAL_TYPE_RELIABILITY: dict[SignalType, str] = {
    SignalType.CONCERN: "single_report",        # 0.3 — unverified until corroborated
    SignalType.RESOURCE: "community_verified",   # 0.7 — resource info is verifiable
    SignalType.EVENT: "community_verified",      # 0.7 — event announcements
    SignalType.TESTIMONY: "anonymous",           # 0.1 — personal accounts, low weight
}


@dataclass
class CommunitySignal:
    """A single community-submitted civic signal."""

    text: str
    zip_code: str
    date: str = ""           # ISO-8601; defaults to now
    signal_type: str = "concern"  # concern | resource | event | testimony
    language: str = "en"
    anonymous: bool = True

    def __post_init__(self):
        # Normalize signal_type to enum value
        if isinstance(self.signal_type, SignalType):
            self.signal_type = self.signal_type.value
        self.signal_type = self.signal_type.lower()

        # Default date
        if not self.date:
            self.date = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when a community signal fails validation."""
    pass


def _strip_pii(text: str) -> str:
    """Remove personally identifiable information patterns from text."""
    for pattern, replacement in _PII_COMPILED:
        text = pattern.sub(replacement, text)
    return text


def _redact_forbidden_words(text: str) -> str:
    """Replace forbidden alert words with safe alternatives.

    Rather than silently dropping signals containing these words, we redact
    to preserve the signal's informational content while complying with the
    FORBIDDEN_ALERT_WORDS policy.
    """
    return _FORBIDDEN_RE.sub("[REDACTED]", text)


def validate_community_signal(signal: CommunitySignal) -> CommunitySignal:
    """Validate and sanitize a community signal.

    Parameters
    ----------
    signal : CommunitySignal
        Raw signal to validate.

    Returns
    -------
    CommunitySignal
        Sanitized signal ready for ingestion.

    Raises
    ------
    ValidationError
        If the signal fails hard validation rules.
    """
    errors: list[str] = []

    # --- Text validation ---
    text = signal.text.strip()
    if len(text) < MIN_TEXT_LENGTH:
        errors.append(
            f"Text too short ({len(text)} chars, minimum {MIN_TEXT_LENGTH})"
        )
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        logger.warning("Text truncated to %d characters", MAX_TEXT_LENGTH)

    # --- ZIP validation ---
    zip_code = str(signal.zip_code).strip().zfill(5)
    if not re.match(r"^\d{5}$", zip_code):
        errors.append(f"Invalid ZIP format: {signal.zip_code}")
    elif zip_code not in ALL_ZIPS and zip_code not in ZIP_CENTROIDS:
        errors.append(
            f"ZIP {zip_code} not in target coverage area. "
            f"Valid ZIPs: {', '.join(sorted(ALL_ZIPS))}"
        )

    # --- Signal type validation ---
    try:
        sig_type = SignalType(signal.signal_type.lower())
    except ValueError:
        errors.append(
            f"Invalid signal_type '{signal.signal_type}'. "
            f"Must be one of: {[t.value for t in SignalType]}"
        )
        sig_type = SignalType.CONCERN

    # --- Date validation ---
    try:
        dt = pd.to_datetime(signal.date, utc=True)
        # Future dates not allowed (small tolerance for clock skew)
        if dt > datetime.now(timezone.utc) + timedelta(minutes=5):
            errors.append("Signal date is in the future")
    except (ValueError, TypeError):
        errors.append(f"Invalid date format: {signal.date}")

    if errors:
        raise ValidationError("; ".join(errors))

    # --- Sanitization ---
    text = _strip_pii(text)
    text = _redact_forbidden_words(text)

    return CommunitySignal(
        text=text,
        zip_code=zip_code,
        date=signal.date,
        signal_type=sig_type.value,
        language=signal.language or "en",
        anonymous=signal.anonymous,
    )


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def _check_rate_limit(session_id: str = "default") -> bool:
    """Check if the session/IP has exceeded the submission rate limit.

    Returns True if the submission is allowed, False if rate-limited.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=1)

    # Prune old entries
    _rate_tracker[session_id] = [
        ts for ts in _rate_tracker[session_id] if ts > cutoff
    ]

    if len(_rate_tracker[session_id]) >= MAX_SIGNALS_PER_HOUR:
        return False

    _rate_tracker[session_id].append(now)
    return True


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest_community_signals(
    signals: list[CommunitySignal | dict],
    session_id: str = "default",
    output_path: Path | None = None,
) -> int:
    """Validate, normalize, and save community signals to CSV.

    Parameters
    ----------
    signals : list
        CommunitySignal instances or dicts with matching fields.
    session_id : str
        Session/IP identifier for rate limiting.
    output_path : Path, optional
        Override default output path.

    Returns
    -------
    int
        Number of signals successfully ingested.
    """
    out = output_path or OUTPUT_PATH
    accepted: list[dict] = []
    rejected = 0

    for raw in signals:
        # Rate limit check
        if not _check_rate_limit(session_id):
            logger.warning(
                "Rate limit reached for session '%s' (%d/hr). "
                "Remaining signals skipped.",
                session_id,
                MAX_SIGNALS_PER_HOUR,
            )
            break

        # Coerce dict → CommunitySignal
        if isinstance(raw, dict):
            try:
                raw = CommunitySignal(**raw)
            except TypeError as exc:
                logger.warning("Invalid signal dict: %s", exc)
                rejected += 1
                continue

        # Validate
        try:
            clean = validate_community_signal(raw)
        except ValidationError as exc:
            logger.warning("Rejected signal: %s", exc)
            rejected += 1
            continue

        # Determine source reliability weight
        sig_type_enum = SignalType(clean.signal_type)
        reliability_key = _SIGNAL_TYPE_RELIABILITY.get(
            sig_type_enum, "single_report"
        )
        reliability_weight = SOURCE_RELIABILITY.get(reliability_key, 0.3)

        # Normalize to pipeline format
        source_label = "community_anonymous" if clean.anonymous else "community_identified"

        accepted.append({
            "text": clean.text,
            "source": source_label,
            "zip": clean.zip_code,
            "date": pd.to_datetime(clean.date, utc=True).isoformat(),
            "signal_type": clean.signal_type,
            "language": clean.language,
            "reliability_weight": reliability_weight,
        })

    if not accepted:
        logger.info("No signals accepted (rejected=%d)", rejected)
        return 0

    df_new = pd.DataFrame(accepted)

    # Merge with existing file
    if out.exists():
        try:
            existing = pd.read_csv(out, encoding="utf-8")
            df_new = pd.concat([existing, df_new], ignore_index=True)
            df_new.drop_duplicates(
                subset=["text", "date", "zip"], keep="last", inplace=True
            )
        except Exception as exc:
            logger.warning("Could not merge existing CSV: %s", exc)

    out.parent.mkdir(parents=True, exist_ok=True)
    df_new.to_csv(out, index=False, encoding="utf-8")

    logger.info(
        "Ingested %d community signals (rejected=%d) → %s",
        len(accepted), rejected, out,
    )
    return len(accepted)


# ---------------------------------------------------------------------------
# Loading (for downstream pipeline)
# ---------------------------------------------------------------------------

def load_community_signals(
    path: Path | None = None,
) -> pd.DataFrame:
    """Load community signals in pipeline-compatible format.

    Returns a DataFrame with columns: text, source, zip, date
    (the standard pipeline schema), dropping community-specific extras.
    """
    src = path or OUTPUT_PATH
    if not src.exists():
        logger.info("No community input file found at %s", src)
        return pd.DataFrame(columns=PIPELINE_COLUMNS)

    df = pd.read_csv(src, encoding="utf-8")

    # Ensure pipeline columns exist
    for col in PIPELINE_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df[PIPELINE_COLUMNS].copy()


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_community_input() -> dict:
    """Pipeline entry point: load community signals into raw data layer.

    Checks for pending community submissions in the configured input
    path and ensures they are in pipeline-compatible CSV format.

    Returns
    -------
    dict
        Summary with record count.
    """
    df = load_community_signals()
    count = len(df)
    if count > 0:
        logger.info("Community input: loaded %d signals for pipeline", count)
    else:
        logger.info("Community input: no pending signals")
    return {"records": count}


# ---------------------------------------------------------------------------
# Standalone demo / test
# ---------------------------------------------------------------------------

def _self_test():
    """Quick validation test with sample signals."""
    import tempfile, os

    tmp_dir = Path(tempfile.mkdtemp())
    test_csv = tmp_dir / "test_community.csv"

    print("=" * 60)
    print("Community Input — Self-Test")
    print("=" * 60)

    # Valid signals
    test_signals = [
        CommunitySignal(
            text="Community forum on immigrant rights happening Saturday at the library",
            zip_code="07060",
            signal_type="event",
            language="en",
            anonymous=True,
        ),
        CommunitySignal(
            text="Free legal consultation available for DACA recipients next Tuesday",
            zip_code="07062",
            signal_type="resource",
            language="en",
            anonymous=False,
        ),
        CommunitySignal(
            text="There is growing concern about policy changes affecting local families",
            zip_code="07063",
            signal_type="concern",
            language="en",
            anonymous=True,
        ),
        # Dict-form input
        {
            "text": "Workshop on know your rights at the community center",
            "zip_code": "08817",
            "signal_type": "event",
        },
    ]

    count = ingest_community_signals(
        test_signals, session_id="test", output_path=test_csv
    )
    print(f"[OK] Ingested {count} signals")

    # Load back
    df = load_community_signals(path=test_csv)
    assert len(df) == count, f"Expected {count}, got {len(df)}"
    assert list(df.columns) == PIPELINE_COLUMNS
    print(f"[OK] Loaded {len(df)} signals in pipeline format")
    print(f"     Columns: {list(df.columns)}")

    # Test PII stripping
    pii_signal = CommunitySignal(
        text="Call John at 555-123-4567 or email john@example.com for help with resources",
        zip_code="07060",
        signal_type="resource",
    )
    clean = validate_community_signal(pii_signal)
    assert "555-123-4567" not in clean.text
    assert "john@example.com" not in clean.text
    assert "[PHONE_REDACTED]" in clean.text
    assert "[EMAIL_REDACTED]" in clean.text
    print("[OK] PII stripping works")

    # Test forbidden word redaction
    forbidden_signal = CommunitySignal(
        text="People report a sighting of activity near the center and possible raid",
        zip_code="07060",
        signal_type="concern",
    )
    clean = validate_community_signal(forbidden_signal)
    for word in ["sighting", "activity", "raid"]:
        assert word not in clean.text.lower(), f"Forbidden word '{word}' still present"
    print("[OK] Forbidden word redaction works")

    # Test invalid ZIP rejection
    bad_zip = CommunitySignal(
        text="This is a test signal with invalid ZIP code",
        zip_code="99999",
        signal_type="concern",
    )
    try:
        validate_community_signal(bad_zip)
        print("[FAIL] Should have rejected invalid ZIP")
    except ValidationError:
        print("[OK] Invalid ZIP correctly rejected")

    # Test too-short text rejection
    short_text = CommunitySignal(
        text="Hi",
        zip_code="07060",
        signal_type="concern",
    )
    try:
        validate_community_signal(short_text)
        print("[FAIL] Should have rejected short text")
    except ValidationError:
        print("[OK] Short text correctly rejected")

    # Test rate limiting
    _rate_tracker.clear()
    for i in range(MAX_SIGNALS_PER_HOUR + 5):
        allowed = _check_rate_limit("rate_test")
        if i < MAX_SIGNALS_PER_HOUR:
            assert allowed, f"Should be allowed at {i}"
        else:
            assert not allowed, f"Should be rate-limited at {i}"
    print(f"[OK] Rate limiting works ({MAX_SIGNALS_PER_HOUR}/hr)")

    # Cleanup
    try:
        os.remove(test_csv)
        os.rmdir(tmp_dir)
    except OSError:
        pass

    print("\n✓ All self-tests passed.")


if __name__ == "__main__":
    _self_test()
