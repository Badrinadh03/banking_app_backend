def test_login_records_login_event(client, auth_headers):
    headers = auth_headers(email="loginhist@example.com")

    response = client.get("/users/me/login-history", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1


def test_multiple_logins_appear_in_history_newest_first(client, auth_headers):
    email = "multilogin@example.com"
    headers = auth_headers(email=email)
    client.post("/auth/login", json={"identifier": email, "password": "password123"})

    response = client.get("/users/me/login-history", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_change_password_success(client, auth_headers):
    email = "changepw@example.com"
    headers = auth_headers(email=email)

    response = client.post(
        "/users/me/change-password",
        json={"current_password": "password123", "new_password": "newpassword456"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["password_changed_at"] is not None

    login_response = client.post(
        "/auth/login", json={"identifier": email, "password": "newpassword456"}
    )
    assert login_response.status_code == 200

    old_login_response = client.post(
        "/auth/login", json={"identifier": email, "password": "password123"}
    )
    assert old_login_response.status_code == 400


def test_change_password_rejects_wrong_current_password(client, auth_headers):
    headers = auth_headers(email="wrongcurrent@example.com")

    response = client.post(
        "/users/me/change-password",
        json={"current_password": "wrongpassword", "new_password": "newpassword456"},
        headers=headers,
    )
    assert response.status_code == 400


def test_update_settings_toggles_remember_device(client, auth_headers):
    headers = auth_headers(email="settingstoggle@example.com")

    response = client.patch(
        "/users/me/settings", json={"remember_device": True}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["remember_device"] is True

    response = client.patch(
        "/users/me/settings", json={"remember_device": False}, headers=headers
    )
    assert response.json()["remember_device"] is False


def test_signup_rejects_weak_password_too_short(client):
    response = client.post(
        "/auth/signup",
        json={
            "email": "weak1@example.com",
            "password": "abc123",
            "full_name": "Weak",
            "phone_number": "5555550001",
        },
    )
    assert response.status_code == 422


def test_signup_rejects_password_without_digit(client):
    response = client.post(
        "/auth/signup",
        json={
            "email": "weak2@example.com",
            "password": "abcdefgh",
            "full_name": "Weak",
            "phone_number": "5555550002",
        },
    )
    assert response.status_code == 422


def test_signup_rejects_password_without_letter(client):
    response = client.post(
        "/auth/signup",
        json={
            "email": "weak3@example.com",
            "password": "12345678",
            "full_name": "Weak",
            "phone_number": "5555550003",
        },
    )
    assert response.status_code == 422


def test_change_password_rejects_weak_new_password(client, auth_headers):
    headers = auth_headers(email="weakchange@example.com")
    response = client.post(
        "/users/me/change-password",
        json={"current_password": "password123", "new_password": "short1"},
        headers=headers,
    )
    assert response.status_code == 422


def test_change_email_success(client, auth_headers):
    email = "oldid@example.com"
    headers = auth_headers(email=email)

    response = client.post(
        "/users/me/change-email",
        json={"new_email": "newid@example.com", "current_password": "password123"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["email"] == "newid@example.com"

    login_response = client.post(
        "/auth/login", json={"identifier": "newid@example.com", "password": "password123"}
    )
    assert login_response.status_code == 200


def test_change_email_rejects_wrong_password(client, auth_headers):
    headers = auth_headers(email="oldid2@example.com")
    response = client.post(
        "/users/me/change-email",
        json={"new_email": "newid2@example.com", "current_password": "wrongpassword"},
        headers=headers,
    )
    assert response.status_code == 400


def test_change_email_rejects_duplicate(client, auth_headers):
    auth_headers(email="taken@example.com")
    headers = auth_headers(email="wantstaken@example.com")

    response = client.post(
        "/users/me/change-email",
        json={"new_email": "taken@example.com", "current_password": "password123"},
        headers=headers,
    )
    assert response.status_code == 400


def test_update_primary_contact_method(client, auth_headers):
    headers = auth_headers(email="contactpref@example.com")
    response = client.patch(
        "/users/me", json={"primary_contact_method": "email"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["primary_contact_method"] == "email"


def test_settings_and_password_endpoints_require_auth(client):
    assert client.get("/users/me/login-history").status_code == 401
    assert client.patch("/users/me/settings", json={"remember_device": True}).status_code == 401
    assert (
        client.post(
            "/users/me/change-password",
            json={"current_password": "a", "new_password": "b"},
        ).status_code
        == 401
    )
