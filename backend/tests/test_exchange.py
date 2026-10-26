from typing import Any

import pytest
from fastapi import HTTPException

from app.auth.exchange import ACCESS_TOKEN_TYPE, TOKEN_EXCHANGE_GRANT, exchange_token
from app.config import Settings

SETTINGS = Settings(
    keycloak_url="http://kc.test", keycloak_realm="r", keycloak_client_id="c", keycloak_client_secret="s"
)


class _Response:
    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self._body = body
        self.text = str(body)

    def json(self) -> Any:
        if not isinstance(self._body, dict):
            raise ValueError("not json")
        return self._body


def fake_client(response: _Response, sent: dict[str, Any]) -> type:
    class _Client:
        def __init__(self, **_: Any) -> None: ...

        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *_: Any) -> None: ...

        async def post(self, url: str, data: dict[str, str]) -> _Response:
            sent.update(url=url, data=data)
            return response

    return _Client


async def test_exchange_sends_a_standard_token_exchange_request(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, Any] = {}
    monkeypatch.setattr(
        "app.auth.exchange.httpx.AsyncClient", fake_client(_Response(200, {"access_token": "new"}), sent)
    )

    assert await exchange_token(SETTINGS, "subject", "mcp-datetime") == "new"

    assert sent["url"] == "http://kc.test/realms/r/protocol/openid-connect/token"
    assert sent["data"] == {
        "grant_type": TOKEN_EXCHANGE_GRANT,
        "client_id": "c",
        "client_secret": "s",
        "subject_token": "subject",
        "subject_token_type": ACCESS_TOKEN_TYPE,
        "requested_token_type": ACCESS_TOKEN_TYPE,
        "audience": "mcp-datetime",
    }  # no `requested_subject`: Keycloak rejects it for a standard exchange


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            {"error": "invalid_request", "error_description": "Requested audience not available: x"},
            "Requested audience",
        ),
        ({"error": "access_denied"}, "access_denied"),
        ("<html>", "<html>"),
    ],
    ids=["description", "error-only", "not-json"],
)
async def test_exchange_failures_report_keycloak_reason(
    monkeypatch: pytest.MonkeyPatch, body: Any, expected: str
) -> None:
    monkeypatch.setattr("app.auth.exchange.httpx.AsyncClient", fake_client(_Response(400, body), {}))

    with pytest.raises(HTTPException) as exc:
        await exchange_token(SETTINGS, "subject", "x")

    assert exc.value.status_code == 502
    assert expected in exc.value.detail
