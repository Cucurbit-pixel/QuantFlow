import requests
import os
import time
from typing import List


def get_priority(signal_type: str) -> str:
    """根據訊號類型返回優先級"""
    high_priority = ["sell_call", "sell_put"]
    medium_priority = ["long_call", "long_put"]
    
    if signal_type in high_priority:
        return "🔴 高"
    elif signal_type in medium_priority:
        return "🟡 中"
    elif signal_type in ["strong_buy", "buy"]:
        return "🟢 普通"
    else:
        return "⚪ 低"


def build_embed(candidate: dict) -> dict:
    """
    建立 Discord Embed 通知
    支援四種 Options 訊號 + 優先級 + 三級止盈
    """
    ticker = candidate.get("ticker", "UNKNOWN")
    tier = candidate.get("tier", "C")
    rs_rating = candidate.get("rs_rating", 0)
    rsi = candidate.get("rsi", 0)
    macd_status = candidate.get("macd_status", "neutral")
    trend = candidate.get("trend", "多頭排列")
    signal_type = candidate.get("signal_type", "watch")

    # Tier 顏色
    tier_colors = {
        "S": 0xE63946,
        "A": 0xF4A261,
        "B": 0x2A9D8F,
        "C": 0xE9C46A,
        "D": 0x457B9D,
    }
    color = tier_colors.get(tier, 0x6C757D)

    # MACD 顯示
    macd_map = {
        "golden_cross": "🟢 金叉",
        "bullish_momentum": "🟢 多頭動能",
        "death_cross": "🔴 死叉",
        "bearish_momentum": "🔴 空頭動能",
        "neutral": "⚪ 中性",
    }
    macd_display = macd_map.get(macd_status, "⚪ 中性")

    # 訊號顯示
    signal_map = {
        "sell_call": "📉 Sell Call（見頂）",
        "sell_put": "📈 Sell Put（見底）",
        "long_call": "🚀 Long Call（看漲）",
        "long_put": "🔻 Long Put（看跌）",
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
    suggested_strike = candidate.get("suggested_strike")
    near_term_exp = candidate.get("near_term_exp", "")
    monthly_exp = candidate.get("monthly_exp", "")

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
        f"• MA50：${ma50:.2f}\n\n"
        f"**⚠️ 風險控制**\n"
        f"• 現價：${close:.2f}\n"
        f"• 入場：${entry:.2f}\n"
        f"• 止損：${stop_loss:.2f}\n"
        f"• 止盈 Level 1：${tp1:.2f}（先出 30%）\n"
        f"• 止盈 Level 2：${tp2:.2f}（再出 40%）\n"
        f"• 止盈 Level 3：${tp3:.2f}（剩餘倉位）"
    )

    # Options 建議
    if signal_type in ["sell_call", "sell_put", "long_call", "long_put"] and suggested_strike:
        options_title = {
            "sell_call": "📉 Options 建議（Sell Call）",
            "sell_put": "📈 Options 建議（Sell Put）",
            "long_call": "🚀 Options 建議（Long Call）",
            "long_put": "🔻 Options 建議（Long Put）",
        }.get(signal_type, "Options 建議")

        description += (
            f"\n\n**{options_title}**\n"
            f"• 建議行權價：${suggested_strike:.2f}\n"
            f"• 近月到期：{near_term_exp}\n"
            f"• 月期權到期：{monthly_exp}"
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