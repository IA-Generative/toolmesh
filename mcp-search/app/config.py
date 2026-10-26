from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_SEARCH_", extra="ignore")

    # Base URL of the SearXNG instance; it must allow the `json` output format.
    searxng_url: str = "http://localhost:8888"
    timeout_seconds: float = 15
    # `fetch_page` downloads URLs chosen by the caller: loopback, private and link-local addresses are refused
    # unless this is set (link-local ones, e.g. cloud metadata, never pass).
    allow_private_hosts: bool = False
    max_fetch_bytes: int = 2_000_000
