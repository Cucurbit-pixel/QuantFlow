import yfinance as yf
from screener.common import get_logger

logger = get_logger(__name__)

# 精選流動性高的股票（避免掃太多導致超時）
OPTIONS_UNIVERSE = [
    "SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA", "AMD",
    "META", "AMZN", "GOOGL", "AVGO", "NFLX", "CRM", "ORCL",
    "JPM", "BAC", "XOM", "COST", "UNH"
]


def get_moneyness(option_type: str, strike: float, spot: float) -> str:
    """判斷價內 / 價外 / 平價"""
    if option_type == "CALL":
        if strike < spot * 0.98:
            return "價內"
        elif strike > spot * 1.02:
            return "價外"
        else:
            return "平價"
    else:  # PUT
        if strike > spot * 1.02:
            return "價內"
        elif strike < spot * 0.98:
            return "價外"
        else:
            return "平價"


def scan_ticker_options(ticker: str, min_vol: int = 200, min_vol_oi: float = 2.0) -> list:
    """掃描單一股票的期權異動"""
    alerts = []
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty:
            return []
        spot = float(hist["Close"].iloc[-1])

        # 只取最近 3 個到期日，加快速度
        expirations = stock.options[:3] if stock.options else []
        if not expirations:
            return []

        for exp in expirations:
            try:
                chain = stock.option_chain(exp)
                # 轉成 MM-DD
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

                        # 分級
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
    max_results: int = 15
) -> list:
    """
    掃描期權異動
    回傳格式同 Dashboard 使用的結構
    """
    if tickers is None:
        tickers = OPTIONS_UNIVERSE

    all_alerts = []
    logger.info(f"開始期權異動掃描，共 {len(tickers)} 隻...")

    for ticker in tickers:
        alerts = scan_ticker_options(ticker, min_vol=min_vol, min_vol_oi=min_vol_oi)
        all_alerts.extend(alerts)

    # 按爆發比例由高到低排序
    all_alerts.sort(key=lambda x: x["vol_oi"], reverse=True)

    # 限制數量
    result = all_alerts[:max_results]
    logger.info(f"期權異動掃描完成，找到 {len(result)} 筆")

    return result