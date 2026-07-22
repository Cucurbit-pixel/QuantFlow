import yfinance as yf
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


def check_breakout(hist) -> str:
    """
    判斷突破是否成立
    """
    try:
        recent = hist.tail(21)
        close = recent["Close"]
        volume = recent["Volume"]

        current_price = close.iloc[-1]
        high_20 = close.iloc[:-1].max()  # 近 20 日最高（唔計今日）
        avg_volume = volume.iloc[:-1].mean()
        today_volume = volume.iloc[-1]

        # 條件：突破 20 日高 + 放量 + 收市企穩
        is_breakout = current_price > high_20
        volume_confirm = today_volume > avg_volume * 1.5
        hold_above = current_price > high_20

        if is_breakout and volume_confirm and hold_above:
            return "✅ 突破成立（放量）"
        elif is_breakout:
            return "⚠️ 突破但量能不足"
        else:
            return "➖ 無明顯突破"
    except Exception:
        return "➖ 無明顯突破"


def fetch_stock_data(ticker: str, qqq_hist=None) -> dict | None:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")  # 用 1 年數據計 52 週新高

        if hist.empty or len(hist) < 63:
            logger.warning(f"{ticker} 數據不足，跳過")
            return None

        close = hist["Close"]
        current_price = round(float(close.iloc[-1]), 2)
        ma20 = round(float(close.rolling(20).mean().iloc[-1]), 2)
        ma50 = round(float(close.rolling(50).mean().iloc[-1]), 2)
        rsi = calculate_rsi(close)

        # 52 週新高
        high_52w = float(close.max())
        distance_to_52w_high = round((current_price / high_52w - 1) * 100, 1)  # 負數代表距離新高有幾多 %

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

        # 突破是否成立
        breakout_status = check_breakout(hist)

        # 訊號判斷（已移除期權）
        if trend_ok and macd_status in ["golden_cross", "bullish_momentum"] and calculate_rs_rating(hist, qqq_hist) >= 80:
            signal_type = "strong_buy"
        elif trend_ok and calculate_rs_rating(hist, qqq_hist) >= 75:
            signal_type = "buy"
        else:
            signal_type = "watch"

        rs_rating = 50
        if qqq_hist is not None:
            rs_rating = calculate_rs_rating(hist, qqq_hist)

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

        entry = round(current_price * 0.995, 2)
        stop_loss = round(current_price * 0.97, 2)
        tp1 = round(current_price * 1.05, 2)
        tp2 = round(current_price * 1.10, 2)
        tp3 = round(current_price * 1.15, 2)

        return {
            "ticker": ticker,
            "tier": tier,
            "rs_rating": rs_rating,
            "rsi": rsi,
            "macd_status": macd_status,
            "trend": trend,
            "trend_ok": trend_ok,
            "signal_type": signal_type,
            "distance_to_52w_high": distance_to_52w_high,
            "breakout_status": breakout_status,
            "close": current_price,
            "ma20": ma20,
            "ma50": ma50,
            "entry": entry,
            "stop_loss": stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "rvol20": 1.8,
            "dollar_vol20": 8_000_000
        }

    except Exception as e:
        logger.error(f"獲取 {ticker} 數據失敗: {e}")
        return None


def fetch_multiple_stocks(tickers: list) -> list:
    try:
        qqq = yf.Ticker("QQQ")
        qqq_hist = qqq.history(period="1y")
    except Exception as e:
        logger.error(f"獲取 QQQ 失敗: {e}")
        qqq_hist = None

    results = []
    for ticker in tickers:
        data = fetch_stock_data(ticker, qqq_hist)
        if data:
            results.append(data)
    return results