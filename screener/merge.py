from screener.common import get_logger
from screener.filters import apply_dynamic_filters
from screener.notifier import send_multiple_embeds, send_discord_message
from screener.build_universe import build_universe

logger = get_logger(__name__)


def run_full_scan():
    logger.info("開始執行完整掃描...")

    # 建立/更新 Universe
    build_universe()

    # 示範數據（之後會換成真實數據）
    sample_data = [
        {
            "ticker": "CVLG",
            "tier": "S",
            "rs_rating": 96,
            "macd_status": "bullish_momentum",
            "trend": "多頭排列",
            "close": 49.13,
            "ma20": 45.54,
            "ma50": 42.04,
            "entry": 48.88,
            "stop_loss": 47.66,
            "tp1": 51.32,
            "tp2": 53.77,
            "tp3": 56.21,
            "rvol20": 3.5,
            "dollar_vol20": 18000000
        },
        {
            "ticker": "BJRI",
            "tier": "S",
            "rs_rating": 95,
            "macd_status": "bullish_momentum",
            "trend": "多頭排列",
            "close": 68.00,
            "ma20": 60.81,
            "ma50": 51.97,
            "entry": 67.66,
            "stop_loss": 65.96,
            "tp1": 71.04,
            "tp2": 74.43,
            "tp3": 77.81,
            "rvol20": 2.8,
            "dollar_vol20": 15000000
        },
    ]
    
    # 過濾
    filtered = apply_dynamic_filters(sample_data)
    
    if not filtered:
        msg = "掃描完成，冇股票符合條件"
        logger.info(msg)
        send_discord_message(msg)
        return []

    # 發送 Embed 通知
    send_multiple_embeds(filtered)
    
    tickers = [r["ticker"] for r in filtered]
    logger.info(f"掃描完成，符合條件嘅股票：{tickers}")
    
    return filtered


if __name__ == "__main__":
    run_full_scan()