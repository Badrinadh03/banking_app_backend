def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def _seed_balance(db_session, account_id: int, amount: str):
    from decimal import Decimal

    from app.models.account import Account

    account = db_session.get(Account, account_id)
    account.balance = Decimal(amount)
    db_session.commit()


def test_close_account_at_zero_balance_succeeds(client, auth_headers):
    headers = auth_headers(email="closezero@example.com")
    account = _create_account(client, headers)

    response = client.post(f"/accounts/{account['id']}/close", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_close_account_rejects_nonzero_balance(client, auth_headers, db_session):
    headers = auth_headers(email="closenonzero@example.com")
    account = _create_account(client, headers)
    _seed_balance(db_session, account["id"], "25.00")

    response = client.post(f"/accounts/{account['id']}/close", headers=headers)
    assert response.status_code == 400


def test_close_account_rejects_non_owner(client, auth_headers):
    owner_headers = auth_headers(email="closeownera@example.com")
    other_headers = auth_headers(email="closeownerb@example.com")
    account = _create_account(client, owner_headers)

    response = client.post(f"/accounts/{account['id']}/close", headers=other_headers)
    assert response.status_code == 403


def test_close_account_rejects_already_closed(client, auth_headers):
    headers = auth_headers(email="closetwice@example.com")
    account = _create_account(client, headers)
    client.post(f"/accounts/{account['id']}/close", headers=headers)

    response = client.post(f"/accounts/{account['id']}/close", headers=headers)
    assert response.status_code == 400


def test_new_account_defaults_to_active_status(client, auth_headers):
    headers = auth_headers(email="closedefault@example.com")
    account = _create_account(client, headers)
    assert account["status"] == "active"
