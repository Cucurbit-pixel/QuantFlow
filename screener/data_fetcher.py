import yfinance as yf
from screener.common import get_logger

logger = get_logger(__name__)


def fetch_stock_data(ticker: str) -> dict | None:
    """
    用 yfinance 獲取單一股票真實數據
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")

        if hist.empty or len(hist) < 50:
            logger.warning(f"{ticker} 數據不足，跳過")
            return None

        close = hist["Close"]
        current_price = round(close.iloc[-1], 2)
        ma20 = round(close.rolling(20).mean().iloc[-1], 2)
        ma50 = round(close.rolling(50).mean().iloc[-1], 2)

        # 簡單 MACD 計算
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

        # 簡單入場、止損、止盈計算
        entry = round(current_price * 0.995, 2)      # 稍微低於現價
        stop_loss = round(current_price * 0.97, 2)  # -3%
        tp1 = round(current_price * 1.05, 2)        # +5%
        tp2 = round(current_price * 1.10, 2)        # +10%
        tp3 = round(current_price * 1.15, 2)        # +15%

        # 簡單 RS Rating（暫時用價格相對強度近似）
        # 真正 RS Rating 需要對比 QQQ，之後可以再加強
        rs_rating = 70
        if trend_ok and macd_status in ["golden_cross", "bullish_momentum"]:
            rs_rating = 85
        if current_price > ma20 * 1.05:
            rs_rating = 90

        # Tier 判斷
        if rs_rating >= 90 and trend_ok:
            tier = "S"
        elif rs_rating >= 80:
            tier = "A"
        elif rs_rating >= 70:
            tier = "B"
        elif rs_rating >= 60:
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
            "rvol20": 1.5,          # 暫時固定，之後可加強
            "dollar_vol20": 5_000_000
        }

    except Exception as e:
        logger.error(f"獲取 {ticker} 數據失敗: {e}")
        return None


def fetch_multiple_stocks(tickers: list) -> list:
    """
    批量獲取多隻股票數據
    """
    results = []
    for ticker in tickers:
        data = fetch_stock_data(ticker)
        if data:
            results.append(data)
    return results