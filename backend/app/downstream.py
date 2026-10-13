"""Mock downstream service: only accepts tokens whose audience is its own (set TOOLMESH_OIDC_AUDIENCE)."""

from fastapi import FastAPI

from app.auth import CurrentUser

app = FastAPI(title="mock downstream service")


@app.get("/whoami")
async def whoami(user: CurrentUser) -> dict:
    return {"service": "downstream", "sub": user.sub, "username": user.username, "roles": user.roles}
