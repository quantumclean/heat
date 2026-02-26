"""
spaCy Transformer NER + Event Tagging for HEAT.

Industrial NLP extraction replacing heuristic parsing.
Uses spaCy transformer pipeline (en_core_web_trf) with fallback
to en_core_web_sm. Provides entity extraction, civic event
detection, relevance scoring, and PII-safe output.
"""
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

# ---------------------------------------------------------------------------
# Civic event taxonomy
# ---------------------------------------------------------------------------
CIVIC_EVENT_TYPES = [
    "POLICY_CHANGE",
    "ENFORCEMENT_ACTION",
    "COMMUNITY_RESPONSE",
    "LEGAL_PROCEEDING",
    "ADVOCACY_EVENT",
    "PUBLIC_HEARING",
]

# Keyword triggers for each event type (lowercased)
_EVENT_TRIGGERS: dict[str, list[str]] = {
    "POLICY_CHANGE": [
        "policy", "executive order", "regulation", "rule change",
        "ordinance", "resolution", "legislation", "signed into law",
        "enacted", "repealed", "amended", "moratorium",
    ],
    "ENFORCEMENT_ACTION": [
        "enforcement", "detained", "deported", "deportation",
        "checkpoint", "sweep", "removal", "warrant", "custody",
        "ice", "cbp", "apprehended",
    ],
    "COMMUNITY_RESPONSE": [
        "rally", "protest", "march", "vigil", "demonstration",
        "petition", "mutual aid", "volunteer", "community meeting",
        "town hall", "organizing", "solidarity",
    ],
    "LEGAL_PROCEEDING": [
        "court", "hearing", "lawsuit", "injunction", "ruling",
        "appeal", "judge", "attorney", "legal aid", "habeas corpus",
        "bond", "asylum", "immigration court",
    ],
    "ADVOCACY_EVENT": [
        "advocacy", "campaign", "fundraiser", "awareness",
        "outreach", "workshop", "training", "know your rights",
        "clinic", "resource fair", "coalition",
    ],
    "PUBLIC_HEARING": [
        "public hearing", "council meeting", "board meeting",
        "testimony", "public comment", "agenda", "minutes",
        "city council", "school board", "zoning",
    ],
}

# Civic relevance keywords (aligned with nlp_analysis.py CIVIC_KEYWORDS)
CIVIC_KEYWORDS: dict[str, list[str]] = {
    "enforcement": [
        "ice", "immigration", "enforcement", "deportation",
        "detention", "raid", "checkpoint",
    ],
    "community": [
        "community", "families", "residents", "neighborhood",
        "local", "citizens",
    ],
    "legal": [
        "legal", "rights", "lawyer", "attorney", "court",
        "hearing", "asylum", "visa",
    ],
    "safety": [
        "safety", "fear", "anxiety", "concern", "worry",
        "scared", "afraid",
    ],
    "response": [
        "sanctuary", "protection", "support", "resources",
        "help", "aid", "services",
    ],
    "education": [
        "school", "students", "attendance", "children",
        "education", "campus",
    ],
    "workplace": [
        "workplace", "employer", "business", "work", "job",
        "employment",
    ],
    "government": [
        "council", "mayor", "city", "county", "federal",
        "state", "policy",
    ],
}

# Flat set for fast lookup
_ALL_CIVIC_TERMS: set[str] = set()
for _terms in CIVIC_KEYWORDS.values():
    _ALL_CIVIC_TERMS.update(_terms)

# Entity types of interest
_ENTITY_TYPES = {"ORG", "GPE", "DATE", "EVENT", "PERSON", "LOC", "FAC", "NORP", "LAW"}

# ---------------------------------------------------------------------------
# spaCy model loading
# ---------------------------------------------------------------------------
_nlp = None
_model_name_loaded: Optional[str] = None


def init_nlp(model_name: Optional[str] = None):
    """
    Load spaCy model with transformer pipeline.

    Tries en_core_web_trf first; falls back to en_core_web_sm.
    The loaded model is cached at module level.

    Parameters
    ----------
    model_name : str, optional
        Explicit model name override.

    Returns
    -------
    spacy.Language
    """
    global _nlp, _model_name_loaded
    import spacy

    candidates = (
        [model_name] if model_name
        else ["en_core_web_trf", "en_core_web_sm"]
    )

    for name in candidates:
        try:
            logger.info("Loading spaCy model '%s'...", name)
            _nlp = spacy.load(name)
            _model_name_loaded = name
            logger.info("Loaded spaCy model '%s'.", name)
            return _nlp
        except OSError:
            logger.warning("spaCy model '%s' not found, trying next.", name)

    raise RuntimeError(
        "No spaCy model available. Install one with:\n"
        "  python -m spacy download en_core_web_trf\n"
        "  OR  python -m spacy download en_core_web_sm"
    )


def _ensure_nlp():
    """Ensure the spaCy model is loaded."""
    global _nlp
    if _nlp is None:
        init_nlp()
    return _nlp


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

def extract_entities(text: str) -> dict[str, list[dict]]:
    """
    Extract named entities grouped by type.

    Parameters
    ----------
    text : str
        Input document.

    Returns
    -------
    dict keyed by entity type (ORG, GPE, DATE, …), each value a list of
    dicts with keys: text, start, end, label.
    """
    nlp = _ensure_nlp()
    doc = nlp(text)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for ent in doc.ents:
        if ent.label_ in _ENTITY_TYPES:
            grouped[ent.label_].append(
                {
                    "text": ent.text,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "label": ent.label_,
                }
            )

    return dict(grouped)


def extract_location_entities(text: str) -> list[dict]:
    """
    Extract specifically GPE, LOC, and FAC entities for geocoding.

    Returns
    -------
    list of dicts with keys: text, label, start, end.
    """
    nlp = _ensure_nlp()
    doc = nlp(text)

    locations = []
    seen = set()
    for ent in doc.ents:
        if ent.label_ in {"GPE", "LOC", "FAC"}:
            key = (ent.text, ent.label_)
            if key not in seen:
                seen.add(key)
                locations.append(
                    {
                        "text": ent.text,
                        "label": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                    }
                )
    return locations


# ---------------------------------------------------------------------------
# Event extraction
# ---------------------------------------------------------------------------

def _classify_event_type(text: str) -> str:
    """Return best matching CIVIC_EVENT_TYPE for a span of text."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for etype, triggers in _EVENT_TRIGGERS.items():
        score = sum(1 for t in triggers if t in text_lower)
        if score > 0:
            scores[etype] = score

    if not scores:
        return "COMMUNITY_RESPONSE"  # safe default
    return max(scores, key=scores.get)


def extract_events(text: str) -> list[dict]:
    """
    Identify civic events in text with structured output.

    Each event dict contains:
        event_type  : one of CIVIC_EVENT_TYPES
        date        : extracted DATE entity or None
        location    : extracted GPE/LOC/FAC or None
        actors      : list of ORG/PERSON entities involved
        description : sentence-level span containing the event trigger
    """
    nlp = _ensure_nlp()
    doc = nlp(text)

    # Collect entity spans
    dates = [ent.text for ent in doc.ents if ent.label_ == "DATE"]
    locations = [ent.text for ent in doc.ents if ent.label_ in {"GPE", "LOC", "FAC"}]
    actors = [ent.text for ent in doc.ents if ent.label_ in {"ORG", "PERSON"}]

    events: list[dict] = []
    for sent in doc.sents:
        sent_text = sent.text.strip()
        if not sent_text:
            continue

        # Check if sentence contains any event trigger
        sent_lower = sent_text.lower()
        triggered = False
        for triggers in _EVENT_TRIGGERS.values():
            if any(t in sent_lower for t in triggers):
                triggered = True
                break

        if not triggered:
            continue

        event_type = _classify_event_type(sent_text)

        # Find entities within this sentence span
        sent_dates = [e.text for e in doc.ents
                      if e.label_ == "DATE" and e.start_char >= sent.start_char and e.end_char <= sent.end_char]
        sent_locs = [e.text for e in doc.ents
                     if e.label_ in {"GPE", "LOC", "FAC"} and e.start_char >= sent.start_char and e.end_char <= sent.end_char]
        sent_actors = [e.text for e in doc.ents
                       if e.label_ in {"ORG", "PERSON"} and e.start_char >= sent.start_char and e.end_char <= sent.end_char]

        events.append(
            {
                "event_type": event_type,
                "date": sent_dates[0] if sent_dates else (dates[0] if dates else None),
                "location": sent_locs[0] if sent_locs else (locations[0] if locations else None),
                "actors": sent_actors or actors[:3],
                "description": sent_text[:300],
            }
        )

    return events


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def batch_extract(texts: list[str]) -> list[dict]:
    """
    Efficient batch NER + event extraction using nlp.pipe().

    Parameters
    ----------
    texts : list[str]
        Documents to process.

    Returns
    -------
    list of dicts, one per document, each containing:
        entities : dict grouped by type
        events   : list of event dicts
        locations: list of location entity dicts
    """
    nlp = _ensure_nlp()
    results = []

    # Use nlp.pipe for batched transformer inference
    batch_size = 16 if "trf" in (_model_name_loaded or "") else 64
    for doc in nlp.pipe(texts, batch_size=batch_size):
        # Entities
        grouped: dict[str, list[dict]] = defaultdict(list)
        for ent in doc.ents:
            if ent.label_ in _ENTITY_TYPES:
                grouped[ent.label_].append(
                    {"text": ent.text, "label": ent.label_,
                     "start": ent.start_char, "end": ent.end_char}
                )

        # Locations
        locs = []
        seen_locs = set()
        for ent in doc.ents:
            if ent.label_ in {"GPE", "LOC", "FAC"}:
                key = (ent.text, ent.label_)
                if key not in seen_locs:
                    seen_locs.add(key)
                    locs.append({"text": ent.text, "label": ent.label_,
                                 "start": ent.start_char, "end": ent.end_char})

        # Events (sentence-level)
        events = []
        dates = [ent.text for ent in doc.ents if ent.label_ == "DATE"]
        all_locs = [ent.text for ent in doc.ents if ent.label_ in {"GPE", "LOC", "FAC"}]
        all_actors = [ent.text for ent in doc.ents if ent.label_ in {"ORG", "PERSON"}]

        for sent in doc.sents:
            sent_lower = sent.text.lower()
            triggered = any(
                t in sent_lower
                for triggers in _EVENT_TRIGGERS.values()
                for t in triggers
            )
            if not triggered:
                continue

            s_dates = [e.text for e in doc.ents
                       if e.label_ == "DATE" and e.start_char >= sent.start_char and e.end_char <= sent.end_char]
            s_locs = [e.text for e in doc.ents
                      if e.label_ in {"GPE", "LOC", "FAC"} and e.start_char >= sent.start_char and e.end_char <= sent.end_char]
            s_actors = [e.text for e in doc.ents
                        if e.label_ in {"ORG", "PERSON"} and e.start_char >= sent.start_char and e.end_char <= sent.end_char]

            events.append({
                "event_type": _classify_event_type(sent.text),
                "date": s_dates[0] if s_dates else (dates[0] if dates else None),
                "location": s_locs[0] if s_locs else (all_locs[0] if all_locs else None),
                "actors": s_actors or all_actors[:3],
                "description": sent.text.strip()[:300],
            })

        results.append({
            "entities": dict(grouped),
            "events": events,
            "locations": locs,
        })

    return results


# ---------------------------------------------------------------------------
# Civic relevance scoring
# ---------------------------------------------------------------------------

def tag_civic_relevance(text: str) -> float:
    """
    Score 0–1 how relevant text is to civic / immigration topics.

    Combines:
      - keyword density from CIVIC_KEYWORDS categories
      - entity relevance (ORG, GPE presence)
      - event trigger density
    """
    nlp = _ensure_nlp()
    doc = nlp(text)
    text_lower = text.lower()
    words = re.findall(r"\b[a-z]{3,}\b", text_lower)
    total_words = max(len(words), 1)

    # 1. Keyword density (0–0.5)
    civic_hits = sum(1 for w in words if w in _ALL_CIVIC_TERMS)
    keyword_score = min(civic_hits / total_words * 5, 0.5)  # scaled

    # 2. Entity relevance (0–0.25)
    relevant_ent_types = {"ORG", "GPE", "LOC", "FAC", "LAW", "NORP"}
    ent_count = sum(1 for ent in doc.ents if ent.label_ in relevant_ent_types)
    entity_score = min(ent_count / max(total_words, 1) * 10, 0.25)

    # 3. Event trigger presence (0–0.25)
    trigger_hits = sum(
        1
        for triggers in _EVENT_TRIGGERS.values()
        for t in triggers
        if t in text_lower
    )
    trigger_score = min(trigger_hits / 10, 0.25)

    return round(min(keyword_score + entity_score + trigger_score, 1.0), 4)


# ---------------------------------------------------------------------------
# PII safety
# ---------------------------------------------------------------------------

def _redact_persons(entities: dict[str, list[dict]], text: str) -> tuple[dict, str]:
    """
    Remove PERSON entities from entity dict and redact them in text.

    Returns
    -------
    (redacted_entities, redacted_text)
    """
    redacted_entities = {k: v for k, v in entities.items() if k != "PERSON"}
    redacted_text = text
    persons = entities.get("PERSON", [])
    # Sort by start descending to preserve offsets
    for ent in sorted(persons, key=lambda e: e["start"], reverse=True):
        redacted_text = (
            redacted_text[: ent["start"]]
            + "[REDACTED]"
            + redacted_text[ent["end"]:]
        )
    return redacted_entities, redacted_text


# ---------------------------------------------------------------------------
# Timeline construction
# ---------------------------------------------------------------------------

def build_event_timeline(entities_list: list[dict]) -> list[dict]:
    """
    Create chronological event timeline from batch_extract results.

    Parameters
    ----------
    entities_list : list[dict]
        Output of batch_extract — one dict per document.

    Returns
    -------
    list of event dicts sorted by date (earliest first).
    Events without parseable dates are appended at the end.
    """
    dated_events: list[tuple[Optional[datetime], dict]] = []

    for doc_result in entities_list:
        for event in doc_result.get("events", []):
            parsed_date = None
            if event.get("date"):
                try:
                    from dateutil.parser import parse as dateparse
                    parsed_date = dateparse(event["date"], fuzzy=True)
                except Exception:
                    pass

            dated_events.append((parsed_date, event))

    # Sort: dated first (ascending), then undated
    dated = sorted(
        [(d, e) for d, e in dated_events if d is not None],
        key=lambda x: x[0],
    )
    undated = [(d, e) for d, e in dated_events if d is None]

    timeline = []
    for dt, event in dated + undated:
        entry = dict(event)
        entry["parsed_date"] = dt.isoformat() if dt else None
        timeline.append(entry)

    return timeline


# ---------------------------------------------------------------------------
# Cluster enrichment
# ---------------------------------------------------------------------------

def enrich_cluster(cluster_texts: list[str], redact_pii: bool = True) -> dict:
    """
    Run full NER + event extraction on a cluster's texts.

    Parameters
    ----------
    cluster_texts : list[str]
        All texts belonging to a single cluster.
    redact_pii : bool
        If True, PERSON entities are stripped from public-facing output.

    Returns
    -------
    Enrichment dict:
        entity_summary  : Counter per entity type → most common values
        events          : list of all extracted events
        timeline        : chronological event timeline
        locations       : deduplicated location entities
        civic_relevance : mean relevance score across cluster
        dominant_event_type : most frequent event type
    """
    batch_results = batch_extract(cluster_texts)

    # Aggregate entities
    entity_counter: dict[str, Counter] = defaultdict(Counter)
    all_events: list[dict] = []
    all_locations: list[dict] = []
    relevance_scores: list[float] = []

    for i, result in enumerate(batch_results):
        entities = result["entities"]

        if redact_pii:
            entities, _ = _redact_persons(entities, cluster_texts[i])

        for etype, ents in entities.items():
            for ent in ents:
                entity_counter[etype][ent["text"]] += 1

        all_events.extend(result["events"])
        all_locations.extend(result["locations"])
        relevance_scores.append(tag_civic_relevance(cluster_texts[i]))

    # Deduplicate locations
    seen = set()
    deduped_locations = []
    for loc in all_locations:
        key = (loc["text"], loc["label"])
        if key not in seen:
            seen.add(key)
            deduped_locations.append(loc)

    # Dominant event type
    event_type_counts = Counter(e["event_type"] for e in all_events)
    dominant = event_type_counts.most_common(1)[0][0] if event_type_counts else None

    # Timeline
    timeline = build_event_timeline(batch_results)

    # Entity summary (top 5 per type)
    entity_summary = {
        etype: counter.most_common(5)
        for etype, counter in entity_counter.items()
    }

    return {
        "entity_summary": entity_summary,
        "events": all_events,
        "timeline": timeline,
        "locations": deduped_locations,
        "civic_relevance": round(
            sum(relevance_scores) / max(len(relevance_scores), 1), 4
        ),
        "dominant_event_type": dominant,
    }


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_ner_engine() -> dict:
    """Pipeline entry point: run NER enrichment on clustered records.

    Reads ``clustered_records.csv``, groups by ``cluster`` (cluster_id),
    calls ``enrich_cluster()`` per cluster, and exports per-cluster
    enriched metadata to ``data/processed/ner_enrichment.json``.

    This replaces heuristic keyword-matching categorization in
    ``nlp_analysis.py`` with transformer-based entity extraction,
    civic event detection, and relevance scoring.

    Returns
    -------
    dict
        Summary with entity/event counts per cluster.
    """
    init_nlp()

    # Load clustered records
    records_path = PROCESSED_DIR / "clustered_records.csv"
    if not records_path.exists():
        logger.warning("clustered_records.csv not found — skipping NER")
        return {"records": 0, "clusters": 0, "entities": 0, "events": 0}

    import pandas as pd
    df = pd.read_csv(records_path, encoding="utf-8")
    if df.empty or "text" not in df.columns:
        logger.info("No records to process for NER.")
        return {"records": 0, "clusters": 0, "entities": 0, "events": 0}

    # Determine cluster column name (pipeline uses "cluster")
    cluster_col = "cluster_id" if "cluster_id" in df.columns else "cluster"
    if cluster_col not in df.columns:
        logger.warning("No cluster column found — treating all records as one cluster")
        df[cluster_col] = 0

    total_entities = 0
    total_events = 0
    cluster_enrichments: dict[str, dict] = {}

    cluster_ids = sorted(df[cluster_col].dropna().unique())
    logger.info("Running NER enrichment on %d clusters (%d records)…",
                len(cluster_ids), len(df))

    for cid in cluster_ids:
        cluster_df = df[df[cluster_col] == cid]
        texts = cluster_df["text"].dropna().tolist()
        if not texts:
            continue

        enrichment = enrich_cluster(texts, redact_pii=True)

        # Tally counts
        ent_count = sum(
            len(ents) for ents in enrichment.get("entity_summary", {}).values()
        )
        evt_count = len(enrichment.get("events", []))
        total_entities += ent_count
        total_events += evt_count

        cluster_enrichments[str(int(cid))] = {
            "cluster_id": int(cid),
            "record_count": len(texts),
            **enrichment,
        }
        logger.debug("Cluster %d: %d entities, %d events, relevance=%.4f",
                      cid, ent_count, evt_count,
                      enrichment.get("civic_relevance", 0.0))

    # Export combined enrichment JSON (all clusters)
    output_path = PROCESSED_DIR / "ner_enrichment.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cluster_count": len(cluster_enrichments),
        "total_entities": total_entities,
        "total_events": total_events,
        "clusters": cluster_enrichments,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    logger.info("Exported per-cluster NER enrichment → %s", output_path)

    summary = {
        "records": len(df),
        "clusters": len(cluster_enrichments),
        "entities": total_entities,
        "events": total_events,
    }
    logger.info("NER engine complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def export_enrichment_json(
    enrichment: dict,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Write enrichment dict to JSON.

    Parameters
    ----------
    enrichment : dict
        Output of enrich_cluster.
    output_path : Path, optional
        Defaults to PROCESSED_DIR / "ner_enrichment.json".
    """
    if output_path is None:
        output_path = PROCESSED_DIR / "ner_enrichment.json"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **enrichment,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    logger.info("Exported NER enrichment → %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("ner_engine ready — import and call extract_entities(text) or enrich_cluster(texts)")
