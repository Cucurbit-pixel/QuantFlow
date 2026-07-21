from screener.common import get_logger
from screener.features import calculate_rsi, get_macd_status

logger = get_logger(__name__)

def scan_single_stock(ticker: str, price_data: dict) -> dict:
    """
    掃描單隻股票（示範用）
    """
    logger.info(f"開始掃描 {ticker}")
    
    # 簡單示範計算
    rsi = calculate_rsi(price_data.get("prices", []))
    macd_status = get_macd_status(
        price_data.get("macd_line", 0), 
        price_data.get("signal_line", 0)
    )
    
    result = {
        "ticker": ticker,
        "rsi": rsi,
        "macd_status": macd_status,
        "status": "scanned"
    }
    
    logger.info(f"{ticker} 掃描完成")
    return result