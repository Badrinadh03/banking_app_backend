def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def _seed_balance(db_session, account_id: int, amount: str):
    from decimal import Decimal

    from app.models.account import Account

    account = db_session.get(Account, account_id)
    account.balance = Decimal(amount)
    db_session.commit()


def test_large_transaction_creates_fraud_alert(client, auth_headers, db_session):
    headers = auth_headers(email="fraudlarge@example.com")
    source = _create_account(client, headers)
    dest = _create_account(client, headers, "savings")
    _seed_balance(db_session, source["id"], "10000.00")

    response = client.post(
        "/transfers",
        json={"from_account_id": source["id"], "to_account_id": dest["id"], "amount": "2500.00"},
        headers=headers,
    )
    assert response.status_code == 201

    alerts = client.get("/fraud-alerts", headers=headers).json()
    assert any(a["rule"] == "large_transaction" for a in alerts)

    notifications = client.get("/notifications", headers=headers).json()
    assert any("Security alert" in n["message"] for n in notifications)


def test_small_transaction_does_not_create_fraud_alert(client, auth_headers, db_session):
    headers = auth_headers(email="fraudsmall@example.com")
    source = _create_account(client, headers)
    dest = _create_account(client, headers, "savings")
    _seed_balance(db_session, source["id"], "500.00")

    client.post(
        "/transfers",
        json={"from_account_id": source["id"], "to_account_id": dest["id"], "amount": "25.00"},
        headers=headers,
    )

    alerts = client.get("/fraud-alerts", headers=headers).json()
    assert alerts == []


def test_rapid_activity_creates_fraud_alert(client, auth_headers, db_session):
    headers = auth_headers(email="fraudrapid@example.com")
    source = _create_account(client, headers)
    dest = _create_account(client, headers, "savings")
    _seed_balance(db_session, source["id"], "1000.00")

    for _ in range(4):
        response = client.post(
            "/transfers",
            json={"from_account_id": source["id"], "to_account_id": dest["id"], "amount": "10.00"},
            headers=headers,
        )
        assert response.status_code == 201

    alerts = client.get("/fraud-alerts", headers=headers).json()
    assert any(a["rule"] == "rapid_activity" for a in alerts)


def test_acknowledge_fraud_alert(client, auth_headers, db_session):
    headers = auth_headers(email="fraudack@example.com")
    source = _create_account(client, headers)
    dest = _create_account(client, headers, "savings")
    _seed_balance(db_session, source["id"], "10000.00")

    client.post(
        "/transfers",
        json={"from_account_id": source["id"], "to_account_id": dest["id"], "amount": "2100.00"},
        headers=headers,
    )
    alert = client.get("/fraud-alerts", headers=headers).json()[0]
    assert alert["acknowledged"] is False

    response = client.post(f"/fraud-alerts/{alert['id']}/acknowledge", headers=headers)
    assert response.status_code == 200
    assert response.json()["acknowledged"] is True


def test_acknowledge_fraud_alert_rejects_non_owner(client, auth_headers, db_session):
    headers_a = auth_headers(email="fraudownera@example.com")
    headers_b = auth_headers(email="fraudownerb@example.com")
    source = _create_account(client, headers_a)
    dest = _create_account(client, headers_a, "savings")
    _seed_balance(db_session, source["id"], "10000.00")

    client.post(
        "/transfers",
        json={"from_account_id": source["id"], "to_account_id": dest["id"], "amount": "2200.00"},
        headers=headers_a,
    )
    alert = client.get("/fraud-alerts", headers=headers_a).json()[0]

    response = client.post(f"/fraud-alerts/{alert['id']}/acknowledge", headers=headers_b)
    assert response.status_code == 404
