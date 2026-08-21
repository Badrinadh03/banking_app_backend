from datetime import date, timedelta
from decimal import Decimal


def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def _seed_balance(db_session, account_id: int, amount: str):
    from app.models.account import Account

    account = db_session.get(Account, account_id)
    account.balance = Decimal(amount)
    db_session.commit()


def test_create_recurring_transfer_requires_destination(client, auth_headers):
    headers = auth_headers(email="recurringnodest@example.com")
    account = _create_account(client, headers)

    response = client.post(
        "/recurring",
        json={
            "from_account_id": account["id"],
            "payment_type": "transfer",
            "amount": "10.00",
            "frequency": "monthly",
            "next_run_date": str(date.today()),
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_create_list_and_cancel_recurring_payment(client, auth_headers):
    headers = auth_headers(email="recurringcrud@example.com")
    source = _create_account(client, headers)
    dest = _create_account(client, headers, "savings")

    create_response = client.post(
        "/recurring",
        json={
            "from_account_id": source["id"],
            "payment_type": "transfer",
            "to_account_id": dest["id"],
            "amount": "20.00",
            "frequency": "weekly",
            "next_run_date": str(date.today() + timedelta(days=7)),
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    recurring_id = create_response.json()["id"]

    listed = client.get("/recurring", headers=headers).json()
    assert len(listed) == 1

    cancel_response = client.post(f"/recurring/{recurring_id}/cancel", headers=headers)
    assert cancel_response.status_code == 200
    assert cancel_response.json()["is_active"] is False


def test_process_due_payments_executes_transfer_and_advances_date(client, auth_headers, db_session):
    from app.services import recurring_payment_service

    headers = auth_headers(email="recurringdue@example.com")
    source = _create_account(client, headers)
    dest = _create_account(client, headers, "savings")
    _seed_balance(db_session, source["id"], "200.00")

    create_response = client.post(
        "/recurring",
        json={
            "from_account_id": source["id"],
            "payment_type": "transfer",
            "to_account_id": dest["id"],
            "amount": "30.00",
            "description": "Weekly savings sweep",
            "frequency": "weekly",
            "next_run_date": str(date.today()),
        },
        headers=headers,
    )
    recurring_id = create_response.json()["id"]

    processed = recurring_payment_service.process_due_payments(db_session)
    assert processed == 1

    source_after = client.get(f"/accounts/{source['id']}", headers=headers).json()
    dest_after = client.get(f"/accounts/{dest['id']}", headers=headers).json()
    assert float(source_after["balance"]) == 170.0
    assert float(dest_after["balance"]) == 30.0

    listed = client.get("/recurring", headers=headers).json()
    updated = next(r for r in listed if r["id"] == recurring_id)
    assert updated["next_run_date"] == str(date.today() + timedelta(days=7))
    assert updated["last_run_at"] is not None


def test_process_due_payments_skips_on_insufficient_funds_and_notifies(client, auth_headers, db_session):
    from app.services import recurring_payment_service

    headers = auth_headers(email="recurringpoor@example.com")
    source = _create_account(client, headers)
    dest = _create_account(client, headers, "savings")

    client.post(
        "/recurring",
        json={
            "from_account_id": source["id"],
            "payment_type": "transfer",
            "to_account_id": dest["id"],
            "amount": "999.00",
            "frequency": "monthly",
            "next_run_date": str(date.today()),
        },
        headers=headers,
    )

    processed = recurring_payment_service.process_due_payments(db_session)
    assert processed == 0

    notifications = client.get("/notifications", headers=headers).json()
    assert any("couldn't be completed" in n["message"] for n in notifications)


def test_process_due_payments_ignores_future_dated_payments(client, auth_headers, db_session):
    from app.services import recurring_payment_service

    headers = auth_headers(email="recurringfuture@example.com")
    source = _create_account(client, headers)
    dest = _create_account(client, headers, "savings")
    _seed_balance(db_session, source["id"], "200.00")

    client.post(
        "/recurring",
        json={
            "from_account_id": source["id"],
            "payment_type": "transfer",
            "to_account_id": dest["id"],
            "amount": "20.00",
            "frequency": "monthly",
            "next_run_date": str(date.today() + timedelta(days=30)),
        },
        headers=headers,
    )

    processed = recurring_payment_service.process_due_payments(db_session)
    assert processed == 0
