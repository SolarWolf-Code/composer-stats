from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request

from ..clients.composer_mcp import (
    fetch_default_account_uuid,
    fetch_symphonies,
    fetch_symphony_daily_performance,
    fetch_account_holdings_symbols,
    fetch_portfolio_stats,
    fetch_portfolio_daily_performance,
)
from composer_trade_mcp.server import backtest_symphony_by_id
from ..deps.auth_headers import (
    apply_request_headers,
    headers_from_env_or_ctx,
    set_ctx_headers,
)
from ..services.performance_calc import (
    compute_lookback_return,
    compute_stats_from_series,
    fetch_spy_closes,
    fetch_spy_metrics,
    calculate_var_95_historical,
    calculate_var_95_parametric,
    calculate_expected_shortfall,
    calculate_correlation,
    calculate_consistency_score,
)
from ..services.deviation_calc import compute_deviation_metrics
from ..services.performance_calc import compute_metrics_from_daily_returns

router = APIRouter()


async def get_performance_data(account_uuid: str, timeframe: str = "1y") -> Dict[str, Any]:
    """Helper function to get performance data for both portfolio and SPY"""
    # Calculate date range based on timeframe
    from datetime import datetime, timedelta
    end_date = datetime.now()
    if timeframe == "1y":
        start_date = end_date - timedelta(days=365)
    elif timeframe == "6m":
        start_date = end_date - timedelta(days=180)
    elif timeframe == "3m":
        start_date = end_date - timedelta(days=90)
    else:
        start_date = end_date - timedelta(days=365)  # Default to 1 year
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Fetch portfolio performance and SPY performance concurrently
    portfolio_task = asyncio.create_task(
        fetch_portfolio_daily_performance(account_uuid)
    )
    spy_task = asyncio.create_task(fetch_spy_closes(start_str, end_str))

    try:
        portfolio_performance, spy_performance = await asyncio.gather(
            portfolio_task, spy_task, return_exceptions=True
        )
    except Exception as e:
        raise RuntimeError(f"Failed to fetch performance data: {str(e)}")

    # Handle exceptions from individual tasks
    if isinstance(portfolio_performance, Exception):
        raise RuntimeError(f"Failed to fetch portfolio performance: {str(portfolio_performance)}")
    if isinstance(spy_performance, Exception):
        raise RuntimeError(f"Failed to fetch SPY performance: {str(spy_performance)}")

    if not portfolio_performance:
        raise RuntimeError("Failed to fetch portfolio performance")
    if not spy_performance:
        raise RuntimeError("Failed to fetch SPY performance")

    # Ensure portfolio_performance is a list of dicts
    if isinstance(portfolio_performance, dict) and "data" in portfolio_performance:
        portfolio_performance_data = portfolio_performance["data"]
    elif isinstance(portfolio_performance, list):
        portfolio_performance_data = portfolio_performance
    else:
        raise RuntimeError("Unexpected portfolio performance data format")

    # Process SPY performance data (Dict[str, float] format)
    if isinstance(spy_performance, dict):
        spy_performance_data = spy_performance
    else:
        raise RuntimeError("Unexpected SPY performance data format")

    # Align data by date and compute combined performance
    aligned_data = {}
    for item in portfolio_performance_data:
        date = item.get("date")
        if date:
            aligned_data[date] = {"portfolio": item.get("value")}

    # Add SPY data to aligned data
    for date_str, spy_value in spy_performance_data.items():
        if date_str in aligned_data:
            aligned_data[date_str]["sp500"] = spy_value

    # Convert to sorted list
    combined_data = [
        {"date": date, **values} for date, values in aligned_data.items()
    ]
    combined_data.sort(key=lambda x: x["date"])

    return {"data": combined_data}


@router.get("/performance")
async def get_performance(
    request: Request,
    account_uuid: str | None = None,
    start: str | None = None,
    end: str | None = None,
    _=Depends(apply_request_headers),
) -> Dict[str, Any]:
    headers = headers_from_env_or_ctx()
    if not isinstance(headers, dict) or not headers.get("authorization"):
        auth = request.headers.get("authorization")
        api_key_id = request.headers.get("x-api-key-id")
        api_secret = request.headers.get("x-api-secret")
        env = request.headers.get("x-composer-mcp-environment")
        if auth:
            hdrs: Dict[str, str] = {"authorization": auth}
            if env:
                hdrs["x-composer-mcp-environment"] = env
            set_ctx_headers(hdrs)
        elif api_key_id and api_secret:
            import base64

            try:
                basic = base64.b64encode(
                    f"{api_key_id}:{api_secret}".encode("utf-8")
                ).decode("utf-8")
                hdrs = {"authorization": f"Basic {basic}"}
                if env:
                    hdrs["x-composer-mcp-environment"] = env
                set_ctx_headers(hdrs)
            except Exception:
                pass

    # Fail fast with 401 if no credentials are present after attempting header extraction
    headers = headers_from_env_or_ctx()
    if not isinstance(headers, dict) or not headers.get("authorization"):
        raise HTTPException(
            status_code=401,
            detail="Missing Composer credentials. Provide Authorization: Basic ... or x-api-key-id/x-api-secret headers.",
        )

    if not account_uuid:
        try:
            account_uuid = await fetch_default_account_uuid()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    try:
        symphonies = await fetch_symphonies(account_uuid)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    sym_to_perf: Dict[str, Dict[str, Any]] = {}
    all_dates_set: set[str] = set()

    sem = asyncio.Semaphore(8)

    async def fetch_sym(sym_id: str) -> tuple[str, Dict[str, Any] | None]:
        async with sem:
            try:
                perf = await fetch_symphony_daily_performance(account_uuid, sym_id)
                sym_dates: List[str] = perf.get("dates", [])
                depo_series: List[float] = perf.get("deposit_adjusted_series", [])
                value_series: List[float] = perf.get("series", [])
                if not sym_dates or not depo_series:
                    return (sym_id, None)
                return (
                    sym_id,
                    {
                        "dates": sym_dates,
                        "depo": [float(x) for x in depo_series],
                        "value": (
                            [float(x) for x in value_series]
                            if value_series
                            else [None] * len(sym_dates)
                        ),
                        "date_index": {d: i for i, d in enumerate(sym_dates)},
                    },
                )
            except Exception:
                return (sym_id, None)

    tasks: List[asyncio.Task] = []
    for sym in symphonies:
        sym_id = sym.get("id") or sym.get("symphony_id") or sym.get("symphonyId")
        if sym_id:
            tasks.append(asyncio.create_task(fetch_sym(sym_id)))

    for sym_id, perf in await asyncio.gather(*tasks):
        if perf is None:
            continue
        sym_to_perf[sym_id] = perf
        all_dates_set.update(perf["dates"])

    dates: List[str] = sorted(all_dates_set)
    if not dates:
        raise HTTPException(status_code=404, detail="No performance data available")

    def _parse_date(s: str | None):
        if not s:
            return None
        try:
            from datetime import datetime

            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    start_d = _parse_date(start)
    end_d = _parse_date(end)
    if start_d or end_d:
        filtered: List[str] = []
        from datetime import datetime

        for ds in dates:
            try:
                d = datetime.strptime(ds, "%Y-%m-%d").date()
            except Exception:
                continue
            if (start_d is None or d >= start_d) and (end_d is None or d <= end_d):
                filtered.append(ds)
        if filtered:
            dates = filtered

    daily_returns: List[float] = [0.0] * len(dates)
    for idx in range(1, len(dates)):
        d_prev = dates[idx - 1]
        d_curr = dates[idx]
        weighted_sum = 0.0
        total_value_prev = 0.0
        for perf in sym_to_perf.values():
            di = perf["date_index"]
            if d_curr not in di or d_prev not in di:
                continue
            i_prev = di[d_prev]
            i_curr = di[d_curr]
            depo_prev = perf["depo"][i_prev]
            depo_curr = perf["depo"][i_curr]
            if depo_prev is None or depo_prev == 0:
                continue
            r_i = (depo_curr / depo_prev) - 1.0
            v_prev_list = perf["value"]
            v_prev = v_prev_list[i_prev] if i_prev < len(v_prev_list) else None
            if v_prev is None or v_prev <= 0:
                continue
            weighted_sum += v_prev * r_i
            total_value_prev += v_prev
        daily_returns[idx] = (
            (weighted_sum / total_value_prev) if total_value_prev > 0 else 0.0
        )

    series: List[float] = [10000.0]
    for idx in range(1, len(dates)):
        series.append(series[-1] * (1.0 + daily_returns[idx]))

    # Always override/append the current day using intraday deposit-adjusted values,
    # because Composer may zero-out today's daily point mid-session.
    intraday_return: float | None = None
    try:
        from datetime import date as _date

        today_str = _date.today().isoformat()

        # Build a quick lookup of current deposit-adjusted value and current total value per symphony from meta
        current_meta: Dict[str, Dict[str, float]] = {}
        # print(symphonies)
        for sym in symphonies:
            sym_id = sym.get("id") or sym.get("symphony_id") or sym.get("symphonyId")
            if not sym_id:
                continue
            depo_now = sym.get("deposit_adjusted_value")
            total_now = (
                sym.get("value") or sym.get("total_value") or sym.get("portfolio_value")
            )
            try:
                depo_now_f = float(depo_now) if depo_now is not None else None  # type: ignore[arg-type]
                total_now_f = float(total_now) if total_now is not None else None  # type: ignore[arg-type]
            except Exception:
                depo_now_f = None
                total_now_f = None
            if depo_now_f is not None and total_now_f is not None:
                current_meta[str(sym_id)] = {"depo": depo_now_f, "value": total_now_f}

        if current_meta and dates:
            # Determine the last fully completed day (yesterday or prior).
            last_completed = dates[-1]
            if last_completed == today_str and len(dates) >= 2:
                last_completed = dates[-2]

            weighted_sum_today = 0.0
            total_value_prev_today = 0.0
            for sym_id, perf in sym_to_perf.items():
                meta = current_meta.get(sym_id)
                if not meta:
                    continue
                di = perf.get("date_index", {})
                if last_completed not in di:
                    continue
                i_prev = di[last_completed]
                depo_prev = perf["depo"][i_prev]
                v_prev_list = perf.get("value", [])
                v_prev = v_prev_list[i_prev] if i_prev < len(v_prev_list) else None
                if depo_prev is None or depo_prev == 0 or v_prev is None or v_prev <= 0:
                    continue
                r_i_today = (meta["depo"] / float(depo_prev)) - 1.0
                weighted_sum_today += float(v_prev) * r_i_today
                total_value_prev_today += float(v_prev)

            if total_value_prev_today > 0:
                r_today = weighted_sum_today / total_value_prev_today
                intraday_return = r_today
                if dates and dates[-1] == today_str and len(series) >= 2:
                    # Override the existing last point for today
                    series[-1] = series[-2] * (1.0 + r_today)
                else:
                    # Append a fresh intraday point for today
                    dates.append(today_str)
                    series.append(series[-1] * (1.0 + r_today))
    except Exception:
        # If anything goes wrong, skip intraday augmentation silently
        pass

    from typing import Dict as _Dict

    data: List[_Dict[str, Any]] = []
    try:
        if dates:
            start_str = dates[0]
            end_str = dates[-1]
            spy_closes = await fetch_spy_closes(start_str, end_str)
            spy_values_scaled: Dict[str, float] = {}
            if spy_closes:
                first_spy_date = next((d for d in dates if d in spy_closes), None)
                if first_spy_date is not None:
                    spy0 = spy_closes[first_spy_date]
                    port0 = series[dates.index(first_spy_date)]
                    scale = (port0 / spy0) if spy0 else 1.0
                    for k, v in spy_closes.items():
                        spy_values_scaled[k] = v * scale
                else:
                    spy_values_scaled = dict(spy_closes)
            else:
                spy_values_scaled = {}
    except Exception:
        spy_closes = {}
        spy_values_scaled = {}

    normalized_portfolio: List[float] = series

    normalized_spy: List[float] = []
    current_spy = 10000.0
    prev_spy_close: float | None = None
    for dt in dates:
        close = spy_values_scaled.get(dt)  # type: ignore[name-defined]
        if close is None:
            normalized_spy.append(current_spy)
            continue
        if prev_spy_close is None or prev_spy_close <= 0:
            current_spy = 10000.0
        else:
            r = (close / prev_spy_close) - 1.0
            current_spy *= 1.0 + r
        normalized_spy.append(current_spy)
        prev_spy_close = close

    for idx, dt in enumerate(dates):
        data.append(
            {
                "date": dt[5:10],
                "portfolio": round(normalized_portfolio[idx]),
                "sp500": round(normalized_spy[idx]),
            }
        )

    # print(data)

    stats_core = compute_stats_from_series(data)
    port_values = [float(v) for v in normalized_portfolio]
    spy_values = [float(v) for v in normalized_spy]
    if intraday_return is not None:
        port_today = intraday_return
    elif len(port_values) >= 2 and port_values[-2] > 0:
        port_today = (port_values[-1] / port_values[-2]) - 1.0
    else:
        port_today = 0.0

    spy_today = 0.0
    spy_close_keys = sorted(spy_closes.keys()) if isinstance(spy_closes, dict) else []  # type: ignore[name-defined]
    if isinstance(spy_closes, dict) and len(spy_close_keys) >= 2:  # type: ignore[name-defined]
        last_key = spy_close_keys[-1]
        prev_key = spy_close_keys[-2]
        last_close = spy_closes[last_key]  # type: ignore[name-defined]
        prev_close = spy_closes[prev_key]  # type: ignore[name-defined]
        if prev_close > 0:
            spy_today = (last_close / prev_close) - 1.0
    else:
        spy_today = 0.0

    lookbacks = {
        "today": port_today,
        "7d": compute_lookback_return(dates, port_values, 7),
        "30d": compute_lookback_return(dates, port_values, 30),
        "90d": compute_lookback_return(dates, port_values, 90),
        "1y": compute_lookback_return(dates, port_values, 365),
        "total": (
            (port_values[-1] / port_values[0] - 1.0)
            if port_values and port_values[0] > 0
            else 0.0
        ),
    }
    lookbacks_spy = {
        "today": spy_today,
        "7d": compute_lookback_return(dates, spy_values, 7),
        "30d": compute_lookback_return(dates, spy_values, 30),
        "90d": compute_lookback_return(dates, spy_values, 90),
        "1y": compute_lookback_return(dates, spy_values, 365),
        "total": (
            (spy_values[-1] / spy_values[0] - 1.0)
            if spy_values and spy_values[0] > 0
            else 0.0
        ),
    }
    stats = {
        **stats_core,
        "lookbacks": {"portfolio": lookbacks, "sp500": lookbacks_spy},
    }
    return {"data": data, "stats": stats}


@router.get("/allocation")
async def get_allocation(
    request: Request,
    account_uuid: str | None = None,
    _=Depends(apply_request_headers),
) -> Dict[str, Any]:
    headers = headers_from_env_or_ctx()
    if not isinstance(headers, dict) or not headers.get("authorization"):
        auth = request.headers.get("authorization")
        api_key_id = request.headers.get("x-api-key-id")
        api_secret = request.headers.get("x-api-secret")
        env = request.headers.get("x-composer-mcp-environment")
        if auth:
            set_ctx_headers({"authorization": auth, **({"x-composer-mcp-environment": env} if env else {})})
        elif api_key_id and api_secret:
            import base64
            try:
                basic = base64.b64encode(f"{api_key_id}:{api_secret}".encode("utf-8")).decode("utf-8")
                set_ctx_headers({"authorization": f"Basic {basic}", **({"x-composer-mcp-environment": env} if env else {})})
            except Exception:
                pass

    if not account_uuid:
        try:
            account_uuid = await fetch_default_account_uuid()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    # Get symphonies data which contains the actual holdings
    try:
        symphonies = await fetch_symphonies(account_uuid)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    
    # Aggregate holdings from all symphonies
    aggregated_holdings = {}
    total_portfolio_value = 0.0
    
    for symphony in symphonies:
        holdings = symphony.get("holdings", [])
        for holding in holdings:
            ticker = holding.get("ticker")
            value = holding.get("value", 0.0)
            allocation = holding.get("allocation", 0.0)
            amount = holding.get("amount", 0.0)
            
            if ticker and value > 0:
                if ticker in aggregated_holdings:
                    aggregated_holdings[ticker]["market_value"] += value
                    aggregated_holdings[ticker]["quantity"] += amount
                else:
                    aggregated_holdings[ticker] = {
                        "symbol": ticker,
                        "market_value": value,
                        "quantity": amount
                    }
                total_portfolio_value += value
    
    # Convert to list and calculate weights
    items = []
    for holding in aggregated_holdings.values():
        weight = holding["market_value"] / total_portfolio_value if total_portfolio_value > 0 else 0
        items.append({
            "symbol": holding["symbol"],
            "quantity": holding["quantity"],
            "market_value": holding["market_value"],
            "weight": weight,
        })
    
    # Sort descending by weight
    items.sort(key=lambda x: x["weight"], reverse=True)
    return {"items": items, "total_value": total_portfolio_value}


@router.get("/symphonies")
async def get_symphonies(
    request: Request,
    account_uuid: str | None = None,
    _=Depends(apply_request_headers),
) -> Dict[str, Any]:
    headers = headers_from_env_or_ctx()
    if not isinstance(headers, dict) or not headers.get("authorization"):
        auth = request.headers.get("authorization")
        api_key_id = request.headers.get("x-api-key-id")
        api_secret = request.headers.get("x-api-secret")
        env = request.headers.get("x-composer-mcp-environment")
        if auth:
            set_ctx_headers({"authorization": auth, **({"x-composer-mcp-environment": env} if env else {})})
        elif api_key_id and api_secret:
            import base64
            try:
                basic = base64.b64encode(f"{api_key_id}:{api_secret}".encode("utf-8")).decode("utf-8")
                set_ctx_headers({"authorization": f"Basic {basic}", **({"x-composer-mcp-environment": env} if env else {})})
            except Exception:
                pass

    if not account_uuid:
        try:
            account_uuid = await fetch_default_account_uuid()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    try:
        symphonies = await fetch_symphonies(account_uuid)
        return {"symphonies": symphonies}
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/debug/raw-holdings")
async def debug_raw_holdings(
    request: Request,
    account_uuid: str | None = None,
    _=Depends(apply_request_headers),
) -> Dict[str, Any]:
    """Debug endpoint to see raw holdings data structure"""
    headers = headers_from_env_or_ctx()
    if not isinstance(headers, dict) or not headers.get("authorization"):
        auth = request.headers.get("authorization")
        api_key_id = request.headers.get("x-api-key-id")
        api_secret = request.headers.get("x-api-secret")
        env = request.headers.get("x-composer-mcp-environment")
        if auth:
            set_ctx_headers({"authorization": auth, **({"x-composer-mcp-environment": env} if env else {})})
        elif api_key_id and api_secret:
            import base64
            try:
                basic = base64.b64encode(f"{api_key_id}:{api_secret}".encode("utf-8")).decode("utf-8")
                set_ctx_headers({"authorization": f"Basic {basic}", **({"x-composer-mcp-environment": env} if env else {})})
            except Exception:
                pass

    if not account_uuid:
        try:
            account_uuid = await fetch_default_account_uuid()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    # Import the raw function to get unprocessed data
    from composer_trade_mcp.server import get_account_holdings
    raw_holdings = await get_account_holdings.fn(account_uuid)  # type: ignore[attr-defined]
    
    return {
        "account_uuid": account_uuid,
        "raw_holdings": raw_holdings,
        "raw_holdings_type": str(type(raw_holdings)),
        "raw_holdings_length": len(raw_holdings) if isinstance(raw_holdings, (list, dict)) else "N/A"
    }


@router.get("/debug/raw-symphonies")
async def debug_raw_symphonies(
    request: Request,
    account_uuid: str | None = None,
    _=Depends(apply_request_headers),
) -> Dict[str, Any]:
    """Debug endpoint to see raw symphonies data structure"""
    headers = headers_from_env_or_ctx()
    if not isinstance(headers, dict) or not headers.get("authorization"):
        auth = request.headers.get("authorization")
        api_key_id = request.headers.get("x-api-key-id")
        api_secret = request.headers.get("x-api-secret")
        env = request.headers.get("x-composer-mcp-environment")
        if auth:
            set_ctx_headers({"authorization": auth, **({"x-composer-mcp-environment": env} if env else {})})
        elif api_key_id and api_secret:
            import base64
            try:
                basic = base64.b64encode(f"{api_key_id}:{api_secret}".encode("utf-8")).decode("utf-8")
                set_ctx_headers({"authorization": f"Basic {basic}", **({"x-composer-mcp-environment": env} if env else {})})
            except Exception:
                pass

    if not account_uuid:
        try:
            account_uuid = await fetch_default_account_uuid()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    # Import the raw function to get unprocessed data
    from composer_trade_mcp.server import get_aggregate_symphony_stats
    raw_symphonies = await get_aggregate_symphony_stats.fn(account_uuid)  # type: ignore[attr-defined]
    
    return {
        "account_uuid": account_uuid,
        "raw_symphonies": raw_symphonies,
        "raw_symphonies_type": str(type(raw_symphonies)),
        "raw_symphonies_length": len(raw_symphonies) if isinstance(raw_symphonies, (list, dict)) else "N/A"
    }


@router.get("/risk-comparison")
async def get_risk_comparison(
    request: Request,
    account_uuid: str | None = None,
    _=Depends(apply_request_headers),
) -> Dict[str, Any]:
    """Get risk comparison metrics between SPY and Composer portfolio"""
    headers = headers_from_env_or_ctx()
    if not isinstance(headers, dict) or not headers.get("authorization"):
        auth = request.headers.get("authorization")
        api_key_id = request.headers.get("x-api-key-id")
        api_secret = request.headers.get("x-api-secret")
        env = request.headers.get("x-composer-mcp-environment")
        if auth:
            set_ctx_headers({"authorization": auth, **({"x-composer-mcp-environment": env} if env else {})})
        elif api_key_id and api_secret:
            import base64
            try:
                basic = base64.b64encode(f"{api_key_id}:{api_secret}".encode("utf-8")).decode("utf-8")
                set_ctx_headers({"authorization": f"Basic {basic}", **({"x-composer-mcp-environment": env} if env else {})})
            except Exception:
                pass

    if not account_uuid:
        try:
            account_uuid = await fetch_default_account_uuid()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    # Get portfolio data
    try:
        symphonies = await fetch_symphonies(account_uuid)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # First, fetch symphony-level daily performance to get the actual date range
    # Same logic as in the /api/performance endpoint
    sym_to_perf: Dict[str, Dict[str, Any]] = {}
    all_dates_set: set[str] = set()

    sem = asyncio.Semaphore(8)

    async def fetch_sym(sym_id: str) -> tuple[str, Dict[str, Any] | None]:
        async with sem:
            try:
                perf = await fetch_symphony_daily_performance(account_uuid, sym_id)
                sym_dates: List[str] = perf.get("dates", [])
                depo_series: List[float] = perf.get("deposit_adjusted_series", [])
                value_series: List[float] = perf.get("series", [])
                if not sym_dates or not depo_series:
                    return (sym_id, None)
                return (
                    sym_id,
                    {
                        "dates": sym_dates,
                        "depo": [float(x) for x in depo_series],
                        "value": (
                            [float(x) for x in value_series]
                            if value_series
                            else [None] * len(sym_dates)
                        ),
                        "date_index": {d: i for i, d in enumerate(sym_dates)},
                    },
                )
            except Exception:
                return (sym_id, None)

    tasks: List[asyncio.Task] = []
    for sym in symphonies:
        sym_id = sym.get("id") or sym.get("symphony_id") or sym.get("symphonyId")
        if sym_id:
            tasks.append(asyncio.create_task(fetch_sym(sym_id)))

    for sym_id, perf in await asyncio.gather(*tasks):
        if perf is None:
            continue
        sym_to_perf[sym_id] = perf
        all_dates_set.update(perf["dates"])

    dates: List[str] = sorted(all_dates_set)
    
    if not dates:
        raise HTTPException(status_code=404, detail="No performance data available for portfolio")
    
    # Now fetch SPY data for the SAME date range as the portfolio
    portfolio_start_date = dates[0]  # First date in portfolio
    portfolio_end_date = dates[-1]   # Last date in portfolio
    
    print(f"Fetching SPY data from {portfolio_start_date} to {portfolio_end_date}")
    print(f"Portfolio has {len(dates)} trading days")
    
    spy_stats = await fetch_spy_metrics(portfolio_start_date, portfolio_end_date)
    spy_total_return = spy_stats.get("total_return", 0.0)
    spy_cagr = spy_stats.get("cagr", 0.0)
    spy_win_rate = spy_stats.get("win_rate", 0.0)
    spy_avg_win = spy_stats.get("avg_win", 0.0)
    spy_avg_loss = spy_stats.get("avg_loss", 0.0)
    spy_avg_return = spy_stats.get("avg_daily", 0.0)
    spy_largest_win = spy_stats.get("largest_win", 0.0)
    spy_largest_loss = spy_stats.get("largest_loss", 0.0)
    spy_max_drawdown = spy_stats.get("max_drawdown", 0.0)
    spy_annualized_vol = spy_stats.get("ann_std", 0.0)
    spy_sharpe = spy_stats.get("sharpe", 0.0)
    spy_sortino = spy_stats.get("sortino", 0.0)
    spy_reward_risk = spy_stats.get("reward_risk", 0.0)
    spy_current_dd = spy_stats.get("current_dd", 0.0)
    
    # Calculate portfolio-level daily returns
    composer_daily_returns: List[float] = []
    if len(dates) > 1:
        for idx in range(1, len(dates)):
            d_prev = dates[idx - 1]
            d_curr = dates[idx]
            weighted_sum = 0.0
            total_value_prev = 0.0
            for perf in sym_to_perf.values():
                di = perf["date_index"]
                if d_curr not in di or d_prev not in di:
                    continue
                i_prev = di[d_prev]
                i_curr = di[d_curr]
                depo_prev = perf["depo"][i_prev]
                depo_curr = perf["depo"][i_curr]
                if depo_prev is None or depo_prev == 0:
                    continue
                r_i = (depo_curr / depo_prev) - 1.0
                v_prev_list = perf["value"]
                v_prev = v_prev_list[i_prev] if i_prev < len(v_prev_list) else None
                if v_prev is None or v_prev <= 0:
                    continue
                weighted_sum += v_prev * r_i
                total_value_prev += v_prev
            daily_return = (weighted_sum / total_value_prev) if total_value_prev > 0 else 0.0
            composer_daily_returns.append(daily_return)
    
    print(f"Composer daily returns (first 10): {composer_daily_returns[:10]}")
    print(f"Total daily returns: {len(composer_daily_returns)}")
    
    # Use the shared metrics calculation function for Composer portfolio
    composer_metrics = compute_metrics_from_daily_returns(composer_daily_returns)
    
    # Extract values for compatibility with existing code
    composer_total_return = composer_metrics["total_return"]
    composer_cagr = composer_metrics["cagr"]
    composer_volatility = composer_metrics["ann_std"]
    composer_sharpe = composer_metrics["sharpe"]
    composer_sortino = composer_metrics["sortino"]
    composer_reward_risk = composer_metrics["reward_risk"]
    composer_max_drawdown = composer_metrics["max_drawdown"]
    composer_current_dd = composer_metrics["current_dd"]
    composer_win_rate = composer_metrics["win_rate"]
    composer_avg_win = composer_metrics["avg_win"]
    composer_avg_loss = composer_metrics["avg_loss"]
    composer_avg_daily = composer_metrics["avg_daily"]
    composer_largest_win = composer_metrics["largest_win"]
    composer_largest_loss = composer_metrics["largest_loss"]

    return {
        "metrics": [
            {"metric": "Total %", "spy": f"{spy_total_return*100:.2f}%", "composer": f"{composer_total_return*100:.2f}%"},
            {"metric": "CAGR %", "spy": f"{spy_cagr*100:.2f}%", "composer": f"{composer_cagr*100:.2f}%"},
            {"metric": "Win %", "spy": f"{spy_win_rate*100:.2f}%", "composer": f"{composer_win_rate*100:.2f}%"},
            {"metric": "Avg. Win %", "spy": f"{spy_avg_win*100:.2f}%", "composer": f"{composer_avg_win*100:.2f}%"},
            {"metric": "Avg. Loss %", "spy": f"{spy_avg_loss*100:.2f}%", "composer": f"{composer_avg_loss*100:.2f}%"},
            {"metric": "Average %", "spy": f"{spy_avg_return*100:.2f}%", "composer": f"{composer_avg_daily*100:.2f}%"},
            {"metric": "Largest Win", "spy": f"{spy_largest_win*100:.2f}%", "composer": f"{composer_largest_win*100:.2f}%"},
            {"metric": "Largest Loss", "spy": f"{spy_largest_loss*100:.2f}%", "composer": f"{composer_largest_loss*100:.2f}%"},
            {"metric": "Current DD", "spy": f"{spy_current_dd*100:.2f}%", "composer": f"{composer_current_dd*100:.2f}%"},
            {"metric": "Max DD", "spy": f"{spy_max_drawdown*100:.2f}%", "composer": f"{composer_max_drawdown*100:.2f}%"},
            {"metric": "Ann. Std %", "spy": f"{spy_annualized_vol*100:.2f}%", "composer": f"{composer_volatility*100:.2f}%"},
            {"metric": "Sharpe Ratio", "spy": f"{spy_sharpe:.2f}", "composer": f"{composer_sharpe:.2f}"},
            {"metric": "Sortino Ratio", "spy": f"{spy_sortino:.2f}", "composer": f"{composer_sortino:.2f}"},
            {"metric": "Reward/Risk", "spy": f"{spy_reward_risk:.2f}", "composer": f"{composer_reward_risk:.2f}"}
        ]
    }


@router.get("/portfolio-risk")
async def get_portfolio_risk(
    request: Request,
    account_uuid: str | None = None,
    _=Depends(apply_request_headers),
) -> Dict[str, Any]:
    """Get detailed portfolio risk metrics including VaR calculations"""
    headers = headers_from_env_or_ctx()
    if not isinstance(headers, dict) or not headers.get("authorization"):
        auth = request.headers.get("authorization")
        api_key_id = request.headers.get("x-api-key-id")
        api_secret = request.headers.get("x-api-secret")
        env = request.headers.get("x-composer-mcp-environment")
        if auth:
            set_ctx_headers({"authorization": auth, **({"x-composer-mcp-environment": env} if env else {})})
        elif api_key_id and api_secret:
            import base64
            try:
                basic = base64.b64encode(f"{api_key_id}:{api_secret}".encode("utf-8")).decode("utf-8")
                set_ctx_headers({"authorization": f"Basic {basic}", **({"x-composer-mcp-environment": env} if env else {})})
            except Exception:
                pass

    if not account_uuid:
        try:
            account_uuid = await fetch_default_account_uuid()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    try:
        symphonies = await fetch_symphonies(account_uuid)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # Calculate portfolio metrics
    total_value = sum(s.get("value", 0) for s in symphonies)
    total_deposits = sum(s.get("net_deposits", 0) for s in symphonies)
    
    # Fetch portfolio daily performance to get actual returns series
    try:
        portfolio_perf = await fetch_portfolio_daily_performance(account_uuid)
        if isinstance(portfolio_perf, dict) and "data" in portfolio_perf:
            perf_data = portfolio_perf["data"]
        elif isinstance(portfolio_perf, list):
            perf_data = portfolio_perf
        else:
            perf_data = []
        
        # Extract values and calculate daily returns
        portfolio_values = [float(item.get("value", 0)) for item in perf_data if item.get("value")]
        portfolio_daily_returns = []
        for i in range(1, len(portfolio_values)):
            if portfolio_values[i-1] > 0:
                ret = (portfolio_values[i] / portfolio_values[i-1]) - 1.0
                portfolio_daily_returns.append(ret)
        
        # Fetch SPY data for correlation
        from datetime import datetime, timedelta
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=365)
        spy_closes = await fetch_spy_closes(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        spy_values = [v for _, v in sorted(spy_closes.items(), key=lambda t: t[0])]
        spy_daily_returns = []
        for i in range(1, len(spy_values)):
            if spy_values[i-1] > 0:
                ret = (spy_values[i] / spy_values[i-1]) - 1.0
                spy_daily_returns.append(ret)
        
        # Align the return series by taking the minimum length
        if portfolio_daily_returns and spy_daily_returns:
            min_len = min(len(portfolio_daily_returns), len(spy_daily_returns))
            portfolio_daily_returns = portfolio_daily_returns[-min_len:]
            spy_daily_returns = spy_daily_returns[-min_len:]
        
        # Calculate real metrics from daily returns
        historical_var_95 = calculate_var_95_historical(portfolio_daily_returns)
        parametric_var_95 = calculate_var_95_parametric(portfolio_daily_returns)
        expected_shortfall_val = calculate_expected_shortfall(portfolio_daily_returns)
        correlation_with_spy = calculate_correlation(portfolio_daily_returns, spy_daily_returns)
        consistency = calculate_consistency_score(portfolio_daily_returns, window=30)
        
        # Calculate volatility from actual returns
        if portfolio_daily_returns:
            mean_ret = sum(portfolio_daily_returns) / len(portfolio_daily_returns)
            variance = sum((r - mean_ret) ** 2 for r in portfolio_daily_returns) / max(1, len(portfolio_daily_returns) - 1)
            daily_std = variance ** 0.5
            annual_vol = daily_std * (252 ** 0.5)
        else:
            annual_vol = 0.0
        
        # Calculate portfolio sharpe and max drawdown from actual series
        if portfolio_values and len(portfolio_values) >= 2:
            n = len(portfolio_values)
            total_return = portfolio_values[-1] / portfolio_values[0] - 1.0
            annualized_return = (portfolio_values[-1] / portfolio_values[0]) ** (252 / n) - 1.0 if portfolio_values[0] > 0 else 0.0
            portfolio_sharpe = (annualized_return / annual_vol) if annual_vol > 0 else 0.0
            
            # Calculate max drawdown
            peak = portfolio_values[0]
            max_dd = 0.0
            for v in portfolio_values:
                peak = max(peak, v)
                if peak > 0:
                    dd = v / peak - 1.0
                    if dd < max_dd:
                        max_dd = dd
            portfolio_max_drawdown = abs(max_dd)
        else:
            portfolio_sharpe = 0.0
            portfolio_max_drawdown = 0.0
        
    except Exception as e:
        # Fallback to symphony-based calculations if portfolio daily performance fails
        portfolio_sharpe = sum(s.get("sharpe_ratio", 0) * (s.get("value", 0) / total_value) for s in symphonies) if total_value > 0 else 0
        portfolio_max_drawdown = max(abs(s.get("max_drawdown", 0)) for s in symphonies) if symphonies else 0
        portfolio_avg_return = sum(s.get("annualized_rate_of_return", 0) * (s.get("value", 0) / total_value) for s in symphonies) if total_value > 0 else 0
        annual_vol = abs(portfolio_avg_return / portfolio_sharpe) if portfolio_sharpe != 0 else 0.0
        historical_var_95 = 0.0
        parametric_var_95 = 0.0
        expected_shortfall_val = 0.0
        correlation_with_spy = 0.0
        consistency = 0

    return {
        "total_value": total_value,
        "volatility": annual_vol,
        "sharpe_ratio": portfolio_sharpe,
        "max_drawdown": portfolio_max_drawdown,
        "correlation_with_spy": correlation_with_spy,
        "consistency": consistency,
        "var_95_historical": historical_var_95,
        "var_95_parametric": parametric_var_95,
        "expected_shortfall": expected_shortfall_val,
        "var_95_dollar_historical": total_value * historical_var_95,
        "var_95_dollar_parametric": total_value * parametric_var_95,
        "expected_shortfall_dollar": total_value * expected_shortfall_val
    }


@router.get("/symphony/{symphony_id}/live-vs-backtest")
async def get_live_vs_backtest(
    request: Request,
    symphony_id: str,
    account_uuid: str | None = None,
    _=Depends(apply_request_headers),
) -> Dict[str, Any]:
    """
    Compare live performance vs backtested performance for a symphony.
    
    This endpoint calculates deviation metrics to identify how much the live performance
    differs from the backtest over the same time period. Higher deviation indicates
    higher risk that the symphony may not perform as expected.
    
    Returns:
    - deviation_metrics: tracking error, correlation, RMSE, max/mean deviation, risk score
    - live_performance: live performance data
    - backtest_performance: backtest data over the same period
    - comparison_data: side-by-side performance comparison
    """
    headers = headers_from_env_or_ctx()
    if not isinstance(headers, dict) or not headers.get("authorization"):
        auth = request.headers.get("authorization")
        api_key_id = request.headers.get("x-api-key-id")
        api_secret = request.headers.get("x-api-secret")
        env = request.headers.get("x-composer-mcp-environment")
        if auth:
            hdrs: Dict[str, str] = {"authorization": auth}
            if env:
                hdrs["x-composer-mcp-environment"] = env
            set_ctx_headers(hdrs)
        elif api_key_id and api_secret:
            import base64
            try:
                basic = base64.b64encode(
                    f"{api_key_id}:{api_secret}".encode("utf-8")
                ).decode("utf-8")
                hdrs = {"authorization": f"Basic {basic}"}
                if env:
                    hdrs["x-composer-mcp-environment"] = env
                set_ctx_headers(hdrs)
            except Exception:
                pass

    # Fail fast with 401 if no credentials
    headers = headers_from_env_or_ctx()
    if not isinstance(headers, dict) or not headers.get("authorization"):
        raise HTTPException(
            status_code=401,
            detail="Missing Composer credentials. Provide Authorization: Basic ... or x-api-key-id/x-api-secret headers.",
        )

    if not account_uuid:
        try:
            account_uuid = await fetch_default_account_uuid()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    # Fetch live performance data
    try:
        live_perf = await fetch_symphony_daily_performance(account_uuid, symphony_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Error fetching live performance: {str(exc)}")

    if not live_perf or "dates" not in live_perf:
        raise HTTPException(status_code=404, detail="No live performance data available for this symphony")

    live_dates = live_perf.get("dates", [])
    live_series = live_perf.get("deposit_adjusted_series", [])
    
    if not live_dates or not live_series:
        raise HTTPException(status_code=404, detail="Insufficient live performance data")

    # Use the first and last date from live performance for backtest
    start_date = live_dates[0]
    end_date = live_dates[-1]

    # Fetch backtest data for the same period
    try:
        backtest_result = await backtest_symphony_by_id.fn(  # type: ignore[attr-defined]
            symphony_id=symphony_id,
            start_date=start_date,
            end_date=end_date,
            include_daily_values=True,
            capital=float(live_series[0]) if live_series[0] else 10000.0,  # Start with same capital as live
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error running backtest: {str(exc)}")

    if isinstance(backtest_result, dict) and backtest_result.get("error"):
        raise HTTPException(status_code=502, detail=f"Backtest error: {backtest_result.get('error')}")

    # Extract backtest daily values
    backtest_daily = backtest_result.get("daily_values", {})
    if not backtest_daily or not isinstance(backtest_daily, dict):
        raise HTTPException(status_code=404, detail="No backtest data returned")

    # The backtest returns a dict with structure:
    # {"cumulative_return_date": ["2024-01-01", ...], "Symphony Name": [0, 1.5, ...], "SPY": [...]}
    backtest_dates = backtest_daily.get("cumulative_return_date", [])
    if not backtest_dates:
        raise HTTPException(status_code=404, detail="No backtest dates available")
    
    # Find the symphony data (not SPY or other benchmarks)
    # The symphony data is typically the first non-date, non-benchmark key
    symphony_key = None
    for key in backtest_daily.keys():
        if key != "cumulative_return_date" and key not in ["SPY", "QQQ", "BTC", "ETH"]:
            symphony_key = key
            break
    
    if not symphony_key or symphony_key not in backtest_daily:
        # Fallback: use any non-date key
        for key in backtest_daily.keys():
            if key != "cumulative_return_date":
                symphony_key = key
                break
    
    if not symphony_key:
        raise HTTPException(status_code=404, detail="Could not find symphony data in backtest results")
    
    cumulative_returns = backtest_daily[symphony_key]
    
    # Convert cumulative return percentages to actual values
    initial_value = float(live_series[0]) if live_series[0] else 10000.0
    backtest_values = []
    for cum_return_pct in cumulative_returns:
        if cum_return_pct is not None:
            # cumulative_returns are percentages from first day (e.g., 0, 1.5, 2.3 means 0%, 1.5%, 2.3% gain)
            cum_return = float(cum_return_pct) / 100.0
            value = initial_value * (1.0 + cum_return)
            backtest_values.append(value)
        else:
            backtest_values.append(initial_value)  # Use initial value for None entries

    # Calculate deviation metrics
    deviation_metrics = compute_deviation_metrics(
        live_dates=live_dates,
        live_values=[float(v) for v in live_series],
        backtest_dates=backtest_dates,
        backtest_values=backtest_values
    )

    # Create comparison data for visualization
    live_map = {date: value for date, value in zip(live_dates, live_series)}
    backtest_map = {date: value for date, value in zip(backtest_dates, backtest_values)}
    
    common_dates = sorted(set(live_dates) & set(backtest_dates))
    comparison_data = []
    for date in common_dates:
        live_val = float(live_map[date])
        backtest_val = float(backtest_map[date])
        deviation_pct = ((live_val - backtest_val) / backtest_val * 100) if backtest_val > 0 else 0.0
        
        comparison_data.append({
            "date": date,
            "live": round(live_val, 2),
            "backtest": round(backtest_val, 2),
            "deviation_pct": round(deviation_pct, 2)
        })

    # Interpret risk score
    risk_score = deviation_metrics["risk_score"]
    if risk_score < 20:
        risk_level = "Low"
        risk_description = "Live performance closely tracks backtest"
    elif risk_score < 40:
        risk_level = "Moderate"
        risk_description = "Some deviation from backtest, monitor closely"
    elif risk_score < 60:
        risk_level = "Elevated"
        risk_description = "Significant deviation from backtest, consider reviewing strategy"
    else:
        risk_level = "High"
        risk_description = "Large deviation from backtest, may indicate high risk or changed market conditions"

    return {
        "symphony_id": symphony_id,
        "period": {
            "start": start_date,
            "end": end_date,
            "days": len(common_dates)
        },
        "deviation_metrics": {
            **deviation_metrics,
            "risk_level": risk_level,
            "risk_description": risk_description
        },
        "summary": {
            "live_cumulative_return": round(
                ((live_series[-1] / live_series[0]) - 1.0) * 100, 2
            ) if live_series and live_series[0] > 0 else 0.0,
            "backtest_cumulative_return": round(
                ((backtest_values[-1] / backtest_values[0]) - 1.0) * 100, 2
            ) if backtest_values and backtest_values[0] > 0 else 0.0,
            "tracking_error_annualized_pct": round(deviation_metrics["tracking_error"] * 100, 2),
            "correlation": round(deviation_metrics["correlation"], 3),
        },
        "comparison_data": comparison_data,
        "backtest_stats": backtest_result.get("stats", {})
    }


@router.get("/portfolio/live-vs-backtest")
async def get_portfolio_live_vs_backtest(
    request: Request,
    account_uuid: str | None = None,
    _=Depends(apply_request_headers),
) -> Dict[str, Any]:
    """
    Compare live vs backtest performance for all symphonies in the portfolio.
    
    This endpoint provides a portfolio-wide view of how each symphony is performing
    relative to its backtest, helping identify which strategies may be at higher risk.
    
    Returns a list of symphonies sorted by risk score (highest risk first).
    """
    headers = headers_from_env_or_ctx()
    if not isinstance(headers, dict) or not headers.get("authorization"):
        auth = request.headers.get("authorization")
        api_key_id = request.headers.get("x-api-key-id")
        api_secret = request.headers.get("x-api-secret")
        env = request.headers.get("x-composer-mcp-environment")
        if auth:
            hdrs: Dict[str, str] = {"authorization": auth}
            if env:
                hdrs["x-composer-mcp-environment"] = env
            set_ctx_headers(hdrs)
        elif api_key_id and api_secret:
            import base64
            try:
                basic = base64.b64encode(
                    f"{api_key_id}:{api_secret}".encode("utf-8")
                ).decode("utf-8")
                hdrs = {"authorization": f"Basic {basic}"}
                if env:
                    hdrs["x-composer-mcp-environment"] = env
                set_ctx_headers(hdrs)
            except Exception:
                pass

    # Fail fast with 401 if no credentials
    headers = headers_from_env_or_ctx()
    if not isinstance(headers, dict) or not headers.get("authorization"):
        raise HTTPException(
            status_code=401,
            detail="Missing Composer credentials. Provide Authorization: Basic ... or x-api-key-id/x-api-secret headers.",
        )

    if not account_uuid:
        try:
            account_uuid = await fetch_default_account_uuid()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    # Fetch all symphonies
    try:
        symphonies = await fetch_symphonies(account_uuid)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if not symphonies:
        raise HTTPException(status_code=404, detail="No symphonies found in portfolio")

    # Process each symphony concurrently (with rate limiting)
    sem = asyncio.Semaphore(3)  # Limit to 3 concurrent backtests
    
    async def process_symphony(symphony: Dict[str, Any]) -> Dict[str, Any] | None:
        async with sem:
            symphony_id = symphony.get("id") or symphony.get("symphony_id") or symphony.get("symphonyId")
            symphony_name = symphony.get("name", "Unknown")
            
            if not symphony_id:
                return None
            
            try:
                # Fetch live performance
                live_perf = await fetch_symphony_daily_performance(account_uuid, symphony_id)
                
                if not live_perf or "dates" not in live_perf:
                    return None
                
                live_dates = live_perf.get("dates", [])
                live_series = live_perf.get("deposit_adjusted_series", [])
                
                if not live_dates or not live_series or len(live_dates) < 2:
                    return None
                
                start_date = live_dates[0]
                end_date = live_dates[-1]
                
                # Run backtest
                backtest_result = await backtest_symphony_by_id.fn(  # type: ignore[attr-defined]
                    symphony_id=symphony_id,
                    start_date=start_date,
                    end_date=end_date,
                    include_daily_values=True,
                    capital=float(live_series[0]) if live_series[0] else 10000.0,
                )
                
                if isinstance(backtest_result, dict) and backtest_result.get("error"):
                    return None
                
                backtest_daily = backtest_result.get("daily_values", {})
                if not backtest_daily or not isinstance(backtest_daily, dict):
                    return None
                
                # Convert backtest data - same logic as single symphony endpoint
                backtest_dates = backtest_daily.get("cumulative_return_date", [])
                if not backtest_dates:
                    return None
                
                # Find the symphony data key
                symphony_key = None
                for key in backtest_daily.keys():
                    if key != "cumulative_return_date" and key not in ["SPY", "QQQ", "BTC", "ETH"]:
                        symphony_key = key
                        break
                
                if not symphony_key:
                    for key in backtest_daily.keys():
                        if key != "cumulative_return_date":
                            symphony_key = key
                            break
                
                if not symphony_key or symphony_key not in backtest_daily:
                    return None
                
                cumulative_returns = backtest_daily[symphony_key]
                
                # Convert cumulative return percentages to actual values
                initial_value = float(live_series[0]) if live_series[0] else 10000.0
                backtest_values = []
                for cum_return_pct in cumulative_returns:
                    if cum_return_pct is not None:
                        cum_return = float(cum_return_pct) / 100.0
                        value = initial_value * (1.0 + cum_return)
                        backtest_values.append(value)
                    else:
                        backtest_values.append(initial_value)
                
                # Calculate deviation metrics
                deviation_metrics = compute_deviation_metrics(
                    live_dates=live_dates,
                    live_values=[float(v) for v in live_series],
                    backtest_dates=backtest_dates,
                    backtest_values=backtest_values
                )
                
                # Determine risk level
                risk_score = deviation_metrics["risk_score"]
                if risk_score < 20:
                    risk_level = "Low"
                elif risk_score < 40:
                    risk_level = "Moderate"
                elif risk_score < 60:
                    risk_level = "Elevated"
                else:
                    risk_level = "High"
                
                # Calculate returns
                live_return = ((live_series[-1] / live_series[0]) - 1.0) * 100 if live_series[0] > 0 else 0.0
                backtest_return = ((backtest_values[-1] / backtest_values[0]) - 1.0) * 100 if backtest_values[0] > 0 else 0.0
                
                return {
                    "symphony_id": symphony_id,
                    "symphony_name": symphony_name,
                    "risk_score": round(risk_score, 2),
                    "risk_level": risk_level,
                    "tracking_error_annualized_pct": round(deviation_metrics["tracking_error"] * 100, 2),
                    "correlation": round(deviation_metrics["correlation"], 3),
                    "mean_deviation_pct": round(deviation_metrics["mean_deviation"] * 100, 2),
                    "max_deviation_pct": round(deviation_metrics["max_deviation"] * 100, 2),
                    "live_return_pct": round(live_return, 2),
                    "backtest_return_pct": round(backtest_return, 2),
                    "return_difference_pct": round(live_return - backtest_return, 2),
                    "period_days": deviation_metrics["num_data_points"],
                    "current_value": float(symphony.get("value", 0)),
                }
            except Exception as e:
                # Log error but continue with other symphonies
                import logging
                logging.error(f"Error processing symphony {symphony_id}: {str(e)}")
                return None
    
    # Process all symphonies concurrently
    tasks = [process_symphony(sym) for sym in symphonies]
    results = await asyncio.gather(*tasks)
    
    # Filter out None results and sort by risk score (highest first)
    symphony_comparisons = [r for r in results if r is not None]
    symphony_comparisons.sort(key=lambda x: x["risk_score"], reverse=True)
    
    # Calculate portfolio-level statistics
    if symphony_comparisons:
        total_value = sum(s["current_value"] for s in symphony_comparisons)
        
        # Weighted average risk score
        weighted_risk_score = sum(
            s["risk_score"] * (s["current_value"] / total_value)
            for s in symphony_comparisons
        ) if total_value > 0 else 0
        
        # Count by risk level
        risk_counts = {
            "Low": sum(1 for s in symphony_comparisons if s["risk_level"] == "Low"),
            "Moderate": sum(1 for s in symphony_comparisons if s["risk_level"] == "Moderate"),
            "Elevated": sum(1 for s in symphony_comparisons if s["risk_level"] == "Elevated"),
            "High": sum(1 for s in symphony_comparisons if s["risk_level"] == "High"),
        }
        
        portfolio_summary = {
            "total_symphonies": len(symphony_comparisons),
            "total_portfolio_value": total_value,
            "weighted_avg_risk_score": round(weighted_risk_score, 2),
            "risk_level_counts": risk_counts,
            "avg_tracking_error_pct": round(
                sum(s["tracking_error_annualized_pct"] for s in symphony_comparisons) / len(symphony_comparisons), 2
            ),
            "avg_correlation": round(
                sum(s["correlation"] for s in symphony_comparisons) / len(symphony_comparisons), 3
            ),
        }
    else:
        portfolio_summary = {
            "total_symphonies": 0,
            "total_portfolio_value": 0,
            "weighted_avg_risk_score": 0,
            "risk_level_counts": {"Low": 0, "Moderate": 0, "Elevated": 0, "High": 0},
            "avg_tracking_error_pct": 0,
            "avg_correlation": 0,
        }
    
    return {
        "portfolio_summary": portfolio_summary,
        "symphonies": symphony_comparisons
    }
