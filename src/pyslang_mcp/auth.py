"""Small authentication helpers for HTTP deployments."""

from __future__ import annotations

from hmac import compare_digest

from mcp.server.auth.provider import AccessToken


class StaticBearerTokenVerifier:
    """Validate one static bearer token for simple internal deployments."""

    def __init__(self, token: str, *, client_id: str = "pyslang-mcp-internal") -> None:
        stripped = token.strip()
        if not stripped:
            raise ValueError("Bearer token must not be empty.")
        self._token = stripped
        self._client_id = client_id

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return access info when the supplied bearer token matches."""

        if not compare_digest(token, self._token):
            return None
        return AccessToken(
            token=token,
            client_id=self._client_id,
            scopes=["pyslang-mcp"],
        )
