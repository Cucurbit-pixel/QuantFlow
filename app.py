from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json
from pathlib import Path
from datetime import datetime

app = FastAPI(title="QuantFlow Dashboard")

# 如果之後有 templates 資料夾可以用，而家先用純 HTML
def load_latest_scan():
    file_path = Path("data/latest_scan.json")
    if not file_path.exists():
        return {
            "scan_time": "尚未有掃描記錄",
            "count": 0,
            "stocks": []
        }
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import json
from pathlib import Path

app = FastAPI(title="QuantFlow Dashboard")


def load_latest_scan():
    file_path = Path("data/latest_scan.json")
    if not file_path.exists():
        return {
            "scan_time": "尚未有掃描記錄",
            "count": 0,
            "stocks": []
        }
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    data = load_latest_scan()
    stocks = data.get("stocks", [])
    scan_time = data.get("scan_time", "未知")
    count = data.get("count", 0)

    cards_html = ""
    if not stocks:
        cards_html = "<p style='color:#aaa;'>目前冇符合條件嘅股票</p>"
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
            
            distance = s.get("distance_to_52w_high", 0)
            if distance >= 0:
                distance_text = f"已創新高 (+{distance}%)"
            else:
                distance_text = f"{distance}%"

            cards_html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="ticker">{s.get('ticker')}</span>
                    <span class="tier tier-{tier}">Tier {tier}</span>
                </div>
                <div class="signal">{signal_text}</div>
                <div class="info">
                    <div>RS Rating：<b>{s.get('rs_rating')}</b></div>
                    <div>RSI：{s.get('rsi')}</div>
                    <div>MACD：{s.get('macd_status')}</div>
                    <div>趨勢：{s.get('trend')}</div>
                    <div>距離 52 週新高：{distance_text}</div>
                    <div>突破：{s.get('breakout_status')}</div>
                </div>
                <div class="price">
                    現價：${s.get('close')} | 入場：${s.get('entry')} | 止損：${s.get('stop_loss')}
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
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #0f0f0f;
                color: #eee;
                margin: 0;
                padding: 16px;
            }}
            h1 {{
                font-size: 1.5rem;
                margin-bottom: 4px;
            }}
            .meta {{
                color: #888;
                font-size: 0.9rem;
                margin-bottom: 20px;
            }}
            .card {{
                background: #1c1c1e;
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 14px;
                border-left: 4px solid #333;
            }}
            .card-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }}
            .ticker {{
                font-size: 1.3rem;
                font-weight: 700;
            }}
            .tier {{
                font-size: 0.85rem;
                padding: 2px 8px;
                border-radius: 6px;
                background: #333;
            }}
            .tier-S {{ background: #e63946; }}
            .tier-A {{ background: #f4a261; color: #000; }}
            .tier-B {{ background: #2a9d8f; }}
            .signal {{
                font-size: 1.1rem;
                margin-bottom: 10px;
            }}
            .info {{
                font-size: 0.9rem;
                color: #ccc;
                line-height: 1.6;
            }}
            .price {{
                margin-top: 10px;
                font-size: 0.85rem;
                color: #aaa;
            }}
        </style>
    </head>
    <body>
        <h1>QuantFlow 掃描結果</h1>
        <div class="meta">
            最新掃描時間：{scan_time}<br>
            符合條件：{count} 隻股票
        </div>
        {cards_html}
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/api/latest")
def api_latest():
    return load_latest_scan()


@app.get("/", response_class=HTMLResponse)
def dashboard():
    data = load_latest_scan()
    stocks = data.get("stocks", [])
    scan_time = data.get("scan_time", "未知")
    count = data.get("count", 0)

    # 產生股票卡片 HTML
    cards_html = ""
    if not stocks:
        cards_html = "<p style='color:#aaa;'>目前冇符合條件嘅股票</p>"
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
            
            distance = s.get("distance_to_52w_high", 0)
            if distance >= 0:
                distance_text = f"已創新高 (+{distance}%)"
            else:
                distance_text = f"{distance}%"

            cards_html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="ticker">{s.get('ticker')}</span>
                    <span class="tier tier-{tier}">Tier {tier}</span>
                </div>
                <div class="signal">{signal_text}</div>
                <div class="info">
                    <div>RS Rating：<b>{s.get('rs_rating')}</b></div>
                    <div>RSI：{s.get('rsi')}</div>
                    <div>MACD：{s.get('macd_status')}</div>
                    <div>趨勢：{s.get('trend')}</div>
                    <div>距離 52 週新高：{distance_text}</div>
                    <div>突破：{s.get('breakout_status')}</div>
                </div>
                <div class="price">
                    現價：${s.get('close')} | 入場：${s.get('entry')} | 止損：${s.get('stop_loss')}
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
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #0f0f0f;
                color: #eee;
                margin: 0;
                padding: 16px;
            }}
            h1 {{
                font-size: 1.5rem;
                margin-bottom: 4px;
            }}
            .meta {{
                color: #888;
                font-size: 0.9rem;
                margin-bottom: 20px;
            }}
            .card {{
                background: #1c1c1e;
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 14px;
                border-left: 4px solid #333;
            }}
            .card-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }}
            .ticker {{
                font-size: 1.3rem;
                font-weight: 700;
            }}
            .tier {{
                font-size: 0.85rem;
                padding: 2px 8px;
                border-radius: 6px;
                background: #333;
            }}
            .tier-S {{ background: #e63946; }}
            .tier-A {{ background: #f4a261; color: #000; }}
            .tier-B {{ background: #2a9d8f; }}
            .signal {{
                font-size: 1.1rem;
                margin-bottom: 10px;
            }}
            .info {{
                font-size: 0.9rem;
                color: #ccc;
                line-height: 1.6;
            }}
            .price {{
                margin-top: 10px;
                font-size: 0.85rem;
                color: #aaa;
            }}
        </style>
    </head>
    <body>
        <h1>QuantFlow 掃描結果</h1>
        <div class="meta">
            最新掃描時間：{scan_time}<br>
            符合條件：{count} 隻股票
        </div>
        {cards_html}
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/api/latest")
def api_latest():
    """提供 JSON API，之後其他地方都可以用"""
    return load_latest_scan()