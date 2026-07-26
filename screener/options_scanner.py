import json
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf
from screener.common import get_logger

logger = get_logger(__name__)

OPTIONS_CACHE_PATH = Path("data/options_alerts.json")
OI_STRUCTURE_CACHE_PATH = Path("data/oi_structure.json")
CACHE_MINUTES = 15

OPTIONS_UNIVERSE = [
    "SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA", "AMD",
    "META", "AMZN", "GOOGL", "AVGO", "NFLX", "CRM", "ORCL",
    "JPM", "BAC", "XOM", "COST", "UNH"
]

# 用於 OI 結構分析的精選標的（避免太慢）
OI_STRUCTURE_TICKERS = ["SPY", "QQQ", "TSLA", "NVDA", "AAPL", "AMZN", "META"]


def get_moneyness(option_type: str, strike: float, spot: float) -> str:
    if option_type == "CALL":
        if strike < spot * 0.98:
            return "價內"
        elif strike > spot * 1.02:
            return "價外"
        else:
            return "平價"
    else:
        if strike > spot * 1.02:
            return "價內"
        elif strike < spot * 0.98:
            return "價外"
        else:
            return "平價"


def get_action_and_bias(option_type: str) -> tuple:
    """
    免費數據無法精確分買賣方向，暫用約定：
    Call → 買入 Call / 偏多
    Put  → 買入 Put / 偏空
    """
    if option_type == "CALL":
        return "買入 Call", "偏多"
    return "買入 Put", "偏空"


def scan_ticker_options(ticker: str, min_vol: int = 200, min_vol_oi: float = 2.0) -> list:
    alerts = []
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty:
            return []
        spot = float(hist["Close"].iloc[-1])

        expirations = stock.options[:2] if stock.options else []
        if not expirations:
            return []

        for exp in expirations:
            try:
                chain = stock.option_chain(exp)
                parts = exp.split("-")
                exp_short = f"{parts[1]}-{parts[2]}" if len(parts) == 3 else exp

                for opt_type, df in [("CALL", chain.calls), ("PUT", chain.puts)]:
                    if df is None or df.empty:
                        continue

                    for _, row in df.iterrows():
                        volume = int(row.get("volume") or 0)
                        oi = int(row.get("openInterest") or 0)
                        strike = float(row.get("strike") or 0)

                        if volume < min_vol or oi <= 0:
                            continue

                        vol_oi = round(volume / oi, 2)
                        if vol_oi < min_vol_oi:
                            continue

                        if vol_oi >= 4.0 and volume >= 500:
                            level = "high"
                        elif vol_oi >= 2.5 and volume >= 300:
                            level = "medium"
                        else:
                            level = "low"

                        action, bias = get_action_and_bias(opt_type)

                        alerts.append({
                            "level": level,
                            "ticker": ticker,
                            "option_type": opt_type,
                            "action": action,
                            "bias": bias,
                            "strike": strike,
                            "expiry": exp_short,
                            "vol_oi": vol_oi,
                            "volume": volume,
                            "oi": oi,
                            "moneyness": get_moneyness(opt_type, strike, spot)
                        })
            except Exception as e:
                logger.warning(f"{ticker} {exp} 期權鏈失敗: {e}")
                continue

    except Exception as e:
        logger.error(f"掃描 {ticker} 期權失敗: {e}")

    return alerts


def calc_max_pain(calls_df, puts_df) -> float | None:
    """計算 Max Pain（使期權買家總虧損最大的到價）"""
    try:
        strikes = set()
        call_oi = {}
        put_oi = {}

        if calls_df is not None and not calls_df.empty:
            for _, row in calls_df.iterrows():
                k = float(row.get("strike") or 0)
                oi = int(row.get("openInterest") or 0)
                if k > 0:
                    strikes.add(k)
                    call