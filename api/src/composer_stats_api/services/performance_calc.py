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



# Detailed metrics from price values
def _daily_returns_from_values(values: List[float]) -> List[float]:
    if len(values) < 2:
        return []
    returns: List[float] = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        if prev > 0:
            returns.append(curr / prev - 1.0)
        else:
            returns.append(0.0)
    return returns


def _max_drawdown_from_values(values: List[float]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            dd = v / peak - 1.0
            if dd < max_dd:
                max_dd = dd
    return abs(max_dd)


def _current_drawdown(values: List[float]) -> float:
    if not values:
        return 0.0
    peak = max(values)
    last = values[-1]
    return last / peak - 1.0 if peak > 0 else 0.0


def compute_detailed_metrics_from_values(values: List[float]) -> Dict[str, float]:
    if not values or len(values) < 2:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "avg_daily": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "max_drawdown": 0.0,
            "ann_std": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "reward_risk": 0.0,
            "current_dd": 0.0,
        }

    n = len(values)
    total_return = values[-1] / values[0] - 1.0 if values[0] > 0 else 0.0
    daily_returns = _daily_returns_from_values(values)
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / max(1, len(daily_returns) - 1)
    daily_std = variance ** 0.5
    ann_std = daily_std * (252 ** 0.5)
    cagr = (values[-1] / values[0]) ** (252 / n) - 1.0 if values[0] > 0 else 0.0
    positives = [r for r in daily_returns if r > 0]
    negatives = [r for r in daily_returns if r < 0]
    win_rate = len(positives) / len(daily_returns) if daily_returns else 0.0
    avg_win = sum(positives) / len(positives) if positives else 0.0
    avg_loss = sum(negatives) / len(negatives) if negatives else 0.0
    largest_win = max(daily_returns) if daily_returns else 0.0
    largest_loss = min(daily_returns) if daily_returns else 0.0
    max_dd = _max_drawdown_from_values(values)
    sharpe = (cagr / ann_std) if ann_std > 0 else 0.0
    downside_std = (sum(r * r for r in negatives) / max(1, len(negatives))) ** 0.5 if negatives else 0.0
    sortino = (cagr / (downside_std * (252 ** 0.5))) if downside_std > 0 else 0.0
    reward_risk = (cagr / ann_std) if ann_std > 0 else 0.0
    curr_dd = _current_drawdown(values)

    return {
        "total_return": total_return,
        "cagr": cagr,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "avg_daily": mean,
        "largest_win": largest_win,
        "largest_loss": largest_loss,
        "max_drawdown": max_dd,
        "ann_std": ann_std,
        "sharpe": sharpe,
        "sortino": sortino,
        "reward_risk": reward_risk,
        "current_dd": curr_dd,
    }


async def fetch_spy_metrics(start: str, end: str) -> Dict[str, float]:
    closes = await fetch_spy_closes(start, end)
    if not closes:
        return compute_detailed_metrics_from_values([])
    values = [v for _, v in sorted(closes.items(), key=lambda t: t[0])]
    return compute_detailed_metrics_from_values(values)


def calculate_var_95_historical(daily_returns: List[float]) -> float:
    """Calculate historical VaR at 95% confidence level"""
    if not daily_returns or len(daily_returns) < 20:
        return 0.0
    sorted_returns = sorted(daily_returns)
    index = int(len(sorted_returns) * 0.05)
    return abs(sorted_returns[index])


def calculate_var_95_parametric(daily_returns: List[float]) -> float:
    """Calculate parametric VaR at 95% confidence level (assumes normal distribution)"""
    if not daily_returns:
        return 0.0
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / max(1, len(daily_returns) - 1)
    std_dev = variance ** 0.5
    # 95% confidence = 1.645 standard deviations (one-tailed)
    return abs(mean - 1.645 * std_dev)


def calculate_expected_shortfall(daily_returns: List[float]) -> float:
    """Calculate Expected Shortfall (CVaR) at 95% confidence level"""
    if not daily_returns or len(daily_returns) < 20:
        return 0.0
    sorted_returns = sorted(daily_returns)
    index = int(len(sorted_returns) * 0.05)
    worst_returns = sorted_returns[:index+1]
    return abs(sum(worst_returns) / len(worst_returns)) if worst_returns else 0.0


def calculate_correlation(returns_a: List[float], returns_b: List[float]) -> float:
    """Calculate Pearson correlation between two return series"""
    if not returns_a or not returns_b or len(returns_a) != len(returns_b):
        return 0.0
    n = len(returns_a)
    if n < 2:
        return 0.0
    
    mean_a = sum(returns_a) / n
    mean_b = sum(returns_b) / n
    
    numerator = sum((returns_a[i] - mean_a) * (returns_b[i] - mean_b) for i in range(n))
    
    sum_sq_a = sum((r - mean_a) ** 2 for r in returns_a)
    sum_sq_b = sum((r - mean_b) ** 2 for r in returns_b)
    
    denominator = (sum_sq_a * sum_sq_b) ** 0.5
    
    if denominator == 0:
        return 0.0
    
    return numerator / denominator


def calculate_consistency_score(daily_returns: List[float], window: int = 30) -> float:
    """
    Calculate consistency score as percentage of rolling windows with positive returns.
    Score from 0-100, where 100 means all rolling 30-day periods were positive.
    """
    if not daily_returns or len(daily_returns) < window:
        return 0.0
    
    positive_windows = 0
    total_windows = len(daily_returns) - window + 1
    
    for i in range(total_windows):
        window_return = sum(daily_returns[i:i+window])
        if window_return > 0:
            positive_windows += 1
    
    return (positive_windows / total_windows) * 100.0 if total_windows > 0 else 0.0
