def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def _seed_balance(db_session, account_id: int, amount: str):
    from decimal import Decimal

    from app.models.account import Account

    account = db_session.get(Account, account_id)
    account.balance = Decimal(amount)
    db_session.commit()


def test_create_savings_goal(client, auth_headers):
    headers = auth_headers(email="goalcreate@example.com")
    account = _create_account(client, headers, "savings")

    response = client.post(
        "/savings-goals",
        json={"account_id": account["id"], "name": "Emergency fund", "target_amount": "1000.00"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Emergency fund"
    assert float(body["current_balance"]) == 0.0
    assert body["percent_complete"] == 0.0


def test_savings_goal_progress_reflects_real_balance(client, auth_headers, db_session):
    headers = auth_headers(email="goalprogress@example.com")
    account = _create_account(client, headers, "savings")
    _seed_balance(db_session, account["id"], "250.00")

    client.post(
        "/savings-goals",
        json={"account_id": account["id"], "name": "Vacation", "target_amount": "500.00"},
        headers=headers,
    )

    listed = client.get("/savings-goals", headers=headers).json()
    assert float(listed[0]["current_balance"]) == 250.0
    assert listed[0]["percent_complete"] == 50.0


def test_savings_goal_progress_caps_at_100_percent(client, auth_headers, db_session):
    headers = auth_headers(email="goalcap@example.com")
    account = _create_account(client, headers, "savings")
    _seed_balance(db_session, account["id"], "900.00")

    client.post(
        "/savings-goals",
        json={"account_id": account["id"], "name": "Overfunded", "target_amount": "500.00"},
        headers=headers,
    )

    listed = client.get("/savings-goals", headers=headers).json()
    assert listed[0]["percent_complete"] == 100.0


def test_delete_savings_goal(client, auth_headers):
    headers = auth_headers(email="goaldelete@example.com")
    account = _create_account(client, headers, "savings")
    created = client.post(
        "/savings-goals",
        json={"account_id": account["id"], "name": "Temp goal", "target_amount": "100.00"},
        headers=headers,
    ).json()

    response = client.delete(f"/savings-goals/{created['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get("/savings-goals", headers=headers).json() == []


def test_create_savings_goal_rejects_unowned_account(client, auth_headers):
    owner_headers = auth_headers(email="goalownera@example.com")
    other_headers = auth_headers(email="goalownerb@example.com")
    account = _create_account(client, owner_headers, "savings")

    response = client.post(
        "/savings-goals",
        json={"account_id": account["id"], "name": "Not mine", "target_amount": "100.00"},
        headers=other_headers,
    )
    assert response.status_code == 403
