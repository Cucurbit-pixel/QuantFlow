from fastapi import FastAPI, Form, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
import json
from pathlib import Path
import yfinance as yf
import asyncio
from typing import List

app = FastAPI(title="QuantFlow Dashboard")

active_connections: List[WebSocket] = []


async def broadcast(message: dict):
    for connection in active_connections[:]:
        try:
            await connection.send_json(message)
        except Exception:
            if connection in active_connections:
                active_connections.remove(connection)


def load_config():
    path = Path("data/config.json")
    if not path.exists():
        return {
            "min_rs_rating": 80,
            "require_trend_ok": True,
            "require_macd_bullish": True,
            "tickers": []
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict):
    Path("data").mkdir(exist_ok=True)
    with open("data/config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_latest_scan():
    path = Path("data/latest_scan.json")
    if not path.exists():
        return {"scan_time": "尚未有掃描記錄", "count": 0, "stocks": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sort_stocks(stocks: list) -> list:
    tier_order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
    return sorted(
        stocks,
        key=lambda x: (tier_order.get(x.get("tier", "D"), 99), x.get("ticker", ""))
    )


def get_index_data():
    symbols = {
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "Dow Jones": "^DJI",
        "恆生指數": "^HSI"
    }
    results = []
    for name, symbol in symbols.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="5d")
            if len(hist) >= 2:
                current = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                change_pt = current - prev
                change_pct = (change_pt / prev) * 100
                results.append({
                    "name": name,
                    "price": f"{current:,.2f}",
                    "change_pt": change_pt,
                    "change_pt_str": f"{change_pt:+,.2f}",
                    "change_pct": change_pct,
                    "change_pct_str": f"{change_pct:+.2f}%"
                })
            else:
                results.append({
                    "name": name, "price": "--", "change_pt": 0,
                    "change_pt_str": "--", "change_pct": 0, "change_pct_str": "--"
                })
        except Exception:
            results.append({
                "name": name, "price": "--", "change_pt": 0,
                "change_pt_str": "--", "change_pct": 0, "change_pct_str": "--"
            })
    return results


def get_fear_greed():
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if not hist.empty:
            vix_value = float(hist["Close"].iloc[-1])
            if vix_value < 15:
                score = 78
            elif vix_value < 18:
                score = 68
            elif vix_value < 22:
                score = 55
            elif vix_value < 26:
                score = 42
            elif vix_value < 32:
                score = 28
            else:
                score = 15

            if score >= 76:
                level = "極度貪婪"
            elif score >= 56:
                level = "貪婪"
            elif score >= 45:
                level = "中性"
            elif score >= 25:
                level = "恐懼"
            else:
                level = "極度恐懼"

            return score, level
    except Exception:
        pass
    return None, None


def get_options_alerts():
    """
    期權異動數據（暫時用模擬，之後改成真實掃描）
    level: high / medium / low
    """
    # TODO: 之後改為真實 yfinance Vol/OI 掃描結果
    return [
        {
            "level": "high",
            "ticker": "TSLA",
            "option_type": "PUT",
            "strike": 250.0,
            "expiry": "08-15",
            "vol_oi": 4.2,
            "moneyness": "價外"
        },
        {
            "level": "high",
            "ticker": "SPY",
            "option_type": "PUT",
            "strike": 580.0,
            "expiry": "08-01",
            "vol_oi": 3.1,
            "moneyness": "價內"
        },
        {
            "level": "medium",
            "ticker": "NVDA",
            "option_type": "CALL",
            "strike": 140.0,
            "expiry": "08-15",
            "vol_oi": 2.5,
            "moneyness": "價內"
        },
        {
            "level": "medium",
            "ticker": "AAPL",
            "option_type": "CALL",
            "strike": 230.0,
            "expiry": "08-08",
            "vol_oi": 2.1,
            "moneyness": "價外"
        },
        {
            "level": "low",
            "ticker": "AMD",
            "option_type": "CALL",
            "strike": 160.0,
            "expiry": "08-15",
            "vol_oi": 1.8,
            "moneyness": "價內"
        },
    ]


def run_scan_background():
    try:
        from screener.merge import run_full_scan
        run_full_scan()
        print("✅ 背景掃描完成")
        asyncio.run(broadcast({"type": "scan_complete"}))
    except Exception as e:
        print(f"❌ 背景掃描錯誤: {e}")
        asyncio.run(broadcast({"type": "scan_error", "message": str(e)}))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    config = load_config()
    data = load_latest_scan()
    stocks = sort_stocks(data.get("stocks", []))
    scan_time = data.get("scan_time", "未知")
    count = data.get("count", 0)

    indices = get_index_data()
    us_indices = indices[:3]
    hsi = indices[3] if len(indices) > 3 else None
    fg_score, fg_level = get_fear_greed()
    options_alerts = get_options_alerts()

    def render_index_item(idx):
        color = "#22C55E" if idx["change_pct"] > 0 else "#EF4444" if idx["change_pct"] < 0 else "#A78BFA"
        return f"""
        <div class="index-item">
            <div class="index-name">{idx['name']}</div>
            <div class="index-price">{idx['price']}</div>
            <div class="index-pt" style="color:{color}">{idx['change_pt_str']}</div>
            <div class="index-pct" style="color:{color}">{idx['change_pct_str']}</div>
        </div>
        """

    us_html = "".join([render_index_item(i) for i in us_indices])
    hsi_html = render_index_item(hsi) if hsi else ""

    if fg_score is not None:
        fg_html = f"""
        <div class="index-item">
            <div class="index-name">Fear & Greed</div>
            <div class="index-price" style="color:#EF4444; font-size:1.3rem;">{fg_score}</div>
            <div class="index-pt" style="color:#F87171;">({fg_level})</div>
            <div class="index-pct">&nbsp;</div>
        </div>
        """
    else:
        fg_html = """
        <div class="index-item">
            <div class="index-name">Fear & Greed</div>
            <div class="index-price" style="color:#A78BFA;">--</div>
            <div class="index-pt">&nbsp;</div>
            <div class="index-pct">&nbsp;</div>
        </div>
        """

    # 期權異動區塊（有數據先顯示）
    options_html = ""
    if options_alerts:
        high = [a for a in options_alerts if a["level"] == "high"]
        medium = [a for a in options_alerts if a["level"] == "medium"]
        low = [a for a in options_alerts if a["level"] == "low"]

        def render_alert_line(a):
            return f"• {a['ticker']} {a['option_type']} {a['strike']} | 到期 {a['expiry']} | 爆發 {a['vol_oi']}x | {a['moneyness']}"

        high_html = "".join([f"<div class='opt-line'>{render_alert_line(a)}</div>" for a in high])
        medium_html = "".join([f"<div class='opt-line'>{render_alert_line(a)}</div>" for a in medium])
        low_html = "".join([f"<div class='opt-line'>{render_alert_line(a)}</div>" for a in low])

        options_html = f"""
        <div class="options-box">
            <div class="options-title">🚀 期權異動監測</div>
            {f'<div class="opt-level high">🔴 高關注</div>{high_html}' if high else ''}
            {f'<div class="opt-level medium">🟡 中等關注</div>{medium_html}' if medium else ''}
            {f'<div class="opt-level low">🟢 一般觀察</div>{low_html}' if low else ''}
        </div>
        """

    cards_html = ""
    if not stocks:
        cards_html = "<p style='color:#A78BFA;'>目前冇符合條件嘅股票</p>"
    else:
        for s in stocks:
            tier = s.get("tier", "-")
            signal = s.get("signal_type", "watch")
            signal_map = {
                "strong_buy": "🚀🚀🚀 強烈買入",
                "buy": "🚀 買入",
                "watch": "👀 觀察"
            }
            signal_text = signal_map.get(signal, signal)
            company_name = s.get("company_name", "")
            ticker = s.get("ticker", "")
            distance = s.get("distance_to_52w_high", 0)
            distance_text = f"已創新高 (+{distance}%)" if distance >= 0 else f"{distance}%"

            cards_html += f"""
            <div class="card">
                <div class="tier-badge tier-{tier}">Tier {tier}</div>
                <div class="ticker-line">📊 {ticker}</div>
                <div class="company-name">({company_name})</div>
                <div class="signal">{signal_text}</div>
                <div class="info">
                    <div>RS Rating：<b>{s.get('rs_rating')}</b></div>
                    <div>RSI：{s.get('rsi')}</div>
                    <div>MACD：{s.get('macd_status')}</div>
                    <div>趨勢：{s.get('trend')}</div>
                    <div>距離52週新高：{distance_text}</div>
                    <div>突破：{s.get('breakout_status')}</div>
                </div>
                <div class="price">
                    現價：${s.get('close')} | 入場：${s.get('entry')} | 止損：${s.get('stop_loss')}
                </div>
                <div class="tp">
                    止盈1：${s.get('tp1')} | 止盈2：${s.get('tp2')} | 止盈3：${s.get('tp3')}
                </div>
            </div>
            """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>QuantFlow Dashboard</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #0F0A1A;
                color: #F5F3FF;
                margin: 0;
                padding: 16px;
                min-height: 100vh;
            }}
            h1 {{ font-size: 1.5rem; margin: 0 0 6px 0; font-weight: 700; }}
            h2 {{ font-size: 1.05rem; margin: 24px 0 12px 0; color: #C4B5FD; }}
            .meta {{ color: #A78BFA; font-size: 0.9rem; margin-bottom: 16px; }}
            
            .index-row {{
                display: flex;
                background: #1A1229;
                border-radius: 16px;
                padding: 14px 6px;
                margin-bottom: 10px;
                border: 1px solid #2E1F47;
            }}
            .index-item {{ flex: 1; text-align: center; min-width: 0; }}
            .index-name {{ font-size: 0.72rem; color: #A78BFA; margin-bottom: 4px; }}
            .index-price {{ font-size: 0.95rem; font-weight: 700; color: #F5F3FF; }}
            .index-pt {{ font-size: 0.8rem; font-weight: 600; margin-top: 3px; }}
            .index-pct {{ font-size: 0.8rem; font-weight: 600; margin-top: 1px; }}
            
            .options-box {{
                background: #1A1229;
                border-radius: 16px;
                padding: 16px;
                margin-bottom: 16px;
                border: 1px solid #2E1F47;
            }}
            .options-title {{
                font-size: 1.05rem;
                font-weight: 700;
                margin-bottom: 12px;
                color: #F5F3FF;
            }}
            .opt-level {{
                font-size: 0.9rem;
                font-weight: 600;
                margin: 12px 0 6px 0;
            }}
            .opt-level.high {{ color: #F87171; }}
            .opt-level.medium {{ color: #FBBF24; }}
            .opt-level.low {{ color: #4ADE80; }}
            .opt-line {{
                font-size: 0.85rem;
                color: #C4B5FD;
                line-height: 1.7;
                padding-left: 4px