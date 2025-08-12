from __future__ import annotations

import base64
from contextvars import ContextVar
from typing import Dict, Optional

from fastapi import Request


_request_headers_ctx: ContextVar[Optional[Dict[str, str]]] = ContextVar(
    "_request_headers_ctx", default=None
)


def set_ctx_headers(headers: Optional[Dict[str, str]]) -> None:
    _request_headers_ctx.set(headers)


def headers_from_env_or_ctx() -> dict:
    # Only use per-request context (no environment variable fallbacks)
    headers: dict[str, str] = {}
    req_headers = _request_headers_ctx.get()
    if isinstance(req_headers, dict):
        headers.update(req_headers)
    return headers


def apply_request_headers(request: Request) -> None:
    auth = request.headers.get("authorization")
    env = request.headers.get("x-composer-mcp-environment")
    if auth:
        hdrs: Dict[str, str] = {"authorization": auth}
        if env:
            hdrs["x-composer-mcp-environment"] = env
        set_ctx_headers(hdrs)
        return
    api_key_id = request.headers.get("x-api-key-id")
    api_secret = request.headers.get("x-api-secret")
    if api_key_id and api_secret:
        try:
            basic = base64.b64encode(f"{api_key_id}:{api_secret}".encode("utf-8")).decode("utf-8")
            hdrs = {"authorization": f"Basic {basic}"}
            if env:
                hdrs["x-composer-mcp-environment"] = env
            set_ctx_headers(hdrs)
            return
        except Exception:
            pass
    set_ctx_headers(None)


