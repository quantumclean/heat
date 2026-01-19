"""
Location Extraction Module for HEAT
Intelligent location extraction with confidence scoring for social media posts.

This module extracts geographic information from unstructured text, assigns
confidence scores, and maps locations to Plainfield, NJ ZIP codes.

CRITICAL: Part of the safety buffer system - low confidence extractions
must be flagged for manual review to prevent misinformation.
"""
from dataclasses import dataclass
from typing import Optional, Tuple, List
import re
from pathlib import Path

# Import existing config
from config import ZIP_CENTROIDS, TARGET_ZIPS

# ============================================
# Location Confidence Thresholds
# ============================================
LOCATION_CONFIDENCE_THRESHOLD = 0.5  # Minimum confidence to include
MANUAL_REVIEW_THRESHOLD = 0.7        # Below this needs human review

# ============================================
# Geographic Data
# ============================================

# ZIP code boundaries (from app.js)
ZIP_BOUNDARIES = {
    "07060": {
        "center": (40.6137, -74.4154),
        "bounds": {"n": 40.6250, "s": 40.6020, "e": -74.4000, "w": -74.4350},
    },
    "07062": {
        "center": (40.6280, -74.4050),
        "bounds": {"n": 40.6400, "s": 40.6160, "e": -74.3900, "w": -74.4200},
    },
    "07063": {
        "center": (40.5980, -74.4280),
        "bounds": {"n": 40.6100, "s": 40.5860, "e": -74.4100, "w": -74.4450},
    },
}

# Street coordinates for landmark matching (from app.js STREET_COORDS)
STREET_COORDS = {
    "front street": {"lat": 40.6145, "lng": -74.4185, "zip": "07060"},
    "park avenue": {"lat": 40.6180, "lng": -74.4120, "zip": "07060"},
    "watchung avenue": {"lat": 40.6200, "lng": -74.4080, "zip": "07060"},
    "south avenue": {"lat": 40.6050, "lng": -74.4180, "zip": "07060"},
    "plainfield avenue": {"lat": 40.6160, "lng": -74.4200, "zip": "07060"},
    "west front street": {"lat": 40.6140, "lng": -74.4230, "zip": "07060"},
    "east front street": {"lat": 40.6148, "lng": -74.4100, "zip": "07060"},
    "somerset street": {"lat": 40.6195, "lng": -74.4145, "zip": "07062"},
    "green brook road": {"lat": 40.6280, "lng": -74.4050, "zip": "07062"},
    "grove street": {"lat": 40.6240, "lng": -74.4080, "zip": "07062"},
    "leland avenue": {"lat": 40.6050, "lng": -74.4250, "zip": "07063"},
    "woodland avenue": {"lat": 40.5990, "lng": -74.4300, "zip": "07063"},
    "clinton avenue": {"lat": 40.6020, "lng": -74.4220, "zip": "07063"},
    "terrill road": {"lat": 40.5960, "lng": -74.4320, "zip": "07063"},
    "west 7th street": {"lat": 40.6180, "lng": -74.4200, "zip": "07060"},
    "west 4th street": {"lat": 40.6155, "lng": -74.4180, "zip": "07060"},
    "2nd street": {"lat": 40.6135, "lng": -74.4150, "zip": "07060"},
    "3rd street": {"lat": 40.6145, "lng": -74.4160, "zip": "07060"},
    "central avenue": {"lat": 40.6170, "lng": -74.4130, "zip": "07060"},
    "madison avenue": {"lat": 40.6100, "lng": -74.4140, "zip": "07060"},
}

# Nearby cities for context (not Plainfield, but relevant)
NEARBY_LOCATIONS = {
    "edison": {"center": (40.5187, -74.4121), "zip": None},
    "metuchen": {"center": (40.5432, -74.3629), "zip": None},
    "piscataway": {"center": (40.5570, -74.4588), "zip": None},
    "dunellen": {"center": (40.5887, -74.4718), "zip": None},
    "south plainfield": {"center": (40.5779, -74.4115), "zip": None},
    "north plainfield": {"center": (40.6312, -74.4276), "zip": "07062"},
    "scotch plains": {"center": (40.6462, -74.3832), "zip": None},
    "fanwood": {"center": (40.6412, -74.3826), "zip": None},
}

# Landmarks and neighborhoods
LANDMARKS = {
    # Plainfield landmarks
    "plainfield train station": {"lat": 40.6166, "lng": -74.4110, "zip": "07060"},
    "plainfield public library": {"lat": 40.6137, "lng": -74.4154, "zip": "07060"},
    "cedarbrook plaza": {"lat": 40.5980, "lng": -74.4280, "zip": "07063"},
    "washington park": {"lat": 40.6200, "lng": -74.4100, "zip": "07060"},
    "green brook park": {"lat": 40.6280, "lng": -74.4050, "zip": "07062"},
    # Nearby landmarks for context
    "menlo park mall": {"lat": 40.5450, "lng": -74.3250, "zip": None},
    "rutgers stadium": {"lat": 40.5147, "lng": -74.4638, "zip": None},
}


@dataclass
class LocationExtraction:
    """
    Represents an extracted location with confidence metadata.
    
    Attributes:
        text: Original input text
        location: Extracted location string (e.g., "Front Street" or "07060")
        zip_code: Matched ZIP code (one of 07060, 07062, 07063) or None
        confidence: Confidence score 0.0-1.0
        extraction_method: How location was extracted (geotag/address/landmark/zip/city/context)
        coordinates: Optional (lat, lng) tuple
        needs_review: True if confidence < MANUAL_REVIEW_THRESHOLD
    
    Examples:
        >>> LocationExtraction(
        ...     text="Saw something on Front Street",
        ...     location="Front Street",
        ...     zip_code="07060",
        ...     confidence=0.7,
        ...     extraction_method="landmark",
        ...     coordinates=(40.6145, -74.4185),
        ...     needs_review=False
        ... )
    """
    text: str
    location: str
    zip_code: Optional[str]
    confidence: float
    extraction_method: str
    coordinates: Optional[Tuple[float, float]]
    needs_review: bool
    
    def __post_init__(self):
        """Validate and normalize after initialization."""
        # Ensure confidence is in valid range
        self.confidence = max(0.0, min(1.0, self.confidence))
        
        # Determine if manual review is needed
        self.needs_review = self.confidence < MANUAL_REVIEW_THRESHOLD
        
        # Normalize ZIP code
        if self.zip_code:
            self.zip_code = str(self.zip_code).zfill(5)


class LocationExtractor:
    """
    Extract locations from unstructured text with confidence scoring.
    
    Usage:
        >>> extractor = LocationExtractor()
        >>> results = extractor.extract("Saw checkpoint on Front Street, 07060")
        >>> for loc in results:
        ...     print(f"{loc.location} ({loc.confidence:.1f}) - {loc.extraction_method}")
        Front Street (0.7) - landmark
        07060 (0.5) - zip
    """
    
    def __init__(self):
        """Initialize extractor with regex patterns."""
        # Compile regex patterns for efficiency
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile all regex patterns for location extraction."""
        # ZIP code pattern (5 digits, optionally with -4)
        self.zip_pattern = re.compile(r'\b(070[6][0-3])(?:-\d{4})?\b')
        
        # Address pattern (number + street name)
        # Example: "123 Front Street", "456 Park Ave"
        self.address_pattern = re.compile(
            r'\b(\d{1,5})\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way)\b',
            re.IGNORECASE
        )
        
        # City names pattern
        self.city_pattern = re.compile(
            r'\b(Plainfield|North Plainfield|South Plainfield|Edison|Metuchen|Piscataway)\b',
            re.IGNORECASE
        )
        
        # Coordinate pattern (lat, lng in text)
        self.coord_pattern = re.compile(
            r'\b(40\.\d{4,6})\s*,\s*(-74\.\d{4,6})\b'
        )
    
    def extract(self, text: str, geotag: Optional[Tuple[float, float]] = None) -> List[LocationExtraction]:
        """
        Extract all possible locations from text, sorted by confidence.
        
        Args:
            text: Input text to extract locations from
            geotag: Optional explicit geotag coordinates (lat, lng)
        
        Returns:
            List of LocationExtraction objects, sorted by confidence (highest first)
        
        Examples:
            >>> extractor = LocationExtractor()
            >>> results = extractor.extract("Meeting at Plainfield Library, 07060")
            >>> results[0].location
            'plainfield public library'
            >>> results[0].confidence
            0.7
        """
        extractions = []
        text_lower = text.lower()
        
        # 1. Explicit geotag (confidence: 1.0)
        if geotag:
            geo_extraction = self._extract_from_geotag(text, geotag)
            if geo_extraction:
                extractions.append(geo_extraction)
        
        # 2. Coordinates in text (confidence: 0.9)
        coord_extractions = self._extract_coordinates(text)
        extractions.extend(coord_extractions)
        
        # 3. Street addresses (confidence: 0.9)
        address_extractions = self._extract_addresses(text)
        extractions.extend(address_extractions)
        
        # 4. Landmarks and streets (confidence: 0.7)
        landmark_extractions = self._extract_landmarks(text_lower)
        extractions.extend(landmark_extractions)
        
        # 5. ZIP codes (confidence: 0.5)
        zip_extractions = self._extract_zips(text)
        extractions.extend(zip_extractions)
        
        # 6. City names (confidence: 0.3)
        city_extractions = self._extract_cities(text)
        extractions.extend(city_extractions)
        
        # 7. Context-based inference (confidence: 0.1)
        if not extractions:
            context_extraction = self._extract_from_context(text)
            if context_extraction:
                extractions.append(context_extraction)
        
        # Sort by confidence (highest first) and filter by threshold
        extractions = [e for e in extractions if e.confidence >= LOCATION_CONFIDENCE_THRESHOLD]
        extractions.sort(key=lambda x: x.confidence, reverse=True)
        
        return extractions
    
    def _extract_from_geotag(self, text: str, coords: Tuple[float, float]) -> Optional[LocationExtraction]:
        """Extract location from explicit geotag coordinates."""
        lat, lng = coords
        
        # Check if coordinates fall within Plainfield ZIPs
        zip_code = self._coords_to_zip(lat, lng)
        
        if zip_code:
            return LocationExtraction(
                text=text,
                location=f"Geotag: {lat:.4f}, {lng:.4f}",
                zip_code=zip_code,
                confidence=1.0,
                extraction_method="geotag",
                coordinates=coords,
                needs_review=False
            )
        return None
    
    def _extract_coordinates(self, text: str) -> List[LocationExtraction]:
        """Extract coordinates mentioned in text."""
        extractions = []
        
        for match in self.coord_pattern.finditer(text):
            lat = float(match.group(1))
            lng = float(match.group(2))
            zip_code = self._coords_to_zip(lat, lng)
            
            if zip_code:
                extractions.append(LocationExtraction(
                    text=text,
                    location=f"{lat:.4f}, {lng:.4f}",
                    zip_code=zip_code,
                    confidence=0.9,
                    extraction_method="coordinates",
                    coordinates=(lat, lng),
                    needs_review=False
                ))
        
        return extractions
    
    def _extract_addresses(self, text: str) -> List[LocationExtraction]:
        """Extract street addresses from text."""
        extractions = []
        
        for match in self.address_pattern.finditer(text):
            number = match.group(1)
            street_name = match.group(2)
            street_type = match.group(3)
            
            full_address = f"{number} {street_name} {street_type}".lower()
            street_key = f"{street_name} {street_type}".lower()
            
            # Check if street is known
            if street_key in STREET_COORDS:
                street_data = STREET_COORDS[street_key]
                extractions.append(LocationExtraction(
                    text=text,
                    location=full_address,
                    zip_code=street_data["zip"],
                    confidence=0.9,
                    extraction_method="address",
                    coordinates=(street_data["lat"], street_data["lng"]),
                    needs_review=False
                ))
            else:
                # Unknown street, but valid address format
                # Try to infer ZIP from other context
                zip_match = self.zip_pattern.search(text)
                zip_code = zip_match.group(1) if zip_match else None
                
                extractions.append(LocationExtraction(
                    text=text,
                    location=full_address,
                    zip_code=zip_code,
                    confidence=0.6,  # Lower confidence for unknown street
                    extraction_method="address",
                    coordinates=None,
                    needs_review=True
                ))
        
        return extractions
    
    def _extract_landmarks(self, text_lower: str) -> List[LocationExtraction]:
        """Extract known landmarks and street names."""
        extractions = []
        
        # Check landmarks
        for landmark, data in LANDMARKS.items():
            if landmark in text_lower:
                extractions.append(LocationExtraction(
                    text=text_lower,
                    location=landmark,
                    zip_code=data["zip"],
                    confidence=0.7,
                    extraction_method="landmark",
                    coordinates=(data["lat"], data["lng"]) if data["zip"] else None,
                    needs_review=data["zip"] is None
                ))
        
        # Check street names (without address number)
        for street, data in STREET_COORDS.items():
            if street in text_lower:
                extractions.append(LocationExtraction(
                    text=text_lower,
                    location=street,
                    zip_code=data["zip"],
                    confidence=0.7,
                    extraction_method="landmark",
                    coordinates=(data["lat"], data["lng"]),
                    needs_review=False
                ))
        
        return extractions
    
    def _extract_zips(self, text: str) -> List[LocationExtraction]:
        """Extract ZIP codes from text."""
        extractions = []
        
        for match in self.zip_pattern.finditer(text):
            zip_code = match.group(1)
            
            if zip_code in ZIP_BOUNDARIES:
                coords = ZIP_BOUNDARIES[zip_code]["center"]
                extractions.append(LocationExtraction(
                    text=text,
                    location=f"ZIP {zip_code}",
                    zip_code=zip_code,
                    confidence=0.5,
                    extraction_method="zip",
                    coordinates=coords,
                    needs_review=True
                ))
        
        return extractions
    
    def _extract_cities(self, text: str) -> List[LocationExtraction]:
        """Extract city names from text."""
        extractions = []
        
        for match in self.city_pattern.finditer(text):
            city = match.group(1).lower()
            
            # Check if it's a Plainfield variant
            if "plainfield" in city:
                if city == "north plainfield":
                    zip_code = "07062"
                    coords = ZIP_BOUNDARIES["07062"]["center"]
                elif city == "south plainfield":
                    zip_code = "07063"
                    coords = ZIP_BOUNDARIES["07063"]["center"]
                else:
                    # Just "plainfield" - default to central
                    zip_code = "07060"
                    coords = ZIP_BOUNDARIES["07060"]["center"]
                
                extractions.append(LocationExtraction(
                    text=text,
                    location=city,
                    zip_code=zip_code,
                    confidence=0.3,
                    extraction_method="city",
                    coordinates=coords,
                    needs_review=True
                ))
            
            # Nearby cities (for context, but no Plainfield ZIP)
            elif city in NEARBY_LOCATIONS:
                data = NEARBY_LOCATIONS[city]
                extractions.append(LocationExtraction(
                    text=text,
                    location=city,
                    zip_code=data["zip"],
                    confidence=0.3,
                    extraction_method="city",
                    coordinates=data["center"],
                    needs_review=True
                ))
        
        return extractions
    
    def _extract_from_context(self, text: str) -> Optional[LocationExtraction]:
        """
        Infer location from context when no explicit location found.
        
        Very low confidence - requires manual review.
        Uses simple heuristics and keyword matching.
        """
        text_lower = text.lower()
        
        # Check for "near", "by", "around" with location keywords
        context_patterns = [
            r'near\s+(\w+)',
            r'by\s+(\w+)',
            r'around\s+(\w+)',
            r'in\s+the\s+(\w+)\s+area',
        ]
        
        for pattern in context_patterns:
            match = re.search(pattern, text_lower)
            if match:
                context_word = match.group(1)
                
                # If context word is in our known locations
                if context_word in [s.split()[0] for s in STREET_COORDS.keys()]:
                    # Default to central Plainfield
                    return LocationExtraction(
                        text=text,
                        location=f"Near {context_word}",
                        zip_code="07060",
                        confidence=0.1,
                        extraction_method="context",
                        coordinates=ZIP_BOUNDARIES["07060"]["center"],
                        needs_review=True
                    )
        
        return None
    
    def _coords_to_zip(self, lat: float, lng: float) -> Optional[str]:
        """Map coordinates to Plainfield ZIP code if within bounds."""
        for zip_code, data in ZIP_BOUNDARIES.items():
            bounds = data["bounds"]
            if (bounds["s"] <= lat <= bounds["n"] and 
                bounds["w"] <= lng <= bounds["e"]):
                return zip_code
        return None


def extract_location(text: str, geotag: Optional[Tuple[float, float]] = None) -> Optional[LocationExtraction]:
    """
    Convenience function to extract the best location from text.
    
    Args:
        text: Input text
        geotag: Optional geotag coordinates
    
    Returns:
        Highest confidence LocationExtraction or None if no valid location found
    
    Examples:
        >>> loc = extract_location("Checkpoint at Front Street")
        >>> loc.location
        'front street'
        >>> loc.confidence
        0.7
    """
    extractor = LocationExtractor()
    results = extractor.extract(text, geotag)
    return results[0] if results else None


def extract_all_locations(text: str, geotag: Optional[Tuple[float, float]] = None) -> List[LocationExtraction]:
    """
    Extract all possible locations from text.
    
    Args:
        text: Input text
        geotag: Optional geotag coordinates
    
    Returns:
        List of all LocationExtraction objects sorted by confidence
    
    Examples:
        >>> locs = extract_all_locations("Meeting at library in 07060")
        >>> len(locs)
        2
        >>> locs[0].extraction_method
        'landmark'
        >>> locs[1].extraction_method
        'zip'
    """
    extractor = LocationExtractor()
    return extractor.extract(text, geotag)


# ============================================
# Integration with Existing Pipeline
# ============================================

def enrich_records_with_locations(records_df) -> None:
    """
    Enrich DataFrame with location extractions in-place.
    
    Adds columns:
        - extracted_location: Best location string
        - location_confidence: Confidence score
        - location_method: Extraction method
        - location_coords_lat: Latitude (if available)
        - location_coords_lng: Longitude (if available)
        - location_needs_review: Boolean flag
    
    Args:
        records_df: DataFrame with 'text' column
    
    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({"text": ["Activity on Front Street"]})
        >>> enrich_records_with_locations(df)
        >>> df["extracted_location"].iloc[0]
        'front street'
    """
    extractor = LocationExtractor()
    
    results = []
    for text in records_df["text"]:
        # Get best location for each record
        extractions = extractor.extract(str(text))
        
        if extractions:
            best = extractions[0]
            results.append({
                "extracted_location": best.location,
                "location_confidence": best.confidence,
                "location_method": best.extraction_method,
                "location_coords_lat": best.coordinates[0] if best.coordinates else None,
                "location_coords_lng": best.coordinates[1] if best.coordinates else None,
                "location_needs_review": best.needs_review,
            })
        else:
            results.append({
                "extracted_location": None,
                "location_confidence": 0.0,
                "location_method": None,
                "location_coords_lat": None,
                "location_coords_lng": None,
                "location_needs_review": True,
            })
    
    # Add as new columns
    for key in results[0].keys():
        records_df[key] = [r[key] for r in results]


if __name__ == "__main__":
    """Test location extraction with examples."""
    
    print("=" * 60)
    print("HEAT Location Extractor - Test Suite")
    print("=" * 60)
    
    test_cases = [
        # Geotag
        ("Activity reported", (40.6145, -74.4185)),
        
        # Address
        ("Saw checkpoint at 123 Front Street",),
        
        # Landmark
        ("Meeting at Plainfield Public Library",),
        
        # Street name
        ("Something happening on Park Avenue",),
        
        # ZIP code
        ("Concern in 07060 area",),
        
        # City name
        ("Reports from Plainfield",),
        
        # Multiple locations
        ("Activity near Front Street and Park Avenue in 07060",),
        
        # Ambiguous
        ("Something happening in the area",),
        
        # Nearby city
        ("Heard reports from Edison",),
        
        # Coordinates in text
        ("Location: 40.6145, -74.4185",),
    ]
    
    extractor = LocationExtractor()
    
    for i, test in enumerate(test_cases, 1):
        if isinstance(test, tuple) and len(test) == 2 and isinstance(test[1], tuple):
            text, geotag = test
        else:
            text = test[0] if isinstance(test, tuple) else test
            geotag = None
        
        print(f"\n{i}. Input: \"{text}\"")
        if geotag:
            print(f"   Geotag: {geotag}")
        
        results = extractor.extract(text, geotag)
        
        if results:
            for j, loc in enumerate(results, 1):
                print(f"   [{j}] {loc.location}")
                print(f"       Confidence: {loc.confidence:.1f} ({loc.extraction_method})")
                print(f"       ZIP: {loc.zip_code or 'N/A'}")
                if loc.coordinates:
                    print(f"       Coords: ({loc.coordinates[0]:.4f}, {loc.coordinates[1]:.4f})")
                print(f"       Needs Review: {loc.needs_review}")
        else:
            print("   No locations extracted")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
