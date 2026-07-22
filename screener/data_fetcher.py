import yfinance as yf
from datetime import datetime, timedelta
from screener.common import get_logger

logger = get_logger(__name__)


def calculate_rsi(series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 1)


def calculate_rs_rating(stock_hist, qqq_hist) -> int:
    try:
        stock_ret = (stock_hist["Close"].iloc[-1] / stock_hist["Close"].iloc[-63] - 1) * 100
        qqq_ret = (qqq_hist["Close"].iloc[-1] / qqq_hist["Close"].iloc[-63] - 1) * 100
        relative_strength = stock_ret - qqq_ret

        if relative_strength >= 30:
            return 95
        elif relative_strength >= 20:
            return 90
        elif relative_strength >= 10:
            return 85
        elif relative_strength >= 5:
            return 80
        elif relative_strength >= 0:
            return 70
        elif relative_strength >= -5:
            return 60
        elif relative_strength >= -10:
            return 50
        else:
            return 40
    except Exception:
        return 50


def get_next_monthly_expiration() -> str:
    """下一個月期權（下個月第3個星期五）"""
    today = datetime.now()
    year = today.year
    month = today.month + 1
    if month > 12:
        month = 1
        year += 1

    # 找第3個星期五
    first_day = datetime(year, month, 1)
    first_friday = first_day + timedelta(days=(4 - first_day.weekday() + 7) % 7)
    third_friday = first_friday + timedelta(weeks=2)
    return third_friday.strftime("%Y-%m-%d")


def get_near_term_expiration() -> str:
    """近月到期（大約 2～3 週後的星期五）"""
    today = datetime.now()
    days_ahead = 18  # 約 2.5 週
    target = today + timedelta(days=days_ahead)
    # 調到最近的星期五
    days_to_friday = (4 - target.weekday() + 7) % 7
    friday = target + timedelta(days=days_to_friday)
    return friday.strftime("%Y-%m-%d")


def determine_signal(rsi: float, trend_ok: bool, macd_status: str, rs_rating: int, 
                     current_price: float, ma20: float) -> str:
    """
    判斷四種 Options 訊號 + 普通買賣訊號
    """
    # 1. Sell Call（見頂）
    if rsi >= 70 and current_price > ma20 * 1.08 and rs_rating >= 80:
        return "sell_call"

    # 2. Long Put（見頂 + 轉弱）
    if rsi >= 70 and macd_status in ["death_cross", "bearish_momentum"] and current_price > ma20 * 1.06:
        return "long_put"

    # 3. Sell Put（見底）
    if rsi <= 30 and rs_rating >= 60:
        return "sell_put"

    # 4. Long Call（見底 + 轉強）
    if rsi <= 35 and macd_status in ["golden_cross", "bullish_momentum"]:
        return "long_call"

    # 普通買入訊號
    if trend_ok and macd_status in ["golden_cross", "bullish_momentum"] and rs_rating >= 80:
        return "strong_buy"

    if trend_ok and rs_rating >= 75:
        return "buy"

    return "watch"


def fetch_stock_data(ticker: str, qqq_hist=None) -> dict | None:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")

        if hist.empty or len(hist) < 63:
            logger.warning(f"{ticker} 數據不足，跳過")
            return None

        close = hist["Close"]
        current_price = round(float(close.iloc[-1]), 2)
        ma20 = round(float(close.rolling(20).mean().iloc[-1]), 2)
        ma50 = round(float(close.rolling(50).mean().iloc[-1]), 2)
        rsi = calculate_rsi(close)

        # MACD
        exp12 = close.ewm(span=12, adjust=False).mean()
        exp26 = close.ewm(span=26, adjust=False).mean()
        macd_line = exp12 - exp26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()

        macd_value = float(macd_line.iloc[-1])
        signal_value = float(signal_line.iloc[-1])
        prev_macd = float(macd_line.iloc[-2])
        prev_signal = float(signal_line.iloc[-2])

        if macd_value > signal_value and prev_macd <= prev_signal:
            macd_status = "golden_cross"
        elif macd_value > signal_value:
            macd_status = "bullish_momentum"
        elif macd_value < signal_value and prev_macd >= prev_signal:
            macd_status = "death_cross"
        elif macd_value < signal_value:
            macd_status = "bearish_momentum"
        else:
            macd_status = "neutral"

        trend_ok = current_price > ma20 > ma50
        trend = "多頭排列" if trend_ok else "空頭或盤整"

        entry = round(current_price * 0.995, 2)
        stop_loss = round(current_price * 0.97, 2)
        tp1 = round(current_price * 1.05, 2)
        tp2 = round(current_price * 1.10, 2)
        tp3 = round(current_price * 1.15, 2)

        rs_rating = 50
        if qqq_hist is not None:
            rs_rating = calculate_rs_rating(hist, qqq_hist)

        signal_type = determine_signal(rsi, trend_ok, macd_status, rs_rating, current_price, ma20)

        # Options 行權價
        if signal_type in ["sell_call", "long_call"]:
            suggested_strike = round(current_price * 1.06, 2)
        elif signal_type in ["sell_put", "long_put"]:
            suggested_strike = round(current_price * 0.95, 2)
        else:
            suggested_strike = None

        near_term_exp = get_near_term_expiration()
        monthly_exp = get_next_monthly_expiration()

        # Tier
        if rs_rating >= 90 and trend_ok and macd_status in ["golden_cross", "bullish_momentum"]:
            tier = "S"
        elif rs_rating >= 85 and trend_ok:
            tier = "A"
        elif rs_rating >= 75:
            tier = "B"
        elif rs_rating >= 65:
            tier = "C"
        else:
            tier = "D"

        return {
            "ticker": ticker,
            "tier": tier,
            "rs_rating": rs_rating,
            "rsi": rsi,
            "macd_status": macd_status,
            "trend": trend,
            "trend_ok": trend_ok,
            "signal_type": signal_type,
            "close": current_price,
            "ma20": ma20,
            "ma50": ma50,
            "entry": entry,
            "stop_loss": stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "suggested_strike": suggested_strike,
            "near_term_exp": near_term_exp,
            "monthly_exp": monthly_exp,
            "rvol20": 1.8,
            "dollar_vol20": 8_000_000
        }

    except Exception as e:
        logger.error(f"獲取 {ticker} 數據失敗: {e}")
        return None


def fetch_multiple_stocks(tickers: list) -> list:
    try:
        qqq = yf.Ticker("QQQ")
        qqq_hist = qqq.history(period="6mo")
    except Exception as e:
        logger.error(f"獲取 QQQ 失敗: {e}")
        qqq_hist = None

    results = []
    for ticker in tickers:
        data = fetch_stock_data(ticker, qqq_hist)
        if data:
            results.append(data)
    return results