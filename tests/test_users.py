def test_get_me_returns_profile(client, auth_headers):
    headers = auth_headers()
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    # phone number is now required at signup, so it's always set
    assert body["phone_number"] is not None
    # auth_headers gives fixture users a complete profile (address +
    # government ID) so account-opening tests elsewhere don't need to care
    assert body["address"] is not None
    assert body["government_id_last4"] is not None


def test_update_profile_sets_phone_and_address(client, auth_headers):
    headers = auth_headers()
    response = client.patch(
        "/users/me",
        json={"phone_number": "+1-555-123-4567", "address": "123 Main St, Springfield"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    # phone numbers are normalized (formatting stripped) on write
    assert body["phone_number"] == "+15551234567"
    assert body["address"] == "123 Main St, Springfield"


def test_update_profile_partial_update_preserves_other_fields(client, auth_headers):
    headers = auth_headers()
    client.patch("/users/me", json={"phone_number": "+1-555-000-0000"}, headers=headers)
    response = client.patch("/users/me", json={"address": "456 Oak Ave"}, headers=headers)
    body = response.json()
    assert body["phone_number"] == "+15550000000"
    assert body["address"] == "456 Oak Ave"


def test_update_profile_requires_auth(client):
    response = client.patch("/users/me", json={"address": "789 Elm St"})
    assert response.status_code == 401


def test_update_profile_rejects_zip_that_does_not_exist(client, auth_headers, monkeypatch):
    from app.services import zipcode_service

    # Create the fixture user (which itself validates a zip at signup)
    # before stubbing lookups to always fail — the stub is only meant to
    # affect the profile-update request this test actually exercises.
    headers = auth_headers()
    monkeypatch.setattr(
        zipcode_service,
        "lookup_zip_code",
        lambda zip_code: {"service_available": True, "found": False},
    )
    response = client.patch(
        "/users/me",
        json={"address": "1 Nowhere Ave, 00000", "zip_code": "00000"},
        headers=headers,
    )
    assert response.status_code == 400
    assert "zip code" in response.json()["detail"].lower()


def test_update_profile_allowed_when_zip_lookup_service_unavailable(client, auth_headers, monkeypatch):
    from app.services import zipcode_service

    monkeypatch.setattr(
        zipcode_service,
        "lookup_zip_code",
        lambda zip_code: {"service_available": False, "found": False},
    )
    headers = auth_headers()
    response = client.patch(
        "/users/me",
        json={"address": "1 Somewhere Rd, 90210", "zip_code": "90210"},
        headers=headers,
    )
    assert response.status_code == 200


def test_update_profile_email_change_requires_otp_code(client, auth_headers):
    headers = auth_headers()
    response = client.patch("/users/me", json={"email": "new@example.com"}, headers=headers)
    assert response.status_code == 400
    assert "verification code" in response.json()["detail"].lower()


def test_update_profile_email_change_rejects_wrong_otp_code(client, auth_headers, get_otp_code):
    headers = auth_headers()
    get_otp_code("user@example.com")
    response = client.patch(
        "/users/me",
        json={"email": "new@example.com", "otp_code": "000000"},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect code"


def test_update_profile_email_change_succeeds_with_valid_otp_code(client, auth_headers, get_otp_code):
    headers = auth_headers()
    code = get_otp_code("user@example.com")
    response = client.patch(
        "/users/me",
        json={"email": "new@example.com", "otp_code": code},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["email"] == "new@example.com"


def test_update_profile_email_change_rejects_duplicate_email(client, auth_headers, get_otp_code):
    auth_headers(email="taken@example.com")
    headers = auth_headers(email="user@example.com")
    code = get_otp_code("user@example.com")
    response = client.patch(
        "/users/me",
        json={"email": "taken@example.com", "otp_code": code},
        headers=headers,
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_update_profile_resubmitting_same_email_does_not_require_otp(client, auth_headers):
    headers = auth_headers()
    response = client.patch("/users/me", json={"email": "user@example.com"}, headers=headers)
    assert response.status_code == 200


def test_update_profile_rejects_government_id_change_once_set(client, auth_headers):
    # auth_headers fixture users always start with government_id_last4="1234"
    headers = auth_headers(email="govidset@example.com")
    response = client.patch("/users/me", json={"government_id_last4": "9999"}, headers=headers)
    assert response.status_code == 400
    assert "can't be changed" in response.json()["detail"].lower()


def test_update_profile_allows_resubmitting_same_government_id(client, auth_headers):
    headers = auth_headers(email="govidsame@example.com")
    response = client.patch("/users/me", json={"government_id_last4": "1234"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["government_id_last4"] == "1234"


def test_update_profile_allows_setting_government_id_when_blank(client, auth_headers, db_session):
    from app.models.user import User

    headers = auth_headers(email="govidblank@example.com")
    user = db_session.query(User).filter(User.email == "govidblank@example.com").first()
    user.government_id_last4 = None
    db_session.commit()

    response = client.patch("/users/me", json={"government_id_last4": "9999"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["government_id_last4"] == "9999"
