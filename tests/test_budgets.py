from datetime import date


def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def test_create_and_list_budgets(client, auth_headers):
    headers = auth_headers(email="budgetcrud@example.com")

    response = client.post(
        "/budgets", json={"category": "Groceries", "monthly_limit": "300.00"}, headers=headers
    )
    assert response.status_code == 201

    listed = client.get("/budgets", headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["category"] == "Groceries"


def test_delete_budget(client, auth_headers):
    headers = auth_headers(email="budgetdelete@example.com")
    created = client.post(
        "/budgets", json={"category": "Dining", "monthly_limit": "150.00"}, headers=headers
    ).json()

    response = client.delete(f"/budgets/{created['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get("/budgets", headers=headers).json() == []


def test_budget_progress_with_no_matching_transactions_is_zero(client, auth_headers):
    headers = auth_headers(email="budgetprogress@example.com")
    account = _create_account(client, headers)

    client.post(
        "/budgets", json={"category": "Groceries", "monthly_limit": "100.00"}, headers=headers
    )
    client.post(f"/accounts/{account['id']}/deposit", json={"amount": "500.00"}, headers=headers)

    today = date.today()
    response = client.get(
        "/budgets/progress", params={"year": today.year, "month": today.month}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["budget"]["category"] == "Groceries"
    assert float(body[0]["spent"]) == 0.0


def test_budget_progress_matches_description_substring(client, auth_headers, db_session):
    from decimal import Decimal

    from app.models.account import Account

    headers = auth_headers(email="budgetmatch@example.com")
    account = _create_account(client, headers)
    db_account = db_session.get(Account, account["id"])
    db_account.balance = Decimal("500.00")
    db_session.commit()

    client.post(
        "/budgets", json={"category": "Groceries", "monthly_limit": "100.00"}, headers=headers
    )
    other_account = _create_account(client, headers, "savings")
    client.post(
        "/transfers",
        json={
            "from_account_id": account["id"],
            "to_account_id": other_account["id"],
            "amount": "40.00",
            "description": "Weekly Groceries run",
        },
        headers=headers,
    )

    today = date.today()
    response = client.get(
        "/budgets/progress", params={"year": today.year, "month": today.month}, headers=headers
    )
    body = response.json()
    assert float(body[0]["spent"]) == 40.0
    assert float(body[0]["remaining"]) == 60.0
