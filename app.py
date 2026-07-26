from fastapi import FastAPI, Form, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
import json
from pathlib import Path
import math
import yfinance as yf
import asyncio
from typing import List

app = FastAPI(title="QuantFlow Dashboard")
active_connections: List[WebSocket] = []


async def broadcast(message: dict):
    for c in active_connections[:]:
        try:
            await c.send_json(message)
        except Exception:
            if c in active_connections:
                active_connections.remove(c)


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
    order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
    return sorted(
        stocks,
        key=lambda x: (order.get(x.get("tier", "D"), 99), x.get("ticker", ""))
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
            hist = yf.Ticker(symbol).history(period="10d")
            if hist is None or hist.empty or len(hist) < 2:
                results.append({
                    "name": name, "price": "--", "change_pt": 0,
                    "change_pt_str": "--", "change_pct": 0, "change_pct_str": "--"
                })
                continue
            cur = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            if math.isnan(cur) or math.isnan(prev) or prev == 0:
                results.append({
                    "name": name, "price": "--", "change_pt": 0,
                    "change_pt_str": "--", "change_pct": 0, "change_pct_str": "--"
                })
                continue
            pt = cur - prev
            pct = pt / prev * 100
            results.append({
                "name": name,
                "price": f"{cur:,.2f}",
                "change_pt": pt,
                "change_pt_str": f"{pt:+,.2f}",
                "change_pct": pct,
                "change_pct_str": f"{pct:+.2f}%"
            })
        except Exception:
            results.append({
                "name": name, "price": "--", "change_pt": 0,
                "change_pt_str": "--", "change_pct": 0, "change_pct_str": "--"
            })
    return results


def get_fear_greed():
    try:
        hist = yf.Ticker("^VIX").history(period="5d")
        if hist.empty:
            return None, None
        v = float(hist["Close"].iloc[-1])
        if math.isnan(v):
            return None, None
        score = (
            78 if v < 15 else 68 if v < 18 else 55 if v < 22
            else 42 if v < 26 else 28 if v < 32 else 15
        )
        level = (
            "極度貪婪" if score >= 76 else "貪婪" if score >= 56
            else "中性" if score >= 45 else "恐懼" if score >= 25
            else "極度恐懼"
        )
        return score, level
    except Exception:
        return None, None


def get_options_alerts():
    try:
        from screener.options_scanner import load_options_cache
        return load_options_cache()
    except Exception as e:
        print(f"期權快取: {e}")
        return []


def get_oi_structures():
    try:
        from screener.options_scanner import load_oi_structure_cache
        return load_oi_structure_cache()
    except Exception as e:
        print(f"OI 快取: {e}")
        return []


def get_cboe_data():
    try:
        from screener.cboe_sentiment import load_cboe_cache
        return load_cboe_cache() or {}
    except Exception as e:
        print(f"CBOE 快取: {e}")
        return {}


def run_scan_background():
    try:
        from screener.merge import run_full_scan
        from screener.options_scanner import get_or_scan_options
        from screener.cboe_sentiment import get_cboe_sentiment

        run_full_scan()
        print("✅ 股票掃描完成")

        get_or_scan_options(force=True)
        print("✅ 期權掃描完成")

        get_cboe_sentiment(force=True)
        print("✅ CBOE 情緒完成")

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
    oi_structures = get_oi_structures()
    cboe = get_cboe_data()

    def render_index(idx):
        color = (
            "#22C55E" if idx["change_pct"] > 0
            else "#EF4444" if idx["change_pct"] < 0
            else "#A78BFA"
        )
        return f"""
        <div class="index-item">
            <div class="index-name">{idx['name']}</div>
            <div class="index-price">{idx['price']}</div>
            <div class="index-pt" style="color:{color}">{idx['change_pt_str']}</div>
            <div class="index-pct" style="color:{color}">{idx['change_pct_str']}</div>
        </div>
        """

    us_html = "".join(render_index(i) for i in us_indices)
    hsi_html = render_index(hsi) if hsi else ""

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

    # CBOE 情緒
    cboe_html = ""
    if cboe and (
        cboe.get("vix") is not None
        or cboe.get("index_pc") is not None
        or cboe.get("equity_pc") is not None
    ):
        vix = cboe.get("vix")
        vix_s = f"{vix}（{cboe.get('vix_label', '—')}）" if vix is not None else "—"
        ix = cboe.get("index_pc")
        ix_s = f"{ix}（{cboe.get('index_pc_label', '—')}）" if ix is not None else "—"
        eq = cboe.get("equity_pc")
        eq_s = f"{eq}（{cboe.get('equity_pc_label', '—')}）" if eq is not None else "—"
        summary = cboe.get("summary") or ""
        cboe_html = f"""
        <div class="options-box">
            <div class="options-title">📊 CBOE 情緒</div>
            <div class="opt-line">VIX：{vix_s}</div>
            <div class="opt-line">指數 Put/Call：{ix_s}</div>
            <div class="opt-line">Equity Put/Call：{eq_s}</div>
            <div class="opt-reason">{summary}</div>
        </div>
        """

    # 期權異動
    options_html = ""
    if options_alerts:
        def line(a):
            rec = a.get("recommendation") or a.get("option_type", "")
            reason = a.get("reason", "")
            main = (
                f"• {a['ticker']} | {rec} {a['strike']} | "
                f"到期 {a['expiry']} | 爆發 {a['vol_oi']}x | {a.get('moneyness', '')}"
            )
            if reason:
                return (
                    f"<div class='opt-line'>{main}"
                    f"<br><span class='opt-reason'>理由：{reason}</span></div>"
                )
            return f"<div class='opt-line'>{main}</div>"

        high = [a for a in options_alerts if a.get("level") == "high"]
        med = [a for a in options_alerts if a.get("level") == "medium"]
        low = [a for a in options_alerts if a.get("level") == "low"]
        options_html = f"""
        <div class="options-box">
            <div class="options-title">🚀 期權異動監測</div>
            {f'<div class="opt-level high">🔴 高關注</div>{"".join(line(a) for a in high)}' if high else ''}
            {f'<div class="opt-level medium">🟡 中等關注</div>{"".join(line(a) for a in med)}' if med else ''}
            {f'<div class="opt-level low">🟢 一般觀察</div>{"".join(line(a) for a in low)}' if low else ''}
            <div class="opt-disclaimer">※ 建議僅供參考，唔構成投資意見；賣出期權風險較高。</div>
        </div>
        """

    # OI 結構
    oi_html = ""
    if oi_structures:
        lines = []
        for s in oi_structures:
            spot = s.get("spot")
            if spot is None or (isinstance(spot, float) and spot != spot):
                continue
            cw = s.get("call_wall") if s.get("call_wall") is not None else "—"
            pw = s.get("put_wall") if s.get("put_wall") is not None else "—"
            mp = s.get("max_pain") if s.get("max_pain") is not None else "—"
            pcr = s.get("put_call_oi_ratio") if s.get("put_call_oi_ratio") is not None else "—"
            lines.append(
                f"<div class='opt-line'><b>{s['ticker']}</b> 現價 ${spot} | "
                f"Call Wall ${cw} | Put Wall ${pw} | Max Pain ${mp} | "
                f"P/C {pcr} ({s.get('bias', '—')})</div>"
            )
        if lines:
            oi_html = f"""
            <div class="options-box">
                <div class="options-title">📊 未平倉結構（Call / Put Wall · Max Pain）</div>
                {''.join(lines)}
            </div>
            """

    cards_html = ""
    if not stocks:
        cards_html = "<p style='color:#A78BFA;'>目前冇符合條件嘅股票</p>"
    else:
        signal_map = {
            "strong_buy": "🚀🚀🚀 強烈買入",
            "buy": "🚀 買入",
            "watch": "👀 觀察"
        }
        for s in stocks:
            tier = s.get("tier", "-")
            sig = signal_map.get(s.get("signal_type", "watch"), s.get("signal_type", ""))
            dist = s.get("distance_to_52w_high", 0)
            dist_t = f"已創新高 (+{dist}%)" if dist >= 0 else f"{dist}%"
            cards_html += f"""
            <div class="card">
                <div class="tier-badge tier-{tier}">Tier {tier}</div>
                <div class="ticker-line">📊 {s.get('ticker')}</div>
                <div class="company-name">({s.get('company_name', '')})</div>
                <div class="signal">{sig}</div>
                <div class="info">
                    <div>RS Rating：<b>{s.get('rs_rating')}</b></div>
                    <div>RSI：{s.get('rsi')}</div>
                    <div>MACD：{s.get('macd_status')}</div>
                    <div>趨勢：{s.get('trend')}</div>
                    <div>距離52週新高：{dist_t}</div>
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

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QuantFlow Dashboard</title>
<style>
* {{ box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0F0A1A; color: #F5F3FF; margin: 0; padding: 16px; min-height: 100vh;
}}
h1 {{ font-size: 1.5rem; margin: 0 0 6px; font-weight: 700; }}
h2 {{ font-size: 1.05rem; margin: 24px 0 12px; color: #C4B5FD; }}
.meta {{ color: #A78BFA; font-size: 0.9rem; margin-bottom: 16px; }}
.index-row {{
    display: flex; background: #1A1229; border-radius: 16px;
    padding: 14px 6px; margin-bottom: 10px; border: 1px solid #2E1F47;
}}
.index-item {{ flex: 1; text-align: center; min-width: 0; }}
.index-name {{ font-size: 0.72rem; color: #A78BFA; margin-bottom: 4px; }}
.index-price {{ font-size: 0.95rem; font-weight: 700; }}
.index-pt, .index-pct {{ font-size: 0.8rem; font-weight: 600; margin-top: 2px; }}
.options-box {{
    background: #1A1229; border-radius: 16px; padding: 16px;
    margin-bottom: 16px; border: 1px solid #2E1F47;
}}
.options-title {{ font-size: 1.05rem; font-weight: 700; margin-bottom: 12px; }}
.opt-level {{ font-size: 0.9rem; font-weight: 600; margin: 12px 0 6px; }}
.opt-level.high {{ color: #F87171; }}
.opt-level.medium {{ color: #FBBF24; }}
.opt-level.low {{ color: #4ADE80; }}
.opt-line {{ font-size: 0.85rem; color: #C4B5FD; line-height: 1.6; padding: 4px 0; }}
.opt-reason {{ font-size: 0.78rem; color: #A78BFA; }}
.opt-disclaimer {{ font-size: 0.75rem; color: #7C6A9A; margin-top: 12px; }}
.card {{
    background: #1A1229; border-radius: 16px; padding: 16px;
    margin-bottom: 14px; border: 1px solid #2E1F47;
}}
.tier-badge {{
    display: inline-block; font-size: 0.85rem; padding: 4px 14px;
    border-radius: 999px; font-weight: 700; margin-bottom: 10px;
}}
.tier-S {{ background: #E63946; color: #fff; font-weight: 800; }}
.tier-A {{ background: #F4A261; color: #1A1229; }}
.tier-B {{ background: #2A9D8F; color: #fff; }}
.tier-C {{ background: #E9C46A; color: #1A1229; }}
.tier-D {{ background: #457B9D; color: #fff; }}
.ticker-line {{ font-size: 1.25rem; font-weight: 700; }}
.company-name {{ font-size: 0.9rem; color: #A78BFA; margin: 2px 0 10px; }}
.signal {{ font-size: 1.05rem; margin-bottom: 12px; color: #DDD6FE; }}
.info {{ font-size: 0.9rem; color: #C4B5FD; line-height: 1.7; }}
.info b {{ color: #F5F3FF; }}
.price, .tp {{ margin-top: 8px; font-size: 0.85rem; color: #A78BFA; }}
.settings {{
    background: #1A1229; border-radius: 16px; padding: 18px;
    margin-bottom: 20px; border: 1px solid #2E1F47;
}}
label {{ display: block; margin: 12px 0 6px; color: #A78BFA; font-size: 0.9rem; }}
input[type=number] {{
    width: 100%; padding: 12px 14px; border-radius: 12px;
    border: 1px solid #2E1F47; background: #120C1F; color: #F5F3FF; font-size: 1rem;
}}
.checkbox-row {{ display: flex; align-items: center; gap: 10px; margin: 14px 0; }}
.checkbox-row label {{ margin: 0; color: #DDD6FE; }}
button {{
    width: 100%; padding: 14px; border: none; border-radius: 12px;
    font-size: 1rem; font-weight: 600; margin-top: 12px; cursor: pointer;
}}
.btn-primary {{ background: #8B5CF6; color: #fff; }}
.btn-scan {{ background: #7C3AED; color: #fff; }}
.scan-tip {{ text-align: center; color: #A78BFA; font-size: 0.85rem; margin-top: 8px; }}
#status {{
    text-align: center; padding: 8px; border-radius: 8px;
    margin-bottom: 12px; font-size: 0.9rem; display: none;
}}
#status.scanning {{ display: block; background: #2E1F47; color: #C4B5FD; }}
#status.done {{ display: block; background: #14532D; color: #86EFAC; }}
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
<div class="index-row">{us_html}</div>
<div class="index-row">{hsi_html}{fg_html}</div>
{cboe_html}
{options_html}
{oi_html}
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
    <form method="post" action="/run-scan" style="margin-top:8px" id="scan-form">
        <button type="submit" class="btn-scan" id="scan-btn">立即執行掃描</button>
    </form>
    <div class="scan-tip">掃描：股票 + 期權建議 + OI 結構 + CBOE 情緒</div>
</div>
<h2>掃描結果</h2>
{cards_html}
<script>
const p = location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(`${{p}}//${{location.host}}/ws`);
const st = document.getElementById('status');
const btn = document.getElementById('scan-btn');
ws.onmessage = (e) => {{
    const d = JSON.parse(e.data);
    if (d.type === 'scan_complete') {{
        st.className = 'done';
        st.textContent = '✅ 掃描完成，正在刷新...';
        setTimeout(() => location.reload(), 800);
    }} else if (d.type === 'scan_error') {{
        st.className = 'done';
        st.textContent = '❌ ' + (d.message || '');
    }}
}};
document.getElementById('scan-form').onsubmit = () => {{
    st.className = 'scanning';
    st.textContent = '⏳ 掃描中...';
    btn.disabled = true;
    btn.textContent = '掃描中...';
}};
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