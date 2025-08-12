from __future__ import annotations

from typing import Any


_installed = False


def ensure_fastmcp_header_override() -> None:
    global _installed
    if _installed:
        return
    try:
        from fastmcp.server import dependencies as _fastmcp_dependencies  # type: ignore
        from ..deps.auth_headers import headers_from_env_or_ctx

        _fastmcp_dependencies.get_http_headers = (
            lambda include_all=False: headers_from_env_or_ctx()
        )  # type: ignore[attr-defined]
        _installed = True
    except Exception:
        # If fastmcp is not available, skip. The MCP client will import fine.
        _installed = True


