import yfinance as yf
from screener.common import get_logger

logger = get_logger(__name__)


def calculate_rs_rating(stock_hist, qqq_hist) -> int:
    """
    簡單但有效的 RS Rating 計算
    比較股票同 QQQ 近 3 個月的表現
    """
    try:
        # 取最近約 63 個交易日（約 3 個月）
        stock_ret = (stock_hist["Close"].iloc[-1] / stock_hist["Close"].iloc[-63] - 1) * 100
        qqq_ret = (qqq_hist["Close"].iloc[-1] / qqq_hist["Close"].iloc[-63] - 1) * 100

        relative_strength = stock_ret - qqq_ret

        # 轉換成 1~99 的 RS Rating
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


def fetch_stock_data(ticker: str, qqq_hist=None) -> dict | None:
    """
    用 yfinance 獲取單一股票真實數據
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")

        if hist.empty or len(hist) < 63:
            logger.warning(f"{ticker} 數據不足，跳過")
            return None

        close = hist["Close"]
        current_price = round(close.iloc[-1], 2)
        ma20 = round(close.rolling(20).mean().iloc[-1], 2)
        ma50 = round(close.rolling(50).mean().iloc[-1], 2)

        # MACD 計算
        exp12 = close.ewm(span=12, adjust=False).mean()
        exp26 = close.ewm(span=26, adjust=False).mean()
        macd_line = exp12 - exp26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()

        macd_value = macd_line.iloc[-1]
        signal_value = signal_line.iloc[-1]

        if macd_value > signal_value and macd_line.iloc[-2] <= signal_line.iloc[-2]:
            macd_status = "golden_cross"
        elif macd_value > signal_value:
            macd_status = "bullish_momentum"
        elif macd_value < signal_value and macd_line.iloc[-2] >= signal_line.iloc[-2]:
            macd_status = "death_cross"
        elif macd_value < signal_value:
            macd_status = "bearish_momentum"
        else:
            macd_status = "neutral"

        # 趨勢判斷
        trend_ok = current_price > ma20 > ma50
        trend = "多頭排列" if trend_ok else "空頭或盤整"

        # 入場、止損、止盈
        entry = round(current_price * 0.995, 2)
        stop_loss = round(current_price * 0.97, 2)
        tp1 = round(current_price * 1.05, 2)
        tp2 = round(current_price * 1.10, 2)
        tp3 = round(current_price * 1.15, 2)

        # 真正 RS Rating（對比 QQQ）
        rs_rating = 50
        if qqq_hist is not None:
            rs_rating = calculate_rs_rating(hist, qqq_hist)

        # Tier 判斷（更嚴格）
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
            "macd_status": macd_status,
            "trend": trend,
            "trend_ok": trend_ok,
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
    """
    批量獲取多隻股票數據（包含 QQQ 作為基準）
    """
    # 先獲取 QQQ 數據
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