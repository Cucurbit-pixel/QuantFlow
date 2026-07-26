"""
CBOE 情緒指標（免費近似版）
- VIX：恐懼／貪婪參考
- Put/Call：用主要 ETF 期權 OI 近似 Equity / Index 情緒
"""
from datetime import datetime, timedelta
from pathlib import Path
import json
import yfinance as yf
from screener.common import get_logger

logger = get_logger(__name__)

CACHE_PATH = Path("data/cboe_sentiment.json")
CACHE_MINUTES = 30


def _pc_label(ratio: float | None) -> str:
    if ratio is None:
        return "—"
    if ratio >= 1.2:
        return "偏防禦／偏空"
    if ratio >= 1.0:
        return "中性偏防禦"
    if ratio >= 0.7:
        return "中性偏多"
    return "偏多"


def _vix_label(vix: float | None) -> str:
    if vix is None:
        return "—"
    if vix >= 30:
        return "極度恐懼"
    if vix >= 25:
        return "恐懼"
    if vix >= 18:
        return "中性"
    if vix >= 15:
        return "偏貪婪"
    return "貪婪"


def _safe_float(x):
    try:
        v = float(x)
        if v != v:
            return None
        return v
    except Exception:
        return None


def _put_call_from_ticker(ticker: str) -> float | None:
    """用近月期權 OI 計算 Put/Call Ratio"""
    try:
        t = yf.Ticker(ticker)
        expiries = t.options
        if not expiries:
            return None
        chain = t.option_chain(expiries[0])
        call_oi = 0
        put_oi = 0
        if chain.calls is not None and not chain.calls.empty:
            call_oi = int(chain.calls["openInterest"].fillna(0).sum())
        if chain.puts is not None and not chain.puts.empty:
            put_oi = int(chain.puts["openInterest"].fillna(0).sum())
        if call_oi <= 0:
            return None
        return round(put_oi / call_oi, 2)
    except Exception as e:
        logger.warning(f"P/C {ticker} 失敗: {e}")
        return None


def _get_vix() -> float | None:
    try:
        hist = yf.Ticker("^VIX").history(period="5d")
        if hist is None or hist.empty:
            return None
        return _safe_float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.warning(f"VIX 失敗: {e}")
        return None


def fetch_cboe_sentiment() -> dict:
    """
    回傳結構:
    {
      "scan_time": "...",
      "vix": 18.5,
      "vix_label": "中性",
      "equity_pc": 0.85,      # 用 IWM/個股型 ETF 近似
      "equity_pc_label": "...",
      "index_pc": 1.05,       # 用 SPY/QQQ 近似
      "index_pc_label": "...",
      "summary": "..."
    }
    """
    vix = _get_vix()
    # Index 近似：SPY + QQQ 平均
    spy_pc = _put_call_from_ticker("SPY")
    qqq_pc = _put_call_from_ticker("QQQ")
    index_vals = [x for x in (spy_pc, qqq_pc) if x is not None]
    index_pc = round(sum(index_vals) / len(index_vals), 2) if index_vals else None

    # Equity 近似：IWM（小型股）較接近個股情緒
    equity_pc = _put_call_from_ticker("IWM")

    vix_l = _vix_label(vix)
    eq_l = _pc_label(equity_pc)
    ix_l = _pc_label(index_pc)

    # 一句摘要
    parts = []
    if vix is not None:
        parts.append(f"VIX {vix:.1f}（{vix_l}）")
    if index_pc is not None:
        parts.append(f"指數 P/C {index_pc}（{ix_l}）")
    if equity_pc is not None:
        parts.append(f"Equity P/C {equity_pc}（{eq_l}）")
    summary = "；".join(parts) if parts else "暫無 CBOE 情緒數據"

    return {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "vix": round(vix, 2) if vix is not None else None,
        "vix_label": vix_l,
        "equity_pc": equity_pc,
        "equity_pc_label": eq_l,
        "index_pc": index_pc,
        "index_pc_label": ix_l,
        "summary": summary,
    }


def save_cboe_cache(data: dict):
    Path("data").mkdir(exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cboe_cache() -> dict | None:
    if not CACHE_PATH.exists():
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        t = datetime.strptime(data.get("scan_time", "2000-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
        if datetime.now() - t > timedelta(minutes=CACHE_MINUTES):
            return None
        return data
    except Exception:
        return None


def get_cboe_sentiment(force: bool = False) -> dict:
    if not force:
        cached = load_cboe_cache()
        if cached:
            return cached
    data = fetch_cboe_sentiment()
    save_cboe_cache(data)
    return data