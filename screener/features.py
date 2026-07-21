from screener.common import get_logger

logger = get_logger(__name__)

def calculate_rsi(prices: list, period: int = 14) -> float:
    """簡單 RSI 計算"""
    if len(prices) < period + 1:
        return 50.0
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def get_macd_status(macd_line: float, signal_line: float) -> str:
    """判斷 MACD 狀態"""
    if macd_line > signal_line:
        return "bullish_momentum"
    elif macd_line < signal_line:
        return "bearish_momentum"
    else:
        return "neutral"