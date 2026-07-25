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
    scan_time = data.get("scan_time", "