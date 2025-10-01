from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import asyncio
import yfinance as yf
import numpy as np



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


def compute_total_return_from_returns(daily_returns: List[float]) -> float:
    """Calculate total cumulative return from daily returns."""
    if not daily_returns:
        return 0.0
    cumulative = 1.0
    for r in daily_returns:
        cumulative *= (1.0 + r)
    return cumulative - 1.0


def compute_cagr_from_returns(daily_returns: List[float], annual_days: int = 252) -> float:
    """
    Calculate Compound Annual Growth Rate from daily returns.
    
    Parameters:
        daily_returns: List of daily returns
        annual_days: Trading days per year (default 252)
        
    Returns:
        CAGR as decimal (e.g., 0.15 = 15% per year)
    """
    if not daily_returns:
        return 0.0
    
    cumulative = 1.0
    for r in daily_returns:
        cumulative *= (1.0 + r)
    
    years = len(daily_returns) / annual_days
    if years <= 0:
        return 0.0
    
    return cumulative ** (1.0 / years) - 1.0


def compute_volatility_from_returns(daily_returns: List[float], annual_days: int = 252) -> float:
    """
    Calculate annualized volatility (standard deviation) from daily returns.
    
    Parameters:
        daily_returns: List of daily returns
        annual_days: Trading days per year (default 252)
        
    Returns:
        Annualized volatility as decimal
    """
    if not daily_returns or len(daily_returns) < 2:
        return 0.0
    
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    daily_std = variance ** 0.5
    
    return daily_std * (annual_days ** 0.5)


def compute_sharpe_from_returns(daily_returns: List[float], annual_days: int = 252, risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sharpe ratio from daily returns.
    
    Parameters:
        daily_returns: List of daily returns
        annual_days: Trading days per year (default 252)
        risk_free_rate: Annual risk-free rate (default 0.0)
        
    Returns:
        Sharpe ratio
    """
    if not daily_returns:
        return 0.0
    
    cagr = compute_cagr_from_returns(daily_returns, annual_days)
    volatility = compute_volatility_from_returns(daily_returns, annual_days)
    
    if volatility == 0:
        return 0.0
    
    return (cagr - risk_free_rate) / volatility


def compute_sortino_from_returns(daily_returns: List[float], annual_days: int = 252, risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sortino ratio from daily returns (uses downside deviation only).
    
    Parameters:
        daily_returns: List of daily returns
        annual_days: Trading days per year (default 252)
        risk_free_rate: Annual risk-free rate (default 0.0)
        
    Returns:
        Sortino ratio
    """
    if not daily_returns:
        return 0.0
    
    cagr = compute_cagr_from_returns(daily_returns, annual_days)
    negatives = [r for r in daily_returns if r < 0]
    
    if not negatives:
        return cagr if cagr > 0 else 0.0
    
    # Calculate downside deviation
    neg_mean = sum(negatives) / len(negatives)
    neg_variance = sum((r - neg_mean) ** 2 for r in negatives) / max(1, len(negatives) - 1)
    downside_std = neg_variance ** 0.5
    downside_vol = downside_std * (annual_days ** 0.5)
    
    if downside_vol == 0:
        return 0.0
    
    return (cagr - risk_free_rate) / downside_vol


def compute_max_drawdown_from_returns(daily_returns: List[float]) -> Tuple[float, float]:
    """
    Calculate maximum drawdown and current drawdown from daily returns.
    
    Parameters:
        daily_returns: List of daily returns
        
    Returns:
        Tuple of (max_drawdown, current_drawdown) as negative decimals
    """
    if not daily_returns:
        return 0.0, 0.0
    
    cumulative = 1.0
    peak = 1.0
    max_dd = 0.0
    
    for r in daily_returns:
        cumulative *= (1.0 + r)
        peak = max(peak, cumulative)
        dd = (cumulative - peak) / peak
        max_dd = min(max_dd, dd)
    
    current_dd = (cumulative - peak) / peak
    
    return abs(max_dd), current_dd


def compute_risk_reward(daily_returns):
    """
    Compute risk/reward ratio from daily returns.

    Args:
        daily_returns (array-like): Daily returns as floats.

    Returns:
        float: Risk/Reward ratio (avg win / avg loss as positive number).
    """
    daily_returns = np.asarray(daily_returns, dtype=float)
    wins = daily_returns[daily_returns > 0]
    losses = daily_returns[daily_returns < 0]

    if wins.size == 0 or losses.size == 0:
        return None

    avg_win = wins.mean()
    avg_loss = losses.mean()  # negative number

    return avg_win / abs(avg_loss)


def compute_win_loss_stats(daily_returns: List[float]) -> Dict[str, float]:
    """
    Calculate win/loss statistics from daily returns.
    
    Parameters:
        daily_returns: List of daily returns
        
    Returns:
        Dictionary with win_rate, avg_win, avg_loss, largest_win, largest_loss
    """
    if not daily_returns:
        return {
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
        }
    
    positives = [r for r in daily_returns if r > 0]
    negatives = [r for r in daily_returns if r < 0]
    
    return {
        "win_rate": len(positives) / len(daily_returns),
        "avg_win": sum(positives) / len(positives) if positives else 0.0,
        "avg_loss": sum(negatives) / len(negatives) if negatives else 0.0,
        "largest_win": max(daily_returns),
        "largest_loss": min(daily_returns),
    }


def compute_metrics_from_daily_returns(daily_returns: List[float], annual_days: int = 252) -> Dict[str, float]:
    """
    Compute comprehensive metrics from daily returns.
    
    Parameters:
        daily_returns: List of daily returns as decimals (e.g., 0.01 = 1%)
        annual_days: Number of trading days in a year (default 252)
        
    Returns:
        Dictionary with all performance metrics
    """
    print(f"Daily returns: {daily_returns}")

    if not daily_returns or len(daily_returns) < 1:
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
    
    # Calculate all metrics using dedicated functions
    total_return = compute_total_return_from_returns(daily_returns)
    cagr = compute_cagr_from_returns(daily_returns, annual_days)
    volatility = compute_volatility_from_returns(daily_returns, annual_days)
    sharpe = compute_sharpe_from_returns(daily_returns, annual_days)
    sortino = compute_sortino_from_returns(daily_returns, annual_days)
    reward_risk = compute_risk_reward(daily_returns)
    max_dd, current_dd = compute_max_drawdown_from_returns(daily_returns)
    win_loss = compute_win_loss_stats(daily_returns)
    
    # Calculate average daily return
    avg_daily = sum(daily_returns) / len(daily_returns)
    
    return {
        "total_return": total_return,
        "cagr": cagr,
        "win_rate": win_loss["win_rate"],
        "avg_win": win_loss["avg_win"],
        "avg_loss": win_loss["avg_loss"],
        "avg_daily": avg_daily,
        "largest_win": win_loss["largest_win"],
        "largest_loss": win_loss["largest_loss"],
        "max_drawdown": max_dd,
        "ann_std": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "reward_risk": reward_risk if reward_risk is not None else 0.0,
        "current_dd": current_dd,
    }


def compute_detailed_metrics_from_values(values: List[float]) -> Dict[str, float]:
    """
    Compute metrics from price values by first calculating daily returns.
    This is a convenience wrapper around compute_metrics_from_daily_returns.
    """
    if not values or len(values) < 2:
        return compute_metrics_from_daily_returns([])
    
    daily_returns = _daily_returns_from_values(values)
    return compute_metrics_from_daily_returns(daily_returns)


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
