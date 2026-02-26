"""
HEAT Presidio PII Guard
========================
Embeds privacy at ingestion, not display. All text is PII-scrubbed
before storage using Microsoft Presidio + custom immigration-specific
recognizers. NEVER stores original PII — only the scrubbed version
and an audit hash.

Usage from ingest.py:
    from presidio_guard import init_presidio, scrub_pii, batch_scrub
    init_presidio()
    clean_text, entities = scrub_pii(raw_text)
"""

import re
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
LOGS_DIR = Path(__file__).parent.parent / "data" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PII_AUDIT_LOG = LOGS_DIR / "pii_audit.json"

logger = logging.getLogger("heat.presidio_guard")

# ---------------------------------------------------------------------------
# Module-level state (initialized via init_presidio)
# ---------------------------------------------------------------------------
_analyzer = None
_anonymizer = None
_initialized = False
_scrub_stats: dict[str, int] = {}

# ---------------------------------------------------------------------------
# Fallback regex patterns (from export_static.py) — used as secondary sweep
# ---------------------------------------------------------------------------
FALLBACK_PATTERNS: dict[str, tuple[str, str]] = {
    "SSN": (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),
    "PHONE_NUMBER": (r"\b\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b", "[PHONE]"),
    "EMAIL_ADDRESS": (
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "[EMAIL]",
    ),
    "ADDRESS": (
        r"\b\d+\s+[A-Za-z]+\s+[A-Za-z]+\s+"
        r"(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd|Way|Place|Pl)\b",
        "[ADDRESS]",
    ),
    "A_NUMBER": (r"\bA\d{8,9}\b", "[A-NUMBER]"),
    "NJ_DL": (r"\b[A-Z]\d{14}\b", "[NJ_DL]"),
    "IMMIGRATION_PETITION": (
        r"\b(EAC|WAC|LIN|SRC|NBC|MSC|IOE)\d{10,13}\b",
        "[IMMIGRATION_PETITION]",
    ),
}


# ===================================================================
# Custom Presidio Recognizers
# ===================================================================

def _build_custom_recognizers():
    """Build custom PatternRecognizer instances for immigration-specific PII."""
    from presidio_analyzer import Pattern, PatternRecognizer

    recognizers = []

    # A-Number (Alien Registration Number): A followed by 8-9 digits
    recognizers.append(
        PatternRecognizer(
            supported_entity="A_NUMBER",
            name="ImmigrationANumberRecognizer",
            patterns=[
                Pattern(
                    name="a_number",
                    regex=r"\bA\d{8,9}\b",
                    score=0.95,
                ),
            ],
            supported_language="en",
        )
    )

    # NJ Driver License: 1 letter + 14 digits
    recognizers.append(
        PatternRecognizer(
            supported_entity="NJ_DRIVERS_LICENSE",
            name="NJDriversLicenseRecognizer",
            patterns=[
                Pattern(
                    name="nj_dl",
                    regex=r"\b[A-Z]\d{14}\b",
                    score=0.85,
                ),
            ],
            supported_language="en",
        )
    )

    # Immigration petition / receipt numbers (USCIS)
    # Format: 3-letter code + 10-13 digits
    recognizers.append(
        PatternRecognizer(
            supported_entity="IMMIGRATION_PETITION",
            name="ImmigrationPetitionRecognizer",
            patterns=[
                Pattern(
                    name="petition_number",
                    regex=r"\b(EAC|WAC|LIN|SRC|NBC|MSC|IOE)\d{10,13}\b",
                    score=0.90,
                ),
            ],
            supported_language="en",
        )
    )

    return recognizers


# ===================================================================
# Operator mapping (entity type → replacement marker)
# ===================================================================

ENTITY_MARKERS: dict[str, str] = {
    "PERSON": "[PERSON]",
    "PHONE_NUMBER": "[PHONE]",
    "EMAIL_ADDRESS": "[EMAIL]",
    "US_SSN": "[SSN]",
    "CREDIT_CARD": "[CREDIT_CARD]",
    "LOCATION": "[LOCATION]",
    "ADDRESS": "[ADDRESS]",
    "IP_ADDRESS": "[IP_ADDRESS]",
    "DATE_TIME": "[DATE]",
    "NRP": "[NRP]",
    "US_DRIVER_LICENSE": "[DRIVERS_LICENSE]",
    "US_PASSPORT": "[PASSPORT]",
    "US_BANK_NUMBER": "[BANK_NUMBER]",
    "US_ITIN": "[ITIN]",
    "A_NUMBER": "[A-NUMBER]",
    "NJ_DRIVERS_LICENSE": "[NJ_DL]",
    "IMMIGRATION_PETITION": "[IMMIGRATION_PETITION]",
}

DEFAULT_MARKER = "[PII]"


def _build_anonymizer_config():
    """Build Presidio anonymizer operator config using type markers."""
    from presidio_anonymizer.entities import OperatorConfig

    operators: dict[str, OperatorConfig] = {}
    for entity_type, marker in ENTITY_MARKERS.items():
        operators[entity_type] = OperatorConfig(
            "replace", {"new_value": marker}
        )
    # Default for unknown entity types
    operators["DEFAULT"] = OperatorConfig(
        "replace", {"new_value": DEFAULT_MARKER}
    )
    return operators


# ===================================================================
# Public API
# ===================================================================

def configure_recognizers():
    """
    Add custom recognizers for immigration-specific PII to the analyzer.
    Called by init_presidio(), but can be called again to refresh.
    """
    global _analyzer
    if _analyzer is None:
        raise RuntimeError("Call init_presidio() before configure_recognizers()")

    for recognizer in _build_custom_recognizers():
        _analyzer.registry.add_recognizer(recognizer)
    logger.info("Custom immigration recognizers registered")


def init_presidio(languages: Optional[list[str]] = None):
    """
    Initialize Presidio analyzer and anonymizer engines.

    Parameters
    ----------
    languages : list[str]
        Languages to support (default: ``["en", "es"]``).
    """
    global _analyzer, _anonymizer, _initialized, _scrub_stats

    if languages is None:
        languages = ["en", "es"]

    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()

        # Register custom recognizers
        configure_recognizers()

        _initialized = True
        _scrub_stats = {}
        logger.info("Presidio guard initialized (languages=%s)", languages)
    except ImportError:
        logger.warning(
            "presidio-analyzer / presidio-anonymizer not installed. "
            "Falling back to regex-only PII scrubbing."
        )
        _initialized = False


def _fallback_scrub(text: str) -> tuple[str, list[dict]]:
    """Regex-only PII scrubbing when Presidio is unavailable."""
    entities_found: list[dict] = []
    scrubbed = text
    for entity_type, (pattern, marker) in FALLBACK_PATTERNS.items():
        for match in re.finditer(pattern, scrubbed, flags=re.IGNORECASE):
            entities_found.append({
                "entity_type": entity_type,
                "score": 1.0,
                "start": match.start(),
                "end": match.end(),
                "recognizer": "fallback_regex",
            })
        scrubbed = re.sub(pattern, marker, scrubbed, flags=re.IGNORECASE)
    return scrubbed, entities_found


def _regex_sweep(text: str) -> tuple[str, list[dict]]:
    """
    Secondary regex sweep to catch anything Presidio missed.
    Applied after Presidio's pass.
    """
    extra_entities: list[dict] = []
    swept = text
    for entity_type, (pattern, marker) in FALLBACK_PATTERNS.items():
        # Only replace if the marker isn't already there
        for match in re.finditer(pattern, swept, flags=re.IGNORECASE):
            extra_entities.append({
                "entity_type": entity_type,
                "score": 1.0,
                "start": match.start(),
                "end": match.end(),
                "recognizer": "regex_sweep",
            })
        swept = re.sub(pattern, marker, swept, flags=re.IGNORECASE)
    return swept, extra_entities


def scrub_pii(
    text: str, language: str = "en"
) -> tuple[str, list[dict]]:
    """
    Redact PII from *text* and return ``(redacted_text, entities)``.

    Each entity dict contains:
        entity_type, score, start, end, recognizer

    Parameters
    ----------
    text : str
        Raw text to scrub.
    language : str
        ISO language code (default ``"en"``).

    Returns
    -------
    tuple[str, list[dict]]
        (scrubbed text, list of detected entity dicts)
    """
    global _scrub_stats

    if not text or not text.strip():
        return text, []

    entities_list: list[dict] = []

    # --- Presidio pass ---
    if _initialized and _analyzer is not None and _anonymizer is not None:
        try:
            results = _analyzer.analyze(
                text=text,
                language=language,
                entities=None,  # detect all
            )
            if results:
                anonymized = _anonymizer.anonymize(
                    text=text,
                    analyzer_results=results,
                    operators=_build_anonymizer_config(),
                )
                scrubbed = anonymized.text
                for r in results:
                    entities_list.append({
                        "entity_type": r.entity_type,
                        "score": round(r.score, 4),
                        "start": r.start,
                        "end": r.end,
                        "recognizer": r.recognition_metadata.get(
                            "recognizer_name", "presidio"
                        ) if r.recognition_metadata else "presidio",
                    })
            else:
                scrubbed = text
        except Exception as exc:
            logger.error("Presidio analysis failed: %s — using fallback", exc)
            scrubbed, entities_list = _fallback_scrub(text)
    else:
        # Presidio not available — pure regex
        scrubbed, entities_list = _fallback_scrub(text)

    # --- Secondary regex sweep (catches anything Presidio missed) ---
    scrubbed, extra = _regex_sweep(scrubbed)
    entities_list.extend(extra)

    # --- Update stats ---
    for ent in entities_list:
        etype = ent["entity_type"]
        _scrub_stats[etype] = _scrub_stats.get(etype, 0) + 1

    return scrubbed, entities_list


def batch_scrub(
    texts: list[str], language: str = "en"
) -> list[tuple[str, list[dict]]]:
    """
    Efficiently scrub PII from a list of texts.

    Returns a list of ``(scrubbed_text, entities)`` tuples, one per input.
    """
    return [scrub_pii(t, language=language) for t in texts]


def get_scrub_stats() -> dict[str, int]:
    """Return cumulative dict of entity_type → count of redactions."""
    return dict(_scrub_stats)


def validate_redaction(text: str) -> bool:
    """
    Return ``True`` if *text* appears free of residual PII patterns.
    Uses the fallback regex bank as a post-hoc check.
    """
    for _entity_type, (pattern, _marker) in FALLBACK_PATTERNS.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            return False
    return True


def create_audit_log(
    original: str,
    scrubbed: str,
    entities: list[dict],
) -> dict:
    """
    Create an audit record for a single scrub operation.

    Stores a SHA-256 **hash** of the original — never the original text.

    Returns the audit dict and appends it to ``data/logs/pii_audit.json``.
    """
    audit: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "original_hash": hashlib.sha256(original.encode("utf-8")).hexdigest(),
        "scrubbed_preview": scrubbed[:120],
        "entities_detected": len(entities),
        "entity_types": list({e["entity_type"] for e in entities}),
        "entities": entities,
        "redaction_valid": validate_redaction(scrubbed),
    }

    # Append to audit log (JSON-lines style)
    try:
        with open(PII_AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit) + "\n")
    except OSError as exc:
        logger.error("Failed to write PII audit log: %s", exc)

    return audit


# ===================================================================
# Convenience: one-call scrub + audit
# ===================================================================

def scrub_and_audit(text: str, language: str = "en") -> str:
    """
    Scrub PII and write an audit record in one call.
    Returns the scrubbed text only.
    """
    scrubbed, entities = scrub_pii(text, language=language)
    if entities:
        create_audit_log(original=text, scrubbed=scrubbed, entities=entities)
    return scrubbed


# ===================================================================
# Standalone pipeline entry point
# ===================================================================

def run_presidio_guard() -> dict:
    """
    Standalone pipeline step: scrub PII from all processed records.

    Reads ``all_records.csv``, scrubs every text field, and overwrites
    the file in-place. Returns summary statistics.
    """
    import pandas as pd

    init_presidio()

    records_path = PROCESSED_DIR / "all_records.csv"
    if not records_path.exists():
        logger.info("No records file found at %s — nothing to scrub.", records_path)
        return {"records": 0, "entities_found": 0}

    df = pd.read_csv(records_path, encoding="utf-8")
    if df.empty or "text" not in df.columns:
        logger.info("Empty records file — nothing to scrub.")
        return {"records": 0, "entities_found": 0}

    total_entities = 0
    scrubbed_texts = []
    for text in df["text"].fillna(""):
        clean, entities = scrub_pii(str(text))
        scrubbed_texts.append(clean)
        total_entities += len(entities)

    df["text"] = scrubbed_texts
    df.to_csv(records_path, index=False, encoding="utf-8")

    logger.info(
        "Presidio guard scrubbed %d records (%d entities redacted)",
        len(df), total_entities,
    )
    return {
        "records": len(df),
        "entities_found": total_entities,
        "stats": get_scrub_stats(),
    }


# ===================================================================
# Module self-test
# ===================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    init_presidio()

    samples = [
        "John Smith called 555-123-4567 about case A123456789 at 42 Oak Street.",
        "Email jane.doe@example.com, SSN 123-45-6789, NJ license B12345678901234.",
        "Petition WAC2190012345 filed by Maria Garcia on 2026-01-15.",
        "No PII in this community concern about local transit.",
        "La familia en 123 Main Avenue necesita ayuda con EAC2100098765.",
    ]

    for s in samples:
        clean, ents = scrub_pii(s)
        valid = validate_redaction(clean)
        print(f"\nOriginal : {s}")
        print(f"Scrubbed : {clean}")
        print(f"Entities : {[e['entity_type'] for e in ents]}")
        print(f"Valid    : {valid}")

    print(f"\nStats: {get_scrub_stats()}")
