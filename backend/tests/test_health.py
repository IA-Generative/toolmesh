from httpx import ASGITransport, AsyncClient

from app.main import app
from app.version import get_version


async def test_health_returns_ok_status_and_version() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": get_version()}
