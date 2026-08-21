from datetime import datetime, timedelta, timezone


def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


FAKE_IMAGE_BYTES = b"\xff\xd8\xff\xe0fake-jpeg-content"


def _submit_check(client, headers, account_id, amount="150.00"):
    return client.post(
        "/check-deposits",
        data={"account_id": str(account_id), "amount": amount},
        files={
            "front_image": ("front.jpg", FAKE_IMAGE_BYTES, "image/jpeg"),
            "back_image": ("back.jpg", FAKE_IMAGE_BYTES, "image/jpeg"),
        },
        headers=headers,
    )


def test_submit_check_deposit_starts_pending(client, auth_headers):
    headers = auth_headers(email="checksubmit@example.com")
    account = _create_account(client, headers)

    response = _submit_check(client, headers, account["id"])
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["cleared_transaction_id"] is None


def test_submit_check_deposit_rejects_bad_content_type(client, auth_headers):
    headers = auth_headers(email="checkbadtype@example.com")
    account = _create_account(client, headers)

    response = client.post(
        "/check-deposits",
        data={"account_id": str(account["id"]), "amount": "50.00"},
        files={
            "front_image": ("front.txt", b"not an image", "text/plain"),
            "back_image": ("back.jpg", FAKE_IMAGE_BYTES, "image/jpeg"),
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_submit_check_deposit_rejects_unowned_account(client, auth_headers):
    owner_headers = auth_headers(email="checkownera@example.com")
    other_headers = auth_headers(email="checkownerb@example.com")
    account = _create_account(client, owner_headers)

    response = _submit_check(client, other_headers, account["id"])
    assert response.status_code == 403


def test_list_check_deposits(client, auth_headers):
    headers = auth_headers(email="checklist@example.com")
    account = _create_account(client, headers)
    _submit_check(client, headers, account["id"])

    listed = client.get("/check-deposits", headers=headers).json()
    assert len(listed) == 1


def test_get_check_deposit_image_requires_ownership(client, auth_headers):
    owner_headers = auth_headers(email="checkimg_o@example.com")
    stranger_headers = auth_headers(email="checkimg_s@example.com")
    account = _create_account(client, owner_headers)
    deposit = _submit_check(client, owner_headers, account["id"]).json()

    own_response = client.get(
        f"/check-deposits/{deposit['id']}/image/front", headers=owner_headers
    )
    assert own_response.status_code == 200

    stranger_response = client.get(
        f"/check-deposits/{deposit['id']}/image/front", headers=stranger_headers
    )
    assert stranger_response.status_code == 403


def test_clear_due_holds_credits_account_for_real(client, auth_headers, db_session):
    from app.models.check_deposit import CheckDeposit
    from app.services import check_deposit_service

    headers = auth_headers(email="checkclear@example.com")
    account = _create_account(client, headers)
    deposit_body = _submit_check(client, headers, account["id"], amount="200.00").json()

    # Backdate the hold so it's already due, same trick used for OTP/date
    # backdating elsewhere in this suite — the real submit flow always sets
    # a future hold, so a normal deposit never clears immediately in tests.
    db_deposit = db_session.get(CheckDeposit, deposit_body["id"])
    db_deposit.hold_release_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    cleared_count = check_deposit_service.clear_due_holds(db_session)
    assert cleared_count == 1

    account_after = client.get(f"/accounts/{account['id']}", headers=headers).json()
    assert float(account_after["balance"]) == 200.0

    listed = client.get("/check-deposits", headers=headers).json()
    assert listed[0]["status"] == "cleared"
    assert listed[0]["cleared_transaction_id"] is not None


def test_clear_due_holds_ignores_not_yet_due_deposits(client, auth_headers, db_session):
    from app.services import check_deposit_service

    headers = auth_headers(email="checknotdue@example.com")
    account = _create_account(client, headers)
    _submit_check(client, headers, account["id"])

    cleared_count = check_deposit_service.clear_due_holds(db_session)
    assert cleared_count == 0
