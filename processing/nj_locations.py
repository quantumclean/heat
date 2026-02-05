"""
Comprehensive New Jersey Location Database
Maps NJ cities/towns to their actual geographic coordinates and ZIP codes
"""

# Major NJ Cities with coordinates and primary ZIP codes
NJ_CITIES = {
    # North Jersey
    "newark": {"lat": 40.7357, "lng": -74.1724, "zip": "07102", "region": "north"},
    "jersey city": {"lat": 40.7178, "lng": -74.0431, "zip": "07302", "region": "north"},
    "paterson": {"lat": 40.9168, "lng": -74.1718, "zip": "07501", "region": "north"},
    "elizabeth": {"lat": 40.6640, "lng": -74.2107, "zip": "07201", "region": "north"},
    "edison": {"lat": 40.5187, "lng": -74.4121, "zip": "08817", "region": "central"},
    "woodbridge": {"lat": 40.5576, "lng": -74.2846, "zip": "07095", "region": "central"},
    "lakewood": {"lat": 40.0979, "lng": -74.2176, "zip": "08701", "region": "central"},
    "toms river": {"lat": 39.9537, "lng": -74.1979, "zip": "08753", "region": "south"},
    
    # Central Jersey
    "new brunswick": {"lat": 40.4862, "lng": -74.4518, "zip": "08901", "region": "central"},
    "perth amboy": {"lat": 40.5067, "lng": -74.2654, "zip": "08861", "region": "central"},
    "plainfield": {"lat": 40.6137, "lng": -74.4154, "zip": "07060", "region": "central"},
    "north plainfield": {"lat": 40.6312, "lng": -74.4276, "zip": "07062", "region": "central"},
    "south plainfield": {"lat": 40.5779, "lng": -74.4115, "zip": "07080", "region": "central"},
    "piscataway": {"lat": 40.5570, "lng": -74.4588, "zip": "08854", "region": "central"},
    "metuchen": {"lat": 40.5432, "lng": -74.3629, "zip": "08840", "region": "central"},
    "somerville": {"lat": 40.5743, "lng": -74.6099, "zip": "08876", "region": "central"},
    "bridgewater": {"lat": 40.5989, "lng": -74.6104, "zip": "08807", "region": "central"},
    "highland park": {"lat": 40.4968, "lng": -74.4254, "zip": "08904", "region": "central"},
    "dunellen": {"lat": 40.5887, "lng": -74.4718, "zip": "08812", "region": "central"},
    "bound brook": {"lat": 40.5682, "lng": -74.5382, "zip": "08805", "region": "central"},
    "manville": {"lat": 40.5407, "lng": -74.5876, "zip": "08835", "region": "central"},
    "raritan": {"lat": 40.5698, "lng": -74.6321, "zip": "08869", "region": "central"},
    
    # South Jersey
    "trenton": {"lat": 40.2171, "lng": -74.7429, "zip": "08608", "region": "south"},
    "princeton": {"lat": 40.3573, "lng": -74.6672, "zip": "08540", "region": "south"},
    "camden": {"lat": 39.9259, "lng": -75.1196, "zip": "08101", "region": "south"},
    "vineland": {"lat": 39.4864, "lng": -75.0257, "zip": "08360", "region": "south"},
    "atlantic city": {"lat": 39.3643, "lng": -74.4229, "zip": "08401", "region": "south"},
    "cherry hill": {"lat": 39.9349, "lng": -75.0307, "zip": "08002", "region": "south"},
    
    # Additional notable towns
    "hoboken": {"lat": 40.7439, "lng": -74.0324, "zip": "07030", "region": "north"},
    "union city": {"lat": 40.6976, "lng": -74.0238, "zip": "07087", "region": "north"},
    "bayonne": {"lat": 40.6687, "lng": -74.1143, "zip": "07002", "region": "north"},
    "morristown": {"lat": 40.7968, "lng": -74.4815, "zip": "07960", "region": "north"},
    "hackensack": {"lat": 40.8859, "lng": -74.0435, "zip": "07601", "region": "north"},
    "fort lee": {"lat": 40.8509, "lng": -73.9701, "zip": "07024", "region": "north"},
    "summit": {"lat": 40.7167, "lng": -74.3648, "zip": "07901", "region": "north"},
    "westfield": {"lat": 40.6587, "lng": -74.3471, "zip": "07090", "region": "central"},
    "scotch plains": {"lat": 40.6462, "lng": -74.3832, "zip": "07076", "region": "central"},
    "fanwood": {"lat": 40.6412, "lng": -74.3826, "zip": "07023", "region": "central"},
    "rahway": {"lat": 40.6081, "lng": -74.2771, "zip": "07065", "region": "central"},
    "linden": {"lat": 40.6220, "lng": -74.2446, "zip": "07036", "region": "central"},
    "roselle": {"lat": 40.6518, "lng": -74.2613, "zip": "07203", "region": "central"},
    "carteret": {"lat": 40.5771, "lng": -74.2282, "zip": "07008", "region": "central"},
    "sayreville": {"lat": 40.4593, "lng": -74.3609, "zip": "08872", "region": "central"},
}

# Normalize city names (handle variations)
CITY_ALIASES = {
    "n. brunswick": "new brunswick",
    "nb": "new brunswick",
    "n brunswick": "new brunswick",
    "s. plainfield": "south plainfield",
    "n. plainfield": "north plainfield",
    "hpk": "highland park",
    "jc": "jersey city",
    "ac": "atlantic city",
}

def get_city_location(city_name):
    """
    Get coordinates and ZIP for a city name (case-insensitive)
    
    Args:
        city_name: City name string
        
    Returns:
        dict with lat, lng, zip, region or None if not found
    """
    city = city_name.lower().strip()
    
    # Check aliases first
    if city in CITY_ALIASES:
        city = CITY_ALIASES[city]
    
    return NJ_CITIES.get(city)

def extract_nj_cities_from_text(text):
    """
    Extract all NJ city mentions from text
    
    Args:
        text: String to search
        
    Returns:
        List of tuples (city_name, location_dict)
    """
    text_lower = text.lower()
    found_cities = []
    
    for city_name, location in NJ_CITIES.items():
        if city_name in text_lower:
            found_cities.append((city_name, location))
    
    # Check aliases
    for alias, real_name in CITY_ALIASES.items():
        if alias in text_lower and real_name not in [c[0] for c in found_cities]:
            location = NJ_CITIES.get(real_name)
            if location:
                found_cities.append((real_name, location))
    
    return found_cities
