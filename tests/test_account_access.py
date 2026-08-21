def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def _seed_balance(db_session, account_id: int, amount: str):
    from decimal import Decimal

    from app.models.account import Account

    account = db_session.get(Account, account_id)
    account.balance = Decimal(amount)
    db_session.commit()


def test_grant_access_by_email(client, auth_headers):
    owner_headers = auth_headers(email="accessowner1@example.com")
    joint_headers = auth_headers(email="accessjoint1@example.com")
    account = _create_account(client, owner_headers)

    response = client.post(
        f"/accounts/{account['id']}/access",
        json={"contact_identifier": "accessjoint1@example.com"},
        headers=owner_headers,
    )
    assert response.status_code == 201
    assert response.json()["user_name"] == "Test User"


def test_grant_access_rejects_non_owner(client, auth_headers):
    owner_headers = auth_headers(email="accessowner2@example.com")
    stranger_headers = auth_headers(email="accessstranger2@example.com")
    joint_headers = auth_headers(email="accessjoint2@example.com")
    account = _create_account(client, owner_headers)

    response = client.post(
        f"/accounts/{account['id']}/access",
        json={"contact_identifier": "accessjoint2@example.com"},
        headers=stranger_headers,
    )
    assert response.status_code == 403


def test_grant_access_rejects_unknown_contact(client, auth_headers):
    owner_headers = auth_headers(email="accessowner3@example.com")
    account = _create_account(client, owner_headers)

    response = client.post(
        f"/accounts/{account['id']}/access",
        json={"contact_identifier": "nobody-registered@example.com"},
        headers=owner_headers,
    )
    assert response.status_code == 400


def test_joint_user_can_transfer_from_shared_account(client, auth_headers, db_session):
    owner_headers = auth_headers(email="accesstransfer_o@example.com")
    joint_headers = auth_headers(email="accesstransfer_j@example.com")
    shared_account = _create_account(client, owner_headers)
    joint_own_account = _create_account(client, joint_headers)
    _seed_balance(db_session, shared_account["id"], "300.00")

    client.post(
        f"/accounts/{shared_account['id']}/access",
        json={"contact_identifier": "accesstransfer_j@example.com"},
        headers=owner_headers,
    )

    response = client.post(
        "/transfers",
        json={
            "from_account_id": shared_account["id"],
            "to_account_id": joint_own_account["id"],
            "amount": "50.00",
        },
        headers=joint_headers,
    )
    assert response.status_code == 201

    shared_after = client.get(f"/accounts/{shared_account['id']}", headers=joint_headers).json()
    assert float(shared_after["balance"]) == 250.0


def test_stranger_cannot_transfer_from_shared_account(client, auth_headers, db_session):
    owner_headers = auth_headers(email="accessstranger4_o@example.com")
    stranger_headers = auth_headers(email="accessstranger4_s@example.com")
    shared_account = _create_account(client, owner_headers)
    stranger_account = _create_account(client, stranger_headers)
    _seed_balance(db_session, shared_account["id"], "300.00")

    response = client.post(
        "/transfers",
        json={
            "from_account_id": shared_account["id"],
            "to_account_id": stranger_account["id"],
            "amount": "50.00",
        },
        headers=stranger_headers,
    )
    assert response.status_code == 403


def test_joint_user_can_view_statement_and_transactions(client, auth_headers, db_session):
    owner_headers = auth_headers(email="accessview_o@example.com")
    joint_headers = auth_headers(email="accessview_j@example.com")
    shared_account = _create_account(client, owner_headers)
    _seed_balance(db_session, shared_account["id"], "100.00")

    client.post(
        f"/accounts/{shared_account['id']}/access",
        json={"contact_identifier": "accessview_j@example.com"},
        headers=owner_headers,
    )

    response = client.get(f"/accounts/{shared_account['id']}/transactions", headers=joint_headers)
    assert response.status_code == 200


def test_list_and_revoke_access(client, auth_headers):
    owner_headers = auth_headers(email="accessrevoke_o@example.com")
    joint_headers = auth_headers(email="accessrevoke_j@example.com")
    account = _create_account(client, owner_headers)

    client.post(
        f"/accounts/{account['id']}/access",
        json={"contact_identifier": "accessrevoke_j@example.com"},
        headers=owner_headers,
    )
    listed = client.get(f"/accounts/{account['id']}/access", headers=owner_headers).json()
    assert len(listed) == 1
    joint_user_id = listed[0]["user_id"]

    revoke_response = client.delete(
        f"/accounts/{account['id']}/access/{joint_user_id}", headers=owner_headers
    )
    assert revoke_response.status_code == 204

    listed_after = client.get(f"/accounts/{account['id']}/access", headers=owner_headers).json()
    assert listed_after == []

    # revoked joint user can no longer access the account
    deposit_response = client.post(
        f"/accounts/{account['id']}/deposit", json={"amount": "10.00"}, headers=joint_headers
    )
    assert deposit_response.status_code == 403
