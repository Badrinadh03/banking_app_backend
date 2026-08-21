import httpx

ZIPPOTAM_BASE_URL = "https://api.zippopotam.us/us"


def lookup_zip_code(zip_code: str) -> dict:
    """Looks up a US zip code against a real, free, public lookup service.

    Returns `service_available=False` on any network/timeout issue — a
    lookup failure should never block the user, only an explicit "this zip
    doesn't exist" response should. ZIP+4 codes are looked up by their base
    5 digits, since the extended 4 digits are a delivery-route detail the
    lookup service doesn't index.
    """
    base_zip = zip_code.split("-")[0]
    try:
        response = httpx.get(f"{ZIPPOTAM_BASE_URL}/{base_zip}", timeout=5.0)
    except httpx.HTTPError:
        return {"service_available": False, "found": False}

    if response.status_code == 404:
        return {"service_available": True, "found": False}
    if response.status_code != 200:
        return {"service_available": False, "found": False}

    data = response.json()
    place = data["places"][0]
    return {
        "service_available": True,
        "found": True,
        "zip_code": base_zip,
        "city": place["place name"],
        "state": place["state"],
        "state_abbreviation": place["state abbreviation"],
    }
