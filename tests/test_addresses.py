def test_search_addresses_requires_auth(client):
    response = client.get("/addresses/search", params={"q": "1 Infinite Loop"})
    assert response.status_code == 401


def test_search_addresses_returns_results(client, auth_headers):
    headers = auth_headers(email="addrfound@example.com")
    response = client.get("/addresses/search", params={"q": "1 Infinite Loop"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["service_available"] is True
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["street"] == "1 Infinite Loop"
    assert result["city"] == "Testville"
    assert result["state_abbreviation"] == "TS"
    assert result["zip_code"] == "00000"


def test_search_addresses_short_query_returns_no_results(client, auth_headers):
    headers = auth_headers(email="addrshort@example.com")
    response = client.get("/addresses/search", params={"q": "12"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["service_available"] is True
    assert body["results"] == []


def test_search_addresses_service_unavailable_does_not_error(client, auth_headers, monkeypatch):
    from app.services import address_service

    monkeypatch.setattr(
        address_service,
        "search_addresses",
        lambda query, limit=5: {"service_available": False, "results": []},
    )

    headers = auth_headers(email="addroutage@example.com")
    response = client.get("/addresses/search", params={"q": "1 Infinite Loop"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["service_available"] is False
    assert body["results"] == []
