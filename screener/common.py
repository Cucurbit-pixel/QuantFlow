import logging
from logging.handlers import RotatingFileHandler
import os

def get_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # 控制台輸出
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 檔案輸出（可選）
        os.makedirs("logs", exist_ok=True)
        file_handler = RotatingFileHandler(
            "logs/quantflow.log", maxBytes=5*1024*1024, backupCount=3
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger