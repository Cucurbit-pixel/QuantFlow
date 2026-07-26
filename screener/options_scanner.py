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
                    call_oi[k] = call_oi.get(k, 0) + oi

        if puts_df is not None and not puts_df.empty:
            for _, row in puts_df.iterrows():
                k = float(row.get("strike") or 0)
                oi = int(row.get("openInterest") or 0)
                if k > 0:
                    strikes.add(k)
                    put_oi[k] = put_oi.get(k, 0) + oi

        if not strikes:
            return None

        strike_list = sorted(strikes)
        min_pain = None
        max_pain_strike = None

        for s in strike_list:
            pain = 0.0
            for k, oi in call_oi.items():
                pain += max(0.0, s - k) * oi
            for k, oi in put_oi.items():
                pain += max(0.0, k - s) * oi
            if min_pain is None or pain < min_pain:
                min_pain = pain
                max_pain_strike = s

        return max_pain_strike
    except Exception as e:
        logger.warning(f"Max Pain 計算失敗: {e}")
        return None


def analyze_oi_structure(ticker: str) -> dict | None:
    """分析單一股票的 Call Wall / Put Wall / Max Pain"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty:
            return None
        spot = float(hist["Close"].iloc[-1])

        expirations = stock.options[:1] if stock.options else []
        if not expirations:
            return None

        exp = expirations[0]
        chain = stock.option_chain(exp)
        calls = chain.calls
        puts = chain.puts

        call_wall_strike, call_wall_oi = None, 0
        put_wall_strike, put_wall_oi = None, 0
        total_call_oi, total_put_oi = 0, 0

        if calls is not None and not calls.empty:
            for _, row in calls.iterrows():
                oi = int(row.get("openInterest") or 0)
                strike = float(row.get("strike") or 0)
                total_call_oi += oi
                if oi > call_wall_oi:
                    call_wall_oi = oi
                    call_wall_strike = strike

        if puts is not None and not puts.empty:
            for _, row in puts.iterrows():
                oi = int(row.get("openInterest") or 0)
                strike = float(row.get("strike") or 0)
                total_put_oi += oi
                if oi > put_wall_oi:
                    put_wall_oi = oi
                    put_wall_strike = strike

        max_pain = calc_max_pain(calls, puts)
        pc_ratio = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else None
        bias = "偏空" if pc_ratio and pc_ratio > 1.0 else "偏多" if pc_ratio is not None else "—"

        parts = exp.split("-")
        exp_short = f"{parts[1]}-{parts[2]}" if len(parts) == 3 else exp

        return {
            "ticker": ticker,
            "spot": round(spot, 2),
            "expiry": exp_short,
            "call_wall": call_wall_strike,
            "call_wall_oi": call_wall_oi,
            "put_wall": put_wall_strike,
            "put_wall_oi": put_wall_oi,
            "max_pain": max_pain,
            "put_call_oi_ratio": pc_ratio,
            "bias": bias
        }
    except Exception as e:
        logger.error(f"OI 結構分析 {ticker} 失敗: {e}")
        return None


def scan_options_unusual(
    tickers: list = None,
    min_vol: int = 200,
    min_vol_oi: float = 2.0,
    max_results: int = 12
) -> list:
    if tickers is None:
        tickers = OPTIONS_UNIVERSE

    all_alerts = []
    logger.info(f"開始期權異動掃描（並行），共 {len(tickers)} 隻...")

    def fetch_one(ticker):
        return scan_ticker_options(ticker, min_vol=min_vol, min_vol_oi=min_vol_oi)

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_one, t): t for t in tickers}
        for future in as_completed(futures):
            try:
                alerts = future.result()
                all_alerts.extend(alerts)
            except Exception as e:
                logger.error(f"並行期權掃描失敗: {e}")

    all_alerts.sort(key=lambda x: x["vol_oi"], reverse=True)
    result = all_alerts[:max_results]
    logger.info(f"期權異動掃描完成，找到 {len(result)} 筆")
    return result


def scan_oi_structures(tickers: list = None) -> list:
    if tickers is None:
        tickers = OI_STRUCTURE_TICKERS

    results = []
    logger.info(f"開始 OI 結構分析，共 {len(tickers)} 隻...")

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(analyze_oi_structure, t): t for t in tickers}
        for future in as_completed(futures):
            try:
                data = future.result()
                if data:
                    results.append(data)
            except Exception as e:
                logger.error(f"OI 結構並行失敗: {e}")

    results.sort(key=lambda x: x["ticker"])
    logger.info(f"OI 結構分析完成，共 {len(results)} 隻")
    return results


def save_options_cache(alerts: list):
    Path("data").mkdir(exist_ok=True)
    data = {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "alerts": alerts
    }
    with open(OPTIONS_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_oi_structure_cache(structures: list):
    Path("data").mkdir(exist_ok=True)
    data = {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "structures": structures
    }
    with open(OI_STRUCTURE_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_options_cache() -> list:
    if not OPTIONS_CACHE_PATH.exists():
        return []
    try:
        with open(OPTIONS_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        scan_time = datetime.strptime(
            data.get("scan_time", "2000-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S"
        )
        if datetime.now() - scan_time > timedelta(minutes=CACHE_MINUTES):
            return []
        return data.get("alerts", [])
    except Exception as e:
        logger.error(f"讀取期權快取失敗: {e}")
        return []


def load_oi_structure_cache() -> list:
    if not OI_STRUCTURE_CACHE_PATH.exists():
        return []
    try:
        with open(OI_STRUCTURE_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        scan_time = datetime.strptime(
            data.get("scan_time", "2000-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S"
        )
        if datetime.now() - scan_time > timedelta(minutes=CACHE_MINUTES):
            return []
        return data.get("structures", [])
    except Exception as e:
        logger.error(f"讀取 OI 結構快取失敗: {e}")
        return []


def get_or_scan_options(force: bool = False) -> list:
    if not force:
        cached = load_options_cache()
        if cached:
            return cached

    alerts = scan_options_unusual()
    save_options_cache(alerts)

    # 同步更新 OI 結構
    structures = scan_oi_structures()
    save_oi_structure_cache(structures)

    return alerts