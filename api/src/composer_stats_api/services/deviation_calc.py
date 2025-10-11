from __future__ import annotations

from typing import Dict, List, Tuple
import math


def align_series_by_date(
    live_dates: List[str],
    live_values: List[float],
    backtest_dates: List[str],
    backtest_values: List[float],
) -> Tuple[List[str], List[float], List[float]]:
    """
    Align two time series by date, keeping only dates that exist in both series.

    Returns:
        Tuple of (aligned_dates, aligned_live_values, aligned_backtest_values)
    """
    # Create lookup maps
    live_map = {date: value for date, value in zip(live_dates, live_values)}
    backtest_map = {date: value for date, value in zip(backtest_dates, backtest_values)}

    # Find common dates
    common_dates = sorted(set(live_dates) & set(backtest_dates))

    if not common_dates:
        return [], [], []

    aligned_live = [live_map[date] for date in common_dates]
    aligned_backtest = [backtest_map[date] for date in common_dates]

    return common_dates, aligned_live, aligned_backtest


def calculate_daily_returns(values: List[float]) -> List[float]:
    """
    Calculate daily returns from a series of values.
    Returns list will have length = len(values) - 1
    """
    if len(values) < 2:
        return []

    returns = []
    for i in range(1, len(values)):
        if values[i - 1] > 0:
            ret = (values[i] / values[i - 1]) - 1.0
            returns.append(ret)
        else:
            returns.append(0.0)

    return returns


def calculate_tracking_error(
    live_returns: List[float], backtest_returns: List[float]
) -> float:
    """
    Calculate tracking error: standard deviation of the difference in returns.
    A higher tracking error indicates more deviation between live and backtest.
    """
    if len(live_returns) != len(backtest_returns) or len(live_returns) == 0:
        return 0.0

    differences = [lr - br for lr, br in zip(live_returns, backtest_returns)]

    # Calculate standard deviation of differences
    mean_diff = sum(differences) / len(differences)
    variance = sum((d - mean_diff) ** 2 for d in differences) / len(differences)

    # Annualize tracking error (assume 252 trading days)
    tracking_error = math.sqrt(variance) * math.sqrt(252)

    return tracking_error


def calculate_rmse(live_values: List[float], backtest_values: List[float]) -> float:
    """
    Calculate Root Mean Square Error between live and backtest values.
    Measures the average magnitude of deviation.
    """
    if len(live_values) != len(backtest_values) or len(live_values) == 0:
        return 0.0

    squared_errors = [(lv - bv) ** 2 for lv, bv in zip(live_values, backtest_values)]
    mse = sum(squared_errors) / len(squared_errors)

    return math.sqrt(mse)


def calculate_rmse_returns(
    live_returns: List[float], backtest_returns: List[float]
) -> float:
    """
    Calculate Root Mean Square Error between live and backtest returns.
    This is scale-invariant and better for measuring performance drift.

    RMSE = sqrt((1/N) * sum((L_i - B_i)^2))
    """
    if len(live_returns) != len(backtest_returns) or len(live_returns) == 0:
        return 0.0

    n = len(live_returns)
    squared_errors = [(lr - br) ** 2 for lr, br in zip(live_returns, backtest_returns)]
    mse = sum(squared_errors) / n

    return math.sqrt(mse)


def calculate_correlation(
    live_returns: List[float], backtest_returns: List[float]
) -> float:
    """
    Calculate Pearson correlation coefficient between live and backtest returns.
    Values close to 1.0 indicate high similarity, close to 0 indicate no relationship.
    """
    if len(live_returns) != len(backtest_returns) or len(live_returns) < 2:
        return 0.0

    n = len(live_returns)

    # Calculate means
    mean_live = sum(live_returns) / n
    mean_backtest = sum(backtest_returns) / n

    # Calculate correlation coefficient
    numerator = sum(
        (lr - mean_live) * (br - mean_backtest)
        for lr, br in zip(live_returns, backtest_returns)
    )

    sum_sq_live = sum((lr - mean_live) ** 2 for lr in live_returns)
    sum_sq_backtest = sum((br - mean_backtest) ** 2 for br in backtest_returns)

    denominator = math.sqrt(sum_sq_live * sum_sq_backtest)

    if denominator == 0:
        return 0.0

    return numerator / denominator


def calculate_max_deviation(
    live_values: List[float], backtest_values: List[float]
) -> float:
    """
    Calculate the maximum absolute deviation between live and backtest values.
    Normalized as a percentage of the backtest value.
    """
    if len(live_values) != len(backtest_values) or len(live_values) == 0:
        return 0.0

    max_dev = 0.0
    for lv, bv in zip(live_values, backtest_values):
        if bv > 0:
            deviation = abs((lv - bv) / bv)
            max_dev = max(max_dev, deviation)

    return max_dev


def calculate_mean_deviation(
    live_values: List[float], backtest_values: List[float]
) -> float:
    """
    Calculate the mean absolute deviation between live and backtest values.
    Normalized as a percentage of the backtest value.
    """
    if len(live_values) != len(backtest_values) or len(live_values) == 0:
        return 0.0

    deviations = []
    for lv, bv in zip(live_values, backtest_values):
        if bv > 0:
            deviation = abs((lv - bv) / bv)
            deviations.append(deviation)

    if not deviations:
        return 0.0

    return sum(deviations) / len(deviations)


def calculate_cumulative_return_deviation(
    live_values: List[float], backtest_values: List[float]
) -> float:
    """
    Calculate the deviation between cumulative returns (first to last value).
    """
    if len(live_values) < 2 or len(backtest_values) < 2:
        return 0.0

    if live_values[0] <= 0 or backtest_values[0] <= 0:
        return 0.0

    live_cumulative_return = (live_values[-1] / live_values[0]) - 1.0
    backtest_cumulative_return = (backtest_values[-1] / backtest_values[0]) - 1.0

    return live_cumulative_return - backtest_cumulative_return


def compute_deviation_metrics(
    live_dates: List[str],
    live_values: List[float],
    backtest_dates: List[str],
    backtest_values: List[float],
) -> Dict[str, float]:
    """
    Compute comprehensive deviation metrics between live and backtest performance.

    Returns a dictionary with:
    - tracking_error: Annualized standard deviation of return differences (higher = more deviation)
    - correlation: Pearson correlation of returns (closer to 1 = more similar)
    - rmse: Root mean square error of values
    - rmse_returns: Root mean square error of returns
    - max_deviation: Maximum percentage deviation
    - mean_deviation: Average percentage deviation
    - cumulative_return_deviation: Difference in total returns
    - ldr: Live-Drift Risk metric = RMSE × (1 - ρ), where ρ is correlation
    - risk_score: Same as LDR for backward compatibility
    """
    # Align the series by date
    aligned_dates, aligned_live, aligned_backtest = align_series_by_date(
        live_dates, live_values, backtest_dates, backtest_values
    )

    if len(aligned_dates) < 2:
        return {
            "tracking_error": 0.0,
            "correlation": 0.0,
            "rmse": 0.0,
            "rmse_returns": 0.0,
            "max_deviation": 0.0,
            "mean_deviation": 0.0,
            "cumulative_return_deviation": 0.0,
            "ldr": 0.0,
            "risk_score": 0.0,
            "num_data_points": 0,
        }

    # Calculate daily returns
    live_returns = calculate_daily_returns(aligned_live)
    backtest_returns = calculate_daily_returns(aligned_backtest)

    # Calculate all metrics
    tracking_error = calculate_tracking_error(live_returns, backtest_returns)
    correlation = calculate_correlation(live_returns, backtest_returns)
    rmse = calculate_rmse(aligned_live, aligned_backtest)
    rmse_returns = calculate_rmse_returns(live_returns, backtest_returns)
    max_deviation = calculate_max_deviation(aligned_live, aligned_backtest)
    mean_deviation = calculate_mean_deviation(aligned_live, aligned_backtest)
    cumulative_return_dev = calculate_cumulative_return_deviation(
        aligned_live, aligned_backtest
    )

    # Calculate LDR (Live-Drift Risk) metric:
    # LDR = RMSE × (1 - ρ)
    # Where:
    # - RMSE = Root Mean Squared Error between live and backtest returns
    # - ρ (rho) = Pearson correlation coefficient between returns
    #
    # We scale it to be more interpretable:
    # LDR_raw = RMSE_returns × 100 × (2 - correlation)
    # Then normalize to 0-100 scale where:
    # - 0 = perfect tracking (best)
    # - 100 = worst tracking (worst)
    ldr_raw = rmse_returns * 100.0 * (2.0 - correlation)

    # Normalize to 0-100 scale
    # Using min(100, ldr_raw * 100) gives us a clean bounded scale:
    # - LDR_raw = 0.0 → 0 (perfect)
    # - LDR_raw = 0.1 → 10 (low risk)
    # - LDR_raw = 0.5 → 50 (moderate risk)
    # - LDR_raw = 1.0 → 100 (high risk)
    # - LDR_raw > 1.0 → 100 (capped at worst)
    ldr = min(100.0, ldr_raw * 100.0)

    return {
        "tracking_error": tracking_error,
        "correlation": correlation,
        "rmse": rmse,
        "rmse_returns": rmse_returns,
        "max_deviation": max_deviation,
        "mean_deviation": mean_deviation,
        "cumulative_return_deviation": cumulative_return_dev,
        "ldr": ldr,
        "risk_score": ldr,  # Use LDR as the risk_score for backward compatibility
        "num_data_points": len(aligned_dates),
    }
