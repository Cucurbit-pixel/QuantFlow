import json
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf
from screener.common import get_logger

logger = get_logger(__name__)

OPTIONS_CACHE_PATH = Path("data/options_alerts.json")
CACHE_MINUTES = 15  # 快取有效時間（分鐘）

OPTIONS_UNIVERSE = [
    "SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA", "AMD",
    "META", "AMZN", "GOOGL", "AVGO", "NFLX", "CRM", "ORCL",
    "JPM", "BAC", "XOM", "COST", "UNH"
]


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


def scan_ticker_options(ticker: str, min_vol: int = 200, min_vol_oi: float = 2.0) -> list:
    alerts = []
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty:
            return []
        spot = float(hist["Close"].iloc[-1])

        expirations = stock.options[:2] if stock.options else []  # 只取最近 2 個到期，加快速度
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

                        alerts.append({
                            "level": level,
                            "ticker": ticker,
                            "option_type": opt_type,
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


def save_options_cache(alerts: list):
    Path("data").mkdir(exist_ok=True)
    data = {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "alerts": alerts
    }
    with open(OPTIONS_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_options_cache() -> list:
    """讀取快取，過期則回傳空列表"""
    if not OPTIONS_CACHE_PATH.exists():
        return []
    try:
        with open(OPTIONS_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        scan_time = datetime.strptime(data.get("scan_time", "2000-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
        if datetime.now() - scan_time > timedelta(minutes=CACHE_MINUTES):
            logger.info("期權快取已過期")
            return []
        return data.get("alerts", [])
    except Exception as e:
        logger.error(f"讀取期權快取失敗: {e}")
        return []


def get_or_scan_options(force: bool = False) -> list:
    """
    優先讀快取；force=True 或快取過期時重新掃描並寫入快取
    """
    if not force:
        cached = load_options_cache()
        if cached:
            logger.info(f"使用期權快取，共 {len(cached)} 筆")
            return cached

    alerts = scan_options_unusual()
    save_options_cache(alerts)
    return alerts