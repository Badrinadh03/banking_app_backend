from app.constants import BANK_ROUTING_NUMBER_ELECTRONIC
from app.models.account import Account


def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def _seed_balance(db_session, account_id: int, amount: str):
    from decimal import Decimal

    account = db_session.get(Account, account_id)
    account.balance = Decimal(amount)
    db_session.commit()


def test_external_transfer_debits_source_account(client, auth_headers, db_session, get_otp_code):
    headers = auth_headers(email="ext1@example.com")
    account = _create_account(client, headers)
    _seed_balance(db_session, account["id"], "200.00")

    response = client.post(
        "/transfers/external",
        json={
            "from_account_id": account["id"],
            "amount": "75.00",
            "recipient_name": "Jane Doe",
            "external_account_number": "1234567890",
            "external_routing_number": "021000021",
            "external_bank_name": "Other Bank",
            "description": "Rent",
            "otp_code": get_otp_code("ext1@example.com"),
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["transaction_type"] == "external_transfer"
    assert body["to_account_id"] is None
    assert body["external_recipient_name"] == "Jane Doe"
    assert body["external_account_number"] == "1234567890"
    assert body["external_routing_number"] == "021000021"

    account_after = client.get(f"/accounts/{account['id']}", headers=headers).json()
    assert float(account_after["balance"]) == 125.0


def test_external_transfer_insufficient_funds_rejected(client, auth_headers, get_otp_code):
    headers = auth_headers(email="ext2@example.com")
    account = _create_account(client, headers)

    response = client.post(
        "/transfers/external",
        json={
            "from_account_id": account["id"],
            "amount": "50.00",
            "recipient_name": "Jane Doe",
            "external_account_number": "1234567890",
            "external_routing_number": "021000021",
            "otp_code": get_otp_code("ext2@example.com"),
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_external_transfer_rejects_invalid_routing_number(client, auth_headers):
    headers = auth_headers(email="ext3@example.com")
    account = _create_account(client, headers)

    response = client.post(
        "/transfers/external",
        json={
            "from_account_id": account["id"],
            "amount": "10.00",
            "recipient_name": "Jane Doe",
            "external_account_number": "1234567890",
            "external_routing_number": "abc123456",
            "otp_code": "000000",
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_external_transfer_rejects_wrong_otp_code(client, auth_headers, db_session):
    headers = auth_headers(email="extwrongotp@example.com")
    account = _create_account(client, headers)
    _seed_balance(db_session, account["id"], "200.00")

    response = client.post(
        "/transfers/external",
        json={
            "from_account_id": account["id"],
            "amount": "10.00",
            "recipient_name": "Jane Doe",
            "external_account_number": "1234567890",
            "external_routing_number": "021000021",
            "otp_code": "000000",
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_external_transfer_requires_ownership(client, auth_headers, db_session, get_otp_code):
    headers_a = auth_headers(email="ext4a@example.com")
    headers_b = auth_headers(email="ext4b@example.com")
    account_a = _create_account(client, headers_a)
    _seed_balance(db_session, account_a["id"], "100.00")

    response = client.post(
        "/transfers/external",
        json={
            "from_account_id": account_a["id"],
            "amount": "10.00",
            "recipient_name": "Jane Doe",
            "external_account_number": "1234567890",
            "external_routing_number": "021000021",
            "otp_code": get_otp_code("ext4b@example.com"),
        },
        headers=headers_b,
    )
    assert response.status_code == 403


def test_external_transfer_credits_matching_account_at_same_bank(
    client, auth_headers, db_session, get_otp_code
):
    sender_headers = auth_headers(email="samebank_sender@example.com")
    recipient_headers = auth_headers(email="samebank_recipient@example.com")

    sender_account = _create_account(client, sender_headers)
    recipient_account = _create_account(client, recipient_headers)
    _seed_balance(db_session, sender_account["id"], "300.00")

    response = client.post(
        "/transfers/external",
        json={
            "from_account_id": sender_account["id"],
            "amount": "50.00",
            "recipient_name": "Recipient Person",
            "external_account_number": recipient_account["account_number"],
            "external_routing_number": BANK_ROUTING_NUMBER_ELECTRONIC,
            "otp_code": get_otp_code("samebank_sender@example.com"),
        },
        headers=sender_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["to_account_id"] == recipient_account["id"]

    sender_after = client.get(f"/accounts/{sender_account['id']}", headers=sender_headers).json()
    recipient_after = client.get(
        f"/accounts/{recipient_account['id']}", headers=recipient_headers
    ).json()
    assert float(sender_after["balance"]) == 250.0
    assert float(recipient_after["balance"]) == 50.0

    # recipient should have their own "received" notification (email + sms,
    # since every test user now has a phone number on file from signup)
    recipient_notifications = client.get("/notifications", headers=recipient_headers).json()
    assert len(recipient_notifications) == 2
    assert "received" in recipient_notifications[0]["message"].lower()

    # transaction should now show up in the recipient's own account history
    recipient_history = client.get(
        f"/accounts/{recipient_account['id']}/transactions", headers=recipient_headers
    ).json()
    assert len(recipient_history) == 1


def test_external_transfer_same_bank_but_unknown_account_stays_simulated(
    client, auth_headers, db_session, get_otp_code
):
    headers = auth_headers(email="samebank_unknown@example.com")
    account = _create_account(client, headers)
    _seed_balance(db_session, account["id"], "100.00")

    response = client.post(
        "/transfers/external",
        json={
            "from_account_id": account["id"],
            "amount": "10.00",
            "recipient_name": "Nobody",
            "external_account_number": "9999999999",
            "external_routing_number": BANK_ROUTING_NUMBER_ELECTRONIC,
            "otp_code": get_otp_code("samebank_unknown@example.com"),
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["to_account_id"] is None


def test_external_transfer_to_own_other_account_credits_it(
    client, auth_headers, db_session, get_otp_code
):
    headers = auth_headers(email="samebank_self@example.com")
    account_a = _create_account(client, headers, "checking")
    account_b = _create_account(client, headers, "savings")
    _seed_balance(db_session, account_a["id"], "100.00")

    response = client.post(
        "/transfers/external",
        json={
            "from_account_id": account_a["id"],
            "amount": "25.00",
            "recipient_name": "Myself",
            "external_account_number": account_b["account_number"],
            "external_routing_number": BANK_ROUTING_NUMBER_ELECTRONIC,
            "otp_code": get_otp_code("samebank_self@example.com"),
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["to_account_id"] == account_b["id"]

    account_b_after = client.get(f"/accounts/{account_b['id']}", headers=headers).json()
    assert float(account_b_after["balance"]) == 25.0


def test_notifications_created_on_deposit(client, auth_headers):
    headers = auth_headers(email="notif1@example.com")
    account = _create_account(client, headers)
    client.post(f"/accounts/{account['id']}/deposit", json={"amount": "50.00"}, headers=headers)

    response = client.get("/notifications", headers=headers)
    assert response.status_code == 200
    body = response.json()
    # email + sms, since every test user now has a phone number on file from signup
    assert len(body) == 2
    channels = {n["channel"] for n in body}
    assert channels == {"email", "sms"}
    assert all("deposit of $50.00" in n["message"] for n in body)


def test_notification_email_simulated_when_smtp_not_configured(client, auth_headers):
    headers = auth_headers(email="notif_smtp@example.com")
    account = _create_account(client, headers)
    client.post(f"/accounts/{account['id']}/deposit", json={"amount": "10.00"}, headers=headers)

    response = client.get("/notifications", headers=headers)
    body = response.json()[0]
    assert body["delivered"] is False
    assert body["delivery_error"] is None


def test_notifications_created_for_both_channels_when_phone_set(client, auth_headers):
    headers = auth_headers(email="notif2@example.com")
    client.patch("/users/me", json={"phone_number": "+15551234567"}, headers=headers)
    account = _create_account(client, headers)
    client.post(f"/accounts/{account['id']}/deposit", json={"amount": "20.00"}, headers=headers)

    response = client.get("/notifications", headers=headers)
    channels = {n["channel"] for n in response.json()}
    assert channels == {"email", "sms"}


def test_notifications_include_account_and_routing_numbers(
    client, auth_headers, db_session, get_otp_code
):
    headers = auth_headers(email="notif3@example.com")
    account = _create_account(client, headers)
    _seed_balance(db_session, account["id"], "100.00")

    client.post(
        "/transfers/external",
        json={
            "from_account_id": account["id"],
            "amount": "30.00",
            "recipient_name": "Jane Doe",
            "external_account_number": "1234567890",
            "external_routing_number": "021000021",
            "otp_code": get_otp_code("notif3@example.com"),
        },
        headers=headers,
    )

    response = client.get("/notifications", headers=headers)
    message = response.json()[0]["message"]
    assert "routing" in message.lower()
    assert account["account_number"][-4:] in message
    assert "7890" in message  # last 4 of external account number
    assert "021000021" in message


def test_notifications_require_auth(client):
    assert client.get("/notifications").status_code == 401
