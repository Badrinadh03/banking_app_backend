import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal

TODAY = datetime.utcnow().date()


def _create_account(client, headers, account_type="checking"):
    return client.post("/accounts", json={"account_type": account_type}, headers=headers).json()


def test_download_requires_auth(client, auth_headers):
    headers = auth_headers()
    account = _create_account(client, headers)
    response = client.get(
        "/statements/download",
        params={"account_id": account["id"], "start": str(TODAY), "end": str(TODAY)},
    )
    assert response.status_code == 401


def test_download_rejects_unowned_account(client, auth_headers):
    headers_a = auth_headers(email="stmta@example.com")
    headers_b = auth_headers(email="stmtb@example.com")
    account_a = _create_account(client, headers_a)

    response = client.get(
        "/statements/download",
        params={"account_id": account_a["id"], "start": str(TODAY), "end": str(TODAY)},
        headers=headers_b,
    )
    assert response.status_code == 403


def test_download_pdf_has_correct_content_type_and_body(client, auth_headers):
    headers = auth_headers(email="stmtpdf@example.com")
    account = _create_account(client, headers)
    client.post(f"/accounts/{account['id']}/deposit", json={"amount": "50.00"}, headers=headers)

    response = client.get(
        "/statements/download",
        params={
            "account_id": account["id"],
            "start": str(TODAY - timedelta(days=1)),
            "end": str(TODAY),
            "format": "pdf",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 500
    assert "attachment" in response.headers["content-disposition"]


def test_download_csv_rows_match_transactions_in_range(client, auth_headers):
    headers = auth_headers(email="stmtcsv@example.com")
    account = _create_account(client, headers)
    client.post(
        f"/accounts/{account['id']}/deposit",
        json={"amount": "75.00", "description": "Paycheck"},
        headers=headers,
    )

    response = client.get(
        "/statements/download",
        params={
            "account_id": account["id"],
            "start": str(TODAY - timedelta(days=1)),
            "end": str(TODAY),
            "format": "csv",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    rows = list(csv.reader(io.StringIO(response.text)))
    flattened = [cell for row in rows for cell in row]
    assert "Paycheck" in flattened
    assert "deposit" in flattened
    assert any("75.00" in cell for cell in flattened)


def test_download_excludes_transaction_outside_date_range(client, auth_headers, db_session):
    from app.models.transaction import Transaction

    headers = auth_headers(email="stmtrange@example.com")
    account = _create_account(client, headers)
    client.post(
        f"/accounts/{account['id']}/deposit",
        json={"amount": "20.00", "description": "Recent deposit"},
        headers=headers,
    )

    # Backdate an old transaction that should fall outside the requested range.
    old_tx = Transaction(
        from_account_id=None,
        to_account_id=account["id"],
        amount=Decimal("999.00"),
        transaction_type="deposit",
        status="completed",
        description="Ancient deposit",
    )
    db_session.add(old_tx)
    db_session.commit()
    old_tx.created_at = datetime.utcnow() - timedelta(days=100)
    db_session.commit()

    response = client.get(
        "/statements/download",
        params={
            "account_id": account["id"],
            "start": str(TODAY - timedelta(days=1)),
            "end": str(TODAY),
            "format": "csv",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert "Recent deposit" in response.text
    assert "Ancient deposit" not in response.text


def test_download_all_accounts_when_account_id_omitted(client, auth_headers):
    headers = auth_headers(email="stmtall@example.com")
    checking = _create_account(client, headers, "checking")
    savings = _create_account(client, headers, "savings")
    client.post(f"/accounts/{checking['id']}/deposit", json={"amount": "10.00"}, headers=headers)
    client.post(f"/accounts/{savings['id']}/deposit", json={"amount": "20.00"}, headers=headers)

    response = client.get(
        "/statements/download",
        params={"start": str(TODAY - timedelta(days=1)), "end": str(TODAY), "format": "csv"},
        headers=headers,
    )
    assert response.status_code == 200
    assert "All Accounts" in response.text


def test_download_rejects_end_before_start(client, auth_headers):
    headers = auth_headers(email="stmtbaddate@example.com")
    account = _create_account(client, headers)
    response = client.get(
        "/statements/download",
        params={"account_id": account["id"], "start": str(TODAY), "end": str(TODAY - timedelta(days=5))},
        headers=headers,
    )
    assert response.status_code == 400
