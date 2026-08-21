def _open_checking_account(client, headers) -> int:
    response = client.post("/accounts", json={"account_type": "checking"}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def test_list_cards_requires_auth(client):
    response = client.get("/cards")
    assert response.status_code == 401


def test_issue_card_requires_otp_code(client, auth_headers):
    headers = auth_headers()
    account_id = _open_checking_account(client, headers)
    response = client.post("/cards", json={"account_id": account_id}, headers=headers)
    assert response.status_code == 422  # otp_code is required by the schema


def test_issue_card_rejects_wrong_otp_code(client, auth_headers, get_otp_code):
    headers = auth_headers()
    account_id = _open_checking_account(client, headers)
    get_otp_code("user@example.com")
    response = client.post(
        "/cards",
        json={"account_id": account_id, "otp_code": "000000"},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect code"


def test_issue_card_succeeds_with_valid_otp_code(client, auth_headers, get_otp_code):
    headers = auth_headers()
    account_id = _open_checking_account(client, headers)
    code = get_otp_code("user@example.com")
    response = client.post(
        "/cards",
        json={"account_id": account_id, "otp_code": code},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["account_id"] == account_id
    assert len(body["last4"]) == 4
    assert body["status"] == "active"
    assert body["apple_wallet_linked"] is False
    assert body["google_wallet_linked"] is False
    # the full card number/CVV must never appear in the issue response
    assert "card_number" not in body
    assert "cvv" not in body


def test_issue_card_rejects_a_second_card_for_the_same_account(client, auth_headers, get_otp_code):
    headers = auth_headers()
    account_id = _open_checking_account(client, headers)
    code = get_otp_code("user@example.com")
    client.post("/cards", json={"account_id": account_id, "otp_code": code}, headers=headers)

    # A second code via the same channel this soon would hit the resend
    # cooldown — use phone instead, unrelated to what's under test here.
    code2 = get_otp_code("user@example.com", channel="phone")
    response = client.post(
        "/cards",
        json={"account_id": account_id, "otp_code": code2, "otp_channel": "phone"},
        headers=headers,
    )
    assert response.status_code == 400
    assert "already has a debit card" in response.json()["detail"].lower()


def test_issue_card_rejects_account_owned_by_another_user(client, auth_headers, get_otp_code):
    headers = auth_headers()
    other_headers = auth_headers(email="cardowner2@example.com")
    other_account_id = _open_checking_account(client, other_headers)
    code = get_otp_code("user@example.com")
    response = client.post(
        "/cards", json={"account_id": other_account_id, "otp_code": code}, headers=headers
    )
    assert response.status_code == 403


def test_issue_card_for_savings_account_succeeds(client, auth_headers, get_otp_code):
    headers = auth_headers()
    response = client.post("/accounts", json={"account_type": "savings"}, headers=headers)
    account_id = response.json()["id"]
    code = get_otp_code("user@example.com")
    response = client.post(
        "/cards", json={"account_id": account_id, "otp_code": code}, headers=headers
    )
    assert response.status_code == 201


def test_reveal_card_requires_otp_and_returns_full_number(client, auth_headers, get_otp_code):
    headers = auth_headers()
    account_id = _open_checking_account(client, headers)
    code = get_otp_code("user@example.com")
    card = client.post(
        "/cards", json={"account_id": account_id, "otp_code": code}, headers=headers
    ).json()

    reveal_code = get_otp_code("user@example.com", channel="phone")
    response = client.post(
        f"/cards/{card['id']}/reveal",
        json={"otp_code": reveal_code, "otp_channel": "phone"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["card_number"]) == 16
    assert body["card_number"].endswith(card["last4"])
    assert len(body["cvv"]) == 3


def test_reveal_card_rejects_wrong_otp_code(client, auth_headers, get_otp_code):
    headers = auth_headers()
    account_id = _open_checking_account(client, headers)
    code = get_otp_code("user@example.com")
    card = client.post(
        "/cards", json={"account_id": account_id, "otp_code": code}, headers=headers
    ).json()

    get_otp_code("user@example.com", channel="phone")
    response = client.post(
        f"/cards/{card['id']}/reveal",
        json={"otp_code": "000000", "otp_channel": "phone"},
        headers=headers,
    )
    assert response.status_code == 400


def test_freeze_and_unfreeze_card_does_not_require_otp(client, auth_headers, get_otp_code):
    headers = auth_headers()
    account_id = _open_checking_account(client, headers)
    code = get_otp_code("user@example.com")
    card = client.post(
        "/cards", json={"account_id": account_id, "otp_code": code}, headers=headers
    ).json()

    response = client.post(f"/cards/{card['id']}/freeze", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "frozen"

    response = client.post(f"/cards/{card['id']}/unfreeze", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_link_wallet_marks_card_linked(client, auth_headers, get_otp_code):
    headers = auth_headers()
    account_id = _open_checking_account(client, headers)
    code = get_otp_code("user@example.com")
    card = client.post(
        "/cards", json={"account_id": account_id, "otp_code": code}, headers=headers
    ).json()

    response = client.post(
        f"/cards/{card['id']}/wallet", json={"provider": "apple"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["apple_wallet_linked"] is True

    response = client.post(
        f"/cards/{card['id']}/wallet", json={"provider": "google"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["google_wallet_linked"] is True


def test_link_wallet_rejected_while_frozen(client, auth_headers, get_otp_code):
    headers = auth_headers()
    account_id = _open_checking_account(client, headers)
    code = get_otp_code("user@example.com")
    card = client.post(
        "/cards", json={"account_id": account_id, "otp_code": code}, headers=headers
    ).json()
    client.post(f"/cards/{card['id']}/freeze", headers=headers)

    response = client.post(
        f"/cards/{card['id']}/wallet", json={"provider": "apple"}, headers=headers
    )
    assert response.status_code == 400


def test_list_cards_only_returns_current_users_cards(client, auth_headers, get_otp_code):
    headers_a = auth_headers(email="carduser_a@example.com")
    account_a = _open_checking_account(client, headers_a)
    code_a = get_otp_code("carduser_a@example.com")
    client.post("/cards", json={"account_id": account_a, "otp_code": code_a}, headers=headers_a)

    headers_b = auth_headers(email="carduser_b@example.com")
    response = client.get("/cards", headers=headers_b)
    assert response.status_code == 200
    assert response.json() == []

    response = client.get("/cards", headers=headers_a)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_reveal_card_requires_ownership(client, auth_headers, get_otp_code):
    headers_a = auth_headers(email="cardowner_a@example.com")
    account_a = _open_checking_account(client, headers_a)
    code_a = get_otp_code("cardowner_a@example.com")
    card = client.post(
        "/cards", json={"account_id": account_a, "otp_code": code_a}, headers=headers_a
    ).json()

    headers_b = auth_headers(email="cardowner_b@example.com")
    code_b = get_otp_code("cardowner_b@example.com")
    response = client.post(
        f"/cards/{card['id']}/reveal", json={"otp_code": code_b}, headers=headers_b
    )
    assert response.status_code == 403
