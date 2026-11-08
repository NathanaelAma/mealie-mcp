"""Tests for environment-driven configuration."""

from __future__ import annotations

import pytest

from mealie_mcp.config import Settings, _env_bool, _split_tokens


def test_split_tokens_handles_blanks_and_spacing():
    assert _split_tokens("a, b ,,c ") == ["a", "b", "c"]
    assert _split_tokens("") == []
    assert _split_tokens(None) == []


@pytest.mark.parametrize(
    "raw,expected",
    [("true", True), ("1", True), ("YES", True), ("on", True),
     ("false", False), ("0", False), ("nope", False)],
)
def test_env_bool(monkeypatch, raw, expected):
    monkeypatch.setenv("SOME_FLAG", raw)
    assert _env_bool("SOME_FLAG", default=True) is expected


def test_env_bool_default_when_unset(monkeypatch):
    monkeypatch.delenv("SOME_FLAG", raising=False)
    assert _env_bool("SOME_FLAG", default=True) is True


def test_from_env_requires_auth_token(monkeypatch):
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="MCP_AUTH_TOKEN"):
        Settings.from_env()


def test_from_env_parses_values(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "tok1, tok2")
    monkeypatch.setenv("MEALIE_BASE_URL", "https://mealie.example.com/")
    monkeypatch.setenv("MEALIE_READONLY", "false")
    monkeypatch.setenv("MCP_PORT", "9000")
    settings = Settings.from_env()
    assert settings.auth_tokens == ["tok1", "tok2"]
    assert settings.mealie_base_url == "https://mealie.example.com"  # trailing slash stripped
    assert settings.read_only is False
    assert settings.port == 9000
    assert settings.auth_debug is False  # default when MCP_AUTH_DEBUG unset


def test_from_env_parses_auth_debug(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "tok")
    monkeypatch.setenv("MCP_AUTH_DEBUG", "true")
    assert Settings.from_env().auth_debug is True


def test_from_env_defaults_to_read_only(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "tok")
    monkeypatch.delenv("MEALIE_READONLY", raising=False)
    assert Settings.from_env().read_only is True


def test_header_names_default(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "tok")
    monkeypatch.delenv("MEALIE_TOKEN_HEADER", raising=False)
    monkeypatch.delenv("MEALIE_URL_HEADER", raising=False)
    settings = Settings.from_env()
    assert settings.mealie_token_header == "x-mealie-token"
    assert settings.mealie_url_header == "x-mealie-url"


def test_header_names_from_env_are_normalised(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "tok")
    monkeypatch.setenv("MEALIE_TOKEN_HEADER", "  X-API-Key ")
    monkeypatch.setenv("MEALIE_URL_HEADER", "X-Target-Url")
    settings = Settings.from_env()
    assert settings.mealie_token_header == "x-api-key"
    assert settings.mealie_url_header == "x-target-url"


def test_blank_header_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "tok")
    monkeypatch.setenv("MEALIE_TOKEN_HEADER", "")
    assert Settings.from_env().mealie_token_header == "x-mealie-token"


@pytest.mark.parametrize("name", ["Authorization", "authorization", " AUTHORIZATION "])
def test_token_header_cannot_be_authorization(name):
    with pytest.raises(RuntimeError, match="Authorization"):
        Settings(auth_tokens=["tok"], mealie_token_header=name)


def test_url_header_cannot_be_authorization():
    with pytest.raises(RuntimeError, match="MEALIE_URL_HEADER"):
        Settings(auth_tokens=["tok"], mealie_url_header="Authorization")


@pytest.mark.parametrize("name", ["   ", "x api key", "x-api-key:", "x\napi", "tök"])
def test_invalid_header_names_rejected(name):
    with pytest.raises(RuntimeError, match="not a valid HTTP header name"):
        Settings(auth_tokens=["tok"], mealie_token_header=name)


def test_token_and_url_headers_must_differ():
    with pytest.raises(RuntimeError, match="must differ"):
        Settings(
            auth_tokens=["tok"],
            mealie_token_header="X-Api-Key",
            mealie_url_header="x-api-key",
        )
