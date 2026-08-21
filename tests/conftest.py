import itertools

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.services import address_service, email_service, zipcode_service
from fastapi.testclient import TestClient

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def disable_real_email_sending(monkeypatch):
    # Tests must never depend on live external services, regardless of what
    # SMTP credentials happen to be configured in a developer's local .env.
    monkeypatch.setattr(email_service, "send_email", lambda *args, **kwargs: (False, None))


@pytest.fixture(autouse=True)
def stub_zip_code_lookup(monkeypatch):
    # Tests must never depend on the real Zippopotam.us API — deterministic
    # "found" result for any well-formed zip by default. Individual tests
    # can monkeypatch this again to exercise the "not found" path.
    def _fake_lookup(zip_code: str) -> dict:
        return {
            "service_available": True,
            "found": True,
            "zip_code": zip_code.split("-")[0],
            "city": "Testville",
            "state": "Test State",
            "state_abbreviation": "TS",
        }

    monkeypatch.setattr(zipcode_service, "lookup_zip_code", _fake_lookup)


@pytest.fixture(autouse=True)
def stub_address_search(monkeypatch):
    # Tests must never depend on the real Nominatim/OpenStreetMap API —
    # deterministic single-result response for any query long enough to
    # search. Individual tests can monkeypatch this again for other cases.
    def _fake_search(query: str, limit: int = 5) -> dict:
        if len(query.strip()) < 5:
            return {"service_available": True, "results": []}
        return {
            "service_available": True,
            "results": [
                {
                    "display_name": f"{query}, Testville, Test State, 00000, United States",
                    "street": query,
                    "city": "Testville",
                    "state": "Test State",
                    "state_abbreviation": "TS",
                    "zip_code": "00000",
                }
            ],
        }

    monkeypatch.setattr(address_service, "search_addresses", _fake_search)


@pytest.fixture()
def db_session():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client, db_session):
    phone_counter = itertools.count(1)

    def _make_user(
        email: str = "user@example.com",
        password: str = "password123",
        phone_number: str | None = None,
    ):
        if phone_number is None:
            phone_number = f"555555{next(phone_counter):04d}"
        client.post(
            "/auth/signup",
            json={
                "email": email,
                "password": password,
                "full_name": "Test User",
                "phone_number": phone_number,
            },
        )
        # Bypass real OTP verification and give the user a complete profile
        # in tests, same spirit as disable_real_email_sending bypassing real
        # SMTP — tests that exercise accounts/transfers/etc. shouldn't have
        # to know about signup verification or account-opening requirements
        # to get a usable, funded-capable test user.
        user = db_session.query(User).filter(User.email == email).first()
        user.is_verified = True
        user.address = "123 Test St, Testville, TS 00000"
        user.government_id_last4 = "1234"
        db_session.commit()

        response = client.post("/auth/login", json={"identifier": email, "password": password})
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make_user


@pytest.fixture()
def get_otp_code(client):
    # Shared helper for the step-up-verification flows (Zelle/Bill Pay/
    # external transfer) — requests a real code through the same endpoint
    # the frontend uses, and returns the demo_code (email isn't actually
    # sent in tests, per disable_real_email_sending).
    def _get(identifier: str, channel: str = "email") -> str:
        response = client.post(
            "/auth/otp/request", json={"identifier": identifier, "channel": channel}
        )
        return response.json()["demo_code"]

    return _get
