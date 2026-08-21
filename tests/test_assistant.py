from app.config import settings
from app.services import assistant_service


class FakeBlock:
    def __init__(self, type, text=None, id=None, name=None, input=None):
        self.type = type
        self.text = text
        self.id = id
        self.name = name
        self.input = input or {}


class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class FakeMessages:
    def __init__(self, responses):
        self._responses = iter(responses)

    def create(self, **kwargs):
        return next(self._responses)


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


def _stub_client(monkeypatch, responses):
    monkeypatch.setattr(assistant_service, "_get_client", lambda: FakeClient(responses))


def _create_account(client, headers, account_type="checking", initial_deposit=None):
    payload = {"account_type": account_type}
    if initial_deposit is not None:
        payload["initial_deposit"] = initial_deposit
    response = client.post("/accounts", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_assistant_not_configured_without_api_key(client, auth_headers, monkeypatch):
    # Deterministic regardless of whatever a developer's local backend/.env
    # actually has configured — explicitly simulate the unconfigured state.
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    headers = auth_headers()
    response = client.post("/assistant/messages", json={"content": "Hi"}, headers=headers)
    assert response.status_code == 400
    assert "isn't configured" in response.json()["detail"]


def test_plain_text_reply_is_persisted(client, auth_headers, monkeypatch):
    headers = auth_headers()
    _stub_client(
        monkeypatch,
        [FakeResponse("end_turn", [FakeBlock("text", text="Hi there! How can I help?")])],
    )

    response = client.post("/assistant/messages", json={"content": "Hello"}, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "assistant"
    assert body["content"] == "Hi there! How can I help?"
    assert body["suggested_actions"] is None

    history = client.get("/assistant/messages", headers=headers).json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[0]["content"] == "Hello"


def test_tool_use_returns_real_account_data(client, auth_headers, monkeypatch):
    headers = auth_headers()
    account = _create_account(client, headers, initial_deposit="1234.56")

    _stub_client(
        monkeypatch,
        [
            FakeResponse(
                "tool_use",
                [FakeBlock("tool_use", id="t1", name="get_accounts", input={})],
            ),
            FakeResponse(
                "end_turn",
                [FakeBlock("text", text=f"Your checking balance is $1234.56.")],
            ),
        ],
    )

    response = client.post(
        "/assistant/messages", json={"content": "What's my balance?"}, headers=headers
    )
    assert response.status_code == 201
    assert "1234.56" in response.json()["content"]


def test_suggest_action_is_attached_to_reply(client, auth_headers, monkeypatch):
    headers = auth_headers()
    _stub_client(
        monkeypatch,
        [
            FakeResponse(
                "tool_use",
                [
                    FakeBlock(
                        "tool_use",
                        id="t1",
                        name="suggest_action",
                        input={"path": "/transfer-money", "label": "Go to Transfer"},
                    )
                ],
            ),
            FakeResponse(
                "end_turn",
                [FakeBlock("text", text="Head to the Transfer page to send money.")],
            ),
        ],
    )

    response = client.post(
        "/assistant/messages", json={"content": "Send $50 to my savings"}, headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["suggested_actions"] == [{"label": "Go to Transfer", "path": "/transfer-money"}]


def test_suggest_action_rejects_invalid_path(client, auth_headers, monkeypatch):
    headers = auth_headers()
    _stub_client(
        monkeypatch,
        [
            FakeResponse(
                "tool_use",
                [
                    FakeBlock(
                        "tool_use", id="t1", name="suggest_action",
                        input={"path": "/not-a-real-page", "label": "Nope"},
                    )
                ],
            ),
            FakeResponse("end_turn", [FakeBlock("text", text="Okay.")]),
        ],
    )

    response = client.post("/assistant/messages", json={"content": "hi"}, headers=headers)
    assert response.status_code == 201
    assert response.json()["suggested_actions"] is None


def test_clear_messages(client, auth_headers, monkeypatch):
    headers = auth_headers()
    _stub_client(monkeypatch, [FakeResponse("end_turn", [FakeBlock("text", text="Hi!")])])
    client.post("/assistant/messages", json={"content": "Hello"}, headers=headers)

    delete_response = client.delete("/assistant/messages", headers=headers)
    assert delete_response.status_code == 204

    history = client.get("/assistant/messages", headers=headers).json()
    assert history == []


def test_chat_history_is_scoped_per_user(client, auth_headers, monkeypatch):
    headers_a = auth_headers(email="a@example.com")
    headers_b = auth_headers(email="b@example.com")

    _stub_client(monkeypatch, [FakeResponse("end_turn", [FakeBlock("text", text="Hi A!")])])
    client.post("/assistant/messages", json={"content": "Hello from A"}, headers=headers_a)

    history_b = client.get("/assistant/messages", headers=headers_b).json()
    assert history_b == []
