from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import json
from pathlib import Path

app = FastAPI(title="QuantFlow Dashboard")


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
    """按 Tier (S→A→B→C→D) 排序，同一 Tier 再按 ticker A-Z"""
    tier_order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
    return sorted(
        stocks,
        key=lambda x: (tier_order.get(x.get("tier", "D"), 99), x.get("ticker", ""))
    )


@app.get("/", response_class=HTMLResponse)
def dashboard():
    config = load_config()
    data = load_latest_scan()
    stocks = sort_stocks(data.get("stocks", []))
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

            company_name = s.get("company_name", "")
            display_name = f"{s.get('ticker')} ({company_name})" if company_name and company_name != s.get("ticker") else s.get("ticker")

            distance = s.get("distance_to_52w_high", 0)
            distance_text = f"已創新高 (+{distance}%)" if distance >= 0 else f"{distance}%"

            cards_html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="ticker">{display_name}</span>
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
            h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
            h2 {{ font-size: 1.1rem; margin-top: 24px; color: #ccc; }}
            .meta {{ color: #888; font-size: 0.9rem; margin-bottom: 16px; }}
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
            .ticker {{ font-size: 1.15rem; font-weight: 700; }}
            .tier {{
                font-size: 0.85rem;
                padding: 2px 8px;
                border-radius: 6px;
                background: #333;
            }}
            .tier-S {{ background: #e63946; }}
            .tier-A {{ background: #f4a261; color: #000; }}
            .tier-B {{ background: #2a9d8f; }}
            .tier-C {{ background: #e9c46a; color: #000; }}
            .signal {{ font-size: 1.1rem; margin-bottom: 10px; }}
            .info {{ font-size: 0.9rem; color: #ccc; line-height: 1.6; }}
            .price {{ margin-top: 10px; font-size: 0.85rem; color: #aaa; }}
            .settings {{
                background: #1c1c1e;
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 20px;
            }}
            label {{ display: block; margin: 10px 0 4px; color: #aaa; font-size: 0.9rem; }}
            input[type=number] {{
                width: 100%;
                padding: 10px;
                border-radius: 8px;
                border: 1px solid #333;
                background: #111;
                color: #eee;
                font-size: 1rem;
                box-sizing: border-box;
            }}
            .checkbox-row {{
                display: flex;
                align-items: center;
                gap: 8px;
                margin: 12px 0;
            }}
            button {{
                width: 100%;
                padding: 14px;
                border: none;
                border-radius: 10px;
                font-size: 1rem;
                font-weight: 600;
                margin-top: 12px;
                cursor: pointer;
            }}
            .btn-primary {{ background: #3b82f6; color: white; }}
            .btn-scan {{ background: #10b981; color: white; }}
        </style>
    </head>
    <body>
        <h1>QuantFlow 掃描結果</h1>
        <div class="meta">
            最新掃描時間：{scan_time}<br>
            符合條件：{count} 隻股票
        </div>

        <div class="settings">
            <h2>搜尋條件設定</h2>
            <form method="post" action="/update-config">
                <label>最低 RS Rating</label>
                <input type="number" name="min_rs_rating" value="{config.get('min_rs_rating', 80)}" min="0" max="99">

                <div class="checkbox-row">
                    <input type="checkbox" name="require_trend_ok" value="true" {"checked" if config.get("require_trend_ok") else ""}>
                    <label style="margin:0">必須多頭排列</label>
                </div>

                <div class="checkbox-row">
                    <input type="checkbox" name="require_macd_bullish" value="true" {"checked" if config.get("require_macd_bullish") else ""}>
                    <label style="margin:0">必須 MACD 偏多</label>
                </div>

                <button type="submit" class="btn-primary">儲存設定</button>
            </form>

            <form method="post" action="/run-scan" style="margin-top:12px;">
                <button type="submit" class="btn-scan">立即執行掃描</button>
            </form>
        </div>

        <h2>掃描結果</h2>
        {cards_html}
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post("/update-config")
async def update_config(
    min_rs_rating: int = Form(...),
    require_trend_ok: str = Form(None),
    require_macd_bullish: str = Form(None)
):
    config = load_config()
    config["min_rs_rating"] = min_rs_rating
    config["require_trend_ok"] = require_trend_ok == "true"
    config["require_macd_bullish"] = require_macd_bullish == "true"
    save_config(config)
    return RedirectResponse(url="/", status_code=303)


@app.post("/run-scan")
async def run_scan():
    try:
        from screener.merge import run_full_scan
        run_full_scan()
    except Exception as e:
        print(f"掃描錯誤: {e}")
    return RedirectResponse(url="/", status_code=303)


@app.get("/api/latest")
def api_latest():
    return load_latest_scan()