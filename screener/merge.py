from screener.common import get_logger
from screener.filters import apply_dynamic_filters
from screener.notifier import send_discord_message
from screener.build_universe import build_universe

logger = get_logger(__name__)

def run_full_scan():
    logger.info("開始執行完整掃描...")

    # 建立/更新 Universe
    build_universe()

    # 示範數據（之後會換成真實數據）
    sample_data = [
        {"ticker": "AAPL", "rs_rating": 92, "rvol20": 3.5, "dollar_vol20": 18000000},
        {"ticker": "TSLA", "rs_rating": 48, "rvol20": 0.9, "dollar_vol20": 3800000},
        {"ticker": "NVDA", "rs_rating": 88, "rvol20": 2.8, "dollar_vol20": 15000000},
    ]
    
    filtered = apply_dynamic_filters(sample_data)
    
    result_msg = f"掃描完成！符合條件嘅股票：{[r['ticker'] for r in filtered]}"
    logger.info(result_msg)
    
    # 發送 Discord 通知
    send_discord_message(result_msg)
    
    return filtered

if __name__ == "__main__":
    run_full_scan()