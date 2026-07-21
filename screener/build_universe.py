from screener.common import get_logger
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

logger = get_logger(__name__)

SECTOR_FILE = "data/stock_sectors.json"
CACHE_DAYS = 60

def should_do_full_refresh(file_path: str) -> bool:
    if not os.path.exists(file_path):
        return True
    mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
    return datetime.now() - mtime > timedelta(days=CACHE_DAYS)

def load_existing_sectors(file_path: str) -> dict:
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_universe():
    Path("data").mkdir(exist_ok=True)
    
    if not should_do_full_refresh(SECTOR_FILE):
        logger.info("使用快取 sector 資料")
        return load_existing_sectors(SECTOR_FILE)
    
    logger.info("執行全量 sector 更新...")
    # 之後可以接入真實數據來源
    sectors = {"AAPL": "Information Technology", "TSLA": "Consumer Cyclical"}
    
    with open(SECTOR_FILE, "w", encoding="utf-8") as f:
        json.dump(sectors, f, indent=2, ensure_ascii=False)
    
    logger.info(f"已更新 {len(sectors)} 檔股票 sector 資訊")
    return sectors