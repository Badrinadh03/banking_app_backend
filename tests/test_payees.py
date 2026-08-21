def test_create_company_payee(client, auth_headers):
    headers = auth_headers(email="payeeco@example.com")
    response = client.post(
        "/payees",
        json={
            "payee_type": "company",
            "pay_method": "bill_pay",
            "nickname": "Electric bill",
            "company_name": "Xylo Energy",
            "account_number": "123456789",
            "zip_code": "90210",
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["company_name"] == "Xylo Energy"
    assert body["pay_method"] == "bill_pay"


def test_create_person_zelle_payee(client, auth_headers):
    headers = auth_headers(email="payeezelle@example.com")
    response = client.post(
        "/payees",
        json={
            "payee_type": "person",
            "pay_method": "zelle",
            "nickname": "Mom",
            "contact_identifier": "mom@example.com",
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["contact_identifier"] == "mom@example.com"


def test_create_person_billpay_payee(client, auth_headers):
    headers = auth_headers(email="payeebillperson@example.com")
    response = client.post(
        "/payees",
        json={
            "payee_type": "person",
            "pay_method": "bill_pay",
            "nickname": "Landlord",
            "recipient_name": "Jordan Landlord",
            "mailing_address": "1 Rent St, Springfield",
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["recipient_name"] == "Jordan Landlord"


def test_company_payee_requires_account_and_zip(client, auth_headers):
    headers = auth_headers(email="payeecoinvalid@example.com")
    response = client.post(
        "/payees",
        json={
            "payee_type": "company",
            "pay_method": "bill_pay",
            "nickname": "Incomplete",
            "company_name": "Xylo Energy",
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_zelle_payee_requires_contact(client, auth_headers):
    headers = auth_headers(email="payeezelleinvalid@example.com")
    response = client.post(
        "/payees",
        json={"payee_type": "person", "pay_method": "zelle", "nickname": "No contact"},
        headers=headers,
    )
    assert response.status_code == 422


def test_company_payee_rejects_account_number_too_long(client, auth_headers):
    headers = auth_headers(email="payeeacctlong@example.com")
    response = client.post(
        "/payees",
        json={
            "payee_type": "company",
            "pay_method": "bill_pay",
            "nickname": "Too long",
            "company_name": "Xylo Energy",
            "account_number": "1" * 18,
            "zip_code": "90210",
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_company_payee_rejects_account_number_too_short(client, auth_headers):
    headers = auth_headers(email="payeeacctshort@example.com")
    response = client.post(
        "/payees",
        json={
            "payee_type": "company",
            "pay_method": "bill_pay",
            "nickname": "Too short",
            "company_name": "Xylo Energy",
            "account_number": "12",
            "zip_code": "90210",
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_company_payee_rejects_non_numeric_account_number(client, auth_headers):
    headers = auth_headers(email="payeeacctletters@example.com")
    response = client.post(
        "/payees",
        json={
            "payee_type": "company",
            "pay_method": "bill_pay",
            "nickname": "Letters",
            "company_name": "Xylo Energy",
            "account_number": "abcd1234",
            "zip_code": "90210",
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_company_payee_rejects_malformed_zip(client, auth_headers):
    headers = auth_headers(email="payeezipbad@example.com")
    response = client.post(
        "/payees",
        json={
            "payee_type": "company",
            "pay_method": "bill_pay",
            "nickname": "Bad zip",
            "company_name": "Xylo Energy",
            "account_number": "123456789",
            "zip_code": "9021",
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_company_payee_accepts_zip_plus_4(client, auth_headers):
    headers = auth_headers(email="payeezipplus4@example.com")
    response = client.post(
        "/payees",
        json={
            "payee_type": "company",
            "pay_method": "bill_pay",
            "nickname": "Zip plus 4",
            "company_name": "Xylo Energy",
            "account_number": "123456789",
            "zip_code": "90210-1234",
        },
        headers=headers,
    )
    assert response.status_code == 201


def test_company_payee_rejects_zip_that_does_not_exist(client, auth_headers, monkeypatch):
    from app.services import zipcode_service

    monkeypatch.setattr(
        zipcode_service,
        "lookup_zip_code",
        lambda zip_code: {"service_available": True, "found": False},
    )

    headers = auth_headers(email="payeezipnotfound@example.com")
    response = client.post(
        "/payees",
        json={
            "payee_type": "company",
            "pay_method": "bill_pay",
            "nickname": "Fake zip",
            "company_name": "Xylo Energy",
            "account_number": "123456789",
            "zip_code": "00000",
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_company_payee_allowed_when_zip_lookup_service_unavailable(client, auth_headers, monkeypatch):
    from app.services import zipcode_service

    monkeypatch.setattr(
        zipcode_service,
        "lookup_zip_code",
        lambda zip_code: {"service_available": False, "found": False},
    )

    headers = auth_headers(email="payeezipserviceoutage@example.com")
    response = client.post(
        "/payees",
        json={
            "payee_type": "company",
            "pay_method": "bill_pay",
            "nickname": "Service outage",
            "company_name": "Xylo Energy",
            "account_number": "123456789",
            "zip_code": "90210",
        },
        headers=headers,
    )
    assert response.status_code == 201


def test_list_payees_only_returns_own(client, auth_headers):
    headers_a = auth_headers(email="payeelista@example.com")
    headers_b = auth_headers(email="payeelistb@example.com")
    client.post(
        "/payees",
        json={
            "payee_type": "person",
            "pay_method": "zelle",
            "nickname": "A's friend",
            "contact_identifier": "friend@example.com",
        },
        headers=headers_a,
    )

    response = client.get("/payees", headers=headers_b)
    assert response.status_code == 200
    assert response.json() == []

    response_a = client.get("/payees", headers=headers_a)
    assert len(response_a.json()) == 1
