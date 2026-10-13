from pydantic import BaseModel, Field


class User(BaseModel):
    """Caller identity extracted from a validated access token."""

    sub: str
    username: str | None = None
    email: str | None = None
    roles: list[str] = []
    # Raw bearer token, kept so it can be exchanged for downstream calls. Never serialized.
    token: str | None = Field(default=None, exclude=True, repr=False)

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles
