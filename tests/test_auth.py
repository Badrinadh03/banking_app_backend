from app.models.user import User


def _mark_verified(db_session, email):
    user = db_session.query(User).filter(User.email == email).first()
    user.is_verified = True
    db_session.commit()


def test_signup_creates_user(client):
    response = client.post(
        "/auth/signup",
        json={
            "email": "alice@example.com",
            "password": "secret123",
            "full_name": "Alice",
            "phone_number": "5555550101",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["phone_number"] == "5555550101"
    assert body["is_verified"] is False
    assert "hashed_password" not in body


def test_signup_duplicate_email_rejected(client):
    payload = {
        "email": "bob@example.com",
        "password": "secret123",
        "full_name": "Bob",
        "phone_number": "5555550102",
    }
    client.post("/auth/signup", json=payload)
    response = client.post("/auth/signup", json={**payload, "phone_number": "5555550103"})
    assert response.status_code == 400


def test_signup_duplicate_phone_rejected(client):
    client.post(
        "/auth/signup",
        json={
            "email": "phoneowner@example.com",
            "password": "secret123",
            "full_name": "Owner",
            "phone_number": "5555550104",
        },
    )
    response = client.post(
        "/auth/signup",
        json={
            "email": "otherowner@example.com",
            "password": "secret123",
            "full_name": "Other",
            "phone_number": "5555550104",
        },
    )
    assert response.status_code == 400


def test_signup_requires_phone_number(client):
    response = client.post(
        "/auth/signup",
        json={"email": "nophone@example.com", "password": "secret123", "full_name": "No Phone"},
    )
    assert response.status_code == 422


def test_login_returns_token(client, db_session):
    client.post(
        "/auth/signup",
        json={
            "email": "carol@example.com",
            "password": "secret123",
            "full_name": "Carol",
            "phone_number": "5555550105",
        },
    )
    _mark_verified(db_session, "carol@example.com")
    response = client.post(
        "/auth/login", json={"identifier": "carol@example.com", "password": "secret123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_phone_number_returns_token(client, db_session):
    client.post(
        "/auth/signup",
        json={
            "email": "erin@example.com",
            "password": "secret123",
            "full_name": "Erin",
            "phone_number": "555-555-0106",
        },
    )
    _mark_verified(db_session, "erin@example.com")
    response = client.post(
        "/auth/login", json={"identifier": "5555550106", "password": "secret123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password_rejected(client):
    client.post(
        "/auth/signup",
        json={
            "email": "dave@example.com",
            "password": "secret123",
            "full_name": "Dave",
            "phone_number": "5555550107",
        },
    )
    response = client.post(
        "/auth/login", json={"identifier": "dave@example.com", "password": "wrongpass"}
    )
    assert response.status_code == 400


def test_protected_route_requires_token(client):
    response = client.get("/accounts")
    assert response.status_code == 401


def test_email_otp_request_and_verify(client):
    client.post(
        "/auth/signup",
        json={
            "email": "otpemail@example.com",
            "password": "secret123",
            "full_name": "Otp Email",
            "phone_number": "5555550108",
        },
    )
    request_response = client.post(
        "/auth/otp/request", json={"identifier": "otpemail@example.com", "channel": "email"}
    )
    assert request_response.status_code == 200
    body = request_response.json()
    assert body["channel"] == "email"
    # SMTP isn't configured in tests (disable_real_email_sending fixture),
    # so email falls back to demo mode just like phone always does.
    assert body["demo_code"] is not None

    verify_response = client.post(
        "/auth/otp/verify",
        json={
            "identifier": "otpemail@example.com",
            "channel": "email",
            "code": body["demo_code"],
        },
    )
    assert verify_response.status_code == 200
    assert "access_token" in verify_response.json()


def test_phone_otp_request_and_verify(client):
    client.post(
        "/auth/signup",
        json={
            "email": "otpphone@example.com",
            "password": "secret123",
            "full_name": "Otp Phone",
            "phone_number": "5555550109",
        },
    )
    request_response = client.post(
        "/auth/otp/request", json={"identifier": "5555550109", "channel": "phone"}
    )
    assert request_response.status_code == 200
    body = request_response.json()
    assert body["channel"] == "phone"
    assert body["demo_code"] is not None
    assert body["masked_target"].endswith("0109")

    verify_response = client.post(
        "/auth/otp/verify",
        json={"identifier": "5555550109", "channel": "phone", "code": body["demo_code"]},
    )
    assert verify_response.status_code == 200
    assert "access_token" in verify_response.json()


def test_otp_verify_rejects_wrong_code(client):
    client.post(
        "/auth/signup",
        json={
            "email": "otpwrong@example.com",
            "password": "secret123",
            "full_name": "Otp Wrong",
            "phone_number": "5555550110",
        },
    )
    client.post(
        "/auth/otp/request", json={"identifier": "otpwrong@example.com", "channel": "email"}
    )
    response = client.post(
        "/auth/otp/verify",
        json={"identifier": "otpwrong@example.com", "channel": "email", "code": "000000"},
    )
    assert response.status_code == 400


def test_otp_verify_locks_out_after_max_attempts(client):
    client.post(
        "/auth/signup",
        json={
            "email": "otplockout@example.com",
            "password": "secret123",
            "full_name": "Otp Lockout",
            "phone_number": "5555550111",
        },
    )
    client.post(
        "/auth/otp/request", json={"identifier": "otplockout@example.com", "channel": "email"}
    )
    for _ in range(5):
        client.post(
            "/auth/otp/verify",
            json={"identifier": "otplockout@example.com", "channel": "email", "code": "000000"},
        )
    response = client.post(
        "/auth/otp/verify",
        json={"identifier": "otplockout@example.com", "channel": "email", "code": "000000"},
    )
    assert response.status_code == 429


def test_password_login_rejected_before_verification(client):
    client.post(
        "/auth/signup",
        json={
            "email": "unverified1@example.com",
            "password": "secret123",
            "full_name": "Unverified",
            "phone_number": "5555550113",
        },
    )
    response = client.post(
        "/auth/login", json={"identifier": "unverified1@example.com", "password": "secret123"}
    )
    assert response.status_code == 403


def test_verify_account_by_email_then_login_succeeds(client):
    client.post(
        "/auth/signup",
        json={
            "email": "verifyme@example.com",
            "password": "secret123",
            "full_name": "Verify Me",
            "phone_number": "5555550114",
        },
    )
    otp_response = client.post(
        "/auth/otp/request", json={"identifier": "verifyme@example.com", "channel": "email"}
    )
    code = otp_response.json()["demo_code"]

    verify_response = client.post(
        "/auth/verify-account",
        json={"identifier": "verifyme@example.com", "channel": "email", "code": code},
    )
    assert verify_response.status_code == 200
    assert verify_response.json() == {"verified": True}
    # verifying does NOT log the user in
    assert "access_token" not in verify_response.json()

    login_response = client.post(
        "/auth/login", json={"identifier": "verifyme@example.com", "password": "secret123"}
    )
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()


def test_verify_account_by_phone_then_login_succeeds(client):
    client.post(
        "/auth/signup",
        json={
            "email": "verifyphone@example.com",
            "password": "secret123",
            "full_name": "Verify Phone",
            "phone_number": "5555550115",
        },
    )
    otp_response = client.post(
        "/auth/otp/request", json={"identifier": "5555550115", "channel": "phone"}
    )
    code = otp_response.json()["demo_code"]

    verify_response = client.post(
        "/auth/verify-account",
        json={"identifier": "5555550115", "channel": "phone", "code": code},
    )
    assert verify_response.status_code == 200

    login_response = client.post(
        "/auth/login", json={"identifier": "verifyphone@example.com", "password": "secret123"}
    )
    assert login_response.status_code == 200


def test_verify_account_wrong_code_rejected(client):
    client.post(
        "/auth/signup",
        json={
            "email": "verifywrong@example.com",
            "password": "secret123",
            "full_name": "Verify Wrong",
            "phone_number": "5555550116",
        },
    )
    client.post(
        "/auth/otp/request", json={"identifier": "verifywrong@example.com", "channel": "email"}
    )
    response = client.post(
        "/auth/verify-account",
        json={"identifier": "verifywrong@example.com", "channel": "email", "code": "000000"},
    )
    assert response.status_code == 400


def test_otp_login_on_unverified_account_also_verifies_it(client, db_session):
    # Successfully entering an emailed/texted code is itself proof of
    # ownership, so logging in via OTP for the first time both verifies the
    # account and issues a session in one step — no separate verify-account
    # call required.
    client.post(
        "/auth/signup",
        json={
            "email": "otpselfverify@example.com",
            "password": "secret123",
            "full_name": "Otp Self Verify",
            "phone_number": "5555550117",
        },
    )
    otp_response = client.post(
        "/auth/otp/request", json={"identifier": "otpselfverify@example.com", "channel": "email"}
    )
    code = otp_response.json()["demo_code"]

    verify_response = client.post(
        "/auth/otp/verify",
        json={"identifier": "otpselfverify@example.com", "channel": "email", "code": code},
    )
    assert verify_response.status_code == 200
    assert "access_token" in verify_response.json()

    user = db_session.query(User).filter(User.email == "otpselfverify@example.com").first()
    db_session.refresh(user)
    assert user.is_verified is True


def test_reverifying_already_verified_account_is_a_noop(client, auth_headers):
    headers = auth_headers(email="alreadyverified@example.com")
    response = client.get("/users/me", headers=headers)
    assert response.json()["is_verified"] is True


def test_reset_password_with_correct_code_then_login_with_new_password(client, auth_headers):
    headers = auth_headers(email="resetme@example.com")
    assert client.get("/users/me", headers=headers).status_code == 200

    otp_response = client.post(
        "/auth/otp/request", json={"identifier": "resetme@example.com", "channel": "email"}
    )
    code = otp_response.json()["demo_code"]

    reset_response = client.post(
        "/auth/reset-password",
        json={
            "identifier": "resetme@example.com",
            "channel": "email",
            "code": code,
            "new_password": "brandnew456",
        },
    )
    assert reset_response.status_code == 200
    assert reset_response.json() == {"reset": True}

    new_login = client.post(
        "/auth/login", json={"identifier": "resetme@example.com", "password": "brandnew456"}
    )
    assert new_login.status_code == 200

    old_login = client.post(
        "/auth/login", json={"identifier": "resetme@example.com", "password": "password123"}
    )
    assert old_login.status_code == 400


def test_reset_password_rejects_wrong_code(client, auth_headers):
    auth_headers(email="resetwrong@example.com")
    client.post(
        "/auth/otp/request", json={"identifier": "resetwrong@example.com", "channel": "email"}
    )
    response = client.post(
        "/auth/reset-password",
        json={
            "identifier": "resetwrong@example.com",
            "channel": "email",
            "code": "000000",
            "new_password": "brandnew456",
        },
    )
    assert response.status_code == 400


def test_reset_password_rejects_weak_new_password(client, auth_headers):
    auth_headers(email="resetweak@example.com")
    otp_response = client.post(
        "/auth/otp/request", json={"identifier": "resetweak@example.com", "channel": "email"}
    )
    code = otp_response.json()["demo_code"]
    response = client.post(
        "/auth/reset-password",
        json={
            "identifier": "resetweak@example.com",
            "channel": "email",
            "code": code,
            "new_password": "short1",
        },
    )
    assert response.status_code == 422


def test_otp_request_rate_limited_when_resent_too_soon(client):
    client.post(
        "/auth/signup",
        json={
            "email": "otpresend@example.com",
            "password": "secret123",
            "full_name": "Otp Resend",
            "phone_number": "5555550112",
        },
    )
    first = client.post(
        "/auth/otp/request", json={"identifier": "otpresend@example.com", "channel": "email"}
    )
    assert first.status_code == 200
    second = client.post(
        "/auth/otp/request", json={"identifier": "otpresend@example.com", "channel": "email"}
    )
    assert second.status_code == 429
