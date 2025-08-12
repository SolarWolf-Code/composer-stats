"""Composer Stats API package."""

# Ensure FastMCP dependency uses our header source when present
try:  # noqa: SIM105
    from .compat.fastmcp_override import ensure_fastmcp_header_override

    ensure_fastmcp_header_override()
except Exception:  # pragma: no cover - optional dependency
    pass

__all__ = [
    "__version__",
]

__version__ = "0.3.0"


