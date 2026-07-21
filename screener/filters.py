 from screener.common import get_logger

logger = get_logger(__name__)

def apply_dynamic_filters(rows: list) -> list:
    """
    簡單動態過濾
    """
    filtered = []
    
    for row in rows:
        rs = row.get("rs_rating", 0)
        rvol = row.get("rvol20", 0)
        dollar_vol = row.get("dollar_vol20", 0)
        
        if rs >= 55 and rvol >= 1.3 and dollar_vol >= 1_000_000:
            filtered.append(row)
    
    logger.info(f"過濾後剩餘 {len(filtered)} 檔股票")
    return filtered