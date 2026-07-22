from screener.common import get_logger
from screener.filters import apply_dynamic_filters
from screener.notifier import send_multiple_embeds, send_discord_message
from screener.build_universe import build_universe
from screener.data_fetcher import fetch_multiple_stocks

logger = get_logger(__name__)


def run_full_scan():
    logger.info("開始執行完整掃描...")

    # 建立/更新 Universe
    build_universe()

    # ========== 真實股票清單（可之後改成從 Universe 讀取）==========
    tickers = [
        "AAPL", "NVDA", "TSLA", "MSFT", "AMZN",
        "META", "GOOGL", "AMD", "AVGO", "CRM"
    ]

    # 獲取真實數據
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

    if not filtered:
        msg = "掃描完成，冇股票符合條件"
        logger.info(msg)
        send_discord_message(msg)
        return []

    # 發送 Embed 通知
    send_multiple_embeds(filtered)

    tickers_result = [r["ticker"] for r in filtered]
    logger.info(f"掃描完成，符合條件嘅股票：{tickers_result}")

    return filtered


if __name__ == "__main__":
    run_full_scan()