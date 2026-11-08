"""Environment-driven configuration for the Mealie MCP server.

All configuration comes from environment variables so the server can be run
unchanged inside a Docker container. The only required value is at least one
static bearer token used to gate the MCP HTTP endpoint.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


def _split_tokens(raw: str | None) -> list[str]:
    """Parse a comma-separated list of bearer tokens, ignoring blanks."""
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Default header carrying the per-request Mealie API token. Each MCP client
# supplies its own Mealie token here so a single server can serve multiple
# Mealie users. Override with MEALIE_TOKEN_HEADER for clients that can only send
# a fixed set of header names (e.g. claude.ai custom connectors, which offer
# names such as ``x-api-key`` or ``x-auth-token``).
MEALIE_TOKEN_HEADER = "x-mealie-token"

# Default header for the optional per-request Mealie base URL override
# (multi-instance setups). Override with MEALIE_URL_HEADER.
MEALIE_URL_HEADER = "x-mealie-url"

# Header the MCP endpoint's static bearer gate reads. The Mealie headers must
# not reuse it, or the gate token would be forwarded to Mealie (and vice versa).
_GATE_HEADER = "authorization"

# RFC 9110 field-name ("token") characters.
_HEADER_NAME_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


def _normalize_header_name(name: str, env_var: str) -> str:
    """Validate an HTTP header name and return it lower-cased.

    Header lookups are case-insensitive, and Starlette exposes them lower-cased,
    so storing the canonical lower-case form keeps comparisons simple.
    """
    cleaned = name.strip()
    if not cleaned or not _HEADER_NAME_RE.match(cleaned):
        raise RuntimeError(
            f"{env_var}={name!r} is not a valid HTTP header name. Use letters, "
            "digits and '-' (e.g. 'x-api-key')."
        )
    lowered = cleaned.lower()
    if lowered == _GATE_HEADER:
        raise RuntimeError(
            f"{env_var} cannot be 'Authorization': that header carries the "
            "MCP_AUTH_TOKEN gate for this server. Pick another name, such as "
            "'x-api-key' or 'x-auth-token'."
        )
    return lowered


@dataclass(frozen=True)
class Settings:
    """Resolved server settings."""

    # Static bearer token(s) accepted on the MCP endpoint's Authorization header.
    auth_tokens: list[str] = field(default_factory=list)

    # Default Mealie base URL (e.g. https://mealie.example.com). May be overridden
    # per request via the Mealie URL header (default X-Mealie-Url). Required if
    # the header is not sent.
    mealie_base_url: str | None = None

    # HTTP server bind settings (inside the container).
    host: str = "0.0.0.0"
    port: int = 8000
    path: str = "/mcp"

    # Outbound HTTP behaviour when talking to Mealie.
    request_timeout: float = 30.0
    verify_ssl: bool = True

    # When True (default) only read tools are registered. Set MEALIE_READONLY=false
    # to also expose write tools (create/update/delete). Note that the per-request
    # Mealie token's own permissions still apply, so a read-only Mealie token can
    # never mutate data regardless of this flag.
    read_only: bool = True

    log_level: str = "info"

    # When True, log a masked diagnostic for every request reaching the auth gate
    # (whether an Authorization header arrived, its scheme, the token length and a
    # non-reversible fingerprint vs. the configured tokens). Off by default; turn
    # on with MCP_AUTH_DEBUG=true to troubleshoot 401s without leaking secrets.
    auth_debug: bool = False

    # Request header names carrying the per-request Mealie token and the
    # optional base-URL override. Stored lower-cased; validated on construction.
    mealie_token_header: str = MEALIE_TOKEN_HEADER
    mealie_url_header: str = MEALIE_URL_HEADER

    def __post_init__(self) -> None:
        token_header = _normalize_header_name(
            self.mealie_token_header, "MEALIE_TOKEN_HEADER"
        )
        url_header = _normalize_header_name(self.mealie_url_header, "MEALIE_URL_HEADER")
        if token_header == url_header:
            raise RuntimeError(
                f"MEALIE_TOKEN_HEADER and MEALIE_URL_HEADER must differ (both are "
                f"'{token_header}')."
            )
        # Frozen dataclass: assign the normalised values via object.__setattr__.
        object.__setattr__(self, "mealie_token_header", token_header)
        object.__setattr__(self, "mealie_url_header", url_header)

    @classmethod
    def from_env(cls) -> Settings:
        tokens = _split_tokens(os.getenv("MCP_AUTH_TOKEN"))
        if not tokens:
            raise RuntimeError(
                "MCP_AUTH_TOKEN is required: set it to one or more comma-separated "
                "secret bearer tokens that MCP clients must present in the "
                "'Authorization: Bearer <token>' header."
            )

        base_url = os.getenv("MEALIE_BASE_URL")
        if base_url:
            base_url = base_url.rstrip("/")

        return cls(
            auth_tokens=tokens,
            mealie_base_url=base_url,
            host=os.getenv("MCP_HOST", "0.0.0.0"),
            port=int(os.getenv("MCP_PORT", "8000")),
            path=os.getenv("MCP_PATH", "/mcp"),
            request_timeout=float(os.getenv("MEALIE_TIMEOUT", "30")),
            verify_ssl=_env_bool("MEALIE_VERIFY_SSL", True),
            read_only=_env_bool("MEALIE_READONLY", True),
            log_level=os.getenv("MCP_LOG_LEVEL", "info"),
            auth_debug=_env_bool("MCP_AUTH_DEBUG", False),
            mealie_token_header=os.getenv("MEALIE_TOKEN_HEADER") or MEALIE_TOKEN_HEADER,
            mealie_url_header=os.getenv("MEALIE_URL_HEADER") or MEALIE_URL_HEADER,
        )
