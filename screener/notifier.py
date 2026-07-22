import requests
import os
import time
from typing import List


def get_priority(signal_type: str) -> str:
    if signal_type == "strong_buy":
        return "🟢 普通"
    elif signal_type == "buy":
        return "🟢 普通"
    else:
        return "⚪ 低"


def build_embed(candidate: dict) -> dict:
    ticker = candidate.get("ticker", "UNKNOWN")
    tier = candidate.get("tier", "C")
    rs_rating = candidate.get("rs_rating", 0)
    rsi = candidate.get("rsi", 0)
    macd_status = candidate.get("macd_status", "neutral")
    trend = candidate.get("trend", "多頭排列")
    signal_type = candidate.get("signal_type", "watch")
    distance_to_52w = candidate.get("distance_to_52w_high", 0)
    breakout_status = candidate.get("breakout_status", "➖ 無明顯突破")

    tier_colors = {
        "S": 0xE63946,
        "A": 0xF4A261,
        "B": 0x2A9D8F,
        "C": 0xE9C46A,
        "D": 0x457B9D,
    }
    color = tier_colors.get(tier, 0x6C757D)

    macd_map = {
        "golden_cross": "🟢 金叉",
        "bullish_momentum": "🟢 多頭動能",
        "death_cross": "🔴 死叉",
        "bearish_momentum": "🔴 空頭動能",
        "neutral": "⚪ 中性",
    }
    macd_display = macd_map.get(macd_status, "⚪ 中性")

    signal_map = {
        "strong_buy": "🚀🚀🚀 強烈買入",
        "buy": "🚀 買入",
        "watch": "👀 觀察",
    }
    signal_display = signal_map.get(signal_type, "👀 觀察")
    priority = get_priority(signal_type)

    entry = candidate.get("entry", 0)
    tp1 = candidate.get("tp1", 0)
    tp2 = candidate.get("tp2", 0)
    tp3 = candidate.get("tp3", 0)
    stop_loss = candidate.get("stop_loss", 0)
    close = candidate.get("close", 0)
    ma20 = candidate.get("ma20", 0)
    ma50 = candidate.get("ma50", 0)

    # 距離 52 週新高顯示
    if distance_to_52w >= 0:
        distance_text = f"距離 52 週新高：已創新高 (+{distance_to_52w}%)"
    else:
        distance_text = f"距離 52 週新高：{distance_to_52w}%"

    description = (
        f"**級別：{tier}**\n"
        f"**RS Rating: {rs_rating}**\n\n"
        f"**方向 / 訊號**\n"
        f"分層：{tier}級\n"
        f"訊號：{signal_display}\n"
        f"優先級：{priority}\n\n"
        f"**🎯 RS + MACD 動能**\n"
        f"• RS Rating：{rs_rating} (vs QQQ)\n"
        f"• MACD 狀態：{macd_display}\n"
        f"• RSI：{rsi}\n\n"
        f"**📊 技術面摘要**\n"
        f"• 趨勢：{trend}\n"
        f"• MA20：${ma20:.2f}\n"
        f"• MA50：${ma50:.2f}\n"
        f"• {distance_text}\n"
        f"• 突破狀態：{breakout_status}\n\n"
        f"**⚠️ 風險控制**\n"
        f"• 現價：${close:.2f}\n"
        f"• 入場：${entry:.2f}\n"
        f"• 止損：${stop_loss:.2f}\n"
        f"• 止盈 Level 1：${tp1:.2f}（先出 30%）\n"
        f"• 止盈 Level 2：${tp2:.2f}（再出 40%）\n"
        f"• 止盈 Level 3：${tp3:.2f}（剩餘倉位）"
    )

    embed = {
        "title": f"📊 {ticker}",
        "description": description,
        "color": color,
        "footer": {
            "text": "QuantFlow Auto Scan"
        }
    }

    return embed


def send_discord_embed(candidate: dict) -> bool:
    webhook = os.getenv("DISCORD_WEBHOOK", "")
    
    if not webhook:
        print("未設定 DISCORD_WEBHOOK，跳過發送")
        return False

    embed = build_embed(candidate)
    payload = {"embeds": [embed]}

    try:
        response = requests.post(webhook, json=payload, timeout=10)
        
        if response.status_code in (200, 204):
            print(f"✅ 成功發送 {candidate.get('ticker')} 通知")
            return True
        else:
            print(f"❌ 發送失敗: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 發送時發生錯誤: {e}")
        return False


def send_multiple_embeds(candidates: List[dict], batch_size: int = 10) -> None:
    webhook = os.getenv("DISCORD_WEBHOOK", "")
    
    if not webhook:
        print("未設定 DISCORD_WEBHOOK，跳過發送")
        return

    if not candidates:
        return

    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        embeds = [build_embed(c) for c in batch]

        payload = {"embeds": embeds}

        try:
            response = requests.post(webhook, json=payload, timeout=10)

            if response.status_code in (200, 204):
                print(f"✅ 成功發送批次 {i//batch_size + 1}（{len(batch)} 隻股票）")
            elif response.status_code == 429:
                try:
                    retry_after = response.json().get("retry_after", 2)
                except Exception:
                    retry_after = 2
                print(f"⚠️ 觸發速率限制，等待 {retry_after} 秒後重試...")
                time.sleep(retry_after + 0.5)
                response = requests.post(webhook, json=payload, timeout=10)
                if response.status_code in (200, 204):
                    print("✅ 重試成功")
                else:
                    print(f"❌ 重試仍然失敗: {response.status_code}")
            else:
                print(f"❌ 發送失敗: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"❌ 發送時發生錯誤: {e}")

        if i + batch_size < len(candidates):
            time.sleep(1.0)


def send_discord_message(message: str) -> bool:
    webhook = os.getenv("DISCORD_WEBHOOK", "")
    
    if not webhook:
        print("未設定 DISCORD_WEBHOOK，跳過發送")
        return False

    try:
        payload = {"content": message}
        response = requests.post(webhook, json=payload, timeout=10)
        
        if response.status_code in (200, 204):
            print("✅ 文字訊息發送成功")
            return True
        else:
            print(f"❌ 文字訊息發送失敗: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 發送文字訊息時發生錯誤: {e}")
        return False