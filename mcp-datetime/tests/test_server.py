from mcp.client import Client

from app.server import add_business_days, add_to_date, business_days, date_diff, mcp, period_bounds, weekday


def test_add_month_clamps_to_month_end() -> None:
    assert add_to_date("2024-01-31", 1, "months") == "2024-02-29"
    assert add_to_date("2024-02-29", 1, "years") == "2025-02-28"
    assert add_to_date("2024-03-10", -2, "weeks") == "2024-02-25"


def test_date_diff() -> None:
    result = date_diff("2024-01-31", "2025-03-01")
    assert result["total_days"] == 395
    assert result["calendar"] == {"sign": 1, "years": 1, "months": 1, "days": 1}
    assert date_diff("2024-03-01", "2024-02-01")["total_days"] == -29


def test_period_bounds() -> None:
    assert period_bounds("2024-05-15", "quarter") == {"start": "2024-04-01", "end": "2024-06-30", "days": 91}
    assert period_bounds("2024-05-15", "week")["start"] == "2024-05-13"
    assert period_bounds("2024-02-10", "month")["end"] == "2024-02-29"


def test_weekday() -> None:
    assert weekday("2024-02-29")["weekday"] == "Thursday"


def test_business_days() -> None:
    assert business_days("2024-05-13", "2024-05-19") == 5
    assert business_days("2024-05-13", "2024-05-19", ["2024-05-16"]) == 4
    assert add_business_days("2024-05-17", 1) == "2024-05-20"
    assert add_business_days("2024-05-20", -1) == "2024-05-17"


async def test_tools_are_exposed_over_mcp() -> None:
    async with Client(mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        result = await client.call_tool("add_to_date", {"date_iso": "2024-01-31", "amount": 1, "unit": "months"})
    assert {"now", "convert_timezone", "period_bounds", "business_days"} <= names
    assert "2024-02-29" in str(result.content)


async def test_endpoint_rejects_requests_without_token(monkeypatch) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.server import create_app

    monkeypatch.setenv("MCP_DATETIME_OIDC_JWKS_URL", "http://unused.test/certs")
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        response = await client.post("/mcp", json={})
    assert response.status_code == 401
