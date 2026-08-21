import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires a descriptive User-Agent identifying the
# application — anonymous/browser-like User-Agents get blocked.
USER_AGENT = "NorthlineBank-PortfolioProject/1.0 (educational project, not a real bank)"
MIN_QUERY_LENGTH = 5

US_STATE_ABBREVIATIONS = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME",
    "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}


def search_addresses(query: str, limit: int = 5) -> dict:
    """Looks up candidate US street addresses against a real, free, public
    geocoding service (OpenStreetMap Nominatim). Mirrors zipcode_service's
    graceful-degradation shape: `service_available=False` on any
    network/timeout issue, never blocking the user from typing an address
    by hand instead.
    """
    query = query.strip()
    if len(query) < MIN_QUERY_LENGTH:
        return {"service_available": True, "results": []}

    try:
        response = httpx.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "jsonv2",
                "addressdetails": 1,
                "countrycodes": "us",
                "limit": limit,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=5.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return {"service_available": False, "results": []}

    results = []
    seen = set()
    for item in response.json():
        addr = item.get("address", {})
        road = addr.get("road")
        if not road:
            # Skip city/region-level matches — only street-level results
            # are useful for a profile address field.
            continue
        street = " ".join(part for part in [addr.get("house_number"), road] if part)
        city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet") or ""
        state = addr.get("state", "")
        zip_code = (addr.get("postcode") or "").split("-")[0]
        # Nominatim often returns several named points-of-interest sharing
        # the same building/street — collapse those into one suggestion.
        dedupe_key = (street, city, zip_code)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        results.append(
            {
                "display_name": item.get("display_name", street),
                "street": street,
                "city": city,
                "state": state,
                "state_abbreviation": US_STATE_ABBREVIATIONS.get(state, ""),
                "zip_code": zip_code,
            }
        )
    return {"service_available": True, "results": results}
