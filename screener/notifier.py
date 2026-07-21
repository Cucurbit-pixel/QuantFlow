from screener.common import get_logger
import requests
import os

logger = get_logger(__name__)

def send_discord_message(message: str):
    webhook = os.getenv("DISCORD_WEBHOOK", "")
    
    if not webhook:
        logger.warning("未設定 Discord Webhook，跳過發送通知")
        return
    
    try:
        payload = {"content": message}
        response = requests.post(webhook, json=payload)
        if response.status_code == 204:
            logger.info("Discord 通知發送成功")
        else:
            logger.error(f"Discord 通知發送失敗: {response.status_code}")
    except Exception as e:
        logger.error(f"發送 Discord 通知時發生錯誤: {e}")