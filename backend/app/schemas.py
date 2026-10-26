from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_.:-]{1,100}$")]
SourceType = Literal["mcp", "api", "skill"]
# `token_exchange`: the caller's token is exchanged for one targeting `audience`. `none`: public service.
AuthMode = Literal["token_exchange", "none"]


class ToolIn(BaseModel):
    name: Name
    description: str = ""
    tags: list[str] = []
    method: str | None = None
    path: str | None = None
    input_schema: dict[str, Any] | None = None
    # Name on the server when `name` was changed to be unique; set by the discovery, not by clients.
    remote_name: str | None = None


class SourceIn(BaseModel):
    name: Name
    type: SourceType
    description: str | None = None
    url: str | None = None
    openapi_url: str | None = None
    auth_mode: AuthMode = "none"
    audience: str | None = None
    endpoint_include: list[str] = []
    endpoint_exclude: list[str] = []
    required_role: str | None = None
    tags: list[str] = []
    # Tools declared by hand until they are discovered from the server or the OpenAPI spec.
    tools: list[ToolIn] = []

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.type == "skill":
            if not (self.description and self.description.strip()):
                raise ValueError("a skill needs a description")
            if len(self.tools) > 1:
                raise ValueError("a skill is a single tool")
            self.url = self.openapi_url = self.audience = None
            self.auth_mode = "none"
            self.endpoint_include, self.endpoint_exclude = [], []
            return self
        if not self.url:
            raise ValueError("url is required")
        if self.type == "api" and not self.openapi_url:
            raise ValueError("openapi_url is required for an API")
        if self.type == "mcp":
            self.openapi_url = None
            self.endpoint_include, self.endpoint_exclude = [], []
        if self.auth_mode == "token_exchange" and not self.audience:
            raise ValueError("audience is required for token exchange")
        if self.auth_mode == "none":
            self.audience = None
        return self


class ToolOut(BaseModel):
    """A tool as listed to a caller (flattened with its source)."""

    name: str
    description: str
    source: str
    type: SourceType
    tags: list[str] = []
    source_url: str | None = None
    method: str | None = None
    path: str | None = None
    input_schema: dict[str, Any] | None = None
    # How the source is called: `token_exchange` (with its `audience`) or `none` (public).
    auth_mode: AuthMode = "none"
    audience: str | None = None
    # Role required to see the tool; None means any authenticated caller.
    required_role: str | None = None


class SourceToolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    tags: list[str]
    method: str | None
    path: str | None
    input_schema: dict[str, Any] | None
    enabled: bool


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: SourceType
    description: str | None
    url: str | None
    openapi_url: str | None
    auth_mode: AuthMode
    audience: str | None
    endpoint_include: list[str]
    endpoint_exclude: list[str]
    required_role: str | None
    created_by: str
    created_at: datetime
    tools: list[SourceToolOut] = Field(default_factory=list)
