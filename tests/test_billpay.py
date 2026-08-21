def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def _seed_balance(db_session, account_id: int, amount: str):
    from decimal import Decimal

    from app.models.account import Account

    account = db_session.get(Account, account_id)
    account.balance = Decimal(amount)
    db_session.commit()


def _create_company_payee(client, headers, nickname="Electric bill"):
    return client.post(
        "/payees",
        json={
            "payee_type": "company",
            "pay_method": "bill_pay",
            "nickname": nickname,
            "company_name": "Xylo Energy",
            "account_number": "123456789",
            "zip_code": "90210",
        },
        headers=headers,
    ).json()


def test_bill_pay_status_starts_unenrolled(client, auth_headers):
    headers = auth_headers(email="billstatus@example.com")
    response = client.get("/billpay/status", headers=headers)
    assert response.status_code == 200
    assert response.json()["enrolled"] is False


def test_pay_bill_rejected_before_enrollment(client, auth_headers, db_session):
    headers = auth_headers(email="billunenrolled@example.com")
    account = _create_account(client, headers)
    _seed_balance(db_session, account["id"], "500.00")
    payee = _create_company_payee(client, headers)

    response = client.post(
        "/billpay/pay",
        json={
            "from_account_id": account["id"],
            "payee_id": payee["id"],
            "amount": "50.00",
            "otp_code": "000000",
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_enroll_then_pay_bill_succeeds_and_appears_in_activity(
    client, auth_headers, db_session, get_otp_code
):
    headers = auth_headers(email="billenrolled@example.com")
    account = _create_account(client, headers)
    _seed_balance(db_session, account["id"], "500.00")
    payee = _create_company_payee(client, headers)

    enroll_response = client.post("/billpay/enroll", headers=headers)
    assert enroll_response.status_code == 200
    assert enroll_response.json()["enrolled"] is True

    pay_response = client.post(
        "/billpay/pay",
        json={
            "from_account_id": account["id"],
            "payee_id": payee["id"],
            "amount": "75.00",
            "otp_code": get_otp_code("billenrolled@example.com"),
        },
        headers=headers,
    )
    assert pay_response.status_code == 200
    assert pay_response.json()["transaction_type"] == "bill_payment"

    account_after = client.get(f"/accounts/{account['id']}", headers=headers).json()
    assert float(account_after["balance"]) == 425.0

    activity = client.get("/billpay/activity", headers=headers).json()
    assert len(activity) == 1
    assert activity[0]["payee_id"] == payee["id"]

    # bill-payment notification building must not crash the request
    notifications = client.get("/notifications", headers=headers).json()
    assert any(n["message"] for n in notifications)


def test_pay_bill_insufficient_funds(client, auth_headers, get_otp_code):
    headers = auth_headers(email="billpoor@example.com")
    account = _create_account(client, headers)
    payee = _create_company_payee(client, headers)
    client.post("/billpay/enroll", headers=headers)

    response = client.post(
        "/billpay/pay",
        json={
            "from_account_id": account["id"],
            "payee_id": payee["id"],
            "amount": "50.00",
            "otp_code": get_otp_code("billpoor@example.com"),
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_pay_bill_with_unowned_payee_rejected(client, auth_headers, db_session, get_otp_code):
    headers_a = auth_headers(email="billownera@example.com")
    headers_b = auth_headers(email="billownerb@example.com")
    account_b = _create_account(client, headers_b)
    _seed_balance(db_session, account_b["id"], "500.00")
    payee_a = _create_company_payee(client, headers_a)
    client.post("/billpay/enroll", headers=headers_b)

    response = client.post(
        "/billpay/pay",
        json={
            "from_account_id": account_b["id"],
            "payee_id": payee_a["id"],
            "amount": "50.00",
            "otp_code": get_otp_code("billownerb@example.com"),
        },
        headers=headers_b,
    )
    assert response.status_code == 403


def test_pay_bill_rejects_zelle_method_payee(client, auth_headers, db_session, get_otp_code):
    headers = auth_headers(email="billwrongmethod@example.com")
    account = _create_account(client, headers)
    _seed_balance(db_session, account["id"], "500.00")
    client.post("/billpay/enroll", headers=headers)

    zelle_payee = client.post(
        "/payees",
        json={
            "payee_type": "person",
            "pay_method": "zelle",
            "nickname": "Friend",
            "contact_identifier": "friend@example.com",
        },
        headers=headers,
    ).json()

    response = client.post(
        "/billpay/pay",
        json={
            "from_account_id": account["id"],
            "payee_id": zelle_payee["id"],
            "amount": "20.00",
            "otp_code": get_otp_code("billwrongmethod@example.com"),
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_pay_bill_rejects_wrong_otp_code(client, auth_headers, db_session):
    headers = auth_headers(email="billwrongotp@example.com")
    account = _create_account(client, headers)
    _seed_balance(db_session, account["id"], "500.00")
    payee = _create_company_payee(client, headers)
    client.post("/billpay/enroll", headers=headers)

    response = client.post(
        "/billpay/pay",
        json={
            "from_account_id": account["id"],
            "payee_id": payee["id"],
            "amount": "20.00",
            "otp_code": "000000",
        },
        headers=headers,
    )
    assert response.status_code == 400
