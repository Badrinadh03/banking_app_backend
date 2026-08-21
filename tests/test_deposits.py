def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def test_deposit_increases_balance(client, auth_headers):
    headers = auth_headers()
    account = _create_account(client, headers)

    response = client.post(
        f"/accounts/{account['id']}/deposit",
        json={"amount": "50.00", "description": "paycheck"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["transaction_type"] == "deposit"
    assert body["from_account_id"] is None
    assert body["to_account_id"] == account["id"]

    account_after = client.get(f"/accounts/{account['id']}", headers=headers).json()
    assert float(account_after["balance"]) == 50.0


def test_deposit_appears_in_history(client, auth_headers):
    headers = auth_headers()
    account = _create_account(client, headers)
    client.post(f"/accounts/{account['id']}/deposit", json={"amount": "25.00"}, headers=headers)

    history = client.get(f"/accounts/{account['id']}/transactions", headers=headers).json()
    assert len(history) == 1
    assert history[0]["transaction_type"] == "deposit"


def test_deposit_rejects_non_positive_amount(client, auth_headers):
    headers = auth_headers()
    account = _create_account(client, headers)

    response = client.post(
        f"/accounts/{account['id']}/deposit", json={"amount": "0.00"}, headers=headers
    )
    assert response.status_code == 422


def test_deposit_requires_ownership(client, auth_headers):
    headers_a = auth_headers(email="depositA@example.com")
    headers_b = auth_headers(email="depositB@example.com")
    account = _create_account(client, headers_a)

    response = client.post(
        f"/accounts/{account['id']}/deposit", json={"amount": "10.00"}, headers=headers_b
    )
    assert response.status_code == 403


def test_deposit_nonexistent_account_returns_404(client, auth_headers):
    headers = auth_headers()
    response = client.post("/accounts/9999/deposit", json={"amount": "10.00"}, headers=headers)
    assert response.status_code == 404
