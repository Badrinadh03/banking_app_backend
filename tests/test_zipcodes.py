def test_lookup_zip_requires_auth(client):
    response = client.get("/zipcodes/90210")
    assert response.status_code == 401


def test_lookup_zip_found(client, auth_headers):
    headers = auth_headers(email="zipfound@example.com")
    response = client.get("/zipcodes/90210", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["city"] == "Testville"
    assert body["state_abbreviation"] == "TS"


def test_lookup_zip_not_found(client, auth_headers, monkeypatch):
    from app.services import zipcode_service

    # Create the fixture user (which itself validates a zip at signup)
    # before stubbing lookups to always fail — the stub is only meant to
    # affect the /zipcodes GET request this test actually exercises.
    headers = auth_headers(email="zipnotfound@example.com")
    monkeypatch.setattr(
        zipcode_service,
        "lookup_zip_code",
        lambda zip_code: {"service_available": True, "found": False},
    )
    response = client.get("/zipcodes/00000", headers=headers)
    assert response.status_code == 200
    assert response.json()["valid"] is False


def test_lookup_zip_service_unavailable_does_not_block(client, auth_headers, monkeypatch):
    from app.services import zipcode_service

    monkeypatch.setattr(
        zipcode_service,
        "lookup_zip_code",
        lambda zip_code: {"service_available": False, "found": False},
    )

    headers = auth_headers(email="zipserviceoutage@example.com")
    response = client.get("/zipcodes/90210", headers=headers)
    assert response.status_code == 200
    assert response.json()["valid"] is True
