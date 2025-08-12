from __future__ import annotations

from typing import Any, Dict, List

from composer_trade_mcp.server import (
    list_accounts,
    get_aggregate_symphony_stats,
    get_symphony_daily_performance,
)


async def fetch_default_account_uuid() -> str:
    accounts = await list_accounts.fn()  # type: ignore[attr-defined]
    if isinstance(accounts, dict) and accounts.get("error"):
        msg = accounts.get("response") or "Error fetching accounts"
        raise RuntimeError(msg)
    if not accounts:
        raise RuntimeError("No accounts found")
    return accounts[0]["account_uuid"]


async def fetch_symphonies(account_uuid: str) -> List[Dict[str, Any]]:
    agg = await get_aggregate_symphony_stats.fn(account_uuid)  # type: ignore[attr-defined]
    if isinstance(agg, dict) and agg.get("error"):
        msg = agg.get("response") or "Error fetching account symphonies"
        raise RuntimeError(msg)
    if isinstance(agg, dict) and "symphonies" in agg and isinstance(agg["symphonies"], list):
        return agg["symphonies"]
    if isinstance(agg, list):
        return agg
    return []


async def fetch_symphony_daily_performance(account_uuid: str, symphony_id: str) -> Dict[str, Any]:
    perf = await get_symphony_daily_performance.fn(account_uuid, symphony_id)  # type: ignore[attr-defined]
    if isinstance(perf, dict):
        return perf
    return {}


