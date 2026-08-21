from decimal import Decimal

from app.models.account import Account


def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def test_list_all_transactions_across_accounts(client, auth_headers, db_session):
    headers = auth_headers()
    checking = _create_account(client, headers, "checking")
    savings = _create_account(client, headers, "savings")

    client.post(f"/accounts/{checking['id']}/deposit", json={"amount": "100.00"}, headers=headers)
    client.post(
        "/transfers",
        json={"from_account_id": checking["id"], "to_account_id": savings["id"], "amount": "30.00"},
        headers=headers,
    )

    response = client.get("/transactions", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2


def test_list_all_transactions_empty_when_no_accounts(client, auth_headers):
    headers = auth_headers()
    response = client.get("/transactions", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_list_all_transactions_scoped_to_user(client, auth_headers):
    headers_a = auth_headers(email="txuserA@example.com")
    headers_b = auth_headers(email="txuserB@example.com")
    account_a = _create_account(client, headers_a)
    client.post(f"/accounts/{account_a['id']}/deposit", json={"amount": "50.00"}, headers=headers_a)

    response = client.get("/transactions", headers=headers_b)
    assert response.json() == []


def test_list_all_transactions_requires_auth(client):
    assert client.get("/transactions").status_code == 401
