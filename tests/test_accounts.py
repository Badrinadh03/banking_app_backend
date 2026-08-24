from app.models.user import User
from tests.conftest import SIGNUP_ID_FILES, signup_form


def _make_unverified_profile_user(client, db_session, email, password="password123"):
    client.post(
        "/auth/signup",
        data=signup_form(
            email=email,
            password=password,
            full_name="Incomplete Profile",
            phone_number=f"555555{abs(hash(email)) % 10000:04d}",
        ),
        files=SIGNUP_ID_FILES,
    )
    user = db_session.query(User).filter(User.email == email).first()
    user.is_verified = True
    # Signup itself now always collects address/government_id_last4, so this
    # clears them back out to simulate the profile-incomplete state these
    # tests are exercising (e.g. an account opened before that data was
    # required, or cleared by a data-correction flow).
    user.address = None
    user.government_id_last4 = None
    db_session.commit()
    response = client.post("/auth/login", json={"identifier": email, "password": password})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_account_rejected_without_address(client, db_session):
    headers = _make_unverified_profile_user(client, db_session, "noaddress@example.com")
    response = client.post(
        "/accounts",
        json={"account_type": "checking", "government_id_last4": "1234"},
        headers=headers,
    )
    assert response.status_code == 400


def test_create_account_rejected_without_government_id(client, db_session):
    headers = _make_unverified_profile_user(client, db_session, "noid@example.com")
    response = client.post(
        "/accounts",
        json={"account_type": "checking", "address": "1 Main St"},
        headers=headers,
    )
    assert response.status_code == 400


def test_create_account_submitting_requirements_persists_them_to_profile(client, db_session):
    headers = _make_unverified_profile_user(client, db_session, "completesnow@example.com")
    response = client.post(
        "/accounts",
        json={"account_type": "checking", "address": "42 Wallaby Way", "government_id_last4": "5678"},
        headers=headers,
    )
    assert response.status_code == 201

    me = client.get("/users/me", headers=headers).json()
    assert me["address"] == "42 Wallaby Way"
    assert me["government_id_last4"] == "5678"

    # a second account doesn't need to resubmit either field
    second = client.post("/accounts", json={"account_type": "savings"}, headers=headers)
    assert second.status_code == 201


def test_create_account_with_initial_deposit_creates_transaction(client, auth_headers):
    headers = auth_headers(email="openingdeposit@example.com")
    response = client.post(
        "/accounts",
        json={"account_type": "checking", "initial_deposit": "100.00"},
        headers=headers,
    )
    assert response.status_code == 201
    account = response.json()
    assert float(account["balance"]) == 100.0

    transactions = client.get(f"/accounts/{account['id']}/transactions", headers=headers).json()
    assert len(transactions) == 1
    assert transactions[0]["transaction_type"] == "deposit"
    assert transactions[0]["description"] == "Account opening deposit"


def test_create_account_without_initial_deposit_has_zero_balance_and_no_transaction(
    client, auth_headers
):
    headers = auth_headers(email="nodeposit@example.com")
    response = client.post("/accounts", json={"account_type": "checking"}, headers=headers)
    assert response.status_code == 201
    account = response.json()
    assert float(account["balance"]) == 0.0

    transactions = client.get(f"/accounts/{account['id']}/transactions", headers=headers).json()
    assert len(transactions) == 0


def test_create_and_list_accounts(client, auth_headers):
    headers = auth_headers()

    response = client.post("/accounts", json={"account_type": "checking"}, headers=headers)
    assert response.status_code == 201
    account = response.json()
    assert account["account_type"] == "checking"
    assert account["balance"] == "0.00" or float(account["balance"]) == 0.0

    response = client.get("/accounts", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_account_ownership_enforced(client, auth_headers):
    headers_a = auth_headers(email="ownerA@example.com")
    headers_b = auth_headers(email="ownerB@example.com")

    account = client.post("/accounts", json={"account_type": "checking"}, headers=headers_a).json()

    response = client.get(f"/accounts/{account['id']}", headers=headers_b)
    assert response.status_code == 403


def test_get_nonexistent_account_returns_404(client, auth_headers):
    headers = auth_headers()
    response = client.get("/accounts/9999", headers=headers)
    assert response.status_code == 404
