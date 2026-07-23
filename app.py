from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import json
from pathlib import Path
import yfinance as yf

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


@app.get("/", response_class=HTMLResponse)
def dashboard():
    config = load_config()
    data = load_latest_scan()
    stocks = sort_stocks(data.get("stocks", []))
    scan_time = data.get("scan_time", "未知")
    count = data.get("count", 0)

    indices = get_index_data()
    us_indices = indices[:3]   # S&P, Nasdaq, Dow
    hsi = indices[3] if len(indices) > 3 else None
    fg_score, fg_level = get_fear_greed()

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

    hsi_html = ""
    if hsi:
        hsi_html = render_index_item(hsi)

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
            .index-item {{
                flex: 1;
                text-align: center;
                min-width: 0;
            }}
            .index-name {{ font-size: 0.72rem; color: #A78BFA; margin-bottom: 4px; }}
            .index-price {{ font-size: 0.95rem; font-weight: 700; color: #F5F3FF; }}
            .index-pt {{ font-size: 0.8rem; font-weight: 600; margin-top: 3px; }}
            .index-pct {{ font-size: 0.8rem; font-weight: 600; margin-top: 1px; }}
            
            .card {{
                background: #1A1229;
                border-radius: 16px;
                padding: 16px;
                margin-bottom: 14px;
                border: 1px solid #2E1F47;
            }}
            .card-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
                gap: 8px;
            }}
            .ticker {{ font-size: 1.1rem; font-weight: 700; }}
            .tier {{
                font-size: 0.8rem;
                padding: 3px 10px;
                border-radius: 999px;
                font-weight: 600;
            }}
            .tier-S {{ background: #E63946; color: white; }}
            .tier-A {{ background: #F4A261; color: #1A1229; }}
            .tier-B {{ background: #2A9D8F; color: white; }}
            .tier-C {{ background: #E9C46A; color: #1A1229; }}
            .tier-D {{ background: #457B9D; color: white; }}
            .signal {{ font-size: 1.05rem; margin-bottom: 12px; color: #DDD6FE; }}
            .info {{ font-size: 0.9rem; color: #C4B5FD; line-height: 1.7; }}
            .info b {{ color: #F5F3FF; }}
            .price {{ margin-top: 12px; font-size: 0.85rem; color: #A78BFA; }}
            
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
        </style>
    </head>
    <body>
        <h1>QuantFlow 掃描結果</h1>
        <div class="meta">
            最新掃描時間：{scan_time}<br>
            符合條件：{count} 隻股票
        </div>

        <div class="index-row">
            {us_html}
        </div>
        <div class="index-row">
            {hsi_html}
            {fg_html}
        </div>

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

            <form method="post" action="/run-scan" style="margin-top:8px;">
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