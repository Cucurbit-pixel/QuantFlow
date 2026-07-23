import json
from pathlib import Path
from screener.common import get_logger
from screener.filters import apply_dynamic_filters
from screener.notifier import send_multiple_embeds, send_discord_message
from screener.build_universe import build_universe
from screener.data_fetcher import fetch_multiple_stocks

logger = get_logger(__name__)


def load_config():
    """讀取搜尋條件設定"""
    config_path = Path("data/config.json")
    if not config_path.exists():
        logger.warning("找不到 config.json，使用預設設定")
        return {
            "min_rs_rating": 80,
            "require_trend_ok": True,
            "require_macd_bullish": True,
            "tickers": ["AAPL", "NVDA", "MSFT", "AMZN", "META"]
        }
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


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

    # 讀取設定
    config = load_config()
    tickers = config.get("tickers", [])
    min_rs = config.get("min_rs_rating", 80)
    require_trend = config.get("require_trend_ok", True)
    require_macd = config.get("require_macd_bullish", True)

    logger.info(f"設定：min_rs={min_rs}, require_trend={require_trend}, require_macd={require_macd}")
    logger.info(f"股票數量：{len(tickers)}")

    # 建立/更新 Universe
    build_universe()

    # 獲取真實數據
    logger.info(f"開始獲取 {len(tickers)} 隻股票真實數據...")
    stock_data = fetch_multiple_stocks(tickers)
    logger.info(f"成功獲取 {len(stock_data)} 隻股票數據")

    if not stock_data:
        msg = "掃描完成，無法獲取任何股票數據"
        logger.warning(msg)
        send_discord_message(msg)
        save_scan_result([])
        return []

    # 動態過濾（根據 config）
    filtered = []
    for row in stock_data:
        rs = row.get("rs_rating", 0)
        trend_ok = row.get("trend_ok", False)
        macd_status = row.get("macd_status", "neutral")

        if rs < min_rs:
            continue
        if require_trend and not trend_ok:
            continue
        if require_macd and macd_status not in ["golden_cross", "bullish_momentum"]:
            continue

        filtered.append(row)

    logger.info(f"過濾後剩餘 {len(filtered)} 檔股票")

    # 儲存結果
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