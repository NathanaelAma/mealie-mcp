"""Client behaviour when the Mealie header names are customised.

Overrides the shared ``settings`` fixture so the server reads the Mealie token
from ``X-Api-Key`` (as a claude.ai custom connector would send it) and the base
URL override from ``X-Target-Url``.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp.exceptions import ToolError

from mealie_mcp import client as mclient
from mealie_mcp.config import Settings
from tests.conftest import BASE_URL


@pytest.fixture
def settings() -> Settings:
    return Settings(
        auth_tokens=["mcp-token"],
        mealie_base_url=BASE_URL,
        mealie_token_header="X-Api-Key",
        mealie_url_header="X-Target-Url",
    )


async def test_token_read_from_custom_header(configured):
    configured["headers"] = {"x-api-key": "custom-tok"}
    with respx.mock:
        route = respx.get(f"{BASE_URL}/api/recipes").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        await mclient.mealie_get("/api/recipes")
    assert route.calls.last.request.headers["authorization"] == "Bearer custom-tok"


async def test_default_header_ignored_when_customised(configured):
    """Only the configured header is honoured; X-Mealie-Token is not a fallback."""
    configured["headers"] = {"x-mealie-token": "tok"}
    with pytest.raises(ToolError, match="'x-api-key' header"):
        await mclient.mealie_get("/api/recipes")


async def test_url_override_read_from_custom_header(configured):
    configured["headers"] = {"x-api-key": "tok", "x-target-url": "https://other.test/"}
    with respx.mock:
        route = respx.get("https://other.test/api/app/about").mock(
            return_value=httpx.Response(200, json={"version": "1.0"})
        )
        await mclient.mealie_get("/api/app/about")
    assert route.called


async def test_401_message_names_custom_header(configured):
    configured["headers"] = {"x-api-key": "tok"}
    with respx.mock:
        respx.get(f"{BASE_URL}/api/recipes").mock(return_value=httpx.Response(401))
        with pytest.raises(ToolError, match="'x-api-key' header value"):
            await mclient.mealie_get("/api/recipes")
