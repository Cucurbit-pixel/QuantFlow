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
        return {
            "scan_time": "尚未有掃描記錄",
            "data_date_display": "",
            "count": 0,
            "stocks": []
        }
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
    """只讀快取，唔喺頁面載入時掃描"""
    try:
        from screener.options_scanner import load_options_cache
        return load_options_cache()
    except Exception as e:
        print(f"讀取期權快取錯誤: {e}")
        return []


def run_scan_background():
    """背景執行：股票掃描 + 期權掃描"""
    try:
        from screener.merge import run_full_scan
        from screener.options_scanner import get_or_scan_options

        run_full_scan()
        print("✅ 股票掃描完成")

        get_or_scan_options(force=True)
        print("✅ 期權掃描完成")

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
    data_date_display = data.get("data_date_display") or data.get("data_date") or "—"
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
                padding-left: 4px;
            }}
            
            .card {{
                background: #1A1229;
                border-radius: 16px;
                padding: 16px;
                margin-bottom: 14px;
                border: 1px solid #2E1F47;
            }}
            .tier-badge {{
                display: inline-block;
                font-size: 0.85rem;
                padding: 4px 14px;
                border-radius: 999px;
                font-weight: 700;
                margin-bottom: 10px;
            }}
            .tier-S {{ background: #E63946; color: #FFFFFF; font-weight: 800; }}
            .tier-A {{ background: #F4A261; color: #1A1229; }}
            .tier-B {{ background: #2A9D8F; color: white; }}
            .tier-C {{ background: #E9C46A; color: #1A1229; }}
            .tier-D {{ background: #457B9D; color: white; }}
            .ticker-line {{ font-size: 1.25rem; font-weight: 700; color: #F5F3FF; }}
            .company-name {{ font-size: 0.9rem; color: #A78BFA; margin: 2px 0 10px 0; }}
            .signal {{ font-size: 1.05rem; margin-bottom: 12px; color: #DDD6FE; }}
            .info {{ font-size: 0.9rem; color: #C4B5FD; line-height: 1.7; }}
            .info b {{ color: #F5F3FF; }}
            .price {{ margin-top: 12px; font-size: 0.85rem; color: #A78BFA; }}
            .tp {{ margin-top: 6px; font-size: 0.85rem; color: #A78BFA; }}
            
            .settings {{
                background: #1A1229;
                border-radius: 16px;
                padding: 18px;
                margin-bottom: 20px;
                border: 1px solid #2E1F47;
            }}
            label {{ display: block; margin: 12px 0 6px; color: #A78BFA; font-size: 0.9rem; }}
            input[type=number] {{
                width: 100%;
                padding: 12px 14px;
                border-radius: 12px;
                border: 1px solid #2E1F47;
                background: #120C1F;
                color: #F5F3FF;
                font-size: 1rem;
            }}
            .checkbox-row {{
                display: flex;
                align-items: center;
                gap: 10px;
                margin: 14px 0;
            }}
            .checkbox-row label {{ margin: 0; color: #DDD6FE; }}
            button {{
                width: 100%;
                padding: 14px;
                border: none;
                border-radius: 12px;
                font-size: 1rem;
                font-weight: 600;
                margin-top: 12px;
                cursor: pointer;
            }}
            .btn-primary {{ background: #8B5CF6; color: white; }}
            .btn-scan {{ background: #7C3AED; color: white; }}
            .scan-tip {{
                text-align: center;
                color: #A78BFA;
                font-size: 0.85rem;
                margin-top: 8px;
            }}
            #status {{
                text-align: center;
                padding: 8px;
                border-radius: 8px;
                margin-bottom: 12px;
                font-size: 0.9rem;
                display: none;
            }}
            #status.scanning {{
                display: block;
                background: #2E1F47;
                color: #C4B5FD;
            }}
            #status.done {{
                display: block;
                background: #14532D;
                color: #86EFAC;
            }}
        </style>
    </head>
    <body>
        <h1>QuantFlow 掃描結果</h1>
        <div class="meta">
            最新掃描時間：{scan_time}<br>
            數據日期：{data_date_display}<br>
            符合條件：{count} 隻股票
        </div>

        <div id="status"></div>

        <div class="index-row">
            {us_html}
        </div>
        <div class="index-row">
            {hsi_html}
            {fg_html}
        </div>

        {options_html}

        <div class="settings">
            <h2>搜尋條件設定</h2>
            <form method="post" action="/update-config">
                <label>最低 RS Rating</label>
                <input type="number" name="min_rs_rating" value="{config.get('min_rs_rating', 80)}" min="0" max="99">

                <div class="checkbox-row">
                    <input type="checkbox" name="require_trend_ok" value="true" {"checked" if config.get("require_trend_ok") else ""}>
                    <label>必須多頭排列</label>
                </div>

                <div class="checkbox-row">
                    <input type="checkbox" name="require_macd_bullish" value="true" {"checked" if config.get("require_macd_bullish") else ""}>
                    <label>必須 MACD 偏多</label>
                </div>

                <button type="submit" class="btn-primary">儲存設定</button>
            </form>

            <form method="post" action="/run-scan" style="margin-top:8px;" id="scan-form">
                <button type="submit" class="btn-scan" id="scan-btn">立即執行掃描</button>
            </form>
            <div class="scan-tip">掃描會在背景執行（股票 + 期權），完成後自動刷新</div>
        </div>

        <h2>掃描結果</h2>
        {cards_html}

        <script>
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const ws = new WebSocket(`${{protocol}}//${{window.location.host}}/ws`);
            const statusEl = document.getElementById('status');
            const scanBtn = document.getElementById('scan-btn');

            ws.onmessage = function(event) {{
                const data = JSON.parse(event.data);
                if (data.type === 'scan_complete') {{
                    statusEl.className = 'done';
                    statusEl.textContent = '✅ 掃描完成，正在刷新...';
                    setTimeout(() => location.reload(), 800);
                }} else if (data.type === 'scan_error') {{
                    statusEl.className = 'done';
                    statusEl.textContent = '❌ 掃描出錯：' + (data.message || '');
                }}
            }};

            document.getElementById('scan-form').addEventListener('submit', function() {{
                statusEl.className = 'scanning';
                statusEl.textContent = '⏳ 掃描進行中（股票 + 期權），請稍候...';
                scanBtn.disabled = true;
                scanBtn.textContent = '掃描中...';
            }});
        </script>
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
async def run_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scan_background)
    return RedirectResponse(url="/", status_code=303)


@app.get("/api/latest")
def api_latest():
    return load_latest_scan()