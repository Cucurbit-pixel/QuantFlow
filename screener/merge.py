from screener.common import get_logger
from screener.filters import apply_dynamic_filters

logger = get_logger(__name__)

def run_full_scan():
    logger.info("開始執行完整掃描...")
    
    # 這裡之後會接入真實數據
    sample_data = [
        {"ticker": "AAPL", "rs_rating": 92, "rvol20": 3.5, "dollar_vol20": 18000000},
        {"ticker": "TSLA", "rs_rating": 48, "rvol20": 0.9, "dollar_vol20": 3800000},
    ]
    
    filtered = apply_dynamic_filters(sample_data)
    
    logger.info(f"掃描完成，符合條件嘅股票：{[r['ticker'] for r in filtered]}")
    return filtered

if __name__ == "__main__":
    run_full_scan()