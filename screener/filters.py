from screener.common import get_logger

logger = get_logger(__name__)


def apply_dynamic_filters(rows: list) -> list:
    """
    更嚴格的動態過濾
    """
    filtered = []

    for row in rows:
        rs = row.get("rs_rating", 0)
        rvol = row.get("rvol20", 0)
        dollar_vol = row.get("dollar_vol20", 0)
        tier = row.get("tier", "D")
        trend_ok = row.get("trend_ok", False)
        macd_status = row.get("macd_status", "neutral")

        # 更嚴格條件
        if (
            rs >= 80                                    # RS Rating 至少 80
            and tier in ["S", "A", "B"]                 # 只要 S/A/B 級
            and trend_ok                                # 必須多頭排列
            and macd_status in ["golden_cross", "bullish_momentum"]  # MACD 必須偏多
            and rvol >= 1.3
            and dollar_vol >= 3_000_000
        ):
            filtered.append(row)

    logger.info(f"過濾後剩餘 {len(filtered)} 檔股票")
    return filtered