from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request

from ..clients.composer_mcp import (
    fetch_default_account_uuid,
    fetch_symphonies,
    fetch_symphony_daily_performance,
)
from ..deps.auth_headers import (
    apply_request_headers,
    headers_from_env_or_ctx,
    set_ctx_headers,
)
from ..services.performance_calc import (
    compute_lookback_return,
    compute_stats_from_series,
    fetch_spy_closes,
)


router = APIRouter()


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

    # Attempt to append an intraday "today" point using current symphony stats if available.
    try:
        from datetime import date as _date

        today_str = _date.today().isoformat()
        if today_str not in dates:
            # Build a quick lookup of current deposit-adjusted value and current total value per symphony from meta
            current_meta: Dict[str, Dict[str, float]] = {}
            for sym in symphonies:
                sym_id = (
                    sym.get("id") or sym.get("symphony_id") or sym.get("symphonyId")
                )
                if not sym_id:
                    continue
                # Prefer common keys; fall back across known variants
                depo_now = sym.get("deposit_adjusted_value")
                total_now = (
                    sym.get("value")
                    or sym.get("total_value")
                    or sym.get("portfolio_value")
                )
                try:
                    depo_now_f = float(depo_now) if depo_now is not None else None  # type: ignore[arg-type]
                    total_now_f = float(total_now) if total_now is not None else None  # type: ignore[arg-type]
                except Exception:
                    depo_now_f = None
                    total_now_f = None
                if depo_now_f is not None and total_now_f is not None:
                    current_meta[str(sym_id)] = {
                        "depo": depo_now_f,
                        "value": total_now_f,
                    }

            weighted_sum_today = 0.0
            total_value_prev_today = 0.0
            if current_meta:
                last_completed = dates[-1]
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
                    if (
                        depo_prev is None
                        or depo_prev == 0
                        or v_prev is None
                        or v_prev <= 0
                    ):
                        continue
                    r_i_today = (meta["depo"] / float(depo_prev)) - 1.0
                    weighted_sum_today += float(v_prev) * r_i_today
                    total_value_prev_today += float(v_prev)

            if total_value_prev_today > 0:
                r_today = weighted_sum_today / total_value_prev_today
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
    if len(port_values) >= 2 and port_values[-2] > 0:
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
