def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def _seed_balance(db_session, account_id: int, amount: str):
    from decimal import Decimal

    from app.models.account import Account

    account = db_session.get(Account, account_id)
    account.balance = Decimal(amount)
    db_session.commit()


def test_zelle_pay_to_matched_user_credits_them_for_real(
    client, auth_headers, db_session, get_otp_code
):
    sender_headers = auth_headers(email="zellesender@example.com")
    recipient_headers = auth_headers(email="zellerecipient@example.com")
    sender_account = _create_account(client, sender_headers)
    recipient_account = _create_account(client, recipient_headers)
    _seed_balance(db_session, sender_account["id"], "200.00")

    response = client.post(
        "/zelle/pay",
        json={
            "from_account_id": sender_account["id"],
            "contact_identifier": "zellerecipient@example.com",
            "amount": "60.00",
            "otp_code": get_otp_code("zellesender@example.com"),
        },
        headers=sender_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transaction_type"] == "zelle_payment"
    assert body["to_account_id"] == recipient_account["id"]

    sender_after = client.get(f"/accounts/{sender_account['id']}", headers=sender_headers).json()
    recipient_after = client.get(
        f"/accounts/{recipient_account['id']}", headers=recipient_headers
    ).json()
    assert float(sender_after["balance"]) == 140.0
    assert float(recipient_after["balance"]) == 60.0

    recipient_notifications = client.get("/notifications", headers=recipient_headers).json()
    assert len(recipient_notifications) >= 1


def test_zelle_pay_to_unmatched_contact_only_debits_sender(
    client, auth_headers, db_session, get_otp_code
):
    headers = auth_headers(email="zelleunmatched@example.com")
    account = _create_account(client, headers)
    _seed_balance(db_session, account["id"], "200.00")

    response = client.post(
        "/zelle/pay",
        json={
            "from_account_id": account["id"],
            "contact_identifier": "nobody-registered@example.com",
            "amount": "40.00",
            "otp_code": get_otp_code("zelleunmatched@example.com"),
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["to_account_id"] is None

    account_after = client.get(f"/accounts/{account['id']}", headers=headers).json()
    assert float(account_after["balance"]) == 160.0


def test_zelle_pay_insufficient_funds(client, auth_headers, get_otp_code):
    headers = auth_headers(email="zellepoor@example.com")
    account = _create_account(client, headers)

    response = client.post(
        "/zelle/pay",
        json={
            "from_account_id": account["id"],
            "contact_identifier": "someone@example.com",
            "amount": "40.00",
            "otp_code": get_otp_code("zellepoor@example.com"),
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_zelle_pay_rejects_wrong_otp_code(client, auth_headers):
    headers = auth_headers(email="zellewrongotp@example.com")
    account = _create_account(client, headers)

    response = client.post(
        "/zelle/pay",
        json={
            "from_account_id": account["id"],
            "contact_identifier": "someone@example.com",
            "amount": "10.00",
            "otp_code": "000000",
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_zelle_request_appears_in_matched_users_incoming_list(client, auth_headers):
    requester_headers = auth_headers(email="zellereqster@example.com")
    target_headers = auth_headers(email="zellereqtarget@example.com")

    response = client.post(
        "/zelle/request",
        json={"target_identifier": "zellereqtarget@example.com", "amount": "25.00", "note": "Lunch"},
        headers=requester_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"

    incoming = client.get("/zelle/requests", headers=target_headers).json()
    assert len(incoming) == 1
    assert incoming[0]["requester_name"] == "Test User"
    assert incoming[0]["amount"] == "25.00"


def test_zelle_request_pay_completes_transaction_and_flips_status(
    client, auth_headers, db_session, get_otp_code
):
    requester_headers = auth_headers(email="zellereqpay_r@example.com")
    target_headers = auth_headers(email="zellereqpay_t@example.com")
    requester_account = _create_account(client, requester_headers)
    target_account = _create_account(client, target_headers)
    _seed_balance(db_session, target_account["id"], "100.00")

    request_response = client.post(
        "/zelle/request",
        json={"target_identifier": "zellereqpay_t@example.com", "amount": "30.00"},
        headers=requester_headers,
    )
    request_id = request_response.json()["id"]

    pay_response = client.post(
        f"/zelle/requests/{request_id}/pay",
        json={
            "from_account_id": target_account["id"],
            "otp_code": get_otp_code("zellereqpay_t@example.com"),
        },
        headers=target_headers,
    )
    assert pay_response.status_code == 200
    assert pay_response.json()["transaction_type"] == "zelle_payment"

    requester_after = client.get(f"/accounts/{requester_account['id']}", headers=requester_headers).json()
    assert float(requester_after["balance"]) == 30.0

    incoming_after = client.get("/zelle/requests", headers=target_headers).json()
    assert incoming_after == []


def test_zelle_request_decline_works(client, auth_headers):
    requester_headers = auth_headers(email="zellereqdecline_r@example.com")
    target_headers = auth_headers(email="zellereqdecline_t@example.com")

    request_response = client.post(
        "/zelle/request",
        json={"target_identifier": "zellereqdecline_t@example.com", "amount": "10.00"},
        headers=requester_headers,
    )
    request_id = request_response.json()["id"]

    decline_response = client.post(
        f"/zelle/requests/{request_id}/decline", headers=target_headers
    )
    assert decline_response.status_code == 200
    assert decline_response.json()["status"] == "declined"

    incoming_after = client.get("/zelle/requests", headers=target_headers).json()
    assert incoming_after == []


def test_zelle_request_decline_notifies_requester(client, auth_headers):
    requester_headers = auth_headers(email="zellereqdeclinenotify_r@example.com")
    target_headers = auth_headers(email="zellereqdeclinenotify_t@example.com")

    request_response = client.post(
        "/zelle/request",
        json={"target_identifier": "zellereqdeclinenotify_t@example.com", "amount": "15.00"},
        headers=requester_headers,
    )
    request_id = request_response.json()["id"]

    client.post(f"/zelle/requests/{request_id}/decline", headers=target_headers)

    requester_notifications = client.get("/notifications", headers=requester_headers).json()
    assert any("declined your Zelle request" in n["message"] for n in requester_notifications)


def test_zelle_request_pay_rejected_for_non_target_user(client, auth_headers, get_otp_code):
    requester_headers = auth_headers(email="zellereqwrong_r@example.com")
    target_headers = auth_headers(email="zellereqwrong_t@example.com")
    stranger_headers = auth_headers(email="zellereqwrong_s@example.com")
    stranger_account = _create_account(client, stranger_headers)

    request_response = client.post(
        "/zelle/request",
        json={"target_identifier": "zellereqwrong_t@example.com", "amount": "10.00"},
        headers=requester_headers,
    )
    request_id = request_response.json()["id"]

    response = client.post(
        f"/zelle/requests/{request_id}/pay",
        json={
            "from_account_id": stranger_account["id"],
            "otp_code": get_otp_code("zellereqwrong_s@example.com"),
        },
        headers=stranger_headers,
    )
    assert response.status_code == 403


def test_zelle_recent_activity_lists_payments(client, auth_headers, db_session, get_otp_code):
    headers = auth_headers(email="zelleactivity@example.com")
    account = _create_account(client, headers)
    _seed_balance(db_session, account["id"], "100.00")

    client.post(
        "/zelle/pay",
        json={
            "from_account_id": account["id"],
            "contact_identifier": "recurring@example.com",
            "amount": "15.00",
            "otp_code": get_otp_code("zelleactivity@example.com"),
        },
        headers=headers,
    )

    activity = client.get("/zelle/activity", headers=headers).json()
    assert len(activity) == 1
    assert activity[0]["zelle_contact"] == "recurring@example.com"
