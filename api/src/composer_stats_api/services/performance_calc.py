from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import asyncio
import yfinance as yf


def compute_stats_from_series(series: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not series:
        return {
            "annualizedReturn": 0.0,
            "annualizedVol": 0.0,
            "sharpe": 0.0,
            "maxDrawdown": 0.0,
        }
    first = series[0]["portfolio"]
    last = series[-1]["portfolio"]
    num = len(series)
    daily_returns: List[float] = []
    for i in range(1, len(series)):
        prev = series[i - 1]["portfolio"]
        curr = series[i]["portfolio"]
        daily_returns.append(curr / prev - 1)
    if not daily_returns:
        return {
            "annualizedReturn": 0.0,
            "annualizedVol": 0.0,
            "sharpe": 0.0,
            "maxDrawdown": 0.0,
            "winPct": 0.0,
            "avgWin": 0.0,
            "avgLoss": 0.0,
            "calmar": 0.0,
        }
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) * (r - mean) for r in daily_returns) / max(1, len(daily_returns) - 1)
    daily_std = variance ** 0.5
    annualized_vol = daily_std * (252 ** 0.5)
    annualized_return = (last / first) ** (252 / num) - 1 if first > 0 and num > 0 else 0.0
    peak = series[0]["portfolio"]
    max_dd = 0.0
    for p in series:
        peak = max(peak, p["portfolio"])
        dd = p["portfolio"] / peak - 1
        if dd < max_dd:
            max_dd = dd
    sharpe = (annualized_return / annualized_vol) if annualized_vol > 0 else 0.0
    positives = [r for r in daily_returns if r > 0]
    negatives = [r for r in daily_returns if r < 0]
    win_pct = (len(positives) / len(daily_returns)) if daily_returns else 0.0
    avg_win = sum(positives) / len(positives) if positives else 0.0
    avg_loss = sum(negatives) / len(negatives) if negatives else 0.0
    calmar = (annualized_return / abs(max_dd)) if abs(max_dd) > 0 else 0.0
    return {
        "annualizedReturn": annualized_return,
        "annualizedVol": annualized_vol,
        "sharpe": sharpe,
        "maxDrawdown": max_dd,
        "winPct": win_pct,
        "avgWin": avg_win,
        "avgLoss": avg_loss,
        "calmar": calmar,
    }


def compute_lookback_return(dates: List[str], values: List[float], days: int) -> float:
    if not dates or not values or len(dates) != len(values):
        return 0.0
    try:
        last_date = datetime.strptime(dates[-1], "%Y-%m-%d").date()
    except Exception:
        return 0.0
    cutoff = last_date - timedelta(days=days)

    parsed: List[Tuple[int, Any]] = []
    for i, ds in enumerate(dates):
        try:
            d = datetime.strptime(ds, "%Y-%m-%d").date()
            parsed.append((i, d))
        except Exception:
            continue
    if not parsed:
        return 0.0

    start_idx = min(parsed, key=lambda t: abs(t[1] - cutoff))[0]
    start_val = values[start_idx]
    end_val = values[-1]
    if start_val and start_val > 0:
        return end_val / start_val - 1.0
    return 0.0


async def fetch_spy_closes(start: str, end: str) -> Dict[str, float]:
    def _work() -> Dict[str, float]:
        local: Dict[str, float] = {}
        spy = yf.Ticker("SPY")
        try:
            end_inclusive = (
                datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
            ).strftime("%Y-%m-%d")
        except Exception:
            end_inclusive = end
        hist = spy.history(start=start, end=end_inclusive)
        for idx, row in hist.iterrows():
            local[str(idx.date())] = float(row.get("Close") or row.get("Adj Close") or 0.0)
        return local

    return await asyncio.to_thread(_work)


