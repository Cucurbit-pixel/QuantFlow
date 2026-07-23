import json
from pathlib import Path
from screener.common import get_logger
from screener.filters import apply_dynamic_filters
from screener.notifier import send_multiple_embeds, send_discord_message
from screener.build_universe import build_universe
from screener.data_fetcher import fetch_multiple_stocks

logger = get_logger(__name__)


def save_scan_result(filtered: list):
    """把掃描結果存成 JSON"""
    Path("data").mkdir(exist_ok=True)
    
    result = {
        "scan_time": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(filtered),
        "stocks": filtered
    }
    
    with open("data/latest_scan.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"已儲存掃描結果到 data/latest_scan.json（{len(filtered)} 隻）")


def run_full_scan():
    logger.info("開始執行完整掃描...")

    # 建立/更新 Universe
    build_universe()

    # 25 隻股票清單
    tickers = [
        "AAPL", "NVDA", "MSFT", "AMZN", "META",
        "GOOGL", "TSLA", "AMD", "AVGO", "CRM",
        "NFLX", "COST", "ADBE", "PEP", "LLY",
        "V", "MA", "JPM", "XOM", "UNH",
        "HD", "PG", "KO", "WMT", "ORCL"
    ]

    logger.info(f"開始獲取 {len(tickers)} 隻股票真實數據...")
    stock_data = fetch_multiple_stocks(tickers)
    logger.info(f"成功獲取 {len(stock_data)} 隻股票數據")

    if not stock_data:
        msg = "掃描完成，無法獲取任何股票數據"
        logger.warning(msg)
        send_discord_message(msg)
        return []

    # 過濾
    filtered = apply_dynamic_filters(stock_data)

    # 儲存結果（即使係 0 隻都儲存）
    save_scan_result(filtered)

    if not filtered:
        msg = "掃描完成，冇股票符合條件"
        logger.info(msg)
        send_discord_message(msg)
        return []

    # 發送 Discord 通知
    send_multiple_embeds(filtered)

    tickers_result = [r["ticker"] for r in filtered]
    logger.info(f"掃描完成，符合條件嘅股票：{tickers_result}")

    return filtered


if __name__ == "__main__":
    run_full_scan()