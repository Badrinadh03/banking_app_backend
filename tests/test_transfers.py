def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def _seed_balance(db_session, account_id: int, amount: str):
    from decimal import Decimal

    from app.models.account import Account

    account = db_session.get(Account, account_id)
    account.balance = Decimal(amount)
    db_session.commit()


def test_successful_transfer_updates_balances(client, auth_headers, db_session):
    headers = auth_headers()
    source = _create_account(client, headers)
    dest = _create_account(client, headers)
    _seed_balance(db_session, source["id"], "100.00")

    response = client.post(
        "/transfers",
        json={
            "from_account_id": source["id"],
            "to_account_id": dest["id"],
            "amount": "40.00",
            "description": "test transfer",
        },
        headers=headers,
    )
    assert response.status_code == 201

    source_after = client.get(f"/accounts/{source['id']}", headers=headers).json()
    dest_after = client.get(f"/accounts/{dest['id']}", headers=headers).json()
    assert float(source_after["balance"]) == 60.0
    assert float(dest_after["balance"]) == 40.0


def test_transfer_insufficient_funds_rejected(client, auth_headers):
    headers = auth_headers()
    source = _create_account(client, headers)
    dest = _create_account(client, headers)

    response = client.post(
        "/transfers",
        json={"from_account_id": source["id"], "to_account_id": dest["id"], "amount": "50.00"},
        headers=headers,
    )
    assert response.status_code == 400


def test_transfer_from_unowned_account_rejected(client, auth_headers, db_session):
    headers_a = auth_headers(email="a@example.com")
    headers_b = auth_headers(email="b@example.com")
    account_a = _create_account(client, headers_a)
    account_b = _create_account(client, headers_b)
    _seed_balance(db_session, account_a["id"], "100.00")

    response = client.post(
        "/transfers",
        json={"from_account_id": account_a["id"], "to_account_id": account_b["id"], "amount": "10.00"},
        headers=headers_b,
    )
    assert response.status_code == 403


def test_transfer_history_appears_for_both_accounts(client, auth_headers, db_session):
    headers = auth_headers()
    source = _create_account(client, headers)
    dest = _create_account(client, headers)
    _seed_balance(db_session, source["id"], "100.00")

    client.post(
        "/transfers",
        json={"from_account_id": source["id"], "to_account_id": dest["id"], "amount": "25.00"},
        headers=headers,
    )

    source_history = client.get(f"/accounts/{source['id']}/transactions", headers=headers).json()
    dest_history = client.get(f"/accounts/{dest['id']}/transactions", headers=headers).json()
    assert len(source_history) == 1
    assert len(dest_history) == 1
